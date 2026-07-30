"""定时调度器 - 让 pipeline / 采数按计划自动跑。

纯 Python 实现（无 apscheduler 依赖，对标 Beav 的自包含 cron 引擎）：

- :func:`next_cron_run`：5 字段 cron 解析 + 下次触发时间计算。
- :class:`ScheduledTask`：一条定时任务（cron / interval / daily 三种模式）。
- :class:`BackgroundScheduler`：后台线程轮询到期任务，subprocess 执行，持久化到
  ``data/schedules.json``。任务执行用子进程调 ``pipeline.py --smart`` /
  ``fetch_performance.py``，与 CLI 行为一致、解耦。

两种运行方式：
1. ``scripts/scheduler_daemon.py``：常驻守护（Windows 计划任务 / systemd），生产用。
2. ``tabs/calendar.py`` 的「⏰ 定时生成」区：在 Streamlit 应用内启动调度器 + 管理任务。
"""

import json
import subprocess
import sys
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from core.config import DATA_DIR, PROJECT_ROOT, _atomic_write_json, get_logger

logger = get_logger(__name__)

SCHEDULES_FILE = DATA_DIR / "schedules.json"
_TICK_SECONDS = 30  # 轮询间隔
_RUN_TIMEOUT = 1800  # 单任务最长 30 分钟


# ═══════════════════════════════════════════════════════════
# cron 解析
# ═══════════════════════════════════════════════════════════

def _parse_field(expr: str, min_v: int, max_v: int) -> set[int]:
    """解析单个 cron 字段为允许值集合。支持 ``*`` ``*/n`` ``a-b`` ``a,b`` ``a-b/n``。"""
    result: set[int] = set()
    for part in expr.split(","):
        part = part.strip()
        step = 1
        if "/" in part:
            base, _, step_s = part.partition("/")
            step = int(step_s)
            part = base
        if part == "*":
            lo, hi = min_v, max_v
        elif "-" in part:
            lo_s, _, hi_s = part.partition("-")
            lo, hi = int(lo_s), int(hi_s)
        else:
            lo = hi = int(part)
        for v in range(lo, hi + 1, step):
            if min_v <= v <= max_v:
                result.add(v)
    return result


def _day_match(dt: datetime, dom: set[int], dow: set[int], dom_restricted: bool, dow_restricted: bool) -> bool:
    """cron 日匹配：dom 与 dow 都限定时取 OR，否则 AND（标准 cron 语义）。"""
    dom_m = dt.day in dom
    cron_dow = (dt.weekday() + 1) % 7  # Python weekday() Mon=0..Sun=6 -> cron Sun=0..Sat=6
    dow_m = cron_dow in dow
    if dom_restricted and dow_restricted:
        return dom_m or dow_m
    return dom_m and dow_m


def next_cron_run(cron_expr: str, from_dt: datetime | None = None) -> datetime | None:
    """计算 cron_expr 下一次触发时间（> from_dt）。一年内无匹配返回 None。

    逐分钟推进，cap 366 天（527040 步，亚秒级，且只在算 next-fire 时调一次）。
    """
    parts = cron_expr.split()
    if len(parts) != 5:
        raise ValueError(f"cron 表达式必须是 5 字段: {cron_expr!r}")
    minute = _parse_field(parts[0], 0, 59)
    hour = _parse_field(parts[1], 0, 23)
    dom = _parse_field(parts[2], 1, 31)
    month = _parse_field(parts[3], 1, 12)
    dow = {0 if d == 7 else d for d in _parse_field(parts[4], 0, 7)}
    dom_restricted = parts[2] != "*"
    dow_restricted = parts[4] != "*"

    dt = (from_dt or datetime.now()).replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(366 * 24 * 60):
        if (
            dt.month in month
            and dt.hour in hour
            and dt.minute in minute
            and _day_match(dt, dom, dow, dom_restricted, dow_restricted)
        ):
            return dt
        dt += timedelta(minutes=1)
    return None


# ═══════════════════════════════════════════════════════════
# 任务模型
# ═══════════════════════════════════════════════════════════

@dataclass
class ScheduledTask:
    """一条定时任务。

    mode:
      - ``cron``：5 字段 cron 表达式（``cron`` 字段）
      - ``interval``：每 N 分钟（``interval_minutes``）
      - ``daily``：每天 HH:MM（``time_hhmm``）
    action:
      - ``generate``：调 ``pipeline.py --smart`` 生成下一篇选题
      - ``fetch_performance``：调 ``fetch_performance.py`` 采集互动数据
    """

    id: str
    name: str
    enabled: bool = True
    mode: str = "cron"
    cron: str = "0 9 * * *"
    interval_minutes: int = 60
    time_hhmm: str = "09:00"
    action: str = "generate"
    last_run_at: str = ""
    last_result: str = ""
    next_run_at: str = ""


def compute_next_run(task: ScheduledTask, from_dt: datetime | None = None) -> datetime | None:
    """按 task.mode 计算下次触发时间。"""
    now = from_dt or datetime.now()
    if task.mode == "cron":
        return next_cron_run(task.cron, now)
    if task.mode == "interval":
        return now + timedelta(minutes=task.interval_minutes)
    if task.mode == "daily":
        try:
            hh, mm = task.time_hhmm.split(":")
            target = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
        except Exception:
            return None
        if target <= now:
            target += timedelta(days=1)
        return target
    return None


