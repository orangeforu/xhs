import os
import re

from core.agents.base import BaseAgent, MessageBus, Message, MessageType
from core.config import get_logger
from core.utils import load_prompt, extract_json_from_llm
from core.image_generator import generate_cover_ai

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

    def design(self, note_content: str, round_num: int = 0, output_path: str = "", style_override: str = "", visual_direction: str = "") -> dict:
        """基于笔记全文设计封面方案并生成封面图。"""
        # 获取最近使用的风格，强制轮换
        recent_styles = self._get_recent_styles()

        direction_hint = ""
        if visual_direction:
            direction_hint = f"\n**内容策划建议的视觉方向**：{visual_direction}\n请参考这个方向，但根据实际内容做最终决定。"

        design_prompt = f"""请阅读以下小红书笔记的完整内容，为其设计封面方案。

**笔记内容**：
{note_content[:3000]}
{direction_hint}

请输出 JSON 格式的封面设计方案：
{{"title": "...", "subtitle": "...", "style": "...", "prompt": "...", "visual_anchor": "...", "rationale": "..."}}

要求：
1. title 不超过12个字，3秒内能读完。必须具体，禁止"情感笔记""看完沉默了"等万能词
2. subtitle 是一句悬念，不是解释标题
3. style 必须是 warm_grey|twilight|crimson|mist|cool|blank 之一
4. prompt 必须包含温暖安全词（soft warm lighting, cozy atmosphere, gentle pastel tones, emotional warmth）
5. visual_anchor 是从故事中提炼的1个具体画面元素
6. rationale 说明设计思路

**风格轮换要求**：最近使用过的风格是 {recent_styles}。请优先选择不同的风格，避免视觉同质化。如果故事情绪确实适合最近用过的风格，可以选择，但需要在 rationale 中说明理由。
"""
        raw = self.think(design_prompt, temperature=0.7, max_tokens=1200)

        # 解析 JSON
        design = self._parse_design(raw)

        # 暖调 prompt 校验：确保 AI 绘画 prompt 包含暖调安全词
        design["prompt"] = self._ensure_warm_prompt(design.get("prompt", ""))

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

        # 生成封面图（只生成 AI 封面，符合平台策略）
        cover_path = None
        cover_paths = {}
        if output_path:
            base_dir = os.path.dirname(output_path)
            # AI 绘画封面
            ai_path = os.path.join(base_dir, "cover_ai.png")
            try:
                ai_result = generate_cover_ai(
                    prompt=design["prompt"],
                    title=design["title"],
                    subtitle=design["subtitle"],
                    style=design.get("style", "warm_grey"),
                    output_path=ai_path,
                )
                if ai_result:
                    cover_paths["ai"] = ai_result
                    cover_path = ai_result
            except Exception as e:
                logger.warning("AI 封面生成失败: %s", e)

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
            # 确保所有必需字段存在
            design = {
                "title": parsed.get("title", ""),
                "subtitle": parsed.get("subtitle", ""),
                "style": parsed.get("style", "warm_grey"),
                "prompt": parsed.get("prompt", ""),
                "visual_anchor": parsed.get("visual_anchor", ""),
                "rationale": parsed.get("rationale", ""),
            }
            return design

        # fallback: 使用正则提取 key-value 对
        design = {"title": "", "subtitle": "", "style": "warm_grey", "prompt": "", "visual_anchor": "", "rationale": ""}

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
        if not design["prompt"]:
            design["prompt"] = "A soft emotional aesthetic scene, warm lighting, minimalist, cozy atmosphere, gentle pastel tones, emotional warmth"

        return design

    @staticmethod
    def _ensure_warm_prompt(prompt: str) -> str:
        """确保 AI 绘画 prompt 包含暖调安全词，缺少时自动补充。"""
        if not prompt:
            return "A soft emotional aesthetic scene, warm lighting, cozy atmosphere, gentle pastel tones, emotional warmth"

        warm_keywords = ["warm", "cozy", "pastel", "golden", "soft light", "gentle"]
        has_warm = any(kw in prompt.lower() for kw in warm_keywords)

        if not has_warm:
            prompt = prompt.rstrip(".") + ", soft warm lighting, cozy atmosphere, gentle pastel tones, emotional warmth"
            logger.info("AI prompt 缺少暖调关键词，已自动补充")

        # 替换冷调关键词
        cold_replacements = {
            "dimly lit": "softly lit",
            "dark room": "dimly lit cozy room",
            "cold-toned": "warm-toned",
            "blue tones": "warm golden tones",
            "silhouette": "soft figure",
            "empty room": "cozy room",
            "gloomy": "melancholic warm",
            "eerie": "mysterious warm",
        }
        for cold, warm in cold_replacements.items():
            if cold in prompt.lower():
                prompt = re.sub(re.escape(cold), warm, prompt, flags=re.IGNORECASE)
                logger.info("替换冷调关键词: %s -> %s", cold, warm)

        return prompt

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
