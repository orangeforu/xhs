"""Tab 5: 内容日历。"""

from datetime import datetime, timedelta

import streamlit as st

from core.config import load_calendar_json, save_calendar_json

PILLARS = ["亲密关系洞察", "自我成长", "社交关系", "情绪疗愈", "生活态度"]
TIME_SLOTS = {
    "morning": "🌅 早间 (7-9点)",
    "noon": "☀️ 午间 (12-14点)",
    "evening": "🌙 晚间 (20-23点)",
}


def render_calendar_tab():
    """渲染内容日历 Tab。"""
    st.header("📅 内容日历")

    calendar_data = load_calendar_json()

    today = datetime.now()
    current_week = today.strftime("%Y-W%W")
    current_weekday = today.weekday()

    week_start = today - timedelta(days=current_weekday)
    week_end = week_start + timedelta(days=6)

    st.subheader(f"本周 {week_start.strftime('%m/%d')} - {week_end.strftime('%m/%d')}")

    week_data = calendar_data.setdefault("weeks", {}).get(current_week, {"days": {}})

    # 编辑本周计划
    for day_offset in range(7):
        _render_day_editor(day_offset, week_start, current_weekday, week_data)

    calendar_data["weeks"][current_week] = week_data

    if st.button("💾 保存本周日历"):
        save_calendar_json(calendar_data)
        st.success("日历已保存！")

    # 支柱均衡检测
    _render_pillar_distribution(week_data)

    # ── 本周 vs 上周对比 ──
    _render_week_comparison(calendar_data, current_week)


def _render_day_editor(day_offset: int, week_start: datetime, current_weekday: int, week_data: dict):
    """渲染单日编辑器。"""
    day_date = week_start + timedelta(days=day_offset)
    day_key = day_date.strftime("%Y-%m-%d")
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    day_name = weekday_names[day_offset]
    is_today = day_offset == current_weekday

    day_data = week_data["days"].get(day_key, {"slots": {}})

    with st.expander(f"{'👉 ' if is_today else ''}{day_name} {day_date.strftime('%m/%d')}", expanded=is_today):
        for slot_key, slot_label in TIME_SLOTS.items():
            slot_data = day_data["slots"].get(slot_key, {})
            cols = st.columns([1, 2, 2, 1])
            with cols[0]:
                st.caption(slot_label)
            with cols[1]:
                topic = st.text_input(
                    "选题",
                    value=slot_data.get("topic", ""),
                    key=f"cal_{day_key}_{slot_key}_topic",
                    label_visibility="collapsed",
                    placeholder="输入选题...",
                )
            with cols[2]:
                pillar = st.selectbox(
                    "支柱",
                    [""] + PILLARS,
                    index=PILLARS.index(slot_data.get("pillar", "")) + 1 if slot_data.get("pillar", "") in PILLARS else 0,
                    key=f"cal_{day_key}_{slot_key}_pillar",
                    label_visibility="collapsed",
                )
            with cols[3]:
                status = slot_data.get("status", "planned")
                status_icon = {"planned": "⬜", "generated": "📝", "published": "✅"}.get(status, "⬜")
                st.caption(status_icon)

            if topic or pillar:
                day_data["slots"][slot_key] = {
                    "topic": topic,
                    "pillar": pillar,
                    "status": slot_data.get("status", "planned"),
                }

        week_data["days"][day_key] = day_data


def _render_pillar_distribution(week_data: dict):
    """渲染支柱分布。"""
    st.divider()
    st.subheader("📊 本周支柱分布")

    pillar_counts = {}
    for day_data in week_data.get("days", {}).values():
        for slot_data in day_data.get("slots", {}).values():
            p = slot_data.get("pillar", "")
            if p:
                pillar_counts[p] = pillar_counts.get(p, 0) + 1

    total_planned = sum(pillar_counts.values())
    if total_planned > 0:
        cols = st.columns(len(PILLARS))
        for i, pillar in enumerate(PILLARS):
            with cols[i]:
                count = pillar_counts.get(pillar, 0)
                ratio = count / total_planned
                st.metric(pillar, f"{count}篇", f"{ratio:.0%}")
                # 均衡性提示
                if ratio > 0.4:
                    st.warning("占比过高")
                elif ratio == 0 and total_planned >= 3:
                    st.caption("未安排")
    else:
        st.info("本周尚未安排任何内容。")

    # 支柱均衡建议
    if total_planned >= 3:
        empty_pillars = [p for p in PILLARS if pillar_counts.get(p, 0) == 0]
        if empty_pillars:
            st.warning(f"⚠️ 以下支柱本周未安排：{', '.join(empty_pillars)}，建议均衡覆盖。")

        over_pillars = [p for p in PILLARS if pillar_counts.get(p, 0) / total_planned > 0.4]
        if over_pillars:
            st.warning(f"⚠️ 以下支柱占比过高：{', '.join(over_pillars)}，建议分散风险。")


def _render_week_comparison(calendar_data: dict, current_week: str):
    """渲染本周 vs 上周对比。"""
    st.divider()
    st.subheader("📊 本周 vs 上周")

    # 计算上周的 week key
    today = datetime.now()
    last_week = today - timedelta(weeks=1)
    last_week_key = last_week.strftime("%Y-W%W")

    last_week_data = calendar_data.get("weeks", {}).get(last_week_key, {"days": {}})

    # 统计上周完成情况
    last_total = 0
    last_published = 0
    for day_data in last_week_data.get("days", {}).values():
        for slot_data in day_data.get("slots", {}).values():
            if slot_data.get("topic"):
                last_total += 1
                if slot_data.get("status") == "published":
                    last_published += 1

    if last_total > 0:
        completion_rate = last_published / last_total
        cols = st.columns(3)
        with cols[0]:
            st.metric("上周计划", f"{last_total}篇")
        with cols[1]:
            st.metric("上周完成", f"{last_published}篇")
        with cols[2]:
            color = "🟢" if completion_rate >= 0.8 else "🟡" if completion_rate >= 0.5 else "🔴"
            st.metric("完成率", f"{color} {completion_rate:.0%}")

        if completion_rate < 0.5:
            st.warning("⚠️ 上周完成率不足 50%，本周请加强执行力。")
    else:
        st.info("上周无计划记录。")
