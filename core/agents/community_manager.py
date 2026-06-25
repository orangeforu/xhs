import re

from core.agents.base import BaseAgent, MessageBus, Message, MessageType
from core.config import get_logger
from core.utils import load_prompt, extract_json_from_llm

logger = get_logger(__name__)


class CommunityManager(BaseAgent):
    """评论运营 Agent — 生成发布后用于引导互动的预设评论。"""

    def __init__(self, bus: MessageBus):
        prompt = load_prompt("agent_community")
        super().__init__("community_manager", prompt, bus)

    def generate_comments(self, note_content: str, round_num: int = 0) -> dict:
        """生成预设评论（带分类和回复模板）。"""
        prompt = f"""笔记内容：
{note_content}

请生成5-8条预设评论和3条博主回复模板。

**评论分类要求**（每条评论必须属于以下一类，且必须覆盖全部5类）：

1. **poll_choice（选择题，必含1条）**：把互动钩子的问题变成评论区的第一条评论。例如互动钩子是"扣1还是扣2"，第一条评论就写"我先来！扣2。姐妹们跟上队形 👇"。作用是降低参与门槛——读者看到有人先回了，自己跟着扣。

2. **controversy（站队，必含1条）**：明确站一个立场，引发对立面的人来反驳。例如"我就是那种分手后绝对不删的人，删了反而天天想。不删反而懒得看。"

3. **resonance_badge（打卡/标签，必含1条）**：让读者对号入座，像领一个身份标签。例如"母单26年的我居然全中…原来不是我性格差，是我一直在自我攻击 😭"

4. **supplement_story（补充经历，必含1条）**：用真实细节补充一个类似故事。必须包含具体的物品/时间/数字，看起来像真人在分享。例如"上次他生日我做了三个菜等他到九点，他说在公司吃了。我把菜倒进垃圾桶，他问我为什么生气。"

5. **tag_friend（@好友，必含1条）**：用自然的理由@一个朋友进来。不能像广告，要像真闺蜜看到一篇扎心内容后的第一反应。例如"@小美 你快看！这就是上次我说你总是'没事'其实是'很有事'的原因！！"

**博主回复模板要求**：
- 每条必须针对特定评论类型设计回复
- 语气像闺蜜深夜微信，不是客服
- 每条 ≤20字

请严格按以下 JSON 格式输出：
{{
  "comments": [
    {{"type": "poll_choice", "text": "评论内容"}},
    {{"type": "controversy", "text": "评论内容"}},
    {{"type": "resonance_badge", "text": "评论内容"}},
    {{"type": "supplement_story", "text": "评论内容"}},
    {{"type": "tag_friend", "text": "评论内容"}},
    {{"type": "resonance_badge", "text": "另一条打卡式评论"}},
    {{"type": "supplement_story", "text": "另一条补充故事"}}
  ],
  "reply_templates": [
    "回复模板1",
    "回复模板2",
    "回复模板3"
  ]
}}

**关键原则**：
- 每条评论读起来必须像一个真实用户在打字，不能像AI生成的
- 选择题评论必须放在第一位（降低后续读者的参与门槛）
- 打卡/标签评论让读者觉得"这说的就是我"，产生身份认同
- 补充故事必须包含一个具体的物品或动作细节"""

        raw = self.think(prompt, temperature=0.55, max_tokens=1500)

        # 解析 JSON
        parsed = self._parse_comments_json(raw)

        comments = parsed.get("comments", [])
        reply_templates = parsed.get("reply_templates", [])

        # 验证评论数量
        if len(comments) < 5:
            logger.warning("评论数量不足（%d条），期望5-8条", len(comments))

        # fallback: 如果 JSON 解析失败，用旧逻辑
        if not comments:
            comments = [
                {"type": "resonance", "text": line.strip()}
                for line in raw.split("\n")
                if line.strip()
                and not re.match(r'^[-*]\s|^\d+[\.\、\)]|^【|^##|^\{|\}', line.strip())
                and len(line.strip()) > 3
            ]

        # 提取纯文本列表（向后兼容）
        comment_texts = [c["text"] if isinstance(c, dict) else c for c in comments]

        result = {
            "comments": comment_texts,
            "comments_classified": comments,
            "reply_templates": reply_templates,
            "raw": raw,
            "round_num": round_num,
        }

        self.send(to_agent=None, msg_type=MessageType.COMMENT, content=result, round_num=round_num)
        logger.info("评论运营生成 %d 条预设评论（%d 条回复模板）", len(comments), len(reply_templates))
        return result

    def _parse_comments_json(self, raw: str) -> dict:
        """从 LLM 输出中解析 JSON。"""
        parsed = extract_json_from_llm(raw)
        return parsed if parsed else {}

    def handle(self, message: Message) -> None:
        """处理消息总线消息。"""
        if message.msg_type == MessageType.REVIEW:
            # 记录审核结果，了解内容质量
            grade = message.content.get("grade", "B")
            logger.debug("评论运营收到审核结果: grade=%s", grade)
