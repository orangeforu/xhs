"""每日心跳（孵化台的"生命力"）——晨间作战简报：扫战局 → 生成今日三件事 → 落 journal → 推微信。

v1 原则：纯确定性规则，不调 LLM（可靠>聪明）；失败不抛出（调度任务永续运行）。
注册：Windows 计划任务每日 08:30 跑 run_heartbeat.bat（见 README）。
"""
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from push import push_wechat

REPO = Path(__file__).resolve().parents[2]
JOURNAL = REPO / "cockpit" / "journal"
PC_COOKIE = REPO / ".cache" / "xhs_pc_cookie.json"


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def week_focus() -> list[str]:
    """cockpit/status.md 里本周焦点未勾选项。"""
    text = read(REPO / "cockpit" / "status.md")
    m = re.search(r"## 本周焦点.*?\n(.*?)(\n## |\Z)", text, re.S)
    if not m:
        return []
    return [ln[6:].strip() for ln in m.group(1).splitlines() if ln.strip().startswith("- [ ]")]


def cookie_age_days() -> float | None:
    try:
        return (time.time() - PC_COOKIE.stat().st_mtime) / 86400
    except OSError:
        return None


def key_dates() -> list[tuple[str, date]]:
    """从各案例 stop_loss / 98-debt 提取 YYYY-MM-DD 日期。"""
    found: list[tuple[str, date]] = []
    today = date.today()
    for vf in (REPO / "ventures").glob("*/venture.md"):
        text = read(vf)
        for ds in re.findall(r"\d{4}-\d{2}-\d{2}", text):
            d = date.fromisoformat(ds)
            if today <= d <= date.fromordinal(today.toordinal() + 14):
                found.append((vf.parent.name, d))
    return found


def journal_stale_days() -> int | None:
    files = sorted(JOURNAL.glob("*.md")) if JOURNAL.exists() else []
    if not files:
        return None
    last = date.fromisoformat(files[-1].stem)
    return (date.today() - last).days


def build_brief() -> tuple[str, str]:
    """返回 (journal 正文, 微信推送文本)。"""
    today = date.today()
    is_friday = today.weekday() == 4  # 周五=法定复盘日
    lines: list[str] = [f"# 作战简报 {today.isoformat()}（{['一','二','三','四','五','六','日'][today.weekday()]}）", ""]

    # 1. 今日三件事（确定性优先级：周五复盘 > 本周焦点未勾项 > 常规 nudges）
    todo: list[str] = []
    if is_friday:
        todo.append("⚖️ **周五复盘**（~20min，宪法 Cadence）：账本/状态灯/蒸馏/资产健康四件套")
    todo += week_focus()[:3]
    if not todo:
        todo.append("（本周焦点已清空——周五复盘时补下周计划）")

    # 2. 预警
    warns = []
    age = cookie_age_days()
    if age is None:
        warns.append("小红书 PC Cookie 不存在（xhs_crawler 将需重新扫码）")
    elif age > 21:
        warns.append(f"小红书 PC Cookie 已 {age:.0f} 天未刷新，近期可能过期")
    stale = journal_stale_days()
    if stale and stale >= 2:
        warns.append(f"心跳中断过：上次简报是 {stale} 天前（若非假期，检查计划任务）")
    for name, d in key_dates():
        warns.append(f"{name} 关键日期：{d.isoformat()}（{(d - today).days} 天后）")

    lines.append("## 今日三件事")
    lines += [f"{i+1}. {t}" for i, t in enumerate(todo[:3])]
    lines.append("")
    if warns:
        lines.append("## ⚠️ 预警")
        lines += [f"- {w}" for w in warns]
        lines.append("")

    lines.append("## 速览")
    lines.append(f"- 总账/状态：cockpit/ledger.md · cockpit/status.md")
    lines.append(f"- 回执方式：做完的事直接体现在仓库（commit/上架/填表），周五统一对账")

    desp = "\n".join([
        f"### 今日三件事",
        *[f"{i+1}. {t}" for i, t in enumerate(todo[:3])],
        "",
        *([f"⚠️ {w}" for w in warns] if warns else []),
        f"\n—— 孵化台心跳 · 详情见 cockpit/journal/{today.isoformat()}.md",
    ])
    return "\n".join(lines), desp


def main() -> int:
    JOURNAL.mkdir(parents=True, exist_ok=True)
    today = date.today()
    brief, desp = build_brief()
    jp = JOURNAL / f"{today.isoformat()}.md"
    if not jp.exists():  # 同日重跑不覆盖（保留首版）
        jp.write_text(brief, encoding="utf-8")
    ok, msg = push_wechat(f"孵化台晨报 {today.isoformat()}", desp)
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] journal={jp.name} push={'OK' if ok else 'FAIL ' + msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
