#!/usr/bin/env python3
"""生成高质量选题池"""

import json
import re
import shutil
import sys
import time
from datetime import datetime, timezone

from core.config import init, _atomic_write_json, DATA_DIR, get_logger, load_topics_json
from core.writer import _call_api, _extract_content

logger = get_logger(__name__)

SYSTEM_PROMPT = """你是一个小红书"打工人 AI 提效"类内容策划专家，擅长创造高收藏率的选题。你的读者是 25-35 岁一二线城市上班族（运营/产品/行政/财务/设计/新媒体），核心痛点：活多、加班、想靠 AI 提效但被课贩子和浮夸测评坑怕了。

你的选题必须符合以下标准：
1. **每个选题必须是一个具体使用场景，不是一个话题**。不要写"AI 提升办公效率"，要写"周二晚上 9 点 leader 要的竞品分析，我 40 分钟交差了"。选题本身就要有岗位、有任务、有画面感。
2. **每个选题必须有争议锚点**——读完标题后读者会站队："用 AI 交周报算不算偷懒""这个工具值不值得花钱买"。没有争议就没有评论区。
3. 标题必须有"钩子"——让人忍不住想点进去抄作业或想在评论区问"XX 场景能用吗"。
4. **拒绝夸大和焦虑营销**——不写"轻松月入过万""10 分钟干完一天的活"。真实可信是这个赛道 2026 年的护身符。
5. 每个选题必须足够具体——拒绝空泛的"AI 改变职场"式话题。

你熟悉小红书的爆款规律：
- 问句式标题最容易引发评论
- 概念解读式最容易被收藏
- 观点冲击式最容易被分享
- 方法承诺式最容易获得点赞

你每天都在刷小红书/即刻/少数派/微博科技区，对 AI 工具动态和打工人情绪极度敏感。

**你必须避免单一内容带陷阱**：如果一批选题全是"提示词模板"，内容高度同质化，算法和用户都会疲劳。每批必须主动覆盖至少 4 种不同内容情绪：
- 效率爽感（前后对比强烈的成就感）
- 避坑愤怒（被割韭菜的"别再被骗了"）
- 反卷清醒（"AI 是让你准点下班的"价值观）
- 副业搞钱（真实具体的小额变现，不报虚数）
- 翻车自嘲（AI 出糗实录，最有信任感）

**每批至少 2 个选题必须是用户会主动搜索的问句**（如"AI 写周报哪个工具好用""怎么用 AI 做 PPT"），带搜索量的问句标题能带来长尾流量，是新号起量的关键。

**系列归属（每个选题必须归入一个固定系列，让读者有"追更"理由，提升关注转化）**：
- "打工人AI自救指南"（通用提效方法/场景工作流）
- "提示词急救包"（可复制模板/单一场景救命）
- "AI工具实测"（横评/避坑/踩雷实录）
- "1分钟工作流"（短平快的单个任务拆解）
- "老板不知道的AI用法"（反卷/职场生存/搞钱副业）"""

