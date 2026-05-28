import json
import re

from core.agents.base import BaseAgent, MessageBus, Message, MessageType
from core.config import get_logger, load_performance_json
from core.utils import load_prompt

logger = get_logger(__name__)


class TopicStrategist(BaseAgent):
    """选题策划师 Agent — 基于数据给出选题策略建议。"""

    def __init__(self, bus: MessageBus):
        prompt = load_prompt("agent_topic_strategist")
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
- story_prototype: {brief.get("story_prototype", "")}
- controversy_anchor: {brief.get("controversy_anchor", "")}

**历史表现摘要**：
{json.dumps(performance, ensure_ascii=False, indent=2)}

请输出结构化的策略建议和 enriched brief。特别关注：
1. 故事原型是否足够有画面感？是否需要调整？
2. 争议锚点是否能引发站队？是否有更强的争议角度？
3. 基于历史数据，这个选题的标题公式和互动目标是否最优？
"""
        raw = self.think(prompt, temperature=0.6, max_tokens=1200)

        # 解析 enriched brief（简单提取 key-value）
        enriched = dict(brief)
        enriched["_strategy_comment"] = raw

        # 尝试从 raw 中提取关键字段
        for key in ["title_formula", "target_interaction", "angle", "emotional_hook", "visual_direction", "story_prototype", "controversy_anchor"]:
            m = re.search(rf'{key}[：:]\s*(.+?)(?:\n|$)', raw, re.IGNORECASE)
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
        """加载 performance 数据的摘要（使用 config 的原子读取）。"""
        data = load_performance_json()
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

    def handle(self, message: Message):
        pass
