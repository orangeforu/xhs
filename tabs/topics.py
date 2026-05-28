"""Tab 2: 选题池。"""

import streamlit as st

from core.config import load_topics_json


def render_topics_tab():
    """渲染选题池 Tab。"""
    st.header("📚 本月选题池")

    topics_data = load_topics_json()
    topics = topics_data.get("topics", [])

    for i, t in enumerate(topics, 1):
        _render_topic_row(i, t)


def _render_topic_row(i: int, t: dict):
    """渲染单个选题行。"""
    status = t.get("status", "not_started")
    status_map = {
        "not_started": ("未开始", "blue"),
        "generated": ("待审核", "orange"),
        "published": ("已发布", "green"),
        "archived": ("已归档", "gray"),
    }
    label, color = status_map.get(status, (status, "blue"))

    cols = st.columns([0.5, 3, 1, 1, 1])
    with cols[0]:
        st.write(f"**{i}**")
    with cols[1]:
        st.write(t["topic"])
    with cols[2]:
        st.caption(t.get("title_formula", ""))
    with cols[3]:
        st.caption(t.get("target_interaction", ""))
    with cols[4]:
        if color == "green":
            st.success(label)
        elif color == "orange":
            st.warning(label)
        elif color == "gray":
            st.caption(label)
        else:
            st.info(label)

    # 展开显示详细信息
    angle = t.get("angle", "")
    story = t.get("story_prototype", "")
    controversy = t.get("controversy_anchor", "")
    if angle or story or controversy:
        details = []
        if angle:
            details.append(f"**角度**: {angle}")
        if story:
            details.append(f"**故事原型**: {story}")
        if controversy:
            details.append(f"**争议锚点**: {controversy}")
        st.caption(" | ".join(details))
