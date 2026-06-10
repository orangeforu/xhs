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

from core.config import (
    get_logger, init, load_topics_json, save_topics_json, load_calendar_json,
    PROJECT_ROOT, DATA_DIR, _atomic_write_json, _lock_file, _unlock_file,
)
from core.agents.orchestrator import Orchestrator
from core.topic_selector import smart_select, smart_batch
from core.utils import clean_md as _clean_md, write_note_file

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════
# 向后兼容的辅助函数（旧 pipeline 提取逻辑，tests/app 仍依赖）
# ═══════════════════════════════════════════════════════════

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
    # 重新检查替换后的 prompt，避免重复追加
    lowered_after = prompt.lower()
    for safeguard in warm_safeguards:
        if safeguard not in lowered_after:
            prompt += f", {safeguard}"

    # 去除尾部多余的逗号和空格（不用 strip 避免误删首字母）
    return prompt.rstrip(", ").lstrip()


def _load_topic_pool() -> list[dict]:
    """从 data/topics.json 加载选题池。"""
    data = load_topics_json()
    return data.get("topics", [])


def _update_topic_status(topic_str: str, status: str, output_dir: str | None = None) -> None:
    """更新选题状态并持久化到 topics.json（原子读-改-写，带文件锁保护）。"""
    import json as _json

    path = DATA_DIR / "topics.json"
    lock_path = path.with_suffix(".lock")
    with open(lock_path, "w") as lock_f:
        _lock_file(lock_f, exclusive=True)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = _json.load(f)
            for t in data.get("topics", []):
                if t["topic"] == topic_str:
                    t["status"] = status
                    if status == "generated":
                        t["generated_at"] = datetime.now(timezone.utc).isoformat()
                    if output_dir:
                        t["output_dir"] = output_dir
                    break
            _atomic_write_json(path, data, with_lock=False)
        finally:
            _unlock_file(lock_f)


