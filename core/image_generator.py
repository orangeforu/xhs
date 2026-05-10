import io
import os
import platform
import re
import time

import requests
from PIL import Image, ImageDraw, ImageFont

from core.config import get_logger, IMAGE_PROVIDER

logger = get_logger(__name__)

# 小红书黄金封面尺寸
COVER_WIDTH = 1242
COVER_HEIGHT = 1660

# 思源黑体（免费商用）
FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts")
FONT_REGULAR = os.path.join(FONT_DIR, "NotoSansSC-Regular.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "NotoSansSC-Bold.ttf")

# 品牌色调定义
PALETTE = {
    "warm": {
        "bg_top": (255, 252, 248),
        "bg_bottom": (255, 238, 225),
        "title": (60, 35, 20),
        "subtitle": (130, 95, 70),
        "accent": (230, 180, 140),
    },
    "cool": {
        "bg_top": (245, 248, 252),
        "bg_bottom": (220, 230, 245),
        "title": (25, 45, 70),
        "subtitle": (90, 110, 140),
        "accent": (160, 190, 220),
    },
    "blank": {
        "bg_top": (252, 252, 252),
        "bg_bottom": (248, 248, 248),
        "title": (30, 30, 30),
        "subtitle": (100, 100, 100),
        "accent": (200, 200, 200),
    },
}


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """加载字体，失败时按平台 fallback 系统黑体"""
    path = FONT_BOLD if bold else FONT_REGULAR
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        system = platform.system()
        fallbacks = []
        if system == "Darwin":
            fallbacks = ["/System/Library/Fonts/STHeiti Medium.ttc"]
        elif system == "Windows":
            fallbacks = ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"]
        else:
            fallbacks = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                         "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"]
        for fb in fallbacks:
            try:
                return ImageFont.truetype(fb, size)
            except OSError:
                continue
        return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int) -> list[str]:
    """按最大宽度自动换行，正确处理原始换行符"""
    lines = []
    for paragraph in text.split('\n'):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        current = ""
        for char in paragraph:
            test = current + char
            try:
                bbox = font.getbbox(test)
                w = bbox[2] - bbox[0]
            except (AttributeError, TypeError):
                w = 0
            if w > max_width and current:
                lines.append(current)
                current = char
            else:
                current = test
        if current:
            lines.append(current)

    # 合并被拆散的标点（避免句号、逗号等单独成行）
    merged = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if i + 1 < len(lines) and len(lines[i + 1]) == 1 and lines[i + 1] in '。，！？：；、）」】）':
            merged.append(line + lines[i + 1])
            i += 2
        else:
            merged.append(line)
            i += 1
    return merged


def _draw_gradient_bg(draw: ImageDraw.ImageDraw, width: int, height: int, c1: tuple[int, int, int], c2: tuple[int, int, int]) -> None:
    """绘制线性渐变背景（生成 1px 宽渐变条再拉伸，比逐行绘制快 100 倍）"""
    strip = Image.new("RGB", (1, height))
    pixels = []
    for y in range(height):
        ratio = y / max(height - 1, 1)
        r = int(c1[0] * (1 - ratio) + c2[0] * ratio)
        g = int(c1[1] * (1 - ratio) + c2[1] * ratio)
        b = int(c1[2] * (1 - ratio) + c2[2] * ratio)
        pixels.append((r, g, b))
    strip.putdata(pixels)
    gradient = strip.resize((width, height), Image.BILINEAR)
    draw._image.paste(gradient, (0, 0))


def _calc_font_size(text: str, max_width: int, target_size: int, min_size: int = 48) -> tuple[int, ImageFont.FreeTypeFont | ImageFont.ImageFont]:
    """根据文字长度动态计算字号，确保不溢出"""
    for size in range(target_size, min_size - 1, -4):
        font = _get_font(size, bold=True)
        try:
            bbox = font.getbbox(text)
            w = bbox[2] - bbox[0]
        except (AttributeError, TypeError):
            w = 0
        if w <= max_width:
            return size, font
    return min_size, _get_font(min_size, bold=True)


# ═══════════════════════════════════════════════════════════
# 方案2：模板合成（纯代码渲染）
# ═══════════════════════════════════════════════════════════

