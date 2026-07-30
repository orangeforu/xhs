#!/usr/bin/env python3
"""
评论洞察脚本 - 采集自己笔记的真实评论，挖选题反哺选题池
========================================================

用法:
    python scripts/comment_insight.py              # 采集最近笔记评论，挖选题
    python scripts/comment_insight.py --max 5      # 只看最近 5 篇笔记的评论
    python scripts/comment_insight.py --save       # 挖出的选题写入 data/topics.json

闭环：fetch_performance 只采评论「数量」，本脚本采评论「文本」--读者真正在问什么、
吵什么（最高意图信号），LLM 抽成争议框 / 选题，带 source=comment_insight 徽标
进选题池。配套 prompts/agent_writer.md 的 forbiddenFinalPhrases 防溯源泄露。

数据来源：spider_xhs PC 端 get_user_me -> get_user_note_info（拿 xsec_token）
-> get_note_all_out_comment（拉评论）。
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.config import get_logger, load_topics_json, save_topics_json
from core.utils import extract_json_from_llm

logger = get_logger(__name__)

from scripts.xhs_auth_helper import get_pc_auth
from spider_xhs import XHS_Apis

# ═══════════════════════════════════════════════════════════
# LLM 提取（纯函数，便于测试）
# ═══════════════════════════════════════════════════════════

_SYSTEM = "你是小红书情感号选题运营，擅长从评论区争论里挖出下一个选题。"

_PROMPT_TMPL = """笔记标题：{title}

以下是该笔记评论区点赞最高的真实评论：
{comments}

请从评论里挖掘 2-4 个可写下一篇笔记的选题。每个选题必须：
1. 来自评论里真实的争论点 / 痛点 / 追问，不要凭空编造
2. 带「争议锚点」--读者会站队的明确判断
3. 与原笔记同赛道但不重复角度

