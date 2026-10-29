"""Deterministic action reminders with durable, fail-closed delivery receipts.

Importing this module never loads push configuration. Dry runs only read briefing
inputs; regular runs emit safe codes, not message bodies or exception details.
"""

import argparse
import csv
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

# Direct CLI previews must not create a local push.pyc even without python -B.
if __name__ == "__main__":
    sys.dont_write_bytecode = True

if __package__:
    from .push import KNOWN_FAILURES, push_wechat
else:
    from push import KNOWN_FAILURES, push_wechat

REPO = Path(__file__).resolve().parents[2]
ACTION_FIELDS = (
    "action_id",
    "venture",
    "status",
    "owner",
    "opened_on",
    "due_on",
    "next_action",
    "evidence",
    "decision_scope",
)
VENTURE_STATUSES = {"idea", "researching", "planning", "executing", "selling", "maintenance", "closed"}
WARNING_CODES = {
    "ACTIONS_MISSING",
    "ACTIONS_INVALID",
    "ACTION_ROW_INVALID",
    "ACTION_DUPLICATE_ID",
    "ACTION_STATUS_INVALID",
    "ACTION_DATE_INVALID",
    "ACTION_VENTURE_UNKNOWN",
    "VENTURE_METADATA_INVALID",
    "VENTURE_STATUS_INVALID",
    "FOCUS_UNREADABLE",
    "JOURNAL_NAME_INVALID",
    "JOURNAL_FUTURE_DATE",
    "JOURNAL_STALE",
}


@dataclass(frozen=True)
class Action:
    action_id: str
    venture: str
    due_on: date
    next_action: str
    status: str


def _warn(warnings, code):
    if warnings is not None and code not in warnings:
        warnings.append(code)


def _date(value: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("DATE_INVALID")
    return date.fromisoformat(value)


def week_focus(repo=None, warnings=None) -> list[str]:
    try:
        text = (Path(repo or REPO) / "cockpit" / "status.md").read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        _warn(warnings, "FOCUS_UNREADABLE")
        return []
    match = re.search(r"^## 本周焦点[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        return []
    return [m.group(1).strip() for m in re.finditer(r"^\s*- \[ \]\s+(.+)$", match.group(1), re.M)]


def venture_status(path: Path, warnings=None) -> str | None:
    """Read the top-level status scalar in front matter or the first YAML fence.

    Deliberately supports only plain/single/double-quoted status enum scalars.
    Nested keys, prose, dates, YAML aliases and multiline status values are never
    guessed. Unsupported/ambiguous metadata is skipped with a safe warning.
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        _warn(warnings, "VENTURE_METADATA_INVALID")
        return None
    if text.startswith("---\n"):
        block = re.match(r"\A---\n(.*?)\n(?:---|\.\.\.)[ \t]*(?:\n|$)", text, re.S)
    else:
        block = re.search(r"^```ya?ml[ \t]*\n(.*?)^```[ \t]*$", text, re.M | re.S)
    if not block:
        _warn(warnings, "VENTURE_METADATA_INVALID")
        return None
    # Reject unsupported root syntax, especially multiline quoted/flow values
    # that could make an apparent column-zero status part of another scalar.
    for line in block.group(1).splitlines():
        if not line.strip() or line.startswith((" ", "\t", "#")):
            continue
        entry = re.fullmatch(r"""(?:[\w-]+|'[\w-]+'|"[\w-]+")[ \t]*:[ \t]*(.*)""", line)
        value = entry.group(1) if entry else ""
        quoted = re.fullmatch(r""""(?:[^"\\]|\\.)*"(?:[ \t]+\#.*)?[ \t]*""", value) or re.fullmatch(
            r"'(?:[^']|'')*'(?:[ \t]+\#.*)?[ \t]*", value
        )
        if not entry or value.startswith(("[", "{", "&", "*", "!")) or (value.startswith(("'", '"')) and not quoted):
            _warn(warnings, "VENTURE_METADATA_INVALID")
            return None
    values = re.findall(r"^(?:status|'status'|\"status\")[ \t]*:(.*)$", block.group(1), re.M)
    if len(values) != 1:
        _warn(warnings, "VENTURE_METADATA_INVALID")
        return None
    # YAML requires separation after ':' and before an inline comment.
    scalar = re.fullmatch(r"""[ \t]+(?:([a-z]+)|'([a-z]+)'|"([a-z]+)")(?:[ \t]+\#.*)?[ \t]*""", values[0])
    status = next((part for part in scalar.groups() if part is not None), None) if scalar else None
    if status not in VENTURE_STATUSES:
        _warn(warnings, "VENTURE_STATUS_INVALID")
        return None
    return status


