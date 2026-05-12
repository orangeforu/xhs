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
        blocks = [
            ("段落1", False, False),
            ("", False, True),
            ("段落2", False, False),
        ]
        pages = _paginate_blocks(blocks)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0][1][0], "__separator__")

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
