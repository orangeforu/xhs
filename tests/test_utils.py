import unittest

from core.utils import clean_md, load_prompt


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
