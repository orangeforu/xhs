"""Pulse input and connector tests: temporary inputs/configs, never real HTTP."""

import csv
import io
import json
import socket
import sys
import urllib.error
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

PULSE = Path(__file__).resolve().parents[1] / "capabilities" / "pulse"
sys.path.insert(0, str(PULSE))

import heartbeat  # noqa: E402
import push  # noqa: E402

TODAY = date(2026, 10, 30)  # Friday must not outrank explicit deadlines.
SECRET = "FAKE_TOKEN_https://invalid.example/private_body"


def forbid_network(*args, **kwargs):
    raise AssertionError("TEST_NETWORK_FORBIDDEN")


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    monkeypatch.setattr(socket, "socket", forbid_network)
    monkeypatch.setattr(push, "_opener", forbid_network)
    monkeypatch.setattr(push, "DEDICATED_PUSH_JSON", tmp_path / "dedicated.json")
    monkeypatch.setattr(push, "XIANYU_PUSH_JSON", tmp_path / "shared.json")
    monkeypatch.setattr(heartbeat, "REPO", tmp_path / "repo")


def write_actions(root, rows):
    with (root / "cockpit" / "actions.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=heartbeat.ACTION_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def action(identity="a1", due=None, **overrides):
    row = {
        "action_id": identity,
        "venture": "demo",
        "status": "pending",
        "owner": "tester",
        "opened_on": "2026-01-01",
        "due_on": (due or TODAY).isoformat(),
        "next_action": f"任务-{identity}",
        "evidence": "fixture.md",
        "decision_scope": "L0",
    }
    row.update(overrides)
    return row


def make_repo(root):
    (root / "cockpit").mkdir(parents=True)
    (root / "cockpit" / "status.md").write_text(
        "# 状态\n\n## 本周焦点（本周五更新）\n\n  - [ ] 焦点甲\n- [x] 已完成\n- [ ] 焦点乙\n\n## 下节\n- [ ] 不纳入\n",
        encoding="utf-8",
    )
    for name, status in [("demo", "selling"), ("closed", "closed"), ("_template", "idea")]:
        path = root / "ventures" / name
        path.mkdir(parents=True)
        (path / "venture.md").write_text(
            f'# {name}\n\n```yaml\nstatus: "{status}" # comment\n'
            f"opened: 9999-99-99\nstop_loss: {TODAY.isoformat()}\n```\n"
            "正文 status: closed\n正文伪日期 2026-02-31\n",
            encoding="utf-8",
        )
    write_actions(root, [action()])
    return root


@pytest.fixture()
def fake_repo(tmp_path):
    return make_repo(tmp_path / "repo")


def test_deadlines_overdue_inclusive_and_action_statuses(fake_repo):
    write_actions(
        fake_repo,
        [
            action("old", TODAY - timedelta(days=90)),
            action("today"),
            action("edge", TODAY + timedelta(days=14), status="blocked"),
            action("far", TODAY + timedelta(days=15)),
            action("blank", due_on=""),
            action("done", status="done"),
            action("cancelled", status="cancelled"),
        ],
    )
    assert [item.action_id for item in heartbeat.due_actions(fake_repo, TODAY)] == ["old", "today", "edge"]
    assert heartbeat.key_dates(fake_repo, TODAY)[0] == ("demo", TODAY - timedelta(days=90))


def test_closed_template_unknown_and_governance(fake_repo):
    write_actions(
        fake_repo,
        [action(name, venture=name) for name in ["closed", "_template", "unknown", "../demo", "governance", "demo"]],
    )
    warnings = []
    result = heartbeat.due_actions(fake_repo, TODAY, warnings)
    assert {item.venture for item in result} == {"demo", "governance"}
    assert "ACTION_VENTURE_UNKNOWN" in warnings


@pytest.mark.parametrize(
    "source,expected",
    [
        ("# case\n```yaml\nstatus: closed # selling\n```\nstatus: selling\n", "closed"),
        ("---\nstatus: 'selling' # closed\n---\nstatus: closed\n", "selling"),
        ('---\n"status": "planning"\nother:\n  status: closed\n---\n', "planning"),
        ("```yaml\nstatus: selling\nnotes: |\n  status: closed\n```\n", "selling"),
        ("```yaml\nother:\n  status: closed\n```\nstatus: selling\n", None),
        ("```yaml\nstatus: selling\nstatus: closed\n```\n", None),
        ("```yaml\nstatus: selling\nstatus : closed\n```\n", None),
        ("```yaml\nstatus : closed # comment\n```\n", "closed"),
        ("```yaml\nstatus:closed\n```\n", None),
        ('```yaml\nother: "multiline\nstatus: selling\nend"\n```\n', None),
        ('```yaml\nstatus: "closed # not comment"\n```\n', None),
        ("```yaml\nstatus: selling#closed\n```\n", None),
        ("```yaml\nstatus: *alias\n```\n", None),
        ("```yaml\nstatus: |\n  closed\n```\n", None),
        ("```yaml\nstatus: strange\n```\n", None),
        ("# case\nstatus: selling\n", None),
        ("```yaml\nstatus: closed\n", None),
    ],
)
def test_yaml_status_only_metadata(tmp_path, source, expected):
    path = tmp_path / "venture.md"
    path.write_text(source, encoding="utf-8")
    warnings = []
    assert heartbeat.venture_status(path, warnings) == expected
    assert bool(warnings) is (expected is None)


def test_invalid_venture_skipped_and_no_prose_date_scanning(fake_repo):
    path = fake_repo / "ventures" / "demo" / "venture.md"
    path.write_text(f"stop_loss: {TODAY}\nstatus: selling\n", encoding="utf-8")
    warnings = []
    assert heartbeat.due_actions(fake_repo, TODAY, warnings) == []
    assert "VENTURE_METADATA_INVALID" in warnings
    path.write_text(f"```yaml\nstatus: selling\nstop_loss: {TODAY}\n```\n", encoding="utf-8")
    write_actions(fake_repo, [])
    assert heartbeat.key_dates(fake_repo, TODAY) == []


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"due_on": "2026-02-31"}, "ACTION_DATE_INVALID"),
        ({"due_on": "20261030"}, "ACTION_DATE_INVALID"),
        ({"opened_on": "9999-99-99"}, "ACTION_DATE_INVALID"),
        ({"opened_on": ""}, "ACTION_DATE_INVALID"),
        ({"status": SECRET}, "ACTION_STATUS_INVALID"),
        ({"next_action": ""}, "ACTION_ROW_INVALID"),
        ({"action_id": ""}, "ACTION_ROW_INVALID"),
    ],
)
def test_bad_rows_warn_without_crashing_or_echoing(fake_repo, changes, code):
    write_actions(fake_repo, [action("bad", **changes), action("good")])
    warnings = []
    assert [item.action_id for item in heartbeat.due_actions(fake_repo, TODAY, warnings)] == ["good"]
    assert code in warnings
    assert SECRET not in str(warnings)


