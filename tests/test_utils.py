import unittest

from core.utils import clean_md, load_prompt, sanitize_tags, sanitize_tags_in_content


class TestCleanMd(unittest.TestCase):
    """测试 Markdown 清理。"""

    def test_bold_removal(self):
        self.assertEqual(clean_md("**hello**"), "hello")

    def test_italic_removal(self):
        self.assertEqual(clean_md("*hello*"), "hello")

    def test_strikethrough_removal(self):
        self.assertEqual(clean_md("~~hello~~"), "hello")

    def test_inline_code_removal(self):
        self.assertEqual(clean_md("`hello`"), "hello")

    def test_none_returns_empty(self):
        self.assertEqual(clean_md(None), "")

    def test_empty_string(self):
        self.assertEqual(clean_md(""), "")

    def test_mixed_markdown(self):
        self.assertEqual(clean_md("**bold** and *italic*"), "bold and italic")


class TestLoadPrompt(unittest.TestCase):
    """测试 prompt 加载。"""

    def test_load_existing_prompt(self):
        content = load_prompt("agent_writer")
        self.assertIn("情感博主", content)

    def test_load_nonexistent_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_prompt("nonexistent_file_xyz")


class TestSanitizeTags(unittest.TestCase):
    """测试话题标签确定性清洗（D-01）。"""

    def test_filters_generic_and_truncates(self):
        """真实场景：15个含大量泛词的标签 → 去泛词 + 截断到 ≤5。"""
        raw = ("#不懂就问有问必答 #情感 #恋爱 #两性关系 #吵架 #低头 #认输 "
               "#清醒 #女性成长 #自我提升 #恋爱脑 #情感共鸣 #深夜感慨 #情侣相处 #关系经营")
        result = sanitize_tags(raw)
        tags = result.split()
        self.assertLessEqual(len(tags), 5)
        # 泛词应全部被过滤
        for t in tags:
            name = t.lstrip("#")
            self.assertNotIn(name, {"情感", "恋爱", "两性关系", "清醒", "女性成长", "自我提升"})
        # 必带词保留
        self.assertTrue(any("不懂就问" in t for t in tags))

    def test_adds_required_tag_when_missing(self):
        result = sanitize_tags("#情绪反刍 #自我觉察")
        self.assertIn("#不懂就问有问必答", result)

    def test_no_duplicate_required_tag(self):
        result = sanitize_tags("#不懂就问有问必答 #情绪反刍")
        self.assertEqual(result.count("不懂就问"), 1)

    def test_fills_with_keywords_when_too_few(self):
        result = sanitize_tags("#不懂就问有问必答", keywords=["情绪反刍", "心理后台", "内耗"])
        self.assertGreaterEqual(len(result.split()), 3)

    def test_dedup(self):
        result = sanitize_tags("#情绪反刍 #情绪反刍 #不懂就问有问必答")
        self.assertEqual(result.count("情绪反刍"), 1)

    def test_in_content_replaces_tag_section(self):
        content = "【正文】\n一些内容\n\n【话题标签】\n#情感 #恋爱 #情绪反刍\n\n【视觉风格】\nwarm_grey"
        new = sanitize_tags_in_content(content)
        self.assertNotIn("#情感", new)
        self.assertIn("#不懂就问有问必答", new)
        # 其他 section 不受影响
        self.assertIn("warm_grey", new)
        self.assertIn("【正文】", new)


if __name__ == "__main__":
    unittest.main()
