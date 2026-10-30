"""离线产品工具回归：只读源码，API/vendor 使用 stub，产物仅写 pytest 临时目录。"""

import ast
import builtins
import hashlib
import json
import socket
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

REPO = Path(__file__).resolve().parents[1]
CASE = REPO / "ventures" / "ai_workflow_kit"
WORKFLOWS = CASE / "tools" / "test_workflows.py"
PDFS = CASE / "products" / "build_pdfs.py"
LINKS = CASE / "tools" / "fill_links.py"
AUTH = REPO / "capabilities" / "xhs_crawler" / "xhs_auth_helper.py"
FAKE_ENV = {"LLM_API_KEY": "offline-placeholder", "LLM_MODEL": "offline-test-model",
            "LLM_BASE_URL": "https://offline.invalid/v1"}


def forbidden(*args, **kwargs):
    raise AssertionError("offline test attempted forbidden I/O or import")


class OfflineRequestError(Exception):
    pass


class Response:
    def __init__(self, *, status=200, content="offline answer", finish="stop", payload=None):
        self.status_code = status
        self.payload = payload if payload is not None else {
            "choices": [{"message": {"content": content}, "finish_reason": finish}]
        }

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def load_offline(path, monkeypatch):
    """先读获准源码；执行期间禁止凭证读写、网络和第三方渲染/vendor 导入。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module = ModuleType(path.stem)
    module.__file__ = str(path)
    requests_stub = ModuleType("requests")
    requests_stub.RequestException = OfflineRequestError
    requests_stub.post = Mock(side_effect=forbidden)
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"spider_xhs", "xhs_auth_helper", "pymupdf", "markdown2", "dotenv"}:
            forbidden()
        return original_import(name, *args, **kwargs)

    with monkeypatch.context() as guard:
        guard.setitem(sys.modules, "requests", requests_stub)
        guard.setattr(builtins, "__import__", guarded_import)
        guard.setattr(builtins, "open", forbidden)
        for name in ("open", "read_text", "read_bytes", "write_text", "mkdir"):
            guard.setattr(Path, name, forbidden)
        guard.setattr(socket, "socket", forbidden)
        guard.setattr(socket, "create_connection", forbidden)
        exec(compile(tree, str(path), "exec"), module.__dict__)
    return module


@pytest.fixture
def workflow(monkeypatch):
    module = load_offline(WORKFLOWS, monkeypatch)
    monkeypatch.setattr(module, "load_env", Mock(side_effect=forbidden))
    monkeypatch.setattr(module.time, "sleep", Mock())
    return module


@pytest.mark.parametrize("cwd", [REPO, CASE])
def test_paths_and_imports_are_cwd_independent(cwd, monkeypatch):
    monkeypatch.chdir(cwd)
    workflow = load_offline(WORKFLOWS, monkeypatch)
    pdfs = load_offline(PDFS, monkeypatch)
    links = load_offline(LINKS, monkeypatch)
    assert workflow.CASE == pdfs.CASE == links.CASE == CASE
    assert workflow.REPO == pdfs.REPO == links.REPO == REPO
    assert workflow.KIT.parent == pdfs.KIT_DIR == CASE / "products" / "ai-office-workflows"
    assert workflow.KIT.is_file()
    assert workflow.KIT.parent / "qa" == workflow.QA_DIR
    assert links.DIST.parent == workflow.KIT.parent
    assert pdfs.FONT_REG == REPO / "capabilities" / "_shared" / "fonts" / "NotoSansSC-Regular.ttf"
    assert pdfs.FONT_BOLD.is_file()
    assert not hasattr(workflow, "ENV")


@pytest.mark.parametrize("start", [8000, 10**9])
@pytest.mark.parametrize("content", ["", "truncated body"])
def test_length_retry_is_bounded_even_with_partial_body(workflow, start, content):
    workflow.requests.post = Mock(return_value=Response(content=content, finish="length"))
    result = workflow.call_llm([{"role": "user", "content": "test"}], start, env=FAKE_ENV)
    tokens = [call.kwargs["json"]["max_tokens"] for call in workflow.requests.post.call_args_list]
    assert tokens == ([8000, 16000, 32000] if start == 8000 else [32000] * 3)
    assert len(result["attempts"]) == workflow.MAX_ATTEMPTS == 3
    assert result["status"] == "failed" and result["output"] is None
    assert result["error"] == "length_limit"
    assert all(attempt["output"] == content for attempt in result["attempts"])
    assert workflow.time.sleep.call_count == 2  # 不在最后一次失败后继续等待


@pytest.mark.parametrize("value", [True, 0, -1, 1.5])
def test_invalid_token_budget_does_not_call_api(workflow, value):
    with pytest.raises(ValueError):
        workflow.call_llm([], value, env=FAKE_ENV)
    workflow.requests.post.assert_not_called()


def test_mixed_failures_share_one_retry_budget(workflow):
    workflow.requests.post = Mock(side_effect=[
        Response(status=503), Response(content="partial", finish="length"), Response(),
    ])
    result = workflow.call_llm([], env=FAKE_ENV)
    assert result["status"] == "completed"
    assert result["output"] == "offline answer"
    assert [a["max_tokens"] for a in result["attempts"]] == [8000, 8000, 16000]
    assert workflow.requests.post.call_count == 3
    assert "passed" not in result


@pytest.mark.parametrize("response,expected_calls,error", [
    (Response(payload={"choices": [{"message": {"reasoning_content": "NOT AN ANSWER"},
                                     "finish_reason": "stop"}]}), 3, "empty_content"),
    (Response(payload={"error": {"message": "not evidence"}}), 3, "api_error"),
    (Response(payload=ValueError("bad json")), 3, "invalid_response"),
    (Response(payload={"choices": []}), 3, "invalid_response"),
    (Response(status=401), 1, "http_401"),
    (Response(status=429), 3, "http_429"),
    (Response(content="partial", finish="content_filter"), 1, "incomplete_response"),
    (Response(content="[API ERROR] service error"), 1, "api_error_content"),
])
def test_failed_responses_never_become_answers(workflow, response, expected_calls, error):
    workflow.requests.post = Mock(return_value=response)
    result = workflow.call_llm([], env=FAKE_ENV)
    assert result["status"] == "failed"
    assert result["output"] is None and result["error"] == error
    assert workflow.requests.post.call_count == expected_calls
    assert "NOT AN ANSWER" not in json.dumps(result)


def test_transport_exceptions_are_bounded_and_sanitized(workflow):
    workflow.requests.post = Mock(side_effect=OfflineRequestError("private-header-placeholder"))
    result = workflow.call_llm([], env=FAKE_ENV)
    assert result["status"] == "failed" and result["output"] is None
    assert workflow.requests.post.call_count == 3
    assert "private-header-placeholder" not in json.dumps(result)


def prepare_run(module, tmp_path, monkeypatch):
    kit = tmp_path / "kit.txt"
    kit.write_bytes("".join(f"```\r\nprompt-{i}\r\n```\r\n" for i in range(10)).encode("utf-8"))
    qa = tmp_path / "qa"
    qa.mkdir()
    monkeypatch.setattr(module, "KIT", kit)
    monkeypatch.setattr(module, "QA_DIR", qa)
    monkeypatch.setattr(module, "SCENARIOS", {
        1: {"name": "offline", "input": "fixture input", "followup": "fixture followup", "checks": ["manual check"]},
    })
    monkeypatch.setattr(module, "BASELINE", {1: "baseline {input}"})
    return kit, qa


def test_runs_preserve_original_evidence_and_bind_metadata(workflow, tmp_path, monkeypatch, capsys):
    kit, qa = prepare_run(workflow, tmp_path, monkeypatch)
    historic = {qa / "run-01-old.md": b"original evidence", qa / "summary.json": b'{"original": true}'}
    for path, content in historic.items():
        path.write_bytes(content)
    workflow.requests.post = Mock(return_value=Response())
    assert workflow.run(env=FAKE_ENV) == 0
    first = next(path for path in qa.iterdir() if path.is_dir())
    originals = {path: path.read_bytes() for path in first.iterdir()}
    assert workflow.run(env=FAKE_ENV) == 0
    runs = [path for path in qa.iterdir() if path.is_dir()]
    assert len(runs) == 2
    assert all(path.read_bytes() == content for path, content in {**historic, **originals}.items())
    for run_dir in runs:
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        entry = json.loads((run_dir / "run-01.json").read_text(encoding="utf-8"))
        assert summary["run_id"] == entry["run_id"] == run_dir.name
        assert summary["model"] == entry["model"] == FAKE_ENV["LLM_MODEL"]
        assert summary["manual_review_status"] == entry["manual_review_status"] == "pending"
        assert summary["entries"][0]["manual_review_status"] == "pending"
        assert summary["failed_calls"] == 0
        assert summary["source_files"]["kit"]["sha256"] == hashlib.sha256(kit.read_bytes()).hexdigest()
        assert summary["source_files"]["runner"]["sha256"] == hashlib.sha256(WORKFLOWS.read_bytes()).hexdigest()
        for key in ("prompt", "input", "followup"):
            assert entry[f"{key}_sha256"] == hashlib.sha256(entry[key].encode("utf-8")).hexdigest()
        assert entry["prompt"] == "prompt-0\n"
        assert entry["final_output"] == "offline answer"
        assert len(entry["rounds"]) == 2
        assert entry["rounds"][1]["messages"][-2] == {"role": "assistant", "content": "offline answer"}
        assert entry["baseline"]["messages"][0]["content"] == "baseline fixture input"
        for call in [*entry["rounds"], entry["baseline"]]:
            canonical = json.dumps(call["messages"], ensure_ascii=False, sort_keys=True).encode("utf-8")
            assert call["messages_sha256"] == hashlib.sha256(canonical).hexdigest()
        for record in (summary, entry, entry["rounds"][0]["result"]["attempts"][0]):
            for key in ("started_at_utc", "completed_at_utc"):
                assert datetime.fromisoformat(record[key]).utcoffset() == timedelta(0)
        with pytest.raises(FileExistsError):
            workflow.write_evidence(run_dir / "summary.json", {"overwrite": True})
        assert FAKE_ENV["LLM_API_KEY"] not in (run_dir / "summary.json").read_text(encoding="utf-8")
    assert "10/10" not in capsys.readouterr().out
    workflow.load_env.assert_not_called()


def test_run_failure_skips_followup_and_returns_nonzero(workflow, tmp_path, monkeypatch):
    _, qa = prepare_run(workflow, tmp_path, monkeypatch)
    monkeypatch.setattr(workflow, "BASELINE", {})
    workflow.requests.post = Mock(return_value=Response(status=401))
    workflow.load_env = Mock(return_value=FAKE_ENV)
    assert workflow.run() == 1
    workflow.load_env.assert_called_once_with()
    assert workflow.requests.post.call_count == 1
    run_dir = next(qa.iterdir())
    entry = json.loads((run_dir / "run-01.json").read_text(encoding="utf-8"))
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert entry["final_output"] is None and len(entry["rounds"]) == 1
    assert entry["execution_status"] == "failed"
    assert entry["manual_review_status"] == "pending"
    assert summary["failed_calls"] == 1


def test_run_id_collision_fails_before_api_or_overwrite(workflow, tmp_path, monkeypatch):
    _, qa = prepare_run(workflow, tmp_path, monkeypatch)
    fixed = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    monkeypatch.setattr(workflow, "datetime", SimpleNamespace(now=lambda tz: fixed))
    monkeypatch.setattr(workflow, "uuid4", lambda: SimpleNamespace(hex="fixed"))
    workflow.requests.post = Mock(return_value=Response())
    assert workflow.run(env=FAKE_ENV) == 0
    run_dir = next(qa.iterdir())
    original = {p: p.read_bytes() for p in run_dir.iterdir()}
    calls = workflow.requests.post.call_count
    with pytest.raises(FileExistsError):
        workflow.run(env=FAKE_ENV)
    assert calls == workflow.requests.post.call_count
    assert all(path.read_bytes() == data for path, data in original.items())


def test_delivery_sources_exclude_internal_drafts(monkeypatch):
    module = load_offline(PDFS, monkeypatch)
    names = [p.name for p in module.delivery_sources()]
    expected = [sorted(module.KIT_DIR.glob(f"workflow-{i:02d}-*.md"))[0].name for i in range(1, 11)]
    expected.append("anti-bs-cheat-sheet.md")
    assert names == expected
    for forbidden_name in ("README.md", "workflows-outline.md", "listing-mianbaoduo.md",
                           "listing-xianyu.md", "launch-reddit.md", "launch-xhs-note.md"):
        assert forbidden_name not in names


def test_pdf_check_is_path_only_and_css_preserves_braces(tmp_path, monkeypatch):
    module = load_offline(PDFS, monkeypatch)
    monkeypatch.setattr(module, "DIST_DIR", tmp_path / "must-not-create")
    monkeypatch.setattr(module, "build_cn", forbidden)
    monkeypatch.setattr(module, "build_en", forbidden)
    with monkeypatch.context() as guard:
        guard.setitem(sys.modules, "pymupdf", None)
        guard.setitem(sys.modules, "markdown2", None)
        guard.setattr(Path, "mkdir", forbidden)
        guard.setattr(Path, "read_bytes", forbidden)
        guard.setattr(Path, "read_text", forbidden)
        assert module.main(["--check"]) == 0
    assert not module.DIST_DIR.exists()
    assert '@font-face { font-family: noto; src: url("' in module.CSS
    assert module.FONT_REG.as_posix() in module.CSS
    assert module.FONT_BOLD.as_posix() in module.CSS
    assert "body { font-family: noto;" in module.CSS
    assert module.CSS.count("{") == module.CSS.count("}")
    tree = ast.parse(PDFS.read_text(encoding="utf-8"))
    css = next(node for node in tree.body if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == "CSS" for target in node.targets))
    assert not any(isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) for node in ast.walk(css))


@pytest.mark.parametrize("missing", ["FONT_REG", "FONT_BOLD", "KIT_DIR"])
def test_pdf_missing_paths_fail_before_build(tmp_path, monkeypatch, missing):
    module = load_offline(PDFS, monkeypatch)
    monkeypatch.setattr(module, missing, tmp_path / "missing")
    monkeypatch.setattr(module, "DIST_DIR", tmp_path / "must-not-create")
    monkeypatch.setattr(module, "build_cn", forbidden)
    assert module.main(["--cn"]) == 1
    assert module.main(["--check"]) == 1
    with pytest.raises(FileNotFoundError):
        module.render_pdf("", tmp_path / "must-not-render.pdf")
    assert not module.DIST_DIR.exists()


def test_links_only_change_draft_and_preserve_pending_review(tmp_path, monkeypatch, capsys):
    module = load_offline(LINKS, monkeypatch)
    draft = tmp_path / "draft.txt"
    draft.write_text("审核状态待确认\n## ①\n【面包多链接】\n## ④\n"
                     "[link](https://mbd.pub/o/bread/old?from=old)。\n", encoding="utf-8")
    history = tmp_path / "history.txt"
    history.write_text("（平台/过审状态待确认，链接待回填）", encoding="utf-8")
    actions = tmp_path / "actions.csv"
    actions.write_text("status,pending\n", encoding="utf-8")
    untouched = {history: history.read_bytes(), actions: actions.read_bytes()}
    monkeypatch.setattr(module, "DIST", draft)
    monkeypatch.setattr(sys, "argv", [str(LINKS), "https://mbd.pub/o/bread/new?from=old"])
    original_open = Path.open

    def only_draft(path, *args, **kwargs):
        assert path == draft, f"unexpected I/O: {path}"
        return original_open(path, *args, **kwargs)

    with monkeypatch.context() as guard:
        guard.setattr(Path, "open", only_draft)
        assert module.main() == 0
        assert module.fill_distribution("https://mbd.pub/o/bread/new") == 0
    text = draft.read_text(encoding="utf-8")
    assert "审核状态待确认" in text
    assert "https://mbd.pub/o/bread/new?from=wechat" in text
    assert "[link](https://mbd.pub/o/bread/new?from=zhihu-a)。" in text
    assert all(path.read_bytes() == data for path, data in untouched.items())
    assert not hasattr(module, "fill_plan")
    output = capsys.readouterr().out
    assert "不代表平台审核通过" in output and "不会自动发布" in output
    assert str(REPO / "cockpit" / "actions.csv") in output
    assert "经营记录未修改" in output


@pytest.mark.parametrize("argument", ["--pc", "--creator"])
def test_auth_cli_reports_status_without_reading_cookie(argument, monkeypatch, capsys):
    tree = ast.parse(AUTH.read_text(encoding="utf-8"))
    guard = next(node for node in tree.body if isinstance(node, ast.If)
                 and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name)
                 and node.test.left.id == "__name__")

    class AuthTrap:
        @property
        def cookies(self):
            forbidden()

    login = Mock(return_value=AuthTrap())
    namespace = {"__name__": "__main__", "get_pc_auth": login, "get_creator_auth": login,
                 "clear_all_cookies": forbidden}
    monkeypatch.setattr(sys, "argv", [str(AUTH), argument])
    with monkeypatch.context() as context:
        context.setattr(Path, "open", forbidden)
        context.setattr(socket, "socket", forbidden)
        exec(compile(ast.Module(body=[guard], type_ignores=[]), str(AUTH), "exec"), namespace)
    login.assert_called_once_with()
    output = capsys.readouterr().out
    assert "认证成功" in output and "不输出 Cookie" in output