def test_duplicate_ids_all_skipped(fake_repo):
    write_actions(fake_repo, [action("same"), action("same", status="done")])
    warnings = []
    assert heartbeat.due_actions(fake_repo, TODAY, warnings) == []
    assert "ACTION_DUPLICATE_ID" in warnings


@pytest.mark.parametrize("text", ["bad,header\n", 'action_id,"unclosed\n', "\xff"])
def test_bad_csv_safe_warning(fake_repo, text):
    (fake_repo / "cockpit" / "actions.csv").write_bytes(text.encode("latin-1"))
    warnings = []
    assert heartbeat.due_actions(fake_repo, TODAY, warnings) == []
    assert "ACTIONS_INVALID" in warnings


def test_truncated_csv_row(fake_repo):
    path = fake_repo / "cockpit" / "actions.csv"
    path.write_text(",".join(heartbeat.ACTION_FIELDS) + "\nshort,demo\n", encoding="utf-8")
    warnings = []
    assert heartbeat.due_actions(fake_repo, TODAY, warnings) == []
    assert warnings == ["ACTION_ROW_INVALID"]


def test_missing_csv_is_reported(fake_repo):
    (fake_repo / "cockpit" / "actions.csv").unlink()
    warnings = []
    heartbeat.build_brief(fake_repo, TODAY, warnings)
    assert "ACTIONS_MISSING" in warnings


def test_three_items_deadlines_before_focus_even_on_friday(fake_repo):
    write_actions(fake_repo, [action("today"), action("old", TODAY - timedelta(days=2))])
    brief, message = heartbeat.build_brief(fake_repo, TODAY)
    todo = brief.split("## 今日三件事\n")[1].split("\n\n")[0]
    assert len(todo.splitlines()) == 3
    assert todo.index("任务-old") < todo.index("任务-today") < todo.index("焦点甲")
    assert "焦点乙" not in todo and "已完成" not in brief
    assert "逾期 2 天" in todo and "今日到期" in todo
    assert message == brief
    assert heartbeat.week_focus(fake_repo) == ["焦点甲", "焦点乙"]


def test_more_than_three_actions_have_full_deadline_list(fake_repo):
    write_actions(fake_repo, [action(f"a{i}") for i in range(5)])
    brief, _ = heartbeat.build_brief(fake_repo, TODAY)
    assert "3. " in brief and "4. " not in brief
    assert "焦点甲" not in brief
    assert "demo/a4:" in brief


