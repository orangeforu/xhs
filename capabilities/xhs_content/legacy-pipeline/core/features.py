"""内容特征自动提取 — 零 LLM 调用，纯文本分析。

为每篇生成的笔记提取 20+ 结构化特征，贯穿「生成 → 发布 → 数据录入 → 复盘」
全链路，支撑数据驱动的内容优化。
"""

import re

# ── 常量定义（独立维护，避免循环导入） ──

_IMPORTANT_ANCHORS = [
    "绿萝", "香薰", "台灯", "窗帘", "被子", "枕头", "起球", "发黄",
    "抽屉", "衣柜", "阳台", "厨房", "冰箱", "便利贴", "便签",
    "钥匙", "包包", "围巾", "帽子", "鞋子", "袜子", "拖鞋",
    "花盆", "植物", "咖啡", "茶", "水杯",
    "照片", "相框", "日记", "笔记本", "笔", "信封",
]

_IMPORTANT_ACTIONS = [
    "反扣", "盯着", "删掉", "关掉", "放下", "推开", "拿起",
    "拨了拨", "摸了摸", "揉了揉", "擦了擦", "倒了",
]

_COLLECTION_MARKERS = {
    "清单": ["清单", "对比清单", "清单体", "vs", "VS", "❌", "✅"],
    "自检题": ["自检", "测试", "你中了几条", "测一测", "checklist"],
    "避雷指南": ["避雷", "千万别", "不要做", "别再做", "踩雷"],
    "方法步骤": ["方法", "步骤", "怎么做", "如何", "指南", "教程"],
}

_HOOK_TYPE_PATTERNS = [
    ("选择题", [
        r"扣\d", r"扣一", r"二选一", r"选.个",
        r"选[①②③④⑤]", r"[①②③④⑤]或[①②③④⑤]", r"①或②",
        r"还是", r"还是别的", r"A还是B",
    ]),
    ("打卡式", [r"打卡", r"今天开始", r"做到了来", r"试试.{0,5}来"]),
    ("挑衅式", [r"我不信", r"我不相信", r"谁敢", r"有人能"]),
    ("站队型", [r"站队", r"该不该", r"对不对", r"同不同意"]),
    ("故事征集", [
        r"评论区来[，,]", r"评论区说", r"评论区报",
        r"说[一1]个你", r"分享[一1]个", r"我先来[，,:：]",
    ]),
    ("场景追问", [
        r"你有没有过", r"你做过.{1,25}是什么",
        r"你[被是收到].{1,25}[吗呢？?]", r"你当过",
        r"你呢[？?]?", r"后来怎么样了",
    ]),
]

_DEAD_HOOK_PATTERNS = [
    "说说你的故事", "你经历过吗", "你有什么感受", "你中了几条",
    "评论区告诉我", "你学会了吗", "你觉得呢",
    "什么感觉", "什么心情", "你的故事", "聊聊你的",
]

_FIVE_SEC_ACTIONS = [
    "今天", "现在", "立刻", "马上", "下次", "打开", "找到",
    "回复", "删掉", "改成", "发", "拨", "关", "拉黑", "截图", "写下",
]

_STANCE_MARKERS = [
    r"「[^」]{6,30}」",
    r"不是.{2,10}而是.{2,20}",
    r"不应该|不该|不能|不要",
    r"我.{0,3}觉得|我认为|我猜",
    r"其实.{2,15}不是|原来.{2,15}不是",
    r"就是.{2,15}不是|根本.{2,15}就是",
]

