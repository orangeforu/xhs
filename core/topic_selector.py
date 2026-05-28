"""
智能选题引擎 — 多维度评分 + 多样性保障 + 历史数据反哺
"""

import random
from collections import Counter
from datetime import datetime, timezone

from core.config import get_logger, load_topics_json, load_performance_json

logger = get_logger(__name__)

# ── 评分权重配置 ──
WEIGHTS = {
    "performance": 0.35,   # 历史表现（哪种公式/支柱跑得好）
    "diversity": 0.30,     # 多样性（避免连续用同类）
    "freshness": 0.15,     # 新鲜度（未生成的优先）
    "randomness": 0.20,    # 随机性（避免完全确定性）
}

# 表现等级对应的分数
GRADE_SCORES = {"S": 1.0, "A": 0.8, "B": 0.5, "C": 0.1}


def _load_history() -> dict:
    """加载历史表现数据，返回结构化统计。"""
    perf = load_performance_json()
    notes = perf.get("notes", [])

    if not notes:
        return {
            "has_data": False,
            "formula_grades": {},
            "pillar_grades": {},
            "interaction_grades": {},
            "recent_formulas": [],
            "recent_pillars": [],
        }

    formula_grades: dict[str, list[str]] = {}
    pillar_grades: dict[str, list[str]] = {}
    interaction_grades: dict[str, list[str]] = {}
    recent_formulas = []
    recent_pillars = []

    # 按发布时间排序（最新的在前）
    sorted_notes = sorted(notes, key=lambda n: n.get("published_at", ""), reverse=True)

    for note in notes:
        grade = note.get("grade", "B")
        formula = note.get("title_formula", "")
        pillar = note.get("pillar", "")
        interaction = note.get("target_interaction", "")

        if formula:
            formula_grades.setdefault(formula, []).append(grade)
        if pillar:
            pillar_grades.setdefault(pillar, []).append(grade)
        if interaction:
            interaction_grades.setdefault(interaction, []).append(grade)

    # 最近 5 篇的公式和支柱（用于多样性惩罚）
    for note in sorted_notes[:5]:
        f = note.get("title_formula", "")
        p = note.get("pillar", "")
        if f:
            recent_formulas.append(f)
        if p:
            recent_pillars.append(p)

    return {
        "has_data": True,
        "formula_grades": formula_grades,
        "pillar_grades": pillar_grades,
        "interaction_grades": interaction_grades,
        "recent_formulas": recent_formulas,
        "recent_pillars": recent_pillars,
    }


def _avg_grade_score(grades: list[str]) -> float:
    """计算一组等级的平均分数。"""
    if not grades:
        return 0.5  # 无数据时给中性分
    scores = [GRADE_SCORES.get(g, 0.5) for g in grades]
    return sum(scores) / len(scores)


def _score_topic(topic: dict, history: dict, recent_generated: list[dict]) -> dict:
    """对单个选题进行多维度评分，返回各维度分数和总分。"""
    formula = topic.get("title_formula", "")
    pillar = topic.get("pillar", "")
    interaction = topic.get("target_interaction", "")
    status = topic.get("status", "not_started")

    scores = {}

    # ── 1. 表现分（基于历史数据） ──
    if history["has_data"]:
        formula_score = _avg_grade_score(history["formula_grades"].get(formula, []))
        pillar_score = _avg_grade_score(history["pillar_grades"].get(pillar, []))
        interaction_score = _avg_grade_score(history["interaction_grades"].get(interaction, []))
        scores["performance"] = (formula_score + pillar_score + interaction_score) / 3
    else:
        # 无历史数据时，给各种公式均等机会
        scores["performance"] = 0.5

    # ── 2. 多样性分（与近期生成的内容拉开差异） ──
    diversity_score = 1.0

    # 最近生成的选题中，同类公式/支柱越多，扣分越多
    recent_formula_count = sum(1 for t in recent_generated if t.get("title_formula") == formula)
    recent_pillar_count = sum(1 for t in recent_generated if t.get("pillar") == pillar)
    recent_interaction_count = sum(1 for t in recent_generated if t.get("target_interaction") == interaction)

    # 历史发布中也考虑
    if history["recent_formulas"]:
        formula_freq = history["recent_formulas"].count(formula) / len(history["recent_formulas"])
        diversity_score -= formula_freq * 0.3
    if history["recent_pillars"]:
        pillar_freq = history["recent_pillars"].count(pillar) / len(history["recent_pillars"])
        diversity_score -= pillar_freq * 0.3

    # 本次批量中同类的惩罚
    diversity_score -= recent_formula_count * 0.15
    diversity_score -= recent_pillar_count * 0.15
    diversity_score -= recent_interaction_count * 0.1

    scores["diversity"] = max(0.0, diversity_score)

    # ── 3. 新鲜度分 ──
    if status == "not_started":
        scores["freshness"] = 1.0
    elif status == "generated":
        scores["freshness"] = 0.3
    else:  # published / archived
        scores["freshness"] = 0.0

    # ── 4. 随机分 ──
    scores["randomness"] = random.random()

    # ── 加权总分 ──
    total = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)
    scores["total"] = total

    return scores


