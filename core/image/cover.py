"""封面生成 — AI 绘画 + 模板合成。"""

import hashlib
import io
import os
import random
import time
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFilter

from core.config import get_logger, IMAGE_PROVIDER
from core.image.render import (
    COVER_WIDTH, COVER_HEIGHT, PALETTE, LAYOUT,
    _get_font, _wrap_text, _draw_gradient_bg, _calc_font_size,
)

logger = get_logger(__name__)


def _http_get_with_retry(url: str, retries: int = 3, timeout: int = 120, **kwargs) -> requests.Response:
    """带重试的 HTTP GET，处理 429/5xx 和网络异常。"""
    if retries < 1:
        raise ValueError(f"retries 必须 >= 1，收到 {retries}")
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
                wait = (2 ** attempt) * (0.5 + random.random())
                logger.warning("图片 API 请求失败 (HTTP %s)，%.1f秒后重试 (%d/%d)", status, wait, attempt + 1, retries)
                time.sleep(wait)
                continue
            raise
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_err = e
            wait = (2 ** attempt) * (0.5 + random.random())
            logger.warning("图片 API 请求失败 (%s)，%.1f秒后重试 (%d/%d)", type(e).__name__, wait, attempt + 1, retries)
            time.sleep(wait)
    raise last_err


def generate_cover_template(title: str, subtitle: str, style: str = "warm", number: int | None = None, output_path: str = "assets/cover_template.png") -> str:
    """模板合成封面。"""
    p = PALETTE.get(style, PALETTE["warm"])

    img = Image.new("RGBA", (COVER_WIDTH, COVER_HEIGHT), (*p["bg_top"], 255))
    draw = ImageDraw.Draw(img)

    if style in ("warm", "cool", "warm_grey", "twilight", "crimson", "mist", "blank"):
        _draw_gradient_bg(img, COVER_WIDTH, COVER_HEIGHT, p["bg_top"], p["bg_bottom"])
    elif style == "chat":
        draw.rectangle([(0, 0), (COVER_WIDTH, COVER_HEIGHT)], fill=(235, 235, 235))
        draw.rectangle([(0, 0), (COVER_WIDTH, 110)], fill=(245, 245, 245))
        draw.line([(0, 110), (COVER_WIDTH, 110)], fill=(220, 220, 220), width=1)
        time_font = _get_font(24)
        draw.text((COVER_WIDTH // 2 - 60, 55), "下午 3:42", font=time_font, fill=(150, 150, 150))
    elif style == "number":
        _draw_gradient_bg(img, COVER_WIDTH, COVER_HEIGHT, p["bg_top"], p["bg_bottom"])

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

    margin_x = 100
    max_text_w = COVER_WIDTH - margin_x * 2

    if style == "chat":
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

        draw.rounded_rectangle([(bx, by), (bx + bubble_w, by + bubble_h)], radius=30, fill=(149, 236, 105))
        tri = [
            (bx + bubble_w - 40, by + bubble_h),
            (bx + bubble_w + 15, by + bubble_h + 25),
            (bx + bubble_w - 40, by + bubble_h + 25),
        ]
        draw.polygon(tri, fill=(149, 236, 105))

        y_text = by + bubble_pad
        for i, line in enumerate(title_lines):
            bbox = title_font.getbbox(line)
            tw = bbox[2] - bbox[0]
            x = bx + (bubble_w - tw) // 2
            draw.text((x, y_text + i * 88), line, font=title_font, fill=(40, 40, 40))

        y_sub = y_text + title_h + bubble_pad
        for i, line in enumerate(sub_lines):
            bbox = sub_font.getbbox(line)
            tw = bbox[2] - bbox[0]
            x = bx + (bubble_w - tw) // 2
            draw.text((x, y_sub + i * 48), line, font=sub_font, fill=(80, 80, 80))

    elif style == "number":
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
        draw.text((nx, ny), num, font=num_font, fill=(p["accent"]))

        title_font = _get_font(72, bold=True)
        title_lines = _wrap_text(title, title_font, max_text_w)
        y_title = ny + nh + 60
        for i, line in enumerate(title_lines):
            bbox = title_font.getbbox(line)
            tw = bbox[2] - bbox[0]
            x = (COVER_WIDTH - tw) // 2
            draw.text((x, y_title + i * 92), line, font=title_font, fill=p["title"])

        sub_font = _get_font(36)
        sub_lines = _wrap_text(subtitle, sub_font, max_text_w - 100)
        y_sub = y_title + len(title_lines) * 92 + 50
        for i, line in enumerate(sub_lines):
            bbox = sub_font.getbbox(line)
            tw = bbox[2] - bbox[0]
            x = (COVER_WIDTH - tw) // 2
            draw.text((x, y_sub + i * 54), line, font=sub_font, fill=p["subtitle"])

    elif style == "blank":
        title_size, title_font = _calc_font_size(title, max_text_w, 120)
        title_lines = _wrap_text(title, title_font, max_text_w)
        title_h = len(title_lines) * (title_size + 20)

        y_start = COVER_HEIGHT // 3 - title_h // 2
        for i, line in enumerate(title_lines):
            bbox = title_font.getbbox(line)
            tw = bbox[2] - bbox[0]
            x = (COVER_WIDTH - tw) // 2
            draw.text((x, y_start + i * (title_size + 20)), line, font=title_font, fill=p["title"])

        line_y = y_start + title_h + 60
        draw.rectangle([(COVER_WIDTH // 2 - 40, line_y), (COVER_WIDTH // 2 + 40, line_y + 4)], fill=p["accent"])

        sub_font = _get_font(36)
        sub_lines = _wrap_text(subtitle, sub_font, max_text_w - 100)
        y_sub = line_y + 50
        for i, line in enumerate(sub_lines):
            bbox = sub_font.getbbox(line)
            tw = bbox[2] - bbox[0]
            x = (COVER_WIDTH - tw) // 2
            draw.text((x, y_sub + i * 54), line, font=sub_font, fill=p["subtitle"])

    else:
        title_size, title_font = _calc_font_size(title, max_text_w, 96)
        title_lines = _wrap_text(title, title_font, max_text_w)
        title_h = len(title_lines) * (title_size + 16)

        y_start = COVER_HEIGHT // 3 - title_h // 2
        for i, line in enumerate(title_lines):
            bbox = title_font.getbbox(line)
            tw = bbox[2] - bbox[0]
            x = (COVER_WIDTH - tw) // 2
            draw.text((x + 2, y_start + i * (title_size + 16) + 2), line, font=title_font, fill=(0, 0, 0, 20))
            draw.text((x, y_start + i * (title_size + 16)), line, font=title_font, fill=p["title"])

        line_y = y_start + title_h + 50
        bar_w = 60
        draw.rounded_rectangle(
            [((COVER_WIDTH - bar_w) // 2, line_y), ((COVER_WIDTH + bar_w) // 2, line_y + 3)],
            radius=2,
            fill=p["accent"],
        )

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


def generate_cover_ai(prompt: str, title: str, subtitle: str, style: str = "warm_grey", output_path: str = "assets/cover_ai.png") -> str:
    """AI 绘画封面，支持 pollinations / dalle，失败时 fallback 到模板。"""
    logger.info("正在生成AI绘画封面...")
    logger.info("背景prompt: %s...", prompt[:80])

    p = PALETTE.get(style, PALETTE["warm_grey"])
    bg_img = None

    if IMAGE_PROVIDER == "pollinations":
        encoded_prompt = quote(prompt)
        seed_input = f"{prompt}:{title}:{subtitle}".encode("utf-8")
        dynamic_seed = int(hashlib.md5(seed_input).hexdigest()[:6], 16) % 100000
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
            last_err = None
            for attempt in range(3):
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
                    break
                except requests.exceptions.HTTPError as e:
                    status = e.response.status_code if e.response else 0
                    if status == 429 or 500 <= status < 600:
                        last_err = e
                        wait = (2 ** attempt) * (0.5 + random.random())
                        logger.warning("DALL-E API 请求失败 (HTTP %s)，%.1f秒后重试 (%d/3)", status, wait, attempt + 1)
                        time.sleep(wait)
                        continue
                    raise
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    last_err = e
                    wait = (2 ** attempt) * (0.5 + random.random())
                    logger.warning("DALL-E API 请求失败 (%s)，%.1f秒后重试 (%d/3)", type(e).__name__, wait, attempt + 1)
                    time.sleep(wait)
            else:
                if last_err:
                    logger.warning("DALL-E API 最终失败: %s", last_err)

    else:
        logger.warning("不支持的 IMAGE_PROVIDER: %s", IMAGE_PROVIDER)

    if bg_img is None:
        logger.info("使用模板合成作为fallback...")
        return generate_cover_template(title, subtitle, style=style, output_path=output_path)

    bg_img = bg_img.resize((COVER_WIDTH, COVER_HEIGHT), Image.Resampling.LANCZOS)
    bg_img = bg_img.convert("RGBA")

    overlay = Image.new("RGBA", (COVER_WIDTH, COVER_HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    mask_start = int(COVER_HEIGHT * 0.50)
    mask_full = int(COVER_HEIGHT * 0.78)
    for y in range(mask_start, COVER_HEIGHT):
        if y < mask_full:
            ratio = (y - mask_start) / (mask_full - mask_start)
            ratio = ratio * ratio * (3 - 2 * ratio)
            alpha = int(ratio * 160)
        else:
            alpha = 220
        overlay_draw.line([(0, y), (COVER_WIDTH, y)], fill=(0, 0, 0, alpha))

    composite = Image.alpha_composite(bg_img, overlay)
    draw = ImageDraw.Draw(composite)

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

    region = composite.crop((card_x, card_y, card_x + card_w, card_y + card_h))
    blurred = region.filter(ImageFilter.GaussianBlur(radius=18))
    frost = Image.new("RGBA", blurred.size, (255, 255, 255, 45))
    frosted = Image.alpha_composite(blurred, frost)
    composite.paste(frosted, (card_x, card_y))

    draw.rounded_rectangle(
        [(card_x, card_y), (card_x + card_w, card_y + card_h)],
        radius=24,
        outline=(255, 255, 255, 55),
        width=1,
    )

    decor_w = 40
    decor_y = text_area_top - 14
    draw.rectangle(
        [((COVER_WIDTH - decor_w) // 2, decor_y), ((COVER_WIDTH + decor_w) // 2, decor_y + 2)],
        fill=(*p["accent"], 200),
    )

    shadow_dark = (p["title"][0] // 4, p["title"][1] // 4, p["title"][2] // 4, 200)

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


def generate_all_covers(title: str, subtitle: str, prompt: str, number: int | None = None, output_dir: str = "assets") -> dict[str, str]:
    """一次性生成所有风格的封面。"""
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
