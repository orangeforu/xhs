"""共享测试 fixtures。"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def tmp_data_dir(tmp_path):
    """创建临时数据目录，隔离测试与真实数据。"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "agent_memory").mkdir()
    return data_dir


@pytest.fixture
def mock_memory_dir(tmp_data_dir):
    """Patch AGENT_MEMORY_DIR 到临时目录。"""
    with patch("core.agents.memory.AGENT_MEMORY_DIR", tmp_data_dir / "agent_memory"):
        yield tmp_data_dir / "agent_memory"


@pytest.fixture
def sample_performance():
    """返回一份标准的 performance.json 数据结构。"""
    return {
        "notes": [
            {
                "topic": "测试选题1",
                "title_formula": "问句式",
                "pillar": "亲密关系洞察",
                "grade": "A",
                "verdict": "pass",
                "rounds": 1,
                "likes": 500,
                "collects": 100,
                "comments": 50,
                "shares": 20,
                "exposure": 5000,
            },
            {
                "topic": "测试选题2",
                "title_formula": "观点冲击式",
                "pillar": "自我成长",
                "grade": "B",
                "verdict": "conditional",
                "rounds": 2,
                "likes": 100,
                "collects": 30,
                "comments": 10,
                "shares": 5,
                "exposure": 2000,
            },
        ],
        "summary": {
            "total_published": 2,
            "total_likes": 600,
            "total_collects": 130,
            "total_comments": 60,
            "total_shares": 25,
            "total_exposure": 7000,
            "s_grade_count": 0,
            "a_grade_count": 1,
            "b_grade_count": 1,
            "c_grade_count": 0,
            "current_streak_underperform": 0,
        },
    }


@pytest.fixture
def sample_topics():
    """返回一份标准的 topics.json 数据结构。"""
    return {
        "topics": [
            {
                "topic": "测试选题A",
                "title_formula": "问句式",
                "pillar": "亲密关系洞察",
                "target_interaction": "评论",
                "status": "not_started",
            },
            {
                "topic": "测试选题B",
                "title_formula": "观点冲击式",
                "pillar": "自我成长",
                "target_interaction": "收藏",
                "status": "generated",
            },
            {
                "topic": "测试选题C",
                "title_formula": "方法承诺式",
                "pillar": "社交关系",
                "target_interaction": "点赞",
                "status": "published",
            },
        ]
    }


@pytest.fixture
def mock_llm_response():
    """返回一个 mock 的 LLM JSON 响应。"""
    return json.dumps({
        "verdict": "pass",
        "grade": "A",
        "issues": [],
        "suggestions": [{"location": "结尾", "idea": "可以加一个互动钩子"}],
        "strengths": ["情绪真实", "画面感强"],
        "overall_comment": "整体质量不错",
        "needs_redesign": False,
        "needs_relayout": False,
    }, ensure_ascii=False)
