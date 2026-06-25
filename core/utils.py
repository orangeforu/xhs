"""公共工具函数 — 消除各模块间的重复代码。"""

import json
import re

from core.config import PROMPTS_DIR


def extract_json_from_llm(raw: str) -> dict | None:
    """从 LLM 输出中稳健提取第一个 JSON 对象。

    通过括号深度匹配处理嵌套对象，不会因 ``re.search(r'\\{[^{}]*\\}')`` 而
    在 ``{"a": [{"b": 1}]}`` 这类嵌套结构上失败。
    """
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            if in_string:
                escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def load_prompt(name: str) -> str:
    """从 prompts/ 目录加载 prompt 文件。"""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt 文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def clean_md(text: str) -> str:
    """去掉 Markdown 加粗、斜体、反引号等标记。"""
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)  # **加粗**
    t = re.sub(r"\*(.+?)\*", r"\1", t)      # *斜体*
    t = re.sub(r"~~(.+?)~~", r"\1", t)      # ~~删除线~~
    t = re.sub(r"`(.+?)`", r"\1", t)        # `代码`
    t = re.sub(r"^[\s*_`]+|[\s*_`]+$", "", t)
    return t.strip()


def extract_visual_style(content: str) -> str:
    """从 AI 生成的 Markdown 中提取视觉风格标签。"""
    m = re.search(
        r'(?:视觉风格|风格|style)\s*】?\s*[:：]?\s*\n?\s*`?([a-z_]+)`?',
        content,
        re.IGNORECASE,
    )
    if m:
        style = m.group(1).strip().lower()
        from core.image_generator import PALETTE
        if style in PALETTE:
            return style
    return "warm_grey"


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


FORMULA_INSTRUCTIONS = {
    "问句式": """
【标题公式特化指令 — 问句式】
你的标题必须是一个让人忍不住想回答的问题。核心技巧：
- 问题本身要击中具体场景（不是"爱情是什么"这种空泛问题）
- 标题里隐含一个"反常识"的钩子，让人想点进去看答案
- 正文不要直接回答标题问题，而是用故事让读者自己得出答案
- 结尾的互动钩子用轻钩子：二选一/数字互动/@指令，不要"说说你的故事"
""",
    "概念解读式": """
【标题公式特化指令 — 概念解读式】
你要拆解一个情感概念，让它变得具体可感。核心技巧：
- 不要下定义，用"3个日常场景"来呈现这个概念
- 每个场景都是一个微型故事，有动作、有对话、有反转
- 读者收藏的原因不是"学到了定义"，而是"这就是我啊"
- 封面要突出"X个表现""原来是这样"等收藏驱动力
- 正文中自然嵌入对话对比/场景清单作为收藏元素
""",
    "观点冲击式": """
【标题公式特化指令 — 观点冲击式】
你要提出一个反常识的观点，但不直接说服读者。核心技巧：
- 观点要足够尖锐，让读者第一反应是"不可能吧"
- 用故事层层剥开，让读者在最后恍然大悟"原来真的是这样"
- 不要站队，不要贴标签，只呈现现象
- 讨论度来自"我不同意"和"我也是"两种声音的碰撞
- 第2页的金句可以就是这个观点的最精炼版本
""",
    "方法承诺式": """
【标题公式特化指令 — 方法承诺式】
你要给出一个具体可操作的解决方案。核心技巧：
- 方法必须具体到"下一句话该说什么"
- 用"以前vs现在"的对比展示方法的效果
- 不要列123条，每条都要包裹在故事里
- 收藏驱动来自"这个我能直接用"——确保有可收藏的结构化元素
- 第2页直接给出方法的核心洞察
""",
}


def write_note_file(
    output_file: str,
    brief: dict,
    draft: dict,
    review: dict,
    cover_paths: dict,
    inner_paths: list,
    preset_comments: dict,
    rounds: int = 1,
    title_eval: list | None = None,
    commit_hash: str = "",
) -> None:
    """将笔记及相关产物写入 Markdown 文件（兼容旧格式，确保 app.py 正则解析正常）。"""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# {brief['topic']}\n\n")
        f.write(draft["content"])
        f.write("\n\n---\n\n")
        f.write("## 审核结果\n\n")
        f.write(f"**迭代轮数**: {rounds} | **最终审核**: {review.get('grade', 'B')} | **审核结论**: {review.get('verdict', 'unknown')}")
        if commit_hash:
            f.write(f" | **代码版本**: {commit_hash}")
        f.write("\n\n")
        if review.get("overall_comment"):
            f.write(f"**审核评语**: {review['overall_comment']}\n\n")
        f.write(format_review(review))
        # 标题评分
        if title_eval:
            f.write("\n\n## 标题评分\n\n")
            for i, t in enumerate(title_eval):
                marker = "🏆 推荐" if i == 0 else ""
                f.write(f"- **{t['title']}** — {t['score']}分（{t['level']}级）{marker}\n")
                if t.get("reasons"):
                    for r in t["reasons"][:2]:
                        f.write(f"  - {r}\n")
            if title_eval[0].get("improved"):
                f.write(f"\n**AI 改进建议**: {title_eval[0]['improved']}\n")
        if cover_paths:
            f.write("\n\n## 封面文件\n\n")
            for name, path in cover_paths.items():
                f.write(f"- `{name}`: {path}\n")
        if inner_paths:
            f.write("\n## 内页文件\n\n")
            for path in inner_paths:
                f.write(f"- {path}\n")
        if preset_comments.get("comments"):
            f.write("\n## 预设评论（发布后使用）\n\n")
            # 优先使用分类评论
            classified = preset_comments.get("comments_classified", [])
            if classified:
                type_labels = {
                    "discussion_starter": "引导讨论",
                    "controversy": "制造站队",
                    "resonance": "情感共鸣",
                    "supplement": "补充故事",
                    "tag_friend": "@好友",
                }
                for c in classified:
                    if isinstance(c, dict):
                        label = type_labels.get(c.get("type", ""), c.get("type", ""))
                        f.write(f"- [{label}] {c['text']}\n")
                    else:
                        f.write(f"- {c}\n")
            else:
                for c in preset_comments["comments"]:
                    f.write(f"- {c}\n")
            # 回复模板
            reply_templates = preset_comments.get("reply_templates", [])
            if reply_templates:
                f.write("\n### 博主回复模板\n\n")
                for r in reply_templates:
                    f.write(f"- {r}\n")


def format_review(review: dict) -> str:
    """将结构化审核报告格式化为 Markdown。"""
    if not review:
        return "审核信息缺失"
    parts = []
    parts.append(f"**等级**: {review.get('grade', 'B')}")
    parts.append(f"**结论**: {review.get('verdict', 'unknown')}")

    issues = review.get("issues", [])
    if issues:
        parts.append("\n### 问题\n")
        for i in issues:
            parts.append(f"- **{i.get('location', '')}**: {i.get('problem', '')}")
            if i.get("suggestion"):
                parts.append(f"  - 建议: {i['suggestion']}")

    suggestions = review.get("suggestions", [])
    if suggestions:
        parts.append("\n### 建议\n")
        for s in suggestions:
            parts.append(f"- **{s.get('location', '')}**: {s.get('idea', '')}")

    strengths = review.get("strengths", [])
    if strengths:
        parts.append("\n### 优点\n")
        for s in strengths:
            parts.append(f"- {s}")

    return "\n".join(parts)
