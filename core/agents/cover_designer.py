import os
import re

from core.agents.base import BaseAgent, MessageBus, Message, MessageType
from core.config import get_logger
from core.utils import load_prompt, extract_json_from_llm
from core.image_generator import generate_cover_template

logger = get_logger(__name__)

ALL_STYLES = ["warm_grey", "twilight", "crimson", "mist", "cool", "blank"]

# 风格权重 — 暖色调优先，冷色调降权
_STYLE_WEIGHTS = {
    "warm_grey": 4,
    "blank": 3,
    "crimson": 3,
    "mist": 2,
    "twilight": 1,
    "cool": 1,
}

# 冷调风格 — 如果 LLM 选了冷调且没有强理由，自动替换为暖调
_COLD_STYLES = {"twilight", "cool", "mist"}
_WARM_FALLBACK = {"warm_grey": 1, "blank": 1, "crimson": 1}

# 视觉锚点关键词 — 故事中包含这些元素时，封面设计更容易出效果
VISUAL_ANCHOR_KEYWORDS = [
    # 空间场景
    "窗边", "房间", "沙发", "床头", "桌子", "椅子", "门", "电梯",
    # 光线氛围
    "灯光", "阳光", "暖光", "台灯", "烛光", "黄昏", "清晨", "凌晨", "深夜",
    # 物品道具
    "咖啡", "杯子", "镜子", "手机", "屏幕", "外卖", "窗帘", "被子", "枕头",
    # 交通出行
    "地铁", "公交", "街道", "路灯",
    # 天气自然
    "雨", "雪", "风",
]