严格按 JSON 输出（不要输出其他内容）：
{{
  "topics": [
    {{"topic": "选题标题", "angle": "切入角度", "controversy_point": "争议点", "confidence": 0.8}}
  ]
}}"""


def _build_prompt(note_title: str, comments: list[dict]) -> str:
    top = sorted(comments, key=lambda c: c.get("likes", 0), reverse=True)[:15]
    body = "\n".join(f"- [赞{c.get('likes', 0)}] {c.get('text', '')}" for c in top)
    return _PROMPT_TMPL.format(title=note_title, comments=body or "（无评论）")


def _parse_topics(raw: str) -> list[dict]:
    """从 LLM 输出解析 topics 列表。"""
    parsed = extract_json_from_llm(raw)
    if not parsed:
        return []
    topics = parsed.get("topics", []) if isinstance(parsed, dict) else []
    return [t for t in topics if isinstance(t, dict) and t.get("topic")]


def extract_topics_from_comments(note_title: str, comments: list[dict], llm_call=None) -> list[dict]:
    """从评论中 LLM 提取选题洞察。

    Args:
        note_title: 笔记标题。
        comments: ``[{text, likes}, ...]``。
        llm_call: 可选的 LLM 调用函数 ``f(prompt) -> str``，注入便于测试。
            默认用 ``core.writer._call_api``。
    """
    top = sorted(comments, key=lambda c: c.get("likes", 0), reverse=True)[:15]
    if not top or not any(c.get("text") for c in top):
        return []
    prompt = _build_prompt(note_title, comments)
    if llm_call is None:
        from core.writer import _call_api, _extract_content
        data = _call_api(
            messages=[{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=1200,
        )
        raw = _extract_content(data)
    else:
        raw = llm_call(prompt)
    return _parse_topics(raw)


# ═══════════════════════════════════════════════════════════
# 评论采集
# ═══════════════════════════════════════════════════════════

def _comment_text(c: dict) -> tuple[str, int]:
    """从评论 dict 提取 (文本, 点赞数)。XHS 评论字段名兼容。"""
    text = c.get("content") or c.get("text") or ""
    likes = c.get("like_count", c.get("likes", 0))
    try:
        likes = int(likes)
    except (ValueError, TypeError):
        likes = 0
    return text, likes


def fetch_own_notes(api: XHS_Apis, max_notes: int = 10) -> list[dict]:
    """拉取自己最近发布的笔记（含 xsec_token，用于拉评论）。"""
    success, msg, me = api.get_user_me()
    if not success or not me:
        logger.error("get_user_me 失败: %s", msg)
        return []
    user_id = (me.get("data", {}) or {}).get("user_id") or (me.get("data", {}) or {}).get("userid")
    if not user_id:
        logger.error("未能从 get_user_me 提取 user_id")
        return []

    notes: list[dict] = []
    cursor = ""
    for _ in range(10):  # 最多翻 10 页
        success, msg, res = api.get_user_note_info(user_id, cursor)
        if not success or not res:
            break
        data = res.get("data", {}) or {}
        for item in data.get("notes", []):
            notes.append({
                "note_id": item.get("note_id") or item.get("id", ""),
                "title": item.get("display_title") or item.get("title", "") or "（无标题）",
                "xsec_token": item.get("xsec_token", ""),
            })
        if not data.get("has_more", False):
            break
        cursor = data.get("cursor", "")
        if not cursor:
            break
    return notes[:max_notes]


def fetch_comments(api: XHS_Apis, note: dict) -> list[dict]:
    """拉单篇笔记的一级评论，返回 [{text, likes}, ...]。"""
    note_id = note["note_id"]
    token = note.get("xsec_token", "")
    success, msg, raw_comments = api.get_note_all_out_comment(note_id, token)
    if not success:
        logger.warning("拉评论失败 %s: %s", note_id, msg)
        return []
    result = []
    for c in raw_comments:
        text, likes = _comment_text(c)
        if text:
            result.append({"text": text, "likes": likes})
    return result


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="评论洞察 - 从真实评论挖选题")
    parser.add_argument("--max", type=int, default=10, help="最多分析最近几篇笔记的评论")
    parser.add_argument("--save", action="store_true", help="挖出的选题写入 data/topics.json")
    args = parser.parse_args()

    logger.info("正在登录小红书PC端...")
    auth = get_pc_auth()
    api = XHS_Apis(auth).bootstrap()

    notes = fetch_own_notes(api, max_notes=args.max)
    if not notes:
        logger.info("未拉到自己发布的笔记")
        return
    logger.info("拉到 %d 篇笔记，开始采评论...", len(notes))

    all_topics = []
    for i, note in enumerate(notes, 1):
        comments = fetch_comments(api, note)
        logger.info("[%d/%d] %s -> %d 条评论", i, len(notes), note["title"][:30], len(comments))
        if len(comments) < 3:
            continue  # 评论太少不值得挖
        try:
            topics = extract_topics_from_comments(note["title"], comments)
        except Exception as e:
            logger.warning("LLM 提取失败 %s: %s", note["title"][:30], e)
            continue
        for t in topics:
            t["source"] = "comment_insight"
            t["source_note_id"] = note["note_id"]
            t["source_note_title"] = note["title"]
            t["status"] = "pending"
            all_topics.append(t)
            print(f"  💬 选题: {t.get('topic', '')}（争议点: {t.get('controversy_point', '')}）")

    if not all_topics:
        print("未从评论中挖到选题（评论太少或无争论点）")
        return

    print(f"\n共挖出 {len(all_topics)} 个选题。")
    if args.save:
        topics_data = load_topics_json()
        topics_data.setdefault("topics", []).extend(all_topics)
        save_topics_json(topics_data)
        logger.info("已写入 data/topics.json（带 source=comment_insight 徽标）")
    else:
        print("加 --save 可写入选题池。")


if __name__ == "__main__":
    main()
