"""
Multi-Agent 创作编排器
===================
把 7 个专家 Agent 通过消息总线协作完成一篇笔记的创作。
"""

from core.agents import (
    MessageBus,
    EmotionalWriter,
    CoverDesigner,
    ContentEditor,
    LayoutArtist,
    CommunityManager,
    TopicStrategist,
    ChiefEditor,
)
from core.config import get_logger

logger = get_logger(__name__)


class Orchestrator:
    """编排器 — 创建 Agent 团队，启动 ChiefEditor 协调创作。"""

    def __init__(self):
        self.bus = MessageBus()
        self.writer = EmotionalWriter(self.bus)
        self.designer = CoverDesigner(self.bus)
        self.artist = LayoutArtist(self.bus)
        self.editor = ContentEditor(self.bus)
        self.community = CommunityManager(self.bus)
        self.strategist = TopicStrategist(self.bus)
        self.chief = ChiefEditor(self.bus)

    def run(self, brief: dict, out_dir: str) -> dict:
        """
        执行完整的多 Agent 创作流程。

        Returns:
            dict: 包含 draft, design, inner_paths, review, comments, rounds, status
        """
        # 可选：选题策划师增强 brief
        try:
            enriched_brief = self.strategist.enrich_brief(brief)
        except Exception as e:
            logger.warning("选题策划失败，使用原始 brief: %s", e)
            enriched_brief = brief

        # 主编协调全流程
        result = self.chief.orchestrate(
            brief=enriched_brief,
            writer=self.writer,
            designer=self.designer,
            artist=self.artist,
            editor=self.editor,
            community=self.community,
            out_dir=out_dir,
        )

        result["brief"] = enriched_brief
        return result
