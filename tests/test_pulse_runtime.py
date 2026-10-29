"""Offline runtime/locking/log tests; no real tasks, configuration or notifications."""

import json
import os
import re
import socket
import subprocess
import sys
from datetime import timedelta
from threading import Event, Thread
from unittest.mock import Mock

import pytest
from test_pulse import PULSE, SECRET, TODAY, config, forbid_network, heartbeat, make_repo, push


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    monkeypatch.setattr(socket, "socket", forbid_network)
    monkeypatch.setattr(push, "_opener", forbid_network)
    monkeypatch.setattr(push, "DEDICATED_PUSH_JSON", tmp_path / "dedicated.json")
    monkeypatch.setattr(push, "XIANYU_PUSH_JSON", tmp_path / "shared.json")
    monkeypatch.setattr(heartbeat, "REPO", tmp_path / "repo")


@pytest.fixture()
def root(tmp_path):
    return make_repo(tmp_path / "repo")


def receipt(root):
    return json.loads((root / ".cache" / "pulse_last_run.json").read_text(encoding="utf-8"))


def test_success_state_and_same_day_dedup_even_retry(root, capsys):
    sender = Mock(return_value=(True, "OK"))
    assert heartbeat.main([], repo=root, today=TODAY, sender=sender) == 0
    state = receipt(root)
    assert state["status"] == "succeeded" and state["delivery"] == "delivered"
    assert state["started_at"] and state["finished_at"]
    assert (root / "cockpit" / "journal" / f"{TODAY}.md").is_file()
    assert not (root / ".cache" / "pulse.lock").exists()
    assert heartbeat.main([], repo=root, today=TODAY, sender=sender) == 0
    assert heartbeat.main(["--retry"], repo=root, today=TODAY, sender=sender) == 0
    assert sender.call_count == 1 and receipt(root) == state
    output = capsys.readouterr().out
    assert "ALREADY_SUCCEEDED" in output and "任务" not in output


def test_next_day_can_send_after_success(root):
    sender = Mock(return_value=(True, "OK"))
    assert heartbeat.main([], repo=root, today=TODAY, sender=sender) == 0
    assert heartbeat.main([], repo=root, today=TODAY + timedelta(days=1), sender=sender) == 0
    assert sender.call_count == 2


def test_known_failure_requires_explicit_retry(root, capsys):
    sender = Mock(side_effect=[(False, "REJECTED"), (True, "OK")])
    assert heartbeat.main([], repo=root, today=TODAY, sender=sender) != 0
    state = receipt(root)
    assert state["status"] == "failed" and state["delivery"] == "rejected"
    assert state["finished_at"] and state["error_code"] == "REJECTED"
    assert heartbeat.main([], repo=root, today=TODAY, sender=sender) != 0
    assert sender.call_count == 1 and receipt(root) == state
    assert "RETRY_REQUIRED" in capsys.readouterr().out
    assert heartbeat.main(["--retry"], repo=root, today=TODAY, sender=sender) == 0
    assert sender.call_count == 2 and receipt(root)["status"] == "succeeded"


def test_known_failure_allows_next_day_attempt(root):
    sender = Mock(return_value=(False, "REJECTED"))
    assert heartbeat.main([], repo=root, today=TODAY, sender=sender) != 0
    assert heartbeat.main([], repo=root, today=TODAY + timedelta(days=1), sender=sender) != 0
    assert sender.call_count == 2


def test_no_configuration_records_failure_without_http(root):
    assert heartbeat.main([], repo=root, today=TODAY) != 0
    state = receipt(root)
    assert state["status"] == "failed"
    assert state["delivery"] == "not_sent" and state["error_code"] == "CONFIG_MISSING"
    assert state["started_at"] and state["finished_at"]


