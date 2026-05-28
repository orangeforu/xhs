"""Tab 4: 数据复盘。"""

import os
from datetime import datetime, timezone

import streamlit as st

from core.config import load_performance_json, save_performance_json
from core.publish_helpers import (
    calculate_grade as _calculate_grade,
    calc_interaction_rate as _calc_interaction_rate,
    calc_formula_stats as _calc_formula_stats,
    calc_pillar_stats as _calc_pillar_stats,
    recalculate_summary as _recalculate_summary,
    score_title as _score_title,
)


def _render_engagement_input(performance: dict):
    """互动数据录入 — 让用户手动输入真实互动数据，闭环反馈循环。"""
    notes = performance.get("notes", [])
    # 找出还没有互动数据的已发布笔记
    needs_data = [n for n in notes if n.get("likes", 0) == 0 and n.get("collects", 0) == 0]

    if not needs_data:
        return

    with st.expander(f"📝 录入互动数据（{len(needs_data)} 篇待录入）", expanded=False):
        st.caption("发布笔记后，将小红书后台的真实数据录入，系统会自动学习并优化后续选题和内容策略。")
        for n in needs_data:
            topic = n.get("topic", "未知")
            st.markdown(f"**{topic}**")
            cols = st.columns(5)
            with cols[0]:
                likes = st.number_input("点赞", min_value=0, key=f"likes_{topic}", step=1)
            with cols[1]:
                collects = st.number_input("收藏", min_value=0, key=f"collects_{topic}", step=1)
            with cols[2]:
                comments = st.number_input("评论", min_value=0, key=f"comments_{topic}", step=1)
            with cols[3]:
                shares = st.number_input("分享", min_value=0, key=f"shares_{topic}", step=1)
            with cols[4]:
                exposure = st.number_input("曝光", min_value=0, key=f"exposure_{topic}", step=100)

            if st.button("💾 保存", key=f"save_eng_{topic}"):
                n["likes"] = likes
                n["collects"] = collects
                n["comments"] = comments
                n["shares"] = shares
                n["exposure"] = exposure
                n["grade"] = _calculate_grade(likes)
                _recalculate_summary(performance)
                save_performance_json(performance)
                st.success(f"{topic} 数据已保存！等级: {n['grade']}")
                st.rerun()


def render_analytics_tab(cb_tripped: bool = False, cb_streak: int = 0):
    """渲染数据复盘 Tab。"""
    st.header("📈 数据复盘")

    performance = load_performance_json()
    notes = performance.get("notes", [])
    summary = performance.get("summary", {})

    # 互动数据录入（闭环反馈）
    _render_engagement_input(performance)

    _render_summary_metrics(summary, notes, cb_tripped)
    _render_formula_analysis(notes)
    _render_pillar_analysis(notes)
    _render_interaction_analysis(notes)
    _render_recommendations(notes)
    _render_publishing_insights(notes)


def _render_summary_metrics(summary: dict, notes: list, cb_tripped: bool):
    """渲染统计摘要。"""
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("总发布", summary.get("total_published", 0))
    with col2:
        total_likes = sum(n.get("likes", 0) for n in notes)
        avg_likes = total_likes / len(notes) if notes else 0
        st.metric("总点赞", total_likes, f"均赞 {avg_likes:.0f}")
    with col3:
        total_exposure = sum(n.get("exposure", 0) for n in notes)
        st.metric("总曝光", f"{total_exposure:,}" if total_exposure else "—")
    with col4:
        if total_exposure > 0:
            total_all_interaction = sum(n.get("likes", 0) + n.get("collects", 0) + n.get("comments", 0) + n.get("shares", 0) for n in notes)
            overall_eng_rate = total_all_interaction / total_exposure
            st.metric("平均互动率", f"{overall_eng_rate:.2%}")
        else:
            st.metric("平均互动率", "—")
    with col5:
        s_count = sum(1 for n in notes if _calculate_grade(n.get("likes", 0)) == "S")
        a_count = sum(1 for n in notes if _calculate_grade(n.get("likes", 0)) == "A")
        st.metric("S/A级", f"{s_count}/{a_count}")
    with col6:
        c_count = sum(1 for n in notes if _calculate_grade(n.get("likes", 0)) == "C")
        st.metric("C级不合格", c_count)

    if cb_tripped:
        st.error("🚨 **熔断已触发**：连续 3 篇 C 级（点赞<200）。请立即停止发布，复盘选题方向和内容质量。")
    elif c_count >= 2:
        st.warning(f"⚠️ 已有 {c_count} 篇 C 级内容，请注意内容质量。")


