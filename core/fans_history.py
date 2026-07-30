"""粉丝数据时序 - 定期快照粉丝数，画增长曲线。

spider_xhs PC 端 ``get_user_me`` 能拿到登录账号的粉丝数。每次诊断 / 采数时
快照一笔到 ``data/fans_history.json``，形成时序，供 ``tabs/analytics.py``
画增长曲线。完整粉丝画像（性别 / 年龄 / 城市）需蒲公英 API，账号有权限时再扩展。
"""

import json
from datetime import datetime

from core.config import DATA_DIR, _atomic_write_json, get_logger

logger = get_logger(__name__)

FANS_HISTORY_FILE = DATA_DIR / "fans_history.json"


def _extract_fans(res_json: dict | None) -> int | None:
    """从 get_user_me 响应中稳健提取粉丝数（字段名因接口版本而异）。"""
    if not res_json:
        return None
    data = res_json.get("data", {}) or {}
    if not isinstance(data, dict):
        return None
    for key in ("fans", "fansCount", "fans_count", "follower", "followers", "followersCount"):
        v = data.get(key)
        if v is not None:
            try:
                return int(v)
            except (ValueError, TypeError):
                continue
    return None


def load_fans_history() -> list[dict]:
    """加载粉丝历史时序 ``[{timestamp, fans}, ...]``。"""
    if not FANS_HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(FANS_HISTORY_FILE.read_text(encoding="utf-8"))
        return data.get("history", [])
    except Exception:
        return []


def snapshot_fans(api) -> int | None:
    """调 ``get_user_me`` 快照当前粉丝数，追加到历史。返回当前粉丝数。

    ``api`` 需有 ``get_user_me`` 方法（``XHS_Apis`` 实例）。
    """
    try:
        success, msg, res_json = api.get_user_me()
    except Exception as e:
        logger.warning("get_user_me 异常: %s", e)
        return None
    if not success:
        logger.warning("get_user_me 失败: %s", msg)
        return None
    fans = _extract_fans(res_json)
    if fans is None:
        logger.warning("未能从 get_user_me 响应提取粉丝数")
        return None
    history = load_fans_history()
    history.append({"timestamp": datetime.now().isoformat(timespec="seconds"), "fans": fans})
    history = history[-365:]  # 保留最近 1 年
    FANS_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(FANS_HISTORY_FILE, {"history": history})
    logger.info("粉丝快照: %d（累计 %d 笔）", fans, len(history))
    return fans
