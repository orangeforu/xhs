"""Tab 6: 一键发布助手 — 支持手动复制和自动发布到小红书。"""

import glob
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

from core.config import load_topics_json, load_performance_json, get_logger
from core.publish_helpers import (
    extract_title_candidates as _extract_title_candidates,
    extract_body_for_publish as _extract_body_for_publish,
    extract_title as extract_title_from_md,
    extract_desc as extract_desc_from_md,
    extract_tags as extract_tags_from_md,
    score_title as _score_title,
    check_compliance as _check_compliance,
    resolve_topics,
)

logger = get_logger(__name__)

# ── 导入 Spider_XHS ──
sys.path.insert(0, str(Path(__file__).parent.parent / "spider_xhs"))
from spider_xhs import XHS_Creator_Apis

# ── 导入 Cookie 持久化工具 ──
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.xhs_auth_helper import get_creator_auth

# ── 废笔记健康检查（防 LLM 思考链泄漏被发布）──
from core.utils import check_note_health


# ═══════════════════════════════════════════════════════════
# 自动发布相关
# ═══════════════════════════════════════════════════════════

APPROVED_DIR = Path(__file__).parent.parent / "docs_agent" / "approved"
PUBLISHED_DIR = Path(__file__).parent.parent / "docs_agent" / "published"


def get_approved_notes() -> list:
    """获取 approved/ 目录下的所有笔记。"""
    if not APPROVED_DIR.exists():
        return []
    notes = []
    for d in APPROVED_DIR.iterdir():
        if not d.is_dir():
            continue
        note_md = d / "note.md"
        if not note_md.exists():
            continue
        with open(note_md, 'r', encoding='utf-8') as f:
            content = f.read()
        cover = d / "cover_ai.png"
        if not cover.exists():
            for alt in ["cover.png", "cover.jpg", "cover.jpeg"]:
                alt_path = d / alt
                if alt_path.exists():
                    cover = alt_path
                    break
        inner_pages = sorted([
            p for p in d.iterdir()
            if p.name.startswith("inner_page") and p.suffix.lower() in ('.png', '.jpg', '.jpeg')
        ])
        if not cover.exists():
            continue
        notes.append({
            "dir": d,
            "name": d.name,
            "title": extract_title_from_md(content),
            "desc": extract_desc_from_md(content),
            "tags": extract_tags_from_md(content),
            "health_issues": check_note_health(content),
            "cover": str(cover),
            "images": [str(cover)] + [str(p) for p in inner_pages],
        })
    return notes


def auto_publish_notes(selected_notes: list, progress_bar=None) -> dict:
    """自动发布选中的笔记到小红书。"""
    results = {"success": 0, "failed": 0, "details": []}

    # 登录创作者平台（带 Cookie 持久化）
    logger.info("正在登录小红书创作者平台...")
    auth = get_creator_auth()
    api = XHS_Creator_Apis(auth).bootstrap()
    logger.info("登录成功！")

    total = len(selected_notes)
    for i, note in enumerate(selected_notes):
        if progress_bar:
            progress_bar.progress((i) / total, text=f"正在发布: {note['title'][:20]}...")

        # 废笔记双保险：即使 UI 选中也拒绝发布
        if note.get("health_issues"):
            results["failed"] += 1
            results["details"].append({
                "title": note["title"],
                "status": "skipped",
                "msg": "健康检查未过，已拦截: " + "; ".join(note["health_issues"]),
            })
            logger.warning(f"⏭️ 跳过 {note['title']}: 健康检查未过")
            continue

        # 话题标签：优先解析为真话题链接（进话题流量池），失败的降级纯文本
        resolved_topics, unresolved_tags = resolve_topics(api, note["tags"])
        plain_tags = " ".join([f"#{t}" for t in unresolved_tags]) if unresolved_tags else ""
        full_desc = f"{note['desc']}\n\n{plain_tags}".strip()
        if resolved_topics:
            logger.info(f"✅ 真话题链接: {note['title']} -> {resolved_topics}")
        if unresolved_tags:
            logger.info(f"⚠️ 纯文本标签(未解析): {note['title']} -> {unresolved_tags}")

        try:
            # spider_xhs 的 upload_media/get_file_info 期望 images 是 bytes（np.frombuffer 解码 + data=file 上传），
            # 传路径字符串会报 "a bytes-like object is required, not 'str'"。这里把路径读成 bytes。
            image_bytes_list = []
            for img_path in note["images"]:
                with open(img_path, "rb") as f:
                    image_bytes_list.append(f.read())

            success, msg, result = api.post_note({
                "title": note["title"],
                "desc": full_desc,
                "media_type": "image",
                "topics": resolved_topics,
                "images": image_bytes_list,
            })

            # 打印完整响应，定位"成功但笔记不存在"的误报
            import json as _json
            try:
                logger.info(f"  post_note 返回 success={success} msg={msg!r}")
                logger.info(f"  post_note 完整 result: {_json.dumps(result, ensure_ascii=False)[:800]}")
            except Exception as e:
                logger.warning(f"  打印 result 失败: {e}; result={result!r}")

            if success:
                # 提取笔记 URL
                note_url = _extract_note_url_from_result(result, api, note["title"])

                # 将 URL 追加到 note.md
                if note_url:
                    _append_url_to_note_md(note["dir"], note_url)

                # 移动到 published/
                target = PUBLISHED_DIR / note["dir"].name
                if target.exists():
                    j = 1
                    while True:
                        target = PUBLISHED_DIR / f"{note['dir'].name}_{j}"
                        if not target.exists():
                            break
                        j += 1
                PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
                shutil.move(str(note["dir"]), str(target))

                results["success"] += 1
                results["details"].append({
                    "title": note["title"],
                    "status": "success",
                    "msg": f"发布成功" + (f" | {note_url}" if note_url else ""),
                    "url": note_url,
                })
                logger.info(f"✅ 发布成功: {note['title']}" + (f" | {note_url}" if note_url else ""))
            else:
                results["failed"] += 1
                results["details"].append({
                    "title": note["title"],
                    "status": "failed",
                    "msg": msg,
                })
                logger.error(f"❌ 发布失败: {note['title']} - {msg}")
        except Exception as e:
            results["failed"] += 1
            results["details"].append({
                "title": note["title"],
                "status": "error",
                "msg": str(e),
            })
            logger.error(f"❌ 发布异常: {note['title']} - {e}")

    if progress_bar:
        progress_bar.progress(1.0, text="发布完成！")

    return results


