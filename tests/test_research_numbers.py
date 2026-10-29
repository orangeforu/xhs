"""研究数字离线回归：不读取认证缓存，不加载真实 vendor，不联网或扫码。"""

import ast
import builtins
import json
import socket
import sys
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "capabilities" / "xhs_crawler" / "verify_search.py"


def forbidden(*args, **kwargs):
    raise AssertionError("offline research test attempted external I/O")


@pytest.fixture
def research(monkeypatch):
    source = SOURCE.read_text(encoding="utf-8")
    module = ModuleType("verify_search_offline")
    module.__file__ = str(SOURCE)
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"spider_xhs", "xhs_auth_helper", "dotenv", "qrcode", "_shared"}:
            forbidden()
        return original_import(name, *args, **kwargs)

    with monkeypatch.context() as guard:
        guard.setattr(builtins, "__import__", guarded_import)
        guard.setattr(builtins, "open", forbidden)
        for name in ("open", "read_bytes", "read_text", "write_text", "mkdir"):
            guard.setattr(Path, name, forbidden)
        guard.setattr(socket, "socket", forbidden)
        guard.setattr(socket, "create_connection", forbidden)
        exec(compile(ast.parse(source), str(SOURCE), "exec"), module.__dict__)
    return module


@pytest.mark.parametrize("raw,expected", [
    (0, 0), (123, 123), (0.0, 0), (1234.0, 1234), ("0", 0), (" 42 ", 42),
    ("1.2万", 12000), ("1.25w", 12500), ("1.2W+", 12000), ("2万+", 20000),
    ("1.5k", 1500), ("1.234K", 1234), ("2.4千", 2400), ("0.1万", 1000),
    ("1,234", 1234), ("12，345", 12345), ("1,234,567+", 1234567),
    ("1,234.5k+", 1234500), (" 1.2 万+ ", 12000), (Decimal("12.0"), 12),
])
def test_count_formats(research, raw, expected):
    result = research.to_int(raw)
    assert result == expected
    assert type(result) is int


@pytest.mark.parametrize("raw", [
    None, True, False, "True", "false", "", " ", "未知", "--", "暂无", "1,23",
    "1,234，56", "1..2万", "1w2", "+", "++1", "-1", -1, "1%", "NaN", "inf",
    float("nan"), float("inf"), Decimal("NaN"), {}, [], 1.5, "0.1", "0.00001万",
])
def test_unknown_is_not_zero(research, raw):
    assert research.to_int(raw) is None


@pytest.mark.parametrize("inter,expected", [
    ({"liked": True, "collected": False}, (None, None, None)),
    ({"liked": False, "collected": True, "comment": True}, (None, None, None)),
    ({"liked": True, "liked_count": "1.2万", "collected": True,
      "collected_count": "1,234", "comment_count": "2.5k"}, (12000, 1234, 2500)),
    ({"liked": True, "liked_count": 0, "collected": True, "collected_count": "0"}, (0, 0, None)),
    ({"liked_count": True, "collected_count": False}, (None, None, None)),
    ({"liked": "2.5k", "collected": "1.2w", "comment": "3,000"}, (2500, 12000, 3000)),
    ({}, (None, None, None)),
])
@pytest.mark.parametrize("nested", [True, False])
def test_search_state_flags_do_not_override_counts(research, inter, expected, nested):
    card = {"note_id": "offline", "interact_info": inter}
    note = {"id": "offline", "note_card": card} if nested else card
    item = research.parse_search_item(note)
    assert (item["likes"], item["collects"], item["comments"]) == expected


@pytest.mark.parametrize("detail", [None, {}, {"data": None}, {"data": {"items": []}},
                                      {"data": {"items": [None]}}])
def test_missing_detail_counts_stay_unknown(research, detail):
    result = research.parse_detail_metrics(detail)
    assert result == {"detail_likes": None, "detail_collects": None, "detail_comments": None, "tags": []}


def test_detail_uses_raw_numbers_not_shared_zero_fallback(research):
    result = research.parse_detail_metrics({"data": {"items": [{"note_card": {
        "interact_info": {"liked_count": "1.2万", "collected_count": True, "comment_count": "1,234"},
        "tag_list": [{"name": "fixture"}],
    }}]}})
    assert result == {"detail_likes": 12000, "detail_collects": None,
                      "detail_comments": 1234, "tags": ["fixture"]}


