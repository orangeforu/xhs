"""知识库 + 检索层测试。全部在临时目录进行，不污染真实 knowledge_base/。"""

import time

import core.knowledge_base as kb_mod
import core.knowledge_retrieval as kr_mod
from core.knowledge_base import deprecate, search_records, write_record
from core.knowledge_retrieval import retrieve_patterns_for_brief, retrieve_related_notes


def test_write_and_search_record(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_mod, "KB_DIR", tmp_path)
    p = write_record("pattern", "S级模式：分手后删微信", grade="S", title_formula="问句式", tags=["问句式"])
    assert p.exists()
    recs = search_records(record_type="pattern")
    assert len(recs) == 1
    assert recs[0]["grade"] == "S"
    assert recs[0]["title_formula"] == "问句式"
    assert "问句式" in recs[0]["tags"]


def test_search_by_tags(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_mod, "KB_DIR", tmp_path)
    write_record("pattern", "模式A", tags=["问句式"])
    time.sleep(0.01)
    write_record("pattern", "模式B", tags=["观点冲击式"])
    assert len(search_records(tags=["问句式"])) == 1
    assert len(search_records(tags=["观点冲击式"])) == 1
    assert len(search_records()) == 2


def test_deprecate_excludes_from_active(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_mod, "KB_DIR", tmp_path)
    p = write_record("pattern", "失效模式", tags=["x"])
    assert len(search_records(status="active")) == 1
    assert deprecate(p)
    assert len(search_records(status="active")) == 0
    assert len(search_records(status="deprecated")) == 1
    assert len(search_records(status=None)) == 1  # 不限状态


def test_frontmatter_types_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_mod, "KB_DIR", tmp_path)
    write_record(
        "review",
        "放弃选题",
        body="失败原因正文",
        grade="C",
        rounds=5,
        tags=["问句式", "互联网打工人的深夜"],
        what_failed="连续3轮C级",
    )
    recs = search_records(record_type="review")
    assert recs[0]["grade"] == "C"
    assert recs[0]["rounds"] == 5
    assert recs[0]["what_failed"] == "连续3轮C级"
    assert "失败原因正文" in recs[0]["body"]


def test_invalid_record_type_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_mod, "KB_DIR", tmp_path)
    try:
        write_record("bogus", "x")
    except ValueError:
        return
    raise AssertionError("应拒绝未知记录类型")


def test_retrieve_patterns_for_brief(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_mod, "KB_DIR", tmp_path)
    write_record("pattern", "S级模式：删微信", grade="S", title_formula="问句式",
                 visual_style="crimson", title="分手后该删微信吗", tags=["问句式"])
    ctx = retrieve_patterns_for_brief({"title_formula": "问句式"})
    assert "可复用 pattern" in ctx
    assert "删微信" in ctx
    assert "crimson" in ctx


def test_retrieve_patterns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_mod, "KB_DIR", tmp_path)
    assert retrieve_patterns_for_brief({"title_formula": "问句式"}) == ""


def test_retrieve_related_notes(tmp_path, monkeypatch):
    # 构造一个临时 docs_agent，含一篇 archived 笔记
    note_dir = tmp_path / "archived" / "note_abc"
    note_dir.mkdir(parents=True)
    (note_dir / "note.md").write_text(
        "# 分手后删微信的那天晚上\n\n**最终审核**: A | **审核结论**: pass\n\n正文关于删微信。",
        encoding="utf-8",
    )
    monkeypatch.setattr(kr_mod, "DOCS_AGENT_DIR", tmp_path)
    ctx = retrieve_related_notes("分手 删微信")
    assert "历史相关笔记" in ctx
    assert "删微信" in ctx
    assert "A" in ctx  # grade


def test_retrieve_related_notes_no_match(tmp_path, monkeypatch):
    note_dir = tmp_path / "published" / "note_xyz"
    note_dir.mkdir(parents=True)
    (note_dir / "note.md").write_text("# 完全无关的标题\n\n正文。", encoding="utf-8")
    monkeypatch.setattr(kr_mod, "DOCS_AGENT_DIR", tmp_path)
    assert retrieve_related_notes("分手 删微信") == ""
