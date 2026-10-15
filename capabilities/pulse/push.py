"""微信推送客户端（连接器 v1.1）——三通道：serverchan / pushplus / wecom。

设计：
- 默认复用兄弟仓库 xianyu/push.json 的既有通道（同一 BOSS，密钥不复制，单一信息源）
- 孵化台可配**专属通道**：`.cache/pulse_push.json`（{"provider": "...", "key": "..."}）
  存在则优先——解决 Server酱免费 5 条/天与排队号生意共享挤占的问题，且不动共享配置
- 系统代理死掉时自动绕过（本项目已知坑）；推送失败不抛出，返回 (ok, 原因)
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
XIANYU_PUSH_JSON = Path(r"D:\SoftWare\User\Vs\xianyu\push.json")
DEDICATED_PUSH_JSON = REPO_ROOT / ".cache" / "pulse_push.json"  # 专属通道（可选）


def _opener():
    # 系统代理常指向已死的本地端口（127.0.0.1:33210 事故），直连更稳
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def load_channel() -> tuple[str, str]:
    """读通道配置：专属通道优先，否则复用 xianyu 的。返回 (provider, key)。"""
    for p in (DEDICATED_PUSH_JSON, XIANYU_PUSH_JSON):
        try:
            cfg = json.loads(p.read_text(encoding="utf-8"))
            provider, key = cfg.get("provider", ""), cfg.get("key", "")
            if provider and key:
                return provider, key
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return "", ""


def push_wechat(title: str, desp: str) -> tuple[bool, str]:
    """推送到 BOSS 微信。返回 (ok, msg)。

    已知约束：serverchan 免费额度 5 条/天（与排队号共享时可能被挤占）——
    挤占时推送失败但心跳 journal 照常落盘；要专属额度就配 .cache/pulse_push.json。
    """
    provider, key = load_channel()
    if not provider:
        return False, "无通道配置（xianyu/push.json 与 .cache/pulse_push.json 均缺）"
    try:
        if provider == "serverchan":
            qs = urllib.parse.urlencode({"title": title, "desp": desp})
            resp = json.loads(_opener().open(f"https://sctapi.ftqq.com/{key}.send?{qs}", timeout=15).read())
            return resp.get("code") == 0, resp.get("message", "?")
        if provider == "pushplus":
            qs = urllib.parse.urlencode({"token": key, "title": title, "content": desp})
            resp = json.loads(_opener().open(f"https://www.pushplus.plus/send?{qs}", timeout=15).read())
            return resp.get("code") == 200, resp.get("msg", "?")
        if provider == "wecom":
            req = urllib.request.Request(
                f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}",
                data=json.dumps({"msgtype": "text", "text": {"content": f"{title}\n{desp}"}}, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            resp = json.loads(_opener().open(req, timeout=15).read())
            return resp.get("errcode") == 0, resp.get("errmsg", "?")
        return False, f"未适配的 provider: {provider}"
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read()).get("message", "")
        except Exception:
            detail = ""
        return False, f"HTTP {e.code}: {detail}"
    except Exception as e:  # 推送失败不致命：返回原因供日志
        return False, f"{type(e).__name__}: {e}"


if __name__ == "__main__":
    ok, msg = push_wechat("孵化台连接器测试", "如果你看到这条，说明执行模块的心跳已接通你的微信 ✅")
    print("OK" if ok else f"FAIL {msg}")