def due_actions(repo=None, today=None, warnings=None) -> list[Action]:
    """actions.csv is the only action/deadline receipt source, including overdue rows."""
    root, today = Path(repo or REPO), today or date.today()
    try:
        with (root / "cockpit" / "actions.csv").open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            if (
                not reader.fieldnames
                or len(reader.fieldnames) != len(ACTION_FIELDS)
                or set(reader.fieldnames) != set(ACTION_FIELDS)
            ):
                _warn(warnings, "ACTIONS_INVALID")
                return []
            rows = list(reader)
    except FileNotFoundError:
        _warn(warnings, "ACTIONS_MISSING")
        return []
    except (OSError, UnicodeError, csv.Error):
        _warn(warnings, "ACTIONS_INVALID")
        return []

    # Discover real case directories rather than joining untrusted CSV paths.
    ventures = {}
    for path in sorted((root / "ventures").glob("*/venture.md")):
        if path.parent.name != "_template" and not path.parent.is_symlink() and not path.is_symlink():
            ventures[path.parent.name] = venture_status(path, warnings)
    counts = {}
    for row in rows:
        identity = (row.get("action_id") or "").strip()
        counts[identity] = counts.get(identity, 0) + 1
    found = []
    for row in rows:
        if None in row or any(row.get(field) is None for field in ACTION_FIELDS):
            _warn(warnings, "ACTION_ROW_INVALID")
            continue
        row = {key: value.strip() for key, value in row.items()}
        if any(not row[field] for field in ("action_id", "next_action", "owner", "evidence", "decision_scope")):
            _warn(warnings, "ACTION_ROW_INVALID")
            continue
        if counts[row["action_id"]] != 1:
            _warn(warnings, "ACTION_DUPLICATE_ID")
            continue
        if row["status"] not in {"pending", "blocked", "done", "cancelled"}:
            _warn(warnings, "ACTION_STATUS_INVALID")
            continue
        try:
            _date(row["opened_on"])
            due = _date(row["due_on"]) if row["due_on"] else None
        except ValueError:
            _warn(warnings, "ACTION_DATE_INVALID")
            continue
        venture = row["venture"]
        if venture != "governance":
            if venture not in ventures:
                _warn(warnings, "ACTION_VENTURE_UNKNOWN")
                continue
            if ventures[venture] in {None, "closed"}:
                continue
        if row["status"] in {"pending", "blocked"} and due and due <= today + timedelta(days=14):
            found.append(Action(row["action_id"], venture, due, row["next_action"], row["status"]))
    return sorted(found, key=lambda action: (action.due_on, action.action_id))


def key_dates(repo=None, today=None, warnings=None) -> list[tuple[str, date]]:
    """Compatibility helper: only explicit open-action deadlines, never prose dates."""
    return [(action.venture, action.due_on) for action in due_actions(repo, today, warnings)]


def journal_stale_days(journal=None, today=None, warnings=None) -> int | None:
    today = today or date.today()
    journal = Path(journal) if journal is not None else REPO / "cockpit" / "journal"
    dates = []
    for path in journal.glob("*.md"):
        if not path.is_file():
            continue
        try:
            day = _date(path.stem)
        except ValueError:
            _warn(warnings, "JOURNAL_NAME_INVALID")
            continue
        if day > today:
            _warn(warnings, "JOURNAL_FUTURE_DATE")
            continue
        dates.append(day)
    return (today - max(dates)).days if dates else None


