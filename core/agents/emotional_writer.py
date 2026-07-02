import re

from core.agents.base import BaseAgent, MessageBus, Message, MessageType
from core.config import get_logger
from core.utils import load_prompt, FORMULA_INSTRUCTIONS, sanitize_tags_in_content

logger = get_logger(__name__)


# ── 内容守卫：禁词检查 ──
_FORBIDDEN_PATTERNS = [
    # 说明书语气
    (r'第[一二三四五六七八九十1-9]点|首先[，,]|其次[，,]|总结起来|总的来说', "说明书语气"),
    # 分析腔
    (r'她才明白|后来才懂|其实那时候|现在我懂了|其实真正的[爱喜欢]', "分析腔"),
    # 给结论
    (r'所以[，,]这说明|原来[，,].*是[，,]|真正的[爱喜欢]不是', "给结论"),
    # 开场客套
    (r'^(嗨姐妹|今天聊|好的宝贝|大家好|Hello)', "开场客套"),
    # 心理描写代替动作
    (r'她内心五味杂陈|她觉得很难受|她感到无比|她心想[，,]这', "心理描写代替动作"),
    # 结尾总结
    (r'我想说[，,]|我想告诉你|最后我想说|希望.*能.*', "结尾总结式"),
    # 排比说教
    (r'真正爱你的人不会|真正在乎你的人|真正.*的人.*不会', "排比说教"),
    # 伪对话引导
    (r'你看[，,]|你想啊|说白了|其实你想想', "伪对话引导"),
    # 分析式表达（仅限叙事者分析腔，不含角色对话中的站队点）
    (r'(她才明白|后来才懂|现在才懂|终于知道).*不是.*而是|那不是.{0,5}而是.{0,5}是', "分析式表达"),
    # 结尾下定义式总结（普适化结论）
    (r'(或许|也许|大概)所有人都这样[。.]|不是因为.*只是因为[。.]|有些人.*只(是|不过)是', "结尾下定义式总结"),
    # 内部标签外泄（AI 把 prompt 指令当正文输出）
    (r'【收藏】|【清单】|【对比】|【自检】|【步骤】|【方法】', "内部标签外泄（把prompt指令写进了正文）"),
    # 老套互动钩子（数据证明：76%零互动，此类钩子回复率=0）
    (r'说说你的故事|你经历过吗|你有什么感受|你中了几条|评论区告诉我|你学会了吗|你觉得呢|聊聊你的|你的故事|有什么感觉|什么心情|A还是B[？?]', "零回复钩子（已数据证实无效）"),
]

_COMPILED_FORBIDDEN = [(re.compile(pat, re.IGNORECASE), desc) for pat, desc in _FORBIDDEN_PATTERNS]


def _check_content_guard(content: str) -> list[str]:
    """检查内容是否命中禁词，返回问题列表。空列表 = 通过。"""
    issues = []
    # 只检查正文部分（【正文】到下一个【xxx】之间）
    body_match = re.search(r'【正文】\s*\n(.*?)(?=【|$)', content, re.DOTALL)
    body = body_match.group(1) if body_match else content

    for pattern, desc in _COMPILED_FORBIDDEN:
        matches = pattern.findall(body)
        if matches:
            sample = matches[0] if isinstance(matches[0], str) else str(matches[0])
            issues.append(f"{desc}: 「{sample[:30]}」")

    # 检查加粗数量（不超过6处，放宽限制避免过度修补）
    bold_count = len(re.findall(r'\*\*[^*]+\*\*', body))
    if bold_count > 6:
        issues.append(f"加粗过多: {bold_count}处（限制5-6处）")

    # 检查 emoji 数量（正文不超过2个）
    emoji_re = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U00002764\U00002728\U00001F447]')
    emoji_count = len(emoji_re.findall(body))
    if emoji_count > 3:
        issues.append(f"正文emoji过多: {emoji_count}个（限制2-3个）")

    return issues



# ── 写手自检清单（提交前自查） ──
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


