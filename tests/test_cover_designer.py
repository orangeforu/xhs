import unittest

from core.agents.cover_designer import CoverDesigner, ALL_STYLES


class TestEnforceRotation(unittest.TestCase):
    """测试风格轮换逻辑。"""

    def test_fewer_than_2_recent_returns_original(self):
        result = CoverDesigner._enforce_rotation("warm_grey", [])
        self.assertEqual(result, "warm_grey")

    def test_one_recent_returns_original(self):
        result = CoverDesigner._enforce_rotation("warm_grey", ["twilight"])
        self.assertEqual(result, "warm_grey")

    def test_different_recent_returns_original(self):
        result = CoverDesigner._enforce_rotation("warm_grey", ["twilight", "crimson"])
        self.assertEqual(result, "warm_grey")

    def test_three_same_forces_rotation(self):
        result = CoverDesigner._enforce_rotation("warm_grey", ["warm_grey", "warm_grey"])
        self.assertNotEqual(result, "warm_grey")
        self.assertIn(result, ALL_STYLES)

    def test_rotation_prefers_unused_style(self):
        recent = ["warm_grey", "warm_grey"]
        result = CoverDesigner._enforce_rotation("warm_grey", recent)
        self.assertNotIn(result, recent)

    def test_all_styles_used_picks_first_alternative(self):
        recent = ["warm_grey", "warm_grey"]
        result = CoverDesigner._enforce_rotation("warm_grey", recent)
        self.assertIn(result, ALL_STYLES)
        self.assertNotEqual(result, "warm_grey")


class TestExtractTitleFromContent(unittest.TestCase):
    """测试从内容中提取 fallback 标题。"""

    def test_short_impactful_line(self):
        content = "# 笔记\n\n她盯着手机屏幕看了很久。"
        result = CoverDesigner._extract_title_from_content(content)
        self.assertEqual(result, "她盯着手机屏幕看了很久。")

    def test_skips_metadata_lines(self):
        content = "# 笔记\n\n【标题候选】\n1. 标题一\n2. 标题二\n【封面页】\n大字标题\n她关掉了微信。"
        result = CoverDesigner._extract_title_from_content(content)
        self.assertEqual(result, "她关掉了微信。")

    def test_no_suitable_line_returns_fallback(self):
        content = "# 笔记\n\n这是一个非常非常非常非常非常非常非常非常非常非常长的句子超过十五字"
        result = CoverDesigner._extract_title_from_content(content)
        self.assertEqual(result, "说不出口的话")

    def test_strips_bold_markers(self):
        content = "# 笔记\n\n**她删掉了他的微信。**"
        result = CoverDesigner._extract_title_from_content(content)
        self.assertEqual(result, "她删掉了他的微信。")

    def test_empty_content_returns_fallback(self):
        result = CoverDesigner._extract_title_from_content("")
        self.assertEqual(result, "说不出口的话")


class TestParseDesign(unittest.TestCase):
    """测试设计方案解析。"""

    def setUp(self):
        self.designer = CoverDesigner.__new__(CoverDesigner)

    def test_valid_json(self):
        raw = '{"title": "测试标题", "subtitle": "测试副标题", "style": "crimson", "prompt": "test prompt"}'
        result = self.designer._parse_design(raw)
        self.assertEqual(result["title"], "测试标题")
        self.assertEqual(result["style"], "crimson")

    def test_invalid_json_falls_back_to_regex(self):
        raw = '''"title": "回不去的从前"
"subtitle": "有些路只能一个人走"
"style": "twilight"
"prompt": "A soft emotional scene"'''
        result = self.designer._parse_design(raw)
        self.assertEqual(result["title"], "回不去的从前")
        self.assertEqual(result["style"], "twilight")

    def test_fallback_defaults(self):
        raw = "No structured data at all."
        result = self.designer._parse_design(raw)
        self.assertEqual(result["title"], "说不出口的话")
        self.assertEqual(result["style"], "warm_grey")
        self.assertIn("cozy atmosphere", result["prompt"])

    def test_json_with_extra_fields(self):
        raw = '{"title": "标题", "visual_anchor": "窗边的咖啡杯", "rationale": "温暖感"}'
        result = self.designer._parse_design(raw)
        self.assertEqual(result["visual_anchor"], "窗边的咖啡杯")


if __name__ == "__main__":
    unittest.main()
