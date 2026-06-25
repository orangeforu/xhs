import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.agents.memory import AgentMemory


class TestAgentMemory(unittest.TestCase):
    def setUp(self):
        # 用临时目录避免污染真实数据
        self.tmpdir = tempfile.mkdtemp()
        self.patcher = patch("core.agents.memory.AGENT_MEMORY_DIR", Path(self.tmpdir))
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init_creates_default(self):
        mem = AgentMemory("test_agent")
        self.assertEqual(mem.data["total_runs"], 0)
        self.assertEqual(mem.data["success_count"], 0)

    def test_record_success(self):
        mem = AgentMemory("test_agent")
        mem.record_success({"topic": "test_topic", "grade": "A"})
        self.assertEqual(mem.data["success_count"], 1)
        self.assertEqual(mem.data["total_runs"], 1)
        self.assertEqual(len(mem.data["success_patterns"]), 1)

    def test_record_failure(self):
        mem = AgentMemory("test_agent")
        mem.record_failure({"topic": "test_topic", "grade": "C"})
        self.assertEqual(mem.data["total_runs"], 1)
        self.assertEqual(len(mem.data["failure_patterns"]), 1)

    def test_record_mediocre(self):
        mem = AgentMemory("test_agent")
        mem.record_mediocre({"topic": "test_topic", "grade": "B"})
        self.assertEqual(mem.data["total_runs"], 1)
        self.assertEqual(len(mem.data["mediocre_patterns"]), 1)

    def test_success_dedup(self):
        mem = AgentMemory("test_agent")
        mem.record_success({"topic": "same_topic", "grade": "A"})
        mem.record_success({"topic": "same_topic", "grade": "S"})
        self.assertEqual(len(mem.data["success_patterns"]), 1)
        self.assertEqual(mem.data["success_count"], 2)

    def test_max_patterns(self):
        mem = AgentMemory("test_agent")
        for i in range(15):
            mem.record_success({"topic": f"topic_{i}", "grade": "A"})
        self.assertLessEqual(len(mem.data["success_patterns"]), 10)

    def test_get_stats(self):
        mem = AgentMemory("test_agent")
        mem.record_success({"topic": "t1", "grade": "A"})
        mem.record_failure({"topic": "t2", "grade": "C"})
        stats = mem.get_stats()
        self.assertEqual(stats["total_runs"], 2)
        self.assertEqual(stats["success_count"], 1)
        self.assertAlmostEqual(stats["success_rate"], 0.5)

    def test_get_context_empty(self):
        mem = AgentMemory("test_agent")
        self.assertEqual(mem.get_context(), "")

    def test_get_context_with_data(self):
        mem = AgentMemory("test_agent")
        mem.record_success({"topic": "t1", "grade": "A"})
        ctx = mem.get_context()
        self.assertIn("成功", ctx)

    def test_atomic_save(self):
        mem = AgentMemory("test_agent")
        mem.record_success({"topic": "t1", "grade": "A"})
        mem.flush()  # 脏标记模式需要显式 flush
        # 验证文件存在且是有效 JSON
        path = os.path.join(self.tmpdir, "test_agent.json")
        self.assertTrue(os.path.exists(path))
        with open(path, "r") as f:
            data = json.load(f)
        self.assertEqual(data["success_count"], 1)


if __name__ == "__main__":
    unittest.main()
