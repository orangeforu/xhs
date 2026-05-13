import concurrent.futures
import io
import os
import platform
import re
import time

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

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
# 每个主题包含：bg_top / bg_bottom（渐变）、title（标题/强调正文）、subtitle（辅助文字）、
# accent（装饰色）、body（长正文，比 title 更柔和）、highlight（金句/高亮文字色）
PALETTE = {
    "warm": {
        "bg_top": (255, 252, 248), "bg_bottom": (255, 238, 225),
        "title": (60, 35, 20), "subtitle": (130, 95, 70), "accent": (230, 180, 140),
        "body": (90, 70, 55), "highlight": (45, 30, 20),
    },
    "warm_grey": {
        "bg_top": (250, 247, 243), "bg_bottom": (238, 234, 228),
        "title": (65, 55, 48), "subtitle": (130, 120, 110), "accent": (195, 180, 165),
        "body": (90, 82, 75), "highlight": (50, 42, 36),
    },
    "cool": {
        "bg_top": (245, 248, 252), "bg_bottom": (220, 230, 245),
        "title": (25, 45, 70), "subtitle": (90, 110, 140), "accent": (160, 190, 220),
        "body": (60, 80, 110), "highlight": (20, 35, 55),
    },
    "blank": {
        "bg_top": (252, 252, 252), "bg_bottom": (248, 248, 248),
        "title": (30, 30, 30), "subtitle": (100, 100, 100), "accent": (200, 200, 200),
        "body": (70, 70, 70), "highlight": (20, 20, 20),
    },
    "twilight": {
        "bg_top": (238, 236, 242), "bg_bottom": (220, 218, 228),
        "title": (55, 50, 70), "subtitle": (110, 105, 130), "accent": (180, 170, 200),
        "body": (85, 80, 100), "highlight": (45, 40, 60),
    },
    "crimson": {
        "bg_top": (250, 240, 240), "bg_bottom": (242, 228, 228),
        "title": (85, 35, 35), "subtitle": (140, 90, 90), "accent": (210, 130, 130),
        "body": (120, 70, 70), "highlight": (70, 25, 25),
    },
    "mist": {
        "bg_top": (242, 244, 246), "bg_bottom": (228, 232, 236),
        "title": (50, 60, 70), "subtitle": (105, 115, 125), "accent": (160, 175, 190),
        "body": (80, 90, 100), "highlight": (40, 50, 60),
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


def _add_center_glow(img: Image.Image, palette: dict) -> Image.Image:
    """在画面上方叠加一个极淡的 accent 色光晕，增加空间深度。"""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    cx, cy = img.size[0] // 2, img.size[1] // 3
    c = palette["bg_top"]
    for r in range(500, 0, -25):
        ratio = r / 500
        alpha = int(10 * (1 - ratio))
        glow_draw.ellipse(
            [(cx - int(r * 1.5), cy - r), (cx + int(r * 1.5), cy + r)],
            fill=(min(255, c[0] + 20), min(255, c[1] + 20), min(255, c[2] + 20), alpha),
        )
    return Image.alpha_composite(img, glow)


def _add_noise_texture(img: Image.Image, intensity: int = 4) -> Image.Image:
    """叠加极淡的噪点纹理，模拟纸质质感。"""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    tile_size = 100
    noise = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
    import random
    pixels = []
    for _ in range(tile_size * tile_size):
        if random.random() < 0.12:
            v = random.randint(-intensity, intensity)
            a = random.randint(2, 5)
            pixels.append((128 + v, 128 + v, 128 + v, a))
        else:
            pixels.append((0, 0, 0, 0))
    noise.putdata(pixels)
    width, height = img.size
    full_noise = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for y in range(0, height, tile_size):
        for x in range(0, width, tile_size):
            full_noise.paste(noise, (x, y))
    return Image.alpha_composite(img, full_noise)


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
    p = PALETTE.get(style, PALETTE["warm"])

    # ── 背景 ──
    img = Image.new("RGBA", (COVER_WIDTH, COVER_HEIGHT), (*p["bg_top"], 255))
    draw = ImageDraw.Draw(img)

    if style in ("warm", "cool", "warm_grey", "twilight", "crimson", "mist", "blank"):
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

    # 装饰性大面积色块（仅非 chat/blank 风格）
    if style not in ("chat", "blank"):
        blob = Image.new("RGBA", (COVER_WIDTH, COVER_HEIGHT), (0, 0, 0, 0))
        blob_draw = ImageDraw.Draw(blob)
        cx, cy = COVER_WIDTH // 2, COVER_HEIGHT // 3
        for r in range(500, 0, -25):
            ratio = r / 500
            alpha = int(10 * (1 - ratio))
            blob_draw.ellipse(
                [(cx - int(r * 1.5), cy - r), (cx + int(r * 1.5), cy + r)],
                fill=(*p["accent"], alpha),
            )
        img = Image.alpha_composite(img, blob)
        draw = ImageDraw.Draw(img)

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

        # 装饰细线（3px 圆角风格）
        line_y = y_start + title_h + 50
        bar_w = 60
        draw.rounded_rectangle(
            [((COVER_WIDTH - bar_w) // 2, line_y), ((COVER_WIDTH + bar_w) // 2, line_y + 3)],
            radius=2,
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

    if img.mode == "RGBA":
        img = img.convert("RGB")
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


def generate_cover_ai(prompt: str, title: str, subtitle: str, style: str = "warm_grey", output_path: str = "assets/cover_ai.png") -> str:
    """
    方案1：AI绘画封面
    支持多后端：pollinations / dalle / fallback 模板合成
    """
    logger.info("正在生成AI绘画封面...")
    logger.info("背景prompt: %s...", prompt[:80])

    p = PALETTE.get(style, PALETTE["warm_grey"])
    bg_img = None

    if IMAGE_PROVIDER == "pollinations":
        encoded_prompt = requests.utils.quote(prompt)
        # 动态 seed：基于 prompt+title+subtitle 的 hash，保证同一篇笔记可复现，不同笔记不撞脸
        dynamic_seed = abs(hash((prompt, title, subtitle))) % 100000
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1242&height=1660&nologo=true&seed={dynamic_seed}"
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
        return generate_cover_template(title, subtitle, style=style, output_path=output_path)

    # 调整尺寸
    bg_img = bg_img.resize((COVER_WIDTH, COVER_HEIGHT), Image.LANCZOS)
    bg_img = bg_img.convert("RGBA")

    # 底部渐变遮罩（让文字清晰可读）
    overlay = Image.new("RGBA", (COVER_WIDTH, COVER_HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    mask_start = int(COVER_HEIGHT * 0.50)
    mask_full = int(COVER_HEIGHT * 0.78)
    for y in range(mask_start, COVER_HEIGHT):
        if y < mask_full:
            ratio = (y - mask_start) / (mask_full - mask_start)
            # 平滑缓入
            ratio = ratio * ratio * (3 - 2 * ratio)
            alpha = int(ratio * 160)
        else:
            alpha = 220
        overlay_draw.line([(0, y), (COVER_WIDTH, y)], fill=(0, 0, 0, alpha))

    composite = Image.alpha_composite(bg_img, overlay)
    draw = ImageDraw.Draw(composite)

    # 文字区域计算
    margin_x = 100
    max_text_w = COVER_WIDTH - margin_x * 2
    text_area_top = int(COVER_HEIGHT * 0.70)

    title_size, title_font = _calc_font_size(title, max_text_w, 80)
    title_lines = _wrap_text(title, title_font, max_text_w)
    title_h = len(title_lines) * (title_size + 14)

    sub_font = _get_font(34)
    sub_lines = _wrap_text(subtitle, sub_font, max_text_w - 60)
    sub_h = len(sub_lines) * 48

    card_pad_x = 60
    card_pad_y = 45
    card_w = max_text_w + card_pad_x * 2
    card_h = title_h + sub_h + 50 + card_pad_y * 2
    card_x = (COVER_WIDTH - card_w) // 2
    card_y = text_area_top - card_pad_y

    # ── 毛玻璃卡片 ──
    region = composite.crop((card_x, card_y, card_x + card_w, card_y + card_h))
    blurred = region.filter(ImageFilter.GaussianBlur(radius=18))
    frost = Image.new("RGBA", blurred.size, (255, 255, 255, 45))
    frosted = Image.alpha_composite(blurred, frost)
    composite.paste(frosted, (card_x, card_y))

    # 卡片细边框
    draw.rounded_rectangle(
        [(card_x, card_y), (card_x + card_w, card_y + card_h)],
        radius=24,
        outline=(255, 255, 255, 55),
        width=1,
    )

    # 装饰 accent 细线（标题上方）
    decor_w = 40
    decor_y = text_area_top - 14
    draw.rectangle(
        [((COVER_WIDTH - decor_w) // 2, decor_y), ((COVER_WIDTH + decor_w) // 2, decor_y + 2)],
        fill=(*p["accent"], 200),
    )

    # 主题化阴影色（比纯黑更高级）
    shadow_dark = (p["title"][0] // 4, p["title"][1] // 4, p["title"][2] // 4, 200)

    # 标题
    y_title = text_area_top
    for i, line in enumerate(title_lines):
        try:
            bbox = title_font.getbbox(line)
            tw = bbox[2] - bbox[0]
        except (AttributeError, TypeError):
            tw = 0
        x = (COVER_WIDTH - tw) // 2
        draw.text((x + 3, y_title + i * (title_size + 14) + 3), line, font=title_font, fill=shadow_dark)
        draw.text((x, y_title + i * (title_size + 14)), line, font=title_font, fill=(255, 255, 255, 255))

    # 副标题
    y_sub = y_title + title_h + 30
    for i, line in enumerate(sub_lines):
        try:
            bbox = sub_font.getbbox(line)
            tw = bbox[2] - bbox[0]
        except (AttributeError, TypeError):
            tw = 0
        x = (COVER_WIDTH - tw) // 2
        draw.text((x + 2, y_sub + i * 48 + 2), line, font=sub_font, fill=(*p["title"], 160))
        draw.text((x, y_sub + i * 48), line, font=sub_font, fill=(255, 255, 255, 235))

    final = composite.convert("RGB")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    final.save(output_path, quality=95)
    logger.info("AI绘画封面已保存: %s", output_path)
    return output_path


# ═══════════════════════════════════════════════════════════
# 内页文字图生成 — 小红书「呼吸感」排版
# ═══════════════════════════════════════════════════════════

# 视觉锚点符号（统一风格，不超过3种变体）
ANCHOR_SYMBOLS = ["\u25cf", "\u25cb", "\u25cf"]  # solid circle, hollow circle, solid circle


# 内页排版常量（供分页和渲染共用）
_BASE_FONT_SIZE = 42
_LINE_HEIGHT = int(_BASE_FONT_SIZE * 1.5)
_PARA_SPACING = int(_BASE_FONT_SIZE * 1.8)
_MAX_TEXT_W = int(COVER_WIDTH * 0.55)


def _paginate_blocks(blocks: list) -> list:
    """将 blocks 分页，返回 list[list[block]]，不含渲染，只计算分页。"""
    body_font = _get_font(_BASE_FONT_SIZE, bold=False)
    body_font_bold = _get_font(_BASE_FONT_SIZE + 4, bold=True)
    render_blocks = []
    for para_text, is_bold, is_sep in blocks:
        if is_sep:
            render_blocks.append(('__separator__', False, 0))
            continue
        font = body_font_bold if is_bold else body_font
        wrapped = _wrap_text(para_text, font, _MAX_TEXT_W)
        sub_chunks = []
        for i in range(0, len(wrapped), 3):
            sub_chunks.append(wrapped[i:i+3])
        for chunk in sub_chunks:
            render_blocks.append((chunk, is_bold, len(chunk)))

    y_start = 280
    y_end = COVER_HEIGHT - 120
    usable_height = y_end - y_start

    pages = []
    current_page = []
    current_height = 0
    for item in render_blocks:
        tag, is_bold, line_count = item
        if tag == '__separator__':
            if current_height + _LINE_HEIGHT // 2 > usable_height and current_page:
                pages.append(current_page)
                current_page = []
                current_height = 0
            current_page.append(('__separator__', False, 0))
            current_height += _LINE_HEIGHT // 2
        else:
            block_height = line_count * _LINE_HEIGHT
            if current_page:
                block_height += _PARA_SPACING
            if current_height + block_height > usable_height and current_page:
                pages.append(current_page)
                current_page = []
                current_height = 0
                block_height = line_count * _LINE_HEIGHT
            current_page.append((tag, is_bold, line_count))
            current_height += block_height

    if current_page:
        pages.append(current_page)
    return pages


def generate_inner_page(text: str, page_num: int, total_pages: int, style: str = "warm_grey",
                        output_path: str = "assets/inner_page.png") -> str | None:
    """把单页文字渲染成小红书风格内页图——呼吸感排版，左对齐，短段落，视觉锚点"""
    p = PALETTE.get(style, PALETTE["warm_grey"])

    img = Image.new("RGBA", (COVER_WIDTH, COVER_HEIGHT), (*p["bg_top"], 255))
    draw = ImageDraw.Draw(img)
    _draw_gradient_bg(draw, COVER_WIDTH, COVER_HEIGHT, p["bg_top"], p["bg_bottom"])

    # 叠加 center glow 和纸质噪点
    img = _add_center_glow(img, p)
    img = _add_noise_texture(img, intensity=3)
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)

    text = text.strip()
    if not text:
        return None

    # 解析段落：保留 --- 分隔符、**加粗**标记
    raw_paragraphs = text.split('\n')
    blocks = []  # 每段是 (text, is_bold, is_separator)
    for raw in raw_paragraphs:
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped == '---':
            blocks.append(('', False, True))
            continue

        # 严格过滤元数据行、话题标签行、图片占位符等
        _skip_markers = ['【金句】', '【互动钩子】', '【话题标签】', '【视觉风格】', '【标题候选】', '【封面页】', '【正文】']
        if any(m in stripped for m in _skip_markers):
            continue
        if re.match(r'^话题标签[：:]', stripped):
            continue
        if re.match(r'^视觉风格[：:]', stripped):
            continue
        if re.match(r'\[Image\s*#\d+\]', stripped):
            continue

        # 过滤纯视觉风格标签值
        if stripped in ('warm_grey', 'twilight', 'crimson', 'mist', 'cool', 'warm', 'blank'):
            continue
        # 过滤纯话题标签行（整行都是 #xxx 格式）
        words = stripped.split()
        if words and all(w.startswith('#') for w in words):
            continue

        # 支持行内 **bold** 标记，并移除不支持的 emoji
        is_bold = bool(re.search(r'\*\*(.*?)\*\*', stripped))
        clean = re.sub(r'\*\*(.*?)\*\*', lambda m: m.group(1), stripped).strip()
        clean = re.sub(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0001F900-\U0001F9FF\U00002600-\U000026FF]+", '', clean).strip()
        if clean:
            blocks.append((clean, is_bold, False))

    if not blocks:
        return None

    # 分页
    pages = _paginate_blocks(blocks)

    if not pages or page_num > len(pages):
        return None
    page_blocks = pages[page_num - 1]

    # 渲染参数
    margin_left = 140
    x_start = margin_left
    base_font_size = _BASE_FONT_SIZE
    line_height = _LINE_HEIGHT
    para_spacing = _PARA_SPACING
    body_font = _get_font(base_font_size, bold=False)
    body_font_bold = _get_font(base_font_size + 4, bold=True)
    y_start = 280

    # 绘制当前页
    y = y_start
    anchor_idx = (page_num - 1) % len(ANCHOR_SYMBOLS)

    # 高亮块底色（accent 15% + bg_top 85%）
    bg_top = p["bg_top"]
    accent = p["accent"]
    highlight_bg = (
        int(accent[0] * 0.35 + bg_top[0] * 0.65),
        int(accent[1] * 0.35 + bg_top[1] * 0.65),
        int(accent[2] * 0.35 + bg_top[2] * 0.65),
    )

    # 最后一页：把剩余空间均匀分配到段落间距，让收尾更舒展
    actual_para_spacing = para_spacing
    if page_num == total_pages:
        raw_height = 0
        has_content = False
        for block in page_blocks:
            tag, is_bold, line_count = block
            if tag == '__separator__':
                raw_height += line_height // 2
            else:
                raw_height += line_count * line_height
                if has_content:
                    raw_height += para_spacing
                has_content = True
        usable_height = (COVER_HEIGHT - 120) - y_start
        remaining = usable_height - raw_height
        text_block_count = sum(1 for b in page_blocks if b[0] != '__separator__')
        if text_block_count > 1 and remaining > 0:
            actual_para_spacing = para_spacing + remaining // text_block_count

    # 控制锚点密度：每页最多前 3 个文字段落显示锚点
    text_block_indices = [i for i, b in enumerate(page_blocks) if b[0] != '__separator__']
    anchor_allowed = set(text_block_indices[:3])

    # 正文色阶控制：首段/分隔符后使用 title 色，其余使用 body 色
    after_sep_or_first = True

    for block_idx, block in enumerate(page_blocks):
        tag, is_bold, line_count = block
        if tag == '__separator__':
            sep_x1 = x_start
            sep_x2 = x_start + 80
            sep_y = y + line_height // 2 - 2
            draw.rectangle([(sep_x1, sep_y), (sep_x2, sep_y + 2)], fill=p["accent"])
            y += line_height // 2 + actual_para_spacing // 2
            after_sep_or_first = True
            continue

        font = body_font_bold if is_bold else body_font

        # 最后一页最后一段：短句居中放大，作为视觉落点
        # 找到最后一个非 separator 的 block（忽略末尾的 separator）
        last_text_idx = max((i for i, b in enumerate(page_blocks) if b[0] != '__separator__'), default=-1)
        is_last_block = (block_idx == len(page_blocks) - 1)
        is_last_text_block = (block_idx == last_text_idx)
        is_last_page = (page_num == total_pages)
        is_short = line_count <= 2 and sum(len(line) for line in tag) <= 24

        if is_last_page and is_last_text_block and is_short:
            # 装饰细线
            decor_y = y - 20
            decor_w = 50
            draw.rectangle(
                [((COVER_WIDTH - decor_w) // 2, decor_y), ((COVER_WIDTH + decor_w) // 2, decor_y + 2)],
                fill=p["accent"],
            )
            y = decor_y + 30

            # 放大字号并居中
            large_size = base_font_size + 8
            large_font = _get_font(large_size, bold=True)
            large_lines = _wrap_text(''.join(tag), large_font, _MAX_TEXT_W)
            large_line_h = int(large_size * 1.5)
            for line in large_lines:
                try:
                    bbox = large_font.getbbox(line)
                    lw = bbox[2] - bbox[0]
                except Exception:
                    lw = 0
                x = (COVER_WIDTH - lw) // 2
                draw.text((x, y), line, font=large_font, fill=p["highlight"])
                y += large_line_h
            y += actual_para_spacing
            continue

        # 金句高亮块
        if is_bold:
            max_line_w = 0
            for line in tag:
                try:
                    bbox = font.getbbox(line)
                    lw = bbox[2] - bbox[0]
                except Exception:
                    lw = 0
                max_line_w = max(max_line_w, lw)
            block_h = line_count * line_height
            pad_x = 24
            pad_y = 16
            rect_x1 = x_start - pad_x
            rect_y1 = y - pad_y
            rect_x2 = x_start + max_line_w + pad_x
            rect_y2 = y + block_h + pad_y
            rect_x2 = min(rect_x2, COVER_WIDTH - 40)
            draw.rounded_rectangle(
                [(rect_x1, rect_y1), (rect_x2, rect_y2)],
                radius=16,
                fill=highlight_bg,
            )

        # 锚点
        use_anchor = block_idx in anchor_allowed and not (is_last_page and is_last_text_block)

        dot_size = int(base_font_size * 0.4)
        dot_radius = dot_size // 2

        # 确定本段文字颜色
        if is_bold:
            text_color = p["highlight"]
        elif after_sep_or_first:
            text_color = p["title"]
        else:
            text_color = p["body"]

        for i, line in enumerate(tag):
            if i == 0 and use_anchor:
                dot_x = x_start + dot_radius
                dot_y_center = y + dot_radius
                anchor_sym = ANCHOR_SYMBOLS[anchor_idx]
                if anchor_sym == "\u25cf":
                    draw.ellipse(
                        [(dot_x - dot_radius, dot_y_center - dot_radius),
                         (dot_x + dot_radius, dot_y_center + dot_radius)],
                        fill=p["accent"],
                    )
                else:
                    draw.ellipse(
                        [(dot_x - dot_radius, dot_y_center - dot_radius),
                         (dot_x + dot_radius, dot_y_center + dot_radius)],
                        outline=p["accent"],
                        width=2,
                    )
                anchor_x = x_start + dot_size + int(base_font_size * 0.5)
            else:
                anchor_x = x_start

            draw.text((anchor_x, y), line, font=font, fill=text_color)
            y += line_height

        y += actual_para_spacing
        after_sep_or_first = False

    # 底部页码
    page_font = _get_font(20)
    page_text = f"— {page_num} / {total_pages} —"
    try:
        bbox = page_font.getbbox(page_text)
        tw = bbox[2] - bbox[0]
    except Exception:
        tw = 0
    page_y = COVER_HEIGHT - 70
    # 页码上方细线装饰
    line_w = 30
    draw.rectangle(
        [((COVER_WIDTH - line_w) // 2, page_y - 14), ((COVER_WIDTH + line_w) // 2, page_y - 12)],
        fill=p["accent"],
    )
    draw.text(((COVER_WIDTH - tw) // 2, page_y), page_text, font=page_font, fill=p["subtitle"])

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    img.save(output_path, quality=95)
    logger.info("内页图已保存: %s", output_path)
    return output_path


def generate_inner_pages(content: str, out_dir: str, style: str = "warm_grey") -> list[str]:
    """解析笔记正文，生成所有内页图"""
    # 提取正文部分
    # 提取正文：从【正文】或# 正文开始，到下一个【xxx】或# 【xxx】或文档结束
    end_pattern = r'(?=\n\s*(?:\*?【|#{1,6}\s*【)|$)'
    body_match = re.search(r'\*?【正文】\*?\s*\n+(.*?)' + end_pattern, content, re.DOTALL)
    if not body_match:
        body_match = re.search(r'#{1,6}\s*\[?正文\]?.*?\n(.*?)' + end_pattern, content, re.DOTALL)
    if not body_match:
        body_match = re.search(
            r'\*?【(?:封面页|封面)】\*?[\s\S]*?(?:\n\s*---+\s*\n|\n\n)(.*?)' + end_pattern,
            content,
            re.DOTALL,
        )

    if not body_match:
        logger.warning("未提取到正文，跳过内页生成")
        return []

    body = body_match.group(1).strip()

    # 保留 --- 分隔符，收集所有正文行
    all_lines = []
    for line in body.split('\n'):
        stripped = line.strip()
        _skip_markers = ['【金句】', '【互动钩子】', '【话题标签】', '【视觉风格】', '【标题候选】', '【封面页】', '【正文】']
        if any(m in stripped for m in _skip_markers):
            continue
        if stripped.startswith('#') and not stripped.startswith('##'):
            continue
        if stripped.startswith('【') and '】' in stripped:
            continue
        if re.match(r'^话题标签[：:]', stripped):
            continue
        if re.match(r'^视觉风格[：:]', stripped):
            continue
        if re.match(r'\[Image\s*#\d+\]', stripped):
            continue
        # 过滤纯话题标签行
        words = stripped.split()
        if words and all(w.startswith('#') for w in words):
            continue
        all_lines.append(stripped)

    if not all_lines:
        logger.warning("正文过滤后为空，跳过内页生成")
        return []

    # 将所有行合并为一段文本（保留 --- 分隔符）
    full_text = '\n'.join(all_lines)

    # 解析 blocks（与 generate_inner_page 保持一致）
    raw_paragraphs = full_text.split('\n')
    blocks = []
    for raw in raw_paragraphs:
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped == '---':
            blocks.append(('', False, True))
            continue
        _skip_markers = ['【金句】', '【互动钩子】', '【话题标签】', '【视觉风格】', '【标题候选】', '【封面页】', '【正文】']
        if any(m in stripped for m in _skip_markers):
            continue
        if re.match(r'^话题标签[：:]', stripped):
            continue
        if re.match(r'^视觉风格[：:]', stripped):
            continue
        if re.match(r'\[Image\s*#\d+\]', stripped):
            continue
        words = stripped.split()
        if words and all(w.startswith('#') for w in words):
            continue
        # 支持行内 **bold** 标记，并移除不支持的 emoji
        is_bold = bool(re.search(r'\*\*(.*?)\*\*', stripped))
        clean = re.sub(r'\*\*(.*?)\*\*', lambda m: m.group(1), stripped).strip()
        clean = re.sub(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0001F900-\U0001F9FF\U00002600-\U000026FF]+", '', clean).strip()
        if clean:
            blocks.append((clean, is_bold, False))

    if not blocks:
        logger.warning("正文解析后无有效内容，跳过内页生成")
        return []

    # 精确分页，得到准确总页数
    pages = _paginate_blocks(blocks)
    total_pages = len(pages)
    if total_pages == 0:
        logger.warning("分页后无内容，跳过内页生成")
        return []

    logger.info("📄 共 %d 页内页，开始生成...", total_pages)

    def _render_page(page_num: int) -> str | None:
        path = f"{out_dir}/inner_page_{page_num}.png"
        return generate_inner_page(full_text, page_num, total_pages, style=style, output_path=path)

    paths = []
    max_workers = min(4, total_pages)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_render_page, page_num): page_num for page_num in range(1, total_pages + 1)}
        for future in concurrent.futures.as_completed(futures):
            page_num = futures[future]
            try:
                result = future.result()
                if result:
                    paths.append(result)
                else:
                    logger.warning("第 %d 页生成为空", page_num)
            except Exception as e:
                logger.error("第 %d 页生成异常: %s", page_num, e)

    paths.sort()
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
