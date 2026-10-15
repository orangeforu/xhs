import unittest

from core.publish_helpers import (
    calc_formula_stats,
    calc_interaction_rate,
    calc_pillar_stats,
    calculate_grade,
    check_compliance,
    extract_body_for_publish,
    extract_desc,
    extract_tags,
    extract_title,
    extract_title_candidates,
    recalculate_summary,
    resolve_topics,
    score_title,
)


class TestCalculateGrade(unittest.TestCase):
    def test_zero_likes_is_c(self):
        self.assertEqual(calculate_grade(0), "C")

    def test_low_likes_is_c(self):
        self.assertEqual(calculate_grade(199), "C")

    def test_medium_likes_is_b(self):
        self.assertEqual(calculate_grade(200), "B")
        self.assertEqual(calculate_grade(799), "B")

    def test_high_likes_is_a(self):
        self.assertEqual(calculate_grade(800), "A")
        self.assertEqual(calculate_grade(1500), "A")

    def test_very_high_likes_is_s(self):
        self.assertEqual(calculate_grade(1501), "S")
        self.assertEqual(calculate_grade(10000), "S")


class TestCalcInteractionRate(unittest.TestCase):
    def test_normal_calculation(self):
        note = {"likes": 100, "collects": 50, "comments": 30, "shares": 20, "exposure": 1000}
        self.assertAlmostEqual(calc_interaction_rate(note), 0.2)

    def test_zero_exposure(self):
        note = {"likes": 100, "exposure": 0}
        self.assertEqual(calc_interaction_rate(note), 0.0)

    def test_missing_exposure(self):
        note = {"likes": 100}
        self.assertEqual(calc_interaction_rate(note), 0.0)

    def test_missing_fields(self):
        note = {"exposure": 500}
        self.assertAlmostEqual(calc_interaction_rate(note), 0.0)

    def test_empty_note(self):
        self.assertEqual(calc_interaction_rate({}), 0.0)


class TestCalcFormulaStats(unittest.TestCase):
    def test_grouping(self):
        notes = [
            {"title_formula": "问句式", "likes": 100, "collects": 50, "comments": 10, "shares": 5, "exposure": 500},
            {"title_formula": "问句式", "likes": 200, "collects": 80, "comments": 20, "shares": 10, "exposure": 800},
            {"title_formula": "概念解读式", "likes": 50, "collects": 30, "comments": 5, "shares": 2, "exposure": 300},
        ]
        stats = calc_formula_stats(notes)
        self.assertEqual(stats["问句式"]["count"], 2)
        self.assertEqual(stats["问句式"]["total_likes"], 300)
        self.assertEqual(stats["概念解读式"]["count"], 1)

    def test_empty_notes(self):
        self.assertEqual(calc_formula_stats([]), {})

    def test_missing_formula(self):
        notes = [{"likes": 100, "exposure": 500}]
        stats = calc_formula_stats(notes)
        self.assertIn("未知", stats)


class TestCalcPillarStats(unittest.TestCase):
    def test_grouping(self):
        notes = [
            {"pillar": "自我成长", "likes": 100, "collects": 50, "comments": 10, "shares": 5, "exposure": 500},
            {"pillar": "亲密关系洞察", "likes": 200, "collects": 80, "comments": 20, "shares": 10, "exposure": 800},
        ]
        stats = calc_pillar_stats(notes)
        self.assertEqual(stats["自我成长"]["count"], 1)
        self.assertEqual(stats["亲密关系洞察"]["total_likes"], 200)


class TestCheckCompliance(unittest.TestCase):
    def test_all_good(self):
        result = check_compliance(
            content="这是一段足够长的正文内容" * 30,
            title="测试标题 💌",
            tags=["#不懂就问有问必答", "#情感", "#恋爱"],
            image_count=4,
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["issues"], [])

    def test_title_too_long(self):
        result = check_compliance("内容" * 100, "这是一个超级超级超级超级超级超级超级长的标题", ["#tag1", "#tag2", "#tag3"], 4)
        self.assertFalse(result["passed"])
        self.assertTrue(any("标题超长" in i for i in result["issues"]))

    def test_too_few_tags(self):
        result = check_compliance("内容" * 100, "标题 💌", ["#tag1"], 4)
        self.assertTrue(any("标签不足" in i for i in result["issues"]))

    def test_too_many_tags(self):
        result = check_compliance("内容" * 100, "标题 💌", ["#t1", "#t2", "#t3", "#t4", "#t5", "#t6"], 4)
        self.assertTrue(any("标签过多" in i for i in result["issues"]))

    def test_missing_required_tag(self):
        result = check_compliance("内容" * 100, "标题 💌", ["#情感", "#恋爱", "#成长"], 4)
        self.assertTrue(any("不懂就问" in w for w in result["warnings"]))

    def test_sensitive_words(self):
        result = check_compliance("加我微信了解更多", "标题 💌", ["#不懂就问", "#t1", "#t2"], 4)
        self.assertTrue(any("敏感词" in i for i in result["issues"]))

    def test_too_few_images(self):
        result = check_compliance("内容" * 100, "标题 💌", ["#不懂就问", "#t1", "#t2"], 1)
        self.assertTrue(any("图片不足" in i for i in result["issues"]))

    def test_no_emoji_warning(self):
        result = check_compliance("内容" * 100, "标题没有emoji", ["#不懂就问", "#t1", "#t2"], 4)
        self.assertTrue(any("emoji" in w for w in result["warnings"]))


