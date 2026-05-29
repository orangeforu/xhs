import re

from core.agents.base import BaseAgent, MessageBus, Message, MessageType
from core.config import get_logger
from core.utils import load_prompt, FORMULA_INSTRUCTIONS

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
    # 分析式表达
    (r'那不是.*[，,]而是|这不是.*[，,]而是', "分析式表达"),
    # 老套互动钩子
    (r'说说你的故事|A还是B[？?]|你中了几条|评论区告诉我', "老套互动钩子"),
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

    # 检查加粗数量（不超过3处）
    bold_count = len(re.findall(r'\*\*[^*]+\*\*', body))
    if bold_count > 4:
        issues.append(f"加粗过多: {bold_count}处（限制3-4处）")

    # 检查 emoji 数量（正文不超过2个）
    emoji_re = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U00002764\U00002728\U00001F447]')
    emoji_count = len(emoji_re.findall(body))
    if emoji_count > 3:
        issues.append(f"正文emoji过多: {emoji_count}个（限制2-3个）")

    return issues


class EmotionalWriter(BaseAgent):
    """情感写手 Agent — 负责创作和修改笔记正文。"""

    def __init__(self, bus: MessageBus):
        prompt = load_prompt("agent_writer")
        super().__init__("emotional_writer", prompt, bus)

    def write(self, brief: dict, round_num: int = 0, feedback: str = "") -> dict:
        """创作或重写笔记。带内容守卫：禁词命中时自动重试一次。"""
        user_prompt = self._build_write_prompt(brief, feedback)
        content = self.think(user_prompt, temperature=0.8, max_tokens=2800)

        # 内容守卫：检查禁词（仅第一轮，重写轮由审核官反馈驱动）
        guard_issues = _check_content_guard(content)
        if guard_issues and round_num == 0:
            logger.warning("内容守卫命中 %d 个问题，自动重试: %s", len(guard_issues), guard_issues[:3])
            retry_feedback = feedback + "\n\n【系统自动检测到以下问题，请务必避免】\n" + "\n".join(f"- {i}" for i in guard_issues)
            retry_prompt = self._build_write_prompt(brief, retry_feedback)
            content = self.think(retry_prompt, temperature=0.6, max_tokens=2800)
            guard_issues = _check_content_guard(content)
            if guard_issues:
                logger.warning("重试后仍有 %d 个守卫问题（交由审核官处理）: %s", len(guard_issues), guard_issues[:3])

        result = {
            "brief": brief,
            "content": content,
            "round_num": round_num,
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

        prompt = f"""请创作一篇小红书图文笔记。

**选题**：{brief["topic"]}
**目标互动**：{brief.get("target_interaction", "点赞+收藏")}
**标题公式**：{formula}
{story_hint}
{data_hint}

{formula_instructions}

**核心要求**：
1. 根据故事本身选择最合适的结构（经典金句前置/对话开场/倒叙冲击/反问留白），不要每次都用同一种。参考系统提示中的结构模板。
2. **最扎心的一句话必须单独成页**，像一张可截图的海报。不要铺垫，直接给冲击。
3. 用动作和对话推进故事，不要分析、不要总结、不要给结论。
4. **全篇有1-3句极致扎心的话**，用 `**加粗**` 包裹。其中最重要的一句必须单独成页。
5. **在故事中自然嵌入一个可收藏的元素**（如对话对比/场景清单/避雷清单），让读者有"以后用得上"的理由。
6. 总字数控制在500-800字，**总页数3-5页（不含封面）**。不要为了凑页数注水，内容讲完了就结束。

**输出格式**：
1. 【标题候选】3-4个标题，覆盖情绪宣泄型/认知反差型/场景代入型/人群点名，每个带1-2个emoji
2. 【封面页】大字标题 + 情绪钩子小字 + 背景建议（中文描述 + 英文AI绘画prompt）
   封面氛围要求：整体必须是温暖、柔和、有呼吸感。即使故事情绪偏悲伤，也要用"暖调中的孤独""温柔的光影"方向。
   英文 prompt 中必须包含 "soft warm lighting, cozy atmosphere, gentle pastel tones, emotional warmth"。
3. 【正文】根据故事长短自然分页，页与页之间用 `---` 分隔。不必硬凑页数，内容讲完了就结束。
4. 【金句】一句话，不超过20字，必须加粗
5. 【互动钩子】**轻量化**：不要用"说说你的故事""A还是B？""你中了几条？"这些老套路。用具体场景追问、站队型、反向共鸣、@指令、留白钩子。之后加系列引导："这是「不敢说出口的话」系列第N篇"
6. 【话题标签】**3-5个精准标签**（必带#不懂就问有问必答，不要超过5个）
7. 【视觉风格】选择一个最贴合的风格标签：warm_grey|twilight|crimson|mist|cool

**禁止事项**：
- 禁止"你看""其实""第一第二""总结起来"
- 禁止"真正爱你的人不会..."
- 禁止分析式表达："那不是XX，而是YY"
- 禁止给故事贴标签
- 禁止在结尾说"我想说""我想告诉你"
- 禁止满屏emoji。正文最多放2个emoji（💔✨👇）
"""
        if feedback:
            prompt += f"\n\n【修改反馈】\n{feedback}\n\n请根据以上反馈修改，保持故事核心不变，聚焦解决反馈中的核心问题。不要为改而改。"

        return prompt

    def _get_data_recommendations(self, brief: dict) -> str:
        """从记忆中生成数据驱动的写作建议。"""
        try:
            from core.agents.memory import AgentMemory
            mem = AgentMemory(self.name)
            parts = []

            # 公式表现数据
            formula_perf = mem.data.get("formula_performance", {})
            if formula_perf:
                best = max(formula_perf.items(), key=lambda x: x[1]["avg_score"])
                current_formula = brief.get("title_formula", "")
                if best[0] != current_formula and best[1]["count"] >= 2:
                    parts.append(f"数据提示：「{best[0]}」公式历史表现最好（{best[1]['count']}篇，均分{best[1]['avg_score']}），"
                                 f"当前选题用的是「{current_formula}」。如果故事角度允许，可以考虑切换。")

            # 支柱表现数据
            pillar_perf = mem.data.get("pillar_performance", {})
            if pillar_perf:
                best_pillar = max(pillar_perf.items(), key=lambda x: x[1]["avg_score"])
                if best_pillar[1]["count"] >= 2:
                    parts.append(f"数据提示：「{best_pillar[0]}」支柱是你的流量密码（{best_pillar[1]['count']}篇，均分{best_pillar[1]['avg_score']}）。")

            # 成功率提示
            stats = mem.get_stats()
            if stats["total_runs"] >= 3:
                if stats["success_rate"] < 0.3:
                    parts.append("数据提示：近期成功率偏低，建议选安全牌——用验证过的结构模板，不要冒险尝试新格式。")
                elif stats["success_rate"] > 0.7:
                    parts.append("数据提示：近期成功率很高，可以尝试更有野心的叙事角度。")

            if parts:
                return "\n【数据驱动建议】\n" + "\n".join(f"- {p}" for p in parts)
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
