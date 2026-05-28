"""Tab 3: 创作标准。"""

import os

import streamlit as st


def render_standards_tab():
    """渲染创作标准 Tab。"""
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