def _extract_note_url_from_result(result: dict, api, title: str) -> str | None:
    """从 post_note 结果或已发布列表中提取笔记 URL。"""
    if not result:
        return None

    # 尝试直接从响应中提取 note_id
    note_id = None
    data = result.get("data", {})
    if isinstance(data, dict):
        # 常见字段: note_id, id, noteId
        for key in ("note_id", "id", "noteId"):
            if key in data:
                note_id = str(data[key])
                break

    # 如果直接提取失败，从已发布列表中按标题匹配
    if not note_id:
        try:
            success, msg, notes = api.get_all_posted_notes()
            if success and notes:
                # 按时间倒序，找标题匹配的
                for n in reversed(notes):
                    note_title = n.get("title", "")
                    if note_title and title in note_title or note_title in title:
                        note_id = n.get("note_id") or n.get("id")
                        if note_id:
                            break
        except Exception as e:
            logger.warning(f"从已发布列表获取 note_id 失败: {e}")

    if note_id:
        return f"https://www.xiaohongshu.com/explore/{note_id}"
    return None


def _append_url_to_note_md(note_dir: Path, note_url: str) -> None:
    """将笔记 URL 追加到 note.md 末尾。"""
    note_md = note_dir / "note.md"
    if not note_md.exists():
        return
    try:
        with open(note_md, "a", encoding="utf-8") as f:
            f.write(f"\n\n## 发布记录\n\n")
            f.write(f"**笔记 URL**: {note_url}\n")
            f.write(f"**发布时间**: {datetime.now().isoformat()}\n")
        logger.info(f"  📝 已追加 URL 到 note.md: {note_url}")
    except Exception as e:
        logger.warning(f"  追加 URL 到 note.md 失败: {e}")


def render_publish_tab():
    """渲染一键发布助手 Tab — 支持手动复制和自动发布。"""
    st.header("🚀 一键发布助手")

    # ── 自动发布区域 ──
    with st.expander("🤖 自动发布到小红书（新功能）", expanded=True):
        _render_auto_publish_section()

    st.divider()

    # ── 手动发布区域 ──
    st.caption("或手动复制发布：选择笔记 → 挑选标题 → 复制正文 → 按顺序上传图片 → 粘贴预设评论")

    topics_data = load_topics_json()
    topics = topics_data.get("topics", [])
    performance = load_performance_json()

    eligible_topics = [t for t in topics if t.get("status") in ("generated", "published")]
    if not eligible_topics:
        st.info("暂无可发布的笔记。先在 Terminal 运行 `python pipeline.py --index N` 生成笔记。")
        return

    options = {f"{t['topic']} ({'待审核' if t.get('status') == 'generated' else '已发布'})": t for t in eligible_topics}
    selected_label = st.selectbox("选择要发布的笔记", list(options.keys()))
    selected_topic = options[selected_label]

    out_dir = selected_topic.get("output_dir", "")
    note_path = os.path.join(out_dir, "note.md") if out_dir else ""

    if not (note_path and os.path.exists(note_path)):
        st.error(f"找不到笔记文件：{note_path}")
        return

    with open(note_path, "r", encoding="utf-8") as f:
        raw_content = f.read()

    titles = _extract_title_candidates(raw_content)
    body = _extract_body_for_publish(raw_content)
    tags = selected_topic.get("tags", [])
    hashtags = " ".join([f"#{tag}" for tag in tags])

    # 发布前 Checklist
    _render_compliance_check(raw_content, selected_topic, out_dir, body)

    st.divider()

    col_left, col_right = st.columns([1, 1])

    with col_left:
        _render_title_selection(titles, performance, selected_topic)

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
        _render_image_guide(out_dir)


