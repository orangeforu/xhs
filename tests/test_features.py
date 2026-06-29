"""Unit tests for core/features.py — content feature auto-extraction."""

import pytest
from core.features import (
    extract_features,
    _extract_body,
    _extract_section,
    _extract_cover_title,
    _extract_cover_subtitle,
    _detect_story_structure,
    _detect_stance_point_page,
    _detect_anchoring_items,
    _detect_action_descriptions,
    _detect_collection_elements,
    _detect_hook_type,
    _has_five_sec_action,
    _has_dead_hook,
    _count_words,
    _count_pages,
    _count_bold,
    features_to_yaml,
)


class TestBodyExtraction:
    def test_extract_body_standard(self):
        content = "【正文】\n她把手机放在枕边。\n【金句】"
        assert "手机" in _extract_body(content)

    def test_extract_body_empty(self):
        assert _extract_body("no body here") == ""

    def test_extract_body_with_page_separators(self):
        content = "【正文】\n第一页内容\n---\n第二页内容\n【金句】\n金句文本"
        body = _extract_body(content)
        assert "第一页" in body
        assert "第二页" in body
        assert "金句文本" not in body


class TestSectionExtraction:
    def test_extract_section_hook(self):
        content = "【互动钩子】\n打卡测试\n【话题标签】"
        assert "打卡测试" in _extract_section(content, "互动钩子")

    def test_extract_section_with_hash_prefix(self):
        content = "【互动钩子】\n打卡测试\n\n# 【话题标签】\n#tag1 #tag2"
        section = _extract_section(content, "互动钩子")
        assert "打卡测试" in section
        assert "话题标签" not in section

    def test_extract_section_missing(self):
        assert _extract_section("no section", "互动钩子") == ""


class TestCoverExtraction:
    def test_extract_cover_title_standard(self):
        content = "【封面页】\n大字标题：秒回的人可能不爱你\n情绪钩子小字：测试"
        assert _extract_cover_title(content) == "秒回的人可能不爱你"

    def test_extract_cover_title_with_bold(self):
        content = "【封面页】\n**大字标题**：停止精神内耗\n小字：测试"
        assert _extract_cover_title(content) == "停止精神内耗"

    def test_extract_cover_title_missing_section(self):
        assert _extract_cover_title("no cover") == ""

    def test_extract_cover_subtitle(self):
        content = "【封面页】\n标题：测试\n情绪钩子小字：你等过一个人的回复吗？"
        assert "你等过" in _extract_cover_subtitle(content)

    def test_extract_cover_subtitle_bold(self):
        content = "【封面页】\n标题：测试\n**情绪钩子小字**：两年内耗患者亲测"
        assert "两年内耗" in _extract_cover_subtitle(content)


class TestStoryStructure:
    def test_structure_f_list_body(self):
        body = "她看着手机\n❌ 以前总是秒回\n✅ 现在学会等一等"
        assert _detect_story_structure(body) == "F"

    def test_structure_h_chat(self):
        body = "他：你今天怎么了？\n我：没事\n她：真的没事吗"
        assert _detect_story_structure(body) == "H"

    def test_structure_i_vote(self):
        body = "所以你觉得她该不该分手？投票：\nA. 该分手\nB. 再看看"
        assert _detect_story_structure(body) == "I"

    def test_structure_g_contrast(self):
        body = "以前我觉得爱是秒回\n现在才知道爱是即使很忙也会说一声"
        assert _detect_story_structure(body) == "G"

    def test_structure_b_dialogue(self):
        body = '"你真的想好了吗？"\n她看着他的眼睛，没有回答。'
        assert _detect_story_structure(body) == "B"

    def test_structure_c_flashback(self):
        body = "那是三年前的事了。\n她记得那天下午..."
        assert _detect_story_structure(body) == "C"

    def test_structure_a_bold_opening(self):
        body = "**真正的爱不是占有，是成全**\n\n她终于明白了这句话。"
        assert _detect_story_structure(body) == "A"

    def test_structure_e_default(self):
        body = "她打开冰箱，拿出那瓶放了很久的咖啡。"
        assert _detect_story_structure(body) == "E"

    def test_structure_priority(self):
        """F (清单体) should be detected before E."""
        body = "以前我觉得爱重要\n现在知道钱也重要\n❌ 只谈感情\n✅ 也谈现实"
        assert _detect_story_structure(body) == "F"


class TestStancePoint:
    def test_stance_point_page_1(self):
        body = "「不是不在乎你，而是我太累了」\n---\n第二页内容"
        assert _detect_stance_point_page(body) == 1

    def test_stance_point_page_2(self):
        body = "第一页开头\n---\n她不应该这么做。\n---\n第三页"
        assert _detect_stance_point_page(body) == 2

    def test_stance_point_none(self):
        body = "她只是安静地坐着，什么都没说。"
        assert _detect_stance_point_page(body) is None

    def test_stance_point_not_behind(self):
        body = "我觉得她做得对。\n不应该总是迁就别人。"
        assert _detect_stance_point_page(body) == 1


class TestAnchoringItems:
    def test_detect_multiple_items(self):
        body = "她看着那盆绿萝，又转头望向台灯。"
        items = _detect_anchoring_items(body)
        assert "绿萝" in items
        assert "台灯" in items

    def test_detect_no_items(self):
        assert _detect_anchoring_items("她很难过。") == []

    def test_detect_actions(self):
        assert _detect_action_descriptions("她摸了摸屏幕。") is True

    def test_detect_no_actions(self):
        assert _detect_action_descriptions("她很难过。") is False


