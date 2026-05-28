import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from pipeline import _clean_md, _extract_cover_info, _extract_visual_style, _sanitize_prompt, _update_topic_status


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


class TestSanitizePrompt(unittest.TestCase):
    def test_cold_keywords_replaced(self):
        result = _sanitize_prompt("A dark room with dimly lit corners")
        self.assertNotIn("dark room", result)
        self.assertNotIn("dimly lit", result)
        self.assertIn("warm", result.lower())

    def test_warm_prompt_unchanged(self):
        prompt = "A cozy scene with soft warm lighting"
        result = _sanitize_prompt(prompt)
        self.assertIn("soft warm lighting", result)

    def test_empty_prompt(self):
        self.assertEqual(_sanitize_prompt(""), "")


class TestUpdateTopicStatus(unittest.TestCase):
    def test_updates_status(self):
        tmp = tempfile.mkdtemp()
        topics_path = Path(tmp) / "topics.json"
        data = {
            "topics": [
                {"topic": "测试A", "status": "not_started"},
                {"topic": "测试B", "status": "not_started"},
            ]
        }
        topics_path.write_text(json.dumps(data, ensure_ascii=False))

        with patch("pipeline.load_topics_json", return_value=json.loads(json.dumps(data))):
            with patch("pipeline.save_topics_json") as mock_save:
                _update_topic_status("测试A", "generated", "/tmp/out")
                saved = mock_save.call_args[0][0]
                self.assertEqual(saved["topics"][0]["status"], "generated")
                self.assertEqual(saved["topics"][0]["output_dir"], "/tmp/out")
                self.assertIsNotNone(saved["topics"][0]["generated_at"])

        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


class TestGenerateIntegration(unittest.TestCase):
    """集成测试：mock LLM 调用，测试 generate() 完整流程。"""

    @patch("pipeline._prepare_out_dir")
    @patch("pipeline.load_topics_json")
    @patch("pipeline._update_topic_status")
    @patch("core.agents.base._call_api")
    @patch("core.image_generator.generate_cover_ai", return_value=None)
    def test_generate_returns_completed(self, mock_cover, mock_api, mock_update, mock_topics, mock_outdir):
        """generate() 在 mock LLM 下应返回 completed 状态。"""
        mock_topics.return_value = {
            "topics": [
                {
                    "topic": "测试选题",
                    "title_formula": "问句式",
                    "pillar": "亲密关系洞察",
                    "target_interaction": "评论驱动",
                    "status": "not_started",
                }
            ]
        }

        writer_content = "【封面页】\n大字标题: 测试标题\n情绪钩子小字: 测试小字\n英文AI绘画prompt: A test scene\n\n【正文】\n" + "这是一段测试正文内容。" * 30

        def fake_call_api(**kwargs):
            content = kwargs.get("messages", [{}])[-1].get("content", "")
            if "审核" in content or "审核" in str(kwargs.get("messages", [{}])[0].get("content", "")):
                return {"choices": [{"message": {"content": json.dumps({
                    "verdict": "pass", "grade": "A", "issues": [], "suggestions": [],
                    "strengths": ["情绪真实"], "overall_comment": "不错",
                    "needs_redesign": False, "needs_relayout": False,
                }, ensure_ascii=False)}}]}
            elif "读者体验" in content:
                return {"choices": [{"message": {"content": json.dumps({
                    "grade": "A", "quality_issues": [], "quality_suggestions": [],
                    "discussion_potential": "high",
                }, ensure_ascii=False)}}]}
            elif "评论" in content or "回复模板" in content:
                return {"choices": [{"message": {"content": json.dumps({
                    "comments": [{"type": "resonance", "text": "太真实了"}],
                    "reply_templates": ["抱抱"],
                }, ensure_ascii=False)}}]}
            elif "选题" in content or "brief" in content.lower():
                return {"choices": [{"message": {"content": "增强后的brief"}}]}
            else:
                return {"choices": [{"message": {"content": writer_content}}]}

        mock_api.side_effect = fake_call_api

        tmpdir = tempfile.mkdtemp()
        mock_outdir.return_value = tmpdir

        from pipeline import generate
        result = generate(topic="测试选题")

        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "completed")
        self.assertIn("note", result)
        self.assertIn("review", result)

        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
