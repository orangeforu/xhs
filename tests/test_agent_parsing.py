"""测试 Agent 的 JSON 解析方法（使用 extract_json_from_llm）。"""

import json
import unittest

from core.agents.content_editor import ContentEditor
from core.agents.community_manager import CommunityManager
from core.agents.cover_designer import CoverDesigner


class TestContentEditorParseReview(unittest.TestCase):

    def setUp(self):
        self.editor = ContentEditor.__new__(ContentEditor)

    def test_parse_flat_json(self):
        raw = json.dumps({
            "verdict": "pass",
            "grade": "A",
            "issues": [],
            "suggestions": [],
            "strengths": ["情绪真实"],
            "overall_comment": "不错",
        }, ensure_ascii=False)
        result = self.editor._parse_review(raw)
        self.assertEqual(result["grade"], "A")
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["strengths"], ["情绪真实"])

    def test_parse_nested_issues(self):
        """旧正则会失败的嵌套场景。"""
        raw = json.dumps({
            "verdict": "conditional",
            "grade": "B",
            "issues": [
                {"location": "第1页", "problem": "开场太慢", "suggestion": "直接进故事"},
                {"location": "第3页", "problem": "金句太旧", "suggestion": "换一个"},
            ],
            "suggestions": [],
            "strengths": [],
            "overall_comment": "需要改进",
        }, ensure_ascii=False)
        result = self.editor._parse_review(raw)
        self.assertEqual(len(result["issues"]), 2)
        self.assertEqual(result["issues"][0]["problem"], "开场太慢")

    def test_parse_with_surrounding_text(self):
        raw = '审核结果：\n{"verdict": "fail", "grade": "C", "issues": [{"location": "全文", "problem": "情绪平淡"}]}\n以上。'
        result = self.editor._parse_review(raw)
        self.assertEqual(result["grade"], "C")
        self.assertEqual(len(result["issues"]), 1)

    def test_parse_invalid_json_fallback(self):
        raw = '完全不是JSON格式的文字'
        result = self.editor._parse_review(raw)
        self.assertEqual(result["grade"], "B")  # fallback default
        self.assertEqual(result["verdict"], "conditional")

    def test_defaults_populated(self):
        raw = '{"grade": "A"}'
        result = self.editor._parse_review(raw)
        self.assertEqual(result["verdict"], "conditional")  # default
        self.assertEqual(result["issues"], [])  # default
        self.assertEqual(result["grade"], "A")  # preserved


class TestCommunityManagerParseComments(unittest.TestCase):

    def setUp(self):
        self.cm = CommunityManager.__new__(CommunityManager)

    def test_parse_classified_comments(self):
        raw = json.dumps({
            "comments": [
                {"type": "discussion_starter", "text": "你们有没有遇到过这种情况？"},
                {"type": "resonance", "text": "太真实了，我也是这样"},
            ],
            "reply_templates": ["抱抱你", "加油鸭", "会好起来的"],
        }, ensure_ascii=False)
        result = self.cm._parse_comments_json(raw)
        self.assertEqual(len(result["comments"]), 2)
        self.assertEqual(result["comments"][0]["type"], "discussion_starter")
        self.assertEqual(len(result["reply_templates"]), 3)

    def test_parse_with_surrounding_text(self):
        raw = '好的，这是预设评论：\n{"comments": [{"type": "controversy", "text": "我觉得不对"}], "reply_templates": ["谢谢"]}\n希望有帮助。'
        result = self.cm._parse_comments_json(raw)
        self.assertEqual(len(result["comments"]), 1)

    def test_parse_invalid_returns_empty(self):
        raw = '完全不是JSON'
        result = self.cm._parse_comments_json(raw)
        self.assertEqual(result, {})


class TestCoverDesignerParseDesign(unittest.TestCase):

    def setUp(self):
        self.cd = CoverDesigner.__new__(CoverDesigner)

    def test_parse_design_json(self):
        raw = json.dumps({
            "title": "说不出口的话",
            "subtitle": "有些话藏在心里太久了",
            "style": "warm_grey",
            "prompt": "A soft emotional scene, warm lighting",
            "visual_anchor": "窗边的咖啡杯",
            "rationale": "温暖色调",
        }, ensure_ascii=False)
        result = self.cd._parse_design(raw)
        self.assertEqual(result["title"], "说不出口的话")
        self.assertEqual(result["style"], "warm_grey")

    def test_parse_design_with_surrounding_text(self):
        raw = '设计方案如下：\n{"title": "测试标题", "subtitle": "测试副标题", "style": "twilight", "prompt": "test", "visual_anchor": "灯", "rationale": "温暖"}\n以上。'
        result = self.cd._parse_design(raw)
        self.assertEqual(result["title"], "测试标题")
        self.assertEqual(result["style"], "twilight")

    def test_parse_design_fallback(self):
        raw = '完全不是JSON格式'
        result = self.cd._parse_design(raw)
        self.assertEqual(result["title"], "说不出口的话")  # fallback
        self.assertEqual(result["style"], "warm_grey")  # fallback


if __name__ == "__main__":
    unittest.main()
