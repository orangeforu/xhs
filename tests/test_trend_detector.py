"""Tests for core.trend_detector — 热点抓取和过滤。

对齐 filter_emotional_keywords 的实际契约：入参为 list[dict]（每项含 keyword），
体育赛事（NBA/世界杯等）有意保留（可转化为赛事期间的情感冲突）。
"""
from core.trend_detector import filter_emotional_keywords


def _kw(*words):
    """构造 [{"keyword": w}, ...] 格式的热点列表。"""
    return [{"keyword": w} for w in words]


class TestFilterEmotionalKeywords:
    """测试热点关键词过滤。"""

    def test_emotional_keywords_kept(self):
        result = filter_emotional_keywords(_kw("独居女生的安全感", "恋爱脑的10个表现", "分手后要不要删好友"))
        assert len(result) == 3

    def test_excluded_keywords_filtered(self):
        # 纯金融/军事/数码 → 命中 EXCLUDE_KEYWORDS 被过滤
        result = filter_emotional_keywords(_kw("股票大涨", "基金暴跌", "军事演习", "芯片发布会"))
        assert len(result) == 0

    def test_sports_trends_kept(self):
        # 体育赛事有意保留（可转化为赛事期间的情感冲突）— 实现设计如此
        result = filter_emotional_keywords(_kw("NBA总决赛", "世界杯决赛"))
        assert len(result) == 2

    def test_mixed_keywords(self):
        result = filter_emotional_keywords(_kw(
            "独居女生的安全感",            # 情感(独居) → 保留
            "股票大涨",                    # 排除(股票)
            "分手后要不要删好友",          # 情感(分手) → 保留
            "原神新版本",                  # 不匹配 → 过滤
            "为什么越来越多人不想结婚",    # 情感(为什么+结婚) → 保留
        ))
        keywords = [r["keyword"] for r in result]
        assert "独居女生的安全感" in keywords
        assert "分手后要不要删好友" in keywords
        assert "为什么越来越多人不想结婚" in keywords
        assert "股票大涨" not in keywords
        assert "原神新版本" not in keywords

    def test_question_words_detected(self):
        result = filter_emotional_keywords(_kw("为什么90后不想生孩子", "该不该为了孩子不离婚"))
        assert len(result) == 2

    def test_max_10_results(self):
        # 含"分手"的情感词，20 条全保留后应截断到 10
        result = filter_emotional_keywords(_kw(*[f"分手故事{i}" for i in range(20)]))
        assert len(result) <= 10
        assert len(result) == 10

    def test_empty_input(self):
        assert filter_emotional_keywords([]) == []

    def test_no_emotional_content(self):
        result = filter_emotional_keywords(_kw("科技新闻", "体育赛事", "娱乐八卦"))
        assert len(result) == 0
