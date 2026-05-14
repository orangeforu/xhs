import json
import re

from core.agents.base import BaseAgent, MessageBus, Message, MessageType
from core.config import get_logger, PROMPTS_DIR

logger = get_logger(__name__)


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt 文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class ContentEditor(BaseAgent):
    """内容审核官 Agent — 深度审核，给出可执行的修改建议。"""

    def __init__(self, bus: MessageBus):
        prompt = _load_prompt("agent_editor")
        super().__init__("content_editor", prompt, bus)

    def review(self, note_content: str, round_num: int = 0) -> dict:
        """审核笔记，返回结构化审核报告。"""
        review_prompt = f"""请严格审核以下小红书笔记内容。

**笔记内容**：
{note_content}

请从情绪冲击力、画面感与感官密度、金句新鲜度、故事独特度、基础禁忌五个维度进行审核。

你的审核报告必须具体到位置和内容，给出可执行的修改建议。

请以 JSON 格式输出：
{{
  "verdict": "pass|conditional|fail",
  "grade": "A|B|C",
  "issues": [{{"location": "...", "problem": "...", "suggestion": "..."}}],
  "suggestions": [{{"location": "...", "idea": "..."}}],
  "strengths": ["..."],
  "overall_comment": "...",
  "needs_redesign": false,
  "needs_relayout": false
}}

verdict 规则：
- pass: 几乎没有 issues，可以直接发布
- conditional: 有1-3个小问题，修改后可以发布
- fail: 有重大结构性问题，必须重写

needs_redesign: 如果封面设计与内容情绪可能不符（比如内容很温暖但缺少视觉锚点），标记为 true
needs_relayout: 如果排版或分页有问题，标记为 true
"""
        raw = self.think(review_prompt, temperature=0.3, max_tokens=2500)
        parsed = self._parse_review(raw)

        result = {
            **parsed,
            "round_num": round_num,
            "raw": raw,
        }

        # 广播审核结果
        self.send(to_agent=None, msg_type=MessageType.REVIEW, content=result, round_num=round_num)

        grade = parsed.get("grade", "B")
        verdict = parsed.get("verdict", "conditional")
        logger.info("审核官完成第 %d 轮审核: grade=%s, verdict=%s", round_num, grade, verdict)
        return result

    def _parse_review(self, raw: str) -> dict:
        """解析 LLM 输出的审核 JSON。"""
        # 尝试提取 JSON 块
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group())
                # 标准化
                parsed.setdefault("verdict", "conditional")
                parsed.setdefault("grade", "B")
                parsed.setdefault("issues", [])
                parsed.setdefault("suggestions", [])
                parsed.setdefault("strengths", [])
                parsed.setdefault("overall_comment", "")
                parsed.setdefault("needs_redesign", False)
                parsed.setdefault("needs_relayout", False)
                return parsed
            except json.JSONDecodeError:
                pass

        logger.warning("审核结果 JSON 解析失败，回退文本解析")
        # fallback 文本解析
        grade = "B"
        if '"grade": "A"' in raw or "grade: A" in raw:
            grade = "A"
        elif '"grade": "C"' in raw or "grade: C" in raw:
            grade = "C"

        verdict = "conditional"
        if "verdict" in raw:
            if "pass" in raw.lower():
                verdict = "pass"
            elif "fail" in raw.lower():
                verdict = "fail"

        return {
            "verdict": verdict,
            "grade": grade,
            "issues": [],
            "suggestions": [],
            "strengths": [],
            "overall_comment": raw[:500],
            "needs_redesign": False,
            "needs_relayout": False,
        }

    def handle(self, message: Message):
        """处理消息总线消息。"""
        if message.msg_type == MessageType.DRAFT:
            # 收到新 draft，可以自动触发审核（由 orchestrator 控制是否调用）
            pass

    def record_outcome(self, grade: str, topic: str):
        """记录审核结果。"""
        from core.agents.memory import AgentMemory
        mem = AgentMemory(self.name)
        context = {"topic": topic, "grade": grade}
        if grade in ("A", "S"):
            mem.record_success(context)
        elif grade == "C":
            mem.record_failure(context)
        else:
            mem.data["total_runs"] = mem.data.get("total_runs", 0) + 1
            mem.save()