def _check_data_driven(content: str) -> list[str]:
    """写手提交前自检：数据驱动的检查清单。返回问题列表，空=通过。"""
    import re as _re
    issues = []
    body_match = _re.search(r"【正文】\s*\n(.*?)(?=【|$)", content, _re.DOTALL)
    body = body_match.group(1) if body_match else content

    # 1. 前500字内是否有高辨识度物品
    first_part = body[:500]
    has_anchor = any(kw in first_part for kw in _IMPORTANT_ANCHORS)
    if not has_anchor:
        issues.append("缺少具体物品: 前3页未出现有辨识度的物品")

    # 2. 是否有动作描写代替心理
    has_action = any(kw in body for kw in _IMPORTANT_ACTIONS)
    if not has_action:
        issues.append("缺少动作描写: 全文多用抽象情绪词而非具体动作推进")

    # 3. 是否有收藏元素
    has_collectible = any(kw in body for kw in ["清单", "方法", "步骤", "自检", "测试", "避雷"])
    if not has_collectible:
        issues.append("缺少收藏元素: 没有可收藏的结构化元素")

    # 4. 互动钩子是否能在1秒内回答（数据：76%零互动，根本原因在钩子）
    hook_match = _re.search(r"【互动钩子】\s*\n(.*?)(?=【|$)", content, _re.DOTALL)
    if hook_match:
        hook = hook_match.group(1)
        # 硬拒绝：已被数据证明无效的老套路钩子
        _DEAD_HOOKS = [
            "说说你的故事", "你经历过吗", "你有什么感受", "你中了几条",
            "评论区告诉我", "你学会了吗", "你觉得呢",
            "什么感觉", "什么心情", "你的故事", "聊聊你的",
        ]
        if any(kw in hook for kw in _DEAD_HOOKS):
            issues.append("互动钩子无效: 使用了零回复老套路。必须改用选择题(扣1扣2)、打卡式(做到了来打卡)、挑衅式(我不信有人…)")
        if len(hook) > 40:
            issues.append("互动钩子过长: >40字，读者不会读完。像弹幕一样短，≤20字最佳。")
    else:
        issues.append("缺少互动钩子")

    # 5. 结尾是否有5秒行动（宽松版：有关键词即可通过）
    last_part = body[-300:]
    has_actionable = any(kw in last_part for kw in ["今天", "现在", "立刻", "马上", "下次", "打开", "找到", "回复", "删掉", "改成", "发", "拨", "关", "拉黑", "截图", "写下"])
    if not has_actionable:
        issues.append("缺少5秒行动: 结尾没有给读者立刻能做的一件事")

    # 6. 是否有站队点（debatable stance）— 29篇0评论的根因
    # 站队点必须出现在正文前半部分（前60%），是一个可被反驳的具体判断
    body_half = body[:int(len(body) * 0.6)]
    stance_markers = [
        r'「[^」]{6,30}」',           # 引用的观点句
        r'不是.{2,10}而是.{2,20}',    # "不是X，而是Y"辩论结构
        r'不应该|不该|不能|不要',       # 否定式判断
        r'我.{0,3}觉得|我认为|我猜',   # 个人判断
        r'其实.{2,15}不是|原来.{2,15}不是',  # 反常识揭露
        r'就是.{2,15}不是|根本.{2,15}就是',  # 强化判断
    ]
    has_stance = any(_re.search(m, body_half) for m in stance_markers)
    if not has_stance:
        issues.append("缺少站队点: 正文无争议性观点（29篇0评论的根因）。必须在第3页前植入一个可被反驳的判断，如「不是X，而是Y」或人物直述观点")

    # 移除"收藏元素带数字"和"标题长度"检查 — 自检过严导致内容被过度修补失去个性
    # 这两项改由审核官事后检查，不在写手提交前强制修补

    return issues


def get_data_driven_results(content: str) -> dict:
    """暴露写手自检的结构化结果，供特征提取使用。"""
    issues = _check_data_driven(content)
    return {
        "self_check_issues": issues,
        "self_check_issues_count": len(issues),
        "has_anchor": not any("缺少具体物品" in i for i in issues),
        "has_action": not any("缺少动作描写" in i for i in issues),
        "has_collection": not any("缺少收藏元素" in i for i in issues),
        "has_stance": not any("缺少站队点" in i for i in issues),
        "has_five_sec": not any("缺少5秒行动" in i for i in issues),
    }


