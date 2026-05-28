from core.agents.base import BaseAgent, MessageBus, Message, MessageType
from core.config import get_logger
from core.image_generator import generate_inner_pages

logger = get_logger(__name__)


class LayoutArtist(BaseAgent):
    """排版美工 Agent — 负责内页图的生成。"""

    def __init__(self, bus: MessageBus):
        # LayoutArtist 不需要复杂的 system prompt，它的工作主要是执行
        super().__init__("layout_artist", "你是小红书图文笔记的排版美工，负责将文字内容渲染成美观的内页图片。", bus)

    def layout(self, note_content: str, style: str = "warm_grey", out_dir: str = "", round_num: int = 0) -> list[str]:
        """生成内页图。"""
        logger.info("排版美工开始生成内页图: style=%s", style)

        try:
            inner_paths = generate_inner_pages(note_content, out_dir, style=style)
            logger.info("排版美工完成内页生成: %d 张", len(inner_paths))
        except Exception as e:
            logger.error("内页生成失败: %s", e)
            inner_paths = []

        result = {
            "inner_paths": inner_paths,
            "style": style,
            "round_num": round_num,
        }

        self.send(to_agent=None, msg_type=MessageType.DESIGN, content=result, round_num=round_num)
        return inner_paths

    def handle(self, message: Message):
        if message.msg_type == MessageType.DRAFT:
            # 收到 draft 更新，记录字数
            content = message.content.get("content", "")
            logger.debug("排版美工收到稿件，字数约 %d", len(content))
