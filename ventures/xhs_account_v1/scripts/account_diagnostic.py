#!/usr/bin/env python3
"""
账号体检脚本 - 5 维定性诊断 + 粉丝快照
======================================

用法:
    python scripts/account_diagnostic.py            # 体检并打印结论
    python scripts/account_diagnostic.py --save     # 结论沉淀到知识库 account 记录

与 tabs/analytics.py 的区别：analytics 是「监控」（看 C 级连击 / 公式分布），
本脚本是「诊断」--5 维评分 + 最大优势 / 最大短板 / 下一步动作，用 performance.json
数字当 LLM 诊断的证据输入，给出"为什么 + 改什么"。

5 维：定位清晰度 / 内容结构力 / 互动转化力 / 账号辨识度 / 增长可持续性。
粉丝快照走 core.fans_history.snapshot_fans（get_user_me）。
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.config import get_logger, load_performance_json
from core.fans_history import snapshot_fans
from core.knowledge_base import write_record
from core.utils import extract_json_from_llm

logger = get_logger(__name__)

from scripts.xhs_auth_helper import get_pc_auth
from spider_xhs import XHS_Apis

_DIMENSIONS = ["定位清晰度", "内容结构力", "互动转化力", "账号辨识度", "增长可持续性"]

_SYSTEM = "你是小红书账号诊断专家，基于数据给定性结论，不说空话。"

_PROMPT_TMPL = """以下是这个小红书情感账号的真实数据快照：

{snapshot}

请从 5 个维度给账号打分（每维 1-5 分，1=明显缺失，3=基本合格，5=形成明显优势可当模板）：
{dims}

每个维度给 1-5 分 + 一句原因。然后给出：
- biggest_strength: 最大优势（最该放大的）
- biggest_weakness: 最大短板（下一步最优先修的）
- next_actions: 3 条优先级动作

严格按 JSON 输出（不要其他内容）：
{{
  "dimensions": {{
    "定位清晰度": {{"score": 4, "reason": "..."}},
    "内容结构力": {{"score": 3, "reason": "..."}},
    "互动转化力": {{"score": 2, "reason": "..."}},
    "账号辨识度": {{"score": 3, "reason": "..."}},
    "增长可持续性": {{"score": 3, "reason": "..."}}
  }},
  "biggest_strength": "...",
  "biggest_weakness": "...",
  "next_actions": ["动作1", "动作2", "动作3"]
}}"""


def build_snapshot(performance: dict, fans: int | None) -> dict:
    """从 performance.json + 粉丝数构造体检快照（LLM 的证据输入）。"""
    notes = performance.get("notes", [])
    summary = performance.get("summary", performance.get("stats", {}))
    grade_dist = summary.get("grade_distribution", {}) or {}
    # 取最近 10 篇笔记标题 + 等级 + 互动
    recent = sorted(notes, key=lambda n: n.get("updated_at", ""), reverse=True)[:10]
    recent_brief = [
        {
            "title": n.get("topic", n.get("title", "")),
            "grade": n.get("grade", "?"),
            "likes": n.get("likes", 0),
            "comments": n.get("comments", 0),
            "formula": n.get("title_formula", ""),
            "pillar": n.get("pillar", ""),
        }
        for n in recent
    ]
    return {
        "fans": fans,
        "total_notes": len(notes),
        "avg_likes": summary.get("avg_likes", 0),
        "grade_distribution": grade_dist,
        "recent_notes": recent_brief,
    }


def diagnose_account(snapshot: dict, llm_call=None) -> dict:
    """LLM 5 维诊断。返回解析后的 dict（失败返回空 dict）。"""
    import json
    prompt = _PROMPT_TMPL.format(snapshot=json.dumps(snapshot, ensure_ascii=False, indent=2), dims=" / ".join(_DIMENSIONS))
    if llm_call is None:
        from core.writer import _call_api, _extract_content
        data = _call_api(
            messages=[{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=1500,
        )
        raw = _extract_content(data)
    else:
        raw = llm_call(prompt)
    parsed = extract_json_from_llm(raw)
    return parsed if isinstance(parsed, dict) else {}


def print_report(diagnosis: dict, fans: int | None) -> None:
    print("\n" + "=" * 60)
    print("🩺 账号体检报告" + (f"（当前粉丝 {fans}）" if fans is not None else ""))
    print("=" * 60)
    dims = diagnosis.get("dimensions", {})
    for name in _DIMENSIONS:
        d = dims.get(name, {})
        score = d.get("score", "?")
        reason = d.get("reason", "")
        bar = "⬛" * (score if isinstance(score, int) else 0) + "⬜" * (5 - (score if isinstance(score, int) else 0))
        print(f"  {name} {bar} {score}/5  {reason}")
    print(f"\n💪 最大优势: {diagnosis.get('biggest_strength', '-')}")
    print(f"⚠️ 最大短板: {diagnosis.get('biggest_weakness', '-')}")
    actions = diagnosis.get("next_actions", [])
    if actions:
        print("\n🎯 下一步动作:")
        for i, a in enumerate(actions, 1):
            print(f"  {i}. {a}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="账号体检 - 5 维诊断 + 粉丝快照")
    parser.add_argument("--save", action="store_true", help="结论沉淀到知识库 account 记录")
    parser.add_argument("--no-fetch", action="store_true", help="不登录采集粉丝数（只用已有 performance 数据诊断）")
    args = parser.parse_args()

    performance = load_performance_json()
    fans = None
    if not args.no_fetch:
        try:
            auth = get_pc_auth()
            api = XHS_Apis(auth).bootstrap()
            fans = snapshot_fans(api)
        except Exception as e:
            logger.warning("粉丝快照失败（继续诊断）: %s", e)

    snapshot = build_snapshot(performance, fans)
    if not snapshot["recent_notes"]:
        print("performance.json 无笔记数据，先跑 fetch_performance.py 采数再诊断。")
        return

    try:
        diagnosis = diagnose_account(snapshot)
    except Exception as e:
        logger.error("LLM 诊断失败: %s", e)
        return

    print_report(diagnosis, fans)

    if args.save and diagnosis:
        write_record(
            "account",
            summary=f"账号体检：粉丝 {fans}，{len(snapshot['recent_notes'])} 篇近期笔记",
            body=f"## 最大优势\n{diagnosis.get('biggest_strength','')}\n\n## 最大短板\n{diagnosis.get('biggest_weakness','')}\n\n## 下一步\n"
                 + "\n".join(f"- {a}" for a in diagnosis.get("next_actions", [])),
            fans=fans if fans is not None else 0,
            total_notes=snapshot["total_notes"],
            avg_likes=snapshot["avg_likes"],
            tags=["account-diagnostic"],
        )
        logger.info("已沉淀到知识库 account 记录")


if __name__ == "__main__":
    main()
