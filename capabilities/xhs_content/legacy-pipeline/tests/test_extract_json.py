"""测试 extract_json_from_llm — 从 LLM 输出中稳健提取嵌套 JSON。"""

import json
import unittest

from core.utils import extract_json_from_llm


class TestExtractJsonFromLlm(unittest.TestCase):

    def test_simple_flat_json(self):
        raw = '{"grade": "A", "verdict": "pass"}'
        result = extract_json_from_llm(raw)
        self.assertEqual(result["grade"], "A")
        self.assertEqual(result["verdict"], "pass")

    def test_nested_objects(self):
        """这是旧正则 \\{[^{}]*\\} 会失败的场景。"""
        raw = '{"issues": [{"location": "第1页", "problem": "开场太慢", "suggestion": "直接进故事"}]}'
        result = extract_json_from_llm(raw)
        self.assertEqual(len(result["issues"]), 1)
        self.assertEqual(result["issues"][0]["problem"], "开场太慢")

    def test_deeply_nested(self):
        raw = '{"a": {"b": {"c": [1, 2, 3]}}}'
        result = extract_json_from_llm(raw)
        self.assertEqual(result["a"]["b"]["c"], [1, 2, 3])

    def test_json_with_surrounding_text(self):
        raw = '这是我的审核结果：\n{"grade": "B", "verdict": "conditional"}\n以上。'
        result = extract_json_from_llm(raw)
        self.assertEqual(result["grade"], "B")

    def test_json_with_code_fence(self):
        raw = '```json\n{"grade": "A", "issues": []}\n```'
        result = extract_json_from_llm(raw)
        self.assertEqual(result["grade"], "A")

    def test_string_with_escaped_quotes(self):
        raw = '{"text": "他说\\"你好\\""}'
        result = extract_json_from_llm(raw)
        self.assertEqual(result["text"], '他说"你好"')

    def test_no_json_returns_none(self):
        raw = '这里没有任何 JSON 内容。'
        result = extract_json_from_llm(raw)
        self.assertIsNone(result)

    def test_invalid_json_returns_none(self):
        raw = '{grade: A}'  # 无引号的 key
        result = extract_json_from_llm(raw)
        self.assertIsNone(result)

    def test_multiple_json_objects_returns_first(self):
        raw = '{"a": 1} some text {"b": 2}'
        result = extract_json_from_llm(raw)
        self.assertEqual(result, {"a": 1})

    def test_empty_string(self):
        result = extract_json_from_llm("")
        self.assertIsNone(result)

    def test_real_world_llm_output(self):
        """模拟真实 LLM 输出，带前后解释文字。"""
        raw = """根据审核标准，我对这篇笔记的评估如下：

{
  "verdict": "conditional",
  "grade": "B",
  "issues": [
    {"location": "第2页", "problem": "情绪断层", "suggestion": "加一个过渡场景"},
    {"location": "结尾", "problem": "互动钩子太弱", "suggestion": "用二选一问题"}
  ],
  "suggestions": [
    {"location": "封面", "idea": "标题可以更具体"}
  ],
  "strengths": ["开场有冲击力", "对话真实"],
  "overall_comment": "质量不错但需要优化细节",
  "needs_redesign": false,
  "needs_relayout": false
}

以上是我的审核意见。"""
        result = extract_json_from_llm(raw)
        self.assertEqual(result["grade"], "B")
        self.assertEqual(len(result["issues"]), 2)
        self.assertEqual(result["issues"][0]["location"], "第2页")
        self.assertFalse(result["needs_redesign"])


if __name__ == "__main__":
    unittest.main()
