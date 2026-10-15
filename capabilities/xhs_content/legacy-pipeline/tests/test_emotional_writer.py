"""Tests for EmotionalWriter._build_write_prompt — 写手 prompt 构建。"""

import pytest

from core.agents.base import MessageBus
from core.agents.emotional_writer import EmotionalWriter


@pytest.fixture
def writer():
    return EmotionalWriter(MessageBus())


class TestBuildWritePrompt:
    """测试 _build_write_prompt 的 prompt 构建逻辑。"""

    def test_minimal_brief(self, writer):
        brief = {"topic": "恋爱中的安全感"}
        result = writer._build_write_prompt(brief, "")
        assert "恋爱中的安全感" in result
        assert "问句式" in result  # 默认公式
        assert "点赞+收藏" in result  # 默认目标互动

    def test_full_brief(self, writer):
        brief = {
            "topic": "讨好型人格的觉醒",
            "title_formula": "观点冲击式",
            "target_interaction": "评论+收藏",
            "story_prototype": "她总是笑着说没关系",
            "controversy_anchor": "善良是不是一种软弱",
        }
        result = writer._build_write_prompt(brief, "")
        assert "讨好型人格的觉醒" in result
        assert "观点冲击式" in result
        assert "评论+收藏" in result
        assert "她总是笑着说没关系" in result
        assert "善良是不是一种软弱" in result

    def test_story_prototype_only(self, writer):
        brief = {"topic": "测试", "story_prototype": "原型故事"}
        result = writer._build_write_prompt(brief, "")
        assert "原型故事" in result
        assert "争议锚点" not in result

    def test_controversy_anchor_only(self, writer):
        brief = {"topic": "测试", "controversy_anchor": "争议点"}
        result = writer._build_write_prompt(brief, "")
        assert "争议点" in result
        assert "故事原型" not in result

    def test_with_feedback(self, writer):
        brief = {"topic": "测试"}
        feedback = "请加强开头的冲击力"
        result = writer._build_write_prompt(brief, feedback)
        assert "修改反馈" in result
        assert "请加强开头的冲击力" in result

    def test_empty_feedback_not_appended(self, writer):
        brief = {"topic": "测试"}
        result = writer._build_write_prompt(brief, "")
        assert "修改反馈" not in result

    def test_different_formulas(self, writer):
        formulas = ["问句式", "概念解读式", "观点冲击式", "方法承诺式"]
        for formula in formulas:
            brief = {"topic": "测试", "title_formula": formula}
            result = writer._build_write_prompt(brief, "")
            assert formula in result

    def test_unknown_formula_uses_empty(self, writer):
        brief = {"topic": "测试", "title_formula": "不存在的公式"}
        result = writer._build_write_prompt(brief, "")
        assert "测试" in result

    def test_output_format_sections(self, writer):
        brief = {"topic": "测试"}
        result = writer._build_write_prompt(brief, "")
        assert "标题候选" in result
        assert "封面页" in result
        assert "正文" in result
        assert "金句" in result
        assert "互动钩子" in result
        assert "话题标签" in result
        assert "视觉风格" in result

    def test_forbidden_items_present(self, writer):
        brief = {"topic": "测试"}
        result = writer._build_write_prompt(brief, "")
        assert "禁止" in result
