import unittest

from pipeline import _clean_md, _extract_cover_info, _extract_visual_style


class TestCleanMd(unittest.TestCase):
    def test_removes_bold_asterisks(self):
        self.assertEqual(_clean_md("**bold text**"), "bold text")

    def test_removes_leading_trailing_whitespace(self):
        self.assertEqual(_clean_md("  hello world  "), "hello world")

    def test_removes_backticks(self):
        self.assertEqual(_clean_md("`code`"), "code")

    def test_handles_empty(self):
        self.assertEqual(_clean_md(""), "")
        self.assertEqual(_clean_md(None), "")


class TestExtractCoverInfo(unittest.TestCase):
    def test_standard_format(self):
        content = """
【封面页】
**大字标题**: 测试标题
**情绪钩子小字**: 测试小字
英文AI绘画prompt: A test prompt

【正文】
一些正文内容
"""
        info = _extract_cover_info(content)
        self.assertEqual(info["title"], "测试标题")
        self.assertEqual(info["subtitle"], "测试小字")
        self.assertIn("A test prompt", info["prompt"])
        self.assertIn("soft warm lighting", info["prompt"])

    def test_fallback_prompt_extraction(self):
        content = """
【封面页】
**大字标题**: 标题
**情绪钩子小字**: 小字
**背景建议**: 一个测试场景描述

【正文】
正文
"""
        info = _extract_cover_info(content)
        self.assertEqual(info["title"], "标题")
        self.assertEqual(info["subtitle"], "小字")
        self.assertIn("一个测试场景描述", info["prompt"])
        self.assertIn("soft warm lighting", info["prompt"])

    def test_missing_title(self):
        info = _extract_cover_info("没有封面信息")
        self.assertEqual(info["title"], "")
        self.assertEqual(info["subtitle"], "")
        self.assertIn("A soft emotional aesthetic scene", info["prompt"])

    def test_various_title_formats(self):
        for fmt in ["大字标题", "大字", "标题"]:
            content = f"**{fmt}**: 我的标题\n"
            info = _extract_cover_info(content)
            self.assertEqual(info["title"], "我的标题")

    def test_multiline_subtitle(self):
        content = """
**情绪钩子小字**:
这是多行副标题

【正文】
"""
        info = _extract_cover_info(content)
        self.assertEqual(info["subtitle"], "这是多行副标题")


class TestExtractVisualStyle(unittest.TestCase):
    def test_extracts_warm_grey(self):
        self.assertEqual(
            _extract_visual_style("【视觉风格】: warm_grey"), "warm_grey"
        )

    def test_extracts_twilight(self):
        self.assertEqual(
            _extract_visual_style("【视觉风格】: twilight"), "twilight"
        )

    def test_fallback_to_warm_grey(self):
        self.assertEqual(_extract_visual_style("没有视觉风格"), "warm_grey")

    def test_invalid_style_returns_default(self):
        self.assertEqual(
            _extract_visual_style("【视觉风格】: invalid_style"), "warm_grey"
        )

    def test_case_insensitive(self):
        self.assertEqual(
            _extract_visual_style("【视觉风格】: Twilight"), "twilight"
        )


if __name__ == "__main__":
    unittest.main()