class CoverDesigner(BaseAgent):
    """封面设计师 Agent — 基于全文情绪设计封面方案，强制风格轮换。"""

    def __init__(self, bus: MessageBus):
        prompt = load_prompt("agent_cover_designer")
        super().__init__("cover_designer", prompt, bus)

    def design(self, note_content: str, round_num: int = 0, output_path: str = "", style_override: str = "", visual_direction: str = "", brief: dict = None) -> dict:
        """基于笔记全文设计封面方案并生成封面图。"""
        # 获取最近使用的风格，强制轮换
        recent_styles = self._get_recent_styles()

        direction_hint = ""
        if visual_direction:
            direction_hint = f"\n**内容策划建议的视觉方向**：{visual_direction}\n请参考这个方向，但根据实际内容做最终决定。"

        # 热点内容特殊要求
        trending_hint = ""
        if brief and brief.get("is_trending_content"):
            trending_keyword = brief.get("trending_keyword", "")
            trending_hint = f"""

**热点内容封面要求**：
这是一个热点内容，热点关键词是「{trending_keyword}」。
1. 封面背景必须包含热点元素（如世界杯内容要有足球/球场元素，考研内容要有书本/图书馆元素）
2. 封面标题也要体现热点相关性（可以包含热点关键词）
3. 但整体氛围仍要保持温暖调性（soft warm lighting, cozy atmosphere）
"""

        design_prompt = f"""请阅读以下小红书笔记的完整内容，为其设计封面方案。

**笔记内容**：
{note_content[:3000]}
{direction_hint}
{trending_hint}

请输出 JSON 格式的封面设计方案：
{{"title": "...", "subtitle": "...", "style": "...", "rationale": "..."}}

要求：
1. title 不超过12个字（封面大字必须短而醒目，和笔记标题是两回事），3秒内能读完。必须具体，禁止"情感笔记""看完沉默了"等万能词
2. **标题必须包含矛盾/反差**（数据证明：有矛盾的标题 CTR 是无矛盾的 2-3 倍）。例如："最让人心寒的不是吵架"（不吵架反而更心寒）、"越懂事的人越容易被忽视"（懂事≠被重视）。纯陈述句标题 CTR 极低。
3. **标题应包含至少2个高CTR元素**（数据验证过的）：
   - 具体数字（"一个动作""3种""5步"）— 带数字的标题CTR高15%
   - 问句形式（"是不是""为什么""怎么"）— 问号标题CTR高10%
   - 方法承诺（"动作""方法""步骤""清单"）— 实用承诺CTR高10%
   - "你"字（让读者直接代入）— 读者相关性CTR高8%
   - 反常识/悬念（"不是""原来""其实""没想到"）— 认知冲突CTR高12%
4. subtitle 是一句悬念钩子，不是解释标题，≤15字
5. style 必须是 warm_grey|twilight|crimson|mist|cool|blank 之一
6. rationale 说明设计思路，并指出标题中使用了哪些高CTR元素

**风格轮换要求**：最近使用过的风格是 {recent_styles}。请优先选择不同的风格，避免视觉同质化。
"""
        raw = self.think(design_prompt, temperature=0.7, max_tokens=800)

        # 解析 JSON
        design = self._parse_design(raw)

        # 系列风格绑定：如果指定了 style_override，优先使用
        if style_override and style_override in ALL_STYLES:
            design["style"] = style_override
            logger.info("使用系列绑定风格: %s", style_override)
        else:
            # 强制风格轮换：如果连续2次用了同一个风格，强制换一个
            design["style"] = self._enforce_rotation(design.get("style", "warm_grey"), recent_styles)

        # 冷调风格降权：如果选了冷调风格，有概率替换为暖调
        if design["style"] in _COLD_STYLES and not style_override:
            import random
            if random.random() < 0.6:  # 60% 概率替换为暖调
                warm_choices = list(_WARM_FALLBACK.keys())
                design["style"] = random.choices(warm_choices, weights=list(_WARM_FALLBACK.values()))[0]
                logger.info("冷调风格降权: 替换为暖调 %s", design["style"])

        # 改进 fallback 标题
        if design["title"] in ("情感笔记", ""):
            design["title"] = self._extract_title_from_content(note_content)

        # 生成文字模板封面（大字标题 + 渐变背景，小红书信息流中 CTR 更高）
        cover_path = None
        cover_paths = {}
        if output_path:
            base_dir = os.path.dirname(output_path)
            ai_path = os.path.join(base_dir, "cover_ai.png")
            # 封面已存在则跳过（避免重复生成）
            if os.path.exists(ai_path):
                logger.info("封面已存在，跳过生成: %s", ai_path)
                cover_path = ai_path
                cover_paths["ai"] = ai_path
            else:
                try:
                    ai_result = generate_cover_template(
                        title=design["title"],
                        subtitle=design["subtitle"],
                        style=design.get("style", "warm_grey"),
                        output_path=ai_path,
                    )
                    if ai_result:
                        cover_paths["ai"] = ai_result
                        cover_path = ai_result
                except Exception as e:
                    logger.warning("封面生成失败: %s", e)

        result = {
            "design": design,
            "cover_path": cover_path,
            "cover_paths": cover_paths,
            "round_num": round_num,
        }

        # 广播设计结果
        self.send(to_agent=None, msg_type=MessageType.DESIGN, content=result, round_num=round_num)
        logger.info("封面设计师完成设计: style=%s (最近用过: %s)", design.get("style"), recent_styles)
        return result

    def _get_recent_styles(self) -> list[str]:
        """从记忆中获取最近 3 次使用的风格。"""
        from core.agents.memory import AgentMemory
        mem = AgentMemory(self.name)
        # 从 success_patterns 和 mediocre_patterns 中提取最近的 style
        recent = []
        for pattern in reversed(mem.data.get("success_patterns", [])):
            if "style" in pattern:
                recent.append(pattern["style"])
        for pattern in reversed(mem.data.get("mediocre_patterns", [])):
            if "style" in pattern:
                recent.append(pattern["style"])
        return recent[:3]

    @staticmethod
    def _enforce_rotation(style: str, recent_styles: list[str]) -> str:
        """如果最近 2 次都用了同一个风格，强制换一个。"""
        if len(recent_styles) < 2:
            return style
        if recent_styles[0] == recent_styles[1] == style:
            # 连续3次同一风格，强制换
            alternatives = [s for s in ALL_STYLES if s != style]
            # 优先选择从未用过的
            for alt in alternatives:
                if alt not in recent_styles:
                    logger.info("风格轮换: %s -> %s (避免连续3次相同)", style, alt)
                    return alt
            # 都用过了，选一个最近没用的
            logger.info("风格轮换: %s -> %s (避免连续3次相同)", style, alternatives[0])
            return alternatives[0]
        return style

    @staticmethod
    def _extract_title_from_content(content: str) -> str:
        """从内容中提取一个有意义的标题作为 fallback。"""
        # 尝试找第一句对话或有冲击力的句子
        lines = [l.strip() for l in content.split("\n") if l.strip() and not l.strip().startswith("#")]
        for line in lines[:10]:
            # 跳过元数据行
            if any(kw in line for kw in ["【", "标题", "封面", "正文", "金句", "互动", "话题", "视觉"]):
                continue
            # 取一个有冲击力的短句
            clean = line.replace("**", "").replace("---", "").strip()
            if 4 <= len(clean) <= 15:
                return clean
        return "说不出口的话"

    def _parse_design(self, raw: str) -> dict:
        """从 LLM 输出中解析 JSON 设计方案。"""
        parsed = extract_json_from_llm(raw)
        if parsed:
            design = {
                "title": parsed.get("title", ""),
                "subtitle": parsed.get("subtitle", ""),
                "style": parsed.get("style", "warm_grey"),
                "rationale": parsed.get("rationale", ""),
            }
            return design

        # fallback: 使用正则提取 key-value 对
        design = {"title": "", "subtitle": "", "style": "warm_grey", "rationale": ""}

        for key in design:
            # 匹配 "key": "value" 或 key: value 格式
            m = re.search(rf'["\']?{key}["\']?\s*[:：]\s*["\']?(.+?)["\']?\s*[,}}\n]', raw, re.IGNORECASE)
            if m:
                design[key] = m.group(1).strip()

        # 兜底默认值
        if not design["title"]:
            design["title"] = "说不出口的话"
        if not design["subtitle"]:
            design["subtitle"] = "有些话，藏在心里太久了"

        return design

    def handle(self, message: Message) -> None:
        """处理消息总线消息。"""
        if message.msg_type == MessageType.DRAFT:
            draft_content = message.content.get("content", "")
            has_anchor = any(kw in draft_content for kw in VISUAL_ANCHOR_KEYWORDS)
            if not has_anchor:
                logger.info("封面设计师认为故事缺少视觉锚点，向写手发送请求")
                self.send(
                    to_agent="emotional_writer",
                    msg_type=MessageType.REQUEST,
                    content={"request": "封面需要一个具体的视觉锚点（如一个物品、一个场景、一种光线），请在故事中自然地加入1-2个画面细节，不要改变故事主线。"},
                    round_num=message.round_num,
                )

    def record_outcome(self, grade: str, topic: str, style: str):
        """记录设计结果。"""
        from core.agents.memory import AgentMemory
        mem = AgentMemory(self.name)
        context = {"topic": topic, "grade": grade, "style": style}
        if grade in ("A", "S"):
            mem.record_success(context)
            mem.update_style_preference(f"success_style_{style}", topic)
        elif grade == "C":
            mem.record_failure(context)
        else:
            mem.record_mediocre(context)
        mem.flush()