# A-I 故事结构检测规则（优先级从高到低）
_STRUCTURE_RULES = [
    ("F", [r"[❌✅✗✔][^❌✅✗✔]{2,30}[❌✅✗✔]", r"vs[. ]", r"VS[. ]"]),
    ("H", [r"他[：:].{2,40}\n", r"我[：:].{2,40}\n", r"她[：:].{2,40}\n"]),
    ("I", [r"投票", r"站队", r"你选", r"A\s*[.、]\s*B"]),
    ("G", [r"以前.*现在", r"过去.*现在", r"我曾经.*现在我", r"双视角"]),
    ("B", ['^[“‘"].{3,40}[”’"]', r"^[''].{3,40}['']"]),
    ("C", [r"三个月前", r"那是.{1,5}年前?", r"回到.{1,5}年前?", r"我记得那是"]),
    ("D", [r"你.{1,30}吗[？?]$", r"难道.{1,20}[？?]", r"谁说.{1,20}[？?]"]),
    ("A", [r"^\*\*[^*]{5,30}\*\*\s*$"]),
]


def _extract_body(content: str) -> str:
    """提取【正文】部分。"""
    m = re.search(r"【正文】\s*\n(.*?)(?=\n【[^】]+】)", content, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


def _extract_section(content: str, section_name: str) -> str:
    """提取指定 section 的内容。"""
    m = re.search(rf"【{section_name}】\s*\n?(.*?)(?=\n(?:#{{1,6}}\s*)?【|$)", content, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


def _count_words(text: str) -> int:
    """统计中文字数（去除标点、空白、英文）。"""
    cleaned = re.sub(r"[\s\n\r]+", "", text)
    return len(cleaned)


def _count_bold(text: str) -> int:
    """统计加粗数量。"""
    return len(re.findall(r"\*\*[^*]+\*\*", text))


def _count_emoji(text: str) -> int:
    """统计正文 emoji 数量。"""
    emoji_re = re.compile(
        r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
        r"\U00002702-\U000027B0\U0001F900-\U0001F9FF\U00002600-\U000026FF"
        r"\U0001F1E0-\U0001F1FF❤✨❓❗✅❌⭐]"
    )
    return len(emoji_re.findall(text))


def _count_pages(body: str) -> int:
    """统计正文页数（--- 分隔符数 + 1）。"""
    return len(re.split(r"\n\s*---+\s*\n", body))


def _detect_story_structure(body: str) -> str:
    """检测故事结构类型 A-I，按优先级规则匹配。"""
    for struct_type, patterns in _STRUCTURE_RULES:
        for pattern in patterns:
            if re.search(pattern, body, re.MULTILINE | re.DOTALL):
                return struct_type
    return "E"  # 纯故事流（默认）


def _detect_stance_point_page(body: str) -> int | None:
    """估算站队点首次出现的页码，无则为 None。"""
    pages = re.split(r"\n\s*---+\s*\n", body)
    for i, page_text in enumerate(pages, 1):
        for marker in _STANCE_MARKERS:
            if re.search(marker, page_text):
                return i
    return None


def _detect_anchoring_items(body: str) -> list[str]:
    """扫描正文中出现的具体物品。"""
    found = []
    for item in _IMPORTANT_ANCHORS:
        if item in body:
            found.append(item)
    return found


def _detect_action_descriptions(body: str) -> bool:
    """检测是否有动作描写。"""
    return any(action in body for action in _IMPORTANT_ACTIONS)


def _detect_collection_elements(body: str) -> list[str]:
    """检测收藏元素类型。"""
    found = []
    for category, markers in _COLLECTION_MARKERS.items():
        if any(m in body for m in markers):
            found.append(category)
    return found


def _detect_hook_type(content: str) -> str | None:
    """识别互动钩子类型。"""
    hook_section = _extract_section(content, "互动钩子")
    if not hook_section:
        return None
    for hook_type, patterns in _HOOK_TYPE_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, hook_section):
                return hook_type
    return "其他"


def _has_five_sec_action(body: str) -> bool:
    """检测结尾是否有 5 秒行动。"""
    last_part = body[-300:]
    return any(kw in last_part for kw in _FIVE_SEC_ACTIONS)


def _has_dead_hook(content: str) -> bool:
    """检测是否使用零回复老套路钩子。"""
    hook_section = _extract_section(content, "互动钩子")
    if not hook_section:
        return False
    return any(kw in hook_section for kw in _DEAD_HOOK_PATTERNS)


def _extract_cover_title(content: str) -> str:
    """从笔记内容中提取封面大字标题。"""
    section = _extract_section(content, "封面页")
    if not section:
        return ""
    # 去除 Markdown 加粗标记后再匹配
    clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", section)
    m = re.search(r"(?:大字标题|标题)[：:]\s*(.+?)(?:\n|$)", clean)
    if m:
        return m.group(1).strip()
    return ""


def _extract_cover_subtitle(content: str) -> str:
    """从笔记内容中提取封面副标题（情绪钩子小字）。"""
    section = _extract_section(content, "封面页")
    if not section:
        return ""
    clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", section)
    m = re.search(r"(?:情绪钩子小字|小字钩子|小字|副标题)[：:]\s*(.+?)(?:\n|$)", clean)
    if m:
        return m.group(1).strip()
    return ""


def _extract_visual_style(content: str) -> str:
    """提取视觉风格标签。"""
    m = re.search(r"【视觉风格】\s*\n?\s*`?([a-z_]+)`?", content)
    if m:
        style = m.group(1).strip().lower()
        return style
    return "warm_grey"


def extract_features(
    content: str,
    design: dict | None = None,
    review: dict | None = None,
    rounds: int = 0,
    self_check: dict | None = None,
) -> dict:
    """从笔记内容中提取 20+ 结构化特征，纯文本分析，零 LLM 调用。

    Args:
        content: 笔记完整 Markdown 文本
        design: 封面设计信息（可选，用于补充提取）
        review: 审核报告 dict（可选）
        rounds: 审核迭代轮数
        self_check: 写手自检结果 dict（可选，来自 emotional_writer）

    Returns:
        结构化特征 dict，所有字段均有默认值
    """
    body = _extract_body(content)
    cover_title = _extract_cover_title(content)
    cover_subtitle = _extract_cover_subtitle(content)
    visual_style = _extract_visual_style(content)
    hook_type = _detect_hook_type(content)
    anchoring_items = _detect_anchoring_items(body) if body else []

    features = {
        # ── 内容特征 ──
        "story_structure": _detect_story_structure(body) if body else "E",
        "stance_point_page": _detect_stance_point_page(body) if body else None,
        "anchoring_items": anchoring_items,
        "anchoring_item_count": len(anchoring_items),
        "has_action_description": _detect_action_descriptions(body) if body else False,
        "collection_elements": _detect_collection_elements(body) if body else [],
        "hook_type": hook_type,
        "has_five_sec_action": _has_five_sec_action(body) if body else False,
        "has_dead_hook": _has_dead_hook(content),
        "word_count": _count_words(body) if body else 0,
        "page_count": _count_pages(body) if body else 0,
        "bold_count": _count_bold(body) if body else 0,
        "emoji_count": _count_emoji(body) if body else 0,

        # ── 封面维度 ──
        "cover_title": cover_title,
        "cover_title_length": len(cover_title),
        "cover_subtitle": cover_subtitle,
        "visual_style": visual_style,

        # ── 效率指标 ──
        "review_rounds": rounds,
        "final_grade": review.get("grade", "B") if review else "B",
        "verdict": review.get("verdict", "unknown") if review else "unknown",
        "issues_count": len(review.get("issues", [])) if review else 0,
        "self_check_issues_count": (
            self_check.get("self_check_issues_count", 0) if self_check else 0
        ),

        # ── 时间维度（发布/录入时补填）──
        "published_day_of_week": None,
        "data_collection_days": None,
    }

    return features


def features_to_yaml(features: dict) -> str:
    """将 features dict 格式化为 YAML 文本块，用于写入 note.md。"""
    lines = ["```yaml"]
    for key, value in features.items():
        if value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                items = ", ".join(repr(v) for v in value)
                lines.append(f"{key}: [{items}]")
        elif isinstance(value, bool):
            lines.append(f"{key}: {str(value).lower()}")
        elif isinstance(value, str):
            lines.append(f"{key}: {value}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("```")
    return "\n".join(lines)
