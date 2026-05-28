from concurrent.futures import ThreadPoolExecutor, as_completed

from core.agents.base import BaseAgent, MessageBus, Message, MessageType
from core.config import get_logger
from core.utils import load_prompt, extract_visual_style

logger = get_logger(__name__)


class ChiefEditor(BaseAgent):
    """主编 Agent — 协调所有专家，控制迭代流程，做最终决策。"""

    def __init__(self, bus: MessageBus):
        prompt = load_prompt("agent_chief_editor")
        super().__init__("chief_editor", prompt, bus)

    def orchestrate(self, brief, writer, designer, artist, editor, community, out_dir: str) -> dict:
        """主流程编排。最多5轮迭代。"""
        round_num = 0
        draft = None
        review = None
        design_result = None
        inner_paths = []
        grade_history = []  # 记录每轮审核等级，防止死循环

        # 每次创作流程开始时，重置所有 Agent 的记忆缓存，确保从磁盘加载最新数据
        for agent in (writer, designer, artist, editor, community, self):
            agent.reset_memory_cache()

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
                style_override = brief.get("series_style", "")
                parallel_tasks.append(("design", lambda rn=round_num, cp=cover_path, so=style_override: designer.design(draft["content"], round_num=rn, output_path=cp, style_override=so)))
            else:
                parallel_tasks.append(("design", lambda: design_result))

            if round_num == 0 or (review and review.get("needs_relayout")):
                parallel_tasks.append(("layout", lambda rn=round_num: artist.layout(draft["content"], style=self._extract_style(draft["content"]), out_dir=out_dir, round_num=rn)))
            else:
                parallel_tasks.append(("layout", lambda: inner_paths))

            parallel_tasks.append(("review", lambda rn=round_num: editor.review(draft["content"], round_num=rn)))

            results = {}
            task_errors = {}
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(fn): name for name, fn in parallel_tasks}
                for future in as_completed(futures):
                    name = futures[future]
                    try:
                        results[name] = future.result()
                    except Exception as e:
                        logger.error("并行任务 %s 失败: %s", name, e)
                        task_errors[name] = e
                        results[name] = None

            if "design" in results:
                design_result = results["design"] or design_result
            if "layout" in results:
                inner_paths = results["layout"] or inner_paths

            # 审核任务失败需要特殊处理：区分"服务失败"和"审核不通过"
            if "review" in task_errors:
                logger.error("审核服务失败（非内容问题），将重试审核: %s", task_errors["review"])
                # 不更新 review，让它保持上一轮的值，在 _make_decision 中会因为 review is None 触发 revise
            elif "review" in results and results["review"] is not None:
                review = results["review"]

            # 记录本轮grade，用于检测死循环
            grade_history.append(review.get("grade", "B") if review else "B")

            # 主编决策
            decision = self._make_decision(draft, design_result, review, round_num, grade_history)

            if decision["action"] == "publish":
                logger.info("主编决策: 通过 (%s)", decision["reason"])
                break
            elif decision["action"] == "abandon":
                logger.warning("主编决策: 放弃 (%s)", decision["reason"])
                # 记录失败到各 agent 记忆
                grade = review.get("grade", "C") if review else "C"
                topic = brief["topic"]
                writer.record_outcome(grade, topic)
                editor.record_outcome(grade, topic)
                self._record_decision(grade, topic, round_num)
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
            # 审核服务失败，给写手一个通用反馈要求重新生成
            return {"action": "revise", "feedback": "审核服务暂时不可用，请保持内容质量重新提交", "core_issue": "审核服务异常"}

        verdict = review.get("verdict", "conditional")
        grade = review.get("grade", "B")
        issues = review.get("issues", [])

        # S级直接通过
        if grade == "S" and verdict == "pass":
            return {"action": "publish", "reason": "S级爆款内容"}

        # A级 + pass 直接通过；A级 + conditional 且 issues=0 也可通过
        if grade == "A":
            if verdict == "pass":
                return {"action": "publish", "reason": "A级高质量内容"}
            if verdict == "conditional" and len(issues) == 0:
                return {"action": "publish", "reason": "A级内容，仅有优化建议无硬伤"}

        # B级：必须 0 issues 才能通过，有 issues 就重写
        if grade == "B" and verdict in ("pass", "conditional") and len(issues) == 0:
            return {"action": "publish", "reason": "B级内容无硬伤，可接受"}

        # 死循环检测：连续3轮等级相同且为 B，强制给出不同方向再给一次机会
        if grade_history and len(grade_history) >= 3:
            last_three = grade_history[-3:]
            if len(set(last_three)) == 1 and last_three[0] == "B":
                # B-B-B 死循环：不再强制通过，而是要求换角度重写
                if round_num < 4:
                    return {
                        "action": "revise",
                        "feedback": "连续3轮均为B级，说明当前修改方向无效。请完全换一个叙事角度：如果之前是从'受害者的委屈'切入，这次试试'施害者的无意识'；如果之前是对话推动，这次试试动作细节推动。不要在原来的基础上微调。",
                        "core_issue": "B级死循环：需要彻底换角度",
                    }
                else:
                    # 最后一轮，B级死循环只能放弃
                    return {"action": "abandon", "reason": "5轮迭代均为B级，选题或角度存在根本问题"}

        # 已达最大轮数
        if round_num >= 4:
            if grade in ("S", "A"):
                return {"action": "publish", "reason": "已达最大迭代轮数，内容质量可接受"}
            elif grade == "B" and len(issues) == 0:
                return {"action": "publish", "reason": "已达最大迭代轮数，B级无硬伤，可接受"}
            else:
                return {"action": "abandon", "reason": f"5轮迭代后仍为{grade}级且存在{len(issues)}个问题，放弃发布"}

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

    @staticmethod
    def _extract_style(content: str) -> str:
        """从内容中提取视觉风格标签。"""
        return extract_visual_style(content)

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
            mem.record_mediocre(context)

    def handle(self, message: Message):
        pass
