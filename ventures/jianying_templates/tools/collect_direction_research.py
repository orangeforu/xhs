"""Bounded, read-only XHS interest sampling; NOT Jianying earnings data.

Uses the existing saved PC authentication without replacing it or starting login.
Stops on first API failure; saves no cookies or xsec tokens. Output never overwrites.
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
import re
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / "data" / "direction_research_20261028.json"
QUERIES = [
    ("热点卡点", "剪映卡点模板"), ("热点卡点", "剪映热门模板"),
    ("宠物一图", "剪映宠物模板"), ("宠物一图", "宠物一图模板"),
    ("生日纪念", "剪映生日模板"), ("生日纪念", "生日相册模板"),
    ("商家商品", "剪映商家模板"), ("商家商品", "剪映商品展示模板"),
    ("知识数据", "剪映数据图表"), ("知识数据", "剪映知识科普模板"),
    ("旅行日常", "剪映旅行模板"), ("旅行日常", "剪映日常vlog模板"),
]


def number(value):
    """Preserve missing values; booleans are user state, not engagement counts."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([万wW千kK]?)",
                         str(value).replace(",", "").replace("+", "").strip())
    if not match:
        return None
    factor = {"万": 10000, "w": 10000, "W": 10000,
              "千": 1000, "k": 1000, "K": 1000, "": 1}[match[2]]
    return int(Decimal(match[1]) * factor)


def text(value):
    value = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已省略]", str(value or ""))
    return value[:5000]


def find_card(obj):
    if isinstance(obj, dict):
        if isinstance(obj.get("note_card"), dict):
            return obj["note_card"]
        if "desc" in obj and ("title" in obj or "note_id" in obj):
            return obj
        for value in obj.values():
            found = find_card(value)
            if found:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = find_card(value)
            if found:
                return found
    return None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    csv_path = OUT.with_suffix(".csv")
    if OUT.exists() or csv_path.exists():
        raise FileExistsError("Refusing to overwrite existing research")
    sys.path.insert(0, str(ROOT / "capabilities/xhs_crawler/vendor"))
    report = {
        "retrieved_at": datetime.now(UTC).isoformat(),
        "platform": "小红书PC搜索（不是剪映模板收益）",
        "sample_design": "6方向×2关键词×综合/最新，每组合取前10条有效笔记；每方向最多2条详情；便利样本非随机样本",
        "limitations": ["搜索排序受关键词与账号等影响", "互动不等于付费意愿或模板收入",
                        "跨方向关键词有污染，需人工判定内容类型", "不推算销量、转化率、收益或模板年龄"],
        "queries": [], "details": [],
    }
    quiet = io.StringIO()
    with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
        from spider_xhs import XHS_Apis, XHSPcAuth
        cookie = json.loads((ROOT / ".cache/xhs_pc_cookie.json").read_text(encoding="utf-8"))["cookies"]
        api = XHS_Apis(XHSPcAuth.from_cookie(cookie))
    tokens = {}
    stopped = False
    for direction, query in QUERIES:
        if stopped:
            break
        for sort in [0, 1]:
            entry = {"direction": direction, "query": query, "sort": "综合" if sort == 0 else "最新",
                     "captured_at": datetime.now(UTC).isoformat(), "items": []}
            try:
                with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
                    ok, _message, res = api.search_note(query, page=1, sort_type_choice=sort, note_type=0)
                entry["success"] = bool(ok)
                if not ok:
                    entry["error"] = "API returned failure; stopped without retry or reauthentication"
                    stopped = True
                else:
                    for note in ((res or {}).get("data") or {}).get("items") or []:
                        card = note.get("note_card") or {}
                        nid = note.get("id")
                        if not nid or not card or note.get("model_type") not in (None, "note"):
                            continue
                        inter, user = card.get("interact_info") or {}, card.get("user") or {}
                        tokens[nid] = note.get("xsec_token") or ""
                        entry["items"].append({
                            "id": nid, "title": text(card.get("display_title")),
                            "author_id": user.get("user_id") or user.get("id"),
                            "author": text(user.get("nickname") or user.get("nick_name")),
                            "type": card.get("type"), "likes": number(inter.get("liked_count")),
                            "collects": number(inter.get("collected_count")),
                            "comments": number(inter.get("comment_count")),
                            "shares": number(inter.get("shared_count")),
                            "source_url": "https://www.xiaohongshu.com/explore/" + nid,
                            "corner_tag": card.get("corner_tag_info"),
                        })
                        if len(entry["items"]) >= 10:
                            break
            except Exception as exc:
                entry["success"] = False
                entry["error_type"] = type(exc).__name__
                stopped = True
            report["queries"].append(entry)
            print(direction, query, entry["sort"], len(entry["items"]), flush=True)
            if stopped:
                break
            time.sleep(1)  # Deliberate request pacing, not retry polling.
    if not stopped:
        for direction in dict.fromkeys(d for d, _ in QUERIES):
            candidates = {r["id"]: r for q in report["queries"]
                          if q["direction"] == direction and q["sort"] == "综合" for r in q["items"]}
            ranked = sorted(candidates.values(), key=lambda r: r["likes"] if r["likes"] is not None else -1)
            chosen = [ranked[len(ranked) // 2], ranked[-1]] if ranked else []
            for rec in {r["id"]: r for r in chosen}.values():
                detail = {"direction": direction, "id": rec["id"], "source_url": rec["source_url"]}
                url = rec["source_url"]
                if tokens.get(rec["id"]):
                    url += "?xsec_token=" + tokens[rec["id"]]
                try:
                    with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
                        ok, _message, data = api.get_note_info(url)
                    detail["success"] = bool(ok)
                    if ok:
                        card = find_card(data) or {}
                        detail.update({
                            "title": text(card.get("title")), "desc": text(card.get("desc")),
                            "published_timestamp": card.get("time"),
                            "last_update_timestamp": card.get("last_update_time"),
                            "interact_info": {k: number(v) for k, v in (card.get("interact_info") or {}).items()
                                              if k.endswith("_count")},
                            "tags": [text(t.get("name")) for t in card.get("tag_list", []) if isinstance(t, dict)],
                        })
                except Exception as exc:
                    detail["success"] = False
                    detail["error_type"] = type(exc).__name__
                report["details"].append(detail)
                print("DETAIL", direction, rec["id"], detail["success"], flush=True)
                if not detail["success"]:
                    stopped = True
                    break
                time.sleep(1)
            if stopped:
                break
    report["stopped_early"] = stopped
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = ["direction", "query", "sort", "id", "title", "author_id", "author", "type",
              "likes", "collects", "comments", "shares", "source_url"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for query in report["queries"]:
            for row in query["items"]:
                writer.writerow({k: query[k] if k in ("direction", "query", "sort") else row.get(k)
                                 for k in fields})
    print("SAVED", OUT, "rows", sum(len(q["items"]) for q in report["queries"]),
          "details", len(report["details"]), "stopped_early", stopped)


if __name__ == "__main__":
    main()
