import unittest

from core.agents.chief_editor import ChiefEditor


class TestMakeDecision(unittest.TestCase):
    """测试主编的6条决策路径。"""

    def setUp(self):
        self.ce = ChiefEditor.__new__(ChiefEditor)

    def test_no_review_triggers_revise(self):
        result = self.ce._make_decision({}, None, None, 0)
        self.assertEqual(result["action"], "revise")

    def test_s_grade_pass_publishes(self):
        review = {"grade": "S", "verdict": "pass", "issues": []}
        result = self.ce._make_decision({}, None, review, 0)
        self.assertEqual(result["action"], "publish")

    def test_a_grade_pass_publishes(self):
        review = {"grade": "A", "verdict": "pass", "issues": []}
        result = self.ce._make_decision({}, None, review, 0)
        self.assertEqual(result["action"], "publish")

    def test_b_grade_pass_few_issues_publishes(self):
        """B级≤2个issues可接受通过（实现已放宽，避免过度修补失去个性）。"""
        review = {"grade": "B", "verdict": "pass", "issues": [{"problem": "x"}]}
        result = self.ce._make_decision({}, None, review, 0)
        self.assertEqual(result["action"], "publish")

    def test_b_grade_pass_zero_issues_publishes(self):
        """B级无issues可接受。"""
        review = {"grade": "B", "verdict": "pass", "issues": []}
        result = self.ce._make_decision({}, None, review, 0)
        self.assertEqual(result["action"], "publish")

    def test_b_grade_too_many_issues_revises(self):
        review = {"grade": "B", "verdict": "pass", "issues": [{"problem": "a"}, {"problem": "b"}, {"problem": "c"}]}
        result = self.ce._make_decision({}, None, review, 0)
        self.assertEqual(result["action"], "revise")

    def test_c_grade_revises(self):
        review = {"grade": "C", "verdict": "fail", "issues": [{"problem": "x"}]}
        result = self.ce._make_decision({}, None, review, 0)
        self.assertEqual(result["action"], "revise")

    def test_dead_loop_3_same_b_grades_publishes(self):
        """B-B-B死循环直接通过（实现已放宽：连续3轮同级强制通过，防死循环）。"""
        review = {"grade": "B", "verdict": "conditional", "issues": [{"problem": "a"}, {"problem": "b"}, {"problem": "c"}]}
        grade_history = ["B", "B", "B"]
        result = self.ce._make_decision({}, None, review, 2, grade_history)
        self.assertEqual(result["action"], "publish")

    def test_dead_loop_3_b_at_max_rounds_publishes(self):
        """B-B-B死循环即使到最大轮数也直接通过（防死循环优先于max_rounds放弃）。"""
        review = {"grade": "B", "verdict": "conditional", "issues": [{"problem": "a"}]}
        grade_history = ["B", "B", "B"]
        result = self.ce._make_decision({}, None, review, 4, grade_history)
        self.assertEqual(result["action"], "publish")

    def test_dead_loop_c_c_c_revises(self):
        """C-C-C不触发死循环保护，正常重写。"""
        review = {"grade": "C", "verdict": "fail", "issues": [{"problem": "x"}]}
        grade_history = ["C", "C", "C"]
        result = self.ce._make_decision({}, None, review, 2, grade_history)
        self.assertEqual(result["action"], "revise")

    def test_dead_loop_alternating_grades_no_trigger(self):
        review = {"grade": "B", "verdict": "conditional", "issues": [{"problem": "a"}, {"problem": "b"}, {"problem": "c"}]}
        grade_history = ["A", "B", "A"]
        result = self.ce._make_decision({}, None, review, 2, grade_history)
        self.assertEqual(result["action"], "revise")

    def test_max_rounds_publishes_s_a_b_no_issues(self):
        """最大轮数时，B级无issues可接受，有issues则放弃。"""
        review = {"grade": "B", "verdict": "conditional", "issues": []}
        result = self.ce._make_decision({}, None, review, 4)
        self.assertEqual(result["action"], "publish")

    def test_max_rounds_b_with_issues_abandons(self):
        """最大轮数时，B级仍有>2个issues则放弃（≤2个会通过）。"""
        review = {"grade": "B", "verdict": "conditional", "issues": [{"problem": "a"}, {"problem": "b"}, {"problem": "c"}]}
        result = self.ce._make_decision({}, None, review, 4)
        self.assertEqual(result["action"], "abandon")

    def test_a_conditional_no_issues_publishes(self):
        """A级+conditional+无issues可通过。"""
        review = {"grade": "A", "verdict": "conditional", "issues": []}
        result = self.ce._make_decision({}, None, review, 0)
        self.assertEqual(result["action"], "publish")

    def test_a_conditional_with_issues_revises(self):
        """A级+conditional+有issues需重写。"""
        review = {"grade": "A", "verdict": "conditional", "issues": [{"problem": "x"}]}
        result = self.ce._make_decision({}, None, review, 0)
        self.assertEqual(result["action"], "revise")

    def test_max_rounds_abandons_c(self):
        review = {"grade": "C", "verdict": "fail", "issues": [{"problem": "x"}]}
        result = self.ce._make_decision({}, None, review, 4)
        self.assertEqual(result["action"], "abandon")

    def test_revise_includes_feedback(self):
        review = {
            "grade": "C",
            "verdict": "fail",
            "issues": [{"location": "第2页", "problem": "情绪断层", "suggestion": "加细节"}],
            "suggestions": [{"location": "结尾", "idea": "留白"}],
            "overall_comment": "需要改进",
        }
        result = self.ce._make_decision({}, None, review, 0)
        self.assertEqual(result["action"], "revise")
        self.assertIn("情绪断层", result["feedback"])


