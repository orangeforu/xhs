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

**评论分类要求**（每条评论必须属于以下一类）：
- discussion_starter：引导讨论，让读者想分享自己的经历
- controversy：制造站队，引发观点碰撞
- resonance：情感共鸣，表达"我也是"
- supplement：补充故事，丰富内容
- tag_friend：@朋友，促进裂变传播

**博主回复模板要求**：
- 语气温暖、亲切，像闺蜜聊天
- 每条不超过15字

请严格按以下 JSON 格式输出：
{{
  "comments": [
    {{"type": "discussion_starter", "text": "评论内容"}},
    {{"type": "controversy", "text": "评论内容"}},
    {{"type": "resonance", "text": "评论内容"}},
    {{"type": "supplement", "text": "评论内容"}},
    {{"type": "tag_friend", "text": "评论内容"}}
  ],
  "reply_templates": [
    "回复模板1",
    "回复模板2",
    "回复模板3"
  ]
}}"""

        raw = self.think(prompt, temperature=0.7, max_tokens=1500)

        # 解析 JSON
        parsed = self._parse_comments_json(raw)

        comments = parsed.get("comments", [])
        reply_templates = parsed.get("reply_templates", [])

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

    def handle(self, message: Message):
        pass