@pytest.mark.parametrize("result", [(False, "DELIVERY_UNKNOWN"), (False, SECRET), (True, SECRET), None, {}, (1, "OK")])
def test_unknown_delivery_blocks_retry_and_future_days(root, result, capsys):
    sender = Mock(return_value=result)
    assert heartbeat.main([], repo=root, today=TODAY, sender=sender) != 0
    state = receipt(root)
    assert state["status"] == "delivery_unknown" and state["delivery"] == "unknown"
    assert state["finished_at"]
    for day in [TODAY, TODAY + timedelta(days=1)]:
        assert heartbeat.main(["--retry"], repo=root, today=day, sender=sender) != 0
    assert sender.call_count == 1
    output = capsys.readouterr().out
    assert "MANUAL_CHECK" in output and SECRET not in output + json.dumps(receipt(root))


@pytest.mark.parametrize("exception", [RuntimeError(SECRET), KeyboardInterrupt(SECRET)])
def test_exception_during_send_is_unknown_and_sanitized(root, exception, capsys):
    sender = Mock(side_effect=exception)
    assert heartbeat.main([], repo=root, today=TODAY, sender=sender) != 0
    state = receipt(root)
    assert state["status"] == "delivery_unknown" and state["error_code"] == "DELIVERY_UNKNOWN"
    assert SECRET not in json.dumps(state) + str(capsys.readouterr())


def test_before_send_failure_leaves_safe_failed_state(root, monkeypatch, capsys):
    monkeypatch.setattr(heartbeat, "build_brief", Mock(side_effect=ValueError(SECRET)))
    sender = Mock()
    assert heartbeat.main([], repo=root, today=TODAY, sender=sender) != 0
    state = receipt(root)
    assert state["status"] == "failed" and state["delivery"] == "not_sent"
    assert state["error_code"] == "RUN_FAILED" and state["finished_at"]
    sender.assert_not_called()
    assert SECRET not in str(capsys.readouterr()) + json.dumps(state)


def test_start_and_unknown_are_durable_before_send(root):
    snapshots = []

    def sender(title, body):
        snapshots.append(receipt(root))
        assert (root / ".cache" / "pulse.lock").exists()
        return True, "OK"

    assert heartbeat.main([], repo=root, today=TODAY, sender=sender) == 0
    assert snapshots[0]["status"] == "running" and snapshots[0]["delivery"] == "unknown"
    assert snapshots[0]["finished_at"] is None


def test_final_write_failure_preserves_unknown_to_block_resend(root, monkeypatch):
    original = heartbeat._save_state

    def fail_success(path, state):
        if state["status"] == "succeeded":
            raise OSError(SECRET)
        original(path, state)

    monkeypatch.setattr(heartbeat, "_save_state", fail_success)
    sender = Mock(return_value=(True, "OK"))
    assert heartbeat.main([], repo=root, today=TODAY, sender=sender) != 0
    assert receipt(root)["delivery"] == "unknown"
    monkeypatch.setattr(heartbeat, "_save_state", original)
    assert heartbeat.main(["--retry"], repo=root, today=TODAY, sender=sender) != 0
    assert sender.call_count == 1


def test_initial_write_failure_never_sends(root, monkeypatch, capsys):
    monkeypatch.setattr(heartbeat, "_save_state", Mock(side_effect=OSError(SECRET)))
    sender = Mock()
    assert heartbeat.main([], repo=root, today=TODAY, sender=sender) != 0
    sender.assert_not_called()
    assert SECRET not in str(capsys.readouterr())


@pytest.mark.parametrize("contents", [SECRET, "[]", '{"version":1}', '{"version":9}'])
def test_corrupt_state_fails_closed_and_rewrites_safe_state(root, contents, capsys):
    (root / ".cache").mkdir()
    (root / ".cache" / "pulse_last_run.json").write_text(contents, encoding="utf-8")
    sender = Mock()
    assert heartbeat.main(["--retry"], repo=root, today=TODAY, sender=sender) != 0
    sender.assert_not_called()
    state = receipt(root)
    assert state["status"] == "delivery_unknown"
    assert state["error_code"] == "STATE_INVALID_MANUAL_CHECK"
    assert SECRET not in json.dumps(state) + str(capsys.readouterr())