USER_PROMPT = """请生成10个高质量的"打工人 AI 提效"类小红书选题，要求：

【选题方向】覆盖以下5个支柱，每个支柱2个选题：
1. 提示词急救（可复制模板：周报/PPT/会议纪要/邮件/简历/竞品分析等具体任务）
2. AI办公实测（工具横评/避坑：Excel/PPT/文档/设计/剪辑/翻译）
3. 职场工作流（完整任务拆解：活动策划/数据分析/复盘报告/跨部门扯皮文书）
4. 反卷清醒（价值观+方法：准点下班/拒绝无效加班/AI 时代的工作观）
5. AI搞钱副业（真实小额变现：接单/模板/小产品/自媒体，不报虚数）

【标题公式分布】均匀分布：
- 问句式：让人忍不住想回答的问题
- 概念解读式：拆解一个 AI 使用概念（最容易被收藏）
- 观点冲击式：反常识但真实的观点
- 方法承诺式：具体可操作的方法

【互动目标分布】均匀分布：
- 评论驱动：话题有争议性（用AI算不算偷懒等），大家想表达观点
- 收藏驱动：有可照抄的提示词/清单，想留着以后用
- 分享驱动："转给那个加班的闺蜜/同事"
- 共鸣驱动："太真实了，我也是这么被坑的"
- 点赞驱动：简单认同，"说得对"

【质量要求 — 极其重要】
- **每个选题必须包含一个场景原型**（story_prototype）：用1-2句话描述一个具体的使用场景——什么岗位、什么任务、什么时间压力。不要写"探讨AI提效"，要写"运营小王周三要做季度复盘 PPT，30 页，只剩一个晚上"。
- **每个选题必须有争议锚点**（controversy_anchor）：这个选题会引发什么立场之争？——"有人觉得用AI写周报是偷懒，有人觉得手抄才是浪费"。
- 拒绝夸大收益、拒绝焦虑营销、拒绝空谈概念
- 要像真实打工人在说话，不是科技媒体/营销号
- 关键词要贴近小红书用户的搜索习惯（如"AI写周报""AI做PPT""提示词"）
- **内容光谱均衡（硬性）**：10个选题必须覆盖至少4种内容情绪（效率爽感/避坑愤怒/反卷清醒/副业搞钱/翻车自嘲），严禁全部是指令词模板类
- **搜索型选题配额（硬性）**：至少2个选题是用户会主动搜索的问句标题（带问号、针对具体搜索意图），用于获取长尾搜索流量

请严格按照以下JSON格式输出，不要有任何其他文字：

```json
{
  "topics": [
    {
      "id": 1,
      "topic": "选题标题",
      "title_formula": "问句式/概念解读式/观点冲击式/方法承诺式",
      "target_interaction": "评论驱动/收藏驱动/分享驱动/共鸣驱动/点赞驱动",
      "angle": "具体的切入角度",
      "story_prototype": "用1-2句话描述一个具体的使用场景原型：什么岗位、什么任务、什么时间压力",
      "controversy_anchor": "这个选题会引发什么立场之争？读者会怎么站队？",
      "keywords": ["关键词1", "关键词2", "关键词3", "关键词4"],
      "pillar": "提示词急救/AI办公实测/职场工作流/反卷清醒/AI搞钱副业",
      "series": "打工人AI自救指南/提示词急救包/AI工具实测/1分钟工作流/老板不知道的AI用法"
    }
  ]
}
```"""


def build_user_prompt(existing_hint: str = "", trending_keywords: list[str] | None = None) -> str:
    """构建用户 prompt，可选注入热点关键词。"""
    trending_section = ""
    if trending_keywords:
        kw_list = "、".join(trending_keywords)
        trending_section = f"""

【热点融合要求】以下关键词/话题是当前社会热点或平台高热度话题，请将它们自然融入选题中（至少60%的选题要与热点相关）：
热点关键词：{kw_list}

融合要求：
- 不要生硬蹭热点，要从情感角度切入热点话题
- 热点只是引子，核心还是情感共鸣
- 举例：如果热点是"裁员"，不要写"裁员赔偿攻略"，而要写"被裁那天，男朋友说了一句话我哭了"
"""

    return USER_PROMPT + trending_section + existing_hint


