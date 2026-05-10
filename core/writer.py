import json
import os
import time
from pathlib import Path

import requests

from core.config import get_logger, PROMPTS_DIR

logger = get_logger(__name__)

DEFAULT_MODEL = os.getenv("LLM_MODEL", "kimi-k2-6")
DEFAULT_BASE_URL = os.getenv("LLM_BASE_URL", os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1"))
DEFAULT_API_KEY = os.getenv("LLM_API_KEY", os.getenv("KIMI_API_KEY", ""))

FORMULA_INSTRUCTIONS = {
    "问句式": """
【标题公式特化指令 — 问句式】
你的标题必须是一个让人忍不住想回答的问题。核心技巧：
- 问题本身要击中具体场景（不是"爱情是什么"这种空泛问题）
- 标题里隐含一个"反常识"的钩子，让人想点进去看答案
- 正文不要直接回答标题问题，而是用故事让读者自己得出答案
- 结尾的互动钩子要引导用户在评论区"分享经历"而非"点赞认同"
""",
    "概念解读式": """
【标题公式特化指令 — 概念解读式】
你要拆解一个情感概念，让它变得具体可感。核心技巧：
- 不要下定义，用"3个日常场景"来呈现这个概念
- 每个场景都是一个微型故事，有动作、有对话、有反转
- 读者收藏的原因不是"学到了定义"，而是"这就是我啊"
- 封面要突出"X个表现""原来是这样"等收藏驱动力
""",
    "观点冲击式": """
【标题公式特化指令 — 观点冲击式】
你要提出一个反常识的观点，但不直接说服读者。核心技巧：
- 观点要足够尖锐，让读者第一反应是"不可能吧"
- 用故事层层剥开，让读者在最后恍然大悟"原来真的是这样"
- 不要站队，不要贴标签，只呈现现象
- 讨论度来自"我不同意"和"我也是"两种声音的碰撞
""",
    "方法承诺式": """
【标题公式特化指令 — 方法承诺式】
你要给出一个具体可操作的解决方案。核心技巧：
- 方法必须具体到"下一句话该说什么"
- 用"以前vs现在"的对比展示方法的效果
- 不要列123条，每条都要包裹在故事里
- 收藏驱动来自"这个我能直接用"
""",
}


def _load_prompt(name: str) -> str:
    """从 prompts/ 目录加载 prompt 文件。"""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt 文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _call_api(
    messages: list[dict],
    model: str | None = None,
    max_tokens: int = 2500,
    temperature: float = 0.8,
    retries: int = 3,
) -> dict:
    url = f"{DEFAULT_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEFAULT_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else 0
            if status == 429 or 500 <= status < 600:
                last_err = e
                wait = 2 ** attempt
                logger.warning("API 请求失败 (HTTP %s)，%d秒后重试 (%d/%d)", status, wait, attempt + 1, retries)
                time.sleep(wait)
                continue
            else:
                raise
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_err = e
            wait = 2 ** attempt
            logger.warning("API 请求失败 (%s)，%d秒后重试 (%d/%d)", type(e).__name__, wait, attempt + 1, retries)
            time.sleep(wait)

    raise last_err


def _extract_content(data: dict) -> str:
    """从 OpenAI 兼容响应中提取文本，并进行基础校验。"""
    if not isinstance(data, dict):
        raise ValueError(f"API 返回非 dict 类型: {type(data)}")
    choices = data.get("choices")
    if not choices or not isinstance(choices, list):
        raise ValueError("API 响应缺少 choices 字段")
    message = choices[0].get("message", {})
    content = message.get("content")
    if content is None:
        raise ValueError("API 响应缺少 content 字段")
    return content


def write_note(brief: dict, model: str | None = None) -> dict:
    system_prompt = _load_prompt("system_writer")
    user_template = _load_prompt("write_note")

    formula = brief.get("title_formula", "问句式")
    formula_instructions = FORMULA_INSTRUCTIONS.get(formula, "")

    rewrite_instructions = ""
    if brief.get("_rewrite_instructions"):
        rewrite_instructions = f"""
【重写指令】
上一稿审核未通过，请根据以下问题修改：
{brief['_rewrite_instructions']}
"""

    user_prompt = user_template.format(
        topic=brief["topic"],
        target_interaction=brief["target_interaction"],
        title_formula=formula,
        formula_instructions=formula_instructions,
        rewrite_instructions=rewrite_instructions,
    )

    data = _call_api(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=model,
        temperature=0.8,
        max_tokens=2500,
    )
    content = _extract_content(data)
    return {
        "brief": brief,
        "content": content,
        "model": model or DEFAULT_MODEL,
    }


def review_note(note_content: str, model: str | None = None) -> dict:
    review_template = _load_prompt("review")
    review_prompt = review_template.format(note_content=note_content)

    data = _call_api(
        messages=[{"role": "user", "content": review_prompt}],
        model=model,
        temperature=0.3,
        max_tokens=2500,
    )
    raw = _extract_content(data)

    try:
        parsed = json.loads(raw)
        grade = parsed.get("grade", "B")
        review_text = f"""## 审核等级：{grade}

### 通过项
"""
        checklist = parsed.get("pass_checklist", {})
        for k, v in checklist.items():
            mark = "✅" if v else "❌"
            review_text += f"- {mark} {k}\n"

        issues = parsed.get("issues", [])
        if issues:
            review_text += "\n### 问题\n"
            for i in issues:
                review_text += f"- ❌ {i}\n"

        suggestions = parsed.get("suggestions", [])
        if suggestions:
            review_text += "\n### 修改建议\n"
            for s in suggestions:
                review_text += f"- {s}\n"

        comment = parsed.get("comment", "")
        if comment:
            review_text += f"\n### 总体评价\n{comment}\n"

        return {
            "review": review_text,
            "grade": grade,
            "raw_json": parsed,
            "status": "completed",
        }
    except json.JSONDecodeError:
        logger.warning("审核结果未返回合法JSON，回退为文本解析")
        return {
            "review": raw,
            "grade": "B",
            "raw_json": None,
            "status": "completed",
        }


def generate_preset_comments(note_content: str, model: str | None = None) -> dict:
    """生成发布后用于引导互动的预设评论"""
    template = _load_prompt("preset_comments")
    preset_prompt = template.format(note_content=note_content)

    data = _call_api(
        messages=[{"role": "user", "content": preset_prompt}],
        model=model,
        temperature=0.9,
        max_tokens=1500,
    )
    raw = _extract_content(data)
    comments = [line.strip() for line in raw.split("\n") if line.strip() and not line.strip().startswith(("-", "*", "1.", "2.", "【", "##"))]
    return {
        "comments": comments,
        "raw": raw,
    }
