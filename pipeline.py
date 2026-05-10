#!/usr/bin/env python3
"""
小红书AI创作流水线
用法:
    python pipeline.py --topic "怎么判断男朋友是不是真的爱你？"
"""

import argparse
import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone

from core.config import get_logger, init, load_topics_json, save_topics_json, PROJECT_ROOT, PUBLISHED_DIR
from core.writer import write_note, review_note, generate_preset_comments
from core.image_generator import generate_cover_ai, generate_inner_pages

logger = get_logger(__name__)


def _load_topic_pool():
    """从 data/topics.json 加载选题池。"""
    data = load_topics_json()
    return data.get("topics", [])


def _update_topic_status(topic_str: str, status: str, output_dir: str = None):
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


def _clean_md(text: str) -> str:
    """去掉Markdown加粗、斜体、反引号等标记。"""
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r'^[\s*_`]+|[\s*_`]+$', '', t)
    return t.strip()


def _extract_cover_info(content: str) -> dict:
    """从AI生成的Markdown中提取封面信息。"""
    info = {"title": "", "subtitle": "", "prompt": ""}

    # 大字标题
    m = re.search(r'[\[【\*]*(?:大字标题|大字|标题)[\]】\*]*[:：]\s*(.+?)\s*(?:\n|$)', content, re.IGNORECASE)
    if m:
        info["title"] = _clean_md(m.group(1))
    else:
        m = re.search(r'#+\s*(?:【?封面页?】?)?\s*\n?\s*[*\[]*(?:大字标题|标题)[*\]]*[:：]?\s*(.+?)\s*\n', content, re.IGNORECASE)
        if m:
            info["title"] = _clean_md(m.group(1))

    # 情绪钩子小字 / 副标题（兼容换行格式，如 DeepSeek 会在冒号后换行）
    m = re.search(r'[\[【\*]*(?:情绪钩子小字|小字钩子|小字|副标题|subtitle)[\]】\*]*[:：]\s*\n\s*(.+?)(?:\n\s*\*\*|\n\n|$)', content, re.IGNORECASE)
    if not m:
        m = re.search(r'[\[【\*]*(?:情绪钩子小字|小字钩子|小字|副标题|subtitle)[\]】\*]*[:：]\s*(.+?)\s*(?:\n|$)', content, re.IGNORECASE)
    if m:
        info["subtitle"] = _clean_md(m.group(1))

    # 背景建议 -> AI绘画prompt（优先提取英文 prompt）
    # 先尝试匹配明确的英文 prompt 标记（兼容中间有空格、AI、绘画、**加粗等变体）
    m = re.search(
        r'(?:英文\s*AI\s*绘画\s*prompt|英文\s*AI\s*prompt|英文\s*prompt|AI\s*绘画\s*prompt|English\s*prompt)\*?[:：]\s*\n?\s*(?:[-–]\s*)?(.+?)(?:\n\n|\n#|\n【|$)',
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        info["prompt"] = _clean_md(m.group(1)).replace('\n', ' ')
    else:
        # fallback：匹配通用的背景建议/画面描述（去掉 prompt 避免误匹配英文 prompt 标签）
        m = re.search(
            r'[\[【\*]*(?:背景建议|画面描述|background)[\]】\*]*[:：]\s*(.+?)(?:\n\n|\n#|\n【|$)',
            content,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            info["prompt"] = _clean_md(m.group(1)).replace('\n', ' ')
        else:
            info["prompt"] = f"A soft emotional aesthetic scene related to {info['title']}, warm lighting, minimalist"

    return info


def _write_note_file(output_file: str, brief: dict, result: dict, review: dict, cover_paths: dict, inner_paths: list, preset_comments: dict):
    """将笔记及相关产物写入 Markdown 文件。"""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# {brief['topic']}\n\n")
        f.write(result["content"])
        f.write("\n\n---\n\n")
        f.write("## 审核结果\n\n")
        f.write(review["review"])
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
            for c in preset_comments["comments"]:
                f.write(f"- {c}\n")


def generate(topic: str = None, index: int = None):
    """生成单篇笔记 + 封面。"""
    topic_pool = _load_topic_pool()
    if topic:
        brief = next((t for t in topic_pool if t["topic"] == topic), None)
        if not brief:
            logger.error("选题池中没有找到: %s", topic)
            logger.info("可用选题: %s", [t['topic'] for t in topic_pool])
            return
    elif index is not None:
        brief = topic_pool[index % len(topic_pool)]
    else:
        logger.error("请指定 --topic 或 --index")
        return

    # 准备输出目录
    safe_name = "".join(c for c in brief['topic'] if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')[:30]
    topic_hash = hashlib.md5(brief['topic'].encode()).hexdigest()[:4]
    out_dir = str(PROJECT_ROOT / "docs" / f"{safe_name}_{topic_hash}")
    os.makedirs(out_dir, exist_ok=True)

    logger.info("正在生成笔记: %s", brief['topic'])

    # Step 1: 创作
    result = write_note(brief)
    logger.info("笔记创作完成，字数约 %d", len(result["content"]))

    # Step 2: 提取封面信息
    cover_info = _extract_cover_info(result["content"])
    logger.info("封面信息 — 标题: %s | 小字: %s", cover_info['title'] or '(未提取)', cover_info['subtitle'] or '(未提取)')

    # Step 3: 生成封面（仅AI绘画方案）
    cover_paths = {}
    if cover_info["title"] and cover_info["subtitle"]:
        try:
            cover_paths["ai"] = generate_cover_ai(
                prompt=cover_info["prompt"],
                title=cover_info["title"],
                subtitle=cover_info["subtitle"],
                output_path=os.path.join(out_dir, "cover_ai.png"),
            )
        except Exception as e:
            logger.warning("AI封面生成失败: %s", e)

    # Step 4: 生成内页图
    inner_paths = []
    try:
        inner_paths = generate_inner_pages(result["content"], out_dir, style="warm")
    except Exception as e:
        logger.warning("内页图生成失败: %s", e)

    # Step 5: 审核（结构化）
    logger.info("正在审核...")
    review = review_note(result["content"])
    logger.info("审核等级: %s", review.get("grade", "B"))

    # Step 5b: C级自动重写
    if review.get("grade") == "C":
        logger.warning("审核为 C 级，触发自动重写...")
        suggestions = ""
        if review.get("raw_json"):
            issues = review["raw_json"].get("issues", [])
            sugs = review["raw_json"].get("suggestions", [])
            suggestions = "\n".join([f"- {i}" for i in issues] + [f"- {s}" for s in sugs])
        rewrite_brief = dict(brief)
        rewrite_brief["_rewrite_instructions"] = suggestions or "大幅优化故事节奏，减少分析腔和说教"
        result = write_note(rewrite_brief)
        review = review_note(result["content"])
        logger.info("重写后审核等级: %s", review.get("grade", "B"))

    # Step 6: 生成预设评论
    preset_comments = {}
    try:
        preset_comments = generate_preset_comments(result["content"])
        if preset_comments.get("comments"):
            logger.info("生成 %d 条预设评论", len(preset_comments["comments"]))
    except Exception as e:
        logger.warning("预设评论生成失败: %s", e)

    # Step 7: 保存笔记
    output_file = os.path.join(out_dir, "note.md")
    _write_note_file(output_file, brief, result, review, cover_paths, inner_paths, preset_comments)
    logger.info("已保存到: %s", output_file)

    # Step 8: 更新选题状态
    _update_topic_status(brief["topic"], "generated", out_dir)
    logger.info("选题状态已更新为 generated")

    return {
        "note": result,
        "cover_paths": cover_paths,
        "inner_paths": inner_paths,
        "review": review,
        "preset_comments": preset_comments,
    }


def list_topics():
    topic_pool = _load_topic_pool()
    logger.info("本月选题池（共 %d 个）:", len(topic_pool))
    for i, t in enumerate(topic_pool):
        status = t.get("status", "not_started")
        icon = "✅" if status == "published" else "📝" if status == "generated" else "⬜"
        logger.info("[%d] %s %s (%s | %s | %s)", i, icon, t['topic'], t['title_formula'], t['target_interaction'], status)


def batch_generate(max_count: int = None):
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

    for i, brief in enumerate(pending, 1):
        logger.info("[%d/%d] 正在生成: %s", i, len(pending), brief["topic"])
        try:
            result = generate(topic=brief["topic"])
            if result:
                success += 1
            else:
                failed += 1
        except Exception as e:
            logger.error("生成失败: %s - %s", brief["topic"], e)
            failed += 1

    logger.info("批量生成完成 — 成功: %d, 失败: %d", success, failed)


if __name__ == "__main__":
    init()
    parser = argparse.ArgumentParser(description="小红书AI创作流水线")
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
