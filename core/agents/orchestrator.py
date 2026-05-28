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


def _write_note_file(
    output_file: str,
    brief: dict,
    draft: dict,
    review: dict,
    cover_paths: dict,
    inner_paths: list,
    preset_comments: dict,
    rounds: int = 1,
) -> None:
    """将笔记及相关产物写入 Markdown 文件（兼容旧格式，确保 app.py 正则解析正常）。"""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# {brief['topic']}\n\n")
        f.write(draft["content"])
        f.write("\n\n---\n\n")
        f.write("## 审核结果\n\n")
        f.write(f"**迭代轮数**: {rounds} | **最终审核**: {review.get('grade', 'B')} | **审核结论**: {review.get('verdict', 'unknown')}\n\n")
        if review.get("overall_comment"):
            f.write(f"**审核评语**: {review['overall_comment']}\n\n")
        f.write(_format_review(review))
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


def _format_review(review: dict) -> str:
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
