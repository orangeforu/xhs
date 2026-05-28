"""小红书 AI 创作工作台 — Streamlit 应用入口。"""

import os

import streamlit as st

from core.config import (
    init,
    load_topics_json,
    load_performance_json,
    open_folder,
)
from core.publish_helpers import (
    calculate_grade as _calculate_grade,
    calc_formula_stats as _calc_formula_stats,
    calc_pillar_stats as _calc_pillar_stats,
)
from tabs import (
    render_review_tab,
    render_topics_tab,
    render_standards_tab,
    render_analytics_tab,
    render_calendar_tab,
    render_publish_tab,
)

try:
    init()
except RuntimeError:
    pass  # .env 未配置时允许 app 以只读模式运行（数据复盘等不需要 API key）

st.set_page_config(page_title="小红书AI创作台", page_icon="📝", layout="wide")

st.markdown("""
<style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .stMetric {
        background: linear-gradient(135deg, #fff5f5 0%, #fff0f0 100%);
        border-radius: 12px;
        padding: 12px;
        border: 1px solid #ffe0e0;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 500;
    }
    div[data-testid="stExpander"] {
        border: 1px solid #f0f0f0;
        border-radius: 12px;
        background: #fafafa;
        margin-bottom: 12px;
    }
    h1 {
        color: #c41e3a;
    }
</style>
""", unsafe_allow_html=True)

st.title("📝 小红书情感账号 · AI创作工作台")
st.caption("知心姐姐人设 | 目标：3个月1400粉 | 当前进度：笔记质量模型已固化")

# ── 加载数据 ──
topics_data = load_topics_json()
topics = topics_data.get("topics", [])
performance = load_performance_json()

total_count = len(topics)
generated_count = sum(1 for t in topics if t.get("status") == "generated")
published_count = sum(1 for t in topics if t.get("status") == "published")


def _check_circuit_breaker() -> tuple[bool, int]:
    """检查是否触发熔断：连续3篇C级。返回 (是否熔断, 连续C级数)。"""
    notes = performance.get("notes", [])
    if not notes:
        return False, 0
    recent = [n for n in notes if n.get("likes", 0) > 0 or n.get("grade") in ("S", "A", "B", "C")]
    recent.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    streak = 0
    for n in recent[:3]:
        grade = n.get("grade", "")
        if not grade or grade == "pending":
            grade = _calculate_grade(n.get("likes", 0))
        if grade == "C":
            streak += 1
        else:
            break
    return streak >= 3, streak


cb_tripped, cb_streak = _check_circuit_breaker()


# ── Sidebar ──
st.sidebar.header("📊 数据看板")
st.sidebar.metric("本月目标", f"{total_count}篇", f"已生成 {generated_count}篇")
followers_target = int(os.getenv("FOLLOWERS_TARGET", "1400"))
followers_current = int(os.getenv("FOLLOWERS_CURRENT", "900"))
st.sidebar.metric("粉丝目标", str(followers_target), f"当前 {followers_current}")
st.sidebar.progress(
    published_count / total_count if total_count else 0,
    text=f"发布进度 {published_count}/{total_count}",
)

# 最有效公式/支柱提示
if performance.get("notes"):
    _notes = performance["notes"]
    _formula_stats = _calc_formula_stats(_notes)
    if _formula_stats:
        best_f = max(_formula_stats.items(), key=lambda x: x[1]["total_likes"] / max(x[1]["count"], 1))
        st.sidebar.caption(f"🏆 最有效公式: **{best_f[0]}**（均赞 {best_f[1]['total_likes']/best_f[1]['count']:.0f}）")
    _pillar_stats = _calc_pillar_stats(_notes)
    if _pillar_stats:
        best_p = max(_pillar_stats.items(), key=lambda x: x[1]["total_likes"] / max(x[1]["count"], 1))
        st.sidebar.caption(f"🏆 最有效支柱: **{best_p[0]}**（均赞 {best_p[1]['total_likes']/best_p[1]['count']:.0f}）")

if cb_tripped:
    st.sidebar.error(f"🚨 熔断警告：连续 {cb_streak} 篇 C 级！请暂停发布，复盘选题方向。")
elif cb_streak > 0:
    st.sidebar.warning(f"⚠️ 连续 {cb_streak} 篇 C 级，再发 {3 - cb_streak} 篇将触发熔断。")

st.sidebar.header("📋 快捷操作")
if st.sidebar.button("🚀 生成新笔记"):
    st.sidebar.info("请在 Terminal 运行：python pipeline.py --index N")
if st.sidebar.button("📦 批量生成"):
    st.sidebar.info("请在 Terminal 运行：python pipeline.py --batch")
if st.sidebar.button("📁 打开项目文件夹"):
    open_folder(os.path.dirname(os.path.abspath(__file__)))

# ── Main Tabs ──
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📝 待审核笔记",
    "📚 选题池",
    "📖 创作标准",
    "📈 数据复盘",
    "📅 内容日历",
    "🚀 一键发布助手",
])

with tab1:
    render_review_tab()

with tab2:
    render_topics_tab()

with tab3:
    render_standards_tab()

with tab4:
    render_analytics_tab(cb_tripped=cb_tripped, cb_streak=cb_streak)

with tab5:
    render_calendar_tab()

with tab6:
    render_publish_tab()
