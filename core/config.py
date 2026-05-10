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


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def ensure_dirs():
    """确保必要目录存在。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)


def validate_env():
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


def open_folder(path: str):
    """跨平台打开文件夹。"""
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", path], check=False)
    elif system == "Windows":
        subprocess.run(["explorer", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)


def _atomic_write_json(path: Path, data: dict):
    """原子写入 JSON：先写临时文件再 rename，避免并发写入导致数据损坏。"""
    path.parent.mkdir(parents=True, exist_ok=True)
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
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_topics_json(data: dict):
    """保存选题池 JSON。"""
    _atomic_write_json(DATA_DIR / "topics.json", data)


def load_performance_json() -> dict:
    """加载发布数据 JSON，不存在时返回空模板。"""
    path = DATA_DIR / "performance.json"
    if not path.exists():
        return {"notes": [], "summary": {
            "total_published": 0, "total_likes": 0, "total_collects": 0,
            "total_comments": 0, "total_shares": 0,
            "s_grade_count": 0, "a_grade_count": 0,
            "b_grade_count": 0, "c_grade_count": 0,
            "current_streak_underperform": 0,
        }}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_performance_json(data: dict):
    """保存发布数据 JSON。"""
    _atomic_write_json(DATA_DIR / "performance.json", data)


def init():
    """初始化项目：创建目录、校验环境变量和字体。在入口文件中显式调用。"""
    ensure_dirs()
    validate_env()
    validate_fonts()
