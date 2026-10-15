#!/usr/bin/env python3
"""
调度器守护进程 - 常驻运行定时生成 / 采数任务
================================================

用法:
    python scripts/scheduler_daemon.py                  # 前台常驻运行
    python scripts/scheduler_daemon.py --add            # 交互式添加任务（见 tabs/calendar.py 更方便）
    python scripts/scheduler_daemon.py --list           # 列出当前任务

生产部署：
- Windows：用「任务计划程序」开机启动 ``python scripts/scheduler_daemon.py``
- Linux/macOS：systemd / nohup / screen 常驻

任务在 tabs/calendar.py 的「⏰ 定时生成」区或本脚本 --add 管理，持久化在
data/schedules.json，守护进程和 Streamlit 应用共享同一份配置。
"""

import argparse
import contextlib
import signal
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.config import get_logger
from core.scheduler import ScheduledTask, get_scheduler

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="xhs 定时调度守护进程")
    parser.add_argument("--list", action="store_true", help="列出当前所有任务")
    parser.add_argument("--demo", action="store_true", help="添加一个示例任务（每天 9 点智能生成）")
    args = parser.parse_args()

    sched = get_scheduler()

    if args.list:
        tasks = sched.list_tasks()
        if not tasks:
            print("（暂无定时任务，在 tabs/calendar.py 或 --demo 添加）")
            return
        for t in tasks:
            print(f"[{t.id}] {'✅' if t.enabled else '⏸️'} {t.name} | mode={t.mode} action={t.action} | next={t.next_run_at} | last={t.last_result}")
        return

    if args.demo:
        tid = sched.add_task(ScheduledTask(
            id="", name="每日9点智能生成", mode="cron", cron="0 9 * * *", action="generate",
        ))
        print(f"已添加示例任务 id={tid}（每天 09:00 跑 pipeline.py --smart）")
        return

    # 常驻模式
    logger.info("调度器守护进程启动。Ctrl+C 退出。")
    sched.start()

    def _shutdown(signum, frame):
        logger.info("收到退出信号，停止调度器。")
        sched.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    with contextlib.suppress(AttributeError, ValueError):  # Windows 无 SIGTERM
        signal.signal(signal.SIGTERM, _shutdown)

    # 主线程阻塞等待
    signal.pause() if hasattr(signal, "pause") else _block_forever()


def _block_forever():
    import time
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
