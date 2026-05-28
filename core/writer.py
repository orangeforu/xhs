import json
import os
import time

import requests

from core.config import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL = os.getenv("LLM_MODEL", "kimi-k2-6")
DEFAULT_BASE_URL = os.getenv("LLM_BASE_URL", os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1"))
DEFAULT_API_KEY = os.getenv("LLM_API_KEY", os.getenv("KIMI_API_KEY", ""))


def _call_api(
    messages: list[dict],
    model: str | None = None,
    max_tokens: int = 2500,
    temperature: float = 0.8,
    retries: int = 3,
) -> dict:
    url = f"{DEFAULT_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEFAULT_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else 0
            if status == 429 or 500 <= status < 600:
                last_err = e
                wait = 2 ** attempt
                logger.warning("API 请求失败 (HTTP %s)，%d秒后重试 (%d/%d)", status, wait, attempt + 1, retries)
                time.sleep(wait)
                continue
            else:
                raise
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_err = e
            wait = 2 ** attempt
            logger.warning("API 请求失败 (%s)，%d秒后重试 (%d/%d)", type(e).__name__, wait, attempt + 1, retries)
            time.sleep(wait)
        except (json.JSONDecodeError, ValueError) as e:
            # API 返回了非 JSON 响应（如 HTML 错误页面），可重试
            last_err = e
            wait = 2 ** attempt
            logger.warning("API 返回非 JSON 响应，%d秒后重试 (%d/%d): %s", wait, attempt + 1, retries, e)
            time.sleep(wait)

    if last_err is None:
        raise RuntimeError("_call_api 未执行任何请求（retries=0）")
    raise last_err


def _extract_content(data: dict) -> str:
    """从 OpenAI 兼容响应中提取文本，并进行基础校验。"""
    if not isinstance(data, dict):
        raise ValueError(f"API 返回非 dict 类型: {type(data)}")
    choices = data.get("choices")
    if not choices or not isinstance(choices, list):
        raise ValueError("API 响应缺少 choices 字段")
    message = choices[0].get("message")
    if not message or not isinstance(message, dict):
        raise ValueError("API 响应缺少 message 字段")
    content = message.get("content")
    if content is None:
        raise ValueError("API 响应缺少 content 字段")
    return content