@pytest.mark.parametrize("delivery", ["not_sent", "unknown"])
def test_abandoned_running_state_requires_retry_or_manual_check(root, delivery):
    (root / ".cache").mkdir()
    state = heartbeat._new_state(TODAY)
    state["delivery"] = delivery
    heartbeat._save_state(root / ".cache" / "pulse_last_run.json", state)
    sender = Mock(return_value=(True, "OK"))
    assert heartbeat.main([], repo=root, today=TODAY, sender=sender) != 0
    sender.assert_not_called()
    result = heartbeat.main(["--retry"], repo=root, today=TODAY, sender=sender)
    assert (result == 0) is (delivery == "not_sent")


def test_existing_lock_is_not_deleted_or_overwritten(root, capsys):
    cache = root / ".cache"
    cache.mkdir()
    lock = cache / "pulse.lock"
    lock.write_text("owner", encoding="utf-8")
    sender = Mock()
    for args in [[], ["--retry"]]:
        assert heartbeat.main(args, repo=root, today=TODAY, sender=sender) != 0
    assert lock.read_text(encoding="utf-8") == "owner"
    assert not (cache / "pulse_last_run.json").exists()
    assert "LOCK_BUSY_MANUAL_CHECK" in capsys.readouterr().out
    sender.assert_not_called()


def test_concurrent_calls_only_one_sender(root):
    entered, release = Event(), Event()
    outcomes = []

    def sender(title, body):
        entered.set()
        assert release.wait(timeout=10)
        return True, "OK"

    first_sender = Mock(side_effect=sender)
    other_sender = Mock()
    worker = Thread(target=lambda: outcomes.append(heartbeat.main([], repo=root, today=TODAY, sender=first_sender)))
    worker.start()
    try:
        assert entered.wait(timeout=10)
        incumbent = receipt(root)
        assert heartbeat.main(["--retry"], repo=root, today=TODAY, sender=other_sender) != 0
        assert receipt(root) == incumbent
    finally:
        release.set()
        worker.join(timeout=10)
    assert not worker.is_alive() and outcomes == [0]
    first_sender.assert_called_once()
    other_sender.assert_not_called()


def test_dry_run_no_files_config_or_sender_even_with_lock(root, monkeypatch, capsys):
    cache = root / ".cache"
    cache.mkdir()
    (cache / "pulse.lock").write_text("locked", encoding="utf-8")
    (cache / "pulse_last_run.json").write_text(SECRET, encoding="utf-8")
    config(cache / "pulse_push.json")
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    loader, sender = Mock(side_effect=AssertionError("CONFIG_ACCESS_FORBIDDEN")), Mock()
    monkeypatch.setattr(push, "load_channel", loader)
    assert heartbeat.main(["--dry-run", "--retry"], repo=root, today=TODAY, sender=sender) == 0
    after = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    assert before == after
    loader.assert_not_called()
    sender.assert_not_called()
    assert "今日三件事" in capsys.readouterr().out


def test_dry_run_fresh_root_does_not_create_cache(root):
    assert heartbeat.main(["--dry-run"], repo=root, today=TODAY) == 0
    assert not (root / ".cache").exists()
    assert not (root / "cockpit" / "journal").exists()


def test_direct_cli_preview_without_bytecode_writes(root):
    scripts = root / "capabilities" / "pulse"
    scripts.mkdir(parents=True)
    for filename in ["heartbeat.py", "push.py"]:
        (scripts / filename).write_bytes((PULSE / filename).read_bytes())
    before = {path.relative_to(root) for path in root.rglob("*")}
    env = dict(os.environ, PYTHONUTF8="1")
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    result = subprocess.run(
        [sys.executable, str(scripts / "heartbeat.py"), "--dry-run"],
        env=env,
        capture_output=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )
    assert result.returncode == 0 and "今日三件事" in result.stdout
    assert before == {path.relative_to(root) for path in root.rglob("*")}