class TestRecalculateSummary(unittest.TestCase):
    def test_basic_summary(self):
        perf = {"notes": [
            {"likes": 100, "collects": 50, "comments": 10, "shares": 5, "exposure": 500, "grade": "A"},
            {"likes": 200, "collects": 80, "comments": 20, "shares": 10, "exposure": 800, "grade": "B"},
        ]}
        recalculate_summary(perf)
        self.assertEqual(perf["summary"]["total_published"], 2)
        self.assertEqual(perf["summary"]["total_likes"], 300)
        self.assertEqual(perf["summary"]["a_grade_count"], 1)
        self.assertEqual(perf["summary"]["b_grade_count"], 1)

    def test_empty_notes(self):
        perf = {"notes": []}
        recalculate_summary(perf)
        self.assertEqual(perf["summary"]["total_published"], 0)


class TestExtractTitleCandidates(unittest.TestCase):
    def test_normal_extraction(self):
        content = """# 笔记标题

【标题候选】
1. 第一个标题 💔
2. 第二个标题 ✨
3. 第三个标题

【封面页】"""
        titles = extract_title_candidates(content)
        self.assertEqual(len(titles), 3)
        self.assertEqual(titles[0], "第一个标题 💔")

    def test_no_candidates(self):
        content = "# 笔记\n\n正文内容"
        self.assertEqual(extract_title_candidates(content), [])


class TestExtractBodyForPublish(unittest.TestCase):
    def test_normal_extraction(self):
        content = """# 标题

【正文】
这是正文第一段。

---

这是正文第二段。

## 审核结果"""
        body = extract_body_for_publish(content)
        self.assertIn("这是正文第一段", body)
        self.assertIn("这是正文第二段", body)
        self.assertNotIn("---", body)

    def test_no_body_returns_empty(self):
        content = "# 标题\n\n【封面页】\n封面内容"
        self.assertEqual(extract_body_for_publish(content), "")


class TestScoreTitle(unittest.TestCase):
    def test_optimal_title(self):
        result = score_title("你有没有过这种奇怪的感觉？💔", {})
        self.assertGreaterEqual(result["score"], 60)
        self.assertTrue(any("长度适中" in r for r in result["reasons"]))

    def test_too_long_title(self):
        result = score_title("这是一个非常非常非常非常非常非常非常长的标题超过了二十个字💔", {})
        self.assertTrue(any("超长" in r for r in result["reasons"]))

    def test_no_emoji(self):
        result = score_title("你有没有过这种感觉", {})
        self.assertTrue(any("emoji" in r for r in result["reasons"]))

    def test_question_mark_bonus(self):
        result = score_title("你有没有过这种感觉？💔", {})
        self.assertTrue(any("问句式" in r for r in result["reasons"]))

    def test_negative_pattern_penalty(self):
        result = score_title("看完沉默了💔", {})
        self.assertTrue(any("低质词" in r for r in result["reasons"]))
        # 50 base + 5 short + 10 emoji - 15 negative = 50
        self.assertLessEqual(result["score"], 50)

    def test_score_clamped(self):
        result = score_title("看完沉默了看完沉默了看完沉默了看完沉默了看完沉默了💔", {})
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)

    def test_level_classification(self):
        result = score_title("短标题💔", {})
        self.assertIn(result["level"], ["S", "A", "B", "C"])

    def test_formula_diversity_penalty(self):
        """同一公式近期使用过多应降分。"""
        # 3 篇近期都用问句式
        perf = {"notes": [
            {"title_formula": "问句式"},
            {"title_formula": "问句式"},
            {"title_formula": "问句式"},
            {"title_formula": "概念解读式"},
            {"title_formula": "观点冲击式"},
        ]}
        result_with_penalty = score_title("你有没有过这种感觉？💔", perf)
        result_without = score_title("你有没有过这种感觉？💔", {})
        # 有惩罚时分数应该更低
        self.assertLess(result_with_penalty["score"], result_without["score"])
        self.assertTrue(any("缺乏多样性" in r or "已用" in r for r in result_with_penalty["reasons"]))

    def test_no_penalty_for_unique_formula(self):
        """近期公式不重复时不应降分。"""
        perf = {"notes": [
            {"title_formula": "问句式"},
            {"title_formula": "概念解读式"},
            {"title_formula": "观点冲击式"},
        ]}
        result = score_title("你有没有过这种感觉？💔", perf)
        self.assertFalse(any("缺乏多样性" in r for r in result["reasons"]))


