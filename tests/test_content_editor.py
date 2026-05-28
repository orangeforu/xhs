import unittest

from core.agents.content_editor import ContentEditor


class TestParseReview(unittest.TestCase):
    """测试审核结果解析 — JSON 路径和回退文本路径。"""

    def setUp(self):
        self.editor = ContentEditor.__new__(ContentEditor)

    def test_valid_json_fills_defaults(self):
        raw = '{"grade": "A", "verdict": "pass", "issues": [], "strengths": ["好"]}'
        result = self.editor._parse_review(raw)
        self.assertEqual(result["grade"], "A")
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["strengths"], ["好"])
        self.assertEqual(result["suggestions"], [])
        self.assertEqual(result["overall_comment"], "")
        self.assertFalse(result["needs_redesign"])
        self.assertFalse(result["needs_relayout"])

    def test_json_with_all_fields(self):
        raw = '''{
            "grade": "S",
            "verdict": "pass",
            "issues": [{"location": "第2页", "problem": "节奏略快"}],
            "suggestions": [{"location": "结尾", "idea": "加留白"}],
            "strengths": ["画面感强"],
            "overall_comment": "优秀作品",
            "needs_redesign": true,
            "needs_relayout": false
        }'''
        result = self.editor._parse_review(raw)
        self.assertEqual(result["grade"], "S")
        self.assertTrue(result["needs_redesign"])
        self.assertEqual(len(result["issues"]), 1)

    def test_json_missing_optional_fields(self):
        raw = '{"grade": "B"}'
        result = self.editor._parse_review(raw)
        self.assertEqual(result["grade"], "B")
        self.assertEqual(result["verdict"], "conditional")
        self.assertIsInstance(result["issues"], list)

    def test_fallback_text_grade_a(self):
        raw = 'Some analysis text\n"grade": "A"\nverdict: pass'
        result = self.editor._parse_review(raw)
        self.assertEqual(result["grade"], "A")

    def test_fallback_text_grade_c(self):
        raw = 'Analysis:\ngrade: C\nThis content has issues.'
        result = self.editor._parse_review(raw)
        self.assertEqual(result["grade"], "C")

    def test_fallback_text_verdict_fail(self):
        raw = '{"broken": json\nverdict: fail'
        result = self.editor._parse_review(raw)
        self.assertEqual(result["verdict"], "fail")

    def test_fallback_text_defaults(self):
        raw = 'No structured data here.'
        result = self.editor._parse_review(raw)
        self.assertEqual(result["grade"], "B")
        self.assertEqual(result["verdict"], "conditional")
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["suggestions"], [])

    def test_fallback_preserves_raw_in_comment(self):
        raw = "A" * 600
        result = self.editor._parse_review(raw)
        self.assertEqual(len(result["overall_comment"]), 500)


if __name__ == "__main__":
    unittest.main()
