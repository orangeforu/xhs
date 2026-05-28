import os
import glob
import re
import shutil
from datetime import datetime, timezone, timedelta

import streamlit as st

from core.config import (
    init,
    load_topics_json,
    save_topics_json,
    load_performance_json,
    save_performance_json,
    load_calendar_json,
    save_calendar_json,
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


def _calc_interaction_rate(note: dict) -> float:
    """计算互动率 = (点赞+收藏+评论+分享) / 曝光量"""
    exposure = note.get("exposure", 0)
    if not exposure:
        return 0.0
    total = note.get("likes", 0) + note.get("collects", 0) + note.get("comments", 0) + note.get("shares", 0)
    return total / exposure


def _calc_formula_stats(notes: list[dict]) -> dict:
    """按标题公式分组统计平均数据。"""
    stats: dict[str, dict] = {}
    for n in notes:
        formula = n.get("title_formula", "未知")
        if formula not in stats:
            stats[formula] = {"count": 0, "total_likes": 0, "total_collects": 0, "total_comments": 0, "total_shares": 0, "total_engagement": 0.0}
        s = stats[formula]
        s["count"] += 1
        s["total_likes"] += n.get("likes", 0)
        s["total_collects"] += n.get("collects", 0)
        s["total_comments"] += n.get("comments", 0)
        s["total_shares"] += n.get("shares", 0)
        rate = _calc_interaction_rate(n)
        s["total_engagement"] += rate
    return stats


def _calc_pillar_stats(notes: list[dict]) -> dict:
    """按内容支柱分组统计平均数据。"""
    stats: dict[str, dict] = {}
    for n in notes:
        pillar = n.get("pillar", "未知")
        if pillar not in stats:
            stats[pillar] = {"count": 0, "total_likes": 0, "total_collects": 0, "total_comments": 0, "total_shares": 0, "total_engagement": 0.0}
        s = stats[pillar]
        s["count"] += 1
        s["total_likes"] += n.get("likes", 0)
        s["total_collects"] += n.get("collects", 0)
        s["total_comments"] += n.get("comments", 0)
        s["total_shares"] += n.get("shares", 0)
        rate = _calc_interaction_rate(n)
        s["total_engagement"] += rate
    return stats


def _check_compliance(content: str, title: str, tags: list[str], image_count: int) -> dict:
    """发布前合规检查。"""
    issues = []
    warnings = []

    # 标题检查
    if len(title) > 20:
        issues.append(f"标题超长（{len(title)}字，建议≤20字）")
    if not re.search(r'[\U0001F300-\U0001F9FF\U00002600-\U000027B0]', title):
        warnings.append("标题缺少 emoji，建议加 1-2 个")

    # 标签检查
    if len(tags) < 3:
        issues.append(f"标签不足（{len(tags)}个，要求 3-5 个）")
    elif len(tags) > 5:
        issues.append(f"标签过多（{len(tags)}个，要求 3-5 个）")
    if not any("不懂就问" in t for t in tags):
        warnings.append("缺少必带标签 #不懂就问有问必答")

    # 图片检查
    if image_count < 3:
        issues.append(f"图片不足（{image_count}张，建议 3-6 张）")
    elif image_count > 9:
        warnings.append(f"图片较多（{image_count}张），小红书最多 9 张")

    # 敏感词检查
    sensitive_words = ["私信", "微信", "淘宝", "京东", "拼多多", "抖音", "快手", "B站",
                       "公众号", "小程序", "加我", "联系我", "购买链接", "下单"]
    found = [w for w in sensitive_words if w in content]
    if found:
        issues.append(f"检测到引流/敏感词：{', '.join(found)}")

    # 正文长度检查
    body_len = len(re.sub(r'\s+', '', content))
    if body_len < 300:
        warnings.append(f"正文偏短（{body_len}字，建议 500-800 字）")
    elif body_len > 1200:
        warnings.append(f"正文偏长（{body_len}字，建议 500-800 字）")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


def _recalculate_summary(performance: dict) -> None:
    """根据 notes 数据重算 summary 统计。"""
    notes = performance.get("notes", [])
    summary = performance.setdefault("summary", {})
    summary["total_published"] = len(notes)
    summary["total_likes"] = sum(n.get("likes", 0) for n in notes)
    summary["total_collects"] = sum(n.get("collects", 0) for n in notes)
    summary["total_comments"] = sum(n.get("comments", 0) for n in notes)
    summary["total_shares"] = sum(n.get("shares", 0) for n in notes)
    summary["total_exposure"] = sum(n.get("exposure", 0) for n in notes)
    summary["s_grade_count"] = sum(1 for n in notes if n.get("grade") == "S")
    summary["a_grade_count"] = sum(1 for n in notes if n.get("grade") == "A")
    summary["b_grade_count"] = sum(1 for n in notes if n.get("grade") == "B")
    summary["c_grade_count"] = sum(1 for n in notes if n.get("grade") == "C")


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


# ── 发布辅助函数 ──
def _extract_title_candidates(content: str) -> list[str]:
    """从 note.md 提取标题候选列表。"""
    titles = []
    m = re.search(r"【标题候选】\s*(.+?)\s*(?=【|$)", content, re.DOTALL)
    if m:
        block = m.group(1).strip()
        for line in block.split("\n"):
            line = line.strip()
            if not line:
                continue
            cleaned = re.sub(r"^\d+[\.、]\s*", "", line)
            cleaned = re.sub(r"^[\s*_`]+|[\s*_`]+$", "", cleaned)
            if cleaned:
                titles.append(cleaned)
    return titles


def _extract_body_for_publish(content: str) -> str:
    """提取并格式化正文，适合小红书发布。"""
    m = re.search(r"【正文】\s*(.+?)(?=## 审核结果|## 预设评论|## 封面|$)", content, re.DOTALL)
    if not m:
        return ""
    body = m.group(1).strip()
    body = re.sub(r"\*\*(.+?)\*\*", r"\1", body)
    body = re.sub(r"\n\s*---\s*\n", "\n\n", body)
    body = re.sub(r"^#+\s*", "", body, flags=re.MULTILINE)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


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
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📝 待审核笔记", "📚 选题池", "📖 创作标准", "📈 数据复盘", "📅 内容日历", "🚀 一键发布助手"])

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
                            "title_formula": t.get("title_formula", ""),
                            "pillar": t.get("pillar", ""),
                            "target_interaction": t.get("target_interaction", ""),
                            "published_at": t["published_at"],
                            "exposure": 0,
                            "likes": 0,
                            "collects": 0,
                            "comments": 0,
                            "shares": 0,
                            "grade": "pending",
                        })
                        _recalculate_summary(perf)
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