def build_brief(repo=None, today=None, warnings=None) -> tuple[str, str]:
    root, today = Path(repo or REPO), today or date.today()
    warnings = [] if warnings is None else warnings
    actions = due_actions(root, today, warnings)
    focus = week_focus(root, warnings)
    todo = []
    for action in actions:
        delta = (action.due_on - today).days
        when = f"逾期 {-delta} 天" if delta < 0 else "今日到期" if delta == 0 else f"{delta} 天后到期"
        todo.append(
            f"[{action.venture}/{action.action_id}] {action.next_action}"
            f"（{action.due_on.isoformat()}，{when}，{action.status}）"
        )
    # A weekly focus may reference an action already listed above; do not spend
    # two of the three slots reminding about the same action ID.
    focus = [item for item in focus if not any(action.action_id in item for action in actions)]
    todo = (todo + focus)[:3]
    if not todo:
        todo = ["暂无明确到期行动或未完成周焦点；请核对 cockpit/actions.csv。"]
    stale = journal_stale_days(root / "cockpit" / "journal", today, warnings)
    if stale is not None and stale >= 2:
        _warn(warnings, "JOURNAL_STALE")
    lines = [f"# 作战简报 {today.isoformat()}", "", "## 今日三件事"]
    lines += [f"{i}. {item}" for i, item in enumerate(todo, 1)]
    if actions:
        lines += ["", "## 到期提醒（含逾期，截止未来 14 天）"]
        lines += [f"- {action.venture}/{action.action_id}: {action.due_on.isoformat()}" for action in actions]
    if warnings:
        lines += ["", "## 输入预警", *[f"- {code}" for code in warnings]]
    lines += ["", "## 回执", "- 行动、截止与完成回执仅维护 cockpit/actions.csv；简报不是完成证据。"]
    brief = "\n".join(lines) + "\n"
    return brief, brief


class PulseError(Exception):
    pass


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise PulseError("ARGUMENTS_INVALID")


