"""共享渲染工具 — 字体、渐变、噪点、文字排版、布局常量。"""

import functools
import os
import platform
import random
import re
import types

from PIL import Image, ImageDraw, ImageFont

from core.config import get_logger, FONT_DIR

logger = get_logger(__name__)

# ── 封面尺寸 ──
COVER_WIDTH = 1242
COVER_HEIGHT = 1660

# ── 字体路径 ──
FONT_REGULAR = str(FONT_DIR / "NotoSansSC-Regular.ttf")
FONT_BOLD = str(FONT_DIR / "NotoSansSC-Bold.ttf")


def _freeze_dict(d: dict) -> types.MappingProxyType:
    """返回只读视图，防止意外修改模块级常量。"""
    return types.MappingProxyType(d)


# ── 内页排版常量 ──
LAYOUT = _freeze_dict({
    "base_font_size": 52,
    "bold_extra": 6,
    "line_height_ratio": 1.55,
    "para_spacing_ratio": 2.0,
    "max_text_width_ratio": 0.68,
    "page_top": 200,
    "page_bottom_margin": 140,
    "margin_left": 120,
    "separator_height_ratio": 1.2,
    "last_page_expand": True,
    "anchor_max_per_page": 3,
    "last_block_font_boost": 18,
    "bubble_pad_y": 28,
    "last_block_max_chars": 28,
    "page_number_font_size": 22,
    "page_number_y_offset": 80,
})

# ── 品牌色调（冻结） ──
PALETTE = _freeze_dict({
    "warm": {
        "bg_top": (255, 252, 248), "bg_bottom": (255, 238, 225),
        "title": (60, 35, 20), "subtitle": (130, 95, 70), "accent": (230, 180, 140),
        "body": (90, 70, 55), "highlight": (45, 30, 20),
        "cover_accent": (225, 140, 80),  # 封面用：更浓的暖橘
    },
    "warm_grey": {
        "bg_top": (242, 234, 222), "bg_bottom": (218, 206, 188),
        "title": (60, 50, 42), "subtitle": (125, 112, 98), "accent": (188, 166, 138),
        "body": (85, 75, 65), "highlight": (45, 38, 30),
        "cover_accent": (175, 130, 95),  # 封面用：咖啡色
    },
    "cool": {
        "bg_top": (245, 248, 252), "bg_bottom": (220, 230, 245),
        "title": (25, 45, 70), "subtitle": (90, 110, 140), "accent": (160, 190, 220),
        "body": (60, 80, 110), "highlight": (20, 35, 55),
        "cover_accent": (90, 140, 200),  # 封面用：亮蓝
    },
    "blank": {
        "bg_top": (252, 252, 252), "bg_bottom": (248, 248, 248),
        "title": (30, 30, 30), "subtitle": (100, 100, 100), "accent": (200, 200, 200),
        "body": (70, 70, 70), "highlight": (20, 20, 20),
        "cover_accent": (80, 80, 80),  # 封面用：深灰
    },
    "twilight": {
        "bg_top": (228, 222, 238), "bg_bottom": (198, 188, 222),
        "title": (55, 50, 75), "subtitle": (110, 103, 132), "accent": (172, 158, 200),
        "body": (82, 76, 100), "highlight": (42, 36, 62),
        "cover_accent": (135, 112, 180),  # 封面用：紫色
    },
    "crimson": {
        "bg_top": (250, 240, 240), "bg_bottom": (242, 228, 228),
        "title": (85, 35, 35), "subtitle": (140, 90, 90), "accent": (210, 130, 130),
        "body": (120, 70, 70), "highlight": (70, 25, 25),
        "cover_accent": (200, 85, 75),  # 封面用：正红
    },
    "mist": {
        "bg_top": (242, 244, 246), "bg_bottom": (228, 232, 236),
        "title": (50, 60, 70), "subtitle": (105, 115, 125), "accent": (160, 175, 190),
        "body": (80, 90, 100), "highlight": (40, 50, 60),
        "cover_accent": (100, 140, 175),  # 封面用：蓝灰
    },
})

# ── 从 LAYOUT 导出常用常量 ──
_BASE_FONT_SIZE = LAYOUT["base_font_size"]
_LINE_HEIGHT = int(_BASE_FONT_SIZE * LAYOUT["line_height_ratio"])
_PARA_SPACING = int(_BASE_FONT_SIZE * LAYOUT["para_spacing_ratio"])
_MAX_TEXT_W = int(COVER_WIDTH * LAYOUT["max_text_width_ratio"])


@functools.lru_cache(maxsize=32)
def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """加载字体，失败时按平台 fallback 系统黑体。"""
    path = FONT_BOLD if bold else FONT_REGULAR
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        logger.warning("字体文件缺失: %s，尝试系统 fallback", path)

    system = platform.system()
    fallbacks = []
    if system == "Darwin":
        fallbacks = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
    elif system == "Windows":
        fallbacks = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
        ]
    else:
        fallbacks = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        ]
    for fb in fallbacks:
        try:
            return ImageFont.truetype(fb, size)
        except OSError:
            continue

    # 最后的 fallback：DejaVu Sans（不包含 CJK，但至少有拉丁字符）
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except OSError:
        pass

    raise OSError(
        f"无法加载任何字体。请确保 assets/fonts/ 下有 NotoSansSC-Regular.ttf 和 NotoSansSC-Bold.ttf，"
        f"或系统有中文字体（macOS: PingFang, Windows: msyh, Linux: NotoSansCJK）。"
    )


