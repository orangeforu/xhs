import json
import logging
import os
import platform
import subprocess
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# 统一日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DOCS_DIR = PROJECT_ROOT / "docs"
PUBLISHED_DIR = PROJECT_ROOT / "published"
ASSETS_DIR = PROJECT_ROOT / "assets"
FONT_DIR = ASSETS_DIR / "fonts"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

# 图片生成配置
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "pollinations").lower()
IMAGE_API_KEY = os.getenv("IMAGE_API_KEY", "")


# ── 跨平台文件锁 ──
if platform.system() in ("Linux", "Darwin"):
    import fcntl

    def _lock_file(f, exclusive: bool = True) -> None:
        op = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(f.fileno(), op)

    def _unlock_file(f) -> None:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
else:
    # Windows: 使用 msvcrt 文件锁
    import msvcrt

    def _lock_file(f, exclusive: bool = True) -> None:
        mode = msvcrt.LK_NBLCK if exclusive else msvcrt.LK_NBRLCK
        try:
            msvcrt.locking(f.fileno(), mode, 1)
        except OSError:
            # 如果锁被占用，重试
            import time
            for _ in range(10):
                time.sleep(0.1)
                try:
                    msvcrt.locking(f.fileno(), mode, 1)
                    return
                except OSError:
                    continue
            raise

    def _unlock_file(f) -> None:
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def ensure_dirs() -> None:
    """确保必要目录存在。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)


def validate_env() -> None:
    """验证关键环境变量，缺失时立即报错并给出清晰指引。"""
    api_key = os.getenv("LLM_API_KEY", "") or os.getenv("KIMI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "LLM_API_KEY 未配置。请将 .env.example 复制为 .env 并填写你的 API Key。"
        )


def validate_fonts() -> bool:
    """检查字体文件是否存在，返回是否可用。"""
    regular = FONT_DIR / "NotoSansSC-Regular.ttf"
    bold = FONT_DIR / "NotoSansSC-Bold.ttf"
    ok = regular.exists() and bold.exists()
    if not ok:
        logging.warning(
            "思源黑体字体文件未找到（%s），将使用系统 fallback 字体。", FONT_DIR
        )
    return ok


def open_folder(path: str) -> None:
    """跨平台打开文件夹。"""
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", path], check=False)
    elif system == "Windows":
        subprocess.run(["explorer", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)


def _atomic_write_json(path: Path, data: dict, with_lock: bool = True) -> None:
    """原子写入 JSON：先写临时文件再 rename，避免并发写入导致数据损坏。

    Args:
        with_lock: 是否使用文件锁保护写入（默认 True）
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    if with_lock:
        # 使用 .lock 文件作为锁文件，避免对同一个文件同时读写
        lock_path = path.with_suffix(".lock")
        with open(lock_path, "w") as lock_f:
            _lock_file(lock_f, exclusive=True)
            try:
                _write_json_atomic(path, data)
            finally:
                _unlock_file(lock_f)
    else:
        _write_json_atomic(path, data)


def _write_json_atomic(path: Path, data: dict) -> None:
    """实际的原子写入逻辑。"""
    fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, str(path))
    except Exception:
        os.unlink(tmp_path)
        raise


def load_topics_json() -> dict:
    """加载选题池 JSON，文件不存在时抛出 FileNotFoundError。"""
    path = DATA_DIR / "topics.json"
    if not path.exists():
        raise FileNotFoundError(
            f"选题池文件不存在: {path}。请先创建 data/topics.json。"
        )
    lock_path = path.with_suffix(".lock")
    with open(lock_path, "w") as lock_f:
        _lock_file(lock_f, exclusive=False)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        finally:
            _unlock_file(lock_f)


def save_topics_json(data: dict) -> None:
    """保存选题池 JSON（带锁保护）。"""
    path = DATA_DIR / "topics.json"
    _atomic_write_json(path, data, with_lock=True)


def load_performance_json() -> dict:
    """加载发布数据 JSON，不存在时返回空模板。"""
    path = DATA_DIR / "performance.json"
    if not path.exists():
        return {"notes": [], "summary": {
            "total_published": 0, "total_likes": 0, "total_collects": 0,
            "total_comments": 0, "total_shares": 0, "total_exposure": 0,
            "s_grade_count": 0, "a_grade_count": 0,
            "b_grade_count": 0, "c_grade_count": 0,
            "current_streak_underperform": 0,
        }}
    lock_path = path.with_suffix(".lock")
    with open(lock_path, "w") as lock_f:
        _lock_file(lock_f, exclusive=False)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        finally:
            _unlock_file(lock_f)


def save_performance_json(data: dict) -> None:
    """保存发布数据 JSON（带锁保护）。"""
    path = DATA_DIR / "performance.json"
    _atomic_write_json(path, data, with_lock=True)


def _grade_from_likes(likes: int) -> str:
    """根据点赞数计算等级。委托给 publish_helpers.calculate_grade。"""
    from core.publish_helpers import calculate_grade
    return calculate_grade(likes)


def update_note_performance(topic: str, metrics: dict) -> bool:
    """更新单篇笔记的运营数据（按 topic 匹配）。

    metrics 示例: {"likes": 100, "collects": 50, "comments": 20, "shares": 10, "exposure": 5000}
    返回是否找到并更新了该笔记。
    """
    data = load_performance_json()
    for note in data.get("notes", []):
        if note.get("topic") == topic:
            for key in ("likes", "collects", "comments", "shares", "exposure"):
                if key in metrics:
                    note[key] = int(metrics[key])
            note["grade"] = _grade_from_likes(note.get("likes", 0))
            save_performance_json(data)
            return True
    return False


def load_calendar_json() -> dict:
    """加载内容日历 JSON，不存在时返回空模板。"""
    path = DATA_DIR / "calendar.json"
    if not path.exists():
        return {"weeks": {}, "series": {}}
    lock_path = path.with_suffix(".lock")
    with open(lock_path, "w") as lock_f:
        _lock_file(lock_f, exclusive=False)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        finally:
            _unlock_file(lock_f)


def save_calendar_json(data: dict) -> None:
    """保存内容日历 JSON。"""
    path = DATA_DIR / "calendar.json"
    _atomic_write_json(path, data)


def init() -> None:
    """初始化项目：创建目录、校验环境变量和字体。在入口文件中显式调用。"""
    ensure_dirs()
    validate_env()
    validate_fonts()
