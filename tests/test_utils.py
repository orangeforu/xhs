import unittest

from core.utils import extract_json_from_llm, clean_md, load_prompt


class TestExtractJsonFromLlm(unittest.TestCase):
    """测试从 LLM 输出中提取 JSON 的稳健性。"""

    def test_simple_json(self):
        raw = '{"grade": "A", "verdict": "pass"}'
        result = extract_json_from_llm(raw)
        self.assertEqual(result["grade"], "A")
        self.assertEqual(result["verdict"], "pass")

    def test_nested_json(self):
        raw = '{"issues": [{"location": "第1页", "problem": "开场太慢"}]}'
        result = extract_json_from_llm(raw)
        self.assertIsInstance(result["issues"], list)
        self.assertEqual(result["issues"][0]["location"], "第1页")

    def test_deeply_nested_json(self):
        raw = '{"a": {"b": {"c": [1, 2, 3]}}}'
        result = extract_json_from_llm(raw)
        self.assertEqual(result["a"]["b"]["c"], [1, 2, 3])

    def test_json_with_markdown_wrapper(self):
        raw = '```json\n{"grade": "B"}\n```'
        result = extract_json_from_llm(raw)
        self.assertEqual(result["grade"], "B")

    def test_json_with_surrounding_text(self):
        raw = 'Here is my analysis:\n{"grade": "A", "verdict": "pass"}\nDone.'
        result = extract_json_from_llm(raw)
        self.assertEqual(result["grade"], "A")

    def test_no_json_returns_none(self):
        raw = "This is just text with no JSON."
        result = extract_json_from_llm(raw)
        self.assertIsNone(result)

    def test_empty_string_returns_none(self):
        result = extract_json_from_llm("")
        self.assertIsNone(result)

    def test_escaped_quotes_in_json(self):
        raw = '{"text": "他说\\"你好\\""}'
        result = extract_json_from_llm(raw)
        self.assertEqual(result["text"], '他说"你好"')

    def test_invalid_json_returns_none(self):
        raw = '{"grade": "A", "broken": }'
        result = extract_json_from_llm(raw)
        self.assertIsNone(result)

    def test_multiple_json_objects_returns_first(self):
        raw = '{"a": 1} some text {"b": 2}'
        result = extract_json_from_llm(raw)
        self.assertEqual(result, {"a": 1})


class TestCleanMd(unittest.TestCase):
    """测试 Markdown 清理。"""

    def test_bold_removal(self):
        self.assertEqual(clean_md("**hello**"), "hello")

    def test_italic_removal(self):
        self.assertEqual(clean_md("*hello*"), "hello")

    def test_strikethrough_removal(self):
        self.assertEqual(clean_md("~~hello~~"), "hello")

    def test_inline_code_removal(self):
        self.assertEqual(clean_md("`hello`"), "hello")

    def test_none_returns_empty(self):
        self.assertEqual(clean_md(None), "")

    def test_empty_string(self):
        self.assertEqual(clean_md(""), "")

    def test_mixed_markdown(self):
        self.assertEqual(clean_md("**bold** and *italic*"), "bold and italic")


class TestLoadPrompt(unittest.TestCase):
    """测试 prompt 加载。"""

    def test_load_existing_prompt(self):
        content = load_prompt("agent_writer")
        self.assertIn("情感博主", content)

    def test_load_nonexistent_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_prompt("nonexistent_file_xyz")


if __name__ == "__main__":
    unittest.main()
