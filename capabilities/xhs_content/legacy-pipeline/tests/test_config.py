"""Tests for core.config — 配置和数据持久化函数。"""

import json
import os
from unittest.mock import patch

import pytest

from core.config import (
    _atomic_write_json,
    _grade_from_likes,
    ensure_dirs,
    load_performance_json,
    load_topics_json,
    save_performance_json,
    save_topics_json,
    update_note_performance,
    validate_env,
    _write_json_atomic,
)


class TestGradeFromLikes:
    """测试 _grade_from_likes（委托给 publish_helpers.calculate_grade）。"""

    def test_zero_likes_is_c(self):
        assert _grade_from_likes(0) == "C"

    def test_low_likes_is_c(self):
        assert _grade_from_likes(199) == "C"

    def test_medium_likes_is_b(self):
        assert _grade_from_likes(200) == "B"
        assert _grade_from_likes(799) == "B"

    def test_high_likes_is_a(self):
        assert _grade_from_likes(800) == "A"
        assert _grade_from_likes(1500) == "A"

    def test_very_high_likes_is_s(self):
        assert _grade_from_likes(1501) == "S"
        assert _grade_from_likes(10000) == "S"


class TestAtomicWriteJson:
    """测试 _atomic_write_json 原子写入。"""

    def test_writes_valid_json(self, tmp_path):
        target = tmp_path / "test.json"
        data = {"key": "value", "nested": {"a": 1}}
        _atomic_write_json(target, data, with_lock=False)
        result = json.loads(target.read_text(encoding="utf-8"))
        assert result == data

    def test_creates_parent_dirs(self, tmp_path):
        target = tmp_path / "sub" / "dir" / "test.json"
        _atomic_write_json(target, {"ok": True}, with_lock=False)
        assert target.exists()
        assert json.loads(target.read_text()) == {"ok": True}

    def test_overwrites_existing(self, tmp_path):
        target = tmp_path / "test.json"
        _atomic_write_json(target, {"v": 1}, with_lock=False)
        _atomic_write_json(target, {"v": 2}, with_lock=False)
        assert json.loads(target.read_text()) == {"v": 2}

    def test_cleans_temp_on_error(self, tmp_path):
        target = tmp_path / "test.json"
        with patch("core.config._write_json_atomic", side_effect=IOError("disk full")):
            with pytest.raises(IOError):
                _atomic_write_json(target, {"x": 1}, with_lock=False)
        # 临时文件不应残留
        json_files = list(tmp_path.glob("*.json"))
        assert len(json_files) == 0


class TestWriteJsonAtomic:
    """测试 _write_json_atomic 实际写入逻辑。"""

    def test_normal_write(self, tmp_path):
        target = tmp_path / "data.json"
        _write_json_atomic(target, {"中文": "测试"})
        result = json.loads(target.read_text(encoding="utf-8"))
        assert result == {"中文": "测试"}

    def test_unicode_preserved(self, tmp_path):
        target = tmp_path / "data.json"
        data = {"emoji": "💔", "chinese": "你好世界"}
        _write_json_atomic(target, data)
        result = json.loads(target.read_text(encoding="utf-8"))
        assert result == data


class TestLoadTopicsJson:
    """测试 load_topics_json。"""

    def test_load_existing_file(self, tmp_path, sample_topics):
        target = tmp_path / "topics.json"
        target.write_text(json.dumps(sample_topics, ensure_ascii=False), encoding="utf-8")
        with patch("core.config.DATA_DIR", tmp_path):
            result = load_topics_json()
        assert result == sample_topics

    def test_missing_file_raises(self, tmp_path):
        with patch("core.config.DATA_DIR", tmp_path):
            with pytest.raises(FileNotFoundError, match="选题池文件不存在"):
                load_topics_json()


class TestSaveTopicsJson:
    """测试 save_topics_json。"""

    def test_save_and_reload(self, tmp_path, sample_topics):
        with patch("core.config.DATA_DIR", tmp_path):
            save_topics_json(sample_topics)
            result = load_topics_json()
        assert result == sample_topics


