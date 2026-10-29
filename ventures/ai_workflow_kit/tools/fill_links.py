"""仅在本地分发草稿中回填面包多链接，不验证审核、不发布、不更新经营记录。

用法：
    python ventures/ai_workflow_kit/tools/fill_links.py https://mbd.pub/o/bread/xxxx

按渠道分节替换 launch-cn-distribution.md 的链接或占位符，重复执行保持幂等。
渠道参数仅是待核验标签，不证明点击、成交或平台审核通过。
实际渠道证据需由人工写入仓库 cockpit/actions.csv，历史计划保持不变。
"""
import re
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]  # ventures/ai_workflow_kit
REPO = Path(__file__).resolve().parents[3]
DIST = CASE / "products" / "ai-office-workflows" / "launch-cn-distribution.md"

PLACEHOLDER = "【面包多链接】"
# 面包多链接（含旧尾缀）的匹配：主机 + 路径 + 可选查询串。
# 排除 Markdown 边界及中文标点，替换时保留原始草稿结构。
LINK_RE = re.compile(r"https?://(?:www\.)?(?:mbd\.pub|mianbaoduo\.com)/[^\s`'\"）】\]，。；、<>)]+")

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


def main():
    if len(sys.argv) != 2 or not valid_url(sys.argv[1].strip()):
        print(__doc__)
        return 1
    bare = clean_url(sys.argv[1].strip())
    n = fill_distribution(bare)

    print(f"仅回填本地分发草稿 {n} 处（渠道尾缀已区分）。")
    print("链接存在不代表平台审核通过；公开话术须人工复核，本工具不会自动发布。")
    print("实际渠道证据请人工写入:", REPO / "cockpit" / "actions.csv")
    print("历史计划和经营记录未修改；不自动记录发布、成交或经营成功。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