def test_sort_and_statistics_distinguish_unknown_from_zero(research):
    items = [{"likes": None}, {"likes": True}, {"likes": "0"}, {"likes": "1.2w"}, {"likes": "2k"}]
    ranked = sorted(items, key=research.like_sort_key, reverse=True)
    assert [item["likes"] for item in ranked] == ["1.2w", "2k", "0", None, True]
    assert research.likes_summary(items) == {
        "likes_known": 3, "likes_unknown": 2, "likes_max": 12000, "likes_median": 2000,
    }
    assert research.likes_summary([{"likes": "0"}, {"likes": "1"}])["likes_median"] == 0.5
    assert research.format_count(None) == research.format_count(False) == "未知"
    assert research.format_count(0) == "0"


@pytest.mark.parametrize("items", [[], [{"likes": None}], [{"likes": True}, {"likes": "unknown"}]])
def test_no_observations_have_no_numeric_statistics(research, items):
    summary = research.likes_summary(items)
    assert summary["likes_max"] is None and summary["likes_median"] is None
    assert summary["likes_known"] == 0 and summary["likes_unknown"] == len(items)


def test_main_all_count_call_sites_offline(research, tmp_path, monkeypatch, capsys):
    """搜索/详情/认证/二维码全部 stub，覆盖排序、详情回填、统计与终端格式化。"""
    def note(note_id, **inter):
        return {"id": note_id, "model_type": "note", "note_card": {"interact_info": inter}}

    api = Mock()
    api.bootstrap.return_value = api
    api.search_some_note.side_effect = [
        (True, "", [{**note("unknown", liked=True, collected=False), "xsec_token": "PRIVATE-LINK-TOKEN"}]),
        (True, "", [note("missing"), note("zero", liked_count=0), note("many", liked_count="1.2w")]),
        (True, "", []),
        (False, "offline search failure", []),
    ]
    api.get_note_info.return_value = (True, "", {"data": {"items": [{"note_card": {
        "interact_info": {"liked": True, "collected": False, "comment_count": "1.5k"}
    }}]}})
    vendor = ModuleType("spider_xhs")
    vendor.XHS_Apis = Mock(return_value=api)
    auth = ModuleType("xhs_auth_helper")
    auth.get_pc_auth = Mock(return_value=object())
    qr = ModuleType("qrcode")

    class QRCode:
        add_data = forbidden
        print_ascii = forbidden

    qr.QRCode = QRCode
    monkeypatch.setitem(sys.modules, "spider_xhs", vendor)
    monkeypatch.setitem(sys.modules, "xhs_auth_helper", auth)
    monkeypatch.setitem(sys.modules, "qrcode", qr)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(research.time, "sleep", Mock())
    monkeypatch.setattr(research, "SEARCHES", [(f"fixture-{i}", 0, 0, 3) for i in range(4)])
    output = tmp_path / "research.json"
    monkeypatch.setattr(research, "OUT", output)
    original_open = Path.open

    def only_output(path, *args, **kwargs):
        assert path == output, f"unexpected path access: {path}"
        return original_open(path, *args, **kwargs)

    with monkeypatch.context() as guard:
        guard.setattr(Path, "open", only_output)
        guard.setattr(builtins, "open", forbidden)
        guard.setattr(socket, "socket", forbidden)
        guard.setattr(socket, "create_connection", forbidden)
        research.main()
    queries = json.loads(output.read_text(encoding="utf-8"))["queries"]
    assert queries[0]["likes_median"] is None and queries[0]["likes_max"] is None
    assert queries[0]["items"][0]["likes"] is None
    assert queries[0]["items"][0]["collects"] is None
    assert queries[1]["likes_median"] == 6000
    assert queries[1]["likes_known"] == 2 and queries[1]["likes_unknown"] == 1
    assert queries[2]["likes_median"] is None and queries[2]["title_price_signal_rate"] is None
    assert queries[3]["error"] == "search_failed"
    assert "PRIVATE-LINK-TOKEN" not in output.read_text(encoding="utf-8")
    for query in queries[:2]:
        for item in query["items"]:
            assert item["detail_likes"] is None and item["detail_collects"] is None
            assert item["detail_comments"] == 1500
    detail_urls = [call.args[0] for call in api.get_note_info.call_args_list]
    assert detail_urls[1:] == [f"https://www.xiaohongshu.com/explore/{key}" for key in ("many", "zero", "missing")]
    assert "未知" in capsys.readouterr().out
    auth.get_pc_auth.assert_called_once_with()
