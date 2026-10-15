"""Tab 1: 待审核笔记。"""

import os
import shutil
from datetime import datetime, timezone

import streamlit as st

from core.config import load_topics_json, save_topics_json


def render_review_tab():
    """渲染待审核笔记 Tab。"""
    st.header("待审核笔记")

    topics_data = load_topics_json()
    topics = topics_data.get("topics", [])

    generated_topics = [t for t in topics if t.get("status") == "generated"]

    if not generated_topics:
        st.info("暂无待审核笔记。运行 pipeline.py 生成后，笔记会出现在这里。")
    else:
        for t in generated_topics:
            _render_topic_card(t, topics_data, topics)


def _render_topic_card(t: dict, topics_data: dict, topics: list):
    """渲染单个选题卡片。"""
    out_dir = t.get("output_dir", "")
    note_path = os.path.join(out_dir, "note.md") if out_dir else ""
    if not (note_path and os.path.exists(note_path)):
        st.warning(f"选题 **{t['topic']}** 标记为已生成，但找不到文件：{note_path}")
        return

    with st.expander(f"📄 {t['topic']}", expanded=True):
        try:
            with open(note_path, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            st.error(f"文件已被删除: {note_path}")
            return
        st.markdown(content)

        # 提取预设评论
        preset_text = ""
        if "## 预设评论" in content:
            preset_text = content.split("## 预设评论")[1].strip()

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button(f"✅ 通过", key=f"pass_{t['id']}"):
                _handle_approve(t, out_dir, topics_data)

        with col2:
            _handle_feedback(t, topics_data)

        with col3:
            _handle_reject(t, out_dir, topics_data)

        if preset_text:
            st.subheader("💬 预设评论（发布后复制到评论区）")
            st.text_area("全选复制", preset_text, height=200, key=f"preset_{t['id']}")


def _handle_approve(t: dict, out_dir: str, topics_data: dict):
    """处理审核通过操作。"""
    topic_name = os.path.basename(out_dir)
    approved_dir = os.path.join("docs_agent", "approved", topic_name)
    if os.path.exists(approved_dir):
        st.warning(f"docs_agent/approved/{topic_name} 已存在，将被覆盖。")
    shutil.move(out_dir, approved_dir)

    t["status"] = "approved"
    t["approved_at"] = datetime.now(timezone.utc).isoformat()
    t["output_dir"] = approved_dir
    save_topics_json(topics_data)

    st.success(f"{t['topic']} 已审核通过！目录已移动到 docs_agent/approved/。请在小红书发布后告知我。")
    st.rerun()


def _handle_feedback(t: dict, topics_data: dict):
    """处理修改意见。"""
    if st.button(f"📝 需要修改", key=f"edit_{t['id']}"):
        st.session_state[f"show_feedback_{t['id']}"] = True

    if st.session_state.get(f"show_feedback_{t['id']}"):
        feedback = st.text_area(
            "修改意见",
            key=f"feedback_{t['id']}",
            placeholder="请输入修改意见，点击「保存并重新生成」后将使用 feedback 重新创作..."
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 保存并重新生成", key=f"save_feedback_{t['id']}"):
                if feedback.strip():
                    t["feedback"] = feedback.strip()
                    t["status"] = "not_started"
                    save_topics_json(topics_data)
                    st.session_state.pop(f"show_feedback_{t['id']}", None)
                    st.success(f"修改意见已保存，选题已重置为待生成状态。请使用 pipeline.py --topic \"{t['topic']}\" 重新生成。")
                    st.rerun()
                else:
                    st.warning("请输入修改意见")
        with c2:
            if st.button("取消", key=f"cancel_feedback_{t['id']}"):
                st.session_state.pop(f"show_feedback_{t['id']}", None)
                st.rerun()


def _handle_reject(t: dict, out_dir: str, topics_data: dict):
    """处理打回重写。"""
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