def _prepare_out_dir(topic: str) -> str:
    """准备输出目录。"""
    safe_name = "".join(c for c in topic if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")[:30]
    topic_hash = hashlib.md5(topic.encode()).hexdigest()[:4]
    out_dir = str(PROJECT_ROOT / "docs_agent" / "pending" / f"{safe_name}_{topic_hash}")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def generate(topic: str | None = None, index: int | None = None, smart: bool = False) -> dict | None:
    """生成单篇笔记 — Multi-Agent 协作模式。"""
    topic_pool = _load_topic_pool()

    if smart:
        brief, scores = smart_select(topic_pool)
        if not brief:
            logger.error("智能选题失败：没有可用选题")
            return None
        logger.info("智能选题结果: %s", brief["topic"])
    elif topic:
        brief = next((t for t in topic_pool if t["topic"] == topic), None)
        if not brief:
            logger.error("选题池中没有找到: %s", topic)
            logger.info("可用选题: %s", [t["topic"] for t in topic_pool])
            return None
    elif index is not None:
        if not topic_pool:
            logger.error("选题池为空，无法按索引选取")
            return None
        # 优先按 topic ID 匹配，fallback 到列表位置
        brief = next((t for t in topic_pool if t.get("id") == index), None)
        if not brief:
            brief = topic_pool[index % len(topic_pool)]
            logger.info("未找到 ID=%d 的选题，使用列表位置 %d", index, index % len(topic_pool))
    else:
        logger.error("请指定 --topic、--index 或 --smart")
        return None

    # 读取用户反馈（如有）
    user_feedback = brief.pop("feedback", "")
    if user_feedback:
        logger.info("检测到用户反馈: %s", user_feedback[:100])

    out_dir = _prepare_out_dir(brief["topic"])
    logger.info("=" * 60)
    logger.info("Multi-Agent 创作启动: %s", brief["topic"])
    logger.info("=" * 60)

    # 查找系列风格绑定
    calendar = load_calendar_json()
    series_config = calendar.get("series", {})
    for series_name, series_info in series_config.items():
        if series_name in brief.get("topic", ""):
            brief["series_style"] = series_info.get("style", "")
            logger.info("匹配系列「%s」，绑定风格: %s", series_name, brief["series_style"])
            break

    # 创建编排器，启动 7-Agent 协作流程
    orchestrator = Orchestrator()
    result = orchestrator.run(brief, out_dir, user_feedback=user_feedback)

    if result.get("status") == "abandoned":
        logger.warning("创作被主编放弃: %s", result.get("reason", "未知原因"))
        return {
            "status": "abandoned",
            "reason": result.get("reason"),
            "brief": brief,
        }

    draft = result.get("draft")
    if not draft:
        logger.error("编排器未返回 draft，可能内部异常")
        return None
    review = result["review"]
    design = result.get("design", {})
    inner_paths = result.get("inner_paths", [])
    comments = result.get("comments", {})
    rounds = result.get("rounds", 1)

    # 构建封面路径字典（支持 A/B 双封面）
    cover_paths = {}
    if design:
        # 优先使用 cover_paths（A/B 双方案）
        if design.get("cover_paths"):
            cover_paths = design["cover_paths"]
        elif design.get("cover_path"):
            cover_paths["ai"] = design["cover_path"]

    # LLM 标题评分
    title_eval = None
    try:
        from core.publish_helpers import extract_title_candidates, evaluate_title_candidates
        candidates = extract_title_candidates(draft.get("content", ""))
        if candidates:
            title_eval = evaluate_title_candidates(candidates, brief["topic"])
            if title_eval:
                best = title_eval[0]
                logger.info("标题评分完成: 最佳「%s」(%d分, %s级)", best["title"], best["score"], best["level"])
    except Exception as e:
        logger.warning("标题评分失败（不影响主流程）: %s", e)

    # 保存笔记文件
    output_file = os.path.join(out_dir, "note.md")
    write_note_file(output_file, brief, draft, review, cover_paths, inner_paths, comments, rounds, title_eval=title_eval)
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
        logger.info("[ID %s] %s %s (%s | %s | %s)", t.get("id", i), icon, t["topic"], t["title_formula"], t["target_interaction"], status)


def _generate_trending_brief(trending_item: dict) -> dict | None:
    """基于热点信息生成完整的 brief。

    Args:
        trending_item: 热点信息，包含 keyword, source, heat, emotional_potential, story_angle_hint

    Returns:
        完整的 brief，包含 topic, title_formula, angle 等字段
    """
    try:
        from core.writer import _call_api, _extract_content
        keyword = trending_item["keyword"]
        story_hint = trending_item.get("story_angle_hint", "")
        emotional_potential = trending_item.get("emotional_potential", "medium")

        prompt = f"""请基于以下热点信息，生成一个小红书情感笔记的选题 brief。

**热点信息**：
- 热点关键词：{keyword}
- 情感转化潜力：{emotional_potential}
- 故事角度提示：{story_hint}

**要求**：
1. 选题必须围绕热点展开，但核心是情感冲突，热点只是场景
2. 标题公式建议用「观点冲击式」或「问句式」，更容易吸引点击
3. 目标互动建议用「评论驱动」或「共鸣驱动」
4. 角度要具体、有画面感，能引发读者共鸣
5. 选题标题要包含热点关键词，利用热点的搜索流量

**输出格式**（JSON）：
{{
  "topic": "选题标题（必须包含热点关键词，15-25字）",
  "title_formula": "标题公式（观点冲击式/问句式/概念解读式/方法承诺式）",
  "target_interaction": "目标互动（评论驱动/共鸣驱动/分享驱动/点赞驱动）",
  "angle": "角度（具体描述，50-100字）",
  "keywords": ["关键词1", "关键词2", "关键词3"],
  "pillar": "支柱（亲密关系洞察/自我成长/情绪管理/社交洞察）"
}}

请只输出 JSON，不要输出其他内容。"""

        messages = [{"role": "user", "content": prompt}]
        response = _call_api(messages, temperature=0.7, max_tokens=2000)

        import json
        logger.info("API 完整响应: %s", json.dumps(response, ensure_ascii=False, indent=2)[:1000])

        content = _extract_content(response)

        logger.info("LLM 原始输出: %s", content[:500])

        from core.utils import extract_json_from_llm
        brief = extract_json_from_llm(content)

        if not brief or "topic" not in brief:
            logger.warning("热点 brief 生成失败：缺少必要字段。LLM 输出: %s", content[:300])
            return None

        # 添加热点特殊字段
        brief["trending_keyword"] = keyword
        brief["story_angle_hint"] = story_hint
        brief["emotional_potential"] = emotional_potential
        brief["is_trending_content"] = True

        logger.info("热点 brief 生成成功: %s", brief["topic"])
        return brief

    except Exception as e:
        logger.error("热点 brief 生成失败: %s", e)
        return None


def generate_trending(max_count: int = 1) -> list[dict]:
    """基于当前热点生成内容。

    Args:
        max_count: 最多生成几篇热点内容

    Returns:
        生成结果列表
    """
    from core.trend_detector import get_trending_briefs

    logger.info("=" * 60)
    logger.info("热点内容生成模式启动")
    logger.info("=" * 60)

    # 采集热点
    trending_briefs = get_trending_briefs()
    if not trending_briefs:
        logger.warning("未获取到热点数据，无法生成热点内容")
        return []

    logger.info("获取到 %d 个热点，准备生成 %d 篇内容", len(trending_briefs), max_count)

    # 限制生成数量
    trending_briefs = trending_briefs[:max_count]

    results = []
    for i, trending_item in enumerate(trending_briefs, 1):
        logger.info("[%d/%d] 正在处理热点: %s", i, len(trending_briefs), trending_item["keyword"])

        # 生成完整 brief
        brief = _generate_trending_brief(trending_item)
        if not brief:
            logger.warning("热点 %s 的 brief 生成失败，跳过", trending_item["keyword"])
            continue

        # 直接用 brief 调用 orchestrator 生成内容
        out_dir = _prepare_out_dir(brief["topic"])
        logger.info("Multi-Agent 创作启动: %s", brief["topic"])

        orchestrator = Orchestrator()
        result = orchestrator.run(brief, out_dir)

        if result.get("status") == "abandoned":
            logger.warning("创作被主编放弃: %s", result.get("reason", "未知原因"))
            continue

        draft = result.get("draft")
        if not draft:
            logger.error("编排器未返回 draft，可能内部异常")
            continue

        review = result["review"]
        design = result.get("design", {})
        inner_paths = result.get("inner_paths", [])
        comments = result.get("comments", {})
        rounds = result.get("rounds", 1)

        # 构建封面路径字典（从 result 顶层获取，不是在 design 里）
        cover_paths = result.get("cover_paths") or {}
        if not cover_paths and result.get("cover_path"):
            cover_paths["ai"] = result["cover_path"]

        # LLM 标题评分
        title_eval = None
        try:
            from core.publish_helpers import extract_title_candidates, evaluate_title_candidates
            candidates = extract_title_candidates(draft.get("content", ""))
            if candidates:
                title_eval = evaluate_title_candidates(candidates, brief["topic"])
        except Exception as e:
            logger.warning("标题评分失败（不影响主流程）: %s", e)

        # 保存笔记文件
        output_file = os.path.join(out_dir, "note.md")
        write_note_file(output_file, brief, draft, review, cover_paths, inner_paths, comments, rounds, title_eval=title_eval)
        logger.info("热点内容已保存: %s", output_file)
        logger.info("选题状态: generated | 共迭代 %d 轮 | 最终等级: %s", rounds, review.get("grade", "B"))

        results.append({
            "trending_keyword": brief["trending_keyword"],
            "topic": brief["topic"],
            "output_dir": out_dir,
            "status": "completed",
        })

    logger.info("热点内容生成完成: 成功 %d/%d", len(results), len(trending_briefs))
    return results


def batch_generate(max_count: int | None = None, smart: bool = False, workers: int = 1) -> None:
    """批量生成选题。smart=True 时按智能排序选取。workers>1 时并行生成。"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    topic_pool = _load_topic_pool()

    if smart:
        count = max_count or 3
        pending = smart_batch(count=count, topic_pool=topic_pool)
        if not pending:
            logger.info("没有可用的选题。")
            return
        logger.info("智能批量选题完成，共选出 %d 个选题", len(pending))
    else:
        pending = [t for t in topic_pool if t.get("status") == "not_started"]
        if not pending:
            logger.info("没有待生成的选题，全部已完成。")
            return
        if max_count:
            pending = pending[:max_count]

    logger.info("批量生成开始，共 %d 篇待生成（workers=%d）", len(pending), workers)
    success = 0
    failed = 0
    abandoned = 0

    def _gen(idx: int, brief: dict) -> tuple[int, str, dict | None]:
        logger.info("[%d/%d] 正在生成: %s", idx, len(pending), brief["topic"])
        result = generate(topic=brief["topic"])
        return idx, brief["topic"], result

    if workers <= 1:
        # 串行模式
        for i, brief in enumerate(pending, 1):
            try:
                _, _, result = _gen(i, brief)
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
    else:
        # 并行模式
        with ThreadPoolExecutor(max_workers=min(workers, len(pending))) as executor:
            futures = {
                executor.submit(_gen, i, brief): i
                for i, brief in enumerate(pending, 1)
            }
            for future in as_completed(futures):
                try:
                    idx, topic, result = future.result()
                    if result:
                        if result.get("status") == "abandoned":
                            abandoned += 1
                        else:
                            success += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error("生成失败: %s", e)
                    failed += 1

    logger.info("批量生成完成 — 成功: %d, 放弃: %d, 失败: %d", success, abandoned, failed)


if __name__ == "__main__":
    init()
    parser = argparse.ArgumentParser(description="小红书AI创作流水线 — Multi-Agent 架构")
    parser.add_argument("--topic", type=str, help="指定选题")
    parser.add_argument("--index", type=int, help="选题索引")
    parser.add_argument("--smart", action="store_true", help="智能选题（基于评分推荐最优选题）")
    parser.add_argument("--list", action="store_true", help="列出所有选题")
    parser.add_argument("--batch", action="store_true", help="批量生成所有未开始的选题")
    parser.add_argument("--max", type=int, help="批量生成时限制最大篇数")
    parser.add_argument("--workers", type=int, default=1, help="批量生成并行数（默认1，串行）")
    parser.add_argument("--trending", action="store_true", help="基于当前热点生成内容")
    args = parser.parse_args()

    if args.list:
        list_topics()
    elif args.batch:
        batch_generate(max_count=args.max, smart=args.smart, workers=args.workers)
    elif args.trending:
        generate_trending(max_count=args.max or 1)
    else:
        generate(topic=args.topic, index=args.index, smart=args.smart)