def _score_title_ctr(title: str) -> int:
    """基于历史数据给标题打CTR预测分（0-100）。"""
    score = 50
    import re as _re
    # 具体数字（一个动作/3个/5步）
    if _re.search(r'[0-9]+|[一二三四五六七八九十]', title):
        score += 15
    # 问号（问题比陈述高20% CTR）
    if '？' in title or '?' in title:
        score += 10
    # "你"字（读者相关性）
    if '你' in title:
        score += 8
    # 方法承诺词
    if any(kw in title for kw in ['动作', '方法', '步骤', '清单', '指南', '测试', '自检']):
        score += 10
    # 痛点词
    if any(kw in title for kw in ['焦虑', '崩溃', '累', '痛', '毁掉', '毁掉', '失去', '分手']):
        score += 7
    # 反常识/悬念词
    if any(kw in title for kw in ['不是', '原来', '其实', '竟然', '居然', '没想到']):
        score += 12
    # emoji（适量加分）
    emoji_count = len(_re.findall(r'[\U0001F600-\U0001F64F]', title))
    if 1 <= emoji_count <= 2:
        score += 5
    elif emoji_count > 2:
        score -= 10
    # 长度惩罚（过长降CTR，小红书限制20字）
    if len(title) > 20:
        score -= 30  # 强制惩罚，超过平台限制会被截断
    elif len(title) < 10:
        score -= 5
    return score


def _optimize_title(content: str) -> str:
    """基于CTR评分优化标题选择。"""
    import re as _re
    title_match = _re.search(r"【标题候选】\s*\n(.*?)(?=【|$)", content, _re.DOTALL)
    if not title_match:
        return content
    titles_block = title_match.group(1)
    # 提取每行标题（跳过空行和分隔符）
    lines = [l.strip() for l in titles_block.split('\n') if l.strip() and not l.strip().startswith('---')]
    if len(lines) < 2:
        return content
    # 评分
    scored = []
    for line in lines:
        # 去掉可能的前缀（如"1. "、"①"）
        clean = _re.sub(r'^[\d]+[.、\s]+', '', line)
        clean = _re.sub(r'^[①②③④⑤][\s.、]*', '', clean)
        score = _score_title_ctr(clean)
        scored.append((score, line, clean))
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_line, best_title = scored[0]
    # 如果最佳标题不在第一位，替换
    first_line = lines[0]
    if best_line != first_line and best_score > _score_title_ctr(first_line) + 5:
        # 把最佳标题放到第一位
        new_lines = [best_line] + [l for l in lines if l != best_line]
        new_block = '\n'.join(new_lines)
        content = content[:title_match.start(1)] + new_block + content[title_match.end(1):]
        logger.info("标题CTR优化: '%s' (分%d) 替代 '%s' (分%d)",
                    best_title[:30], best_score, first_line[:30], _score_title_ctr(first_line))
    return content


