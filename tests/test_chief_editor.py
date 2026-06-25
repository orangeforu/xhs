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

    def test_b_grade_pass_few_issues_revises(self):
        """B级有issues必须重写，不能及格就发。"""
        review = {"grade": "B", "verdict": "pass", "issues": [{"problem": "x"}]}
        result = self.ce._make_decision({}, None, review, 0)
        self.assertEqual(result["action"], "revise")

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

    def test_dead_loop_3_same_b_grades_triggers_angle_change(self):
        """B-B-B死循环应要求换角度重写，不再强制通过。"""
        review = {"grade": "B", "verdict": "conditional", "issues": [{"problem": "a"}, {"problem": "b"}, {"problem": "c"}]}
        grade_history = ["B", "B", "B"]
        result = self.ce._make_decision({}, None, review, 2, grade_history)
        self.assertEqual(result["action"], "revise")
        self.assertIn("换一个叙事角度", result["feedback"])

    def test_dead_loop_3_b_at_max_rounds_abandons(self):
        """B-B-B死循环在最后一轮应放弃。"""
        review = {"grade": "B", "verdict": "conditional", "issues": [{"problem": "a"}]}
        grade_history = ["B", "B", "B"]
        result = self.ce._make_decision({}, None, review, 4, grade_history)
        self.assertEqual(result["action"], "abandon")

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
        """最大轮数时，B级仍有issues则放弃。"""
        review = {"grade": "B", "verdict": "conditional", "issues": [{"problem": "x"}]}
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
