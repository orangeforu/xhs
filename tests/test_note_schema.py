"""NoteRecord 统一解析 schema 的测试。"""

import unittest

from core.note_schema import NoteRecord, _to_int


def _detail(liked="1234", collected="56", comment="7", share="0", title="示例标题", tags=None):
    return {
        "data": {
            "items": [
                {
                    "note_card": {
                        "title": title,
                        "interact_info": {
                            "liked_count": liked,
                            "collected_count": collected,
                            "comment_count": comment,
                            "share_count": share,
                        },
                        "tag_list": [{"name": t} for t in (tags or [])],
                    }
                }
            ]
        }
    }


class TestToInt(unittest.TestCase):
    def test_string_digit(self):
        self.assertEqual(_to_int("1234"), 1234)

    def test_int_passthrough(self):
        self.assertEqual(_to_int(1234), 1234)

    def test_chinese_unit_to_zero(self):
        self.assertEqual(_to_int("1.2万"), 0)

    def test_empty_to_zero(self):
        self.assertEqual(_to_int(""), 0)
        self.assertEqual(_to_int(None), 0)

    def test_bool_to_zero(self):
        self.assertEqual(_to_int(True), 0)


class TestFromApiDetail(unittest.TestCase):
    def test_normal_parse(self):
        rec = NoteRecord.from_api_detail(
            _detail(liked="1500", collected="200", comment="30", share="5", tags=["不懂就问有问必答", "失恋"]),
            note_id="abc123",
            url="https://www.xiaohongshu.com/explore/abc123",
        )
        self.assertEqual(rec.note_id, "abc123")
        self.assertEqual(rec.title, "示例标题")
        self.assertEqual(rec.likes, 1500)
        self.assertEqual(rec.collects, 200)
        self.assertEqual(rec.comments, 30)
        self.assertEqual(rec.shares, 5)
        self.assertEqual(rec.tags, ["不懂就问有问必答", "失恋"])

    def test_string_counts_from_api(self):
        # spider_xhs 偶尔返回字符串型计数
        rec = NoteRecord.from_api_detail(_detail(liked="999"))
        self.assertEqual(rec.likes, 999)

    def test_missing_items_returns_empty(self):
        # items 缺失不应抛异常，返回空字段（与历史行为一致）
        rec = NoteRecord.from_api_detail({"data": {}})
        self.assertEqual(rec.title, "")
        self.assertEqual(rec.likes, 0)
        self.assertEqual(rec.tags, [])

    def test_empty_items_list_returns_empty(self):
        # items=[] 历史上会 IndexError，这里降级为空字段（更稳健）
        rec = NoteRecord.from_api_detail({"data": {"items": []}})
        self.assertEqual(rec.title, "")
        self.assertEqual(rec.likes, 0)

    def test_tag_list_with_non_dict_entries(self):
        detail = {
            "data": {
                "items": [
                    {"note_card": {"tag_list": [{"name": "ok"}, "junk", 123, {"no": "name"}]}}
                ]
            }
        }
        rec = NoteRecord.from_api_detail(detail)
        self.assertEqual(rec.tags, ["ok"])

    def test_to_dict_roundtrip(self):
        rec = NoteRecord.from_api_detail(_detail(liked="10"), note_id="x", url="u")
        d = rec.to_dict()
        self.assertEqual(d["note_id"], "x")
        self.assertEqual(d["likes"], 10)
        self.assertEqual(d["title"], "示例标题")


if __name__ == "__main__":
    unittest.main()
