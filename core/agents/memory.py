import json
from pathlib import Path
from typing import Any

from core.config import DATA_DIR, get_logger

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
            except (json.JSONDecodeError, Exception) as e:
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
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def record_success(self, context: dict):
        self.data["success_patterns"].append(context)
        self.data["success_patterns"] = self.data["success_patterns"][-10:]
        self.data["success_count"] += 1
        self.data["total_runs"] += 1
        self.save()

    def record_failure(self, context: dict):
        self.data["failure_patterns"].append(context)
        self.data["failure_patterns"] = self.data["failure_patterns"][-10:]
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
            parts.append("【你过去成功的经验】")
            for p in self.data["success_patterns"][-3:]:
                parts.append(f"- {json.dumps(p, ensure_ascii=False)}")

        if self.data.get("failure_patterns"):
            parts.append("【你过去失败的教训（避免重蹈覆辙）】")
            for p in self.data["failure_patterns"][-3:]:
                parts.append(f"- {json.dumps(p, ensure_ascii=False)}")

        if self.data.get("style_preferences"):
            parts.append("【你积累的风格偏好】")
            for k, v in list(self.data["style_preferences"].items())[-5:]:
                parts.append(f"- {k}: {v}")

        return "\n".join(parts) if parts else ""

    def get_stats(self) -> dict:
        total = self.data.get("total_runs", 0)
        success = self.data.get("success_count", 0)
        return {
            "total_runs": total,
            "success_count": success,
            "success_rate": success / max(total, 1),
        }
