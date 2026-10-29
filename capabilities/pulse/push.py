"""Offline on import; push errors and receipts expose only allowlisted codes."""

import json
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
XIANYU_PUSH_JSON = REPO_ROOT.parent / "xianyu" / "push.json"
DEDICATED_PUSH_JSON = REPO_ROOT / ".cache" / "pulse_push.json"

# Only these failures positively mean that no delivery was accepted.
KNOWN_FAILURES = frozenset({"CONFIG_MISSING", "CONFIG_INVALID", "UNSUPPORTED_PROVIDER", "REQUEST_INVALID", "REJECTED"})


class ChannelError(ValueError):
    """Never attach configuration contents or underlying exception messages."""


def _opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def load_channel(config_paths=None) -> tuple[str, str]:
    """Dedicated config wins; only absence permits falling back to shared config."""
    paths = (DEDICATED_PUSH_JSON, XIANYU_PUSH_JSON) if config_paths is None else config_paths
    for path in paths:
        try:
            cfg = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            continue
        except Exception:
            raise ChannelError("CONFIG_INVALID") from None
        if not isinstance(cfg, dict):
            raise ChannelError("CONFIG_INVALID")
        provider, key = cfg.get("provider"), cfg.get("key")
        if not isinstance(provider, str) or not isinstance(key, str) or not provider.strip() or not key.strip():
            raise ChannelError("CONFIG_INVALID")
        return provider.strip(), key.strip()
    return "", ""


def push_wechat(title: str, desp: str, *, config_paths=None, opener_factory=None) -> tuple[bool, str]:
    """Return (True, OK), a known failure, or DELIVERY_UNKNOWN; never retry HTTP.

    An exception after entering open() may follow a successful remote delivery.
    Neither HTTP error bodies nor provider messages are read into diagnostics.
    Injectable paths and transport keep unit tests entirely offline.
    """
    try:
        provider, key = load_channel(config_paths)
    except Exception:
        return False, "CONFIG_INVALID"
    if not provider:
        return False, "CONFIG_MISSING"
    if provider not in {"serverchan", "pushplus", "wecom"}:
        return False, "UNSUPPORTED_PROVIDER"

    try:
        if provider == "serverchan":
            url = f"https://sctapi.ftqq.com/{urllib.parse.quote(key, safe='')}.send"
            data = urllib.parse.urlencode({"title": title, "desp": desp}).encode("utf-8")
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            field, success = "code", 0
        elif provider == "pushplus":
            url = "https://www.pushplus.plus/send"
            data = json.dumps({"token": key, "title": title, "content": desp}, ensure_ascii=False).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            field, success = "code", 200
        else:
            url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?" + urllib.parse.urlencode({"key": key})
            data = json.dumps({"msgtype": "text", "text": {"content": f"{title}\n{desp}"}}, ensure_ascii=False).encode(
                "utf-8"
            )
            headers = {"Content-Type": "application/json"}
            field, success = "errcode", 0
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        opener = (opener_factory or _opener)()
    except Exception:
        return False, "REQUEST_INVALID"

    try:
        with opener.open(request, timeout=15) as response:
            receipt = json.loads(response.read())
        # Missing, string, boolean or otherwise malformed codes cannot confirm delivery.
        if not isinstance(receipt, dict) or type(receipt.get(field)) is not int:
            return False, "DELIVERY_UNKNOWN"
        if receipt[field] == success:
            return True, "OK"
        return False, "REJECTED"
    except Exception:
        # Even HTTP errors can be generated after the downstream accepted the message.
        return False, "DELIVERY_UNKNOWN"