def generate_cover_template(title: str, subtitle: str, style: str = "warm", number: int | None = None, output_path: str = "assets/cover_template.png") -> str:
    """
    模板合成封面
    style可选: warm(暖调留白) / cool(冷调留白) / chat(聊天记录风) / blank(纯文字海报) / number(数字封面)
    """
    img = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT), color="white")
    draw = ImageDraw.Draw(img)

    p = PALETTE.get(style, PALETTE["warm"])

    # ── 背景 ──
    if style in ("warm", "cool", "blank"):
        _draw_gradient_bg(draw, COVER_WIDTH, COVER_HEIGHT, p["bg_top"], p["bg_bottom"])
    elif style == "chat":
        # 微信聊天背景
        draw.rectangle([(0, 0), (COVER_WIDTH, COVER_HEIGHT)], fill=(235, 235, 235))
        # 手机顶栏
        draw.rectangle([(0, 0), (COVER_WIDTH, 110)], fill=(245, 245, 245))
        draw.line([(0, 110), (COVER_WIDTH, 110)], fill=(220, 220, 220), width=1)
        # 时间戳
        time_font = _get_font(24)
        draw.text((COVER_WIDTH // 2 - 60, 55), "下午 3:42", font=time_font, fill=(150, 150, 150))
    elif style == "number":
        _draw_gradient_bg(draw, COVER_WIDTH, COVER_HEIGHT, p["bg_top"], p["bg_bottom"])

    # ── 安全边距 ──
    margin_x = 100
    max_text_w = COVER_WIDTH - margin_x * 2

    # ── 文字渲染 ──
    if style == "chat":
        # 聊天消息气泡（居中偏上，占画面约1/3）
        bubble_pad = 50
        title_font = _get_font(64, bold=True)
        title_lines = _wrap_text(title, title_font, 840)
        title_h = len(title_lines) * 88

        sub_font = _get_font(32)
        sub_lines = _wrap_text(subtitle, sub_font, 700)
        sub_h = len(sub_lines) * 48

        bubble_w = 920
        bubble_h = title_h + sub_h + bubble_pad * 3
        bx = (COVER_WIDTH - bubble_w) // 2
        by = COVER_HEIGHT // 3 - bubble_h // 2

        # 气泡底色
        draw.rounded_rectangle([(bx, by), (bx + bubble_w, by + bubble_h)], radius=30, fill=(149, 236, 105))
        # 小三角
        tri = [
            (bx + bubble_w - 40, by + bubble_h),
            (bx + bubble_w + 15, by + bubble_h + 25),
            (bx + bubble_w - 40, by + bubble_h + 25),
        ]
        draw.polygon(tri, fill=(149, 236, 105))

        # 标题在气泡内
        y_text = by + bubble_pad
        for i, line in enumerate(title_lines):
            bbox = title_font.getbbox(line)
            tw = bbox[2] - bbox[0]
            x = bx + (bubble_w - tw) // 2
            draw.text((x, y_text + i * 88), line, font=title_font, fill=(40, 40, 40))

        # 副标题在气泡内
        y_sub = y_text + title_h + bubble_pad
        for i, line in enumerate(sub_lines):
            bbox = sub_font.getbbox(line)
            tw = bbox[2] - bbox[0]
            x = bx + (bubble_w - tw) // 2
            draw.text((x, y_sub + i * 48), line, font=sub_font, fill=(80, 80, 80))

    elif style == "number":
        # 数字封面：超大数字 + 标题 + 副标题
        num = str(number) if number else "3"
        num_font = _get_font(420, bold=True)
        try:
            bbox = num_font.getbbox(num)
            nw = bbox[2] - bbox[0]
            nh = bbox[3] - bbox[1]
        except (AttributeError, TypeError):
            nw, nh = 300, 400
        nx = (COVER_WIDTH - nw) // 2
        ny = COVER_HEIGHT // 5
        # 淡色数字
        draw.text((nx, ny), num, font=num_font, fill=(p["accent"]))

        # 标题在数字下方
        title_font = _get_font(72, bold=True)
        title_lines = _wrap_text(title, title_font, max_text_w)
        y_title = ny + nh + 60
        for i, line in enumerate(title_lines):
            bbox = title_font.getbbox(line)
            tw = bbox[2] - bbox[0]
            x = (COVER_WIDTH - tw) // 2
            draw.text((x, y_title + i * 92), line, font=title_font, fill=p["title"])

        # 副标题
        sub_font = _get_font(36)
        sub_lines = _wrap_text(subtitle, sub_font, max_text_w - 100)
        y_sub = y_title + len(title_lines) * 92 + 50
        for i, line in enumerate(sub_lines):
            bbox = sub_font.getbbox(line)
            tw = bbox[2] - bbox[0]
            x = (COVER_WIDTH - tw) // 2
            draw.text((x, y_sub + i * 54), line, font=sub_font, fill=p["subtitle"])

    elif style == "blank":
        # 纯文字海报：大面积留白，标题超大
        title_size, title_font = _calc_font_size(title, max_text_w, 120)
        title_lines = _wrap_text(title, title_font, max_text_w)
        title_h = len(title_lines) * (title_size + 20)

        y_start = COVER_HEIGHT // 3 - title_h // 2
        for i, line in enumerate(title_lines):
            bbox = title_font.getbbox(line)
            tw = bbox[2] - bbox[0]
            x = (COVER_WIDTH - tw) // 2
            draw.text((x, y_start + i * (title_size + 20)), line, font=title_font, fill=p["title"])

        # 底部细线装饰
        line_y = y_start + title_h + 60
        draw.rectangle([(COVER_WIDTH // 2 - 40, line_y), (COVER_WIDTH // 2 + 40, line_y + 4)], fill=p["accent"])

        # 副标题
        sub_font = _get_font(36)
        sub_lines = _wrap_text(subtitle, sub_font, max_text_w - 100)
        y_sub = line_y + 50
        for i, line in enumerate(sub_lines):
            bbox = sub_font.getbbox(line)
            tw = bbox[2] - bbox[0]
            x = (COVER_WIDTH - tw) // 2
            draw.text((x, y_sub + i * 54), line, font=sub_font, fill=p["subtitle"])

    else:
        # warm / cool 常规风格
        title_size, title_font = _calc_font_size(title, max_text_w, 96)
        title_lines = _wrap_text(title, title_font, max_text_w)
        title_h = len(title_lines) * (title_size + 16)

        y_start = COVER_HEIGHT // 3 - title_h // 2
        for i, line in enumerate(title_lines):
            bbox = title_font.getbbox(line)
            tw = bbox[2] - bbox[0]
            x = (COVER_WIDTH - tw) // 2
            # 轻微阴影增加层次
            draw.text((x + 2, y_start + i * (title_size + 16) + 2), line, font=title_font, fill=(0, 0, 0, 20))
            draw.text((x, y_start + i * (title_size + 16)), line, font=title_font, fill=p["title"])

        # 装饰细线
        line_y = y_start + title_h + 50
        bar_w = 60
        draw.rectangle(
            [((COVER_WIDTH - bar_w) // 2, line_y), ((COVER_WIDTH + bar_w) // 2, line_y + 5)],
            fill=p["accent"],
        )

        # 副标题
        sub_font = _get_font(40)
        sub_lines = _wrap_text(subtitle, sub_font, max_text_w - 80)
        y_sub = line_y + 60
        for i, line in enumerate(sub_lines):
            bbox = sub_font.getbbox(line)
            tw = bbox[2] - bbox[0]
            x = (COVER_WIDTH - tw) // 2
            draw.text((x, y_sub + i * 58), line, font=sub_font, fill=p["subtitle"])

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    img.save(output_path, quality=95)
    logger.info("模板封面已保存: %s (style=%s)", output_path, style)
    return output_path


# ═══════════════════════════════════════════════════════════
# 方案1：AI绘画 + 文字叠加
# ═══════════════════════════════════════════════════════════

def _http_get_with_retry(url: str, retries: int = 3, timeout: int = 120, **kwargs) -> requests.Response:
    """带重试的 HTTP GET，处理 429/5xx 和网络异常。"""
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=timeout, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else 0
            if status == 429 or 500 <= status < 600:
                last_err = e
                wait = 2 ** attempt
                logger.warning("图片 API 请求失败 (HTTP %s)，%d秒后重试 (%d/%d)", status, wait, attempt + 1, retries)
                time.sleep(wait)
                continue
            raise
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_err = e
            wait = 2 ** attempt
            logger.warning("图片 API 请求失败 (%s)，%d秒后重试 (%d/%d)", type(e).__name__, wait, attempt + 1, retries)
            time.sleep(wait)
    raise last_err


def generate_cover_ai(prompt: str, title: str, subtitle: str, output_path: str = "assets/cover_ai.png") -> str:
    """
    方案1：AI绘画封面
    支持多后端：pollinations / dalle / fallback 模板合成
    """
    logger.info("正在生成AI绘画封面...")
    logger.info("背景prompt: %s...", prompt[:80])

    bg_img = None

    if IMAGE_PROVIDER == "pollinations":
        encoded_prompt = requests.utils.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1242&height=1660&nologo=true&seed=42"
        try:
            resp = _http_get_with_retry(image_url)
            bg_img = Image.open(io.BytesIO(resp.content))
        except (requests.exceptions.RequestException, OSError, Image.UnidentifiedImageError) as e:
            logger.warning("Pollinations API 失败: %s", e)

    elif IMAGE_PROVIDER == "dalle":
        api_key = os.getenv("IMAGE_API_KEY", os.getenv("OPENAI_API_KEY", ""))
        if not api_key:
            logger.warning("IMAGE_API_KEY / OPENAI_API_KEY 未配置，跳过 DALL-E")
        else:
            try:
                resp = requests.post(
                    "https://api.openai.com/v1/images/generations",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": "dall-e-3", "prompt": prompt, "size": "1024x1792", "n": 1},
                    timeout=180,
                )
                resp.raise_for_status()
                data = resp.json()
                img_url = data["data"][0]["url"]
                img_resp = _http_get_with_retry(img_url)
                bg_img = Image.open(io.BytesIO(img_resp.content))
            except Exception as e:
                logger.warning("DALL-E API 失败: %s", e)

    else:
        logger.warning("不支持的 IMAGE_PROVIDER: %s", IMAGE_PROVIDER)

    if bg_img is None:
        logger.info("使用模板合成作为fallback...")
        return generate_cover_template(title, subtitle, style="warm", output_path=output_path)

    # 调整尺寸
    bg_img = bg_img.resize((COVER_WIDTH, COVER_HEIGHT), Image.LANCZOS)
    bg_img = bg_img.convert("RGBA")

    # 底部1/3渐变遮罩（让文字清晰可读）
    overlay = Image.new("RGBA", (COVER_WIDTH, COVER_HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    mask_start = int(COVER_HEIGHT * 0.55)
    for y in range(mask_start, COVER_HEIGHT):
        alpha = int(((y - mask_start) / (COVER_HEIGHT - mask_start)) * 180)
        overlay_draw.line([(0, y), (COVER_WIDTH, y)], fill=(0, 0, 0, alpha))

    composite = Image.alpha_composite(bg_img, overlay)
    draw = ImageDraw.Draw(composite)

    # 文字区域：底部，左右留边距
    margin_x = 80
    max_text_w = COVER_WIDTH - margin_x * 2
    text_area_top = int(COVER_HEIGHT * 0.62)

    # 标题：白色加粗，动态字号
    title_size, title_font = _calc_font_size(title, max_text_w, 84)
    title_lines = _wrap_text(title, title_font, max_text_w)
    title_h = len(title_lines) * (title_size + 16)

    y_title = text_area_top
    for i, line in enumerate(title_lines):
        try:
            bbox = title_font.getbbox(line)
            tw = bbox[2] - bbox[0]
        except (AttributeError, TypeError):
            tw = 0
        x = (COVER_WIDTH - tw) // 2
        # 黑色阴影增强可读性
        draw.text((x + 3, y_title + i * (title_size + 16) + 3), line, font=title_font, fill=(0, 0, 0, 200))
        draw.text((x, y_title + i * (title_size + 16)), line, font=title_font, fill=(255, 255, 255, 255))

    # 副标题
    sub_font = _get_font(36)
    sub_lines = _wrap_text(subtitle, sub_font, max_text_w - 60)
    y_sub = y_title + title_h + 40
    for i, line in enumerate(sub_lines):
        try:
            bbox = sub_font.getbbox(line)
            tw = bbox[2] - bbox[0]
        except (AttributeError, TypeError):
            tw = 0
        x = (COVER_WIDTH - tw) // 2
        draw.text((x + 2, y_sub + i * 54 + 2), line, font=sub_font, fill=(0, 0, 0, 150))
        draw.text((x, y_sub + i * 54), line, font=sub_font, fill=(255, 255, 255, 230))

    final = composite.convert("RGB")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    final.save(output_path, quality=95)
    logger.info("AI绘画封面已保存: %s", output_path)
    return output_path


# ═══════════════════════════════════════════════════════════
# 内页文字图生成
# ═══════════════════════════════════════════════════════════

def generate_inner_page(text: str, page_num: int, style: str = "warm", output_path: str = "assets/inner_page.png") -> str | None:
    """把单页文字渲染成小红书风格内页图——大留白、居中、有设计感"""
    img = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT), color="white")
    draw = ImageDraw.Draw(img)
    p = PALETTE.get(style, PALETTE["warm"])

    # 背景渐变
    _draw_gradient_bg(draw, COVER_WIDTH, COVER_HEIGHT, p["bg_top"], p["bg_bottom"])

    text = text.strip()
    if not text:
        return None

    # 拆分行并识别加粗
    raw_lines = []
    for l in text.split('\n'):
        l = l.strip()
        if not l:
            continue
        is_bold = l.startswith('**') and l.endswith('**')
        if is_bold:
            l = l[2:-2].strip()
        raw_lines.append((l, is_bold))

    if not raw_lines:
        return None

    margin_x = 140
    max_text_w = COVER_WIDTH - margin_x * 2

    # 动态字号：行数越少字越大，小红书风格
    n = len(raw_lines)
    if n <= 2:
        font_size = 64
    elif n <= 4:
        font_size = 56
    elif n <= 6:
        font_size = 48
    else:
        font_size = 44

    font = _get_font(font_size, bold=False)
    bold_font = _get_font(font_size, bold=True)

    # 逐行 wrap
    lines = []
    for line, is_bold in raw_lines:
        wrapped = _wrap_text(line, font, max_text_w)
        for w in wrapped:
            lines.append((w, is_bold))

    # wrap 后如果超过 10 行，缩小字号
    while len(lines) > 10 and font_size > 32:
        font_size -= 4
        font = _get_font(font_size, bold=False)
        bold_font = _get_font(font_size, bold=True)
        lines = []
        for line, is_bold in raw_lines:
            wrapped = _wrap_text(line, font, max_text_w)
            for w in wrapped:
                lines.append((w, is_bold))

    # 布局：文字居中偏上，大量留白
    line_height = int(font_size * 1.8)
    total_h = len(lines) * line_height
    y_start = max(340, (COVER_HEIGHT - total_h) // 2 - 60)
    if y_start + total_h > COVER_HEIGHT - 120:
        y_start = COVER_HEIGHT - 120 - total_h

    # 渲染文字（居中）
    for i, (line, is_bold) in enumerate(lines):
        f = bold_font if is_bold else font
        try:
            bbox = f.getbbox(line)
            tw = bbox[2] - bbox[0]
        except (AttributeError, TypeError):
            tw = 0
        x = (COVER_WIDTH - tw) // 2
        draw.text((x, y_start + i * line_height), line, font=f, fill=p["title"])

    # 底部页码
    page_font = _get_font(18)
    page_text = f"{page_num}"
    try:
        bbox = page_font.getbbox(page_text)
        tw = bbox[2] - bbox[0]
    except Exception:
        tw = 0
    draw.text((COVER_WIDTH - margin_x - tw, COVER_HEIGHT - 80), page_text, font=page_font, fill=p["subtitle"])

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    img.save(output_path, quality=95)
    logger.info("内页图已保存: %s", output_path)
    return output_path


def generate_inner_pages(content: str, out_dir: str, style: str = "warm") -> list[str]:
    """解析笔记正文，生成所有内页图"""
    # 提取正文部分
    # 兼容 **【正文】** 等 Markdown 加粗标记
    body_match = re.search(r'\*?【正文】\*?\s*\n+(.*?)(?:\n\s*\*?【金句】\*?|\n\s*#{1,6}\s*\[?金句\]?|$)', content, re.DOTALL)
    if not body_match:
        # fallback 1: 尝试匹配没有标记的正文
        body_match = re.search(r'#{1,6}\s*\[?正文\]?.*?\n(.*?)(?:\n\s*#{1,6}\s*\[?金句\]?|$)', content, re.DOTALL)
    if not body_match:
        # fallback 2: 匹配封面页和第一个发布标记之间的内容
        body_match = re.search(
            r'\*?【(?:封面页|封面)】\*?[\s\S]*?(?:\n\s*---+\s*\n|\n\n)(.*?)(?:\n\s*\*?【(?:金句|互动钩子|话题标签|标题候选)】\*?|\n\s*#{1,6}\s*\[?(?:金句|互动钩子|话题标签|标题候选)\]?|$)',
            content,
            re.DOTALL,
        )

    if not body_match:
        logger.warning("未提取到正文，跳过内页生成")
        return []

    body = body_match.group(1).strip()
    pages = re.split(r'\n\s*---\s*\n', body)
    pages = [p.strip() for p in pages if p.strip()]

    if not pages:
        logger.warning("正文未分页，跳过内页生成")
        return []

    # 过滤发布元数据 + 按每页最多8行重新拆分
    final_pages = []
    for page in pages:
        lines = page.split('\n')
        clean_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # 跳过发布元数据标记
            if any(marker in stripped for marker in ['【金句】', '【互动钩子】', '【话题标签】', '【标题候选】', '【封面页】', '【正文】']):
                continue
            # 跳过纯话题标签行
            if stripped.startswith('#') and not stripped.startswith('##'):
                continue
            clean_lines.append(stripped)

        # 按每页最多8行拆分（小红书风格：少量文字+大量留白）
        for i in range(0, len(clean_lines), 8):
            final_pages.append('\n'.join(clean_lines[i:i + 8]))

    if not final_pages:
        logger.warning("正文过滤后为空，跳过内页生成")
        return []

    logger.info("📄 提取到 %d 页内页，开始生成...", len(final_pages))
    paths = []
    for i, page_text in enumerate(final_pages, 1):
        path = f"{out_dir}/inner_page_{i}.png"
        result = generate_inner_page(page_text, i, style=style, output_path=path)
        if result:
            paths.append(result)

    logger.info("✅ 内页生成完成，共 %d 张", len(paths))
    return paths


# ═══════════════════════════════════════════════════════════
# 批量生成入口
# ═══════════════════════════════════════════════════════════

def generate_all_covers(title: str, subtitle: str, prompt: str, number: int | None = None, output_dir: str = "assets") -> dict[str, str]:
    """一次性生成所有风格的封面，方便对比"""
    os.makedirs(output_dir, exist_ok=True)
    results = {}

    results["ai"] = generate_cover_ai(
        prompt, title, subtitle,
        output_path=f"{output_dir}/cover_ai.png",
    )

    for style in ["warm", "cool", "chat", "blank", "number"]:
        results[style] = generate_cover_template(
            title, subtitle, style=style, number=number,
            output_path=f"{output_dir}/cover_{style}.png",
        )

    return results


if __name__ == "__main__":
    title = "情绪稳定，是种什么体验？"
    subtitle = "她说：我终于不骗自己了"
    prompt = "A clean wooden table with a steaming cup of coffee, soft warm lighting, cozy atmosphere, minimalist aesthetic, gentle bokeh background, emotional warmth, feminine aesthetic, pastel warm tones"

    logger.info("=" * 60)
    logger.info("开始生成封面对比样例 (1242×1660)")
    logger.info("=" * 60)

    results = generate_all_covers(title, subtitle, prompt, number=3)

    logger.info("\n" + "=" * 60)
    logger.info("生成完成！文件列表：")
    for name, path in results.items():
        logger.info("  [%s] %s", name, path)
    logger.info("=" * 60)
