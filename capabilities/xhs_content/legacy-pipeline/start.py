#!/usr/bin/env python3
"""小红书AI创作系统 - 交互式入口"""

import subprocess
import sys

from core.config import init, load_topics_json
from core.topic_selector import recommend
from pipeline import generate as pipeline_generate, batch_generate as pipeline_batch_generate


def pause():
    input("\n按回车返回主菜单...")


def show_topics():
    """显示选题池"""
    data = load_topics_json()
    topics = data.get("topics", [])
    print("\n" + "=" * 60)
    print("  选题池")
    print("=" * 60)
    for i, t in enumerate(topics):
        status = t.get("status", "not_started")
        icon = {"published": "[已发布]", "generated": "[待审核]"}.get(status, "[未开始]")
        formula = t.get("title_formula", "")
        interaction = t.get("target_interaction", "")
        print(f"  [{i:>2}] {icon} {t['topic']}")
        print(f"       {formula} | {interaction}")
    print("=" * 60)
    return topics


def generate_note(topics):
    """生成笔记"""
    print("\n选择选题方式：")
    print("  [1] 按编号选择")
    print("  [2] 按关键词搜索")
    print("  [3] 智能推荐（AI 选出最优选题）")
    print("  [0] 返回")
    choice = input("\n请选择: ").strip()

    if choice == "0":
        return
    elif choice == "3":
        print("\nAI 正在分析选题池...\n")
        recs = recommend(count=5)
        if not recs:
            print("没有可用的选题")
            return
        print("推荐选题（按综合评分排序）：")
        for i, rec in enumerate(recs):
            t = rec["topic"]
            score = rec["scores"]["total"]
            reasons = " | ".join(rec["reasons"])
            print(f"  [{i}] {t['topic']}")
            print(f"      评分: {score:.2f} | {t['title_formula']} | {t['pillar']}")
            print(f"      推荐理由: {reasons}")
        print()
        idx = input("选择编号（或按回车让 AI 自动选最优）: ").strip()
        if idx == "":
            # 自动选第一个（最高分）
            print(f"\nAI 自动选择: {recs[0]['topic']['topic']}\n")
            pipeline_generate(smart=True)
        elif idx.isdigit() and 0 <= int(idx) < len(recs):
            selected_topic = recs[int(idx)]["topic"]
            print(f"\n正在生成笔记: {selected_topic['topic']}\n")
            pipeline_generate(topic=selected_topic["topic"])
        else:
            print("无效选择")
            return
    elif choice == "1":
        idx = input(f"输入选题编号 (0-{len(topics)-1}): ").strip()
        if not idx.isdigit() or int(idx) < 0 or int(idx) >= len(topics):
            print("无效编号")
            return
        selected_idx = int(idx)
        print(f"\n正在生成笔记...\n")
        pipeline_generate(index=selected_idx)
    elif choice == "2":
        keyword = input("输入关键词: ").strip()
        matched = [t for t in topics if keyword in t["topic"]]
        if not matched:
            print(f"未找到包含「{keyword}」的选题")
            return
        print("\n匹配的选题：")
        for i, t in enumerate(matched):
            idx = topics.index(t)
            print(f"  [{idx}] {t['topic']}")
        idx = input("\n输入编号: ").strip()
        if not idx.isdigit():
            print("无效编号")
            return
        selected_idx = int(idx)
        print(f"\n正在生成笔记...\n")
        pipeline_generate(index=selected_idx)
    else:
        print("无效选择")
        return

    print("\n生成完成！")


def batch_generate():
    """批量生成"""
    print("\n批量生成模式：")
    print("  [1] 智能排序（AI 推荐最优选题顺序）")
    print("  [2] 按顺序生成（选题池默认顺序）")
    mode = input("选择模式（默认智能排序）: ").strip()
    smart = mode != "2"

    max_count = input("生成数量（留空=全部）: ").strip()
    max_count_int = int(max_count) if max_count.isdigit() else None
    print(f"\n开始{'智能' if smart else '顺序'}批量生成...\n")
    pipeline_batch_generate(max_count=max_count_int, smart=smart)


def open_dashboard():
    """打开审核工作台"""
    print("\n正在启动 Streamlit 工作台...")
    print("浏览器将自动打开 http://localhost:8501")
    print("按 Ctrl+C 退出\n")
    subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"])


def show_smart_recommendations():
    """显示智能推荐选题"""
    print("\nAI 正在分析选题池和历史数据...\n")
    recs = recommend(count=5)
    if not recs:
        print("没有可用的选题")
        return

    print("=" * 60)
    print("  智能推荐 Top 5")
    print("=" * 60)
    for i, rec in enumerate(recs):
        t = rec["topic"]
        score = rec["scores"]["total"]
        reasons = " | ".join(rec["reasons"])
        print(f"\n  [{i+1}] {t['topic']}")
        print(f"      综合评分: {score:.2f}")
        print(f"      公式: {t['title_formula']} | 支柱: {t['pillar']}")
        print(f"      互动目标: {t['target_interaction']}")
        print(f"      推荐理由: {reasons}")
        print(f"      角度: {t.get('angle', '无')}")

    print("\n" + "=" * 60)
    print("  使用「生成笔记」→「智能推荐」可直接用推荐选题生成")
    print("=" * 60)


def main():
    init()

    while True:
        print()
        print("=" * 60)
        print("  小红书AI创作系统")
        print("=" * 60)
        print("  [1] 查看选题池")
        print("  [2] 生成笔记")
        print("  [3] 批量生成")
        print("  [4] 审核工作台")
        print("  [5] 智能推荐选题")
        print("  [0] 退出")
        print("=" * 60)

        try:
            choice = input("\n请选择: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if choice == "0":
            print("再见！")
            break
        elif choice == "1":
            show_topics()
            pause()
        elif choice == "2":
            topics = show_topics()
            generate_note(topics)
            pause()
        elif choice == "3":
            batch_generate()
            pause()
        elif choice == "4":
            open_dashboard()
        elif choice == "5":
            show_smart_recommendations()
            pause()
        else:
            print("无效选择，请重新输入")


if __name__ == "__main__":
    main()