def _render_auto_publish_section():
    """渲染自动发布区域。"""
    st.subheader("🤖 自动发布")
    st.caption("从 approved/ 目录读取已审核通过的笔记，自动发布到小红书创作者平台")

    notes = get_approved_notes()

    if not notes:
        st.info("approved/ 目录下没有待自动发布的笔记。请先在「待审核笔记」Tab 中点击「✅ 通过」审核笔记。")
        return

    st.write(f"发现 **{len(notes)}** 篇待发布笔记：")

    # 显示笔记列表，支持选择
    selected = []
    for note in notes:
        col1, col2, col3 = st.columns([3, 1, 1])
        unhealthy = bool(note.get("health_issues"))
        with col1:
            st.write(f"📄 **{note['title']}**")
            st.caption(f"标签: {', '.join(note['tags'])} | 图片: {len(note['images'])} 张")
            if unhealthy:
                st.error("⚠️ 健康检查未过，已禁用发布：\n- " + "\n- ".join(note["health_issues"]))
        with col2:
            # 预览封面
            if note['cover']:
                st.image(note['cover'], width=80)
        with col3:
            if st.checkbox("选择发布", key=f"select_{note['name']}", disabled=unhealthy):
                selected.append(note)
        st.divider()

    if selected:
        st.write(f"已选择 **{len(selected)}** 篇笔记")

        # 发布按钮
        if st.button("🚀 开始自动发布", type="primary", disabled=len(selected) == 0):
            progress_bar = st.progress(0, text="准备发布...")
            status_text = st.empty()

            try:
                status_text.info("正在登录小红书创作者平台，请使用 App 扫描弹出的二维码...")
                results = auto_publish_notes(selected, progress_bar=progress_bar)

                # 显示结果
                status_text.empty()
                progress_bar.empty()

                st.success(f"发布完成！成功 {results['success']} 篇，失败 {results['failed']} 篇")

                for detail in results['details']:
                    if detail['status'] == 'success':
                        st.success(f"✅ {detail['title']}: {detail['msg']}")
                    else:
                        st.error(f"❌ {detail['title']}: {detail['msg']}")

            except Exception as e:
                progress_bar.empty()
                status_text.empty()
                st.error(f"发布过程出错: {e}")
    else:
        st.info("请勾选要发布的笔记")


def _render_compliance_check(raw_content: str, selected_topic: dict, out_dir: str, body: str):
    """渲染发布前合规检查。"""
    st.subheader("✅ 发布前检查")

    tag_match = re.search(r'【话题标签】\s*(.+?)(?=【|$)', raw_content, re.DOTALL)
    parsed_tags = []
    if tag_match:
        for word in tag_match.group(1).strip().split():
            word = word.strip()
            if word.startswith("#") and len(word) > 1:
                parsed_tags.append(word)

    body_for_check = _extract_body_for_publish(raw_content)
    image_count = len(glob.glob(os.path.join(out_dir, "*.png")))

    title_candidates = _extract_title_candidates(raw_content)
    check_title = title_candidates[0] if title_candidates else selected_topic.get("topic", "")

    compliance = _check_compliance(body_for_check, check_title, parsed_tags, image_count)

    if compliance["passed"]:
        st.success("合规检查通过")
    else:
        for issue in compliance["issues"]:
            st.error(f"❌ {issue}")

    if compliance["warnings"]:
        for warn in compliance["warnings"]:
            st.warning(f"⚠️ {warn}")

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


def _render_title_selection(titles: list, performance: dict, selected_topic: dict):
    """渲染标题选择区域。"""
    st.subheader("1️⃣ 选择标题")
    if titles:
        title_scores = []
        for t in titles:
            ts = _score_title(t, performance)
            title_scores.append((t, ts))

        title_scores.sort(key=lambda x: x[1]["score"], reverse=True)

        title_options = []
        for t, ts in title_scores:
            level_color = {"S": "🟢", "A": "🔵", "B": "🟡", "C": "🔴"}.get(ts["level"], "⚪")
            label = f"{level_color} [{ts['score']}分] {t}"
            title_options.append(label)

        selected_idx = st.radio("推荐标题（按评分排序）", range(len(title_options)), format_func=lambda i: title_options[i], index=0)
        selected_title = title_scores[selected_idx][0]

        with st.expander("评分详情"):
            for reason in title_scores[selected_idx][1]["reasons"]:
                st.caption(f"- {reason}")
    else:
        selected_title = st.text_input("自定义标题", value=selected_topic.get("topic", ""))


def _render_image_guide(out_dir: str):
    """渲染图片上传顺序指南。"""
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
