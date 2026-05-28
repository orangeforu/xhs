import unittest
from unittest.mock import patch

from core.topic_selector import _avg_grade_score, _score_topic, smart_select, smart_batch
from generate_topics import _extract_keywords, _is_similar


class TestExtractKeywords(unittest.TestCase):
    def test_chinese_bigrams(self):
        # _extract_keywords 用 bigram 提取中文关键词
        kw = _extract_keywords("为什么你总是情绪反刍")
        self.assertIn("为什", kw)
        self.assertIn("什么", kw)
        self.assertIn("情绪", kw)
        self.assertIn("反刍", kw)

    def test_mixed_keywords(self):
        kw = _extract_keywords("独居生活 guidebook")
        self.assertIn("独居", kw)
        self.assertIn("居生", kw)
        self.assertIn("guidebook", kw)

    def test_short_chinese(self):
        # "我你他" 3个字符，生成 bigrams: "我你", "你他"
        kw = _extract_keywords("我你他")
        self.assertEqual(len(kw), 2)
        self.assertIn("我你", kw)
        self.assertIn("你他", kw)


class TestIsSimilar(unittest.TestCase):
    def test_identical(self):
        self.assertTrue(_is_similar("搭子社交的真相", "搭子社交的真相"))

    def test_similar(self):
        # 共享关键词"搭子社交"占比高
        self.assertTrue(_is_similar("搭子社交背后的情感真相", "搭子社交的情感秘密"))

    def test_different(self):
        self.assertFalse(_is_similar("恋爱中的边界感", "职场人际关系处理"))

    def test_empty(self):
        self.assertFalse(_is_similar("", "test"))

    def test_partial_overlap(self):
        # 部分重叠但不够相似
        self.assertFalse(_is_similar("恋爱中的边界感很重要", "独居生活的仪式感"))


class TestAvgGradeScore(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(_avg_grade_score([]), 0.5)

    def test_all_s(self):
        self.assertEqual(_avg_grade_score(["S", "S"]), 1.0)

    def test_mixed(self):
        score = _avg_grade_score(["S", "C"])
        self.assertAlmostEqual(score, 0.55)


class TestScoreTopic(unittest.TestCase):
    def test_fresh_topic_high_freshness(self):
        topic = {"topic": "test", "title_formula": "问句式", "pillar": "自我成长",
                 "target_interaction": "评论驱动", "status": "not_started"}
        history = {"has_data": False, "formula_grades": {}, "pillar_grades": {},
                   "interaction_grades": {}, "recent_formulas": [], "recent_pillars": []}
        scores = _score_topic(topic, history, [])
        self.assertEqual(scores["freshness"], 1.0)

    def test_published_topic_low_freshness(self):
        topic = {"topic": "test", "title_formula": "问句式", "pillar": "自我成长",
                 "target_interaction": "评论驱动", "status": "published"}
        history = {"has_data": False, "formula_grades": {}, "pillar_grades": {},
                   "interaction_grades": {}, "recent_formulas": [], "recent_pillars": []}
        scores = _score_topic(topic, history, [])
        self.assertEqual(scores["freshness"], 0.0)


class TestSmartSelect(unittest.TestCase):
    def test_returns_topic(self):
        pool = [
            {"topic": "test1", "title_formula": "问句式", "pillar": "自我成长",
             "target_interaction": "评论驱动", "status": "not_started"},
            {"topic": "test2", "title_formula": "观点冲击式", "pillar": "亲密关系洞察",
             "target_interaction": "分享驱动", "status": "not_started"},
        ]
        topic, scores = smart_select(topic_pool=pool)
        self.assertIsNotNone(topic)
        self.assertIn("total", scores)

    def test_empty_pool(self):
        topic, scores = smart_select(topic_pool=[])
        self.assertIsNone(topic)


class TestSmartBatch(unittest.TestCase):
    def test_diversity(self):
        pool = [
            {"topic": f"test{i}", "title_formula": f"formula{i % 2}", "pillar": f"pillar{i % 3}",
             "target_interaction": "评论驱动", "status": "not_started"}
            for i in range(10)
        ]
        batch = smart_batch(count=3, topic_pool=pool)
        self.assertEqual(len(batch), 3)
        # 应该有不同的 formula
        formulas = [t["title_formula"] for t in batch]
        self.assertGreater(len(set(formulas)), 1)


if __name__ == "__main__":
    unittest.main()
