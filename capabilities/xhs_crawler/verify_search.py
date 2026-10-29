"""小红书站内实测：验证「剪映模板/婚礼视频」供需与价格带（2026-10-15）。

BOSS 观察待验证：① 剪映模板私卖供给密集；② 婚礼模板 20-200 元/份；
③ 整片制作报价 200+。本脚本用 PC 端搜索 API 采集真实笔记数据。

用法：python capabilities/xhs_crawler/verify_search.py（显式采集才联网）
输出：案例data/xhs_jianying_verify_时间戳.json；不覆盖历史证据，不保存临时认证参数
"""
import contextlib
import json
import re
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from statistics import median

PROJECT_ROOT = Path(__file__).resolve().parents[2]      # 仓库根（.env/.cache 所在）
CAP_DIR = Path(__file__).resolve().parent               # capabilities/xhs_crawler

# vendor/认证模块只在显式运行 main 时导入，数字解析可纯离线导入。
OUT = (PROJECT_ROOT / "ventures" / "jianying_templates" / "data"
       / f"xhs_jianying_verify_{datetime.now():%Y%m%d_%H%M%S_%f}.json")

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


def to_int(value) -> int | None:
    """解析非负互动数（万/w/k/千、千分位、末尾 +）；未知与布尔均为 None。

    + 保留展示数值，不能据此推断精确计数；不能解释成整数的值不截断为 0。
    """
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (str, int, float, Decimal)):
        return None
    match = re.fullmatch(
        r"([0-9]{1,3}(?:[,，][0-9]{3})+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)\s*([万wWkK千]?)\+?",
        str(value).strip(),
    )
    if not match:
        return None
    number, unit = match.groups()
    multiplier = {"万": 10000, "w": 10000, "k": 1000, "千": 1000}.get(unit.lower(), 1)
    count = Decimal(number.replace(",", "").replace("，", "")) * multiplier
    return int(count) if count == count.to_integral_value() else None


def interaction_count(inter: dict, *keys: str) -> int | None:
    """优先 *_count；liked/collected 可能只是当前用户的布尔状态。"""
    for key in keys:
        count = to_int(inter.get(key))
        if count is not None:
            return count
    return None


def parse_search_item(note: dict) -> dict:
    """从搜索结果条目提取可拿到的字段，缺失/布尔互动数不回填为零。"""
    card = note.get("note_card") or note
    inter = card.get("interact_info")
    inter = inter if isinstance(inter, dict) else {}
    user = card.get("user") or {}
    ts = card.get("time") or note.get("time")
    return {
        "id": note.get("id") or card.get("note_id"),
        "xsec_token": note.get("xsec_token") or "",
        "title": card.get("display_title") or "",
        "user": user.get("nickname") or user.get("nick_name") or "",
        "type": card.get("type") or note.get("type") or "",
        "likes": interaction_count(inter, "liked_count", "liked"),
        "collects": interaction_count(inter, "collected_count", "collected"),
        "comments": interaction_count(inter, "comment_count", "comment"),
        "ts": ts,
        "title_price_signal": bool(PRICE_RE.search(card.get("display_title") or "")),
    }


def parse_detail_metrics(detail) -> dict:
    """直接解析原始详情，避免共享 NoteRecord 的缺失值→0 行为污染研究统计。"""
    data = detail.get("data", detail) if isinstance(detail, dict) else {}
    data = data if isinstance(data, dict) else {}
    items = data.get("items")
    item = items[0] if isinstance(items, list) and items else data
    card = item.get("note_card", item) if isinstance(item, dict) else {}
    card = card if isinstance(card, dict) else {}
    counts = parse_search_item({"note_card": card})
    tags = card.get("tag_list") or []
    return {
        "detail_likes": counts["likes"],
        "detail_collects": counts["collects"],
        "detail_comments": counts["comments"],
        "tags": [t["name"] for t in tags if isinstance(t, dict) and t.get("name")][:8],
    }


def like_sort_key(item):
    count = to_int(item.get("likes"))
    return (count is not None, count if count is not None else -1)


def likes_summary(items):
    counts = [to_int(item.get("likes")) for item in items]
    known = [count for count in counts if count is not None]
    return {
        "likes_known": len(known), "likes_unknown": len(counts) - len(known),
        "likes_max": max(known) if known else None,
        "likes_median": median(known) if known else None,
    }


def format_count(value):
    count = to_int(value)
    return str(count) if count is not None else "未知"


def main():
    if OUT.exists():
        raise FileExistsError("Refusing to overwrite research evidence")
    sys.path.insert(0, str(CAP_DIR / "vendor"))
    sys.path.insert(0, str(CAP_DIR))
    import os

    import qrcode as _qrcode_mod
    from spider_xhs import XHS_Apis
    from xhs_auth_helper import get_pc_auth

    # Windows GBK 终端的 ASCII 二维码改存 PNG；仅显式实测时安装此补丁。
    # add_data 抓链接，print_ascii 时用 box_size=12 重绘（登录代码自带的图过小）。
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
        with contextlib.suppress(Exception):
            os.startfile(str(p))

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
            print("搜索失败；原始错误响应不写日志或证据，避免携带认证参数")
            report["queries"].append({"query": query, "sort": sort_name, "error": "search_failed"})
            time.sleep(5)
            continue

        items = [parse_search_item(n) for n in notes if n.get("model_type") == "note"]
        items = [i for i in items if i["id"]]

        # 取互动最高的 3 条抓详情（正文里找价格证据），未知值排在已知零之后。
        ranked = sorted(items, key=like_sort_key, reverse=True)
        for top in ranked[:3]:
            time.sleep(3)
            url = f"https://www.xiaohongshu.com/explore/{top['id']}"
            if top.get("xsec_token"):
                url += f"?xsec_token={top['xsec_token']}"
            ok, m2, detail = api.get_note_info(url)
            if ok:
                top.update(parse_detail_metrics(detail))
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
                top["detail_error"] = "detail_failed"

        q_entry = {
            "query": query,
            "sort": sort_name,
            "n_notes": len(items),
            **likes_summary(items),
            "title_price_signal_rate": (
                round(sum(1 for i in items if i["title_price_signal"]) / len(items), 2)
                if items else None
            ),
            "items": [{k: value for k, value in item.items() if k != "xsec_token"} for item in items],
        }
        report["queries"].append(q_entry)
        print(f"  有效笔记 {len(items)} 条 | 点赞中位 {q_entry['likes_median']} | "
              f"最高 {q_entry['likes_max']} | 点赞未知 {q_entry['likes_unknown']} 条 | "
              f"标题带转化信号比例 {q_entry['title_price_signal_rate']}")
        for i in ranked[:5]:
            print(f"    [{format_count(i['likes']):>6}赞] {i['title'][:36]} @{i['user'][:12]}")
        time.sleep(5)

    with OUT.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"\n完整数据 -> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