def generate_topics_batch(batch_index: int, existing_topics: list[str], trending_keywords: list[str] | None = None) -> list[dict]:
    """调用LLM生成一批选题（20个），传入已有标题避免重复。"""
    batch_label = f"第{batch_index + 1}批"
    logger.info("正在调用LLM生成选题（%s）...", batch_label)

    existing_hint = ""
    if existing_topics:
        # 只传最近60个标题做去重，避免prompt过长
        recent = existing_topics[-60:]
        existing_hint = f"\n\n【去重要求】以下选题已存在，请勿重复或高度相似：\n{chr(10).join('- ' + t for t in recent)}"

    user_prompt = build_user_prompt(existing_hint, trending_keywords)

    data = _call_api(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.92,
        max_tokens=8000,
    )

    raw = _extract_content(data)

    # 提取JSON部分
    json_match = re.search(r'```json\s*(.*?)\s*```', raw, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = raw.strip()

    try:
        parsed = json.loads(json_str)
        topics = parsed.get("topics", [])
    except json.JSONDecodeError as e:
        logger.error("JSON解析失败（%s）: %s", batch_label, e)
        logger.error("原始响应:\n%s", raw)
        raise

    # 验证和补充字段
    for i, topic in enumerate(topics):
        topic["status"] = "not_started"
        topic["generated_at"] = None
        topic["output_dir"] = None

        required_fields = ["topic", "title_formula", "target_interaction", "angle", "keywords", "pillar", "story_prototype", "controversy_anchor", "series"]
        for field in required_fields:
            if field not in topic:
                logger.warning("选题 %d 缺少字段 %s，使用默认值", i + 1, field)
                if field == "title_formula":
                    topic[field] = "问句式"
                elif field == "target_interaction":
                    topic[field] = "评论驱动"
                elif field == "keywords":
                    topic[field] = []
                elif field == "angle":
                    topic[field] = ""
                elif field == "pillar":
                    topic[field] = "亲密关系洞察"
                elif field == "story_prototype":
                    topic[field] = ""
                elif field == "controversy_anchor":
                    topic[field] = ""
                elif field == "series":
                    topic[field] = "清醒日记"

    logger.info("%s 生成完毕，共 %d 个选题", batch_label, len(topics))
    return topics


def _extract_keywords(title: str) -> set[str]:
    """从标题中提取关键词用于相似度比较。中文用 bigram，英文用完整词。"""
    words = set()
    # 提取英文词
    for w in re.findall(r'[a-zA-Z]+', title):
        if len(w) >= 2:
            words.add(w.lower())
    # 提取中文 bigram（连续2个字符）用于相似度比较
    chinese = re.findall(r'[一-鿿]+', title)
    for segment in chinese:
        if len(segment) >= 2:
            for i in range(len(segment) - 1):
                words.add(segment[i:i+2])
        else:
            words.add(segment)
    return words


def _is_similar(title1: str, title2: str, threshold: float = 0.6) -> bool:
    """判断两个标题是否语义相似（基于关键词重叠率）。"""
    kw1 = _extract_keywords(title1)
    kw2 = _extract_keywords(title2)
    if not kw1 or not kw2:
        return False
    overlap = len(kw1 & kw2)
    # 使用较小集合做分母，提高召回率
    min_size = min(len(kw1), len(kw2))
    return overlap / min_size >= threshold


def generate_topics(total: int = 100, trending_keywords: list[str] | None = None) -> list[dict]:
    """分批生成选题，每批10个，精确+相似度去重合并。"""
    batch_size = 10
    num_batches = (total + batch_size - 1) // batch_size
    all_topics: list[dict] = []
    all_titles: list[str] = []

    def _process_batch(batch: list[dict]) -> None:
        """处理一批选题，去重后加入结果列表。"""
        for t in batch:
            title = t.get("topic", "")
            # 精确去重
            if title in all_titles:
                logger.info("跳过精确重复选题: %s", title)
                continue
            # 相似度去重
            if any(_is_similar(title, existing) for existing in all_titles):
                logger.info("跳过相似选题: %s", title)
                continue
            all_topics.append(t)
            all_titles.append(title)

    for batch_idx in range(num_batches):
        remaining = total - len(all_topics)
        if remaining <= 0:
            break

        try:
            batch = generate_topics_batch(batch_idx, all_titles, trending_keywords)
            _process_batch(batch)
        except Exception as e:
            logger.error("第%d批生成失败: %s", batch_idx + 1, e)
            if batch_idx < num_batches - 1:
                logger.info("等待3秒后重试...")
                time.sleep(3)
                try:
                    batch = generate_topics_batch(batch_idx, all_titles, trending_keywords)
                    _process_batch(batch)
                except Exception as e2:
                    logger.error("重试失败: %s", e2)

        if batch_idx < num_batches - 1:
            time.sleep(2)  # 批次间间隔，避免API限流

    return all_topics[:total]


def save_topics(topics: list[dict], append: bool = False) -> None:
    """保存选题到topics.json。append=True时追加到已有选题。"""
    if append:
        try:
            existing = load_topics_json()
            existing_topics = existing.get("topics", [])
        except (FileNotFoundError, json.JSONDecodeError):
            existing_topics = []

        # 重新编号
        for i, t in enumerate(topics):
            t["id"] = len(existing_topics) + i + 1

        existing_topics.extend(topics)
        data = {
            "version": datetime.now(timezone.utc).strftime("%Y-%m"),
            "topics": existing_topics,
        }
    else:
        for i, t in enumerate(topics):
            t["id"] = i + 1
        data = {
            "version": datetime.now(timezone.utc).strftime("%Y-%m"),
            "topics": topics,
        }

    path = DATA_DIR / "topics.json"
    _atomic_write_json(path, data)
    logger.info("已保存 %d 个选题到 %s", len(data["topics"]), path)


def main() -> None:
    import argparse
    init()

    parser = argparse.ArgumentParser(description="小红书高质量选题生成器")
    parser.add_argument("--count", type=int, default=100, help="生成选题数量（默认100）")
    parser.add_argument("--append", action="store_true", default=True, help="追加到已有选题池（默认开启）")
    parser.add_argument("--replace", action="store_true", help="替换整个选题池")
    parser.add_argument("--trending", type=str, help="热点关键词，逗号分隔（如：裁员,独居,断亲）")
    parser.add_argument("--auto-trending", action="store_true", help="自动抓取当前热点关键词")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  小红书高质量选题生成器")
    print("=" * 60)

    # 备份旧选题
    old_path = DATA_DIR / "topics.json"
    if old_path.exists():
        backup_path = DATA_DIR / f"topics_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        shutil.copy2(old_path, backup_path)
        logger.info("已备份旧选题到 %s", backup_path)

    trending_keywords = None
    if args.auto_trending:
        from core.trend_detector import get_trending_keywords
        trending_keywords = get_trending_keywords()
        if trending_keywords:
            print(f"\n🔥 自动抓取到 {len(trending_keywords)} 个热点关键词:")
            for kw in trending_keywords:
                print(f"  - {kw}")
        else:
            print("\n⚠️ 未抓取到热点关键词，使用默认选题策略")
    elif args.trending:
        trending_keywords = [kw.strip() for kw in args.trending.split(",") if kw.strip()]
        logger.info("热点关键词: %s", trending_keywords)

    try:
        topics = generate_topics(total=args.count, trending_keywords=trending_keywords)
        append = not args.replace
        save_topics(topics, append=append)

        print("\n" + "=" * 60)
        print(f"  成功生成 {len(topics)} 个高质量选题" + ("（追加模式）" if append else "（替换模式）"))
        print("=" * 60)

        # 显示选题摘要
        pillars = {}
        formulas = {}
        interactions = {}
        for t in topics:
            p = t.get("pillar", "未知")
            f = t.get("title_formula", "未知")
            i = t.get("target_interaction", "未知")
            pillars[p] = pillars.get(p, 0) + 1
            formulas[f] = formulas.get(f, 0) + 1
            interactions[i] = interactions.get(i, 0) + 1

        print("\n【选题支柱分布】")
        for p, count in sorted(pillars.items(), key=lambda x: -x[1]):
            print(f"  {p}: {count}个")

        print("\n【标题公式分布】")
        for f, count in sorted(formulas.items(), key=lambda x: -x[1]):
            print(f"  {f}: {count}个")

        print("\n【互动目标分布】")
        for i, count in sorted(interactions.items(), key=lambda x: -x[1]):
            print(f"  {i}: {count}个")

        print("\n【新生成选题列表】")
        for t in topics:
            print(f"  [{t['id']:>3}] {t['topic']}")
            print(f"        {t['title_formula']} | {t['target_interaction']} | {t['pillar']}")
            if t.get("story_prototype"):
                print(f"        故事: {t['story_prototype'][:60]}...")
            if t.get("controversy_anchor"):
                print(f"        争议: {t['controversy_anchor'][:60]}...")

        # 显示总数
        try:
            all_data = load_topics_json()
            total = len(all_data.get("topics", []))
            generated = sum(1 for t in all_data["topics"] if t.get("status") == "generated")
            not_started = sum(1 for t in all_data["topics"] if t.get("status") in ("not_started", None, ""))
            print(f"\n选题池总计: {total} 个 | 已生成: {generated} | 待生成: {not_started}")
        except Exception as e:
            logger.warning("加载选题池统计失败: %s", e)

        print("\n" + "=" * 60)
        print("  使用 python pipeline.py --list 查看完整选题池")
        print("  使用 python pipeline.py --batch 批量生成笔记")
        print("=" * 60)

    except Exception as e:
        logger.error("生成选题失败: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
