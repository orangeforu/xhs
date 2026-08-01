#!/usr/bin/env python3
"""小红书创作系统 — 统一命令入口（中文触发词，不用记复杂脚本名）

用「记忆点 + 背后脚本」的方式把所有操作串起来。你只需记住中文动作词。

完整闭环（按顺序）:
    生成 → 审核 → 发布 → 采集

常用:
    python xhs 生成              # 启动 Streamlit 工作台（推荐，页面上做一切）
    python xhs 发布              # 一键发布 approved/ 里的笔记到小红书
    python xhs 采集              # 一键采集互动数据 + 竞品爆款灌进选题池
    python xhs 登录              # 登录/刷新小红书 Cookie（创作者端 + PC端）

全部命令:
    python xhs                   # 显示这个帮助菜单
    python xhs 生成 [N]          # 启动工作台；或直接生成第 N 篇（N=选题编号）
    python xhs 批量 [N]           # 批量生成 N 篇（默认3）
    python xhs 工作台             # 启动 Streamlit 审核发布工作台
    python xhs 发布 [N]           # 发布笔记（N=篇数，默认全部 approved）
    python xhs 采集 [--query 词] # 采集互动数据 + 竞品分析灌选题池
    python xhs 竞品 [词] [--max N]# 只做竞品爆款分析（不采集已发布数据）
    python xhs 登录              # 登录创作者端（发布用）
    python xhs 登录 PC           # 登录 PC 端（采集数据用）
    python xhs 诊断              # 账号诊断
    python xhs 评论              # 抓评论区洞察
    python xhs 复刻 [URL]         # 复刻指定爆款笔记
    python xhs 列表              # 列出选题池
"""
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
PY = sys.executable

# Windows GBK 终端打不出中文/emoji，强制 UTF-8
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _run(cmd: list[str]):
    """运行子命令。"""
    subprocess.run(cmd, cwd=str(PROJECT_ROOT))


def _streamlit():
    print("\n🚀 启动 Streamlit 工作台...")
    print("浏览器打开 http://localhost:8501")
    print("页面上能完成：选题筛选/生成/审核/发布/数据复盘，全程不用命令行。\n")
    _run([PY, "-m", "streamlit", "run", "app.py"])


def _generate(args):
    if not args:
        _streamlit()
        return
    # xhs 生成 3 → 生成第3篇
    if args[0].isdigit():
        print(f"\n生成第 {args[0]} 篇笔记...\n")
        _run([PY, "pipeline.py", "--index", args[0]])
    else:
        _streamlit()


def _batch(args):
    n = args[0] if args and args[0].isdigit() else "3"
    print(f"\n批量生成 {n} 篇笔记...\n")
    _run([PY, "pipeline.py", "--batch", "--max", n])


def _publish(args):
    n = args[0] if args and args[0].isdigit() else None
    cmd = [PY, "scripts/auto_publish.py"]
    if n:
        cmd += ["--limit", n]
        print(f"\n发布最多 {n} 篇笔记到小红书...\n")
    else:
        print("\n发布 approved/ 里所有笔记到小红书...\n")
    _run(cmd)


def _collect(args):
    print("\n采集已发布笔记互动数据 + 竞品爆款灌选题池...\n")
    cmd = [PY, "scripts/data_sync.py"]
    # 透传 --query / --skip-* 等参数
    cmd += [a for a in args if a.startswith("-")]
    _run(cmd)


def _competitor(args):
    print("\n竞品爆款分析...\n")
    cmd = [PY, "scripts/competitor_analysis.py", "--save"]
    # 找 query 词
    query = next((a for a in args if not a.startswith("-")), "")
    if query:
        cmd += ["--query", query]
    _run(cmd)


def _login(args):
    if args and args[0].upper() in ("PC", "pc"):
        print("\n登录小红书 PC 端（采集数据用）...\n")
        _run([PY, "scripts/xhs_auth_helper.py", "--pc"])
    else:
        print("\n登录小红书创作者端（发布用）...\n")
        _run([PY, "scripts/xhs_auth_helper.py", "--creator"])


def _diagnostic(args):
    print("\n账号诊断...\n")
    _run([PY, "scripts/account_diagnostic.py"])


def _comment(args):
    print("\n抓取评论区洞察...\n")
    _run([PY, "scripts/comment_insight.py"])


def _replicate(args):
    url = args[0] if args else ""
    cmd = [PY, "scripts/replicate_viral.py"]
    if url:
        cmd += [url]
    print(f"\n复刻爆款笔记{'：' + url if url else '...'}\n")
    _run(cmd)


def _list(args):
    _run([PY, "pipeline.py", "--list"])


COMMANDS = {
    "生成": ("启动工作台；或「生成 N」生成第 N 篇", _generate),
    "批量": ("批量生成 N 篇（默认3）", _batch),
    "工作台": ("启动 Streamlit 审核发布工作台", _streamlit),
    "发布": ("发布笔记到小红书（N=篇数）", _publish),
    "采集": ("采集互动数据 + 竞品爆款灌选题池", _collect),
    "竞品": ("只做竞品爆款分析（可带搜索词）", _competitor),
    "登录": ("登录创作者端（PC 端用「登录 PC」）", _login),
    "诊断": ("账号诊断", _diagnostic),
    "评论": ("抓取评论区洞察", _comment),
    "复刻": ("复刻爆款笔记（可带 URL）", _replicate),
    "列表": ("列出选题池", _list),
}


def _help():
    print("=" * 60)
    print("  小红书创作系统 · 命令速查（中文触发词）")
    print("=" * 60)
    print("\n完整闭环（按顺序）: 生成 → 审核 → 发布 → 采集\n")
    print("最常用：")
    print("  python xhs 生成        # 启动工作台（推荐，页面上做一切）")
    print("  python xhs 发布        # 一键发布笔记到小红书")
    print("  python xhs 采集        # 采集互动数据 + 竞品灌选题池")
    print("  python xhs 登录        # 登录/刷新小红书 Cookie\n")
    print("-" * 60)
    print("全部命令：")
    for cmd, (desc, _) in COMMANDS.items():
        print(f"  python xhs {cmd:<6} # {desc}")
    print("-" * 60)
    print("\n💡 记忆口诀：生成 → 审核 → 发布 → 采集")
    print("   生成在「工作台」做，发布用「发布」，数据回流用「采集」\n")


def main():
    if len(sys.argv) < 2:
        _help()
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd in ("-h", "--help", "help", "帮助"):
        _help()
        return

    if cmd not in COMMANDS:
        print(f"❌ 未知命令：{cmd}")
        print("输入 `python xhs` 查看所有命令\n")
        return

    desc, func = COMMANDS[cmd]
    try:
        func(args)
    except KeyboardInterrupt:
        print("\n已取消")


if __name__ == "__main__":
    main()
