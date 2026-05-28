from core.agents.base import BaseAgent, MessageBus, Message, MessageType
from core.config import get_logger
from core.utils import load_prompt, extract_json_from_llm

logger = get_logger(__name__)


class ContentEditor(BaseAgent):
    """内容审核官 Agent — 深度审核 + 读者体验视角，给出可执行的修改建议。"""

    def __init__(self, bus: MessageBus):
        prompt = load_prompt("agent_editor")
        super().__init__("content_editor", prompt, bus)
        self.reader_prompt = load_prompt("review")

    def review(self, note_content: str, round_num: int = 0) -> dict:
        """审核笔记，返回结构化审核报告（含读者体验视角）。"""
        # 第一轮：专业审核
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

        # 第二轮：读者体验视角（并行不阻塞主审核，失败不影响结果）
        reader_data = self._reader_experience_review(note_content)

        # 合并读者体验数据
        if reader_data:
            parsed["reader_experience"] = reader_data
            # 如果读者体验评分比专业审核低，降级并加入 issues
            reader_grade = reader_data.get("grade", "B")
            grade_order = {"S": 0, "A": 1, "B": 2, "C": 3}
            current = grade_order.get(parsed.get("grade", "B"), 2)
            reader = grade_order.get(reader_grade, 2)
            if reader > current:
                logger.info(
                    "读者体验评分 (%s) 低于专业审核 (%s)，降级",
                    reader_grade, parsed.get("grade"),
                )
                parsed["grade"] = reader_grade
                # 更新 verdict
                if reader_grade == "C":
                    parsed["verdict"] = "fail"
                elif reader_grade == "B":
                    if parsed.get("verdict") == "pass":
                        parsed["verdict"] = "conditional"

            # 将读者体验中发现的质量问题合并到 issues
            quality_issues = reader_data.get("quality_issues", [])
            quality_suggestions = reader_data.get("quality_suggestions", [])
            default_suggestion = quality_suggestions[0] if quality_suggestions else "参考读者体验反馈修改"
            for qi in quality_issues[:3]:
                if isinstance(qi, str):
                    parsed.setdefault("issues", []).append({
                        "location": "读者体验",
                        "problem": qi,
                        "suggestion": default_suggestion,
                    })

            # 将讨论潜力低作为 suggestion
            if reader_data.get("discussion_potential") == "low":
                parsed.setdefault("suggestions", []).append({
                    "location": "全文",
                    "idea": "读者体验视角认为讨论潜力低，建议增加争议性或站队感",
                })

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

    def _reader_experience_review(self, note_content: str) -> dict | None:
        """读者体验视角审核，失败返回 None。"""
        try:
            reader_prompt_filled = self.reader_prompt.replace("{note_content}", note_content)
            raw = self.think(reader_prompt_filled, temperature=0.5, max_tokens=1500)
            parsed = extract_json_from_llm(raw)
            if parsed:
                return parsed
        except Exception as e:
            logger.warning("读者体验审核失败（不影响主审核）: %s", e)
        return None

    def _parse_review(self, raw: str) -> dict:
        """解析 LLM 输出的审核 JSON。"""
        parsed = extract_json_from_llm(raw)
        if parsed:
            parsed.setdefault("verdict", "conditional")
            parsed.setdefault("grade", "B")
            parsed.setdefault("issues", [])
            parsed.setdefault("suggestions", [])
            parsed.setdefault("strengths", [])
            parsed.setdefault("overall_comment", "")
            parsed.setdefault("needs_redesign", False)
            parsed.setdefault("needs_relayout", False)
            return parsed

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
            # 收到初稿，记录字数用于统计
            content = message.content.get("content", "")
            round_num = message.round_num
            logger.debug("审核官收到第 %d 轮稿件，字数约 %d", round_num, len(content))

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
            mem.record_mediocre(context)
