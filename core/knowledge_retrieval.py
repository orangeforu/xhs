"""知识库检索 - 为创作流程注入可复用模式和历史相关笔记。

两层检索（均纯 Python，无向量依赖--语料小，向量是过度工程）：

1. :func:`retrieve_patterns_for_brief`：从 ``knowledge_base/pattern/`` 检索匹配
   brief 的已验证模式（S/A 级笔记的结构），注入 TopicStrategist。
2. :func:`retrieve_related_notes`：从 ``docs_agent/archived|published/`` 的 note.md
   按关键词命中检索历史相关笔记，避免选题 / 角度重复，可注入 ContentEditor。
"""

import re

from core.config import PROJECT_ROOT, get_logger
from core.knowledge_base import search_records

logger = get_logger(__name__)

DOCS_AGENT_DIR = PROJECT_ROOT / "docs_agent"


def retrieve_patterns_for_brief(brief: dict, limit: int = 3) -> str:
    """检索与 brief 匹配的可复用 pattern 记录，返回可注入 prompt 的文本。

    匹配策略：按 brief 的 ``title_formula`` / ``series`` / ``pillar`` 作为 tags
    检索；命中不足时回退到全部 active pattern。无记录返回空串。
    """
    try:
        tags = [str(brief[k]) for k in ("title_formula", "series", "pillar") if brief.get(k)]
        records = search_records(record_type="pattern", tags=tags or None, status="active", limit=limit)
        if not records:
            records = search_records(record_type="pattern", status="active", limit=limit)
    except Exception as e:
        logger.debug("pattern 检索失败（不影响主流程）: %s", e)
        return ""
    if not records:
        return ""
    lines = ["【可复用 pattern - 借鉴结构，不要照抄内容】"]
    for r in records:
        parts = [f"- 「{r.get('summary', '')}」"]
        for f in ("title_formula", "visual_style", "grade", "series"):
            if r.get(f):
                parts.append(f"{f}={r[f]}")
        if r.get("title"):
            parts.append(f"标题示例={r['title']}")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def _extract_title(note_md_text: str) -> str:
    # 复用 core.publish_helpers 的单一真源实现
    from core.publish_helpers import extract_title

    return extract_title(note_md_text)


def _extract_grade(note_md_text: str) -> str:
    m = re.search(r"\*\*最终审核\*\*:\s*([SABC])", note_md_text)
    return m.group(1) if m else ""


def retrieve_related_notes(query: str, top_k: int = 3) -> str:
    """从已发布 / 归档笔记中按关键词命中检索相关历史笔记。

    用于避免选题 / 角度重复。返回 ``[参考N - 标题 (grade)]`` 格式文本；无命中返回空串。
    """
    keywords = [w for w in re.split(r"[\s，。、？！,.\?\!]+", query or "") if len(w) >= 2]
    if not keywords:
        return ""
    scored: list[tuple[int, str, str, str]] = []
    for sub in ("archived", "published"):
        d = DOCS_AGENT_DIR / sub
        if not d.exists():
            continue
        for note_dir in d.iterdir():
            if not note_dir.is_dir():
                continue
            md = note_dir / "note.md"
            if not md.exists():
                continue
            try:
                text = md.read_text(encoding="utf-8")
            except Exception:
                continue
            hits = sum(text.count(kw) for kw in keywords)
            if hits == 0:
                continue
            grade = _extract_grade(text)
            scored.append((hits, _extract_title(text), grade, sub))
    if not scored:
        return ""
    scored.sort(key=lambda x: x[0], reverse=True)
    lines = ["【历史相关笔记 - 避免角度重复，可借鉴差异化点】"]
    for i, (_hits, title, grade, sub) in enumerate(scored[:top_k], 1):
        g = f" [{grade}级]" if grade else ""
        lines.append(f"[参考{i} - {title}{g} ({sub})]")
    return "\n".join(lines)
