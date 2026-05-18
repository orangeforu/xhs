import json

from core.agents.base import BaseAgent, MessageBus, Message, MessageType
from core.config import get_logger, PROMPTS_DIR, DATA_DIR

logger = get_logger(__name__)


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt 文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class TopicStrategist(BaseAgent):
    """选题策划师 Agent — 基于数据给出选题策略建议。"""

    def __init__(self, bus: MessageBus):
        prompt = _load_prompt("agent_topic_strategist")
        super().__init__("topic_strategist", prompt, bus)

    def enrich_brief(self, brief: dict, round_num: int = 0) -> dict:
        """基于 performance 数据增强 brief。"""
        # 加载 performance 数据
        performance = self._load_performance_summary()

        prompt = f"""请基于以下选题和历史数据，给出策略建议。

**原始选题**：
- topic: {brief.get("topic", "")}
- title_formula: {brief.get("title_formula", "问句式")}
- target_interaction: {brief.get("target_interaction", "点赞")}
- angle: {brief.get("angle", "")}

**历史表现摘要**：
{json.dumps(performance, ensure_ascii=False, indent=2)}

请输出结构化的策略建议和 enriched brief。
"""
        raw = self.think(prompt, temperature=0.6, max_tokens=1200)

        # 解析 enriched brief（简单提取 key-value）
        enriched = dict(brief)
        enriched["_strategy_comment"] = raw

        # 尝试从 raw 中提取关键字段
        for key in ["title_formula", "target_interaction", "angle", "emotional_hook", "visual_direction"]:
            m = __import__('re').search(rf'{key}[：:]\s*(.+?)(?:\n|$)', raw, __import__('re').IGNORECASE)
            if m:
                enriched[key] = m.group(1).strip()

        result = {
            "original_brief": brief,
            "enriched_brief": enriched,
            "strategy": raw,
            "round_num": round_num,
        }

        self.send(to_agent=None, msg_type=MessageType.BRIEF, content=result, round_num=round_num)
        logger.info("选题策划师完成 brief 增强")
        return enriched

    def _load_performance_summary(self) -> dict:
        """加载 performance 数据的摘要。"""
        path = DATA_DIR / "performance.json"
        if not path.exists():
            return {"notes": [], "summary": {}}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            notes = data.get("notes", [])
            if not notes:
                return {"notes": [], "summary": data.get("summary", {})}
            # 生成摘要：按 title_formula 统计表现
            formula_stats = {}
            for n in notes:
                formula = n.get("title_formula", "未知")
                grade = n.get("grade", "B")
                if formula not in formula_stats:
                    formula_stats[formula] = {"count": 0, "grades": []}
                formula_stats[formula]["count"] += 1
                formula_stats[formula]["grades"].append(grade)
            return {
                "total_notes": len(notes),
                "formula_stats": formula_stats,
                "summary": data.get("summary", {}),
            }
        except Exception as e:
            logger.warning("加载 performance 数据失败: %s", e)
            return {"notes": [], "summary": {}}

    def handle(self, message: Message):
        pass
