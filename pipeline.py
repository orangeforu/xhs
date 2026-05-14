#!/usr/bin/env python3
"""
小红书AI创作流水线 — Multi-Agent 架构
=====================================
7 个专家 Agent 通过消息总线协作完成笔记创作：
选题策划师 → 情感写手 → (封面设计师 ∥ 排版美工 ∥ 内容审核官) → 主编决策 → 评论运营
"""

import argparse
import hashlib
import os
import re
from datetime import datetime, timezone

from core.config import get_logger, init, load_topics_json, save_topics_json, PROJECT_ROOT
from core.agents.orchestrator import Orchestrator, _write_note_file

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════
# 向后兼容的辅助函数（旧 pipeline 提取逻辑，tests/app 仍依赖）
# ═══════════════════════════════════════════════════════════

def _clean_md(text: str) -> str:
    """去掉Markdown加粗、斜体、反引号等标记。"""
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"^[\s*_`]+|[\s*_`]+$", "", t)
    return t.strip()


def _extract_cover_info(content: str) -> dict:
    """从AI生成的Markdown中提取封面信息。"""
    info = {"title": "", "subtitle": "", "prompt": ""}

    m = re.search(r'[\[【\*]*(?:大字标题|大字|标题)[\]】\*]*[:：]\s*(.+?)\s*(?:\n|$)', content, re.IGNORECASE)
    if m:
        info["title"] = _clean_md(m.group(1))
    else:
        m = re.search(r'#+\s*(?:【?封面页?】?)?\s*\n?\s*[\*\[]*(?:大字标题|标题)[\*\]]*[:：]?\s*(.+?)\s*\n', content, re.IGNORECASE)
        if m:
            info["title"] = _clean_md(m.group(1))

    m = re.search(r'[\[【\*]*(?:情绪钩子小字|小字钩子|小字|副标题|subtitle)[\]】\*]*[:：]\s*\n\s*(.+?)(?:\n\s*\*\*|\n\n|$)', content, re.IGNORECASE)
    if not m:
        m = re.search(r'[\[【\*]*(?:情绪钩子小字|小字钩子|小字|副标题|subtitle)[\]】\*]*[:：]\s*(.+?)\s*(?:\n|$)', content, re.IGNORECASE)
    if m:
        info["subtitle"] = _clean_md(m.group(1))

    m = re.search(
        r'(?:英文\s*AI\s*绘画\s*prompt|英文\s*AI\s*prompt|英文\s*prompt|AI\s*绘画\s*prompt|English\s*prompt)\*{0,2}[:：]\s*\n?\s*(?:[-–]\s*)?(.+?)(?:\n\n|\n#|\n【|$)',
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        info["prompt"] = _clean_md(m.group(1)).replace("\n", " ")
    else:
        m = re.search(
            r'[\[【\*]*(?:背景建议|画面描述|background)[\]】\*]*[:：]\s*(.+?)(?:\n\n|\n#|\n【|$)',
            content,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            info["prompt"] = _clean_md(m.group(1)).replace("\n", " ")
        else:
            topic_hint = info["title"] or "emotional warmth"
            info["prompt"] = f"A soft emotional aesthetic scene related to {topic_hint}, warm lighting, minimalist"

    info["prompt"] = _sanitize_prompt(info["prompt"])

    if not info["title"]:
        logger.warning("未能从笔记中提取封面标题")
    if not info["subtitle"]:
        logger.warning("未能从笔记中提取封面副标题")

    return info


def _sanitize_prompt(prompt: str) -> str:
    """校验并修正 AI 绘画 prompt，防止生成恐怖/阴冷氛围。"""
    if not prompt:
        return prompt

    cold_keywords = [
        "dimly lit", "dark room", "cold-toned", "cold toned",
        "cold light", "silhouette", "empty room", "uncanny", "eerie", "creepy",
        "haunted", "gloomy", "desolate", "hollow", "void",
        "pitch black", "pitch-black", "shadowy", "ominous",
        "bleak", "dreary", "forlorn", "abandoned",
        "darkness", "no light", "black background",
        "monochrome gray", "monochrome grey", "grayscale",
    ]

    lowered = prompt.lower()
    found_cold = [kw for kw in cold_keywords if kw in lowered]

    if found_cold:
        logger.warning("封面 prompt 检测到阴冷关键词 %s，自动修正为温暖氛围", found_cold)
        replacements = {
            "dimly lit": "softly lit",
            "dark room": "warm cozy room",
            "cold-toned": "warm-toned",
            "cold toned": "warm toned",
            "cold light": "warm glow",
            "silhouette": "soft profile",
            "empty room": "cozy room with soft textures",
            "uncanny": "gentle",
            "eerie": "peaceful",
            "creepy": "warm",
            "haunted": "serene",
            "gloomy": "softly glowing",
            "desolate": "quietly comforting",
            "hollow": "tender",
            "void": "warm space",
            "pitch black": "soft twilight",
            "pitch-black": "soft twilight",
            "shadowy": "dappled with warm light",
            "ominous": "gentle",
            "bleak": "softly lit",
            "dreary": "warm and calm",
            "forlorn": "peaceful",
            "abandoned": "quietly lived-in",
            "darkness": "soft warm glow",
            "no light": "gentle warm light",
            "black background": "soft cream background",
            "monochrome gray": "soft pastel tones",
            "monochrome grey": "soft pastel tones",
            "grayscale": "warm muted tones",
        }
        for bad, good in replacements.items():
            prompt = re.sub(re.escape(bad), good, prompt, flags=re.IGNORECASE)

    warm_safeguards = [
        "soft warm lighting",
        "cozy atmosphere",
        "gentle pastel tones",
        "emotional warmth",
    ]
    for safeguard in warm_safeguards:
        if safeguard not in lowered:
            prompt += f", {safeguard}"

    return prompt.strip(", ")


def _extract_visual_style(content: str) -> str:
    """从AI生成的Markdown中提取视觉风格标签。"""
    m = re.search(
        r'[\[【\*]*(?:视觉风格|风格|style)[\]】\*]*[:：]\s*\n?\s*`?([a-z_]+)`?',
        content,
        re.IGNORECASE,
    )
    if m:
        style = m.group(1).strip().lower()
        valid_styles = {"warm_grey", "twilight", "crimson", "mist", "cool", "warm", "blank"}
        if style in valid_styles:
            return style
    return "warm_grey"


def _load_topic_pool() -> list[dict]:
    """从 data/topics.json 加载选题池。"""
    data = load_topics_json()
    return data.get("topics", [])


def _update_topic_status(topic_str: str, status: str, output_dir: str | None = None) -> None:
    """更新选题状态并持久化到 topics.json。"""
    data = load_topics_json()
    for t in data.get("topics", []):
        if t["topic"] == topic_str:
            t["status"] = status
            if status == "generated":
                t["generated_at"] = datetime.now(timezone.utc).isoformat()
            if output_dir:
                t["output_dir"] = output_dir
            break
    save_topics_json(data)


def _prepare_out_dir(topic: str) -> str:
    """准备输出目录。"""
    safe_name = "".join(c for c in topic if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")[:30]
    topic_hash = hashlib.md5(topic.encode()).hexdigest()[:4]
    out_dir = str(PROJECT_ROOT / "docs_agent" / f"{safe_name}_{topic_hash}")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def generate(topic: str | None = None, index: int | None = None) -> dict | None:
    """生成单篇笔记 — Multi-Agent 协作模式。"""
    topic_pool = _load_topic_pool()
    if topic:
        brief = next((t for t in topic_pool if t["topic"] == topic), None)
        if not brief:
            logger.error("选题池中没有找到: %s", topic)
            logger.info("可用选题: %s", [t["topic"] for t in topic_pool])
            return None
    elif index is not None:
        brief = topic_pool[index % len(topic_pool)]
    else:
        logger.error("请指定 --topic 或 --index")
        return None

    out_dir = _prepare_out_dir(brief["topic"])
    logger.info("=" * 60)
    logger.info("Multi-Agent 创作启动: %s", brief["topic"])
    logger.info("=" * 60)

    # 创建编排器，启动 7-Agent 协作流程
    orchestrator = Orchestrator()
    result = orchestrator.run(brief, out_dir)

    if result.get("status") == "abandoned":
        logger.warning("创作被主编放弃: %s", result.get("reason", "未知原因"))
        return {
            "status": "abandoned",
            "reason": result.get("reason"),
            "brief": brief,
        }

    draft = result["draft"]
    review = result["review"]
    design = result.get("design", {})
    inner_paths = result.get("inner_paths", [])
    comments = result.get("comments", {})
    rounds = result.get("rounds", 1)

    # 构建封面路径字典（兼容旧格式）
    cover_paths = {}
    if design and design.get("cover_path"):
        cover_paths["ai"] = design["cover_path"]

    # 保存笔记文件
    output_file = os.path.join(out_dir, "note.md")
    _write_note_file(output_file, brief, draft, review, cover_paths, inner_paths, comments, rounds)
    logger.info("已保存到: %s", output_file)

    # 更新选题状态
    _update_topic_status(brief["topic"], "generated", out_dir)
    logger.info("选题状态已更新为 generated | 共迭代 %d 轮 | 最终等级: %s", rounds, review.get("grade", "B"))

    return {
        "note": draft,
        "cover_paths": cover_paths,
        "inner_paths": inner_paths,
        "review": review,
        "preset_comments": comments,
        "rounds": rounds,
        "status": "completed",
    }


def list_topics() -> None:
    topic_pool = _load_topic_pool()
    logger.info("本月选题池（共 %d 个）:", len(topic_pool))
    for i, t in enumerate(topic_pool):
        status = t.get("status", "not_started")
        icon = "✅" if status == "published" else "📝" if status == "generated" else "⬜"
        logger.info("[%d] %s %s (%s | %s | %s)", i, icon, t["topic"], t["title_formula"], t["target_interaction"], status)


def batch_generate(max_count: int | None = None) -> None:
    """批量生成所有未开始的选题。"""
    topic_pool = _load_topic_pool()
    pending = [t for t in topic_pool if t.get("status") == "not_started"]

    if not pending:
        logger.info("没有待生成的选题，全部已完成。")
        return

    if max_count:
        pending = pending[:max_count]

    logger.info("批量生成开始，共 %d 篇待生成", len(pending))
    success = 0
    failed = 0
    abandoned = 0

    for i, brief in enumerate(pending, 1):
        logger.info("[%d/%d] 正在生成: %s", i, len(pending), brief["topic"])
        try:
            result = generate(topic=brief["topic"])
            if result:
                if result.get("status") == "abandoned":
                    abandoned += 1
                else:
                    success += 1
            else:
                failed += 1
        except Exception as e:
            logger.error("生成失败: %s - %s", brief["topic"], e)
            failed += 1

    logger.info("批量生成完成 — 成功: %d, 放弃: %d, 失败: %d", success, abandoned, failed)


if __name__ == "__main__":
    init()
    parser = argparse.ArgumentParser(description="小红书AI创作流水线 — Multi-Agent 架构")
    parser.add_argument("--topic", type=str, help="指定选题")
    parser.add_argument("--index", type=int, help="选题索引")
    parser.add_argument("--list", action="store_true", help="列出所有选题")
    parser.add_argument("--batch", action="store_true", help="批量生成所有未开始的选题")
    parser.add_argument("--max", type=int, help="批量生成时限制最大篇数")
    args = parser.parse_args()

    if args.list:
        list_topics()
    elif args.batch:
        batch_generate(max_count=args.max)
    else:
        generate(topic=args.topic, index=args.index)