class EmotionalWriter(BaseAgent):
    """情感写手 Agent — 负责创作和修改笔记正文。"""

    def __init__(self, bus: MessageBus):
        prompt = load_prompt("agent_writer")
        super().__init__("emotional_writer", prompt, bus)

    def write(self, brief: dict, round_num: int = 0, feedback: str = "") -> dict:
        """创作或重写笔记。带内容守卫：禁词命中时自动重试一次。"""
        feedback = feedback or ""
        user_prompt = self._build_write_prompt(brief, feedback)
        content = self.think(user_prompt, temperature=0.8, max_tokens=2800)

        # 写手自检：数据驱动检查清单（提交前自查）
        data_issues = _check_data_driven(content)
        if data_issues:
            logger.warning("写手自检发现 %d 个问题，自动修补: %s", len(data_issues), data_issues[:3])
            self_fix_feedback = (feedback or "") + "\n\n【系统自检发现以下问题，请在不改变故事核心的前提下修补】\n" + "\n".join(f"- {i}" for i in data_issues)
            self_fix_prompt = self._build_write_prompt(brief, self_fix_feedback)
            content = self.think(self_fix_prompt, temperature=0.5, max_tokens=2800)

        # 内容守卫：检查禁词（仅第一轮，重写轮由审核官反馈驱动）
        guard_issues = _check_content_guard(content)
        if guard_issues and round_num == 0:
            logger.warning("内容守卫命中 %d 个问题，自动重试: %s", len(guard_issues), guard_issues[:3])
            retry_feedback = (feedback or "") + "\n\n【系统自动检测到以下问题，请务必避免】\n" + "\n".join(f"- {i}" for i in guard_issues)
            retry_prompt = self._build_write_prompt(brief, retry_feedback)
            content = self.think(retry_prompt, temperature=0.6, max_tokens=2800)
            guard_issues = _check_content_guard(content)
            if guard_issues:
                logger.warning("重试后仍有 %d 个守卫问题（交由审核官处理）: %s", len(guard_issues), guard_issues[:3])

        # 标题CTR优化：基于历史数据选择最佳标题
        content = _optimize_title(content)

        # 标签确定性兜底（D-01）：LLM 常无视"3-5个精准标签"规则，用代码强制清洗
        content = sanitize_tags_in_content(content, brief.get("keywords"))

        result = {
            "brief": brief,
            "content": content,
            "round_num": round_num,
            "self_check": get_data_driven_results(content),
        }

        # 广播 draft 到总线
        self.send(to_agent=None, msg_type=MessageType.DRAFT, content=result, round_num=round_num)
        logger.info("写手完成第 %d 轮创作，字数约 %d", round_num, len(content))
        return result

    def _build_write_prompt(self, brief: dict, feedback: str) -> str:
        formula = brief.get("title_formula", "问句式")
        formula_instructions = FORMULA_INSTRUCTIONS.get(formula, "")

        # 从记忆中获取数据驱动的建议
        data_hint = self._get_data_recommendations(brief)
        story_hint = ""
        if brief.get("story_prototype"):
            story_hint += f"\n**故事原型**：{brief['story_prototype']}"
        if brief.get("controversy_anchor"):
            story_hint += f"\n**争议锚点**：{brief['controversy_anchor']}"
        if brief.get("series"):
            story_hint += (
                f"\n**所属系列**：《{brief['series']}》（你的固定栏目，追更感=涨粉关键）。"
                f"在【互动钩子】之后，必须加一句系列引导，例如"
                f"「这是《{brief['series']}》系列，关注我看下一篇 👇」。"
            )

        # 热点内容特殊指导
        trending_hint = ""
        if brief.get("is_trending_content"):
            trending_keyword = brief.get("trending_keyword", "")
            story_angle_hint = brief.get("story_angle_hint", "")

            trending_hint = f"""

**热点内容创作指南**：
这是一个热点内容，热点关键词是「{trending_keyword}」。

**热点+情感的融合要求**：
1. 故事背景必须包含热点元素，让用户一看就知道和当前热点相关
2. 但核心必须是情感冲突，热点只是场景。比如「{story_angle_hint}」
3. 标题必须包含热点关键词「{trending_keyword}」，利用热点的搜索流量
4. 封面也要体现热点元素，但要保持温暖调性（soft warm lighting, cozy atmosphere）
5. 故事要具体、有画面感，不要写成新闻稿或热点评论
6. 热点是"钩子"，情感是"留人"的东西。用户因为热点点进来，因为情感共鸣而停留、点赞、收藏

**热点内容标题示例**（参考这个风格）：
- 「世界杯」期间老公天天看球，我突然想离婚了
- 看完「奥运会」夺冠，我给异地恋的男友发了分手
- 「考研」上岸那天，我和陪了我3年的女朋友说再见
"""

        prompt = f"""请创作一篇小红书图文笔记。

**选题**：{brief["topic"]}
**目标互动**：{brief.get("target_interaction", "点赞+收藏")}
**标题公式**：{formula}
{story_hint}
{data_hint}
{trending_hint}

{formula_instructions}

**核心要求（铁律，违反任何一条内容直接作废）**：
1. 根据故事本身选择最合适的结构：A(金句前置)/B(对话开场)/C(倒叙冲击)/D(反问留白)/E(纯故事流)/F(清单体)/G(双视角对比)/**H(聊天对比型-高互动)**/**I(投票站队型-争议型)**。收藏型选题优先H，争议型优先I。
2. **最扎心的一句话必须单独成页**，像一张可截图的海报。不要铺垫，直接给冲击。
3. 用动作和对话推进故事，不要分析、不要总结、不要给结论。
4. **全篇有1-3句极致扎心的话**，用 `**加粗**` 包裹。其中最重要的一句必须单独成页。
5. **每篇必须包含一个"可收藏的实用元素"**（这是互动率的核心驱动力）。纯故事没人收藏。必须在故事中自然嵌入以下至少一种：
   - ✅ 对比清单：❌ vs ✅（如"3种无效关心 vs 3种有效关心"）
   - ✅ 自检题/测试：让读者对照自身（如"你中了几条？"）
   - ✅ 避雷指南：具体场景+正确做法
   - ✅ 方法/步骤：可直接执行的行动
6. **每篇必须有一个"争议性观点"或"站队空间"**。不要写"正确但无聊"的内容。要让读者看完有"我同意"或"我觉得不对"的冲动，才会评论。
7. **每篇结尾必须给读者一个"立刻能做的一件事"**。不是空洞的"学会爱自己"，而是具体的行动（如"今天就把那个对话框删了""下次她说'没事'的时候，回一句'我猜你有事'"）。
8. 总字数控制在500-800字，**总页数4-5页（不含封面）**。不要为了凑页数注水，内容讲完了就结束。宁可多一页也不要让故事断在半截。
9. **第1页必须直接抛出冲突/金句/反转**，不要铺垫叙事。读者前2秒决定是否继续，铺垫=流失。像微信突然弹出一条消息，直接进故事。
10. **前3页必须出现至少1个有辨识度的具体物品**。不是泛泛的"手机""杯子"，而是"蔫了的绿萝""起球的旧T恤""香薰机"这种有辨识度的。数据证明：有具体物品的笔记停留时间是没有的2-3倍。
11. **互动钩子必须从三种模板中选一种（已经过数据验证，其他类型回复率为0）**：
    - **选择题**："做过____的扣1，没做过的扣2"（读者只需打1个数字）
    - **打卡式**："今天开始试试____。做到了来评论区打卡。"（收藏+评论双驱动）
    - **挑衅式**："我不信有人____。有的评论区扣1。"（争议型选题专用）
    禁止用"说说你的故事""你经历过吗""你中了几条""有什么感觉"等已被数据证明无效的钩子。
12. **结尾的5秒行动必须是具体的小事**。比如"今天就把备注改回全名""发完这条消息就关机睡觉"，不是"学会爱自己"。
13. **对话必须用"角色：内容"格式**（如 `她：我今天好累` / `他：嗯` / `领导：大家辛苦了` / `妈妈：你都多大了`）。**禁止用引号叙述对话**（如一连串 `"不辛苦不辛苦"` 引号行，或 `她说"xxx"`）。"角色：内容"格式会被渲染成左右聊天气泡，视觉冲击远强于纯文字——这是内页停留时长的关键。聊天记录/群聊/伴侣对话/家人对话/回忆对话场景，必须用此格式。

**输出格式**：
1. 【标题候选】3-4个标题，**每个严格控制在10-20个字以内（含标点、emoji，这是小红书硬限制）**，口语化像朋友说话（直接写标题本身，不要加"情绪宣泄型：""认知反差型："等分类前缀），每个带1-2个emoji。**如果是热点内容，标题必须包含热点关键词**
2. 【封面页】大字标题 + 情绪钩子小字 + 背景建议（中文描述 + 英文AI绘画prompt）
   封面氛围要求：整体必须是温暖、柔和、有呼吸感。即使故事情绪偏悲伤，也要用"暖调中的孤独""温柔的光影"方向。
   英文 prompt 中必须包含 "soft warm lighting, cozy atmosphere, gentle pastel tones, emotional warmth"。
   **如果是热点内容，封面背景建议中必须包含热点元素**（如世界杯内容要有足球/球场元素，考研内容要有书本/图书馆元素）
3. 【正文】根据故事长短自然分页，页与页之间用 `---` 分隔。`---` 是**硬分页符**——代码会严格尊重你的分页决策，在 `---` 处强制换页。所以你要主动把控节奏：每段内容控制在**单页可容纳范围内（约 250-350 字 / 12-15 行）**，让每页都有完整的语义单元（一个场景/一段对话/一个金句），而不是机械堆字数。**结尾的行动句（"今天就把..."）不要单独用 --- 分页——它应该和上一页的故事结尾自然衔接。**宁可一页短一点留白，也不要塞太满被代码强制跨页切割。内容讲完了就结束，不必硬凑页数。
4. 【金句】一句话，不超过20字，必须加粗
5. 【互动钩子】**必须用以下三种类型之一**（不要用"说说你的故事""你中了几条"老套路）：
   - **站队型**："你觉得她该不该A？评论区站队" / "A还是B？不要只点赞，要说话"
   - **具体场景追问**："你有没有过为了'懂事'把期待默默折起来的时刻？"
   - **故事征集型**："评论区说一个你不敢当面说的事，我先来"
6. 【话题标签】**3-5个精准标签**（必带#不懂就问有问必答，不要超过5个）
7. 【视觉风格】选择一个最贴合的风格标签：warm_grey|twilight|crimson|mist|cool

**禁止事项**：
- 禁止"你看""其实""第一第二""总结起来"
- 禁止"真正爱你的人不会..."
- 禁止分析式表达："那不是XX，而是YY"
- 禁止给故事贴标签
- 禁止在结尾说"我想说""我想告诉你"
- **禁止结尾下定义式总结**：不要用"陪你熬过最难的日子，不是因为...只是因为..."、"或许所有人都这样"这种普适化结论来解释故事的"道理"。结尾应该用具体的行动/场景/细节收尾（比如"她把那支刻字的铅笔扔进了垃圾桶"），而不是用分析性的语言总结"人性本质"。故事讲完了就结束，不要把道理掰开揉碎讲给读者听。
- 禁止满屏emoji。正文最多放2个emoji（💔✨👇）
- **禁止写"（第1页）""（第2页）"等页码标记**，页与页之间只用 `---` 分隔
- **禁止纯叙事无实用元素**——每篇必须有收藏价值
- **禁止老套路互动钩子**——不要用"说说你的故事""你中了几条""你经历过吗""有什么感受""A还是B""评论区告诉我""你学会了吗""你觉得呢"。这些已被数据证明回复率为0
"""
        if feedback:
            prompt += f"\n\n【修改反馈】\n{feedback}\n\n请根据以上反馈修改，保持故事核心不变，聚焦解决反馈中的核心问题。不要为改而改。"

        return prompt

    def _get_data_recommendations(self, brief: dict) -> str:
        """从记忆中生成数据驱动的写作建议（基于 CTR 真实数据）。"""
        try:
            from core.agents.memory import AgentMemory
            mem = AgentMemory(self.name)
            parts = []

            # 公式表现数据 — 优先使用 avg_ctr
            formula_perf = mem.data.get("formula_performance", {})
            if formula_perf:
                current_formula = brief.get("title_formula", "")
                # 找出 CTR 最高的公式
                best = max(formula_perf.items(), key=lambda x: x[1].get("avg_ctr", 0))
                current_stats = formula_perf.get(current_formula, {})
                current_ctr = current_stats.get("avg_ctr", 0)
                best_ctr = best[1].get("avg_ctr", 0)
                if best[0] != current_formula and best[1]["count"] >= 2 and best_ctr > current_ctr + 1:
                    parts.append(f"📊 数据提示：「{best[0]}」公式历史CTR最高（{best[1]['count']}篇，均CTR {best_ctr}%），"
                                 f"当前用的是「{current_formula}」(均CTR {current_ctr}%)。如果故事角度允许，考虑切换标题公式。")

            # 支柱表现数据
            pillar_perf = mem.data.get("pillar_performance", {})
            if pillar_perf:
                best_pillar = max(pillar_perf.items(), key=lambda x: x[1].get("avg_ctr", 0))
                if best_pillar[1]["count"] >= 2:
                    parts.append(f"📊 数据提示：「{best_pillar[0]}」是你的流量密码（{best_pillar[1]['count']}篇，均CTR {best_pillar[1]['avg_ctr']}%）。")

            # 成功率提示
            stats = mem.get_stats()
            if stats["total_runs"] >= 3:
                if stats["success_rate"] < 0.3:
                    parts.append("📊 数据提示：近期成功率偏低，建议选安全牌——用验证过的结构模板，不要冒险尝试新格式。")
                elif stats["success_rate"] > 0.7:
                    parts.append("📊 数据提示：近期成功率很高，可以尝试更有野心的叙事角度。")

            if parts:
                return "\n" + "\n".join(parts)
        except Exception as e:
            logger.debug("获取数据建议失败（不影响主流程）: %s", e)
        return ""

    def handle(self, message: Message) -> None:
        """处理其他 agent 通过消息总线发来的消息。"""
        if message.msg_type == MessageType.REQUEST:
            if message.from_agent == "cover_designer":
                # 封面设计师请求补充视觉锚点
                req = message.content.get("request", "")
                logger.info("写手收到封面设计师请求: %s", req)
                # 在当前会话记忆中记录协作请求
                self._respond_to_designer(req)
            elif message.from_agent == "chief_editor":
                # 主编的重写指令由 orchestrator 直接处理，这里只记录
                pass

    def _respond_to_designer(self, request: str):
        """响应封面设计师的补充请求——在当前创作中追加视觉细节。"""
        # 记录协作历史
        from core.agents.memory import AgentMemory
        mem = AgentMemory(self.name)
        mem.add_collaboration_note("cover_designer", f"请求: {request}")

    def record_outcome(self, grade: str, topic: str):
        """记录创作结果，用于持久化学习。"""
        from core.agents.memory import AgentMemory
        mem = AgentMemory(self.name)
        context = {"topic": topic, "grade": grade}
        if grade in ("A", "S"):
            mem.record_success(context)
        elif grade == "C":
            mem.record_failure(context)
        else:
            mem.record_mediocre(context)
        mem.flush()
