import re

from core.agents.base import BaseAgent, MessageBus, Message, MessageType
from core.config import get_logger, PROMPTS_DIR

logger = get_logger(__name__)


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt 文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class CommunityManager(BaseAgent):
    """评论运营 Agent — 生成发布后用于引导互动的预设评论。"""

    def __init__(self, bus: MessageBus):
        prompt = _load_prompt("agent_community")
        super().__init__("community_manager", prompt, bus)

    def generate_comments(self, note_content: str, round_num: int = 0) -> dict:
        """生成预设评论。"""
        prompt = f"""笔记内容：
{note_content}

请生成5-8条评论，直接输出评论内容，每条之间用空行分隔。不要编号，不要加引号。"""

        raw = self.think(prompt, temperature=0.7, max_tokens=1500)

        comments = [
            line.strip()
            for line in raw.split("\n")
            if line.strip()
            and not re.match(r'^[-*]\s|^\d+[\.\、\)]|^【|^##', line.strip())
        ]

        result = {
            "comments": comments,
            "raw": raw,
            "round_num": round_num,
        }

        self.send(to_agent=None, msg_type=MessageType.COMMENT, content=result, round_num=round_num)
        logger.info("评论运营生成 %d 条预设评论", len(comments))
        return result

    def handle(self, message: Message):
        pass
