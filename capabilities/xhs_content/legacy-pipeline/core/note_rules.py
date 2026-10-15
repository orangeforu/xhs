"""笔记领域规则 — 标签卫生 + 废笔记健康检查。

从 core.utils 拆出，因为这些是【领域业务规则】（D-01/D-02 标签策略、防 LLM
思考链泄漏三道防线），不是通用工具。core.utils 保留 re-export 兼容旧调用点。

设计原则：凡 prompt 写了但 LLM 不稳定遵守的规则，一律用确定性代码兜底，
不依赖 LLM 自觉。详见 CLAUDE.md「涨粉优化约定」与「废笔记健康检查」。
"""

import re

# ── 话题标签确定性清洗（D-01）──
# 营销号高频泛词黑名单：搜索价值≈0 且易触发降权（用户已认可）
GENERIC_TAG_BLACKLIST = {
    "情感", "恋爱", "两性关系", "爱情", "生活", "日常",
    "心理", "女生必看", "治愈", "思考", "反思",
    "情感共鸣", "深夜感慨", "自我提升", "恋爱脑", "情侣相处",
    "关系经营", "女性成长", "清醒",
}
REQUIRED_TAG = "不懂就问有问必答"
MAX_TAGS = 5
MIN_TAGS = 3


def sanitize_tags(raw_tag_line: str, keywords: list[str] | None = None) -> str:
    """确定性清洗话题标签：去泛词、补必带词、截断到 3-5 个。

    不依赖 LLM 自觉遵守 prompt 规则——凡 prompt 写了但 LLM 不稳定遵守的，
    一律用确定性代码兜底。返回空格分隔的 "#标签1 #标签2 ..." 字符串。
    """
    tags = re.findall(r"#([^#\s]+)", raw_tag_line)
    seen: set[str] = set()
    deduped: list[str] = []
    for t in tags:
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            deduped.append(t)

    # 过滤泛词黑名单
    cleaned = [t for t in deduped if t not in GENERIC_TAG_BLACKLIST]

    # 必带词兜底
    if not any(REQUIRED_TAG in t for t in cleaned):
        cleaned.insert(0, REQUIRED_TAG)

    # 截断到上限
    cleaned = cleaned[:MAX_TAGS]

    # 不足下限时用选题 keywords 补精准长尾词
    if len(cleaned) < MIN_TAGS and keywords:
        for kw in keywords:
            kw = kw.strip()
            if kw and kw not in seen and kw not in GENERIC_TAG_BLACKLIST:
                cleaned.append(kw)
                seen.add(kw)
                if len(cleaned) >= MAX_TAGS:
                    break
        cleaned = cleaned[:MAX_TAGS]

    return " ".join(f"#{t}" for t in cleaned)


def sanitize_tags_in_content(content: str, keywords: list[str] | None = None) -> str:
    """对 note.md 中【话题标签】段做确定性清洗，返回清洗后的整篇内容。

    匹配 "【话题标签】\\n<标签行>"，把标签行替换为清洗结果。
    """
    m = re.search(r"(【话题标签】\s*\n)([^\n【]+)", content)
    if not m:
        return content
    cleaned = sanitize_tags(m.group(2), keywords)
    return content[: m.start(2)] + cleaned + content[m.end(2):]


def check_tags_compliance(content: str) -> list[str]:
    """检查 note.md 标签是否合规，返回问题列表（空 = 合规）。

    用于 D-02 主编硬门禁：标签数量越界或含泛词时强制重写，
    不依赖 LLM 审核自觉（实测 LLM 会无视"3-5个"规则给通过）。
    """
    m = re.search(r"【话题标签】\s*\n([^\n【]+)", content)
    if not m:
        # 无标签段不报：真实笔记由 prompt 强制输出标签段，缺标签通常意味着
        # content 并非合法笔记（如异常/mock 产物）。本检查只针对"已有标签段"的质量。
        return []
    tags = re.findall(r"#([^#\s]+)", m.group(1))
    issues = []
    if len(tags) > MAX_TAGS:
        issues.append(f"标签过多（{len(tags)}个，要求 3-5 个）")
    if len(tags) < MIN_TAGS:
        issues.append(f"标签过少（{len(tags)}个，要求 3-5 个）")
    generic = [t for t in tags if t in GENERIC_TAG_BLACKLIST]
    if generic:
        issues.append(f"含降权泛标签：{', '.join('#' + t for t in generic)}")
    return issues


# ── 废笔记健康检查（防 LLM 思考链泄漏进发布流程）──
# 模型（如 glm-5.2）有时把英文推理过程混进 content 返回，_extract_content 不剥离，
# 导致整篇笔记变成思考链。本检查在三道防线复用：主编门禁 / 发布前置校验 / UI 标记。
THINKING_LEAK_PATTERNS = [
    r"\bLet me\b",
    r"\bLet's\b",
    r"\bI need to\b",
    r"\bI'll\b",
    r"\bI should\b",
    r"\bHmm\b",
    r"\bThe user wants\b",
    r"\bwait\b.*\bLet me\b",
]
THINKING_LEAK_RE = re.compile("|".join(THINKING_LEAK_PATTERNS), re.IGNORECASE)


def check_note_health(content: str) -> list[str]:
    """检查笔记是否为废笔记（LLM 思考链泄漏/无标签段/英文占比异常），返回问题列表（空=健康）。

    防止 glm-5.2 等模型把思考过程混进 content 后一路过关被发布。三道防线复用：
    - 生成时：ChiefEditor 门禁拦截，废草稿 revise（与 check_tags_compliance 并列）
    - 发布时：auto_publish / 🚀tab 前置校验，废笔记拒绝发布
    - UI：🚀tab 标记问题笔记

    判定规则（命中任一即视为废笔记）：
    1. 思考链特征词命中 ≥2 处（Let me / I need to / Hmm 等）
    2. 正文英文词 > 20 且 > 中文字数 × 0.5（小红书情感笔记以中文为主）

    注：标签段缺失不在此检查范围（由 check_tags_compliance 专门负责），
    避免误伤"写手漏标签但内容正常"的笔记。
    """
    if not content:
        return ["内容为空"]

    issues: list[str] = []

    # 1. 思考链泄漏特征词
    leaks = THINKING_LEAK_RE.findall(content)
    if len(leaks) >= 2:
        issues.append(f"疑似 LLM 思考链泄漏（命中 {len(leaks)} 处英文推理特征词）")

    # 2. 英文占比异常
    chinese = len(re.findall(r"[一-鿿]", content))
    english_words = len(re.findall(r"[a-zA-Z]+", content))
    if english_words > 20 and english_words > chinese * 0.5:
        issues.append(f"英文占比异常（英文词 {english_words} vs 中文字 {chinese}）")

    return issues