# Tab 3: 创作标准
with tab3:
    st.header("📖 A级创作标准速查")

    dna_path = "docs/persona_dna.md"
    if os.path.exists(dna_path):
        with open(dna_path, "r", encoding="utf-8") as f:
            dna = f.read()
    else:
        dna = ""

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
        # 计算整体互动率
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

    # ── 标题公式效果分析 ──
    if notes:
        st.divider()
        st.subheader("📊 标题公式效果分析")

        formula_stats = _calc_formula_stats(notes)
        if formula_stats:
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
            # 按平均点赞排序
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

        # ── 内容支柱效果分析 ──
        st.subheader("📊 内容支柱效果分析")

        pillar_stats = _calc_pillar_stats(notes)
        if pillar_stats:
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

        # ── 互动目标效果分析 ──
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

        # ── 运营建议 ──
        st.divider()
        st.subheader("💡 运营建议")

        recommendations = []

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
            recent_3 = sorted(notes, key=lambda x: x.get("published_at", ""), reverse=True)[:3]
            recent_grades = [_calculate_grade(n.get("likes", 0)) for n in recent_3]
            if all(g == "C" for g in recent_grades):
                recommendations.append("🚨 连续 3 篇 C 级，建议立即暂停发布，全面复盘。")
            elif all(g in ("S", "A") for g in recent_grades):
                recommendations.append("🔥 连续 3 篇高质量，趁热打铁，可以加速发布节奏。")

        if not recommendations:
            recommendations.append("数据积累中，继续发布后会生成个性化建议。")

        for rec in recommendations:
            st.markdown(rec)

    st.divider()
    st.subheader("📋 已发布笔记数据录入")

    if not notes:
        st.info("暂无已发布笔记。在「待审核笔记」Tab 中点击「通过并发布」后，笔记会出现在这里。")
    else:
        for i, note in enumerate(notes):
            topic = note.get("topic", f"笔记 {i+1}")
            with st.expander(f"{topic}", expanded=False):
                cols = st.columns(6)
                with cols[0]:
                    exposure = st.number_input("曝光量", min_value=0, value=note.get("exposure", 0), key=f"exposure_{i}")
                with cols[1]:
                    likes = st.number_input("点赞", min_value=0, value=note.get("likes", 0), key=f"likes_{i}")
                with cols[2]:
                    collects = st.number_input("收藏", min_value=0, value=note.get("collects", 0), key=f"collects_{i}")
                with cols[3]:
                    comments = st.number_input("评论", min_value=0, value=note.get("comments", 0), key=f"comments_{i}")
                with cols[4]:
                    shares = st.number_input("分享", min_value=0, value=note.get("shares", 0), key=f"shares_{i}")
                with cols[5]:
                    grade = _calculate_grade(likes)
                    grade_color = {"S": "🟢", "A": "🔵", "B": "🟡", "C": "🔴"}.get(grade, "⚪")
                    st.markdown(f"**等级: {grade_color} {grade}**")

                # 互动率显示
                total_interaction = likes + collects + comments + shares
                if exposure > 0:
                    eng_rate = total_interaction / exposure
                    st.caption(f"互动率: {eng_rate:.2%} | 总互动: {total_interaction} | 曝光: {exposure}")
                else:
                    st.caption(f"总互动: {total_interaction} | 请填写曝光量以计算互动率")

                if st.button("💾 保存数据", key=f"save_perf_{i}"):
                    note["exposure"] = exposure
                    note["likes"] = likes
                    note["collects"] = collects
                    note["comments"] = comments
                    note["shares"] = shares
                    note["grade"] = grade
                    _recalculate_summary(performance)
                    save_performance_json(performance)
                    st.success(f"{topic} 数据已保存！")
                    st.rerun()

