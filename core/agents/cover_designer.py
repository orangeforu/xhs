import json
import re

from core.agents.base import BaseAgent, MessageBus, Message, MessageType
from core.config import get_logger, PROMPTS_DIR
from core.image_generator import generate_cover_ai, generate_cover_template

logger = get_logger(__name__)


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt 文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class CoverDesigner(BaseAgent):
    """封面设计师 Agent — 基于全文情绪设计封面方案。"""

    def __init__(self, bus: MessageBus):
        prompt = _load_prompt("agent_cover_designer")
        super().__init__("cover_designer", prompt, bus)

    def design(self, note_content: str, round_num: int = 0, output_path: str = "") -> dict:
        """基于笔记全文设计封面方案并生成封面图。"""
        # 调用 LLM 做设计决策
        design_prompt = f"""请阅读以下小红书笔记的完整内容，为其设计封面方案。

**笔记内容**：
{note_content[:3000]}

请输出 JSON 格式的封面设计方案：
{{"title": "...", "subtitle": "...", "style": "...", "prompt": "...", "visual_anchor": "...", "rationale": "..."}}

要求：
1. title 不超过12个字，3秒内能读完
2. subtitle 是一句悬念，不是解释标题
3. style 必须是 warm_grey|twilight|crimson|mist|cool|blank 之一
4. prompt 必须包含温暖安全词（soft warm lighting, cozy atmosphere, gentle pastel tones, emotional warmth）
5. visual_anchor 是从故事中提炼的1个具体画面元素
6. rationale 说明设计思路
"""
        raw = self.think(design_prompt, temperature=0.7, max_tokens=1200)

        # 解析 JSON
        design = self._parse_design(raw)

        # 生成封面图
        cover_path = None
        if output_path:
            try:
                cover_path = generate_cover_ai(
                    prompt=design["prompt"],
                    title=design["title"],
                    subtitle=design["subtitle"],
                    style=design.get("style", "warm_grey"),
                    output_path=output_path,
                )
            except Exception as e:
                logger.warning("AI 封面生成失败，fallback 到模板: %s", e)
                try:
                    cover_path = generate_cover_template(
                        title=design["title"],
                        subtitle=design["subtitle"],
                        style=design.get("style", "warm_grey"),
                        output_path=output_path,
                    )
                except Exception as e2:
                    logger.error("封面模板也生成失败: %s", e2)

        result = {
            "design": design,
            "cover_path": cover_path,
            "round_num": round_num,
        }

        # 广播设计结果
        self.send(to_agent=None, msg_type=MessageType.DESIGN, content=result, round_num=round_num)
        logger.info("封面设计师完成设计: style=%s", design.get("style"))
        return result

    def _parse_design(self, raw: str) -> dict:
        """从 LLM 输出中解析 JSON 设计方案。"""
        # 尝试提取 JSON 块
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass

        # fallback: 手动解析
        design = {"title": "", "subtitle": "", "style": "warm_grey", "prompt": "", "visual_anchor": "", "rationale": ""}

        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            for key in design:
                if f'"{key}"' in line or f"'{key}'" in line:
                    val = line.split(":", 1)[-1].strip().strip(',').strip('"').strip("'")
                    design[key] = val

        # 如果解析失败，用内容关键词兜底
        if not design["title"]:
            design["title"] = "情感笔记"
        if not design["subtitle"]:
            design["subtitle"] = "看完沉默了"
        if not design["prompt"]:
            design["prompt"] = "A soft emotional aesthetic scene, warm lighting, minimalist, cozy atmosphere, gentle pastel tones, emotional warmth"

        return design

    def handle(self, message: Message):
        """处理消息总线消息。"""
        if message.msg_type == MessageType.DRAFT:
            # 收到写手的新 draft，自动分析是否需要补充视觉锚点
            draft_content = message.content.get("content", "")
            # 检查是否有足够的视觉锚点（具体场景、物品、光线）
            has_anchor = any(kw in draft_content for kw in ["窗边", "灯光", "阳光", "咖啡", "杯子", "房间", "沙发", "床头", "镜子", "手机", "屏幕", "外卖", "雨", "雪", "风", "窗帘", "被子", "枕头", "桌子", "椅子", "门", "电梯", "地铁", "公交", "街道", "路灯", "路灯", "黄昏", "清晨", "凌晨", "深夜", "暖光", "台灯", "烛光"])
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
            mem.data["total_runs"] = mem.data.get("total_runs", 0) + 1
            mem.save()
