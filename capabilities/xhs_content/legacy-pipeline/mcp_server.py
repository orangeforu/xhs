#!/usr/bin/env python3
"""
xhs MCP 服务器 - 把生成 / 发布 / 采数暴露为 MCP 工具，供 AI 客户端对话驱动
==========================================================================

用法（需先安装 fastmcp：`pip install fastmcp`）：
    python mcp_server.py                 # stdio 模式（Claude Desktop / CherryStudio）
    python mcp_server.py --transport sse # SSE 模式

Claude Desktop 配置（claude_desktop_config.json）：
    {
      "mcpServers": {
        "xhs": { "command": "python", "args": ["D:/software/vs/xhs/mcp_server.py"] }
      }
    }

工具：list_topics / generate_note / get_performance / fetch_performance /
publish_approved / login_status。重操作走子进程（与 CLI 行为一致、解耦），
读操作直接读 JSON。stdio 模式下日志重定向到 stderr（stdout 留给 MCP 协议）。
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.config import load_topics_json, load_performance_json, PROJECT_ROOT as ROOT


def _run_script(script: str, extra_args: list[str] | None = None, timeout: int = 1800) -> str:
    """子进程跑项目脚本，返回 stdout（截断）。失败抛 RuntimeError。"""
    cmd = [sys.executable, str(ROOT / script), *(extra_args or [])]
    res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError(f"{script} 失败(rc={res.returncode}): {res.stderr[:300]}")
    return res.stdout[:2000]


def _build_server():
    """构造 FastMCP 服务器（lazy import fastmcp）。"""
    try:
        from fastmcp import FastMCP
    except ImportError:
        print(
            "fastmcp 未安装。请运行: pip install fastmcp\n"
            "然后重新启动本服务器。", file=sys.stderr,
        )
        sys.exit(1)

    mcp = FastMCP("xhs")

    @mcp.tool()
    def list_topics() -> str:
        """列出选题池（data/topics.json），含状态 / 公式 / 标签。"""
        data = load_topics_json()
        topics = data.get("topics", [])
        brief = [
            {"index": i, "topic": t.get("topic", ""), "status": t.get("status", ""),
             "formula": t.get("formula", t.get("title_formula", "")), "tags": t.get("tags", [])}
            for i, t in enumerate(topics)
        ]
        return json.dumps({"total": len(topics), "topics": brief}, ensure_ascii=False)

    @mcp.tool()
    def generate_note(topic_index: int | None = None) -> str:
        """生成一篇笔记。不传 topic_index 则 --smart 智能选题；传则 --index N。
        产物落到 docs_agent/pending/。"""
        if topic_index is not None:
            out = _run_script("pipeline.py", ["--index", str(topic_index)])
        else:
            out = _run_script("pipeline.py", ["--smart"])
        return f"生成完成。\n{out}"

    @mcp.tool()
    def get_performance() -> str:
        """读取 performance.json + 熔断状态，供分析。"""
        data = load_performance_json()
        notes = data.get("notes", [])
        cb = data.get("circuit_breaker", {})
        summary = {
            "total_notes": len(notes),
            "avg_likes": data.get("summary", {}).get("avg_likes", 0),
            "grade_distribution": data.get("summary", {}).get("grade_distribution", {}),
            "circuit_breaker_tripped": cb.get("tripped", False),
            "c_grade_streak": cb.get("streak", 0),
            "recent": sorted(notes, key=lambda n: n.get("updated_at", ""), reverse=True)[:5],
        }
        return json.dumps(summary, ensure_ascii=False, indent=2)

    @mcp.tool()
    def fetch_performance() -> str:
        """采集已发布笔记互动数据，更新 performance.json（登录 PC 端）。"""
        return _run_script("scripts/fetch_performance.py")

    @mcp.tool()
    def publish_approved(limit: int = 0, dry_run: bool = False) -> str:
        """发布 approved/ 笔记到小红书。dry_run=True 仅预览。"""
        args = []
        if dry_run:
            args.append("--dry-run")
        if limit > 0:
            args += ["--limit", str(limit)]
        return _run_script("scripts/auto_publish.py", args)

    @mcp.tool()
    def login_status() -> str:
        """检查 PC / 创作者端 cookie 是否就绪。"""
        cache = ROOT / ".cache"
        pc = (cache / "xhs_pc_cookie.json").exists()
        creator = (cache / "xhs_creator_cookie.json").exists()
        return json.dumps({"pc_cookie": pc, "creator_cookie": creator}, ensure_ascii=False)

    return mcp


def main():
    parser = argparse.ArgumentParser(description="xhs MCP 服务器")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    args = parser.parse_args()

    # stdio 模式：日志只能进 stderr，stdout 留给 MCP 协议
    if args.transport == "stdio":
        logging.basicConfig(stream=sys.stderr, level=logging.INFO)

    mcp = _build_server()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