class TestTagGate(unittest.TestCase):
    """测试 D-02 标签硬门禁。"""

    def setUp(self):
        self.ce = ChiefEditor.__new__(ChiefEditor)

    def _draft(self, tag_line):
        return {"content": f"【正文】\n故事\n\n【话题标签】\n{tag_line}\n\n【视觉风格】\nwarm_grey"}

    def test_too_many_tags_blocks_s_grade(self):
        """标签过多时，即使 S 级 pass 也强制重写。"""
        tags = " ".join(f"#标签{i}" for i in range(8)) + " #不懂就问有问必答"
        review = {"grade": "S", "verdict": "pass", "issues": []}
        result = self.ce._make_decision(self._draft(tags), None, review, 0)
        self.assertEqual(result["action"], "revise")

    def test_generic_tags_block_publish(self):
        """含降权泛词时强制重写。"""
        review = {"grade": "A", "verdict": "pass", "issues": []}
        result = self.ce._make_decision(self._draft("#不懂就问有问必答 #情感 #恋爱"), None, review, 0)
        self.assertEqual(result["action"], "revise")

    def test_compliant_tags_allow_publish(self):
        """合规标签不影响正常发布。"""
        review = {"grade": "A", "verdict": "pass", "issues": []}
        result = self.ce._make_decision(self._draft("#不懂就问有问必答 #情绪反刍 #自我觉察"), None, review, 0)
        self.assertEqual(result["action"], "publish")


class TestBuildFeedback(unittest.TestCase):
    """测试反馈构建。"""

    def setUp(self):
        self.ce = ChiefEditor.__new__(ChiefEditor)

    def test_empty_review(self):
        fb = self.ce._build_feedback({})
        self.assertIn("修改原则", fb)

    def test_with_issues_and_suggestions(self):
        review = {
            "issues": [{"location": "第1页", "problem": "开场太慢", "suggestion": "直接进故事"}],
            "suggestions": [{"location": "结尾", "idea": "加互动钩子"}],
            "overall_comment": "整体不错",
        }
        fb = self.ce._build_feedback(review)
        self.assertIn("开场太慢", fb)
        self.assertIn("直接进故事", fb)
        self.assertIn("加互动钩子", fb)
        self.assertIn("整体不错", fb)


if __name__ == "__main__":
    unittest.main()