class _FakeTopicApi:
    """模拟 XHS_Creator_Apis.get_topic：按关键字返回不同结果。"""

    def __init__(self, resolved: set[str], fail: set[str] | None = None):
        self._resolved = resolved
        self._fail = fail or set()

    def get_topic(self, keyword, proxies=None):
        if keyword in self._fail:
            # 模拟 get_topic 抛异常
            raise RuntimeError(f"network error for {keyword}")
        if keyword in self._resolved:
            return True, "ok", {"data": {"topic_info_dtos": [{"id": "1", "link": "x", "name": keyword}]}}
        # 解析成功但无匹配话题
        return True, "ok", {"data": {"topic_info_dtos": []}}


class TestResolveTopics(unittest.TestCase):
    def test_resolved_and_unresolved_split(self):
        api = _FakeTopicApi(resolved={"不懂就问有问必答", "失恋互助"})
        resolved, unresolved = resolve_topics(api, ["不懂就问有问必答", "失恋互助", "冷门标签XYZ"])
        self.assertEqual(resolved, ["不懂就问有问必答", "失恋互助"])
        self.assertEqual(unresolved, ["冷门标签XYZ"])

    def test_api_exception_degrades_to_plain_text(self):
        api = _FakeTopicApi(resolved={"失恋互助"}, fail={"炸了的话题"})
        resolved, unresolved = resolve_topics(api, ["炸了的话题", "失恋互助"])
        self.assertEqual(resolved, ["失恋互助"])
        self.assertEqual(unresolved, ["炸了的话题"])

    def test_empty_tags(self):
        api = _FakeTopicApi(resolved=set())
        self.assertEqual(resolve_topics(api, []), ([], []))

    def test_all_unresolved(self):
        api = _FakeTopicApi(resolved=set())
        resolved, unresolved = resolve_topics(api, ["a", "b"])
        self.assertEqual(resolved, [])
        self.assertEqual(unresolved, ["a", "b"])


class TestExtractTitle(unittest.TestCase):
    """extract_title 单一真源 — 锁住 auto_publish / tabs/publish / knowledge_retrieval 共用的行为。"""

    def test_yaml_frontmatter_title_wins(self):
        content = "---\ntitle: YAML标题\n---\n# markdown标题"
        self.assertEqual(extract_title(content), "YAML标题")

    def test_markdown_h1_fallback(self):
        content = "# 你不是恋爱脑\n\n正文"
        self.assertEqual(extract_title(content), "你不是恋爱脑")

    def test_first_h1_when_multiple(self):
        # MULTILINE ^ 锚定每行，re.search 返回第一个匹配
        content = "# 第一标题\n正文\n# 第二标题"
        self.assertEqual(extract_title(content), "第一标题")

    def test_no_title_returns_placeholder(self):
        self.assertEqual(extract_title("只有正文没有标题"), "未命名笔记")

    def test_strips_whitespace(self):
        content = "#   带空格的标题  \n"
        self.assertEqual(extract_title(content), "带空格的标题")


class TestExtractDesc(unittest.TestCase):
    def test_strips_frontmatter_and_h1(self):
        content = "---\ntitle: T\n---\n# 标题\n正文本体"
        self.assertEqual(extract_desc(content), "正文本体")

    def test_strips_image_and_link_markup(self):
        content = "# 标题\n![alt](img.png)普通文字[点这](http://x)"
        self.assertEqual(extract_desc(content), "普通文字")

    def test_truncates_to_500(self):
        body = "字" * 600
        content = f"# 标题\n{body}"
        self.assertEqual(len(extract_desc(content)), 500)

    def test_strips_leading_whitespace(self):
        content = "# 标题\n\n\n  前导空白正文"
        self.assertEqual(extract_desc(content), "前导空白正文")


class TestExtractTags(unittest.TestCase):
    def test_basic_extraction(self):
        content = "正文 #恋爱脑 #深夜 标签"
        self.assertEqual(extract_tags(content), ["恋爱脑", "深夜"])

    def test_dedup_keeps_order(self):
        content = "#a #b #a #c #b"
        self.assertEqual(extract_tags(content), ["a", "b", "c"])

    def test_empty_returns_empty(self):
        self.assertEqual(extract_tags("没有标签的正文"), [])

    def test_no_false_positive_on_hash_in_text(self):
        # # 后无词字符 → 不算标签
        self.assertEqual(extract_tags("标题 # 标题"), [])


if __name__ == "__main__":
    unittest.main()