class TestCollectionElements:
    def test_list_and_self_check(self):
        body = "❌ 无效关心\n✅ 有效关心\n\n你中了几条？"
        elements = _detect_collection_elements(body)
        assert "清单" in elements
        assert "自检题" in elements

    def test_method_steps(self):
        body = "怎么做呢？第一步：打开对话框。这个方法很简单。"
        assert "方法步骤" in _detect_collection_elements(body)

    def test_no_collections(self):
        assert _detect_collection_elements("纯故事叙述。") == []


class TestHookType:
    def test_hook_choice(self):
        content = "【互动钩子】\n做过真爱的扣1，没过期的扣2"
        assert _detect_hook_type(content) == "选择题"

    def test_hook_checkin(self):
        content = "【互动钩子】\n今天开始试试，做到了来打卡"
        assert _detect_hook_type(content) == "打卡式"

    def test_hook_challenge(self):
        content = "【互动钩子】\n我不信有人从来没委屈过自己"
        assert _detect_hook_type(content) == "挑衅式"

    def test_hook_stance(self):
        content = "【互动钩子】\n你觉得她该不该分手？评论区站队"
        assert _detect_hook_type(content) == "站队型"

    def test_hook_story_collection(self):
        content = "【互动钩子】\n评论区说一个你不敢当面说的话"
        assert _detect_hook_type(content) == "故事征集"

    def test_hook_scene_question(self):
        content = "【互动钩子】\n你有没有过删了又写写了又删的时刻？"
        assert _detect_hook_type(content) == "场景追问"

    def test_hook_scene_question_ni_bei(self):
        content = "【互动钩子】\n你被哪个瞬间伤到过？用一句话说出来。"
        assert _detect_hook_type(content) == "场景追问"

    def test_hook_choice_by_hai_shi(self):
        content = "【互动钩子】\n是原谅，还是离开？评论区告诉我"
        assert _detect_hook_type(content) == "选择题"

    def test_hook_other(self):
        content = "【互动钩子】\n一段无法分类的钩子文本"
        assert _detect_hook_type(content) == "其他"

    def test_hook_missing_section(self):
        assert _detect_hook_type("没有钩子") is None


class TestFiveSecAction:
    def test_has_action(self):
        body = "她看着屏幕。" * 10 + "今天就把那个对话框删了。"
        assert _has_five_sec_action(body) is True

    def test_no_action(self):
        body = "她只是安静地坐着。" * 10
        assert _has_five_sec_action(body) is False


class TestDeadHook:
    def test_dead_hook_detected(self):
        content = "【互动钩子】\n说说你的故事，评论区告诉我吧"
        assert _has_dead_hook(content) is True

    def test_dead_hook_not_detected(self):
        content = "【互动钩子】\n做过真爱的扣1"
        assert _has_dead_hook(content) is False


class TestCounting:
    def test_count_pages(self):
        assert _count_pages("页1\n---\n页2\n---\n页3") == 3

    def test_count_single_page(self):
        assert _count_pages("只有一页") == 1

    def test_count_bold(self):
        assert _count_bold("**加粗1** 普通 **加粗2**") == 2


class TestExtractFeatures:
    def test_full_extraction(self):
        content = """
【封面页】
大字标题：秒回的人不爱你
情绪钩子小字：你等过回复吗

【正文】
她把手机放在枕边。那盆绿萝的叶子黄了三片。
---
她想起他说的话：不是不在乎，而是太累了。

【金句】
**秒回的人，不爱你**
【互动钩子】
做过秒回的扣1，没做过的扣2
【视觉风格】
warm_grey
"""
        review = {"grade": "B", "verdict": "pass", "issues": [{"a": 1}, {"b": 2}]}
        f = extract_features(content, review=review, rounds=2)

        assert f["cover_title"] == "秒回的人不爱你"
        assert f["cover_title_length"] == 7
        assert f["visual_style"] == "warm_grey"
        assert f["story_structure"] == "E"
        assert f["page_count"] == 2
        assert f["anchoring_items"] == ["绿萝"]
        assert f["hook_type"] == "选择题"
        assert f["has_dead_hook"] is False
        assert f["review_rounds"] == 2
        assert f["final_grade"] == "B"
        assert f["issues_count"] == 2
        assert f["published_day_of_week"] is None
        assert f["data_collection_days"] is None

    def test_extraction_with_self_check(self):
        content = "【正文】\n纯故事\n【金句】\n金句"
        sc = {"self_check_issues_count": 4}
        f = extract_features(content, self_check=sc)
        assert f["self_check_issues_count"] == 4

    def test_extraction_empty_content(self):
        f = extract_features("")
        assert f["word_count"] == 0
        assert f["page_count"] == 0
        assert f["story_structure"] == "E"


class TestFeaturesToYaml:
    def test_yaml_output(self):
        f = {
            "story_structure": "A",
            "anchoring_items": ["绿萝", "台灯"],
            "anchoring_item_count": 2,
            "has_action_description": True,
            "cover_title_length": 8,
            "published_day_of_week": None,
        }
        yaml_str = features_to_yaml(f)
        assert "story_structure: A" in yaml_str
        assert "anchoring_items: ['绿萝', '台灯']" in yaml_str
        assert "true" in yaml_str
        assert "null" in yaml_str
        assert "```yaml" in yaml_str
