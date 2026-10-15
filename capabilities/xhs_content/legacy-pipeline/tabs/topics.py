"""Tab 2: 选题池。"""

import streamlit as st

from core.config import load_topics_json


def render_topics_tab():
    """渲染选题池 Tab。"""
    st.header("📚 本月选题池")

    topics_data = load_topics_json()
    topics = topics_data.get("topics", [])

    # 热点选题生成
    _render_trending_section()

    for i, t in enumerate(topics, 1):
        _render_topic_row(i, t)


def _render_trending_section():
    """渲染热点选题生成区域。"""
    with st.expander("🔥 热点感知 + 一键生成选题", expanded=False):
        st.caption("自动抓取当前热点关键词，融合情感角度生成选题。")

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("📡 抓取当前热点", key="fetch_trending"):
                with st.spinner("正在抓取热点..."):
                    try:
                        from core.trend_detector import get_trending_keywords
                        keywords = get_trending_keywords()
                        if keywords:
                            st.session_state["trending_keywords"] = keywords
                            st.success(f"抓取到 {len(keywords)} 个情感相关热点")
                        else:
                            st.warning("未抓取到情感相关热点，请稍后重试")
                    except Exception as e:
                        st.error(f"抓取失败: {e}")

        if "trending_keywords" in st.session_state:
            keywords = st.session_state["trending_keywords"]
            st.markdown("**当前热点关键词**：" + " | ".join(f"`{kw}`" for kw in keywords))

            with col2:
                count = st.number_input("生成数量", min_value=5, max_value=50, value=10, step=5, key="trending_count")
                if st.button("🚀 生成热点选题", key="gen_trending_topics"):
                    with st.spinner(f"正在融合 {len(keywords)} 个热点生成 {count} 个选题..."):
                        try:
                            from generate_topics import generate_topics, save_topics
                            new_topics = generate_topics(total=count, trending_keywords=keywords)
                            if new_topics:
                                save_topics(new_topics, append=True)
                                st.success(f"成功生成 {len(new_topics)} 个热点选题！")
                                st.rerun()
                            else:
                                st.error("选题生成失败")
                        except Exception as e:
                            st.error(f"生成失败: {e}")


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
