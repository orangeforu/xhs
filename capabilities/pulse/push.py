"""微信推送客户端（Server酱，复用兄弟仓库 push.json 的既有通道）。

设计：不复制密钥——直接读 xianyu 仓库的 push.json（同一 BOSS、同一条已验证通道），
单一信息源原则。系统代理死掉时自动绕过（本项目已知坑）。
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
XIANYU_PUSH_JSON = Path(r"D:\SoftWare\User\Vs\xianyu\push.json")


def _opener():
    # 系统代理常指向已死的本地端口（127.0.0.1:33210 事故），直连更稳
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def push_wechat(title: str, desp: str) -> tuple[bool, str]:
    """推送到 BOSS 微信（Server酱）。返回 (ok, msg)。

    已知约束：免费额度 5 条/天，与兄弟仓库（排队号报警）共享——孵化台每日只发 1 条
    晨报，额度被挤占时推送失败但 journal 照常落盘（心跳不因通道死）。
    """
    try:
        cfg = json.loads(XIANYU_PUSH_JSON.read_text(encoding="utf-8"))
        key = cfg.get("key", "")
        provider = cfg.get("provider", "")
        if not key:
            return False, "push.json 缺 key"
        if provider != "serverchan":
            return False, f"未适配的 provider: {provider}"
        qs = urllib.parse.urlencode({"title": title, "desp": desp})
        url = f"https://sctapi.ftqq.com/{key}.send?{qs}"
        resp = json.loads(_opener().open(url, timeout=15).read())
        return resp.get("code") == 0, resp.get("message", "?")
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
