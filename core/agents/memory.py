import json
from pathlib import Path
from typing import Any

from core.config import DATA_DIR, get_logger, _atomic_write_json

logger = get_logger(__name__)

AGENT_MEMORY_DIR = DATA_DIR / "agent_memory"


class AgentMemory:
    """Agent 跨会话持久化记忆。"""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.path = AGENT_MEMORY_DIR / f"{agent_name}.json"
        self.data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("加载 %s 记忆失败: %s", self.agent_name, e)
        return {
            "success_patterns": [],
            "failure_patterns": [],
            "style_preferences": {},
            "collaboration_notes": {},
            "total_runs": 0,
            "success_count": 0,
            "version": 1,
        }

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(self.path, self.data)

    def record_success(self, context: dict):
        # 去重：同一 topic 不重复记录
        topic = context.get("topic", "")
        self.data["success_patterns"] = [
            p for p in self.data["success_patterns"] if p.get("topic") != topic
        ]
        self.data["success_patterns"].append(context)
        self.data["success_patterns"] = self.data["success_patterns"][-10:]
        self.data["success_count"] += 1
        self.data["total_runs"] += 1
        self.save()

    def record_failure(self, context: dict):
        # 去重：同一 topic 不重复记录
        topic = context.get("topic", "")
        self.data["failure_patterns"] = [
            p for p in self.data["failure_patterns"] if p.get("topic") != topic
        ]
        self.data["failure_patterns"].append(context)
        self.data["failure_patterns"] = self.data["failure_patterns"][-10:]
        self.data["total_runs"] += 1
        self.save()

    def record_mediocre(self, context: dict):
        """记录 B 级平庸内容，用于学习什么内容只是'及格'。"""
        key = "mediocre_patterns"
        if key not in self.data:
            self.data[key] = []
        topic = context.get("topic", "")
        self.data[key] = [
            p for p in self.data[key] if p.get("topic") != topic
        ]
        self.data[key].append(context)
        self.data[key] = self.data[key][-10:]
        self.data["total_runs"] += 1
        self.save()

    def add_collaboration_note(self, partner: str, note: str):
        notes = self.data.setdefault("collaboration_notes", {})
        partner_notes = notes.setdefault(partner, [])
        partner_notes.append(note)
        notes[partner] = partner_notes[-5:]
        self.save()

    def update_style_preference(self, key: str, value: Any):
        self.data.setdefault("style_preferences", {})[key] = value
        self.save()

    def get_context(self) -> str:
        """生成记忆上下文文本，注入到 prompt 中。"""
        parts = []

        if self.data.get("success_patterns"):
            parts.append("【你过去成功的经验 — 保持这些做法】")
            for p in self.data["success_patterns"][-3:]:
                parts.append(f"- {json.dumps(p, ensure_ascii=False)}")

        if self.data.get("failure_patterns"):
            parts.append("【你过去失败的教训 — 避免重蹈覆辙】")
            for p in self.data["failure_patterns"][-3:]:
                parts.append(f"- {json.dumps(p, ensure_ascii=False)}")
            parts.append("请特别注意：以上失败案例中的问题，在本次创作中必须避免。")

        if self.data.get("mediocre_patterns"):
            parts.append("【过去表现平庸的内容 — 这些内容及格但没有引爆，思考如何超越】")
            for p in self.data["mediocre_patterns"][-3:]:
                parts.append(f"- {json.dumps(p, ensure_ascii=False)}")

        if self.data.get("style_preferences"):
            parts.append("【你积累的风格偏好】")
            for k, v in list(self.data["style_preferences"].items())[-5:]:
                parts.append(f"- {k}: {v}")

        stats = self.get_stats()
        if stats["total_runs"] > 0:
            parts.append(
                f"【你的历史表现】共 {stats['total_runs']} 次，"
                f"成功率 {stats['success_rate']:.0%}。"
                f"{'保持水准，争取突破S级。' if stats['success_rate'] > 0.7 else '需要提升质量，关注失败教训。'}"
            )

        return "\n".join(parts) if parts else ""

    def get_stats(self) -> dict:
        total = self.data.get("total_runs", 0)
        success = self.data.get("success_count", 0)
        return {
            "total_runs": total,
            "success_count": success,
            "success_rate": success / max(total, 1),
        }
