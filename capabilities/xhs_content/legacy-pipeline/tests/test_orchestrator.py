"""Tests for write_note_file and format_review — 笔记文件写入和审核格式化。"""

from core.utils import format_review, write_note_file


class TestFormatReview:
    """测试 format_review 纯函数。"""

    def test_none_review(self):
        assert format_review(None) == "审核信息缺失"

    def test_empty_review(self):
        result = format_review({})
        assert "审核信息缺失" in result  # 空 dict 等同于 falsy

    def test_review_with_defaults(self):
        result = format_review({"issues": [], "strengths": []})
        assert "B" in result  # 默认 grade
        assert "unknown" in result  # 默认 verdict

    def test_full_review(self):
        review = {
            "grade": "A",
            "verdict": "pass",
            "issues": [
                {"location": "第2页", "problem": "节奏略快", "suggestion": "加一段留白"},
                {"location": "结尾", "problem": "钩子不够强"},
            ],
            "suggestions": [
                {"location": "开头", "idea": "可以用对话开场"},
            ],
            "strengths": ["情绪真实", "画面感强"],
        }
        result = format_review(review)
        assert "A" in result
        assert "pass" in result
        assert "第2页" in result
        assert "节奏略快" in result
        assert "加一段留白" in result
        assert "钩子不够强" in result
        assert "对话开场" in result
        assert "情绪真实" in result
        assert "画面感强" in result

    def test_review_no_issues(self):
        review = {"grade": "S", "verdict": "pass", "strengths": ["完美"]}
        result = format_review(review)
        assert "S" in result
        assert "完美" in result
        assert "问题" not in result  # 无 issues section

    def test_review_no_suggestions(self):
        review = {"grade": "B", "verdict": "conditional", "issues": [{"location": "全文", "problem": "深度不足"}]}
        result = format_review(review)
        assert "深度不足" in result
        assert "建议" not in result  # 无 suggestions section

    def test_review_no_strengths(self):
        review = {"grade": "C", "verdict": "fail"}
        result = format_review(review)
        assert "C" in result
        assert "优点" not in result  # 无 strengths section


class TestWriteNoteFile:
    """测试 write_note_file 文件写入。"""

    def _make_brief(self):
        return {"topic": "测试选题"}

    def _make_draft(self):
        return {"content": "这是正文内容。"}

    def _make_review(self):
        return {"grade": "A", "verdict": "pass", "issues": [], "strengths": ["好"]}

    def test_basic_output(self, tmp_path):
        out = str(tmp_path / "note.md")
        write_note_file(out, self._make_brief(), self._make_draft(), self._make_review(),
                        {}, [], {"comments": []}, rounds=1)
        content = open(out, encoding="utf-8").read()
        assert "# 测试选题" in content
        assert "这是正文内容" in content
        assert "## 审核结果" in content
        assert "A" in content

    def test_with_cover_paths(self, tmp_path):
        out = str(tmp_path / "note.md")
        covers = {"ai": "/path/to/cover_ai.png", "warm": "/path/to/cover_warm.png"}
        write_note_file(out, self._make_brief(), self._make_draft(), self._make_review(),
                        covers, [], {"comments": []}, rounds=1)
        content = open(out, encoding="utf-8").read()
        assert "封面文件" in content
        assert "cover_ai.png" in content
        assert "cover_warm.png" in content

    def test_with_inner_paths(self, tmp_path):
        out = str(tmp_path / "note.md")
        inners = ["/path/inner_1.png", "/path/inner_2.png"]
        write_note_file(out, self._make_brief(), self._make_draft(), self._make_review(),
                        {}, inners, {"comments": []}, rounds=1)
        content = open(out, encoding="utf-8").read()
        assert "内页文件" in content
        assert "inner_1.png" in content

    def test_with_classified_comments(self, tmp_path):
        out = str(tmp_path / "note.md")
        comments = {
            "comments": ["评论1", "评论2"],
            "comments_classified": [
                {"type": "resonance", "text": "太真实了"},
                {"type": "discussion_starter", "text": "你们觉得呢？"},
            ],
            "reply_templates": ["谢谢喜欢", "抱抱你"],
        }
        write_note_file(out, self._make_brief(), self._make_draft(), self._make_review(),
                        {}, [], comments, rounds=2)
        content = open(out, encoding="utf-8").read()
        assert "预设评论" in content
        assert "情感共鸣" in content
        assert "太真实了" in content
        assert "引导讨论" in content
        assert "博主回复模板" in content
        assert "谢谢喜欢" in content

    def test_with_plain_comments_fallback(self, tmp_path):
        out = str(tmp_path / "note.md")
        comments = {"comments": ["纯文本评论1", "纯文本评论2"]}
        write_note_file(out, self._make_brief(), self._make_draft(), self._make_review(),
                        {}, [], comments, rounds=1)
        content = open(out, encoding="utf-8").read()
        assert "纯文本评论1" in content
        assert "纯文本评论2" in content

    def test_empty_cover_and_inner(self, tmp_path):
        out = str(tmp_path / "note.md")
        write_note_file(out, self._make_brief(), self._make_draft(), self._make_review(),
                        {}, [], {"comments": []}, rounds=1)
        content = open(out, encoding="utf-8").read()
        assert "封面文件" not in content
        assert "内页文件" not in content

    def test_review_comment_included(self, tmp_path):
        out = str(tmp_path / "note.md")
        review = {"grade": "A", "verdict": "pass", "overall_comment": "优秀作品"}
        write_note_file(out, self._make_brief(), self._make_draft(), review,
                        {}, [], {"comments": []}, rounds=1)
        content = open(out, encoding="utf-8").read()
        assert "优秀作品" in content
