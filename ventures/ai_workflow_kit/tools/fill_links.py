# -*- coding: utf-8 -*-
"""一条命令回填面包多链接，把分发弹药库从 95% 就绪变成 100% 就绪。

用法：
    python scripts/fill_links.py https://mbd.pub/o/bread/xxxx [--author 店铺主页URL]

做什么：
1. launch-cn-distribution.md：按渠道分节回填带统计尾缀的链接
   （?from=wechat / zhihu-a / zhihu-b / jike / xhs-dm ...，4 周对账时分辨来单渠道）
2. docs/回本计划_codingplan.md：记账表里的"链接待回填"替换为真实链接
3. 幂等：重复跑会先清掉旧链接/占位符再填新的

跑完只剩 4 个人工粘贴动作（发到你自己的社交账号，物理上只能你做）。
"""
import re
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]  # ventures/ai_workflow_kit
DIST = CASE / "products" / "ai-office-workflows" / "launch-cn-distribution.md"
PLAN = CASE / "docs" / "回本计划_codingplan.md"

PLACEHOLDER = "【面包多链接】"
# 面包多链接（含旧尾缀）的匹配：主机 + 路径 + 可选查询串。
# 路径字符排除空白/反引号/中文标点，防止吞掉 markdown 反引号和句读。
LINK_RE = re.compile(r"https?://(?:www\.)?(?:mbd\.pub|mianbaoduo\.com)/[^\s`'\"）】]，。；、]*")

# 分节 → 渠道尾缀（对应 md 里的 ## ① ... ## ⑦ 小节）
SECTION_TAG = {
    "①": "wechat",        # 朋友圈直给
    "②": "wechat-story",  # 朋友圈故事版
    "③": "dm",            # 私发同事
    "④": "zhihu-a",       # 知乎·周报题
    "⑤": "zhihu-b",       # 知乎·纪要题
    "⑥": "jike",          # 即刻
    "⑦": "xhs-dm",        # 小红书私信
}


def valid_url(u: str) -> bool:
    return bool(re.match(r"^https?://(?:www\.)?(?:mbd\.pub|mianbaoduo\.com)/\S+$", u))


def clean_url(u: str) -> str:
    """去掉旧查询串，得到裸链接。"""
    return u.split("?")[0].rstrip("/")


def fill_distribution(bare: str) -> int:
    text = DIST.read_text(encoding="utf-8")
    lines = text.split("\n")
    current = None
    filled = 0
    for i, line in enumerate(lines):
        m = re.match(r"^## ([①②③④⑤⑥⑦])", line)
        if m:
            current = m.group(1)
            continue
        if PLACEHOLDER in line or LINK_RE.search(line):
            tag = SECTION_TAG.get(current, "generic")
            new_line = re.sub(LINK_RE, f"{bare}?from={tag}", line)
            new_line = new_line.replace(PLACEHOLDER, f"{bare}?from={tag}")
            if new_line != line:
                filled += line.count(PLACEHOLDER) + len(LINK_RE.findall(line))
                lines[i] = new_line
    DIST.write_text("\n".join(lines), encoding="utf-8")
    return filled


def fill_plan(bare: str) -> bool:
    text = PLAN.read_text(encoding="utf-8")
    new = text.replace("（平台/过审状态待确认，链接待回填）", f"（购买链接：{bare}）")
    new = re.sub(r"（购买链接：https?://\S+?）", f"（购买链接：{bare}）", new)
    if new != text:
        PLAN.write_text(new, encoding="utf-8")
        return True
    return False


def main():
    if len(sys.argv) < 2 or not valid_url(sys.argv[1].strip()):
        print(__doc__)
        print("示例: python scripts/fill_links.py https://mbd.pub/o/bread/mbd-xxxxx")
        return 1
    bare = clean_url(sys.argv[1].strip())

    n = fill_distribution(bare)
    plan_updated = fill_plan(bare)

    print(f"✅ 弹药库回填 {n} 处（渠道尾缀已区分）；回本计划{'已更新' if plan_updated else '无需更新（已是该链接）'}")
    print("裸链接（店铺/通用场景用）:", bare)
    print()
    print("剩下 4 个粘贴动作（只能你做，共约 20 分钟）：")
    print("  1. 朋友圈：launch-cn-distribution.md §① 今天的，§② 第 2 周的")
    print("  2. 私发 3 个同事：§③")
    print("  3. 知乎找 2 个问题各答一题：§④§⑤（链接放文末+简介）")
    print("  4. 即刻：§⑥")
    return 0


if __name__ == "__main__":
    sys.exit(main())
