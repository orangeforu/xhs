"""Offline checks for action receipts and template snapshots; no writes or network."""
from __future__ import annotations

import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACTION_FIELDS = (
    "action_id", "venture", "status", "owner", "opened_on", "due_on",
    "next_action", "evidence", "decision_scope",
)
OBSERVATION_FIELDS = (
    "作品编号", "观察时间", "首次公开日", "抖音作品链接", "累计使用量",
    "抖音累计播放量", "测试流量标记", "数据完整性", "来源证据", "备注",
)


def subscription_covered(net_contributions: list[str | None], monthly_cost: str = "118") -> bool | None:
    """Use already reconciled net contributions, never gross sales or withdrawals.

    Unknown input means unknown coverage. Callers must establish delivery,
    settlement, period completeness and no double-deducted fees first.
    """
    cost = Decimal(monthly_cost)
    if not cost.is_finite() or cost < 0:
        raise ValueError("Invalid monthly cost")
    if not net_contributions or any(v is None or not v.strip() for v in net_contributions):
        return None
    try:
        amounts = [Decimal(v) for v in net_contributions if v is not None]
    except InvalidOperation as exc:
        raise ValueError("Invalid net contribution") from exc
    if any(not amount.is_finite() for amount in amounts):
        raise ValueError("Non-finite net contribution")
    return sum(amounts, Decimal("0")) >= cost


def read_csv(path: Path, required: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(required):
            raise ValueError(f"{path.name}: unexpected columns")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f"{path.name}: malformed row")
    return rows


def valid_date(value: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def validate_actions(rows: list[dict[str, str]], ventures: set[str]) -> list[str]:
    errors = []
    seen = set()
    for line, row in enumerate(rows, 2):
        prefix = f"actions.csv:{line}"
        aid = row.get("action_id", "")
        if not aid or aid in seen:
            errors.append(f"{prefix}: missing/duplicate action_id")
        seen.add(aid)
        if row.get("venture") not in ventures | {"governance"}:
            errors.append(f"{prefix}: unknown venture")
        if row.get("status") not in {"pending", "blocked", "done", "cancelled"}:
            errors.append(f"{prefix}: invalid status")
        for field in ("owner", "next_action", "evidence", "decision_scope"):
            if not row.get(field, "").strip():
                errors.append(f"{prefix}: missing {field}")
        if not valid_date(row.get("opened_on", "")):
            errors.append(f"{prefix}: invalid opened_on")
        due = row.get("due_on", "")
        if due and not valid_date(due):
            errors.append(f"{prefix}: invalid due_on")
    return errors


def validate_observations(rows: list[dict[str, str]], public_dates: dict[str, str]) -> list[str]:
    errors = []
    seen = set()
    for line, row in enumerate(rows, 2):
        prefix = f"observations.csv:{line}"
        work = row.get("作品编号", "")
        stamp = row.get("观察时间", "")
        if work not in public_dates:
            errors.append(f"{prefix}: unknown work ID")
        elif row.get("首次公开日") != public_dates[work]:
            errors.append(f"{prefix}: public date differs from register")
        try:
            observed = datetime.fromisoformat(stamp)
            public = date.fromisoformat(row.get("首次公开日", ""))
            if observed.tzinfo is None or observed.date() < public:
                raise ValueError("Missing timezone or pre-public observation")
            key = (work, observed)
            if key in seen:
                errors.append(f"{prefix}: duplicate snapshot")
            seen.add(key)
        except ValueError:
            errors.append(f"{prefix}: invalid observation/public date")
        for field in ("累计使用量", "抖音累计播放量"):
            value = row.get(field, "")
            if value and not re.fullmatch(r"[0-9]+", value):
                errors.append(f"{prefix}: invalid count in {field}")
        if row.get("测试流量标记") not in {"无", "含测试", "未知"}:
            errors.append(f"{prefix}: invalid test traffic marker")
        if row.get("数据完整性") not in {"完整", "不完整"}:
            errors.append(f"{prefix}: invalid completeness")
        if row.get("数据完整性") == "完整" and not row.get("累计使用量"):
            errors.append(f"{prefix}: complete snapshot missing usage count")
        if row.get("抖音累计播放量") and not row.get("抖音作品链接"):
            errors.append(f"{prefix}: play count has no associated work")
        if not row.get("来源证据", "").strip():
            errors.append(f"{prefix}: missing evidence")
        if (not row.get("累计使用量") or not row.get("抖音累计播放量")) and not row.get("备注", "").strip():
            errors.append(f"{prefix}: explain unavailable fields")
    return errors


def check_repo(root: Path) -> list[str]:
    ventures = {p.name for p in (root / "ventures").iterdir()
                if p.is_dir() and not p.name.startswith("_")}
    errors = validate_actions(read_csv(root / "cockpit/actions.csv", ACTION_FIELDS), ventures)
    data = root / "ventures/jianying_templates/data"
    with (data / "official_template_register.csv").open(encoding="utf-8-sig", newline="") as handle:
        records = list(csv.DictReader(handle))
    public_dates = {r["作品编号"]: r["首次公开日"] for r in records}
    if len(public_dates) != len(records):
        errors.append("register.csv: duplicate work ID")
    errors.extend(validate_observations(read_csv(data / "official_template_observations.csv", OBSERVATION_FIELDS), public_dates))
    return errors


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        errors = check_repo(ROOT)
    except (OSError, ValueError, KeyError, csv.Error) as exc:
        print(f"Record validation failed ({type(exc).__name__})")
        return 1
    for error in errors:
        print(error)
    if not errors:
        print("Record contracts OK; empty ledgers do not prove sales, delivery or income.")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
