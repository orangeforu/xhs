"""Tests for core.trend_detector — 热点抓取和过滤。"""

from core.trend_detector import filter_emotional_keywords, EMOTIONAL_KEYWORDS, EXCLUDE_KEYWORDS


class TestFilterEmotionalKeywords:
    """测试热点关键词过滤。"""

    def test_emotional_keywords_kept(self):
        trending = ["独居女生的安全感", "恋爱脑的10个表现", "分手后要不要删好友"]
        result = filter_emotional_keywords(trending)
        assert len(result) == 3

    def test_excluded_keywords_filtered(self):
        trending = ["NBA总决赛", "原神新版本", "股票大涨", "世界杯决赛"]
        result = filter_emotional_keywords(trending)
        assert len(result) == 0

    def test_mixed_keywords(self):
        trending = [
            "独居女生的安全感",  # 情感
            "NBA总决赛",  # 排除
            "分手后要不要删好友",  # 情感
            "原神新版本",  # 排除
            "为什么越来越多人不想结婚",  # 情感（含"为什么"）
        ]
        result = filter_emotional_keywords(trending)
        assert "独居女生的安全感" in result
        assert "分手后要不要删好友" in result
        assert "为什么越来越多人不想结婚" in result
        assert "NBA总决赛" not in result
        assert "原神新版本" not in result

    def test_question_words_detected(self):
        trending = ["为什么90后不想生孩子", "该不该为了孩子不离婚"]
        result = filter_emotional_keywords(trending)
        assert len(result) == 2

    def test_max_10_results(self):
        trending = [f"情感话题{i}" for i in range(20)]
        result = filter_emotional_keywords(trending)
        assert len(result) <= 10

    def test_empty_input(self):
        assert filter_emotional_keywords([]) == []

    def test_no_emotional_content(self):
        trending = ["科技新闻", "体育赛事", "娱乐八卦"]
        result = filter_emotional_keywords(trending)
        assert len(result) == 0
