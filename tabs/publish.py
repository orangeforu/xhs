"""Tab 6: 一键发布助手。"""

import glob
import os
import re

import streamlit as st

from core.config import load_topics_json, load_performance_json
from core.publish_helpers import (
    extract_title_candidates as _extract_title_candidates,
    extract_body_for_publish as _extract_body_for_publish,
    score_title as _score_title,
    check_compliance as _check_compliance,
)


def render_publish_tab():
    """渲染一键发布助手 Tab。"""
    st.header("🚀 一键发布助手")
    st.caption("选择笔记 → 挑选标题 → 复制正文 → 按顺序上传图片 → 粘贴预设评论")

    topics_data = load_topics_json()
    topics = topics_data.get("topics", [])
    performance = load_performance_json()

    eligible_topics = [t for t in topics if t.get("status") in ("generated", "published")]
    if not eligible_topics:
        st.info("暂无可发布的笔记。先在 Terminal 运行 `python pipeline.py --index N` 生成笔记。")
        return

    options = {f"{t['topic']} ({'待审核' if t.get('status') == 'generated' else '已发布'})": t for t in eligible_topics}
    selected_label = st.selectbox("选择要发布的笔记", list(options.keys()))
    selected_topic = options[selected_label]

    out_dir = selected_topic.get("output_dir", "")
    note_path = os.path.join(out_dir, "note.md") if out_dir else ""

    if not (note_path and os.path.exists(note_path)):
        st.error(f"找不到笔记文件：{note_path}")
        return

    with open(note_path, "r", encoding="utf-8") as f:
        raw_content = f.read()

    titles = _extract_title_candidates(raw_content)
    body = _extract_body_for_publish(raw_content)
    tags = selected_topic.get("tags", [])
    hashtags = " ".join([f"#{tag}" for tag in tags])

    # 发布前 Checklist
    _render_compliance_check(raw_content, selected_topic, out_dir, body)

    st.divider()

    col_left, col_right = st.columns([1, 1])

    with col_left:
        _render_title_selection(titles, performance, selected_topic)

        st.subheader("2️⃣ 发布正文")
        full_text = f"{body}\n\n{hashtags}".strip()
        st.text_area(
            "点击文本框，按 Ctrl+A 全选后复制",
            full_text,
            height=280,
            key="publish_body",
        )

        if "## 预设评论" in raw_content:
            preset = raw_content.split("## 预设评论")[1].strip()
            st.subheader("4️⃣ 预设评论（发布后粘贴到评论区）")
            st.text_area("", preset, height=120, key="publish_preset")

    with col_right:
        _render_image_guide(out_dir)


def _render_compliance_check(raw_content: str, selected_topic: dict, out_dir: str, body: str):
    """渲染发布前合规检查。"""
    st.subheader("✅ 发布前检查")

    tag_match = re.search(r'【话题标签】\s*(.+?)(?=【|$)', raw_content, re.DOTALL)
    parsed_tags = []
    if tag_match:
        for word in tag_match.group(1).strip().split():
            word = word.strip()
            if word.startswith("#") and len(word) > 1:
                parsed_tags.append(word)

    body_for_check = _extract_body_for_publish(raw_content)
    image_count = len(glob.glob(os.path.join(out_dir, "*.png")))

    title_candidates = _extract_title_candidates(raw_content)
    check_title = title_candidates[0] if title_candidates else selected_topic.get("topic", "")

    compliance = _check_compliance(body_for_check, check_title, parsed_tags, image_count)

    if compliance["passed"]:
        st.success("合规检查通过")
    else:
        for issue in compliance["issues"]:
            st.error(f"❌ {issue}")

    if compliance["warnings"]:
        for warn in compliance["warnings"]:
            st.warning(f"⚠️ {warn}")

    checklist_cols = st.columns(4)
    with checklist_cols[0]:
        title_ok = len(check_title) <= 20
        st.markdown(f"{'✅' if title_ok else '❌'} 标题 ≤ 20字（{len(check_title)}字）")
        has_emoji = bool(re.search(r'[\U0001F300-\U0001F9FF\U00002600-\U000027B0]', check_title))
        st.markdown(f"{'✅' if has_emoji else '⚠️'} 标题含 emoji")
    with checklist_cols[1]:
        tag_ok = 3 <= len(parsed_tags) <= 5
        st.markdown(f"{'✅' if tag_ok else '❌'} 标签 3-5个（{len(parsed_tags)}个）")
        has_required_tag = any("不懂就问" in t for t in parsed_tags)
        st.markdown(f"{'✅' if has_required_tag else '⚠️'} 含必带标签")
    with checklist_cols[2]:
        img_ok = 3 <= image_count <= 9
        st.markdown(f"{'✅' if img_ok else '❌'} 图片 3-9张（{image_count}张）")
    with checklist_cols[3]:
        body_ok = 300 <= len(re.sub(r'\s+', '', body_for_check)) <= 1200
        st.markdown(f"{'✅' if body_ok else '⚠️'} 正文字数合理")


def _render_title_selection(titles: list, performance: dict, selected_topic: dict):
    """渲染标题选择区域。"""
    st.subheader("1️⃣ 选择标题")
    if titles:
        title_scores = []
        for t in titles:
            ts = _score_title(t, performance)
            title_scores.append((t, ts))

        title_scores.sort(key=lambda x: x[1]["score"], reverse=True)

        title_options = []
        for t, ts in title_scores:
            level_color = {"S": "🟢", "A": "🔵", "B": "🟡", "C": "🔴"}.get(ts["level"], "⚪")
            label = f"{level_color} [{ts['score']}分] {t}"
            title_options.append(label)

        selected_idx = st.radio("推荐标题（按评分排序）", range(len(title_options)), format_func=lambda i: title_options[i], index=0)
        selected_title = title_scores[selected_idx][0]

        with st.expander("评分详情"):
            for reason in title_scores[selected_idx][1]["reasons"]:
                st.caption(f"- {reason}")
    else:
        selected_title = st.text_input("自定义标题", value=selected_topic.get("topic", ""))


def _render_image_guide(out_dir: str):
    """渲染图片上传顺序指南。"""
    st.subheader("3️⃣ 图片上传顺序")
    image_files = sorted(
        glob.glob(os.path.join(out_dir, "*.png")),
        key=lambda x: (
            0 if "cover" in os.path.basename(x).lower() else 1,
            os.path.basename(x),
        ),
    )
    if not image_files:
        st.warning("该笔记目录下没有找到图片。")
    else:
        for i, img_path in enumerate(image_files, 1):
            fname = os.path.basename(img_path)
            st.caption(f"第{i}张 · {fname}")
            st.image(img_path, use_container_width=True)
            if i == 1:
                st.info("☝️ 第一张是封面，上传时记得放在最前面")
            st.divider()
