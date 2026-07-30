#!/usr/bin/env python3
"""
爆款复刻脚本 - 输入爆款 URL，复刻结构产出可发布笔记
====================================================

用法:
    python scripts/replicate_viral.py "https://www.xiaohongshu.com/explore/XXXXX"

与 competitor_analysis.py 的区别：竞品分析只产出「选题建议」写进 topics.json；
本脚本输入一篇爆款 URL -> 拆解 5 个模板（标题/封面/正文/互动/标签）-> 产出符合
brief schema 的 enriched brief -> 直接喂 Orchestrator.run 走完整多 Agent 流水线
（写手/封面/排版/审核/评论），产出可发布的成稿。

copy_mode=style-only（默认）：保留标题句式与互动机制，重写措辞与案例。
ChiefEditor 相似度硬门禁（copy_overlap_ratio>40%）拦截逐句照抄。
源笔记模板同时沉淀到知识库 pattern 记录。
"""

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.config import get_logger, PENDING_DIR
from core.utils import extract_json_from_llm
from core.note_schema import NoteRecord, _get_note_card
from core.knowledge_base import write_record

logger = get_logger(__name__)

from spider_xhs import XHS_Apis
from scripts.xhs_auth_helper import get_pc_auth


_SYSTEM = "你是小红书爆款拆解专家，把一篇爆款拆成可复用模板，再转化成同赛道新选题的 brief。"

_PROMPT_TMPL = """以下是爆款笔记的拆解素材：

标题：{title}
正文：{desc}
标签：{tags}

请拆解 5 个模板（标题句式 / 封面信息层级 / 正文结构 / 互动机制 / 标签组合），
然后基于这些模板生成一个**同赛道但全新**的选题 brief（不要照抄原文措辞和案例）。

严格按 JSON 输出（不要其他内容）：
{{
  "templates": {{
    "title_template": "标题句式抽象，如「被___惊到了」",
    "cover_template": "封面信息层级描述",
    "body_template": "正文结构描述",
    "interaction_template": "互动机制描述",
    "tag_template": "标签组合"
  }},
  "brief": {{
    "topic": "新选题（一句话）",
    "title_formula": "问句式|概念解读式|观点冲击式|方法承诺式",
    "angle": "切入角度",
    "story_prototype": "故事原型（具体场景）",
    "controversy_anchor": "争议锚点（可站队的判断）",
    "visual_style": "warm_grey|twilight|crimson|mist|cool",
    "tags": ["不懂就问有问必答", "标签2", "标签3"]
  }}
}}"""


def deconstruct_to_brief(source_title: str, source_desc: str, source_tags: list[str], llm_call=None) -> dict | None:
    """LLM 拆解爆款 -> 返回 {templates, brief}。失败返回 None。"""
    prompt = _PROMPT_TMPL.format(
        title=source_title,
        desc=(source_desc or "")[:800],
        tags=" ".join(f"#{t}" for t in source_tags) or "（无）",
    )
    if llm_call is None:
        from core.writer import _call_api, _extract_content
        data = _call_api(
            messages=[{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=1500,
        )
        raw = _extract_content(data)
    else:
        raw = llm_call(prompt)
    parsed = extract_json_from_llm(raw)
    if not isinstance(parsed, dict) or "brief" not in parsed:
        return None
    return parsed


def build_brief_from_deconstruction(parsed: dict, source_url: str, source_desc: str) -> dict:
    """把拆解结果转成 Orchestrator 可消费的 brief（含 source_content 供相似度门禁）。"""
    brief = dict(parsed.get("brief", {}))
    brief["copy_mode"] = "style-only"
    brief["source_url"] = source_url
    brief["source_content"] = source_desc  # ChiefEditor 据此做相似度硬门禁
    brief.setdefault("target_interaction", "点赞+收藏")
    brief.setdefault("keywords", brief.get("tags", []))
    if "visual_style" in brief:  # CoverDesigner 读 visual_direction
        brief["visual_direction"] = brief["visual_style"]
    return brief


def main():
    parser = argparse.ArgumentParser(description="爆款复刻 - URL -> 成稿")
    parser.add_argument("url", help="爆款笔记 URL")
    parser.add_argument("--no-run", action="store_true", help="只拆解不跑流水线（打印 brief）")
    args = parser.parse_args()

    m = re.search(r"/explore/([a-zA-Z0-9]+)", args.url)
    if not m:
        logger.error("无法从 URL 提取笔记 ID: %s", args.url)
        return
    note_id = m.group(1)

    logger.info("正在登录小红书PC端...")
    auth = get_pc_auth()
    api = XHS_Apis(auth).bootstrap()

    success, msg, detail = api.get_note_info(args.url)
    if not success:
        logger.error("获取源笔记失败: %s", msg)
        return
    card = _get_note_card(detail)
    source_title = card.get("title", "")
    source_desc = card.get("desc", "")
    rec = NoteRecord.from_api_detail(detail, note_id=note_id, url=args.url)
    source_tags = rec.tags

    print(f"📦 源笔记：{source_title}（赞 {rec.likes}）")

    parsed = deconstruct_to_brief(source_title, source_desc, source_tags)
    if not parsed:
        logger.error("LLM 拆解失败")
        return

    print("\n🧩 拆解模板：")
    print(json.dumps(parsed.get("templates", {}), ensure_ascii=False, indent=2))

    brief = build_brief_from_deconstruction(parsed, args.url, source_desc)
    print("\n📝 新选题 brief：")
    print(json.dumps(brief, ensure_ascii=False, indent=2))

    # 沉淀源模板到知识库
    try:
        write_record(
            "pattern",
            summary=f"爆款拆解：{source_title[:40]}（赞{rec.likes}）",
            body=json.dumps(parsed.get("templates", {}), ensure_ascii=False, indent=2),
            grade="ref",
            title=source_title,
            title_formula=brief.get("title_formula", ""),
            visual_style=brief.get("visual_style", ""),
            tags=source_tags[:5],
            source_url=args.url,
        )
    except Exception as e:
        logger.warning("知识库写入失败（不影响主流程）: %s", e)

    if args.no_run:
        return

    # 跑完整多 Agent 流水线
    from core.agents.orchestrator import Orchestrator
    out_dir = str(PENDING_DIR / f"replicate_{note_id[:12]}")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    logger.info("启动多 Agent 流水线生成复刻笔记 -> %s", out_dir)
    result = Orchestrator().run(brief, out_dir)
    print(f"\n✅ 复刻完成: status={result.get('status')} rounds={result.get('rounds')} -> {out_dir}")


if __name__ == "__main__":
    main()
