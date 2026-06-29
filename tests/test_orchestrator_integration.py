"""集成测试：Orchestrator.run() 和 ChiefEditor.orchestrate() 完整流程。"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from core.agents.orchestrator import Orchestrator
from core.agents.base import MessageBus


class TestOrchestratorRun(unittest.TestCase):
    """测试 Orchestrator.run() 完整编排流程。"""

    @patch("core.agents.base._call_api")
    @patch("core.image_generator.generate_cover_ai", return_value=None)
    def test_run_returns_completed(self, mock_cover, mock_api):
        """Orchestrator.run() 在 mock LLM 下应返回 completed 状态。"""
        writer_content = (
            "【封面页】\n"
            "大字标题: 测试标题\n"
            "情绪钩子小字: 测试小字\n"
            "英文AI绘画prompt: A test scene\n\n"
            "【正文】\n"
            + "这是一段测试正文内容。\n" * 30
            + "\n\n【话题标签】\n#不懂就问有问必答 #测试标签1 #测试标签2\n"
        )

        def fake_call_api(**kwargs):
            content = kwargs.get("messages", [{}])[-1].get("content", "")
            system = kwargs.get("messages", [{}])[0].get("content", "")

            if "审核" in content or "审核" in system:
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
        brief = {
            "topic": "测试选题",
            "title_formula": "问句式",
            "pillar": "亲密关系洞察",
            "target_interaction": "评论驱动",
            "status": "not_started",
        }

        try:
            orchestrator = Orchestrator()
            result = orchestrator.run(brief, tmpdir)

            self.assertIn("draft", result)
            self.assertIn("review", result)
            self.assertIn("comments", result)
            self.assertIn("rounds", result)
            self.assertNotEqual(result.get("status"), "abandoned")
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    @patch("core.agents.base._call_api")
    @patch("core.image_generator.generate_cover_ai", return_value=None)
    def test_run_abandons_after_max_rounds(self, mock_cover, mock_api):
        """连续 C 级应触发放弃。"""
        writer_content = (
            "【封面页】\n"
            "大字标题: 测试标题\n"
            "情绪钩子小字: 测试小字\n"
            "英文AI绘画prompt: A test scene\n\n"
            "【正文】\n"
            + "这是一段测试正文内容。\n" * 30
            + "\n\n【话题标签】\n#不懂就问有问必答 #测试标签1 #测试标签2\n"
        )

        call_count = {"n": 0}

        def fake_call_api(**kwargs):
            content = kwargs.get("messages", [{}])[-1].get("content", "")
            system = kwargs.get("messages", [{}])[0].get("content", "")

            if "审核" in content or "审核" in system:
                # 始终返回 C 级
                return {"choices": [{"message": {"content": json.dumps({
                    "verdict": "fail", "grade": "C",
                    "issues": [{"problem": "内容质量不足", "location": "全文", "suggestion": "重写"}],
                    "suggestions": [{"location": "全文", "idea": "重写"}], "strengths": [],
                    "overall_comment": "不合格",
                    "needs_redesign": False, "needs_relayout": False,
                }, ensure_ascii=False)}}]}
            elif "读者体验" in content:
                return {"choices": [{"message": {"content": json.dumps({
                    "grade": "C", "quality_issues": ["质量差"],
                    "quality_suggestions": ["重写"],
                    "discussion_potential": "low",
                }, ensure_ascii=False)}}]}
            elif "评论" in content or "回复模板" in content:
                return {"choices": [{"message": {"content": json.dumps({
                    "comments": [{"type": "resonance", "text": "..."}],
                    "reply_templates": ["..."],
                }, ensure_ascii=False)}}]}
            elif "选题" in content or "brief" in content.lower():
                return {"choices": [{"message": {"content": "增强后的brief"}}]}
            else:
                return {"choices": [{"message": {"content": writer_content}}]}

        mock_api.side_effect = fake_call_api

        tmpdir = tempfile.mkdtemp()
        brief = {
            "topic": "测试选题",
            "title_formula": "问句式",
            "pillar": "亲密关系洞察",
            "target_interaction": "评论驱动",
        }

        try:
            orchestrator = Orchestrator()
            result = orchestrator.run(brief, tmpdir)

            self.assertEqual(result.get("status"), "abandoned")
            self.assertGreaterEqual(result.get("rounds", 0), 3)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    @patch("core.agents.base._call_api")
    @patch("core.image_generator.generate_cover_ai", return_value=None)
    def test_run_s_grade_passes_immediately(self, mock_cover, mock_api):
        """S 级应在第 1 轮直接通过。"""
        writer_content = (
            "【封面页】\n"
            "大字标题: 测试标题\n"
            "情绪钩子小字: 测试小字\n"
            "英文AI绘画prompt: A test scene\n\n"
            "【正文】\n"
            + "这是一段测试正文内容。\n" * 30
            + "\n\n【话题标签】\n#不懂就问有问必答 #测试标签1 #测试标签2\n"
        )

        def fake_call_api(**kwargs):
            content = kwargs.get("messages", [{}])[-1].get("content", "")
            system = kwargs.get("messages", [{}])[0].get("content", "")

            if "审核" in content or "审核" in system:
                return {"choices": [{"message": {"content": json.dumps({
                    "verdict": "pass", "grade": "S", "issues": [], "suggestions": [],
                    "strengths": ["完美"], "overall_comment": "优秀",
                    "needs_redesign": False, "needs_relayout": False,
                }, ensure_ascii=False)}}]}
            elif "读者体验" in content:
                return {"choices": [{"message": {"content": json.dumps({
                    "grade": "S", "quality_issues": [], "quality_suggestions": [],
                    "discussion_potential": "high",
                }, ensure_ascii=False)}}]}
            elif "评论" in content or "回复模板" in content:
                return {"choices": [{"message": {"content": json.dumps({
                    "comments": [{"type": "resonance", "text": "太棒了"}],
                    "reply_templates": ["抱抱"],
                }, ensure_ascii=False)}}]}
            elif "选题" in content or "brief" in content.lower():
                return {"choices": [{"message": {"content": "增强后的brief"}}]}
            else:
                return {"choices": [{"message": {"content": writer_content}}]}

        mock_api.side_effect = fake_call_api

        tmpdir = tempfile.mkdtemp()
        brief = {
            "topic": "测试选题",
            "title_formula": "问句式",
            "pillar": "亲密关系洞察",
            "target_interaction": "评论驱动",
        }

        try:
            orchestrator = Orchestrator()
            result = orchestrator.run(brief, tmpdir)

            self.assertEqual(result.get("rounds"), 1)
            self.assertEqual(result["review"]["grade"], "S")
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestChiefEditorOrchestrate(unittest.TestCase):
    """测试 ChiefEditor.orchestrate() 编排循环。"""

    @patch("core.agents.base._call_api")
    @patch("core.image_generator.generate_cover_ai", return_value=None)
    def test_orchestrate_coordinates_agents(self, mock_cover, mock_api):
        """orchestrate() 应协调 writer、editor、community 完成创作。"""
        writer_content = (
            "【封面页】\n"
            "大字标题: 测试标题\n"
            "情绪钩子小字: 测试小字\n"
            "英文AI绘画prompt: A test scene\n\n"
            "【正文】\n"
            + "这是一段测试正文内容。\n" * 30
            + "\n\n【话题标签】\n#不懂就问有问必答 #测试标签1 #测试标签2\n"
        )

        def fake_call_api(**kwargs):
            content = kwargs.get("messages", [{}])[-1].get("content", "")
            system = kwargs.get("messages", [{}])[0].get("content", "")

            if "审核" in content or "审核" in system:
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
            elif "请创作" in content or "写一篇" in content:
                return {"choices": [{"message": {"content": writer_content}}]}
            else:
                return {"choices": [{"message": {"content": "增强后的brief"}}]}

        mock_api.side_effect = fake_call_api

        tmpdir = tempfile.mkdtemp()
        brief = {
            "topic": "测试选题",
            "title_formula": "问句式",
            "pillar": "亲密关系洞察",
            "target_interaction": "评论驱动",
        }

        try:
            from core.agents import (
                EmotionalWriter, CoverDesigner, ContentEditor,
                LayoutArtist, CommunityManager, ChiefEditor,
            )
            bus = MessageBus()
            writer = EmotionalWriter(bus)
            designer = CoverDesigner(bus)
            artist = LayoutArtist(bus)
            editor = ContentEditor(bus)
            community = CommunityManager(bus)
            chief = ChiefEditor(bus)

            result = chief.orchestrate(
                brief=brief,
                writer=writer,
                designer=designer,
                artist=artist,
                editor=editor,
                community=community,
                out_dir=tmpdir,
            )

            self.assertIn("draft", result)
            self.assertIn("review", result)
            # 验证 LLM 被调用多次（writer + editor + community）
            self.assertGreaterEqual(mock_api.call_count, 3, "LLM 应被调用至少 3 次")
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
