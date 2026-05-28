"""发布辅助纯函数 — 从 app.py 提取，便于独立测试。"""

import re


def calculate_grade(likes: int) -> str:
    """根据点赞数计算等级。"""
    if likes > 1500:
        return "S"
    elif likes >= 800:
        return "A"
    elif likes >= 200:
        return "B"
    return "C"


def calc_interaction_rate(note: dict) -> float:
    """计算互动率 = (点赞+收藏+评论+分享) / 曝光量。"""
    exposure = note.get("exposure", 0)
    if not exposure:
        return 0.0
    total = note.get("likes", 0) + note.get("collects", 0) + note.get("comments", 0) + note.get("shares", 0)
    return total / exposure


def _calc_group_stats(notes: list[dict], group_key: str, default_label: str = "未知") -> dict:
    """按指定字段分组统计平均数据（通用实现）。"""
    stats: dict[str, dict] = {}
    for n in notes:
        group = n.get(group_key, default_label)
        if group not in stats:
            stats[group] = {"count": 0, "total_likes": 0, "total_collects": 0, "total_comments": 0, "total_shares": 0, "total_engagement": 0.0}
        s = stats[group]
        s["count"] += 1
        s["total_likes"] += n.get("likes", 0)
        s["total_collects"] += n.get("collects", 0)
        s["total_comments"] += n.get("comments", 0)
        s["total_shares"] += n.get("shares", 0)
        rate = calc_interaction_rate(n)
        s["total_engagement"] += rate
    return stats


def calc_formula_stats(notes: list[dict]) -> dict:
    """按标题公式分组统计平均数据。"""
    return _calc_group_stats(notes, "title_formula")


def calc_pillar_stats(notes: list[dict]) -> dict:
    """按内容支柱分组统计平均数据。"""
    return _calc_group_stats(notes, "pillar")


def check_compliance(content: str, title: str, tags: list[str], image_count: int) -> dict:
    """发布前合规检查。"""
    issues = []
    warnings = []

    # 标题检查
    if len(title) > 20:
        issues.append(f"标题超长（{len(title)}字，建议≤20字）")
    if not re.search(r'[\U0001F300-\U0001F9FF\U00002600-\U000027B0]', title):
        warnings.append("标题缺少 emoji，建议加 1-2 个")

    # 标签检查
    if len(tags) < 3:
        issues.append(f"标签不足（{len(tags)}个，要求 3-5 个）")
    elif len(tags) > 5:
        issues.append(f"标签过多（{len(tags)}个，要求 3-5 个）")
    if not any("不懂就问" in t for t in tags):
        warnings.append("缺少必带标签 #不懂就问有问必答")

    # 图片检查
    if image_count < 3:
        issues.append(f"图片不足（{image_count}张，建议 3-6 张）")
    elif image_count > 9:
        warnings.append(f"图片较多（{image_count}张），小红书最多 9 张")

    # 敏感词检查
    sensitive_words = ["私信", "微信", "淘宝", "京东", "拼多多", "抖音", "快手", "B站",
                       "公众号", "小程序", "加我", "联系我", "购买链接", "下单"]
    found = [w for w in sensitive_words if w in content]
    if found:
        issues.append(f"检测到引流/敏感词：{', '.join(found)}")

    # 正文长度检查
    body_len = len(re.sub(r'\s+', '', content))
    if body_len < 300:
        warnings.append(f"正文偏短（{body_len}字，建议 500-800 字）")
    elif body_len > 1200:
        warnings.append(f"正文偏长（{body_len}字，建议 500-800 字）")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


def recalculate_summary(performance: dict) -> None:
    """根据 notes 数据重算 summary 统计。"""
    notes = performance.get("notes", [])
    summary = performance.setdefault("summary", {})
    summary["total_published"] = len(notes)
    summary["total_likes"] = sum(n.get("likes", 0) for n in notes)
    summary["total_collects"] = sum(n.get("collects", 0) for n in notes)
    summary["total_comments"] = sum(n.get("comments", 0) for n in notes)
    summary["total_shares"] = sum(n.get("shares", 0) for n in notes)
    summary["total_exposure"] = sum(n.get("exposure", 0) for n in notes)
    summary["s_grade_count"] = sum(1 for n in notes if n.get("grade") == "S")
    summary["a_grade_count"] = sum(1 for n in notes if n.get("grade") == "A")
    summary["b_grade_count"] = sum(1 for n in notes if n.get("grade") == "B")
    summary["c_grade_count"] = sum(1 for n in notes if n.get("grade") == "C")


