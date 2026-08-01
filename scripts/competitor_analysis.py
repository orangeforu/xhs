#!/usr/bin/env python3
"""
竞品分析脚本 — 采集情感赛道爆款笔记，反哺选题池
================================================

用法:
    python scripts/competitor_analysis.py              # 分析情感赛道爆款
    python scripts/competitor_analysis.py --query "恋爱"  # 指定关键词
    python scripts/competitor_analysis.py --save       # 保存到 data/topics.json

功能:
    1. 搜索指定关键词的爆款笔记（按点赞排序）
    2. 分析标题公式、互动数据、话题标签
    3. 提取高互动笔记的特征
    4. 生成选题建议，可一键加入选题池
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# 将项目根目录加入路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.config import get_logger, PROJECT_ROOT as CONF_ROOT, load_topics_json, save_topics_json

logger = get_logger(__name__)

# ── 导入 Spider_XHS ──
from spider_xhs import XHS_Apis

# ── 导入 Cookie 持久化工具 ──
from scripts.xhs_auth_helper import get_pc_auth

# ── 笔记解析统一 schema ──
from core.note_schema import NoteRecord


# ═══════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════

DEFAULT_QUERIES = [
    "情感共鸣",
    "恋爱技巧",
    "分手复合",
    "情绪价值",
    "亲密关系",
]

# 爆款阈值
HOT_LIKES_THRESHOLD = 1000  # 点赞 > 1000 视为爆款


# ═══════════════════════════════════════════════════════════
# 分析函数
# ═══════════════════════════════════════════════════════════

def analyze_title(title: str) -> dict:
    """分析标题使用的公式。"""
    result = {
        "formula": "其他",
        "has_emoji": bool(re.search(r'[\U0001F300-\U0001F9FF\U00002600-\U000027B0]', title)),
        "has_number": bool(re.search(r'\d+', title)),
        "has_question": '?' in title or '？' in title or any(w in title for w in ['吗', '呢', '怎么', '为什么']),
        "length": len(title),
    }

    # 判断标题公式
    if any(w in title for w in ['为什么', '怎么', '如何', '什么', '吗', '？', '?']):
        result["formula"] = "问句式"
    elif any(w in title for w in ['原来', '真相', '本质', '秘密', '底层']):
        result["formula"] = "概念解读式"
    elif any(w in title for w in ['千万别', '不要', '停止', '醒醒', '清醒']):
        result["formula"] = "观点冲击式"
    elif any(w in title for w in ['3个', '5个', '方法', '技巧', '步骤', '教你']):
        result["formula"] = "方法承诺式"

    return result


def extract_tags_from_note(note_detail: dict) -> list:
    """从笔记详情中提取话题标签。"""
    return NoteRecord.from_api_detail(note_detail).tags


def analyze_note(note: dict, api: XHS_Apis) -> dict:
    """分析单篇笔记。优先用搜索结果自带的 note_card，拿不到再调详情接口。"""
    note_url = f"https://www.xiaohongshu.com/explore/{note['id']}"

    # 搜索结果里通常已带 note_card（含 interact_info/title/tag_list），直接用，省一次请求
    note_card = note.get("note_card") or {}
    if not note_card.get("interact_info"):
        # 搜索结果缺 note_card，fallback 到详情接口
        success, msg, detail = api.get_note_info(note_url)
        if success and detail:
            note_card = (detail.get("data") or {}).get("note_card") or detail.get("note_card") or {}

    if not note_card:
        logger.warning(f"笔记无 card 数据: {note_url}")
        return None

    interact = note_card.get("interact_info", {})
    if not isinstance(interact, dict):
        interact = {}
    tag_list = note_card.get("tag_list", [])
    tags = [t.get("name", "") for t in tag_list if isinstance(t, dict) and t.get("name")]

    title = note_card.get("display_title") or note_card.get("title", "") or ""
    likes = _to_int_local(interact.get("liked_count", 0))
    title_analysis = analyze_title(title)

    return {
        "title": title,
        "url": note_url,
        "likes": likes,
        "collects": _to_int_local(interact.get("collected_count", 0)),
        "comments": _to_int_local(interact.get("comment_count", 0)),
        "tags": tags,
        "title_formula": title_analysis["formula"],
        "title_features": title_analysis,
        "is_hot": likes >= HOT_LIKES_THRESHOLD,
    }


def _to_int_local(v) -> int:
    """容错地把字符串数字转 int。"""
    try:
        return int(str(v).replace(",", "").strip() or 0)
    except (ValueError, TypeError):
        return 0


def generate_topic_suggestion(note: dict) -> dict:
    """基于爆款笔记生成选题建议。"""
    return {
        "topic": note["title"],
        "angle": f"借鉴爆款公式「{note['title_formula']}」",
        "formula": note["title_formula"],
        "tags": note["tags"][:5],
        "reference_url": note["url"],
        "reference_likes": note["likes"],
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════

def analyze_competitors(query: str, api: XHS_Apis, max_notes: int = 20) -> list:
    """搜索并分析竞品笔记。"""
    logger.info(f"搜索关键词: {query}")

    success, msg, notes = api.search_some_note(
        query=query,
        require_num=max_notes,
        sort_type_choice=2,  # 最多点赞
        note_type=2,         # 图文笔记
    )

    if not success:
        logger.error(f"搜索失败: {msg}")
        return []

    # 过滤有效笔记
    notes = [n for n in notes if n.get("model_type") == "note"]
    logger.info(f"找到 {len(notes)} 篇笔记，开始分析...")

    results = []
    for i, note in enumerate(notes):
        logger.info(f"[{i+1}/{len(notes)}] 分析笔记: {note.get('id', '')}")
        analysis = analyze_note(note, api)
        if analysis:
            results.append(analysis)

    return results


def print_analysis_report(results: list):
    """打印分析报告。"""
    if not results:
        print("未找到可分析的笔记")
        return

    hot_notes = [r for r in results if r["is_hot"]]
    total_likes = sum(r["likes"] for r in results)
    avg_likes = total_likes / len(results) if results else 0

    print("\n" + "="*60)
    print("📊 竞品分析报告")
    print("="*60)
    print(f"总笔记数: {len(results)}")
    print(f"爆款数 (>1000赞): {len(hot_notes)}")
    print(f"平均点赞: {avg_likes:.0f}")
    print(f"总点赞: {total_likes}")
    print("-"*60)

    # 标题公式统计
    formula_counts = {}
    for r in results:
        f = r["title_formula"]
        formula_counts[f] = formula_counts.get(f, 0) + 1

    print("\n📌 标题公式分布:")
    for formula, count in sorted(formula_counts.items(), key=lambda x: -x[1]):
        print(f"  {formula}: {count} 篇")

    # 爆款笔记详情
    if hot_notes:
        print("\n🔥 爆款笔记 TOP 5:")
        hot_notes.sort(key=lambda x: x["likes"], reverse=True)
        for i, note in enumerate(hot_notes[:5], 1):
            print(f"\n  {i}. {note['title'][:40]}")
            print(f"     点赞: {note['likes']} | 收藏: {note['collects']} | 评论: {note['comments']}")
            print(f"     公式: {note['title_formula']}")
            print(f"     标签: {', '.join(note['tags'])}")
            print(f"     链接: {note['url']}")

    # 高频标签
    all_tags = []
    for r in results:
        all_tags.extend(r["tags"])

    tag_counts = {}
    for t in all_tags:
        tag_counts[t] = tag_counts.get(t, 0) + 1

    print("\n🏷️ 高频标签 TOP 10:")
    for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"  #{tag}: {count} 次")

    print("="*60)


def load_performance_insights() -> dict:
    """从 performance.json 加载历史表现洞察，用于优化竞品搜索策略。"""
    try:
        from core.config import load_performance_json
        performance = load_performance_json()
    except Exception:
        return {}

    notes = performance.get("notes", [])
    if not notes:
        return {}

    # 按公式统计表现
    formula_stats = {}
    for n in notes:
        formula = n.get("title_formula", "未知")
        if formula not in formula_stats:
            formula_stats[formula] = {"count": 0, "total_likes": 0, "grades": []}
        formula_stats[formula]["count"] += 1
        formula_stats[formula]["total_likes"] += n.get("likes", 0)
        formula_stats[formula]["grades"].append(n.get("grade", "C"))

    # 计算每个公式的平均点赞和 C 级率
    insights = {"formula_scores": {}, "best_formulas": [], "avoid_formulas": []}
    for formula, stats in formula_stats.items():
        avg_likes = stats["total_likes"] / stats["count"] if stats["count"] else 0
        c_rate = stats["grades"].count("C") / stats["count"] if stats["count"] else 0
        insights["formula_scores"][formula] = {
            "avg_likes": avg_likes,
            "c_rate": c_rate,
            "count": stats["count"],
        }
        # C 级率 > 50% 的公式要避免
        if c_rate > 0.5 and stats["count"] >= 3:
            insights["avoid_formulas"].append(formula)
        # 平均点赞 > 500 的公式是优质公式
        elif avg_likes > 500:
            insights["best_formulas"].append(formula)

    # 按平均点赞排序
    insights["best_formulas"].sort(
        key=lambda f: insights["formula_scores"][f]["avg_likes"],
        reverse=True,
    )

    return insights


def optimize_queries_by_performance(queries: list, insights: dict) -> list:
    """根据历史表现优化搜索关键词。"""
    if not insights or not insights.get("best_formulas"):
        return queries

    # 如果历史数据显示某些公式表现好，增加相关关键词
    formula_keywords = {
        "问句式": ["为什么", "怎么", "什么", "吗"],
        "概念解读式": ["原来", "真相", "本质", "秘密"],
        "观点冲击式": ["千万别", "不要", "停止", "醒醒"],
        "方法承诺式": ["方法", "技巧", "步骤", "教你"],
    }

    optimized = list(queries)
    for formula in insights["best_formulas"][:2]:  # 只取前 2 个最佳公式
        keywords = formula_keywords.get(formula, [])
        for kw in keywords[:2]:  # 每个公式取前 2 个关键词
            new_query = f"情感 {kw}"
            if new_query not in optimized:
                optimized.append(new_query)
                logger.info(f"根据历史表现，增加搜索关键词: {new_query} (公式: {formula})")

    return optimized


def print_performance_insights(insights: dict):
    """打印历史表现洞察。"""
    if not insights:
        print("\n📊 暂无历史表现数据（performance.json 为空或不存在）")
        return

    print("\n" + "=" * 60)
    print("📈 历史表现洞察（用于优化竞品搜索）")
    print("=" * 60)

    for formula, stats in insights["formula_scores"].items():
        status = "🌟" if formula in insights["best_formulas"] else "⚠️" if formula in insights["avoid_formulas"] else "➖"
        print(f"  {status} {formula}: 均赞 {stats['avg_likes']:.0f} | C级率 {stats['c_rate']*100:.0f}% | 样本 {stats['count']} 篇")

    if insights["best_formulas"]:
        print(f"\n🏆 推荐优先搜索公式: {', '.join(insights['best_formulas'])}")
    if insights["avoid_formulas"]:
        print(f"\n🚫 建议回避公式: {', '.join(insights['avoid_formulas'])}")
    print("=" * 60)


def save_to_topics(results: list, topics_data: dict) -> dict:
    """把爆款分析结果转成选题，去重后追加到 topics.json。

    原 main 调用了同名函数但项目里未定义（历史 bug），在此补齐实现。
    """
    from datetime import datetime

    existing = topics_data.get("topics", [])
    existing_titles = {t.get("topic") for t in existing}
    next_id = max((t.get("id", 0) for t in existing), default=0) + 1

    added = 0
    for r in results:
        title = r.get("title", "").strip()
        if not title or title in existing_titles:
            continue
        existing.append({
            "id": next_id,
            "topic": title,
            "title_formula": r.get("title_formula", ""),
            "target_interaction": "共鸣驱动",
            "angle": f"借鉴爆款公式「{r.get('title_formula', '')}」(原赞{r.get('likes', 0)})",
            "keywords": r.get("tags", [])[:5],
            "pillar": "自我成长",
            "status": "not_started",
            "reference_url": r.get("url", ""),
            "reference_likes": r.get("likes", 0),
            "added_at": datetime.now().isoformat(),
        })
        existing_titles.add(title)
        next_id += 1
        added += 1

    topics_data["topics"] = existing
    logger.info(f"新增 {added} 个爆款选题到选题池（去重后）")
    return topics_data


def main():
    parser = argparse.ArgumentParser(description="竞品分析 — 采集情感赛道爆款笔记")
    parser.add_argument("--query", type=str, default="", help="搜索关键词（默认: 情感共鸣）")
    parser.add_argument("--max", type=int, default=20, help="最多分析笔记数")
    parser.add_argument("--save", action="store_true", help="保存选题到 data/topics.json")
    args = parser.parse_args()

    # 加载历史表现洞察
    insights = load_performance_insights()
    print_performance_insights(insights)

    # 登录（带 Cookie 持久化）
    logger.info("正在登录小红书PC端...")
    auth = get_pc_auth()
    api = XHS_Apis(auth).bootstrap()
    logger.info("登录成功！")

    # 确定搜索关键词（根据历史表现优化）
    queries = [args.query] if args.query else DEFAULT_QUERIES
    queries = optimize_queries_by_performance(queries, insights)

    all_results = []
    for query in queries:
        results = analyze_competitors(query, api, max_notes=args.max)
        all_results.extend(results)

    # 去重
    seen_urls = set()
    unique_results = []
    for r in all_results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            unique_results.append(r)

    # 打印报告
    print_analysis_report(unique_results)

    # 保存选题
    if args.save:
        topics_data = load_topics_json()
        topics_data = save_to_topics(unique_results, topics_data)
        save_topics_json(topics_data)
        logger.info("选题已保存到 data/topics.json")

    # 生成选题建议文件
    suggestions = [generate_topic_suggestion(r) for r in unique_results if r["is_hot"]]
    if suggestions:
        output_file = PROJECT_ROOT / "data" / "competitor_suggestions.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(suggestions, f, ensure_ascii=False, indent=2)
        logger.info(f"选题建议已保存到: {output_file}")


if __name__ == "__main__":
    main()
