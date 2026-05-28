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

# 排除的非情感关键词
EXCLUDE_KEYWORDS = {
    "足球", "篮球", "NBA", "世界杯", "欧冠", "英超",
    "游戏", "手游", "LOL", "王者", "原神", "吃鸡",
    "股票", "基金", "比特币", "理财",
    "军事", "战争", "政治",
    "娱乐", "综艺", "选秀", "偶像",
    "美食", "旅游", "穿搭", "美妆", "护肤",
}


def _fetch_weibo_trending() -> list[str]:
    """从微博热搜抓取热点关键词。"""
    try:
        import requests
        # 微博热搜公开接口
        resp = requests.get(
            "https://weibo.com/ajax/side/hotSearch",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if resp.status_code != 200:
            logger.warning("微博热搜请求失败: %d", resp.status_code)
            return []

        data = resp.json()
        trending = []
        for item in data.get("data", {}).get("realtime", [])[:30]:
            word = item.get("word", "")
            if word:
                trending.append(word)
        logger.info("微博热搜抓取成功，共 %d 条", len(trending))
        return trending
    except Exception as e:
        logger.warning("微博热搜抓取失败: %s", e)
        return []


def _fetch_baidu_trending() -> list[str]:
    """从百度热搜抓取热点关键词。"""
    try:
        import requests
        resp = requests.get(
            "https://top.baidu.com/board?tab=realtime",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if resp.status_code != 200:
            logger.warning("百度热搜请求失败: %d", resp.status_code)
            return []

        # 从 HTML 中提取热搜词
        keywords = re.findall(r'class="title_.*?>(.*?)<', resp.text)
        keywords = [k.strip() for k in keywords if k.strip()][:20]
        logger.info("百度热搜抓取成功，共 %d 条", len(keywords))
        return keywords
    except Exception as e:
        logger.warning("百度热搜抓取失败: %s", e)
        return []


def filter_emotional_keywords(trending: list[str]) -> list[str]:
    """从热点列表中筛选出与情感类内容相关的关键词。"""
    emotional = []
    for keyword in trending:
        # 排除非情感内容
        if any(ex in keyword for ex in EXCLUDE_KEYWORDS):
            continue
        # 包含情感关键词
        if any(em in keyword for em in EMOTIONAL_KEYWORDS):
            emotional.append(keyword)
            continue
        # 看起来像情感话题（包含关系/情绪相关词）
        if any(w in keyword for w in ["怎么", "为什么", "是不是", "该不该", "能不能"]):
            emotional.append(keyword)

    return emotional[:10]  # 最多返回 10 个


def get_trending_keywords() -> list[str]:
    """获取当前热点关键词（主入口）。返回去重后的情感相关热点。"""
    all_trending = []

    # 并行抓取多个数据源
    sources = [
        ("微博", _fetch_weibo_trending),
        ("百度", _fetch_baidu_trending),
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

    # 去重
    seen = set()
    unique = []
    for kw in all_trending:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)

    # 过滤出情感相关
    emotional = filter_emotional_keywords(unique)
    logger.info("热点抓取完成: 总共 %d 条 → 情感相关 %d 条", len(unique), len(emotional))
    return emotional


def get_trending_for_topics() -> str:
    """获取热点关键词，格式化为 generate_topics 可用的字符串。"""
    keywords = get_trending_keywords()
    if not keywords:
        return ""
    return ",".join(keywords)
