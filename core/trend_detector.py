"""热点抓取模块 — 从公开数据源获取当前热点关键词，供选题生成使用。"""

import re
from core.config import get_logger

logger = get_logger(__name__)

# 情感类相关关键词（用于过滤热点）
EMOTIONAL_KEYWORDS = {
    # 关系类
    "恋爱", "分手", "出轨", "暧昧", "相亲", "结婚", "离婚", "前任", "暗恋", "表白",
    "渣男", "渣女", "冷暴力", "PUA", "备胎", "异地恋", "网恋", "彩礼", "婆媳",
    "男朋友", "女朋友", "老公", "老婆", "对象", "脱单", "单身", "情侣",
    # 自我类
    "独居", "焦虑", "内耗", "抑郁", "自卑", "自律", "裸辞", "考研", "考公",
    "社恐", "内卷", "躺平", "摆烂", "情绪", "崩溃", "治愈", "成长", "原生家庭",
    # 生活类
    "租房", "合租", "加班", "工资", "消费", "断舍离", "极简", "独处", "社交",
    "朋友", "闺蜜", "室友", "同事", "领导", "职场",
    # 情绪类
    "委屈", "心酸", "失望", "崩溃", "破防", "泪目", "扎心", "真实", "清醒",
    "释怀", "放下", "遗憾", "后悔", "勇敢", "底气",
}

# 排除的非情感关键词（仅限真正无法转化为情感故事的热点）
# 注意：体育赛事（世界杯/奥运会等）允许保留，可以转化为"赛事期间的情感冲突"故事
EXCLUDE_KEYWORDS = {
    # 纯金融/理财（无法转化为情感故事）
    "股票", "基金", "比特币", "理财", "A股", "美股", "港股", "期货",
    # 纯政治/军事（敏感且无法转化）
    "军事", "战争", "政治", "两会", "政策",
    # 纯技术/数码（除非涉及人际关系）
    "发布会", "新品", "芯片", "系统更新",
}

# "可转化为情感故事"的热点类型（即使包含非情感关键词，也允许保留）
TRENDS_WITH_EMOTIONAL_POTENTIAL = {
    "世界杯", "奥运会", "欧洲杯", "NBA", "欧冠",  # 体育赛事 → 赛事期间的情感冲突
    "考研", "考公", "高考",  # 考试季 → 压力/陪伴/牺牲
    "毕业季", "开学季",  # 季节性 → 分手/新开始/成长
    "情人节", "七夕", "520", "跨年",  # 节日 → 情感仪式感
    "春节", "中秋",  # 家庭节日 → 回家/团聚/矛盾
}


def _fetch_weibo_trending() -> list[dict]:
    """从微博热搜抓取热点关键词。

    Returns:
        热点列表，每项包含 keyword, source, heat 等字段
    """
    try:
        import requests
        # 微博热搜公开接口 - 使用更完整的请求头
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://weibo.com/",
        }
        resp = requests.get(
            "https://weibo.com/ajax/side/hotSearch",
            timeout=10,
            headers=headers,
        )
        if resp.status_code != 200:
            logger.warning("微博热搜请求失败: %d", resp.status_code)
            return []

        data = resp.json()
        trending = []
        for item in data.get("data", {}).get("realtime", [])[:30]:
            word = item.get("word", "")
            heat = item.get("num", 0)  # 热度值
            if word:
                trending.append({
                    "keyword": word,
                    "source": "weibo",
                    "heat": heat,
                })
        logger.info("微博热搜抓取成功，共 %d 条", len(trending))
        return trending
    except Exception as e:
        logger.warning("微博热搜抓取失败: %s", e)
        return []


