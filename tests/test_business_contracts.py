"""Offline guards for evidence, money and operational record contracts."""
import re
from copy import deepcopy
from pathlib import Path

import pytest

from capabilities.venture_toolkit.validate_records import (
    check_repo,
    read_csv,
    subscription_covered,
    validate_actions,
    validate_observations,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(("values", "expected"), [
    (["100"], False), (["117.99"], False), (["118"], True),
    (["80", "38"], True), (["118", "-1"], False),
    (["120", None], None), ([""], None), ([], None),
])
def test_subscription_is_net_and_complete(values, expected):
    assert subscription_covered(values) is expected


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "not-money"])
def test_subscription_rejects_invalid_money(bad):
    with pytest.raises(ValueError):
        subscription_covered([bad])


def test_action_can_be_registered_after_its_deadline():
    row = {"action_id": "X-1", "venture": "demo", "status": "pending", "owner": "AI",
           "opened_on": "2026-10-29", "due_on": "2026-10-27", "next_action": "Check receipts",
           "evidence": "venture.md", "decision_scope": "Proposal only"}
    assert validate_actions([row], {"demo"}) == []
    broken = {**row, "due_on": "2026-02-30"}
    assert any("due_on" in e for e in validate_actions([broken], {"demo"}))
    assert any("duplicate" in e for e in validate_actions([row, row], {"demo"}))
    assert any("status" in e for e in validate_actions([{**row, "status": "unknown"}], {"demo"}))
    assert any("evidence" in e for e in validate_actions([{**row, "evidence": ""}], {"demo"}))


@pytest.fixture()
def snapshot():
    return {"作品编号": "A001", "观察时间": "2026-11-04T10:00:00+08:00",
            "首次公开日": "2026-11-01", "抖音作品链接": "https://example.com/work/1",
            "累计使用量": "20", "抖音累计播放量": "100", "测试流量标记": "未知",
            "数据完整性": "完整", "来源证据": "redacted.png", "备注": ""}


def test_snapshot_preserves_unknown_counts(snapshot):
    row = {**snapshot, "累计使用量": "", "数据完整性": "不完整", "备注": "不可见"}
    assert validate_observations([row], {"A001": "2026-11-01"}) == []
    assert row["累计使用量"] == ""


def test_snapshot_join_time_and_duplicate_guards(snapshot):
    known = {"A001": "2026-11-01"}
    assert validate_observations([snapshot], known) == []
    assert any("duplicate" in e for e in validate_observations([snapshot, snapshot], known))
    same_in_utc = {**snapshot, "观察时间": "2026-11-04T02:00:00+00:00"}
    assert any("duplicate" in e for e in validate_observations([snapshot, same_in_utc], known))
    for field, value in [("作品编号", "missing"), ("观察时间", "2026-11-04T10:00:00"),
                         ("首次公开日", "2026-11-02"), ("累计使用量", "1.2万"),
                         ("测试流量标记", "guessed"), ("来源证据", "")]:
        broken = deepcopy(snapshot)
        broken[field] = value
        assert validate_observations([broken], known), field


def test_csv_schema_and_row_shape(tmp_path):
    csv_file = tmp_path / "sample.csv"
    csv_file.write_text("a,b\n1,2,3\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_csv(csv_file, ("a", "b"))
    with pytest.raises(ValueError):
        read_csv(csv_file, ("x", "y"))


def test_current_record_contracts():
    assert check_repo(ROOT) == []


def test_case_status_mirrors_match_dashboard():
    from capabilities.pulse.heartbeat import venture_status

    dashboard = (ROOT / "cockpit/status.md").read_text(encoding="utf-8")
    for card in (ROOT / "ventures").glob("*/venture.md"):
        if card.parent.name.startswith("_"):
            continue
        status = venture_status(card)
        assert status is not None
        assert f"| {card.parent.name} | {status} |" in dashboard


def test_chinese_v11_has_ten_prompts_and_explicit_review_gate():
    text = (ROOT / "ventures/ai_workflow_kit/products/ai-office-workflows/kit-cn-打工人AI提效工作流包.md").read_text(encoding="utf-8")
    assert len(re.findall(r"```\n(.*?)```", text, re.S)) == 10
    assert "v1.1 待复测稿" in text and "不是新一轮API实测" in text
    for unsupported in ["40 分钟 → 10 分钟", "AI 的引用 10-20% 是错的", "真实会议一定有没主的活", "零缺口 = 它编了"]:
        assert unsupported not in text
    assert "正式责任" in text and "比较基期" in text and "纯感谢" in text


def test_current_critical_document_guards():
    manual = (ROOT / "ventures/jianying_templates/执行手册_从今天开始_20261028.md").read_text(encoding="utf-8")
    research = (ROOT / "ventures/jianying_templates/剪映官方付费模板_90天实操手册_20261028.md").read_text(encoding="utf-8")
    assert "件均累计约 ¥15" not in manual + research
    assert "仍是净成功" not in manual
    assert "official_template_observations.csv" in manual
    bundle = (ROOT / "ventures/jianying_templates/周岁纪念套装_最小交付规格_20261028.md").read_text(encoding="utf-8")
    assert "非会员" in bundle and "导出" in bundle and "额外" in bundle
