import os
import glob
import shutil
from datetime import datetime, timezone

import streamlit as st

from core.config import (
    init,
    load_topics_json,
    save_topics_json,
    load_performance_json,
    save_performance_json,
    open_folder,
)

init()

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

# ── 熔断检测 ──
def _calculate_grade(likes: int) -> str:
    if likes > 1500:
        return "S"
    elif likes >= 800:
        return "A"
    elif likes >= 200:
        return "B"
    return "C"


def _check_circuit_breaker() -> tuple[bool, int]:
    """检查是否触发熔断：连续3篇C级。返回 (是否熔断, 连续C级数)。"""
    notes = performance.get("notes", [])
    if not notes:
        return False, 0
    # 按发布时间排序，取最近3篇已录入数据的
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
tab1, tab2, tab3, tab4 = st.tabs(["📝 待审核笔记", "📚 选题池", "📖 创作标准", "📈 数据复盘"])

# Tab 1: 待审核笔记
with tab1:
    st.header("待审核笔记")

    generated_topics = [t for t in topics if t.get("status") == "generated"]
    legacy_drafts = sorted(glob.glob("docs/draft_note_*.md"))

    if not generated_topics and not legacy_drafts:
        st.info("暂无待审核笔记。运行 pipeline.py 生成后，笔记会出现在这里。")
    else:
        for t in generated_topics:
            out_dir = t.get("output_dir", "")
            note_path = os.path.join(out_dir, "note.md") if out_dir else ""
            if not (note_path and os.path.exists(note_path)):
                st.warning(f"选题 **{t['topic']}** 标记为已生成，但找不到文件：{note_path}")
                continue

            with st.expander(f"📄 {t['topic']}", expanded=True):
                try:
                    with open(note_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except FileNotFoundError:
                    st.error(f"文件已被删除: {note_path}")
                    continue
                st.markdown(content)

                # 提取预设评论
                preset_text = ""
                if "## 预设评论" in content:
                    preset_text = content.split("## 预设评论")[1].strip()

                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button(f"✅ 通过并发布", key=f"pass_{t['id']}"):
                        topic_name = os.path.basename(out_dir)
                        pub_dir = os.path.join("published", topic_name)
                        if os.path.exists(pub_dir):
                            st.warning(f"published/{topic_name} 已存在，将被覆盖。")
                        shutil.move(out_dir, pub_dir)

                        t["status"] = "published"
                        t["published_at"] = datetime.now(timezone.utc).isoformat()
                        save_topics_json(topics_data)

                        perf = load_performance_json()
                        perf["notes"].append({
                            "topic_id": t["id"],
                            "topic": t["topic"],
                            "published_at": t["published_at"],
                            "likes": 0,
                            "collects": 0,
                            "comments": 0,
                            "shares": 0,
                            "grade": "pending",
                        })
                        perf["summary"]["total_published"] = len(perf["notes"])
                        save_performance_json(perf)

                        st.success(f"{t['topic']} 已发布！目录已移动到 published/")
                        st.rerun()

                with col2:
                    if st.button(f"📝 需要修改", key=f"edit_{t['id']}"):
                        st.warning("请在下方输入修改意见，或直接编辑 docs/ 下的文件。")
                        st.text_area("修改意见", key=f"feedback_{t['id']}")

                with col3:
                    if st.button(f"❌ 打回重写", key=f"reject_{t['id']}"):
                        st.session_state[f"confirm_reject_{t['id']}"] = True
                    if st.session_state.get(f"confirm_reject_{t['id']}"):
                        st.warning(f"确认打回 **{t['topic']}**？将删除生成的全部文件。")
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("确认打回", key=f"confirm_yes_{t['id']}"):
                                t["status"] = "not_started"
                                if os.path.exists(out_dir):
                                    shutil.rmtree(out_dir)
                                for k in ("generated_at", "output_dir", "published_at"):
                                    t.pop(k, None)
                                save_topics_json(topics_data)
                                st.session_state.pop(f"confirm_reject_{t['id']}", None)
                                st.error(f"{t['topic']} 已打回。请调整 pipeline.py 的 prompt 后重新生成。")
                                st.rerun()
                        with c2:
                            if st.button("取消", key=f"confirm_no_{t['id']}"):
                                st.session_state.pop(f"confirm_reject_{t['id']}", None)
                                st.rerun()

                if preset_text:
                    st.subheader("💬 预设评论（发布后复制到评论区）")
                    st.text_area("全选复制", preset_text, height=200, key=f"preset_{t['id']}")

        # 遗留草稿兼容
        if legacy_drafts:
            st.divider()
            st.caption("以下草稿未关联选题池（旧版遗留）")
            for f in legacy_drafts:
                fname = os.path.basename(f)
                with st.expander(f"📄 {fname}"):
                    with open(f, "r", encoding="utf-8") as file:
                        st.markdown(file.read())

# Tab 2: 选题池
with tab2:
    st.header("📚 本月选题池")

    for i, t in enumerate(topics, 1):
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

# Tab 3: 创作标准
with tab3:
    st.header("📖 A级创作标准速查")

    with open("docs/persona_dna.md", "r", encoding="utf-8") as f:
        dna = f.read()

    st.subheader("🚫 绝对禁忌词")
    st.code("你看 / 你就看一点 / 其实啊 / 其实 / 第一...第二... / 总结起来 / 总之 / 真正爱你的人不会...")

    st.subheader("✅ 每篇必须包含")
    must_have = [
        "亲近视角：'我闺蜜跟我说' 或 '有姐妹私信我'",
        "博主共情：'其实我也有过这种时候'",
        "最狠的一句话：极致扎心短句",
        "以前vs现在对比",
        "反常识洞察角度",
        "治愈出口 + 价值承诺",
        "评论引导互动问题",
        "封面：情绪钩子小字（无具体虚假事件）",
    ]
    for item in must_have:
        st.checkbox(item, value=True, disabled=True)

    st.subheader("📐 图文分页格式")
    st.markdown("""
    - **封面**：大字标题 + 情绪钩子小字
    - **内页1**：开场画面（抓眼球细节）
    - **内页2-3**：故事展开 + 深入内心 + 对比
    - **内页4**：反常识洞察
    - **内页5**：博主共情 + 治愈
    - **内页6**：金句 + 价值承诺 + 评论引导
    """)

    if st.toggle("查看完整 DNA 报告", key="show_dna"):
        st.markdown(dna)

# Tab 4: 数据复盘
with tab4:
    st.header("📈 数据复盘")

    notes = performance.get("notes", [])
    summary = performance.get("summary", {})

    # 统计摘要
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("总发布", summary.get("total_published", 0))
    with col2:
        total_likes = sum(n.get("likes", 0) for n in notes)
        avg_likes = total_likes / len(notes) if notes else 0
        st.metric("总点赞", total_likes, f"均赞 {avg_likes:.0f}")
    with col3:
        s_count = sum(1 for n in notes if _calculate_grade(n.get("likes", 0)) == "S")
        st.metric("S级爆款", s_count)
    with col4:
        a_count = sum(1 for n in notes if _calculate_grade(n.get("likes", 0)) == "A")
        st.metric("A级优质", a_count)
    with col5:
        c_count = sum(1 for n in notes if _calculate_grade(n.get("likes", 0)) == "C")
        st.metric("C级不合格", c_count)

    if cb_tripped:
        st.error("🚨 **熔断已触发**：连续 3 篇 C 级（点赞<200）。请立即停止发布，复盘选题方向和内容质量。")
    elif c_count >= 2:
        st.warning(f"⚠️ 已有 {c_count} 篇 C 级内容，请注意内容质量。")

    st.divider()
    st.subheader("📋 已发布笔记数据录入")

    if not notes:
        st.info("暂无已发布笔记。在「待审核笔记」Tab 中点击「通过并发布」后，笔记会出现在这里。")
    else:
        for i, note in enumerate(notes):
            topic = note.get("topic", f"笔记 {i+1}")
            with st.expander(f"{topic}", expanded=False):
                cols = st.columns(5)
                with cols[0]:
                    likes = st.number_input("点赞", min_value=0, value=note.get("likes", 0), key=f"likes_{i}")
                with cols[1]:
                    collects = st.number_input("收藏", min_value=0, value=note.get("collects", 0), key=f"collects_{i}")
                with cols[2]:
                    comments = st.number_input("评论", min_value=0, value=note.get("comments", 0), key=f"comments_{i}")
                with cols[3]:
                    shares = st.number_input("分享", min_value=0, value=note.get("shares", 0), key=f"shares_{i}")
                with cols[4]:
                    grade = _calculate_grade(likes)
                    grade_color = {"S": "🟢", "A": "🔵", "B": "🟡", "C": "🔴"}.get(grade, "⚪")
                    st.markdown(f"**等级: {grade_color} {grade}**")

                if st.button("💾 保存数据", key=f"save_perf_{i}"):
                    note["likes"] = likes
                    note["collects"] = collects
                    note["comments"] = comments
                    note["shares"] = shares
                    note["grade"] = grade
                    save_performance_json(performance)
                    st.success(f"{topic} 数据已保存！")
                    st.rerun()
