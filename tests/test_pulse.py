"""pulse 执行模块测试（全部离线：不碰网络、不碰真实配置文件）。"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

PULSE = Path(__file__).resolve().parents[1] / "capabilities" / "pulse"
sys.path.insert(0, str(PULSE))

import heartbeat  # noqa: E402
import push  # noqa: E402

# ── 连接器：通道选择逻辑 ──────────────────────────────────────

def test_dedicated_channel_wins(tmp_path, monkeypatch):
    dedicated = tmp_path / "pulse_push.json"
    dedicated.write_text(json.dumps({"provider": "pushplus", "key": "T1"}), encoding="utf-8")
    shared = tmp_path / "push.json"
    shared.write_text(json.dumps({"provider": "serverchan", "key": "SCTxxx"}), encoding="utf-8")
    monkeypatch.setattr(push, "DEDICATED_PUSH_JSON", dedicated)
    monkeypatch.setattr(push, "XIANYU_PUSH_JSON", shared)
    assert push.load_channel() == ("pushplus", "T1")


def test_fallback_to_shared_channel(tmp_path, monkeypatch):
    shared = tmp_path / "push.json"
    shared.write_text(json.dumps({"provider": "serverchan", "key": "SCTxxx"}), encoding="utf-8")
    monkeypatch.setattr(push, "DEDICATED_PUSH_JSON", tmp_path / "none.json")
    monkeypatch.setattr(push, "XIANYU_PUSH_JSON", shared)
    assert push.load_channel() == ("serverchan", "SCTxxx")


def test_no_channel_at_all(tmp_path, monkeypatch):
    monkeypatch.setattr(push, "DEDICATED_PUSH_JSON", tmp_path / "none1.json")
    monkeypatch.setattr(push, "XIANYU_PUSH_JSON", tmp_path / "none2.json")
    assert push.load_channel() == ("", "")


def test_unsupported_provider_fails_soft(tmp_path, monkeypatch):
    cfg = tmp_path / "push.json"
    cfg.write_text(json.dumps({"provider": "carrier_pigeon", "key": "x"}), encoding="utf-8")
    monkeypatch.setattr(push, "DEDICATED_PUSH_JSON", tmp_path / "none.json")
    monkeypatch.setattr(push, "XIANYU_PUSH_JSON", cfg)
    ok, msg = push.push_wechat("t", "d")
    assert not ok and "未适配" in msg


# ── 心跳：简报生成逻辑 ────────────────────────────────────────

@pytest.fixture()
def fake_repo(tmp_path, monkeypatch):
    """搭一个最小假仓库：cockpit/status.md + 一个带止损日期的案例。"""
    (tmp_path / "cockpit").mkdir()
    (tmp_path / "cockpit" / "status.md").write_text(
        "# 状态\n\n## 本周焦点（本周五更新）\n\n"
        "- [ ] 任务甲\n- [x] 任务乙（已完成）\n- [ ] 任务丙\n\n## 下节\n",
        encoding="utf-8",
    )
    v = tmp_path / "ventures" / "demo"
    v.mkdir(parents=True)
    (v / "venture.md").write_text(
        f"stop_loss: 至 {date.today() + timedelta(days=5)} 0 询盘关线", encoding="utf-8"
    )
    monkeypatch.setattr(heartbeat, "REPO", tmp_path)
    monkeypatch.setattr(heartbeat, "JOURNAL", tmp_path / "cockpit" / "journal")
    monkeypatch.setattr(heartbeat, "PC_COOKIE", tmp_path / ".cache" / "none.json")
    return tmp_path


def test_week_focus_only_unchecked(fake_repo):
    items = heartbeat.week_focus()
    assert items == ["任务甲", "任务丙"]


def test_brief_contains_todo_and_warnings(fake_repo):
    brief, desp = heartbeat.build_brief()
    assert "任务甲" in brief and "任务丙" in brief
    assert "任务乙" not in brief  # 已勾选不进三件事
    assert "demo" in brief  # 关键日期预警（5 天后的止损日）


def test_key_dates_only_near_future(fake_repo):
    far = fake_repo / "ventures" / "far"
    far.mkdir()
    (far / "venture.md").write_text(
        f"stop_loss: 至 {date.today() + timedelta(days=60)} 关线", encoding="utf-8"
    )
    names = [n for n, _ in heartbeat.key_dates()]
    assert "demo" in names and "far" not in names  # 只报 14 天窗口内的


def test_cookie_missing_produces_warning(fake_repo):
    _, desp = heartbeat.build_brief()
    assert "Cookie 不存在" in desp