# Tab 5: 内容日历
with tab5:
    st.header("📅 内容日历")

    calendar_data = load_calendar_json()

    # 获取当前周
    today = datetime.now()
    current_week = today.strftime("%Y-W%W")
    current_weekday = today.weekday()  # 0=Monday

    # 计算本周起止日期
    week_start = today - timedelta(days=current_weekday)
    week_end = week_start + timedelta(days=6)

    st.subheader(f"本周 {week_start.strftime('%m/%d')} - {week_end.strftime('%m/%d')}")

    # 支柱列表
    PILLARS = ["亲密关系洞察", "自我成长", "社交关系", "情绪疗愈", "生活态度"]
    TIME_SLOTS = {
        "morning": "🌅 早间 (7-9点)",
        "noon": "☀️ 午间 (12-14点)",
        "evening": "🌙 晚间 (20-23点)",
    }

    # 加载本周计划
    week_data = calendar_data.setdefault("weeks", {}).get(current_week, {"days": {}})

    # 编辑本周计划
    for day_offset in range(7):
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

                # 保存到 day_data
                if topic or pillar:
                    day_data["slots"][slot_key] = {
                        "topic": topic,
                        "pillar": pillar,
                        "status": slot_data.get("status", "planned"),
                    }

            week_data["days"][day_key] = day_data

    # 保存日历
    calendar_data["weeks"][current_week] = week_data

    if st.button("💾 保存本周日历"):
        save_calendar_json(calendar_data)
        st.success("日历已保存！")

    # ── 支柱均衡检测 ──
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
            count = pillar_counts.get(pillar, 0)
            ratio = count / total_planned
            with cols[i]:
                st.metric(pillar[:4], f"{count}篇", f"{ratio:.0%}")
                if ratio > 0.4:
                    st.warning("偏重")
                elif ratio == 0 and total_planned > 2:
                    st.caption("缺失")

        # 均衡度评估
        max_ratio = max(pillar_counts.values()) / total_planned if total_planned > 0 else 0
        if max_ratio > 0.5:
            st.warning(f"⚠️ 支柱分布不均，最大占比 {max_ratio:.0%}。建议增加其他支柱内容。")
        elif len([p for p in PILLARS if pillar_counts.get(p, 0) > 0]) >= 3:
            st.success("✅ 支柱分布均衡，继续保持。")
    else:
        st.info("本周暂无排期，请在上方填写选题计划。")

    # ── 发布时间建议 ──
    st.divider()
    st.subheader("⏰ 发布时间建议")

    if performance.get("notes"):
        time_analysis = {}
        for n in performance["notes"]:
            pub_time = n.get("published_at", "")
            if not pub_time:
                continue
            try:
                dt = datetime.fromisoformat(pub_time.replace("Z", "+00:00"))
                hour = dt.hour
                if 7 <= hour < 9:
                    slot = "早间 (7-9点)"
                elif 12 <= hour < 14:
                    slot = "午间 (12-14点)"
                elif 20 <= hour < 23:
                    slot = "晚间 (20-23点)"
                else:
                    slot = "其他时段"
                if slot not in time_analysis:
                    time_analysis[slot] = {"count": 0, "total_likes": 0}
                time_analysis[slot]["count"] += 1
                time_analysis[slot]["total_likes"] += n.get("likes", 0)
            except (ValueError, TypeError):
                pass

        if time_analysis:
            for slot, data in sorted(time_analysis.items(), key=lambda x: x[1]["total_likes"] / max(x[1]["count"], 1), reverse=True):
                avg = data["total_likes"] / data["count"] if data["count"] > 0 else 0
                st.caption(f"**{slot}**：{data['count']}篇 | 平均点赞 {avg:.0f}")
            best_slot = max(time_analysis.items(), key=lambda x: x[1]["total_likes"] / max(x[1]["count"], 1))
            st.success(f"💡 最佳发布时段：**{best_slot[0]}**（平均点赞 {best_slot[1]['total_likes']/best_slot[1]['count']:.0f}）")
    else:
        st.info("暂无发布数据，积累数据后会推荐最佳发布时间。")

    # ── 系列配置 ──
    st.divider()
    st.subheader("📚 系列管理")

    VISUAL_STYLES = ["warm_grey", "twilight", "crimson", "mist", "cool", "blank"]
    series_data = calendar_data.setdefault("series", {})

    # 现有系列列表
    if series_data:
        for series_name, series_info in series_data.items():
            cols = st.columns([3, 2, 1])
            with cols[0]:
                st.markdown(f"**{series_name}**")
            with cols[1]:
                current_style = series_info.get("style", "warm_grey")
                st.caption(f"视觉风格: {current_style}")
            with cols[2]:
                st.caption(f"{series_info.get('count', 0)}篇")

    # 添加/编辑系列
    with st.expander("添加/编辑系列"):
        new_series_name = st.text_input("系列名称", key="new_series_name", placeholder="如：不敢说出口的话")
        new_series_style = st.selectbox(
            "绑定视觉风格",
            VISUAL_STYLES,
            index=VISUAL_STYLES.index(series_data.get(new_series_name, {}).get("style", "warm_grey")) if new_series_name in series_data else 0,
            key="new_series_style",
        )
        new_series_desc = st.text_input("系列描述", key="new_series_desc", placeholder="简短描述系列主题")

        if st.button("💾 保存系列配置") and new_series_name:
            series_data[new_series_name] = {
                "style": new_series_style,
                "description": new_series_desc,
                "count": series_data.get(new_series_name, {}).get("count", 0),
            }
            calendar_data["series"] = series_data
            save_calendar_json(calendar_data)
            st.success(f"系列「{new_series_name}」已保存，绑定风格: {new_series_style}")
            st.rerun()

    # 使用说明
    st.info("💡 系列绑定视觉风格后，该系列下的所有笔记将自动使用指定风格生成封面，保持视觉一致性。")