def test_invalid_cli_arguments_do_not_echo_secrets(root, capsys):
    assert heartbeat.main(["--" + SECRET], repo=root, today=TODAY) != 0
    assert SECRET not in str(capsys.readouterr())
    assert not (root / ".cache").exists()


def test_focus_does_not_duplicate_an_explicit_action(root):
    focus = root / "cockpit" / "status.md"
    focus.write_text("## 本周焦点\n- [ ] Follow a1\n- [ ] Independent task\n", encoding="utf-8")
    brief, _ = heartbeat.build_brief(root, TODAY)
    todo = brief.split("## 到期提醒")[0]
    assert "Follow a1" not in todo and "Independent task" in todo


def test_warnings_in_receipt_do_not_include_action_content(root):
    from test_pulse import action, write_actions

    write_actions(root, [action(status=SECRET)])
    sender = Mock(return_value=(True, "OK"))
    assert heartbeat.main([], repo=root, today=TODAY, sender=sender) == 0
    state = receipt(root)
    assert "ACTION_STATUS_INVALID" in state["warnings"]
    assert SECRET not in json.dumps(state)


@pytest.mark.parametrize("filename", ["run_heartbeat.bat", "安装每日心跳.bat"])
def test_batch_ascii_crlf_and_no_hardcoded_drive(filename):
    data = (PULSE / filename).read_bytes()
    text = data.decode("ascii")
    assert b"\r\n" in data and b"\n" not in data.replace(b"\r\n", b"")
    assert not re.search(r"[A-Za-z]:[\\/]", text)
    assert "start " not in text.lower() and "pythonw" not in text.lower()
    if filename == "run_heartbeat.bat":
        assert 'set "PYTHON_EXE=python"' in text
        assert '"%PYTHON_EXE%" -B "%~dp0heartbeat.py"' in text
        assert "2>&1" in text and "exit /b %PULSE_EXIT%" in text
    else:
        assert 'if /i not "%~1"=="--install"' in text
        assert "choice /C NY" in text and "if not errorlevel 2 exit /b 1" in text
        command = next(line for line in text.splitlines() if line.startswith("schtasks "))
        assert "%~dp0run_heartbeat.bat" in command and " /F" not in command


@pytest.mark.skipif(os.name != "nt", reason="Windows batch execution uses a fake heartbeat only")
@pytest.mark.parametrize("dry_run", [False, True])
def test_batch_wait_exit_and_logging_with_fake_python_entrypoint(tmp_path, dry_run):
    # Copy only the launcher. This stub cannot import pulse, read credentials or send HTTP.
    root = tmp_path / "fake repo with spaces"
    scripts = root / "capabilities" / "pulse"
    scripts.mkdir(parents=True)
    launcher = scripts / "run_heartbeat.bat"
    launcher.write_bytes((PULSE / "run_heartbeat.bat").read_bytes())
    (scripts / "heartbeat.py").write_text(
        'import sys\nprint("SAFE_STDOUT")\nprint("SAFE_STDERR", file=sys.stderr)\nsys.exit(7)\n', encoding="ascii"
    )
    env = dict(os.environ, PYTHON_EXE=sys.executable)
    args = [str(launcher), *(["--dry-run"] if dry_run else [])]
    result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 7
    log = root / ".cache" / "pulse" / "pulse.log"
    if dry_run:
        assert not (root / ".cache").exists()
        assert "SAFE_STDOUT" in result.stdout and "SAFE_STDERR" in result.stderr
    else:
        assert "SAFE_STDOUT" in log.read_text() and "SAFE_STDERR" in log.read_text()
        again = subprocess.run(args, env=env, capture_output=True, text=True, timeout=15, check=False)
        assert again.returncode == 7 and log.read_text().count("SAFE_STDOUT") == 2