def _render_formula_analysis(notes: list):
    """渲染标题公式效果分析。"""
    if not notes:
        return

    st.divider()
    st.subheader("📊 标题公式效果分析")

    formula_stats = _calc_formula_stats(notes)
    if not formula_stats:
        return

    formula_rows = []
    for formula, s in formula_stats.items():
        count = s["count"]
        formula_rows.append({
            "公式": formula,
            "篇数": count,
            "平均点赞": s["total_likes"] / count,
            "平均收藏": s["total_collects"] / count,
            "平均评论": s["total_comments"] / count,
            "平均互动率": s["total_engagement"] / count,
        })
    formula_rows.sort(key=lambda x: x["平均点赞"], reverse=True)
    best_formula = formula_rows[0]["公式"] if formula_rows else ""

    for row in formula_rows:
        is_best = row["公式"] == best_formula
        cols = st.columns([2, 1, 1, 1, 1, 1])
        with cols[0]:
            label = f"🏆 **{row['公式']}**" if is_best else row["公式"]
            st.markdown(label)
        with cols[1]:
            st.caption(f"{row['篇数']}篇")
        with cols[2]:
            st.caption(f"👍 {row['平均点赞']:.0f}")
        with cols[3]:
            st.caption(f"⭐ {row['平均收藏']:.0f}")
        with cols[4]:
            st.caption(f"💬 {row['平均评论']:.0f}")
        with cols[5]:
            st.caption(f"📈 {row['平均互动率']:.2%}")

    if best_formula:
        st.success(f"💡 最有效公式：**{best_formula}**，建议增加该类型选题比例。")


def _render_pillar_analysis(notes: list):
    """渲染内容支柱效果分析。"""
    st.subheader("📊 内容支柱效果分析")

    pillar_stats = _calc_pillar_stats(notes)
    if not pillar_stats:
        return

    pillar_rows = []
    for pillar, s in pillar_stats.items():
        count = s["count"]
        pillar_rows.append({
            "支柱": pillar,
            "篇数": count,
            "平均点赞": s["total_likes"] / count,
            "平均收藏": s["total_collects"] / count,
            "平均评论": s["total_comments"] / count,
            "平均互动率": s["total_engagement"] / count,
        })
    pillar_rows.sort(key=lambda x: x["平均点赞"], reverse=True)
    best_pillar = pillar_rows[0]["支柱"] if pillar_rows else ""

    for row in pillar_rows:
        is_best = row["支柱"] == best_pillar
        cols = st.columns([2, 1, 1, 1, 1, 1])
        with cols[0]:
            label = f"🏆 **{row['支柱']}**" if is_best else row["支柱"]
            st.markdown(label)
        with cols[1]:
            st.caption(f"{row['篇数']}篇")
        with cols[2]:
            st.caption(f"👍 {row['平均点赞']:.0f}")
        with cols[3]:
            st.caption(f"⭐ {row['平均收藏']:.0f}")
        with cols[4]:
            st.caption(f"💬 {row['平均评论']:.0f}")
        with cols[5]:
            st.caption(f"📈 {row['平均互动率']:.2%}")

    if best_pillar:
        st.success(f"💡 最有效支柱：**{best_pillar}**，这是你的流量密码。")


def _render_interaction_analysis(notes: list):
    """渲染互动目标效果分析。"""
    st.subheader("📊 互动目标效果分析")

    interaction_types = {}
    for n in notes:
        it = n.get("target_interaction", "未知")
        if it not in interaction_types:
            interaction_types[it] = {"count": 0, "total_likes": 0, "total_collects": 0}
        interaction_types[it]["count"] += 1
        interaction_types[it]["total_likes"] += n.get("likes", 0)
        interaction_types[it]["total_collects"] += n.get("collects", 0)

    if interaction_types:
        for it, s in sorted(interaction_types.items(), key=lambda x: x[1]["total_likes"] / max(x[1]["count"], 1), reverse=True):
            count = s["count"]
            avg_likes = s["total_likes"] / count
            avg_collects = s["total_collects"] / count
            st.caption(f"**{it}**：{count}篇 | 平均点赞 {avg_likes:.0f} | 平均收藏 {avg_collects:.0f}")