def extract_title_candidates(content: str) -> list[str]:
    """从 note.md 提取标题候选列表。"""
    titles = []
    m = re.search(r"【标题候选】\s*(.+?)\s*(?=【|$)", content, re.DOTALL)
    if m:
        block = m.group(1).strip()
        for line in block.split("\n"):
            line = line.strip()
            if not line:
                continue
            cleaned = re.sub(r"^\d+[\.、]\s*", "", line)
            cleaned = re.sub(r"^[\s*_`]+|[\s*_`]+$", "", cleaned)
            if cleaned:
                titles.append(cleaned)
    return titles


def extract_body_for_publish(content: str) -> str:
    """提取并格式化正文，适合小红书发布。"""
    m = re.search(r"【正文】\s*(.+?)(?=## 审核结果|## 预设评论|## 封面|$)", content, re.DOTALL)
    if not m:
        return ""
    body = m.group(1).strip()
    body = re.sub(r"\*\*(.+?)\*\*", r"\1", body)
    body = re.sub(r"\n\s*---\s*\n", "\n\n", body)
    body = re.sub(r"^#+\s*", "", body, flags=re.MULTILINE)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def score_title(title: str, performance: dict) -> dict:
    """给标题打分，返回分数和分析。"""
    notes = performance.get("notes", [])
    score = 50  # 基础分
    reasons = []

    # 1. 长度评分（12-18字最佳）
    length = len(title)
    if 12 <= length <= 18:
        score += 15
        reasons.append("长度适中")
    elif length < 12:
        score += 5
        reasons.append("偏短，信息量可能不足")
    elif length > 20:
        score -= 10
        reasons.append("超长，可能被截断")

    # 2. emoji 检测
    emoji_count = len(re.findall(r'[\U0001F300-\U0001F9FF\U00002600-\U000027B0]', title))
    if 1 <= emoji_count <= 2:
        score += 10
        reasons.append("emoji 数量合适")
    elif emoji_count == 0:
        score -= 5
        reasons.append("缺少 emoji")

    # 3. 句式特征
    if "？" in title or "?" in title:
        score += 8
        reasons.append("问句式，易引发好奇")
    if any(kw in title for kw in ["才", "终于", "突然", "竟然", "居然"]):
        score += 5
        reasons.append("含转折词，有悬念")
    if any(kw in title for kw in ["最", "第一", "唯一", "绝了"]):
        score += 5
        reasons.append("含极端词，有冲击力")

    # 4. 基于历史公式表现调整
    if notes:
        if "？" in title or "?" in title:
            formula = "问句式"
        elif any(kw in title for kw in ["指南", "方法", "步骤", "个"]):
            formula = "方法承诺式"
        elif any(kw in title for kw in ["才", "终于", "其实", "原来"]):
            formula = "概念解读式"
        else:
            formula = "观点冲击式"

        formula_notes = [n for n in notes if n.get("title_formula") == formula]
        if formula_notes:
            avg_likes = sum(n.get("likes", 0) for n in formula_notes) / len(formula_notes)
            if avg_likes > 500:
                score += 10
                reasons.append(f"{formula}历史表现优秀（均赞{avg_likes:.0f}）")
            elif avg_likes < 200:
                score -= 5
                reasons.append(f"{formula}历史表现一般（均赞{avg_likes:.0f}）")

    # 5. 负面特征检测
    negative_patterns = ["看完沉默", "情感笔记", "建议收藏", "必看", "震惊"]
    for pattern in negative_patterns:
        if pattern in title:
            score -= 15
            reasons.append(f"含低质词「{pattern}」")

    # 6. 公式多样性惩罚：如果同一公式近期使用过多，降分
    if notes:
        recent = notes[-5:]  # 最近 5 篇
        if formula:
            same_count = sum(1 for n in recent if n.get("title_formula") == formula)
            if same_count >= 3:
                score -= 10
                reasons.append(f"{formula}近期已用{same_count}次，缺乏多样性")
            elif same_count >= 2:
                score -= 5
                reasons.append(f"{formula}近期已用{same_count}次")

    score = max(0, min(100, score))

    return {
        "score": score,
        "reasons": reasons,
        "level": "S" if score >= 85 else "A" if score >= 70 else "B" if score >= 50 else "C",
    }
