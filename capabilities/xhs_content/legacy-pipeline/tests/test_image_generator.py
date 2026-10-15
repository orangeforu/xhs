import unittest

from core.image_generator import _paginate_blocks


class TestPaginateBlocks(unittest.TestCase):
    def test_single_page(self):
        blocks = [
            ("短段落1", False, False),
            ("短段落2", False, False),
        ]
        pages = _paginate_blocks(blocks)
        self.assertEqual(len(pages), 1)
        self.assertEqual(len(pages[0]), 2)

    def test_separator_handling(self):
        # separator 是强制分页符（commit 4381bb6 重构后语义）：
        # 遇到 `---`/空行 → 分页，separator 自身不入页。
        # 但两页都很短（≤3 行）时会触发极短页合并 → 重新合成 1 页。
        blocks = [
            ("段落1", False, False),
            ("", False, True),
            ("段落2", False, False),
        ]
        pages = _paginate_blocks(blocks)
        # 合并后应为 1 页，且页内不应残留 separator（它只是分页符）
        self.assertEqual(len(pages), 1)
        self.assertNotIn("__separator__", [b[0] for b in pages[0]])

    def test_bold_blocks(self):
        blocks = [
            ("金句内容", True, False),
        ]
        pages = _paginate_blocks(blocks)
        self.assertEqual(len(pages), 1)
        self.assertTrue(pages[0][0][1])

    def test_multiple_pages(self):
        long_text = "这是一句很长的话。" * 200
        blocks = [
            (long_text, False, False),
        ]
        pages = _paginate_blocks(blocks)
        self.assertGreaterEqual(len(pages), 1)

    def test_empty_blocks(self):
        pages = _paginate_blocks([])
        self.assertEqual(pages, [])

    def test_separator_at_page_boundary(self):
        blocks = [
            ("段落1", False, False),
            ("", False, True),
            ("段落2", False, False),
        ]
        pages = _paginate_blocks(blocks)
        self.assertEqual(len(pages), 1)


if __name__ == "__main__":
    unittest.main()
