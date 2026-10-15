"""调度器 cron 解析 + 任务 CRUD 测试。不实际启动线程 / 跑子进程。"""

from datetime import datetime

import core.scheduler as sched_mod
from core.scheduler import (
    BackgroundScheduler,
    ScheduledTask,
    _build_command,
    _parse_field,
    compute_next_run,
    next_cron_run,
)

# ── cron 字段解析 ──

def test_parse_field_star():
    assert _parse_field("*", 0, 59) == set(range(60))


def test_parse_field_step():
    assert _parse_field("*/15", 0, 59) == {0, 15, 30, 45}


def test_parse_field_range_and_list():
    assert _parse_field("1-3,10", 0, 59) == {1, 2, 3, 10}


def test_parse_field_range_step():
    assert _parse_field("0-30/10", 0, 59) == {0, 10, 20, 30}


# ── next_cron_run ──

def test_daily_9am_before():
    # 2026-07-30 08:00 -> 当天 09:00
    assert next_cron_run("0 9 * * *", datetime(2026, 7, 30, 8, 0)) == datetime(2026, 7, 30, 9, 0)


def test_daily_9am_after():
    # 2026-07-30 09:30 -> 次日 09:00
    assert next_cron_run("0 9 * * *", datetime(2026, 7, 30, 9, 30)) == datetime(2026, 7, 31, 9, 0)


def test_every_30_min():
    assert next_cron_run("*/30 * * * *", datetime(2026, 7, 30, 8, 5)) == datetime(2026, 7, 30, 8, 30)


def test_weekly_monday():
    # 2026-07-30 是周四 -> 下周一 2026-08-03 09:00
    assert next_cron_run("0 9 * * 1", datetime(2026, 7, 30, 8, 0)) == datetime(2026, 8, 3, 9, 0)


def test_sunday_as_7():
    # 7 = 周日。2026-07-30 周四 -> 下周日 2026-08-02 09:00
    assert next_cron_run("0 9 * * 7", datetime(2026, 7, 30, 8, 0)) == datetime(2026, 8, 2, 9, 0)


def test_dom_monthly():
    # 每月 1 号 08:30。2026-07-30 -> 2026-08-01 08:30
    assert next_cron_run("30 8 1 * *", datetime(2026, 7, 30, 8, 0)) == datetime(2026, 8, 1, 8, 30)


def test_dom_and_dow_or_logic():
    # dom=15 与 dow=1(周一) 都限定 -> OR。2026-07-30 周四 -> 2026-08-03 周一 早于 8-15
    assert next_cron_run("0 9 15 * 1", datetime(2026, 7, 30, 8, 0)) == datetime(2026, 8, 3, 9, 0)


def test_invalid_cron_raises():
    try:
        next_cron_run("0 9", datetime(2026, 7, 30))
    except ValueError:
        return
    raise AssertionError("非法 cron 应抛 ValueError")


# ── compute_next_run ──

def test_compute_next_run_interval():
    t = ScheduledTask(id="x", name="t", mode="interval", interval_minutes=60)
    nxt = compute_next_run(t, datetime(2026, 7, 30, 8, 0))
    assert nxt == datetime(2026, 7, 30, 9, 0)


def test_compute_next_run_daily_today():
    t = ScheduledTask(id="x", name="t", mode="daily", time_hhmm="09:00")
    assert compute_next_run(t, datetime(2026, 7, 30, 8, 0)) == datetime(2026, 7, 30, 9, 0)


def test_compute_next_run_daily_tomorrow():
    t = ScheduledTask(id="x", name="t", mode="daily", time_hhmm="09:00")
    assert compute_next_run(t, datetime(2026, 7, 30, 9, 30)) == datetime(2026, 7, 31, 9, 0)


# ── _build_command ──

def test_build_command_generate():
    cmd = _build_command(ScheduledTask(id="x", name="t", action="generate"))
    assert cmd[-1] == "--smart"
    assert "pipeline.py" in cmd[-2]


def test_build_command_fetch():
    cmd = _build_command(ScheduledTask(id="x", name="t", action="fetch_performance"))
    assert any("fetch_performance.py" in c for c in cmd)


# ── BackgroundScheduler CRUD（持久化到临时文件）──

def test_scheduler_crud(tmp_path, monkeypatch):
    monkeypatch.setattr(sched_mod, "SCHEDULES_FILE", tmp_path / "schedules.json")
    sched = BackgroundScheduler()

    # add
    tid = sched.add_task(ScheduledTask(id="", name="每日生成", mode="cron", cron="0 9 * * *"))
    tasks = sched.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].id == tid
    assert tasks[0].next_run_at  # 已算出下次触发

    # toggle
    enabled = sched.toggle_task(tid)
    assert enabled is False  # 原本 True -> 关闭
    assert sched.list_tasks()[0].enabled is False

    # remove
    assert sched.remove_task(tid)
    assert sched.list_tasks() == []


def test_scheduler_persistence(tmp_path, monkeypatch):
    f = tmp_path / "schedules.json"
    monkeypatch.setattr(sched_mod, "SCHEDULES_FILE", f)
    sched = BackgroundScheduler()
    sched.add_task(ScheduledTask(id="", name="持久化任务", mode="daily", time_hhmm="10:00"))
    assert f.exists()

    # 新实例从同一文件加载
    sched2 = BackgroundScheduler()
    tasks = sched2.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].name == "持久化任务"