def _stamp():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _atomic_write(path: Path, text: str):
    """Replace only after a flushed write; the old receipt survives failed writes."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _save_state(path, state):
    _atomic_write(path, json.dumps(state, ensure_ascii=True, indent=2) + "\n")


@contextmanager
def run_lock(path: Path):
    """An exclusive lock is never reclaimed automatically, including with --retry."""
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise PulseError("LOCK_BUSY_MANUAL_CHECK") from None
    try:
        os.close(fd)
        yield
    finally:
        path.unlink()


def _new_state(today):
    return {
        "version": 1,
        "date": today.isoformat(),
        "started_at": _stamp(),
        "finished_at": None,
        "status": "running",
        "delivery": "not_sent",
        "error_code": None,
        "warnings": [],
    }


def _load_state(path):
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    try:
        valid_pairs = {
            ("running", "not_sent"),
            ("running", "unknown"),
            ("succeeded", "delivered"),
            ("failed", "not_sent"),
            ("failed", "rejected"),
            ("delivery_unknown", "unknown"),
        }
        if not isinstance(state, dict) or state.get("version") != 1:
            raise ValueError
        _date(state["date"])
        datetime.fromisoformat(state["started_at"])
        if state["finished_at"] is not None:
            datetime.fromisoformat(state["finished_at"])
        if (state["status"], state["delivery"]) not in valid_pairs:
            raise ValueError
        if state["status"] != "running" and state["finished_at"] is None:
            raise ValueError
        if state.get("error_code") not in KNOWN_FAILURES | {
            None,
            "DELIVERY_UNKNOWN",
            "STATE_INVALID_MANUAL_CHECK",
            "RUN_FAILED",
            "INTERRUPTED_BEFORE_SEND",
        }:
            raise ValueError
        if not isinstance(state.get("warnings"), list) or any(code not in WARNING_CODES for code in state["warnings"]):
            raise ValueError
        # Never propagate extra, untrusted fields into a later state write.
        return {key: state[key] for key in _new_state(_date(state["date"]))}
    except (KeyError, ValueError, TypeError):
        raise PulseError("STATE_INVALID_MANUAL_CHECK") from None


def _finish(state, status, delivery, code=None):
    state.update(status=status, delivery=delivery, error_code=code, finished_at=_stamp())


def _run(root, today, retry, sender):
    cache = root / ".cache"
    cache.mkdir(parents=True, exist_ok=True)
    state_path = cache / "pulse_last_run.json"
    with run_lock(cache / "pulse.lock"):
        try:
            previous = _load_state(state_path)
        except Exception:
            state = _new_state(today)
            _finish(state, "delivery_unknown", "unknown", "STATE_INVALID_MANUAL_CHECK")
            _save_state(state_path, state)
            print("ERROR STATE_INVALID_MANUAL_CHECK")
            return 1
        if previous:
            if previous["delivery"] == "unknown" or _date(previous["date"]) > today:
                _finish(previous, "delivery_unknown", "unknown", "DELIVERY_UNKNOWN")
                _save_state(state_path, previous)
                print("ERROR DELIVERY_UNKNOWN_MANUAL_CHECK")
                return 1
            if previous["status"] == "running":
                _finish(previous, "failed", "not_sent", "INTERRUPTED_BEFORE_SEND")
                _save_state(state_path, previous)
            if previous["date"] == today.isoformat():
                if previous["status"] == "succeeded":
                    print("OK ALREADY_SUCCEEDED")
                    return 0
                if not retry:
                    print("ERROR RETRY_REQUIRED")
                    return 1

        state = _new_state(today)
        _save_state(state_path, state)  # Must persist the start before any side effect.
        try:
            brief, body = build_brief(root, today, state["warnings"])
            journal = root / "cockpit" / "journal"
            journal.mkdir(parents=True, exist_ok=True)
            _atomic_write(journal / f"{today.isoformat()}.md", brief)
            # A crash from this point on must never cause an automatic duplicate.
            state["delivery"] = "unknown"
            _save_state(state_path, state)
            if sender is None:
                result = push_wechat(
                    f"孵化台晨报 {today.isoformat()}",
                    body,
                    config_paths=(cache / "pulse_push.json", root.parent / "xianyu" / "push.json"),
                )
            else:
                result = sender(f"孵化台晨报 {today.isoformat()}", body)
            if isinstance(result, tuple) and len(result) == 2 and result[0] is True and result[1] == "OK":
                _finish(state, "succeeded", "delivered")
            elif (
                isinstance(result, tuple)
                and len(result) == 2
                and result[0] is False
                and isinstance(result[1], str)
                and result[1] in KNOWN_FAILURES
            ):
                _finish(state, "failed", "rejected" if result[1] == "REJECTED" else "not_sent", result[1])
            else:
                _finish(state, "delivery_unknown", "unknown", "DELIVERY_UNKNOWN")
        except BaseException:
            # Also record interrupts during a send, without exposing their payload.
            unknown = state["delivery"] == "unknown"
            _finish(
                state,
                "delivery_unknown" if unknown else "failed",
                "unknown" if unknown else "not_sent",
                "DELIVERY_UNKNOWN" if unknown else "RUN_FAILED",
            )
        _save_state(state_path, state)
        for code in state["warnings"]:
            print(f"WARN {code}")
        if state["status"] == "succeeded":
            print("OK SUCCEEDED")
            return 0
        code = "DELIVERY_UNKNOWN_MANUAL_CHECK" if state["delivery"] == "unknown" else state["error_code"]
        print(f"ERROR {code}")
        return 1


def main(argv=None, *, repo=None, today=None, sender=None) -> int:
    """CLI and injectable offline runtime. No state/config/lock writes on --dry-run."""
    try:
        parser = SafeParser(description=__doc__)
        parser.add_argument("--dry-run", action="store_true", help="Preview only; no writes or push config access")
        parser.add_argument("--retry", action="store_true", help="Retry today's known failure, never unknown delivery")
        args = parser.parse_args(argv)
        root, today = Path(repo or REPO), today or date.today()
        if args.dry_run:
            brief, _ = build_brief(root, today)
            print(brief, end="")
            return 0
        return _run(root, today, args.retry, sender)
    except PulseError as error:
        # Only locally constructed, fixed codes may reach the log.
        code = str(error)
        print("ERROR " + (code if code in {"LOCK_BUSY_MANUAL_CHECK", "ARGUMENTS_INVALID"} else "RUN_FAILED"))
        return 1
    except Exception:
        print("ERROR RUNTIME_IO_FAILED_MANUAL_CHECK")
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