def _build_command(task: ScheduledTask) -> list[str]:
    """构造任务执行的子进程命令。"""
    py = sys.executable
    if task.action == "fetch_performance":
        return [py, str(PROJECT_ROOT / "scripts" / "fetch_performance.py")]
    # 默认 generate：--smart 自动选最优 pending 选题生成 1 篇
    return [py, str(PROJECT_ROOT / "pipeline.py"), "--smart"]


# ═══════════════════════════════════════════════════════════
# 调度器
# ═══════════════════════════════════════════════════════════

class BackgroundScheduler:
    """后台线程调度器。单进程内单例（start 幂等）。"""

    def __init__(self):
        self._tasks: list[ScheduledTask] = []
        self._lock = threading.RLock()  # 可重入：_save 等方法可能在持锁时被调用
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._inflight: set[str] = set()
        self._load()

    # ── 持久化 ──
    def _load(self) -> None:
        if not SCHEDULES_FILE.exists():
            self._tasks = []
            return
        try:
            data = json.loads(SCHEDULES_FILE.read_text(encoding="utf-8"))
            self._tasks = [ScheduledTask(**t) for t in data.get("tasks", [])]
        except Exception as e:
            logger.warning("加载 schedules.json 失败: %s", e)
            self._tasks = []

    def _save(self) -> None:
        with self._lock:
            tasks = [asdict(t) for t in self._tasks]
        SCHEDULES_FILE.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(SCHEDULES_FILE, {"tasks": tasks})

    # ── CRUD ──
    def list_tasks(self) -> list[ScheduledTask]:
        with self._lock:
            return list(self._tasks)

    def add_task(self, task: ScheduledTask) -> str:
        if not task.id:
            task.id = uuid.uuid4().hex[:8]
        nxt = compute_next_run(task)
        task.next_run_at = nxt.isoformat(timespec="seconds") if nxt else ""
        with self._lock:
            self._tasks.append(task)
        self._save()
        logger.info("新增定时任务 [%s] %s (%s)", task.id, task.name, task.mode)
        return task.id

    def remove_task(self, task_id: str) -> bool:
        with self._lock:
            before = len(self._tasks)
            self._tasks = [t for t in self._tasks if t.id != task_id]
            removed = len(self._tasks) < before
        if removed:
            self._save()
        return removed

    def toggle_task(self, task_id: str) -> bool:
        new_enabled: bool | None = None
        with self._lock:
            for t in self._tasks:
                if t.id == task_id:
                    t.enabled = not t.enabled
                    nxt = compute_next_run(t)
                    t.next_run_at = nxt.isoformat(timespec="seconds") if nxt else ""
                    new_enabled = t.enabled
                    break
        if new_enabled is not None:
            self._save()
            return new_enabled
        return False

    # ── 运行 ──
    def start(self) -> None:
        """启动后台轮询线程（幂等，重复调用不会起多个线程）。"""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="xhs-scheduler", daemon=True)
        self._thread.start()
        logger.info("调度器已启动，每 %ds 轮询", _TICK_SECONDS)

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.error("调度器 tick 异常: %s", e)
            self._stop.wait(_TICK_SECONDS)

    def _tick(self) -> None:
        now = datetime.now()
        with self._lock:
            due = [
                t for t in self._tasks
                if t.enabled and t.id not in self._inflight
                and self._is_due(t, now)
            ]
            for t in due:
                self._inflight.add(t.id)
        for t in due:
            self._run_task(t)

    @staticmethod
    def _is_due(task: ScheduledTask, now: datetime) -> bool:
        """next_run_at 为空时现算；到期 = next_run_at <= now。"""
        nxt_str = task.next_run_at
        if not nxt_str:
            nxt = compute_next_run(task, now)
            if not nxt:
                return False
            task.next_run_at = nxt.isoformat(timespec="seconds")
            return nxt <= now
        try:
            return datetime.fromisoformat(nxt_str) <= now
        except Exception:
            return False

    def _run_task(self, task: ScheduledTask) -> None:
        cmd = _build_command(task)
        logger.info("⏰ 触发任务 [%s] %s: %s", task.id, task.name, " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=_RUN_TIMEOUT,
            )
            ok = result.returncode == 0
            status = "success" if ok else f"failed(rc={result.returncode}): {result.stderr[:200]}"
        except subprocess.TimeoutExpired:
            status = f"timeout({_RUN_TIMEOUT}s)"
        except Exception as e:
            status = f"error: {e}"
        finally:
            with self._lock:
                task.last_run_at = datetime.now().isoformat(timespec="seconds")
                task.last_result = status
                nxt = compute_next_run(task)
                task.next_run_at = nxt.isoformat(timespec="seconds") if nxt else ""
                self._inflight.discard(task.id)
            self._save()
            logger.info("⏰ 任务 [%s] 完成: %s", task.id, status)


# 进程内单例（Streamlit / daemon 共用）
_singleton: BackgroundScheduler | None = None
_singleton_lock = threading.Lock()


def get_scheduler() -> BackgroundScheduler:
    """获取进程内调度器单例。"""
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = BackgroundScheduler()
        return _singleton
