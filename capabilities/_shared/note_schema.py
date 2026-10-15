"""笔记数据的统一解析 schema。

把分散在 ``competitor_analysis.py`` / ``fetch_performance.py`` 里对 spider_xhs
``get_note_info`` 响应的解析逻辑收口到一个 :class:`NoteRecord`，避免每加一个
采数脚本（评论洞察 / 首页流分析 / 爆款复刻）就重写一遍 ad-hoc 解析。

响应结构（``get_note_info`` 返回的 ``detail``）::

    detail["data"]["items"][0]["note_card"] = {
        "title": str,
        "interact_info": {"liked_count", "collected_count", "comment_count", "share_count"},
        "tag_list": [{"name": str}, ...],
    }

``note_id`` / ``url`` 不在响应里（来自搜索结果或目录名），由调用方传入。
"""

from dataclasses import dataclass, field


def _to_int(value) -> int:
    """API 互动数可能是字符串，稳健转 int。

    非纯数字串（含"万"等中文单位、空串）返回 0，与历史行为
    ``int(x) if str(x).isdigit() else 0`` 一致。
    """
    if isinstance(value, bool):  # bool 是 int 子类，先排除
        return 0
    if isinstance(value, int):
        return value
    s = str(value)
    return int(s) if s.isdigit() else 0


def _get_note_card(detail: dict) -> dict:
    """从 get_note_info 响应安全取出 note_card（缺失/异常返回 {}）。"""
    data = detail.get("data", {})
    if not isinstance(data, dict):
        return {}
    items = data.get("items", [])
    if not items or not isinstance(items[0], dict):
        return {}
    card = items[0].get("note_card", {})
    return card if isinstance(card, dict) else {}


@dataclass
class NoteRecord:
    """一篇笔记的标准化记录（来自 spider_xhs get_note_info 响应）。"""

    note_id: str = ""
    url: str = ""
    title: str = ""
    likes: int = 0
    collects: int = 0
    comments: int = 0
    shares: int = 0
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_api_detail(cls, detail: dict, note_id: str = "", url: str = "") -> "NoteRecord":
        """从 get_note_info 响应解析笔记字段。

        响应缺失对应字段时返回空字段（不抛异常），与历史行为一致。
        """
        card = _get_note_card(detail)
        interact = card.get("interact_info", {})
        if not isinstance(interact, dict):
            interact = {}
        tag_list = card.get("tag_list", [])
        tags = [t.get("name", "") for t in tag_list if isinstance(t, dict) and t.get("name")]
        return cls(
            note_id=note_id,
            url=url,
            title=card.get("title", "") or "",
            likes=_to_int(interact.get("liked_count", 0)),
            collects=_to_int(interact.get("collected_count", 0)),
            comments=_to_int(interact.get("comment_count", 0)),
            shares=_to_int(interact.get("share_count", 0)),
            tags=tags,
        )

    def to_dict(self) -> dict:
        """转 dict（用于序列化/写 performance.json）。"""
        return {
            "note_id": self.note_id,
            "url": self.url,
            "title": self.title,
            "likes": self.likes,
            "collects": self.collects,
            "comments": self.comments,
            "shares": self.shares,
            "tags": self.tags,
        }
