import unittest

from core.writer import _extract_content


class TestExtractContent(unittest.TestCase):
    def test_normal_response(self):
        data = {"choices": [{"message": {"content": "Hello world"}}]}
        self.assertEqual(_extract_content(data), "Hello world")

    def test_empty_dict(self):
        with self.assertRaises(ValueError) as ctx:
            _extract_content(None)
        self.assertIn("非 dict 类型", str(ctx.exception))

    def test_no_choices(self):
        with self.assertRaises(ValueError) as ctx:
            _extract_content({})
        self.assertIn("缺少 choices", str(ctx.exception))

    def test_choices_is_none(self):
        with self.assertRaises(ValueError) as ctx:
            _extract_content({"choices": None})
        self.assertIn("缺少 choices", str(ctx.exception))

    def test_choices_empty_list(self):
        with self.assertRaises(ValueError) as ctx:
            _extract_content({"choices": []})
        self.assertIn("缺少 choices", str(ctx.exception))

    def test_choice_item_is_none(self):
        data = {"choices": [None]}
        with self.assertRaises(AttributeError):
            _extract_content(data)

    def test_no_message(self):
        data = {"choices": [{}]}
        with self.assertRaises(ValueError) as ctx:
            _extract_content(data)
        self.assertIn("缺少 content", str(ctx.exception))

    def test_no_content(self):
        data = {"choices": [{"message": {}}]}
        with self.assertRaises(ValueError) as ctx:
            _extract_content(data)
        self.assertIn("缺少 content", str(ctx.exception))

    def test_content_is_none(self):
        data = {"choices": [{"message": {"content": None}}]}
        with self.assertRaises(ValueError) as ctx:
            _extract_content(data)
        self.assertIn("缺少 content", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