def _wrap_text(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int,
               balance_lines: bool = True) -> list[str]:
    """按最大宽度自动换行，正确处理原始换行符。

    balance_lines=True 时，段内最后一行过短会被平衡——从倒数第二行移字过来，
    避免"12 字 + 3 字"这种难看的断行。
    """
    _CLOSE_PUNCT = set('。，！？：；、）」】）》…—–·')
    _OPEN_PUNCT = set('（「【《')

    def _char_width(ch: str) -> float:
        try:
            bbox = font.getbbox(ch)
            return bbox[2] - bbox[0]
        except (AttributeError, TypeError):
            return 0

    all_lines = []
    for paragraph in text.split('\n'):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        # 逐字符换行
        para_lines = []
        current = ""
        for char in paragraph:
            test = current + char
            try:
                bbox = font.getbbox(test)
                w = bbox[2] - bbox[0]
            except (AttributeError, TypeError):
                w = 0
            if w > max_width and current:
                para_lines.append(current)
                current = char
            else:
                current = test
        if current:
            para_lines.append(current)

        # 标点合并
        merged = []
        i = 0
        while i < len(para_lines):
            line = para_lines[i]
            if i + 1 < len(para_lines) and len(para_lines[i + 1]) == 1 and para_lines[i + 1] in _CLOSE_PUNCT:
                merged.append(line + para_lines[i + 1])
                i += 2
            elif len(line) == 1 and line in _OPEN_PUNCT and i + 1 < len(para_lines):
                merged.append(line + para_lines[i + 1])
                i += 2
            else:
                merged.append(line)
                i += 1

        # 末行平衡：最后一行太短时，从倒数第二行移字过来
        if balance_lines and len(merged) >= 2:
            last_len = len(merged[-1])
            second_last_len = len(merged[-2])
            # 末行不足倒数第二行的 35% → 平衡
            if last_len < second_last_len * 0.35:
                shift = min(2, second_last_len - 1)
                merged[-1] = merged[-2][-shift:] + merged[-1]
                merged[-2] = merged[-2][:-shift]

        all_lines.extend(merged)

    # 跨段落短行合并：消除"6字孤行"——相邻行中任一行太短就尝试合并
    if balance_lines and len(all_lines) >= 2:
        approx_max_chars = max_width // max(font.size, 1)
        short_threshold = max(6, approx_max_chars // 3)  # 约 5-6 字
        compacted = []
        i = 0
        while i < len(all_lines):
            merged = False
            if i + 1 < len(all_lines):
                a, b = all_lines[i], all_lines[i + 1]
                # 任一太短 → 尝试合并
                if len(a) <= short_threshold or len(b) <= short_threshold:
                    combined = a + b
                    try:
                        bbox = font.getbbox(combined)
                        cw = bbox[2] - bbox[0]
                    except (AttributeError, TypeError):
                        cw = 0
                    if cw <= max_width:
                        compacted.append(combined)
                        i += 2
                        merged = True
            if not merged:
                compacted.append(all_lines[i])
                i += 1
        return compacted

    return all_lines


def _draw_gradient_bg(img: Image.Image, width: int, height: int, c1: tuple[int, int, int], c2: tuple[int, int, int]) -> None:
    """绘制线性渐变背景"""
    strip = Image.new("RGB", (1, height))
    pixels = []
    for y in range(height):
        ratio = y / max(height - 1, 1)
        r = int(c1[0] * (1 - ratio) + c2[0] * ratio)
        g = int(c1[1] * (1 - ratio) + c2[1] * ratio)
        b = int(c1[2] * (1 - ratio) + c2[2] * ratio)
        pixels.append((r, g, b))
    strip.putdata(pixels)
    gradient = strip.resize((width, height), Image.Resampling.BILINEAR)
    img.paste(gradient, (0, 0))


def _add_center_glow(img: Image.Image, palette: dict) -> Image.Image:
    """在画面上方叠加一个极淡的 accent 色光晕。"""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    cx, cy = img.size[0] // 2, img.size[1] // 3
    c = palette["bg_top"]
    for r in range(500, 0, -25):
        ratio = r / 500
        alpha = int(18 * (1 - ratio))
        glow_draw.ellipse(
            [(cx - int(r * 1.5), cy - r), (cx + int(r * 1.5), cy + r)],
            fill=(min(255, c[0] + 20), min(255, c[1] + 20), min(255, c[2] + 20), alpha),
        )
    return Image.alpha_composite(img, glow)


def _add_noise_texture(img: Image.Image, intensity: int = 4, seed: int | None = None) -> Image.Image:
    """叠加极淡的噪点纹理，模拟纸质质感。

    Args:
        img: 输入图像
        intensity: 噪点强度（-intensity 到 +intensity 的随机偏移）
        seed: 随机种子，用于可复现的结果；None 则使用系统时间
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    rng = random.Random(seed)
    tile_size = 100
    noise = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
    pixels = []
    for _ in range(tile_size * tile_size):
        if rng.random() < 0.12:
            v = rng.randint(-intensity, intensity)
            a = rng.randint(2, 5)
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


def _calc_font_size(text: str, max_width: int, target_size: int, min_size: int = 48) -> tuple[int, ImageFont.FreeTypeFont]:
    """根据文字动态计算字号。"""
    for size in range(target_size, min_size - 1, -4):
        font = _get_font(size, bold=True)
        wrapped = _wrap_text(text, font, max_width)
        max_line_w = 0
        for line in wrapped:
            try:
                bbox = font.getbbox(line)
                w = bbox[2] - bbox[0]
            except (AttributeError, TypeError):
                w = 0
            max_line_w = max(max_line_w, w)
        if max_line_w <= max_width:
            return size, font
    return min_size, _get_font(min_size, bold=True)
