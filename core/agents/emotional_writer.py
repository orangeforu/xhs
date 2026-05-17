import json

from core.agents.base import BaseAgent, MessageBus, Message, MessageType
from core.config import get_logger, PROMPTS_DIR

logger = get_logger(__name__)


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


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt 文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class EmotionalWriter(BaseAgent):
    """情感写手 Agent — 负责创作和修改笔记正文。"""

    def __init__(self, bus: MessageBus):
        prompt = _load_prompt("agent_writer")
        super().__init__("emotional_writer", prompt, bus)

    def write(self, brief: dict, round_num: int = 0, feedback: str = "") -> dict:
        """创作或重写笔记。"""
        user_prompt = self._build_write_prompt(brief, feedback)
        content = self.think(user_prompt, temperature=0.8, max_tokens=2800)

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

        prompt = f"""请创作一篇小红书图文笔记。

**选题**：{brief["topic"]}
**目标互动**：{brief.get("target_interaction", "点赞+收藏")}
**标题公式**：{formula}

{formula_instructions}

**核心要求**：
1. 写一个让人忍不住往下翻的故事。**第2页必须单独放一句金句/核心洞察**，像一张可截图的海报。不要铺垫，直接给冲击。
2. 第3-4页用简短故事或场景佐证第2页的金句。用动作和对话推进，不要分析、不要总结、不要给结论。
3. 故事中自然出现"以前"和"现在"的对比，但不要标注"以前vs现在"。
4. **全篇有1-3句极致扎心的话**，用 `**加粗**` 包裹。其中最重要的一句必须单独成页（第2页）。
5. **在故事中自然嵌入一个可收藏的元素**（如对话对比/场景清单/避雷清单），让读者有"以后用得上"的理由。
6. 总字数控制在500-800字，**总页数严格控制在4-5页（不含封面）**。

**输出格式**：
1. 【标题候选】3-4个标题，覆盖情绪宣泄型/认知反差型/场景代入型/人群点名，每个带1-2个emoji
2. 【封面页】大字标题 + 情绪钩子小字 + 背景建议（中文描述 + 英文AI绘画prompt）
   封面氛围要求：整体必须是温暖、柔和、有呼吸感。即使故事情绪偏悲伤，也要用"暖调中的孤独""温柔的光影"方向。
   英文 prompt 中必须包含 "soft warm lighting, cozy atmosphere, gentle pastel tones, emotional warmth"。
3. 【正文】自然分页，页与页之间用 `---` 分隔。**总页数不超过5页**
4. 【金句】一句话，不超过20字，必须加粗
5. 【互动钩子】**轻量化**：用二选一/数字互动/@指令，不要用"说说你的故事"。之后加系列引导："这是「不敢说出口的话」系列第N篇"
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

    def handle(self, message: Message):
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
            mem.data["total_runs"] = mem.data.get("total_runs", 0) + 1
            mem.save()
