#!/usr/bin/env python3
"""小红书AI创作系统 - 交互式入口"""

import subprocess
import sys

from core.config import init, load_topics_json


def show_topics():
    """显示选题池"""
    data = load_topics_json()
    topics = data.get("topics", [])
    print("\n" + "=" * 60)
    print("  选题池")
    print("=" * 60)
    for i, t in enumerate(topics):
        status = t.get("status", "not_started")
        icon = {"published": "✅", "generated": "📝"}.get(status, "⬜")
        formula = t.get("title_formula", "")
        interaction = t.get("target_interaction", "")
        print(f"  [{i:>2}] {icon} {t['topic']}")
        print(f"       {formula} | {interaction} | {status}")
    print("=" * 60)
    return topics


def generate_note(topics):
    """生成笔记"""
    print("\n选择选题方式：")
    print("  [1] 按编号选择")
    print("  [2] 按关键词搜索")
    print("  [0] 返回")
    choice = input("\n请选择: ").strip()

    if choice == "0":
        return
    elif choice == "1":
        idx = input(f"输入选题编号 (0-{len(topics)-1}): ").strip()
        if not idx.isdigit() or int(idx) < 0 or int(idx) >= len(topics):
            print("无效编号")
            return
        cmd = f"{sys.executable} pipeline.py --index {idx}"
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
        cmd = f"{sys.executable} pipeline.py --index {idx}"
    else:
        print("无效选择")
        return

    print(f"\n正在生成笔记...\n")
    subprocess.run(cmd, shell=True)
    print("\n生成完成！运行「审核发布」查看结果。")


def batch_generate():
    """批量生成"""
    max_count = input("生成数量（留空=全部）: ").strip()
    cmd = f"{sys.executable} pipeline.py --batch"
    if max_count.isdigit():
        cmd += f" --max {max_count}"
    print(f"\n开始批量生成...\n")
    subprocess.run(cmd, shell=True)


def open_dashboard():
    """打开审核工作台"""
    print("\n正在启动 Streamlit 工作台...")
    print("浏览器将自动打开 http://localhost:8501")
    print("按 Ctrl+C 退出\n")
    subprocess.run(f"{sys.executable} -m streamlit run app.py", shell=True)


def main():
    init()

    while True:
        print("\n" + "=" * 60)
        print("  小红书AI创作系统")
        print("=" * 60)
        print("  [1] 查看选题池")
        print("  [2] 生成笔记")
        print("  [3] 批量生成")
        print("  [4] 审核工作台")
        print("  [0] 退出")
        print("=" * 60)

        choice = input("\n请选择: ").strip()

        if choice == "0":
            print("再见！")
            break
        elif choice == "1":
            show_topics()
        elif choice == "2":
            topics = show_topics()
            generate_note(topics)
        elif choice == "3":
            batch_generate()
        elif choice == "4":
            open_dashboard()
        else:
            print("无效选择，请重新输入")


if __name__ == "__main__":
    main()
