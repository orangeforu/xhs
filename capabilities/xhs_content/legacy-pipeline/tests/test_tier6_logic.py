"""Tier 6 测试：相似度硬门禁 + 爆款复刻拆解。无网络，全 mock。"""

import scripts.replicate_viral as rv_mod
from core.utils import copy_overlap_ratio


# ── copy_overlap_ratio ──

def test_overlap_identical():
    t = "她把手机反扣在桌上，再也没有拿起来。"
    assert copy_overlap_ratio(t, t) == 1.0


def test_overlap_disjoint():
    a = "今天天气真不错适合出门散步"
    b = "完全不同的另一段文字内容"
    assert copy_overlap_ratio(a, b) == 0.0


def test_overlap_partial():
    src = "她把手机反扣在桌上，再也没有拿起来。"
    draft = "她把手机反扣在桌上，然后转身离开了房间。"  # 部分照抄
    r = copy_overlap_ratio(draft, src)
    assert 0.0 < r < 1.0


def test_overlap_empty():
    assert copy_overlap_ratio("", "x") == 0.0
    assert copy_overlap_ratio("x", "") == 0.0


def test_overlap_whitespace_normalized():
    # 空白不计入，加空格不影响相似度
    a = "她把手机反扣在桌上"
    b = "她 把 手 机 反 扣 在 桌 上"
    assert copy_overlap_ratio(a, b) == 1.0


# ── 爆款复刻拆解 ──

def test_deconstruct_to_brief_with_mock():
    canned = """
    {"templates": {"title_template": "被___惊到了", "cover_template": "大字+情绪小字"},
    "brief": {"topic": "被相亲对象的礼貌惊到了", "title_formula": "观点冲击式",
    "angle": "礼貌背后的距离感", "story_prototype": "相亲饭局",
    "controversy_anchor": "过度礼貌=拒绝", "visual_style": "crimson",
    "tags": ["不懂就问有问必答", "相亲", "恋爱"]}}
    """
    parsed = rv_mod.deconstruct_to_brief(
        "被他的礼貌惊到了", "正文...", ["相亲"], llm_call=lambda p: canned
    )
    assert parsed is not None
    assert "brief" in parsed
    assert parsed["brief"]["title_formula"] == "观点冲击式"


def test_deconstruct_bad_json_returns_none():
    assert rv_mod.deconstruct_to_brief("t", "d", [], llm_call=lambda p: "not json") is None


def test_build_brief_from_deconstruction_has_source_content():
    parsed = {
        "templates": {},
        "brief": {"topic": "新选题", "title_formula": "问句式", "visual_style": "mist", "tags": ["不懂就问有问必答"]},
    }
    brief = rv_mod.build_brief_from_deconstruction(parsed, "https://xhs/123", "源正文内容")
    assert brief["copy_mode"] == "style-only"
    assert brief["source_content"] == "源正文内容"
    assert brief["source_url"] == "https://xhs/123"
    assert brief["visual_direction"] == "mist"  # CoverDesigner 读 visual_direction
    assert brief["target_interaction"]  # 默认值
    assert "不懂就问有问必答" in brief["keywords"]
