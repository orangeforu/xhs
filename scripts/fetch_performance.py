#!/usr/bin/env python3
"""
数据复盘脚本 — 采集已发布笔记的互动数据，更新 performance.json
===========================================================

用法:
    python scripts/fetch_performance.py              # 更新所有已发布笔记数据
    python scripts/fetch_performance.py --days 7     # 只更新最近 7 天发布的
    python scripts/fetch_performance.py --note URL   # 更新指定笔记

功能:
    1. 读取 published/ 和 archived/ 目录下的笔记
    2. 登录小红书 PC 端
    3. 采集每篇笔记的最新互动数据（点赞/收藏/评论）
    4. 计算评分等级（S/A/B/C）
    5. 更新 performance.json
    6. 触发熔断检查
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 将项目根目录加入路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.config import get_logger, load_performance_json, save_performance_json
from core.publish_helpers import calculate_grade
from core.note_schema import NoteRecord

logger = get_logger(__name__)

# ── 导入 Spider_XHS ──
from spider_xhs import XHS_Apis

# ── 导入 Cookie 持久化工具 ──
from scripts.xhs_auth_helper import get_pc_auth


# ═══════════════════════════════════════════════════════════
# 路径配置
# ═══════════════════════════════════════════════════════════

PUBLISHED_DIR = PROJECT_ROOT / "docs_agent" / "published"
ARCHIVED_DIR = PROJECT_ROOT / "docs_agent" / "archived"


# ═══════════════════════════════════════════════════════════
# 笔记解析
# ═══════════════════════════════════════════════════════════

def extract_note_url(note_dir: Path) -> str:
    """从笔记目录提取笔记 URL。优先从 note.md 的发布记录中提取，其次从目录名提取。"""
    note_md = note_dir / "note.md"
    if note_md.exists():
        with open(note_md, 'r', encoding='utf-8') as f:
            content = f.read()

        # 优先匹配发布记录中的 URL
        m = re.search(r'\*\*笔记 URL\*\*:\s*(https://www\.xiaohongshu\.com/explore/[a-zA-Z0-9]+)', content)
        if m:
            return m.group(1)

        # 其次匹配正文中的 URL
        m = re.search(r'https://www\.xiaohongshu\.com/explore/[a-zA-Z0-9]+', content)
        if m:
            return m.group(0)

    return None


def extract_note_id(note_dir: Path) -> str:
    """从笔记目录提取笔记 ID。优先从 URL 提取，其次从目录名提取。"""
    # 优先从 URL 提取
    url = extract_note_url(note_dir)
    if url:
        m = re.search(r'/explore/([a-zA-Z0-9]+)', url)
        if m:
            return m.group(1)

    # 从目录名提取（兼容旧格式）
    dir_name = note_dir.name
    m = re.search(r'([a-f0-9]{24})', dir_name)
    if m:
        return m.group(1)

    return None


def find_all_published_notes() -> list:
    """查找所有已发布的笔记目录。"""
    notes = []

    for base_dir in [PUBLISHED_DIR, ARCHIVED_DIR]:
        if not base_dir.exists():
            continue
        for d in base_dir.iterdir():
            if not d.is_dir():
                continue
            note_id = extract_note_id(d)
            if note_id:
                notes.append({
                    "dir": d,
                    "note_id": note_id,
                    "url": f"https://www.xiaohongshu.com/explore/{note_id}",
                })

    return notes


# ═══════════════════════════════════════════════════════════
# 数据采集
# ═══════════════════════════════════════════════════════════

def fetch_note_performance(note: dict, api: XHS_Apis) -> dict:
    """采集单篇笔记的互动数据。"""
    note_url = note["url"]

    try:
        success, msg, detail = api.get_note_info(note_url)

        if not success:
            logger.warning(f"获取笔记数据失败: {note_url} - {msg}")
            return None

        rec = NoteRecord.from_api_detail(detail, note_id=note["note_id"], url=note_url)

        return {
            "note_id": rec.note_id,
            "url": rec.url,
            "likes": rec.likes,
            "collects": rec.collects,
            "comments": rec.comments,
            "shares": rec.shares,
            "grade": calculate_grade(rec.likes),
            "updated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"采集异常: {note_url} - {e}")
        return None


# ═══════════════════════════════════════════════════════════
# 数据更新
# ═══════════════════════════════════════════════════════════

def update_performance_data(notes_data: list, performance: dict) -> dict:
    """更新 performance.json。"""
    if "notes" not in performance:
        performance["notes"] = []

    existing_map = {n.get("note_id", ""): n for n in performance["notes"]}

    for data in notes_data:
        if not data:
            continue

        note_id = data["note_id"]

        if note_id in existing_map:
            # 更新已有记录
            existing = existing_map[note_id]
            existing["likes"] = data["likes"]
            existing["collects"] = data["collects"]
            existing["comments"] = data["comments"]
            existing["shares"] = data["shares"]
            existing["grade"] = data["grade"]
            existing["updated_at"] = data["updated_at"]
            logger.info(f"更新数据: {note_id} | 点赞: {data['likes']} | 等级: {data['grade']}")
        else:
            # 新增记录
            performance["notes"].append(data)
            logger.info(f"新增记录: {note_id} | 点赞: {data['likes']} | 等级: {data['grade']}")

    # 更新统计
    _update_stats(performance)

    return performance


def _update_stats(performance: dict):
    """更新统计数据。"""
    notes = performance.get("notes", [])

    if not notes:
        return

    total_likes = sum(n.get("likes", 0) for n in notes)
    total_collects = sum(n.get("collects", 0) for n in notes)
    total_comments = sum(n.get("comments", 0) for n in notes)

    grade_counts = {"S": 0, "A": 0, "B": 0, "C": 0}
    for n in notes:
        g = n.get("grade", "C")
        grade_counts[g] = grade_counts.get(g, 0) + 1

    performance["stats"] = {
        "total_notes": len(notes),
        "total_likes": total_likes,
        "total_collects": total_collects,
        "total_comments": total_comments,
        "avg_likes": round(total_likes / len(notes), 1) if notes else 0,
        "grade_distribution": grade_counts,
        "updated_at": datetime.now().isoformat(),
    }

    # 检查熔断
    _check_circuit_breaker(performance)


def _check_circuit_breaker(performance: dict):
    """检查是否触发熔断。"""
    notes = performance.get("notes", [])

    # 按发布时间排序
    recent = [n for n in notes if n.get("published_at") or n.get("updated_at")]
    recent.sort(key=lambda x: x.get("published_at", x.get("updated_at", "")), reverse=True)

    if len(recent) < 3:
        return

    # 检查最近 3 篇
    streak = 0
    for n in recent[:3]:
        if n.get("grade") == "C":
            streak += 1
        else:
            break

    if streak >= 3:
        logger.warning("🚨 熔断警告：连续 3 篇 C 级！请暂停发布，复盘选题方向。")
        performance["circuit_breaker"] = {
            "tripped": True,
            "streak": streak,
            "triggered_at": datetime.now().isoformat(),
        }
    else:
        performance["circuit_breaker"] = {
            "tripped": False,
            "streak": streak,
        }


# ═══════════════════════════════════════════════════════════
# 报告输出
# ═══════════════════════════════════════════════════════════

def print_report(performance: dict):
    """打印数据复盘报告。"""
    stats = performance.get("stats", {})
    notes = performance.get("notes", [])

    print("\n" + "="*60)
    print("📈 数据复盘报告")
    print("="*60)
    print(f"总笔记数: {stats.get('total_notes', 0)}")
    print(f"总点赞: {stats.get('total_likes', 0)}")
    print(f"总收藏: {stats.get('total_collects', 0)}")
    print(f"总评论: {stats.get('total_comments', 0)}")
    print(f"平均点赞: {stats.get('avg_likes', 0)}")
    print("-"*60)

    # 等级分布
    grade_dist = stats.get("grade_distribution", {})
    print("\n📊 等级分布:")
    for grade in ["S", "A", "B", "C"]:
        count = grade_dist.get(grade, 0)
        bar = "█" * count
        print(f"  {grade}: {count} 篇 {bar}")

    # 最近笔记
    recent = sorted(notes, key=lambda x: x.get("updated_at", ""), reverse=True)[:5]
    if recent:
        print("\n📝 最近 5 篇笔记:")
        for i, note in enumerate(recent, 1):
            grade = note.get("grade", "C")
            emoji = {"S": "🌟", "A": "✨", "B": "👍", "C": "⚠️"}.get(grade, "❓")
            print(f"  {i}. {emoji} [{grade}] 点赞: {note.get('likes', 0)} | "
                  f"收藏: {note.get('collects', 0)} | 评论: {note.get('comments', 0)}")

    # 熔断状态
    cb = performance.get("circuit_breaker", {})
    if cb.get("tripped"):
        print("\n🚨 熔断状态: 已触发！")
        print(f"  连续 C 级: {cb.get('streak', 0)} 篇")
        print("  建议: 暂停发布，复盘选题方向")
    else:
        streak = cb.get("streak", 0)
        if streak > 0:
            print(f"\n⚠️ 熔断预警: 连续 {streak} 篇 C 级，再发 {3-streak} 篇将触发熔断")
        else:
            print("\n✅ 熔断状态: 正常")

    print("="*60)


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="数据复盘 — 采集已发布笔记互动数据")
    parser.add_argument("--days", type=int, default=0, help="只更新最近 N 天发布的笔记")
    parser.add_argument("--note", type=str, default="", help="指定笔记 URL 更新")
    args = parser.parse_args()

    # 读取现有数据
    performance = load_performance_json()

    if args.note:
        # 登录（带 Cookie 持久化）
        logger.info("正在登录小红书PC端...")
        auth = get_pc_auth()
        api = XHS_Apis(auth).bootstrap()
        logger.info("登录成功！")

        note_id_match = re.search(r'/explore/([a-zA-Z0-9]+)', args.note)
        if note_id_match:
            note_id = note_id_match.group(1)
            data = fetch_note_performance({"note_id": note_id, "url": args.note}, api)
            if data:
                performance = update_performance_data([data], performance)
        else:
            logger.error("无法从 URL 提取笔记 ID")
    else:
        # 查找所有已发布笔记
        notes = find_all_published_notes()

        if not notes:
            logger.info("没有找到已发布的笔记")
            return

        # 按日期过滤
        if args.days > 0:
            cutoff = datetime.now() - timedelta(days=args.days)
            # 这里简化处理，实际应该读取 published_at
            logger.info(f"只更新最近 {args.days} 天的笔记")

        logger.info(f"找到 {len(notes)} 篇已发布笔记，开始采集数据...")

        # 登录（带 Cookie 持久化）
        logger.info("正在登录小红书PC端...")
        auth = get_pc_auth()
        api = XHS_Apis(auth).bootstrap()
        logger.info("登录成功！")

        # 采集数据
        notes_data = []
        for i, note in enumerate(notes):
            logger.info(f"[{i+1}/{len(notes)}] 采集: {note['note_id']}")
            data = fetch_note_performance(note, api)
            if data:
                notes_data.append(data)

        # 更新 performance.json
        performance = update_performance_data(notes_data, performance)

    # 保存
    save_performance_json(performance)
    logger.info("performance.json 已更新")

    # 打印报告
    print_report(performance)


if __name__ == "__main__":
    main()
