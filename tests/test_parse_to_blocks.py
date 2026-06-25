import unittest

from core.image_generator import _parse_to_blocks, _wrap_text


class TestParseToBlocks(unittest.TestCase):
    """测试文本解析为渲染块。"""

    def test_normal_text(self):
        blocks = _parse_to_blocks("这是一段普通文本")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0][0], "这是一段普通文本")
        self.assertFalse(blocks[0][1])  # not bold
        self.assertFalse(blocks[0][2])  # not separator

    def test_bold_text(self):
        blocks = _parse_to_blocks("**这是加粗文本**")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0][0], "这是加粗文本")
        self.assertTrue(blocks[0][1])  # bold

    def test_separator(self):
        blocks = _parse_to_blocks("---")
        self.assertEqual(len(blocks), 1)
        self.assertTrue(blocks[0][2])  # separator

    def test_filters_skip_markers(self):
        text = "【金句】这是金句\n【互动钩子】评论区见"
        blocks = _parse_to_blocks(text)
        for b in blocks:
            self.assertNotIn("金句", b[0])

    def test_filters_hashtags(self):
        blocks = _parse_to_blocks("#不懂就问有问必答 #情感")
        # 标签应该被过滤
        texts = [b[0] for b in blocks]
        self.assertNotIn("#不懂就问有问必答", texts)

    def test_filters_emoji_only_lines(self):
        blocks = _parse_to_blocks("💔✨👇")
        # 纯 emoji 行应该被过滤
        self.assertEqual(len(blocks), 0)

    def test_mixed_content(self):
        text = "第一段文字\n**加粗段落**\n---\n第二段文字"
        blocks = _parse_to_blocks(text)
        texts = [b[0] for b in blocks]
        self.assertIn("第一段文字", texts)
        self.assertIn("加粗段落", texts)
        self.assertIn("第二段文字", texts)
        separators = [b for b in blocks if b[2]]
        self.assertEqual(len(separators), 1)

    def test_empty_text(self):
        blocks = _parse_to_blocks("")
        self.assertEqual(len(blocks), 0)

    def test_whitespace_only(self):
        blocks = _parse_to_blocks("   \n\n   ")
        self.assertEqual(len(blocks), 0)

    def test_dialogue_protagonist_parsed_as_right_bubble(self):
        """主角方对话行（她：...）识别为右侧气泡（D-05）。"""
        blocks = _parse_to_blocks("她：我今天被领导骂了。")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0][3], "right")

    def test_dialogue_other_role_parsed_as_left_bubble(self):
        """对方对话行（他：...）识别为左侧气泡。"""
        blocks = _parse_to_blocks("他：晚点说。")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0][3], "left")

    def test_non_dialogue_has_no_bubble_side(self):
        """普通叙述句不识别为气泡（side 为 None）。"""
        blocks = _parse_to_blocks("她盯着屏幕看了很久。")
        self.assertEqual(len(blocks), 1)
        self.assertIsNone(blocks[0][3])


class TestWrapText(unittest.TestCase):
    """测试文本换行。"""

    def test_short_text_no_wrap(self):
        from PIL import ImageFont
        font = ImageFont.load_default()
        lines = _wrap_text("短文本", font, 1000)
        self.assertEqual(len(lines), 1)

    def test_empty_text(self):
        from PIL import ImageFont
        font = ImageFont.load_default()
        lines = _wrap_text("", font, 1000)
        self.assertEqual(len(lines), 0)

    def test_long_text_wraps(self):
        from PIL import ImageFont
        font = ImageFont.load_default()
        long_text = "这是一段很长很长的文本" * 20
        lines = _wrap_text(long_text, font, 200)
        self.assertGreater(len(lines), 1)

    def test_newlines_respected(self):
        from PIL import ImageFont
        font = ImageFont.load_default()
        lines = _wrap_text("第一行\n第二行\n第三行", font, 1000)
        self.assertEqual(len(lines), 3)


if __name__ == "__main__":
    unittest.main()