def _fetch_douyin_trending() -> list[dict]:
    """从抖音热搜抓取热点关键词。

    Returns:
        热点列表，每项包含 keyword, source, heat 等字段
    """
    try:
        import requests
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        resp = requests.get(
            "https://www.douyin.com/aweme/v1/web/hot/search/list/",
            timeout=10,
            headers=headers,
        )
        if resp.status_code != 200:
            logger.warning("抖音热搜请求失败: %d", resp.status_code)
            return []

        data = resp.json()
        trending = []
        for item in data.get("data", {}).get("word_list", [])[:30]:
            word = item.get("word", "")
            hot_value = item.get("hot_value", 0)
            if word:
                trending.append({
                    "keyword": word,
                    "source": "douyin",
                    "heat": hot_value,
                })
        logger.info("抖音热搜抓取成功，共 %d 条", len(trending))
        return trending
    except Exception as e:
        logger.warning("抖音热搜抓取失败: %s", e)
        return []


def _fetch_tophub_trending() -> list[dict]:
    """从今日热榜（tophub.today）抓取热点关键词。

    Returns:
        热点列表，每项包含 keyword, source, heat 等字段
    """
    try:
        import requests
        from bs4 import BeautifulSoup
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }
        resp = requests.get(
            "https://tophub.today/n/KqndgxeLl9",  # 微博热搜聚合页
            timeout=10,
            headers=headers,
        )
        if resp.status_code != 200:
            logger.warning("今日热榜请求失败: %d", resp.status_code)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        trending = []

        # 查找热搜条目
        for item in soup.select("table tbody tr")[:30]:
            title_cell = item.select_one("td.al a")
            if title_cell:
                word = title_cell.get_text(strip=True)
                heat_text = item.select_one("td:last-child").get_text(strip=True) if item.select("td") else "0"
                # 提取数字
                import re
                heat_match = re.search(r"(\d+)", heat_text)
                heat = int(heat_match.group(1)) if heat_match else 0

                if word:
                    trending.append({
                        "keyword": word,
                        "source": "tophub_weibo",
                        "heat": heat,
                    })

        logger.info("今日热榜抓取成功，共 %d 条", len(trending))
        return trending
    except Exception as e:
        logger.warning("今日热榜抓取失败: %s", e)
        return []


def filter_emotional_keywords(trending: list[dict]) -> list[dict]:
    """从热点列表中筛选出与情感类内容相关的关键词。

    Args:
        trending: 热点列表，每项包含 keyword, source, heat 等字段

    Returns:
        筛选后的热点列表，按情感转化潜力排序
    """
    emotional = []

    for item in trending:
        keyword = item.get("keyword", "")
        if not keyword:
            continue

        # 排除真正无法转化的热点
        if any(ex in keyword for ex in EXCLUDE_KEYWORDS):
            continue

        # "可转化为情感故事"的热点类型，直接保留
        if any(trend in keyword for trend in TRENDS_WITH_EMOTIONAL_POTENTIAL):
            item["emotional_potential"] = "high"
            emotional.append(item)
            continue

        # 包含情感关键词
        if any(em in keyword for em in EMOTIONAL_KEYWORDS):
            item["emotional_potential"] = "high"
            emotional.append(item)
            continue

        # 看起来像情感话题（包含关系/情绪相关词）
        if any(w in keyword for w in ["怎么", "为什么", "是不是", "该不该", "能不能", "离婚", "分手", "结婚"]):
            item["emotional_potential"] = "medium"
            emotional.append(item)
            continue

        # 人物+冲突类热点（容易编故事）
        if any(w in keyword for w in ["出轨", "劈腿", "家暴", "冷暴力", "分手", "离婚", "结婚", "彩礼", "婆媳"]):
            item["emotional_potential"] = "high"
            emotional.append(item)

    # 按情感转化潜力排序（high > medium > low）
    priority = {"high": 0, "medium": 1, "low": 2}
    emotional.sort(key=lambda x: priority.get(x.get("emotional_potential", "low"), 3))

    return emotional[:10]  # 最多返回 10 个


