import unittest

from pipeline import _sanitize_prompt


class TestSanitizePrompt(unittest.TestCase):
    """测试封面 prompt 安全净化函数。"""

    def test_empty_prompt(self):
        self.assertEqual(_sanitize_prompt(""), "")
        self.assertIsNone(_sanitize_prompt(None))

    def test_warm_prompt_unchanged(self):
        prompt = "A cozy room with soft warm lighting, cozy atmosphere, gentle pastel tones, emotional warmth"
        result = _sanitize_prompt(prompt)
        self.assertIn("soft warm lighting", result)
        self.assertIn("cozy atmosphere", result)

    def test_cold_keywords_replaced(self):
        prompt = "A dimly lit dark room with cold-toned lighting"
        result = _sanitize_prompt(prompt)
        self.assertNotIn("dimly lit", result.lower())
        self.assertNotIn("dark room", result.lower())
        self.assertNotIn("cold-toned", result.lower())
        self.assertIn("softly lit", result)
        self.assertIn("warm cozy room", result)
        self.assertIn("warm-toned", result)

    def test_safeguards_appended(self):
        prompt = "A beautiful garden"
        result = _sanitize_prompt(prompt)
        self.assertIn("soft warm lighting", result)
        self.assertIn("cozy atmosphere", result)
        self.assertIn("gentle pastel tones", result)
        self.assertIn("emotional warmth", result)

    def test_no_duplicate_safeguards(self):
        prompt = "A scene with soft warm lighting and cozy atmosphere"
        result = _sanitize_prompt(prompt)
        # 不应重复追加已存在的 safeguard
        self.assertEqual(result.count("soft warm lighting"), 1)
        self.assertEqual(result.count("cozy atmosphere"), 1)

    def test_multiple_cold_keywords(self):
        prompt = "A gloomy abandoned hollow void scene"
        result = _sanitize_prompt(prompt)
        self.assertNotIn("gloomy", result.lower())
        self.assertNotIn("abandoned", result.lower())
        self.assertNotIn("hollow", result.lower())
        self.assertNotIn("void", result.lower())
        self.assertIn("softly glowing", result)

    def test_case_insensitive_replacement(self):
        prompt = "A DIMLY LIT room with DARK ROOM atmosphere"
        result = _sanitize_prompt(prompt)
        self.assertNotIn("dimly lit", result.lower())
        self.assertNotIn("dark room", result.lower())

    def test_pitch_black_replaced(self):
        prompt = "A pitch black background"
        result = _sanitize_prompt(prompt)
        self.assertNotIn("pitch black", result.lower())
        self.assertIn("soft twilight", result)

    def test_grayscale_replaced(self):
        prompt = "A grayscale monochrome gray image"
        result = _sanitize_prompt(prompt)
        self.assertNotIn("grayscale", result.lower())
        self.assertNotIn("monochrome gray", result.lower())

    def test_silhouette_replaced(self):
        prompt = "A silhouette of a person"
        result = _sanitize_prompt(prompt)
        self.assertNotIn("silhouette", result.lower())
        self.assertIn("soft profile", result)

    def test_eerie_creepy_replaced(self):
        prompt = "An eerie creepy scene"
        result = _sanitize_prompt(prompt)
        self.assertNotIn("eerie", result.lower())
        self.assertNotIn("creepy", result.lower())
        self.assertIn("peaceful", result)
        self.assertIn("warm", result)


if __name__ == "__main__":
    unittest.main()
