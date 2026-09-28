"""知识库 - 跨会话沉淀可复用的定性模式。

5 类记录（对标 xiaohongshu-ops-skill 的 knowledge-base 设计）：

- ``pattern``：已验证有效的结构模板（S/A 级笔记的 标题句式+封面+钩子+正文结构）
- ``review``：失败复盘（放弃的选题：失败原因 / 为什么 / 下次怎么改）
- ``topic``：选题洞察（来自评论挖掘 / 竞品分析）
- ``account``：账号体检结论（定位 / 人设 / 内容支柱 / 红线）
- ``action``：执行动作记录（发布 / 采数 / 复盘动作）

与 :class:`core.agents.memory.AgentMemory` 的区别：AgentMemory 存每个 Agent
最近 10 条 numeric 模式（按 topic 键、进程内）；知识库存的是**人类可读、
可检索、可复用**的结构化模板，跨 Agent、跨会话共享，按时间排序、可废弃。

记录格式：markdown 文件 + YAML-ish frontmatter（无 PyYAML 依赖，自写极简解析）。
文件名：``{date}_{slug}.md``，date 前缀便于按时间排序，slug 便于全文检索。
"""

import re
import threading
from datetime import datetime
from pathlib import Path

from core.config import PROJECT_ROOT, get_logger

logger = get_logger(__name__)

KB_DIR = PROJECT_ROOT / "knowledge_base"
RECORD_TYPES = ("pattern", "review", "topic", "account", "action")
_LOCK = threading.Lock()


def _ensure_dirs() -> None:
    for t in RECORD_TYPES:
        (KB_DIR / t).mkdir(parents=True, exist_ok=True)


def _slugify(text: str, maxlen: int = 40) -> str:
    text = re.sub(r"[^\w一-龥]+", "_", text).strip("_")
    return text[:maxlen] or "record"


def _escape(value) -> str:
    """把值序列化为 frontmatter 单行字符串。"""
    if isinstance(value, list):
        return "[" + ", ".join(_escape(v) for v in value) + "]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value).replace("\n", " ").strip()
    # 含 frontmatter 特殊字符时用双引号包裹
    if not s or any(c in s for c in ":[]#\""):
        return f'"{s}"'
    return s


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """解析 ``---`` 包裹的 frontmatter，返回 (meta_dict, body)。无依赖。"""
    meta: dict = {}
    if not text.startswith("---"):
        return meta, text
    end = text.find("\n---", 3)
    if end == -1:
        return meta, text
    header = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    for line in header.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            meta[key] = [x.strip().strip('"') for x in inner.split(",") if x.strip()] if inner else []
        elif val.startswith('"') and val.endswith('"'):
            meta[key] = val[1:-1]
        elif val in ("true", "false"):
            meta[key] = val == "true"
        elif val.lstrip("-").isdigit():
            meta[key] = int(val)
        else:
            meta[key] = val
    return meta, body


def write_record(record_type: str, summary: str, body: str = "", **fields) -> Path:
    """写一条知识库记录，返回文件路径。

    Args:
        record_type: ``RECORD_TYPES`` 之一。
        summary: 一句话核心结论（必填）。
        body: 自由文本正文（证据 / 细节，可为空）。
        **fields: frontmatter 字段，如 ``grade, tags, title_formula,
            visual_style, source_note, status``。``status`` 默认 ``active``。

    线程安全（内部锁），写入失败只告警不抛（知识库是辅助层，不阻断主流程）。
    """
    if record_type not in RECORD_TYPES:
        raise ValueError(f"未知记录类型 {record_type}，可选: {RECORD_TYPES}")
    _ensure_dirs()
    ts = datetime.now()
    meta = {
        "id": ts.strftime("%Y%m%d%H%M%S") + f"_{record_type}",
        "type": record_type,
        "status": fields.pop("status", "active"),
        "created_at": ts.isoformat(timespec="seconds"),
        "summary": summary,
    }
    meta.update(fields)
    lines = ["---"]
    for k, v in meta.items():
        lines.append(f"{k}: {_escape(v)}")
    lines.append("---")
    content = "\n".join(lines) + "\n\n" + (body or summary) + "\n"
    fname = f"{ts.strftime('%Y-%m-%d')}_{_slugify(summary)}.md"
    path = KB_DIR / record_type / fname
    try:
        with _LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    except Exception as e:  # 知识库写入失败不阻断主流程
        logger.warning("知识库写入失败 [%s]: %s", record_type, e)
        return path
    logger.info("知识库写入 [%s] %s: %s", record_type, path.name, summary[:50])
    return path


def search_records(
    record_type: str | None = None,
    tags: list[str] | None = None,
    status: str | None = "active",
    days: int | None = None,
    limit: int = 10,
) -> list[dict]:
    """检索知识库记录，按创建时间倒序返回。

    Args:
        record_type: 限定类型；None = 全部。
        tags: 任一 tag 命中即返回（记录的 ``tags`` 字段为 list）。
        status: 只返回该状态（active/deprecated/experimental）；None = 不限。
        days: 只返回最近 N 天；None = 不限。
        limit: 最多返回条数。
    """
    _ensure_dirs()
    types = [record_type] if record_type else list(RECORD_TYPES)
    records: list[dict] = []
    for t in types:
        d = KB_DIR / t
        if not d.exists():
            continue
        for p in d.glob("*.md"):
            try:
                text = p.read_text(encoding="utf-8")
            except Exception:
                continue
            meta, body = _parse_frontmatter(text)
            if not meta:
                continue
            if status and meta.get("status") != status:
                continue
            if tags:
                rec_tags = meta.get("tags", [])
                if not isinstance(rec_tags, list):
                    rec_tags = [rec_tags]
                if not any(tg in rec_tags for tg in tags):
                    continue
            if days:
                try:
                    ct = datetime.fromisoformat(str(meta.get("created_at", "")))
                    if (datetime.now() - ct).days > days:
                        continue
                except Exception:
                    pass
            meta["body"] = body.strip()
            meta["path"] = str(p)
            meta["record_type"] = t
            records.append(meta)
    records.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
    return records[:limit]


def deprecate(record_path: str | Path) -> bool:
    """把记录标记为 ``deprecated``（不删除，保留可复盘）。"""
    path = Path(record_path)
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^status:\s*\S+", "status: deprecated", text, count=1, flags=re.MULTILINE)
    path.write_text(text, encoding="utf-8")
    logger.info("知识库记录标记为 deprecated: %s", path.name)
    return True