def get_trending_keywords() -> list[dict]:
    """获取当前热点关键词（主入口）。返回去重后的情感相关热点。

    Returns:
        热点列表，每项包含 keyword, source, heat, emotional_potential 等字段
    """
    all_trending = []

    # 并行抓取多个数据源（微博、抖音、今日热榜）
    sources = [
        ("微博", _fetch_weibo_trending),
        ("抖音", _fetch_douyin_trending),
        ("今日热榜", _fetch_tophub_trending),
    ]

    for name, fetcher in sources:
        try:
            trending = fetcher()
            all_trending.extend(trending)
        except Exception as e:
            logger.warning("%s 热点抓取失败: %s", name, e)

    if not all_trending:
        logger.info("所有热点源均未获取到数据")
        return []

    # 去重（按 keyword）
    seen = set()
    unique = []
    for item in all_trending:
        kw = item.get("keyword", "")
        if kw and kw not in seen:
            seen.add(kw)
            unique.append(item)

    # 过滤出情感相关
    emotional = filter_emotional_keywords(unique)
    logger.info("热点抓取完成: 总共 %d 条 → 情感相关 %d 条", len(unique), len(emotional))
    return emotional


def get_trending_for_topics() -> str:
    """获取热点关键词，格式化为 generate_topics 可用的字符串（向后兼容）。"""
    keywords = get_trending_keywords()
    if not keywords:
        return ""
    # 提取关键词列表，用逗号分隔
    keyword_list = [item["keyword"] for item in keywords]
    return ",".join(keyword_list)


def get_trending_briefs() -> list[dict]:
    """获取热点 brief，供 TopicStrategist 使用。

    Returns:
        热点 brief 列表，每项包含：
        - keyword: 热点关键词
        - source: 来源（weibo/baidu）
        - heat: 热度值
        - emotional_potential: 情感转化潜力（high/medium/low）
        - story_angle_hint: 故事角度提示（可选）
    """
    trending = get_trending_keywords()
    briefs = []

    for item in trending:
        brief = {
            "keyword": item["keyword"],
            "source": item["source"],
            "heat": item.get("heat", 0),
            "emotional_potential": item.get("emotional_potential", "medium"),
            "story_angle_hint": _generate_story_hint(item["keyword"]),
        }
        briefs.append(brief)

    return briefs


def _generate_story_hint(keyword: str) -> str:
    """根据热点关键词，生成故事角度提示。"""
    # 体育赛事 → 赛事期间的情感冲突
    if any(w in keyword for w in ["世界杯", "奥运会", "欧洲杯", "NBA"]):
        return f"「{keyword}」期间，因为看球/追赛引发的伴侣矛盾。比如一方疯狂追赛另一方感到被冷落，或者因为支持的队伍不同引发争论。可以写'他看世界杯的时候，我在想我们的感情是不是也到了换人时间'。"

    # 考试季 → 压力/陪伴/牺牲
    if any(w in keyword for w in ["考研", "考公", "高考"]):
        return f"「{keyword}」季的情感故事。比如备考期间的陪伴与牺牲，考完后的分手季，或者'我陪你熬过了考研，却没能陪你走到最后'。"

    # 节日 → 情感仪式感
    if any(w in keyword for w in ["情人节", "七夕", "520", "跨年"]):
        return f"「{keyword}」的情感仪式感。比如期待与失望的反差，'他说忙没空陪我过节，却在朋友圈给别人点了赞'，或者'最好的礼物不是花，是他记得我随口说过的一句话'。"

    # 家庭节日 → 回家/团聚/矛盾
    if any(w in keyword for w in ["春节", "中秋"]):
        return f"「{keyword}」的家庭情感。比如回家过年的压力，'过年回家，我妈又问我有对象了吗'，或者'团圆饭桌上，我们都在假装幸福'。"

    # 情感关系类
    if any(w in keyword for w in ["离婚", "分手", "出轨", "结婚"]):
        return f"「{keyword}」相关的情感冲突。可以是真实事件的改编，或者'看到这条新闻，我想起了那年我选择的放手'。"

    # 默认提示
    return f"围绕「{keyword}」这个热点，找到一个能引发情感共鸣的角度。可以是热点事件中的人物关系，也可以是热点背景下普通人的情感故事。"
