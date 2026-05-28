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
        review = {"grade": "B", "verdict": "pass", "issues": [{"problem": "x"}]}
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

    def test_dead_loop_3_same_grades_forces_publish(self):
        review = {"grade": "B", "verdict": "conditional", "issues": [{"problem": "a"}, {"problem": "b"}, {"problem": "c"}]}
        grade_history = ["B", "B", "B"]
        result = self.ce._make_decision({}, None, review, 2, grade_history)
        self.assertEqual(result["action"], "publish")
        self.assertIn("死循环", result["reason"])

    def test_dead_loop_only_triggers_for_s_a_b(self):
        review = {"grade": "C", "verdict": "fail", "issues": [{"problem": "x"}]}
        grade_history = ["C", "C", "C"]
        result = self.ce._make_decision({}, None, review, 2, grade_history)
        self.assertEqual(result["action"], "revise")

    def test_dead_loop_alternating_grades_no_trigger(self):
        review = {"grade": "B", "verdict": "conditional", "issues": [{"problem": "a"}, {"problem": "b"}, {"problem": "c"}]}
        grade_history = ["A", "B", "A"]
        result = self.ce._make_decision({}, None, review, 2, grade_history)
        self.assertEqual(result["action"], "revise")

    def test_max_rounds_publishes_s_a_b(self):
        review = {"grade": "B", "verdict": "conditional", "issues": []}
        result = self.ce._make_decision({}, None, review, 4)
        self.assertEqual(result["action"], "publish")

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
