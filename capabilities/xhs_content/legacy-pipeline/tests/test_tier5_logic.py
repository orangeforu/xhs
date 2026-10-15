"""Tier 5 纯逻辑测试：粉丝快照 / 评论洞察 / 账号诊断。无网络，全 mock。"""

import core.fans_history as fh_mod
import scripts.account_diagnostic as diag_mod
import scripts.comment_insight as ci_mod
from core.fans_history import _extract_fans, load_fans_history, snapshot_fans

# ── 粉丝快照 ──

def test_extract_fans_various_keys():
    assert _extract_fans({"data": {"fans": 1234}}) == 1234
    assert _extract_fans({"data": {"fansCount": 99}}) == 99
    assert _extract_fans({"data": {"followers": 5}}) == 5
    assert _extract_fans({"data": {}}) is None
    assert _extract_fans(None) is None
    assert _extract_fans({"data": {"fans": "abc"}}) is None  # 非数字


class _FakeUserApi:
    def __init__(self, res):
        self._res = res

    def get_user_me(self):
        return (True, "ok", self._res)


def test_snapshot_fans_appends_history(tmp_path, monkeypatch):
    f = tmp_path / "fans_history.json"
    monkeypatch.setattr(fh_mod, "FANS_HISTORY_FILE", f)
    api = _FakeUserApi({"data": {"fans": 100, "user_id": "u1"}})
    assert snapshot_fans(api) == 100
    assert snapshot_fans(api) == 100
    hist = load_fans_history()
    assert len(hist) == 2
    assert hist[0]["fans"] == 100
    assert hist[1]["fans"] == 100


def test_snapshot_fans_failure_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(fh_mod, "FANS_HISTORY_FILE", tmp_path / "fans.json")

    class BadApi:
        def get_user_me(self):
            return (False, "auth expired", None)

    assert snapshot_fans(BadApi()) is None


# ── 评论洞察 ──

def test_comment_text_extraction():
    assert ci_mod._comment_text({"content": "好评", "like_count": 5}) == ("好评", 5)
    assert ci_mod._comment_text({"text": "x", "likes": "3"}) == ("x", 3)
    assert ci_mod._comment_text({"content": "", "like_count": 0}) == ("", 0)


def test_parse_topics_valid():
    raw = '{"topics": [{"topic": "t1", "angle": "a1", "controversy_point": "c1", "confidence": 0.8}, {"topic": "t2"}]}'
    topics = ci_mod._parse_topics(raw)
    assert len(topics) == 2
    assert topics[0]["topic"] == "t1"


def test_parse_topics_invalid():
    assert ci_mod._parse_topics("not json") == []
    assert ci_mod._parse_topics('{"topics": []}') == []


def test_extract_topics_from_comments_with_mock():
    comments = [
        {"text": "我也遇到过，气死", "likes": 50},
        {"text": "我觉得不对，应该反过来", "likes": 30},
        {"text": "扣1", "likes": 10},
    ]
    canned = '{"topics": [{"topic": "分手后该不该要回礼物", "angle": "争议", "controversy_point": "该要 vs 不该要", "confidence": 0.9}]}'
    topics = ci_mod.extract_topics_from_comments("原标题", comments, llm_call=lambda p: canned)
    assert len(topics) == 1
    assert "礼物" in topics[0]["topic"]


def test_extract_topics_empty_comments():
    assert ci_mod.extract_topics_from_comments("t", [], llm_call=lambda p: "{}") == []
    assert ci_mod.extract_topics_from_comments("t", [{"text": "", "likes": 0}], llm_call=lambda p: "{}") == []


# ── 账号诊断 ──

def test_build_snapshot_structure():
    perf = {
        "notes": [
            {"topic": "A", "grade": "S", "likes": 1000, "comments": 50, "title_formula": "问句式", "updated_at": "2026-07-01T10:00:00"},
            {"topic": "B", "grade": "C", "likes": 10, "comments": 0, "title_formula": "观点冲击式", "updated_at": "2026-07-29T10:00:00"},
        ],
        "summary": {"avg_likes": 505, "grade_distribution": {"S": 1, "C": 1}},
    }
    snap = diag_mod.build_snapshot(perf, fans=2000)
    assert snap["fans"] == 2000
    assert snap["total_notes"] == 2
    assert len(snap["recent_notes"]) == 2
    # 倒序：B 在前（updated_at 更晚）
    assert snap["recent_notes"][0]["title"] == "B"
    assert snap["grade_distribution"]["S"] == 1


def test_diagnose_account_with_mock():
    snap = {"fans": 100, "total_notes": 3, "avg_likes": 50, "grade_distribution": {"A": 2, "C": 1}, "recent_notes": []}
    canned = """
    {"dimensions": {"定位清晰度": {"score": 4, "reason": "稳"}, "内容结构力": {"score": 3, "reason": "ok"},
    "互动转化力": {"score": 2, "reason": "评论少"}, "账号辨识度": {"score": 4, "reason": "人设强"},
    "增长可持续性": {"score": 3, "reason": "一般"}},
    "biggest_strength": "人设统一", "biggest_weakness": "评论少", "next_actions": ["a", "b", "c"]}
    """
    diag = diag_mod.diagnose_account(snap, llm_call=lambda p: canned)
    assert diag["biggest_strength"] == "人设统一"
    assert len(diag["next_actions"]) == 3
    assert diag["dimensions"]["互动转化力"]["score"] == 2


def test_diagnose_account_bad_json():
    assert diag_mod.diagnose_account({}, llm_call=lambda p: "not json") == {}
