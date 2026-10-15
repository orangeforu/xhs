# -*- coding: utf-8 -*-
"""小红书站内实测：验证「剪映模板/婚礼视频」供需与价格带（2026-10-15）。

BOSS 观察待验证：① 剪映模板私卖供给密集；② 婚礼模板 20-200 元/份；
③ 整片制作报价 200+。本脚本用 PC 端搜索 API 采集真实笔记数据。

用法：python scripts/verify_xhs_jianying.py
输出：data/xhs_jianying_verify.json + 终端摘要
"""
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from spider_xhs import XHS_Apis
from scripts.xhs_auth_helper import get_pc_auth
from core.note_schema import NoteRecord

OUT = PROJECT_ROOT / "data" / "xhs_jianying_verify.json"

# (query, sort_type_choice, note_type, require_num)
# sort: 0综合 1最新 2最多点赞 | type: 0不限 1视频 2图文
SEARCHES = [
    ("婚礼视频模板", 0, 0, 15),
    ("婚礼视频模板", 1, 0, 12),  # 最新：看供给更新速度
    ("剪映模板", 0, 0, 12),
    ("婚礼视频剪辑", 0, 0, 12),
]

PRICE_RE = re.compile(
    r"(\d{2,4})\s*(?:元|块|r)|¥\s*(\d{2,4})|报价|接单|定制|代做|私信|评论区|[扣+]\s*[1想要]|同款|素材包|教程"
)


def parse_search_item(note: dict) -> dict:
    """从搜索结果条目提取可拿到的字段（防御式：扁平/嵌套两种结构都试）。"""
    card = note.get("note_card") or note
    inter = card.get("interact_info") or {}
    user = card.get("user") or {}
    ts = card.get("time") or note.get("time")
    return {
        "id": note.get("id") or card.get("note_id"),
        "xsec_token": note.get("xsec_token") or "",
        "title": card.get("display_title") or "",
        "user": user.get("nickname") or user.get("nick_name") or "",
        "type": card.get("type") or note.get("type") or "",
        "likes": inter.get("liked") or inter.get("liked_count") or "0",
        "collects": inter.get("collected") or "0",
        "comments": inter.get("comment") or inter.get("comment_count") or "0",
        "ts": ts,
        "title_price_signal": bool(PRICE_RE.search(card.get("display_title") or "")),
    }


def to_int(v):
    try:
        return int(str(v).replace("万", "0000").replace("+", "").strip() or 0)
    except Exception:
        return 0


def main():
    # Windows GBK 终端打不出 ASCII 二维码：patch 成存 PNG 并自动打开（同 xhs_auth_helper 手法）
    import os

    import spider_xhs.apis.xhs_pc_login_apis as pc_login_mod

    # 劫持 qrcode.QRCode：add_data 抓链接，print_ascii 时用 box_size=12 重绘大图
    # （登录代码自带 box_size=1，35px 小图手机扫不动），存 PNG 并自动打开
    import qrcode as _qrcode_mod

    _qr_url_holder = {}

    def _add_data_spy(self, data, *args, **kwargs):
        _qr_url_holder["url"] = data
        return self._orig_add_data(data, *args, **kwargs)

    _qrcode_mod.QRCode._orig_add_data = _qrcode_mod.QRCode.add_data
    _qrcode_mod.QRCode.add_data = _add_data_spy

    def _print_ascii_png(self, *args, **kwargs):
        url = _qr_url_holder.get("url") or ""
        p = PROJECT_ROOT / ".cache" / "xhs_pc_qrcode.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        big = _qrcode_mod.QRCode(box_size=12, border=4)
        big.add_data(url)
        big.make(fit=True)
        big.make_image(fill_color="black", back_color="white").save(str(p))
        print(f"[verify] 二维码已保存并打开: {p}（小红书APP扫码，5分钟内有效）")
        try:
            os.startfile(str(p))
        except Exception:
            pass

    _qrcode_mod.QRCode.print_ascii = _print_ascii_png
    print("[verify] print_ascii 劫持已安装（大图版）")

    auth = get_pc_auth()
    api = XHS_Apis(auth).bootstrap()

    report = {"run_at": datetime.now().isoformat(), "queries": []}

    for query, sort_by, note_type, num in SEARCHES:
        sort_name = {0: "综合", 1: "最新", 2: "最多点赞"}[sort_by]
        print(f"\n=== 搜索: {query}（{sort_name}排序，{num}条） ===", flush=True)
        success, msg, notes = api.search_some_note(
            query=query, require_num=num, sort_type_choice=sort_by, note_type=note_type
        )
        if not success:
            print(f"搜索失败: {msg}")
            report["queries"].append({"query": query, "sort": sort_name, "error": msg})
            time.sleep(5)
            continue

        items = [parse_search_item(n) for n in notes if n.get("model_type") == "note"]
        items = [i for i in items if i["id"]]

        # 取互动最高的 3 条抓详情（正文里找价格证据）
        ranked = sorted(items, key=lambda i: to_int(i["likes"]), reverse=True)
        for top in ranked[:3]:
            time.sleep(3)
            url = f"https://www.xiaohongshu.com/explore/{top['id']}"
            if top.get("xsec_token"):
                url += f"?xsec_token={top['xsec_token']}"
            ok, m2, detail = api.get_note_info(url)
            if ok:
                try:
                    rec = NoteRecord.from_api_detail(detail, note_id=top["id"], url=url)
                    top["detail_likes"] = rec.likes
                    top["detail_collects"] = rec.collects
                    top["detail_comments"] = rec.comments
                    top["tags"] = rec.tags[:8]
                except Exception:
                    pass
                desc = ""

                def _find_desc(o, depth=0):
                    """在 detail['data'] 结构里递归找 desc 字段。"""
                    if depth > 4 or o is None:
                        return ""
                    if isinstance(o, dict):
                        if o.get("desc"):
                            return str(o["desc"])
                        for v in o.values():
                            r = _find_desc(v, depth + 1)
                            if r:
                                return r
                    elif isinstance(o, list):
                        for v in o[:5]:
                            r = _find_desc(v, depth + 1)
                            if r:
                                return r
                    return ""

                if isinstance(detail, dict):
                    desc = _find_desc(detail.get("data")) or _find_desc(detail)
                top["desc_head"] = desc[:200]
                prices = re.findall(r"(?:¥|价[格位]?[约?]?)\s*(\d{2,4}(?:\.\d+)?)|\b(\d{2,4})\s*元", desc)
                top["desc_prices"] = [p[0] or p[1] for p in prices][:8]
                top["desc_funnel"] = bool(
                    re.search(r"私信|评论区|扣[一1]|微信|接单|定制|代做|闲鱼", desc)
                )
            else:
                top["detail_error"] = m2

        likes = [to_int(i["likes"]) for i in items]
        q_entry = {
            "query": query,
            "sort": sort_name,
            "n_notes": len(items),
            "likes_max": max(likes) if likes else 0,
            "likes_median": sorted(likes)[len(likes) // 2] if likes else 0,
            "title_price_signal_rate": (
                round(sum(1 for i in items if i["title_price_signal"]) / len(items), 2)
                if items else 0
            ),
            "items": items,
        }
        report["queries"].append(q_entry)
        print(f"  有效笔记 {len(items)} 条 | 点赞中位 {q_entry['likes_median']} | "
              f"最高 {q_entry['likes_max']} | 标题带转化信号比例 {q_entry['title_price_signal_rate']}")
        for i in ranked[:5]:
            print(f"    [{to_int(i['likes']):>6}赞] {i['title'][:36]} @{i['user'][:12]}")
        time.sleep(5)

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完整数据 -> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