# Tab 6: 一键发布助手
with tab6:
    st.header("🚀 一键发布助手")
    st.caption("选择笔记 → 挑选标题 → 复制正文 → 按顺序上传图片 → 粘贴预设评论")

    eligible_topics = [t for t in topics if t.get("status") in ("generated", "published")]
    if not eligible_topics:
        st.info("暂无可发布的笔记。先在 Terminal 运行 `python pipeline.py --index N` 生成笔记。")
    else:
        options = {f"{t['topic']} ({'待审核' if t.get('status') == 'generated' else '已发布'})": t for t in eligible_topics}
        selected_label = st.selectbox("选择要发布的笔记", list(options.keys()))
        selected_topic = options[selected_label]

        out_dir = selected_topic.get("output_dir", "")
        note_path = os.path.join(out_dir, "note.md") if out_dir else ""

        if not (note_path and os.path.exists(note_path)):
            st.error(f"找不到笔记文件：{note_path}")
        else:
            with open(note_path, "r", encoding="utf-8") as f:
                raw_content = f.read()

            titles = _extract_title_candidates(raw_content)
            body = _extract_body_for_publish(raw_content)
            tags = selected_topic.get("tags", [])
            hashtags = " ".join([f"#{tag}" for tag in tags])

            # ── 发布前 Checklist ──
            st.subheader("✅ 发布前检查")

            # 提取标签
            tag_match = re.search(r'【话题标签】\s*(.+?)(?=【|$)', raw_content, re.DOTALL)
            parsed_tags = []
            if tag_match:
                for word in tag_match.group(1).strip().split():
                    word = word.strip()
                    if word.startswith("#") and len(word) > 1:
                        parsed_tags.append(word)

            # 提取正文用于检查
            body_for_check = _extract_body_for_publish(raw_content)

            # 统计图片
            image_count = len(glob.glob(os.path.join(out_dir, "*.png")))

            # 标题候选（取第一个做检查）
            title_candidates = _extract_title_candidates(raw_content)
            check_title = title_candidates[0] if title_candidates else selected_topic.get("topic", "")

            # 运行合规检查
            compliance = _check_compliance(body_for_check, check_title, parsed_tags, image_count)

            if compliance["passed"]:
                st.success("合规检查通过")
            else:
                for issue in compliance["issues"]:
                    st.error(f"❌ {issue}")

            if compliance["warnings"]:
                for warn in compliance["warnings"]:
                    st.warning(f"⚠️ {warn}")

            # Checklist 详情
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

            st.divider()

            col_left, col_right = st.columns([1, 1])

            with col_left:
                st.subheader("1️⃣ 选择标题")
                if titles:
                    selected_title = st.radio("推荐标题（选一个）", titles, index=0)
                else:
                    selected_title = st.text_input("自定义标题", value=selected_topic.get("topic", ""))

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
