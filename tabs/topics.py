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

    # 筛选
    filtered = _render_filter_section(topics)

    # 批量操作
    _render_batch_actions(filtered)

    # 选题列表
    st.caption(f"共 {len(filtered)} / {len(topics)} 个选题")
    for i, t in enumerate(filtered, 1):
        _render_topic_row(i, t, topics_data)


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


def _render_filter_section(topics: list) -> list:
    """筛选区：状态 / 支柱 / 标题公式 / 关键词。返回过滤后的列表。"""
    with st.expander("🔍 筛选选题", expanded=False):
        c1, c2, c3, c4 = st.columns(4)

        status_options = ["全部", "未开始", "待审核", "已发布", "已归档"]
        status_map = {"未开始": "not_started", "待审核": "generated", "已发布": "published", "已归档": "archived"}

        with c1:
            sel_status = st.selectbox("状态", status_options, key="filter_status")
        with c2:
            pillars = ["全部"] + sorted({t.get("pillar", "") for t in topics if t.get("pillar")})
            sel_pillar = st.selectbox("支柱", pillars, key="filter_pillar")
        with c3:
            formulas = ["全部"] + sorted({t.get("title_formula", "") for t in topics if t.get("title_formula")})
            sel_formula = st.selectbox("标题公式", formulas, key="filter_formula")
        with c4:
            keyword = st.text_input("关键词", "", key="filter_keyword", placeholder="选题标题子串")

    filtered = topics
    if sel_status != "全部":
        filtered = [t for t in filtered if t.get("status") == status_map[sel_status]]
    if sel_pillar != "全部":
        filtered = [t for t in filtered if t.get("pillar") == sel_pillar]
    if sel_formula != "全部":
        filtered = [t for t in filtered if t.get("title_formula") == sel_formula]
    if keyword.strip():
        kw = keyword.strip()
        filtered = [t for t in filtered if kw in t.get("topic", "")]

    return filtered


def _render_batch_actions(topics: list):
    """批量操作区：批量生成 + 智能推荐并生成。"""
    from tabs._generate_helper import (
        batch_generate_with_progress,
        check_api_key,
        generate_with_progress,
        render_result,
    )

    not_started = [t for t in topics if t.get("status", "not_started") == "not_started"]

    with st.container(border=True):
        st.subheader("⚙️ 批量生成")
        if not not_started:
            st.caption("当前筛选下没有「未开始」的选题，无法批量生成。调整筛选或先去生成新选题。")
            return

        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            max_n = st.number_input(
                "生成篇数", min_value=1, max_value=20, value=min(3, len(not_started)), step=1, key="batch_count"
            )
        with c2:
            if st.button("📦 批量生成", key="batch_generate_btn", type="primary"):
                if check_api_key():
                    with st.status(f"正在批量生成 {max_n} 篇…", expanded=True):
                        progress = st.empty()
                        success, abandoned, failed, logs = batch_generate_with_progress(
                            max_count=int(max_n), smart=False, status_container=progress
                        )
                    st.info(f"批量完成：✅成功 {success} | ⚠️放弃 {abandoned} | ❌失败 {failed}")
                    if logs:
                        with st.expander("📜 生成日志", expanded=False):
                            st.code("\n".join(logs), language="text")
                    st.rerun()
        with c3:
            if st.button("🧠 智能推荐并生成", key="smart_generate_btn", help="AI 选出最优选题并生成"):
                if check_api_key():
                    with st.status("AI 正在挑选最优选题并生成…", expanded=True):
                        progress = st.empty()
                        result, logs = generate_with_progress(smart=True, status_container=progress)
                    render_result(result, logs)
                    st.rerun()


def _render_topic_row(i: int, t: dict, topics_data: dict):
    """渲染单个选题行。"""
    from tabs._generate_helper import (
        check_api_key,
        generate_with_progress,
        render_result,
    )

    status = t.get("status", "not_started")
    status_map = {
        "not_started": ("未开始", "blue"),
        "generated": ("待审核", "orange"),
        "published": ("已发布", "green"),
        "archived": ("已归档", "gray"),
        "approved": ("待发布", "orange"),
    }
    label, color = status_map.get(status, (status, "blue"))

    cols = st.columns([0.4, 4, 1, 1, 1.2])
    with cols[0]:
        st.write(f"**{i}**")
    with cols[1]:
        st.write(t["topic"])
        angle = t.get("angle", "")
        if angle:
            st.caption(f"角度：{angle}")
    with cols[2]:
        st.caption(t.get("title_formula", ""))
    with cols[3]:
        st.caption(t.get("pillar", ""))
    with cols[4]:
        if color == "green":
            st.success(label)
        elif color == "orange":
            st.warning(label)
        elif color == "gray":
            st.caption(label)
        else:
            st.info(label)

    # 操作按钮：未开始可生成，待审核可重新生成
    if status in ("not_started", "generated"):
        oc1, oc2 = st.columns([1, 5])
        with oc1:
            btn_label = "✍️ 生成笔记" if status == "not_started" else "🔄 重新生成"
            if st.button(btn_label, key=f"gen_{t['id']}_{i}", type="primary" if status == "not_started" else "secondary"):
                if check_api_key():
                    with st.status(f"正在生成「{t['topic']}」…", expanded=True):
                        progress = st.empty()
                        result, logs = generate_with_progress(topic=t["topic"], status_container=progress)
                    render_result(result, logs, topic_label=t["topic"])
                    st.rerun()
