"""数据同步一键脚本 — 串起采集闭环的三个动作。

把"登 PC 端 → 采集已发布笔记互动 → 竞品爆款分析灌进选题池"三步串成一条命令，
让 performance.json 有真实数据、选题池有基于爆款的选题。

用法:
    python scripts/data_sync.py              # 采集 + 竞品分析（默认）
    python scripts/data_sync.py --skip-fetch # 跳过已发布数据采集，只做竞品分析
    python scripts/data_sync.py --skip-comp  # 跳过竞品分析，只采集已发布数据
    python scripts/data_sync.py --query "独居女生"  # 指定竞品搜索词

前置：首次运行会弹二维码，用小红书 APP 扫码登 PC 端。后续复用 Cookie。
"""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Windows GBK 终端打不出 emoji/特殊字符，强制 UTF-8 输出
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from core.config import get_logger

logger = get_logger("data_sync")


def _login_pc():
    """登录 PC 端（带 Cookie 持久化）。后续脚本复用同一 Cookie。"""
    from scripts.xhs_auth_helper import get_pc_auth

    logger.info("=" * 50)
    logger.info("第 1 步：登录小红书 PC 端（采集数据用）")
    logger.info("=" * 50)
    auth = get_pc_auth()
    if not auth:
        raise RuntimeError("PC 端登录失败，无法继续")
    logger.info("✅ PC 端登录成功，Cookie 已复用/保存")
    return auth


def _fetch_performance():
    """采集已发布笔记的真实互动数据，更新 performance.json。"""
    logger.info("=" * 50)
    logger.info("第 2 步：采集已发布笔记互动数据")
    logger.info("=" * 50)
    from scripts.fetch_performance import (
        find_all_published_notes,
        fetch_note_performance,
        update_performance_data,
        load_performance_json,
        save_performance_json,
        print_report,
    )
    from spider_xhs import XHS_Apis

    auth = _login_pc()
    api = XHS_Apis(auth).bootstrap()

    notes = find_all_published_notes()
    if not notes:
        logger.info("没有找到已发布的笔记（docs_agent/published/ 和 archived/ 为空）")
        logger.info("→ 跳过数据采集。先发布几篇笔记，隔 24-48 小时后再跑本脚本。")
        return 0

    logger.info(f"找到 {len(notes)} 篇已发布笔记，开始采集真实互动数据...")

    performance = load_performance_json()
    notes_data = []
    for i, note in enumerate(notes, 1):
        logger.info(f"[{i}/{len(notes)}] 采集: {note.get('note_id')}")
        data = fetch_note_performance(note, api)
        if data:
            notes_data.append(data)

    performance = update_performance_data(notes_data, performance)
    save_performance_json(performance)
    logger.info("✅ performance.json 已更新真实数据")
    print_report(performance)
    return len(notes_data)


def _competitor_analysis(query: str = "", max_notes: int = 20, save: bool = True):
    """竞品爆款分析，分析后灌进选题池。"""
    logger.info("=" * 50)
    logger.info("第 3 步：竞品爆款分析 + 灌进选题池")
    logger.info("=" * 50)
    from scripts.competitor_analysis import (
        analyze_competitors,
        load_performance_insights,
        print_performance_insights,
        print_analysis_report,
        generate_topic_suggestion,
        optimize_queries_by_performance,
        DEFAULT_QUERIES,
    )
    from core.config import load_topics_json, save_topics_json
    from spider_xhs import XHS_Apis
    from scripts.xhs_auth_helper import get_pc_auth
    import json as _json
    from datetime import datetime

    insights = load_performance_insights()
    print_performance_insights(insights)

    auth = get_pc_auth()
    api = XHS_Apis(auth).bootstrap()

    queries = [query] if query else DEFAULT_QUERIES
    queries = optimize_queries_by_performance(queries, insights)
    logger.info(f"搜索关键词: {queries}")

    all_results = []
    for q in queries:
        results = analyze_competitors(q, api, max_notes=max_notes)
        all_results.extend(results)

    # 去重
    seen_urls = set()
    unique_results = []
    for r in all_results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            unique_results.append(r)

    print_analysis_report(unique_results)
    logger.info(f"共采集到 {len(unique_results)} 篇竞品笔记")

    if save and unique_results:
        # competitor_analysis 的 save_to_topics 函数实际不存在（原项目 bug），
        # 这里自己把爆款转成选题格式追加到 topics.json
        topics_data = load_topics_json()
        existing_topics = topics_data.get("topics", [])
        existing_ids = {t.get("topic") for t in existing_topics}
        next_id = max((t.get("id", 0) for t in existing_topics), default=0) + 1

        added = 0
        for r in unique_results:
            topic_title = r["title"]
            if topic_title in existing_ids:
                continue  # 去重
            existing_topics.append({
                "id": next_id,
                "topic": topic_title,
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
            existing_ids.add(topic_title)
            next_id += 1
            added += 1

        topics_data["topics"] = existing_topics
        save_topics_json(topics_data)
        logger.info(f"✅ 新增 {added} 个爆款选题到 data/topics.json（去重后）")

        suggestions = [generate_topic_suggestion(r) for r in unique_results if r.get("is_hot")]
        if suggestions:
            output_file = PROJECT_ROOT / "data" / "competitor_suggestions.json"
            with open(output_file, "w", encoding="utf-8") as f:
                _json.dump(suggestions, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ 选题建议已保存到 {output_file}")

    return len(unique_results)


def main():
    parser = argparse.ArgumentParser(description="数据同步 — 一键采集 + 竞品反哺选题")
    parser.add_argument("--skip-fetch", action="store_true", help="跳过已发布笔记数据采集")
    parser.add_argument("--skip-comp", action="store_true", help="跳过竞品分析")
    parser.add_argument("--query", type=str, default="", help="竞品搜索关键词（默认用内置情感赛道词）")
    parser.add_argument("--max", type=int, default=20, help="竞品分析最多笔记数（默认20）")
    args = parser.parse_args()

    logger.info("🚀 开始数据同步：采集互动数据 + 竞品爆款反哺选题池")
    logger.info("")

    fetched = 0
    analyzed = 0

    if not args.skip_fetch:
        fetched = _fetch_performance()
        logger.info("")

    if not args.skip_comp:
        analyzed = _competitor_analysis(query=args.query, max_notes=args.max, save=True)
        logger.info("")

    logger.info("=" * 50)
    logger.info("🎉 数据同步完成！")
    logger.info(f"  • 采集互动数据: {fetched} 篇已发布笔记")
    logger.info(f"  • 竞品爆款分析: {analyzed} 篇")
    logger.info("=" * 50)
    logger.info("")
    logger.info("下一步：去 Streamlit「📚选题池」看新灌进来的爆款选题，点「生成笔记」即可。")
    logger.info("发布后隔 24-48 小时再跑本脚本，让数据持续反哺。")


if __name__ == "__main__":
    main()