def smart_select(
    topic_pool: list[dict] | None = None,
    exclude_statuses: list[str] | None = None,
) -> tuple[dict | None, dict]:
    """
    智能选出最优选题。

    返回: (选题字典, 评分详情)
    """
    if topic_pool is None:
        data = load_topics_json()
        topic_pool = data.get("topics", [])

    if exclude_statuses is None:
        exclude_statuses = ["published", "archived"]

    # 过滤掉已发布/已归档的
    candidates = [t for t in topic_pool if t.get("status") not in exclude_statuses]

    if not candidates:
        logger.warning("没有可用的选题")
        return None, {}

    history = _load_history()

    # 对每个候选选题评分
    scored = []
    for topic in candidates:
        scores = _score_topic(topic, history, recent_generated=[])
        scored.append((topic, scores))

    # 按总分排序
    scored.sort(key=lambda x: x[1]["total"], reverse=True)

    # 从 top-3 中随机选一个（增加变化性，避免每次选同一个）
    top_n = min(3, len(scored))
    weights = [scored[i][1]["total"] for i in range(top_n)]
    total_weight = sum(weights)
    if total_weight > 0:
        probs = [w / total_weight for w in weights]
        chosen_idx = random.choices(range(top_n), weights=probs, k=1)[0]
    else:
        chosen_idx = 0

    chosen_topic, chosen_scores = scored[chosen_idx]

    logger.info("智能选题: %s (总分: %.2f)", chosen_topic["topic"], chosen_scores["total"])
    logger.info(
        "  各维度: 表现=%.2f 多样性=%.2f 新鲜度=%.2f 随机=%.2f",
        chosen_scores["performance"],
        chosen_scores["diversity"],
        chosen_scores["freshness"],
        chosen_scores["randomness"],
    )

    return chosen_topic, chosen_scores


def smart_batch(
    count: int = 3,
    topic_pool: list[dict] | None = None,
) -> list[dict]:
    """
    智能批量选题，保障多样性。

    每次选出最优后，将其加入"已选"列表影响后续选择，
    确保不会连续选同类型。
    """
    if topic_pool is None:
        data = load_topics_json()
        topic_pool = data.get("topics", [])

    candidates = [t for t in topic_pool if t.get("status") not in ("published", "archived")]

    if not candidates:
        logger.warning("没有可用的选题")
        return []

    history = _load_history()
    selected = []
    remaining = list(candidates)

    for _ in range(min(count, len(remaining))):
        best_topic = None
        best_score = -1.0

        for topic in remaining:
            scores = _score_topic(topic, history, recent_generated=selected)
            if scores["total"] > best_score:
                best_score = scores["total"]
                best_topic = topic

        if best_topic:
            selected.append(best_topic)
            remaining.remove(best_topic)
            logger.info("选中 [%d/%d]: %s (%.2f)", len(selected), count, best_topic["topic"], best_score)

    return selected


def recommend(count: int = 5) -> list[dict]:
    """
    推荐 top-N 选题，附带推荐理由。用于交互式菜单展示。
    """
    data = load_topics_json()
    topic_pool = data.get("topics", [])
    candidates = [t for t in topic_pool if t.get("status") not in ("published", "archived")]

    if not candidates:
        return []

    history = _load_history()

    scored = []
    for topic in candidates:
        scores = _score_topic(topic, history, recent_generated=[])
        scored.append({"topic": topic, "scores": scores})

    scored.sort(key=lambda x: x["scores"]["total"], reverse=True)

    results = []
    for item in scored[:count]:
        topic = item["topic"]
        scores = item["scores"]

        # 生成推荐理由
        reasons = []
        if history["has_data"]:
            formula = topic.get("title_formula", "")
            grades = history["formula_grades"].get(formula, [])
            if grades:
                avg = _avg_grade_score(grades)
                if avg >= 0.7:
                    reasons.append(f"「{formula}」历史表现优秀")

        if scores["diversity"] >= 0.8:
            reasons.append("与近期内容差异化高")
        if scores["freshness"] >= 0.9:
            reasons.append("新鲜选题，未使用过")

        if not reasons:
            reasons.append("综合评分较高")

        results.append({
            "topic": topic,
            "scores": scores,
            "reasons": reasons,
        })

    return results