def test_journal_invalid_names_and_future_date(fake_repo):
    journal = fake_repo / "cockpit" / "journal"
    journal.mkdir()
    for name in ["README", "2026-99-99", "20261029", "2026-10-25", "2099-01-01"]:
        (journal / f"{name}.md").write_text("", encoding="utf-8")
    warnings = []
    assert heartbeat.journal_stale_days(journal, TODAY, warnings) == 5
    assert set(warnings) == {"JOURNAL_NAME_INVALID", "JOURNAL_FUTURE_DATE"}
    brief, _ = heartbeat.build_brief(fake_repo, TODAY)
    assert "JOURNAL_STALE" in brief


def test_no_valid_journal_date_returns_none(tmp_path):
    (tmp_path / "notes.md").write_text("", encoding="utf-8")
    assert heartbeat.journal_stale_days(tmp_path, TODAY, []) is None


def config(path, provider="pushplus", key=SECRET):
    path.write_text(json.dumps({"provider": provider, "key": key}), encoding="utf-8")
    return path


def test_dedicated_then_shared_then_missing(tmp_path):
    dedicated, shared = tmp_path / "dedicated.json", tmp_path / "shared.json"
    config(dedicated, "pushplus", "FAKE_DEDICATED")
    config(shared, "serverchan", "FAKE_SHARED")
    assert push.load_channel() == ("pushplus", "FAKE_DEDICATED")
    dedicated.unlink()
    assert push.load_channel() == ("serverchan", "FAKE_SHARED")
    shared.unlink()
    assert push.load_channel() == ("", "")
    assert push.push_wechat("title", "body") == (False, "CONFIG_MISSING")


@pytest.mark.parametrize("content", ["broken " + SECRET, "[]", '{"provider":1,"key":"x"}', "{}"])
def test_invalid_config_never_falls_back_or_leaks(tmp_path, content):
    (tmp_path / "dedicated.json").write_text(content, encoding="utf-8")
    config(tmp_path / "shared.json")
    with pytest.raises(push.ChannelError, match="^CONFIG_INVALID$"):
        push.load_channel()
    assert push.push_wechat("title", "body") == (False, "CONFIG_INVALID")


def test_unsupported_provider_does_not_echo_input(tmp_path):
    path = config(tmp_path / "config.json", SECRET)
    assert push.push_wechat("title", "body", config_paths=[path]) == (False, "UNSUPPORTED_PROVIDER")


@pytest.mark.parametrize(
    "provider,field,code", [("serverchan", "code", 0), ("pushplus", "code", 200), ("wecom", "errcode", 0)]
)
@pytest.mark.parametrize("success", [True, False])
def test_provider_receipts_only_safe_codes(tmp_path, provider, field, code, success):
    path = config(tmp_path / "config.json", provider)
    receipt = {field: code if success else 12345, "message": SECRET, "msg": SECRET, "errmsg": SECRET}
    opener = Mock()
    opener.open.return_value = io.BytesIO(json.dumps(receipt).encode())
    result = push.push_wechat("title", SECRET, config_paths=[path], opener_factory=lambda: opener)
    assert result == ((True, "OK") if success else (False, "REJECTED"))
    opener.open.assert_called_once()
    request = opener.open.call_args.args[0]
    assert request.method == "POST"
    assert "title" not in request.full_url
    if provider == "pushplus":
        assert "private_body" not in request.full_url


@pytest.mark.parametrize("receipt", [b"not-json", b"{}", b"[]", b'{"code":true}', b'{"code":"200"}'])
def test_malformed_response_is_unknown(tmp_path, receipt):
    opener = Mock()
    opener.open.return_value = io.BytesIO(receipt)
    assert push.push_wechat("t", "d", config_paths=[config(tmp_path / "c.json")], opener_factory=lambda: opener) == (
        False,
        "DELIVERY_UNKNOWN",
    )


@pytest.mark.parametrize("exception", [TimeoutError(SECRET), urllib.error.URLError(SECRET), RuntimeError(SECRET)])
def test_transport_exception_never_leaks(tmp_path, exception, capsys):
    opener = Mock()
    opener.open.side_effect = exception
    result = push.push_wechat("t", SECRET, config_paths=[config(tmp_path / "c.json")], opener_factory=lambda: opener)
    assert result == (False, "DELIVERY_UNKNOWN")
    assert SECRET not in str(result) + str(capsys.readouterr())


def test_http_error_body_is_not_read(tmp_path):
    body = Mock()
    error = urllib.error.HTTPError("https://invalid.example/" + SECRET, 503, SECRET, {}, body)
    opener = Mock()
    opener.open.side_effect = error
    assert push.push_wechat("t", "d", config_paths=[config(tmp_path / "c.json")], opener_factory=lambda: opener) == (
        False,
        "DELIVERY_UNKNOWN",
    )
    body.read.assert_not_called()