def _render_recommendations(notes: list):
    """渲染运营建议。"""
    st.divider()
    st.subheader("💡 运营建议")

    recommendations = []
    formula_stats = _calc_formula_stats(notes)
    pillar_stats = _calc_pillar_stats(notes)

    # 基于公式效果的建议
    if formula_stats:
        best_f = max(formula_stats.items(), key=lambda x: x[1]["total_likes"] / max(x[1]["count"], 1))
        worst_f = min(formula_stats.items(), key=lambda x: x[1]["total_likes"] / max(x[1]["count"], 1))
        if best_f[0] != worst_f[0]:
            best_avg = best_f[1]["total_likes"] / best_f[1]["count"]
            worst_avg = worst_f[1]["total_likes"] / worst_f[1]["count"]
            if best_avg > worst_avg * 1.5:
                recommendations.append(f"📊 **{best_f[0]}** 表现远超 **{worst_f[0]}**（{best_avg:.0f} vs {worst_avg:.0f} 赞），建议增加前者比例。")

    # 基于支柱效果的建议
    if pillar_stats:
        best_p = max(pillar_stats.items(), key=lambda x: x[1]["total_likes"] / max(x[1]["count"], 1))
        recommendations.append(f"🏆 **{best_p[0]}** 是你的流量密码，建议作为主力支柱。")

    # 基于 C 级内容的建议
    c_count = sum(1 for n in notes if _calculate_grade(n.get("likes", 0)) == "C")
    if c_count >= 2:
        recommendations.append(f"⚠️ 已有 {c_count} 篇 C 级内容，建议暂停发布，复盘选题方向后再继续。")

    # 基于互动率的建议
    notes_with_exposure = [n for n in notes if n.get("exposure", 0) > 0]
    if notes_with_exposure:
        avg_eng = sum(_calc_interaction_rate(n) for n in notes_with_exposure) / len(notes_with_exposure)
        if avg_eng < 0.03:
            recommendations.append(f"📈 平均互动率 {avg_eng:.2%} 偏低（目标 3%+），建议优化标题吸引力和评论钩子。")
        elif avg_eng >= 0.05:
            recommendations.append(f"🎉 平均互动率 {avg_eng:.2%} 优秀（目标 5%+），保持当前策略。")

    # 发布节奏建议
    if len(notes) >= 3:
        recent_3 = sorted(notes, key=lambda x: x.get("published_at", ""))[-3:]
        dates = []
        for n in recent_3:
            try:
                dates.append(datetime.fromisoformat(n["published_at"].replace("Z", "+00:00")))
            except (KeyError, ValueError):
                pass
        if len(dates) >= 2:
            gaps = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
            avg_gap = sum(gaps) / len(gaps)
            if avg_gap > 3:
                recommendations.append(f"📅 平均发布间隔 {avg_gap:.0f} 天，建议保持 2-3 天一篇的节奏。")

    if not recommendations:
        recommendations.append("📊 数据不足，继续发布后会生成运营建议。")

    for rec in recommendations:
        st.markdown(f"- {rec}")


def _render_publishing_insights(notes: list):
    """渲染发布效果洞察。"""
    if len(notes) < 3:
        return

    st.divider()
    st.subheader("🔍 发布效果洞察")

    # 热门时段分析
    hour_counts = {}
    for n in notes:
        try:
            dt = datetime.fromisoformat(n["published_at"].replace("Z", "+00:00"))
            hour = dt.hour
            if 7 <= hour < 9:
                slot = "早间 (7-9点)"
            elif 12 <= hour < 14:
                slot = "午间 (12-14点)"
            elif 20 <= hour < 23:
                slot = "晚间 (20-23点)"
            else:
                slot = "其他时段"
            if slot not in hour_counts:
                hour_counts[slot] = {"count": 0, "total_likes": 0}
            hour_counts[slot]["count"] += 1
            hour_counts[slot]["total_likes"] += n.get("likes", 0)
        except (KeyError, ValueError):
            continue

    if hour_counts:
        st.caption("**热门发布时段**：")
        for slot, data in sorted(hour_counts.items(), key=lambda x: x[1]["total_likes"] / max(x[1]["count"], 1), reverse=True):
            avg = data["total_likes"] / data["count"] if data["count"] else 0
            st.caption(f"- {slot}: {data['count']}篇，均赞 {avg:.0f}")

    # 话题标签效果
    tag_stats = {}
    for n in notes:
        topic = n.get("topic", "")
        likes = n.get("likes", 0)
        if topic:
            tag_stats[topic] = tag_stats.get(topic, 0) + likes

    if len(tag_stats) >= 3:
        top_topics = sorted(tag_stats.items(), key=lambda x: x[1], reverse=True)[:3]
        st.caption("**高赞话题**：")
        for topic, total in top_topics:
            st.caption(f"- {topic}: {total} 赞")
