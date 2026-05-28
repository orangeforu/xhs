import json
import threading
from typing import Any

from core.config import DATA_DIR, get_logger, _atomic_write_json

logger = get_logger(__name__)

AGENT_MEMORY_DIR = DATA_DIR / "agent_memory"


class AgentMemory:
    """Agent 跨会话持久化记忆。"""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.path = AGENT_MEMORY_DIR / f"{agent_name}.json"
        self._lock = threading.Lock()
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
            "mediocre_patterns": [],
            "style_preferences": {},
            "collaboration_notes": {},
            "formula_performance": {},
            "pillar_performance": {},
            "total_runs": 0,
            "success_count": 0,
            "version": 2,
        }

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(self.path, self.data)

    def record_success(self, context: dict):
        # 去重：同一 topic 不重复记录
        topic = context.get("topic", "")
        with self._lock:
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
        with self._lock:
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
        topic = context.get("topic", "")
        with self._lock:
            if key not in self.data:
                self.data[key] = []
            self.data[key] = [
                p for p in self.data[key] if p.get("topic") != topic
            ]
            self.data[key].append(context)
            self.data[key] = self.data[key][-10:]
            self.data["total_runs"] += 1
        self.save()

    def add_collaboration_note(self, partner: str, note: str):
        with self._lock:
            notes = self.data.setdefault("collaboration_notes", {})
            partner_notes = notes.setdefault(partner, [])
            partner_notes.append(note)
            notes[partner] = partner_notes[-5:]
        self.save()

    def update_style_preference(self, key: str, value: Any):
        with self._lock:
            self.data.setdefault("style_preferences", {})[key] = value
        self.save()

    @staticmethod
    def _format_pattern(p: dict) -> str:
        """将 pattern dict 格式化为人类可读的单行摘要。"""
        topic = p.get("topic", "未知选题")
        grade = p.get("grade", "")
        formula = p.get("formula", "")
        pillar = p.get("pillar", "")
        rounds = p.get("rounds_used", "")
        parts = [f"「{topic}」"]
        if grade:
            parts.append(f"等级{grade}")
        if formula:
            parts.append(f"公式{formula}")
        if pillar:
            parts.append(f"支柱{pillar}")
        if rounds:
            parts.append(f"{rounds}轮")
        return "，".join(parts)

    def get_context(self) -> str:
        """生成记忆上下文文本，注入到 prompt 中。"""
        parts = []

        if self.data.get("success_patterns"):
            parts.append("【你过去成功的经验 — 保持这些做法】")
            for p in self.data["success_patterns"][-3:]:
                parts.append(f"- {self._format_pattern(p)}")

        if self.data.get("failure_patterns"):
            parts.append("【你过去失败的教训 — 避免重蹈覆辙】")
            for p in self.data["failure_patterns"][-3:]:
                parts.append(f"- {self._format_pattern(p)}")
            parts.append("请特别注意：以上失败案例中的问题，在本次创作中必须避免。")

        if self.data.get("mediocre_patterns"):
            parts.append("【过去表现平庸的内容 — 这些内容及格但没有引爆，思考如何超越】")
            for p in self.data["mediocre_patterns"][-3:]:
                parts.append(f"- {self._format_pattern(p)}")

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

        # 注入数据洞察
        insights = self.get_performance_insights()
        if insights:
            parts.append(insights)

        return "\n".join(parts) if parts else ""

    def get_stats(self) -> dict:
        total = self.data.get("total_runs", 0)
        success = self.data.get("success_count", 0)
        return {
            "total_runs": total,
            "success_count": success,
            "success_rate": success / max(total, 1),
        }

    def ingest_performance_data(self, notes: list[dict]):
        """从 performance.json 中学习公式和支柱的实际表现。"""
        formula_stats: dict[str, list[str]] = {}
        pillar_stats: dict[str, list[str]] = {}

        for n in notes:
            grade = n.get("grade", "B")
            formula = n.get("title_formula", "")
            pillar = n.get("pillar", "")

            if formula:
                formula_stats.setdefault(formula, []).append(grade)
            if pillar:
                pillar_stats.setdefault(pillar, []).append(grade)

        # 更新公式表现
        for formula, grades in formula_stats.items():
            avg_score = sum({"S": 1.0, "A": 0.8, "B": 0.5, "C": 0.1}.get(g, 0.5) for g in grades) / len(grades)
            self.data.setdefault("formula_performance", {})[formula] = {
                "count": len(grades),
                "avg_score": round(avg_score, 2),
                "grades": grades[-5:],  # 只保留最近5个
            }

        # 更新支柱表现
        for pillar, grades in pillar_stats.items():
            avg_score = sum({"S": 1.0, "A": 0.8, "B": 0.5, "C": 0.1}.get(g, 0.5) for g in grades) / len(grades)
            self.data.setdefault("pillar_performance", {})[pillar] = {
                "count": len(grades),
                "avg_score": round(avg_score, 2),
                "grades": grades[-5:],
            }

        self.save()
        logger.info("已从 %d 篇发布数据中学习公式和支柱表现", len(notes))

    def get_performance_insights(self) -> str:
        """生成基于实际数据的洞察文本。"""
        parts = []

        formula_perf = self.data.get("formula_performance", {})
        if formula_perf:
            best_formula = max(formula_perf.items(), key=lambda x: x[1]["avg_score"])
            worst_formula = min(formula_perf.items(), key=lambda x: x[1]["avg_score"])
            if best_formula[0] != worst_formula[0]:
                parts.append(
                    f"【数据洞察】最有效公式: {best_formula[0]}（{best_formula[1]['count']}篇，"
                    f"平均分 {best_formula[1]['avg_score']}）；"
                    f"最弱公式: {worst_formula[0]}（{worst_formula[1]['count']}篇，"
                    f"平均分 {worst_formula[1]['avg_score']}）。"
                )

        pillar_perf = self.data.get("pillar_performance", {})
        if pillar_perf:
            best_pillar = max(pillar_perf.items(), key=lambda x: x[1]["avg_score"])
            parts.append(
                f"【数据洞察】流量密码支柱: {best_pillar[0]}（{best_pillar[1]['count']}篇，"
                f"平均分 {best_pillar[1]['avg_score']}）。"
            )

        return "\n".join(parts) if parts else ""