class TestLoadPerformanceJson:
    """测试 load_performance_json。"""

    def test_load_existing_file(self, tmp_path, sample_performance):
        target = tmp_path / "performance.json"
        target.write_text(json.dumps(sample_performance, ensure_ascii=False), encoding="utf-8")
        with patch("core.config.DATA_DIR", tmp_path):
            result = load_performance_json()
        assert result == sample_performance

    def test_missing_file_returns_template(self, tmp_path):
        with patch("core.config.DATA_DIR", tmp_path):
            result = load_performance_json()
        assert result["notes"] == []
        assert result["summary"]["total_published"] == 0
        assert "s_grade_count" in result["summary"]


class TestSavePerformanceJson:
    """测试 save_performance_json。"""

    def test_save_and_reload(self, tmp_path, sample_performance):
        with patch("core.config.DATA_DIR", tmp_path):
            save_performance_json(sample_performance)
            result = load_performance_json()
        assert result == sample_performance


class TestUpdateNotePerformance:
    """测试 update_note_performance。"""

    def test_update_existing_topic(self, tmp_path, sample_performance):
        with patch("core.config.DATA_DIR", tmp_path):
            save_performance_json(sample_performance)
            result = update_note_performance("测试选题1", {"likes": 999, "exposure": 8000})
        assert result is True
        with patch("core.config.DATA_DIR", tmp_path):
            data = load_performance_json()
        note = next(n for n in data["notes"] if n["topic"] == "测试选题1")
        assert note["likes"] == 999
        assert note["exposure"] == 8000
        assert note["grade"] == "A"  # 999 likes → A

    def test_update_grade_changes(self, tmp_path, sample_performance):
        with patch("core.config.DATA_DIR", tmp_path):
            save_performance_json(sample_performance)
            update_note_performance("测试选题2", {"likes": 2000})
            data = load_performance_json()
        note = next(n for n in data["notes"] if n["topic"] == "测试选题2")
        assert note["grade"] == "S"  # 2000 likes → S

    def test_topic_not_found_returns_false(self, tmp_path, sample_performance):
        with patch("core.config.DATA_DIR", tmp_path):
            save_performance_json(sample_performance)
            result = update_note_performance("不存在的选题", {"likes": 100})
        assert result is False


class TestValidateEnv:
    """测试 validate_env。"""

    def test_with_valid_key(self):
        with patch.dict(os.environ, {"LLM_API_KEY": "sk-test123"}):
            validate_env()  # 应不抛异常

    def test_with_kimi_key(self):
        with patch.dict(os.environ, {"LLM_API_KEY": "", "KIMI_API_KEY": "kimi-key"}):
            validate_env()

    def test_missing_key_raises(self):
        with patch.dict(os.environ, {"LLM_API_KEY": "", "KIMI_API_KEY": ""}, clear=False):
            with pytest.raises(RuntimeError, match="LLM_API_KEY 未配置"):
                validate_env()


class TestEnsureDirs:
    """测试 ensure_dirs。"""

    def test_creates_directories(self, tmp_path):
        with patch("core.config.DATA_DIR", tmp_path / "data"):
            with patch("core.config.DOCS_AGENT_DIR", tmp_path / "docs_agent"):
                with patch("core.config.PENDING_DIR", tmp_path / "docs_agent" / "pending"):
                    with patch("core.config.PUBLISHED_DIR", tmp_path / "docs_agent" / "published"):
                        with patch("core.config.ARCHIVED_DIR", tmp_path / "docs_agent" / "archived"):
                            ensure_dirs()
        assert (tmp_path / "data").is_dir()
        assert (tmp_path / "docs_agent" / "pending").is_dir()
        assert (tmp_path / "docs_agent" / "published").is_dir()
        assert (tmp_path / "docs_agent" / "archived").is_dir()

    def test_idempotent(self, tmp_path):
        with patch("core.config.DATA_DIR", tmp_path / "data"):
            with patch("core.config.DOCS_AGENT_DIR", tmp_path / "docs_agent"):
                with patch("core.config.PENDING_DIR", tmp_path / "docs_agent" / "pending"):
                    with patch("core.config.PUBLISHED_DIR", tmp_path / "docs_agent" / "published"):
                        with patch("core.config.ARCHIVED_DIR", tmp_path / "docs_agent" / "archived"):
                            ensure_dirs()
                            ensure_dirs()  # 第二次不应报错
        assert (tmp_path / "data").is_dir()
