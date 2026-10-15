#!/usr/bin/env python3
"""
批量评审脚本 — 读取所有已生成笔记，提取关键信息帮助筛选。
用法: python review_notes.py
"""

import os
import re
from pathlib import Path

from core.config import load_topics_json, PROJECT_ROOT


def extract_note_summary(note_path: str) -> dict:
    """从 note.md 提取关键信息用于评审。"""
    with open(note_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 提取标题候选
    titles = []
    m = re.search(r"【标题候选】\s*(.+?)\s*(?=【|$)", content, re.DOTALL)
    if m:
        for line in m.group(1).strip().split("\n"):
            cleaned = re.sub(r"^\d+[\.、]\s*", "", line.strip())
            cleaned = re.sub(r"^[\s*_`]+|[\s*_`]+$", "", cleaned)
            if cleaned:
                titles.append(cleaned)

    # 提取金句
    golden = ""
    m = re.search(r"【金句】\s*(.+?)\s*(?=【|$)", content, re.DOTALL)
    if m:
        golden = m.group(1).strip().replace("**", "").replace("\n", " ")[:50]

    # 提取正文摘要（前200字）
    body = ""
    m = re.search(r"【正文】\s*\n(.*?)(?=【|$)", content, re.DOTALL)
    if m:
        body = m.group(1).strip()[:200].replace("\n", " ")

    # 提取审核等级
    grade = "?"
    m = re.search(r'"grade"\s*:\s*"([SABC])"', content)
    if m:
        grade = m.group(1)

    # 提取视觉风格
    style = ""
    m = re.search(r"【视觉风格】\s*(.+?)\s*(?=【|$|---)", content, re.DOTALL)
    if m:
        style = re.sub(r'[*\n]+', '', m.group(1)).strip()

    # 检查封面图是否存在
    note_dir = os.path.dirname(note_path)
    has_cover = os.path.exists(os.path.join(note_dir, "cover_ai.png"))
    inner_pages = len([f for f in os.listdir(note_dir) if f.startswith("inner_page_") and f.endswith(".png")])

    return {
        "titles": titles,
        "golden": golden,
        "body_preview": body,
        "grade": grade,
        "style": style,
        "has_cover": has_cover,
        "inner_pages": inner_pages,
        "path": note_path,
    }


def main():
    topics_data = load_topics_json()
    topics = topics_data.get("topics", [])

    generated = [t for t in topics if t.get("status") == "generated" and t.get("output_dir")]

    print(f"\n{'='*60}")
    print(f"📋 共 {len(generated)} 篇已生成笔记")
    print(f"{'='*60}\n")

    notes = []
    for t in generated:
        note_path = os.path.join(t["output_dir"], "note.md")
        if not os.path.exists(note_path):
            continue
        summary = extract_note_summary(note_path)
        summary["topic"] = t["topic"]
        summary["formula"] = t.get("title_formula", "")
        summary["pillar"] = t.get("pillar", "")
        notes.append(summary)

    # 按等级排序: S > A > B > ? > C
    grade_order = {"S": 0, "A": 1, "B": 2, "?": 3, "C": 4}
    notes.sort(key=lambda n: grade_order.get(n["grade"], 3))

    for i, n in enumerate(notes, 1):
        print(f"{'─'*60}")
        print(f"📝 [{i}] {n['topic'][:50]}")
        print(f"   公式: {n['formula']} | 支柱: {n['pillar']} | 风格: {n['style']}")
        print(f"   等级: {n['grade']} | 封面: {'✅' if n['has_cover'] else '❌'} | 内页: {n['inner_pages']}张")
        if n["titles"]:
            print(f"   标题: {n['titles'][0]}")
        if n["golden"]:
            print(f"   金句: {n['golden']}")
        if n["body_preview"]:
            print(f"   开头: {n['body_preview'][:80]}...")
        print()

    print(f"{'='*60}")
    print("💡 建议：选择等级 A/S 的笔记优先发布，B 级可备选。")
    print("   发布后请在 Streamlit 工作台录入真实互动数据（点赞/收藏/评论/曝光）。")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
