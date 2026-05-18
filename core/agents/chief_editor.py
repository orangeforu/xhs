from concurrent.futures import ThreadPoolExecutor, as_completed

from core.agents.base import BaseAgent, MessageBus, Message, MessageType
from core.config import get_logger, PROMPTS_DIR

logger = get_logger(__name__)


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt 文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class ChiefEditor(BaseAgent):
    """主编 Agent — 协调所有专家，控制迭代流程，做最终决策。"""

    def __init__(self, bus: MessageBus):
        prompt = _load_prompt("agent_chief_editor")
        super().__init__("chief_editor", prompt, bus)

    def orchestrate(self, brief, writer, designer, artist, editor, community, out_dir: str) -> dict:
        """主流程编排。最多5轮迭代。"""
        round_num = 0
        draft = None
        review = None
        design_result = None
        inner_paths = []
        grade_history = []  # 记录每轮审核等级，防止死循环

        # ── Round 0: 初稿 ──
        logger.info("=" * 50)
        logger.info("主编启动创作流程: %s", brief["topic"])
        logger.info("=" * 50)

        draft = writer.write(brief, round_num=0)

        # ── 迭代循环 ──
        while round_num < 5:
            logger.info("--- 第 %d 轮迭代 ---", round_num)

            # 并行：封面设计、内页排版、内容审核
            parallel_tasks = []

            if round_num == 0 or (review and review.get("needs_redesign")):
                cover_path = f"{out_dir}/cover_ai.png"
                parallel_tasks.append(("design", lambda: designer.design(draft["content"], round_num=round_num, output_path=cover_path)))
            else:
                parallel_tasks.append(("design", lambda: design_result))

            if round_num == 0 or (review and review.get("needs_relayout")):
                parallel_tasks.append(("layout", lambda: artist.layout(draft["content"], style=self._extract_style(draft["content"]), out_dir=out_dir, round_num=round_num)))
            else:
                parallel_tasks.append(("layout", lambda: inner_paths))

            parallel_tasks.append(("review", lambda: editor.review(draft["content"], round_num=round_num)))

            results = {}
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(fn): name for name, fn in parallel_tasks}
                for future in as_completed(futures):
                    name = futures[future]
                    try:
                        results[name] = future.result()
                    except Exception as e:
                        logger.error("并行任务 %s 失败: %s", name, e)
                        results[name] = None

            if "design" in results:
                design_result = results["design"] or design_result
            if "layout" in results:
                inner_paths = results["layout"] or inner_paths
            if "review" in results:
                review = results["review"] or review

            # 记录本轮grade，用于检测死循环
            grade_history.append(review.get("grade", "B") if review else "B")

            # 主编决策
            decision = self._make_decision(draft, design_result, review, round_num, grade_history)

            if decision["action"] == "publish":
                logger.info("主编决策: 通过 (%s)", decision["reason"])
                break
            elif decision["action"] == "abandon":
                logger.warning("主编决策: 放弃 (%s)", decision["reason"])
                return {
                    "status": "abandoned",
                    "reason": decision["reason"],
                    "draft": draft,
                    "review": review,
                    "rounds": round_num + 1,
                }
            elif decision["action"] == "revise":
                round_num += 1
                feedback = decision["feedback"]
                logger.info("主编决策: 重写 (第 %d 轮)，核心问题: %s", round_num, decision.get("core_issue", "详见反馈"))
                draft = writer.write(brief, round_num=round_num, feedback=feedback)
            else:
                break

        # ── 生成预设评论 ──
        comments = community.generate_comments(draft["content"], round_num=round_num)

        # ── 记录各 agent 的学习记忆 ──
        grade = review.get("grade", "B") if review else "B"
        topic = brief["topic"]
        writer.record_outcome(grade, topic)
        editor.record_outcome(grade, topic)
        if design_result and design_result.get("design"):
            designer.record_outcome(grade, topic, design_result["design"].get("style", "warm_grey"))

        # 主编自己也记录
        self._record_decision(grade, topic, round_num)

        logger.info("创作流程完成: %s | 最终 grade=%s | 共 %d 轮", topic, grade, round_num + 1)

        return {
            "status": "completed",
            "draft": draft,
            "design": design_result,
            "inner_paths": inner_paths,
            "review": review,
            "comments": comments,
            "rounds": round_num + 1,
        }

    def _make_decision(self, draft, design_result, review, round_num, grade_history=None) -> dict:
        """主编做最终决策。"""
        if not review:
            return {"action": "revise", "feedback": "审核未返回结果，请重新生成", "core_issue": "审核失败"}

        verdict = review.get("verdict", "conditional")
        grade = review.get("grade", "B")
        issues = review.get("issues", [])

        # A级直接通过
        if grade == "A" and verdict == "pass":
            return {"action": "publish", "reason": "A级高质量内容"}

        # B级 + pass/conditional，且无严重 issues，可以通过
        if grade == "B" and verdict in ("pass", "conditional") and len(issues) <= 2:
            return {"action": "publish", "reason": f"B级内容可接受，issues={len(issues)}"}

        # 死循环检测：连续3轮等级相同（如B-B-B），强制通过，避免越改越差
        if grade_history and len(grade_history) >= 3:
            last_three = grade_history[-3:]
            if len(set(last_three)) == 1 and last_three[0] in ("A", "B"):
                return {"action": "publish", "reason": f"连续3轮等级均为{last_three[0]}，避免审核死循环，强制通过"}

        # 已达最大轮数
        if round_num >= 4:
            if grade in ("A", "B"):
                return {"action": "publish", "reason": "已达最大迭代轮数(5轮)，内容可接受"}
            else:
                return {"action": "abandon", "reason": "5轮迭代后仍未达到 publishable 标准"}

        # 需要重写
        feedback = self._build_feedback(review)
        core_issue = issues[0]["problem"] if issues else "整体质量不达标"

        return {
            "action": "revise",
            "feedback": feedback,
            "core_issue": core_issue,
        }

    def _build_feedback(self, review: dict) -> str:
        """把审核报告转化为写手可执行的修改指令。"""
        parts = []

        issues = review.get("issues", [])
        if issues:
            parts.append("【必须修改的问题】")
            for i in issues[:5]:  # 最多5个，避免 overwhelm
                loc = i.get("location", "")
                prob = i.get("problem", "")
                sugg = i.get("suggestion", "")
                parts.append(f"- {loc}: {prob}")
                if sugg:
                    parts.append(f"  → 建议: {sugg}")

        suggestions = review.get("suggestions", [])
        if suggestions:
            parts.append("\n【优化建议（有余力时处理）】")
            for s in suggestions[:3]:
                loc = s.get("location", "")
                idea = s.get("idea", "")
                parts.append(f"- {loc}: {idea}")

        comment = review.get("overall_comment", "")
        if comment:
            parts.append(f"\n【总体评价】{comment}")

        parts.append("\n【修改原则】只解决上面列出的核心问题，不要为了改而改。保持故事的真实感和呼吸感。")

        return "\n".join(parts)

    def _extract_style(self, content: str) -> str:
        """从内容中提取视觉风格标签。"""
        import re
        m = re.search(r'[\[【\*]*(?:视觉风格|风格|style)[\]】\*]*[:：]\s*\n?\s*`?([a-z_]+)`?', content, re.IGNORECASE)
        if m:
            style = m.group(1).strip().lower()
            valid = {"warm_grey", "twilight", "crimson", "mist", "cool", "warm", "blank"}
            if style in valid:
                return style
        return "warm_grey"

    def _record_decision(self, grade: str, topic: str, rounds_used: int):
        """记录主编决策历史。"""
        from core.agents.memory import AgentMemory
        mem = AgentMemory(self.name)
        context = {"topic": topic, "grade": grade, "rounds_used": rounds_used}
        if grade in ("A", "S"):
            mem.record_success(context)
        elif grade == "C":
            mem.record_failure(context)
        else:
            mem.data["total_runs"] = mem.data.get("total_runs", 0) + 1
            mem.save()

    def handle(self, message: Message):
        pass
