"""内页生成 — 分页、解析、渲染。"""

import concurrent.futures
import os
import re

from PIL import Image, ImageDraw

from core.config import get_logger
from core.image.render import (
    COVER_WIDTH, COVER_HEIGHT, PALETTE, LAYOUT,
    _get_font, _wrap_text, _draw_gradient_bg, _add_center_glow, _add_noise_texture,
    _BASE_FONT_SIZE, _LINE_HEIGHT, _PARA_SPACING, _MAX_TEXT_W,
)

logger = get_logger(__name__)

ANCHOR_SYMBOLS = ["●", "○", "◆"]  # solid circle, hollow circle, solid diamond

_SKIP_MARKERS = ['【金句】', '【互动钩子】', '【话题标签】', '【视觉风格】', '【标题候选】', '【封面页】', '【正文】']
_EMOJI_RE = re.compile(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0001F900-\U0001F9FF\U00002600-\U000026FF]+")
_BOLD_RE = re.compile(r'\*\*(.*?)\*\*')


def _parse_to_blocks(text: str) -> list[tuple[str, bool, bool]]:
    """解析文本为 block 列表：(text, is_bold, is_separator)。"""
    blocks = []
    for raw in text.split('\n'):
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped == '---':
            blocks.append(('', False, True))
            continue
        if any(m in stripped for m in _SKIP_MARKERS):
            continue
        if re.match(r'^话题标签[：:]', stripped):
            continue
        if re.match(r'^视觉风格[：:]', stripped):
            continue
        if re.match(r'\[Image\s*#\d+\]', stripped):
            continue
        if re.match(r'^[（(]第?\d+页[）)]', stripped):
            continue
        if re.match(r'^第\d+页', stripped):
            continue
        if stripped in ('warm_grey', 'twilight', 'crimson', 'mist', 'cool', 'warm', 'blank'):
            continue
        words = stripped.split()
        if words and all(w.startswith('#') for w in words):
            continue
        is_bold = bool(_BOLD_RE.search(stripped))
        clean = _BOLD_RE.sub(lambda m: m.group(1), stripped).strip()
        clean = _EMOJI_RE.sub('', clean).strip()
        if clean:
            blocks.append((clean, is_bold, False))
    return blocks


def _paginate_blocks(blocks: list) -> list:
    """将 blocks 分页，返回 list[list[block]]。"""
    body_font = _get_font(_BASE_FONT_SIZE, bold=False)
    body_font_bold = _get_font(_BASE_FONT_SIZE + LAYOUT["bold_extra"], bold=True)
    render_blocks = []
    for para_text, is_bold, is_sep in blocks:
        if is_sep:
            render_blocks.append(('__separator__', False, 0))
            continue
        font = body_font_bold if is_bold else body_font
        wrapped = _wrap_text(para_text, font, _MAX_TEXT_W)
        render_blocks.append((wrapped, is_bold, len(wrapped)))

    y_start = LAYOUT["page_top"]
    y_end = COVER_HEIGHT - LAYOUT["page_bottom_margin"]
    usable_height = y_end - y_start
    sep_height = int(_LINE_HEIGHT * LAYOUT["separator_height_ratio"])

    pages = []
    current_page = []
    current_height = 0
    for item in render_blocks:
        tag, is_bold, line_count = item
        if tag == '__separator__':
            if current_height + sep_height > usable_height and current_page:
                pages.append(current_page)
                current_page = []
                current_height = 0
            current_page.append(('__separator__', False, 0))
            current_height += sep_height
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


def _calc_page_height(page_blocks: list) -> int:
    """计算一页 blocks 的实际渲染高度。"""
    h = 0
    sep_height = int(_LINE_HEIGHT * LAYOUT["separator_height_ratio"])
    for i, (tag, is_bold, line_count) in enumerate(page_blocks):
        if tag == '__separator__':
            h += sep_height
        else:
            if i > 0 and page_blocks[i - 1][0] != '__separator__':
                h += _PARA_SPACING
            h += line_count * _LINE_HEIGHT
    return h


def generate_inner_page(text: str, page_num: int, total_pages: int, style: str = "warm_grey",
                        output_path: str = "assets/inner_page.png",
                        pre_parsed_blocks: list | None = None,
                        pre_paginated_pages: list | None = None) -> str | None:
    """把单页文字渲染成小红书风格内页图。"""
    p = PALETTE.get(style, PALETTE["warm_grey"])
    cover_accent = p.get("cover_accent", p["accent"])

    img = Image.new("RGBA", (COVER_WIDTH, COVER_HEIGHT), (*p["bg_top"], 255))
    _draw_gradient_bg(img, COVER_WIDTH, COVER_HEIGHT, p["bg_top"], p["bg_bottom"])
    img = _add_center_glow(img, p)
    img = _add_noise_texture(img, intensity=3)
    draw = ImageDraw.Draw(img)

    text = text.strip()
    if not text:
        return None

    if pre_paginated_pages is not None:
        pages = pre_paginated_pages
    else:
        blocks = pre_parsed_blocks if pre_parsed_blocks is not None else _parse_to_blocks(text)
        if not blocks:
            return None
        pages = _paginate_blocks(blocks)

    if not pages or page_num > len(pages):
        return None
    page_blocks = pages[page_num - 1]

    x_start = LAYOUT["margin_left"]
    base_font_size = _BASE_FONT_SIZE
    line_height = _LINE_HEIGHT
    para_spacing = _PARA_SPACING
    body_font = _get_font(base_font_size, bold=False)
    body_font_bold = _get_font(base_font_size + LAYOUT["bold_extra"], bold=True)
    y_start = LAYOUT["page_top"]
    y_limit = COVER_HEIGHT - LAYOUT["page_bottom_margin"]

    y = y_start
    anchor_idx = (page_num - 1) % len(ANCHOR_SYMBOLS)

    # 顶部装饰细线
    draw.rectangle(
        [(x_start, y_start - 30), (x_start + 80, y_start - 28)],
        fill=(*cover_accent, 40),
    )

    # 左侧装饰竖线（底部渐隐）
    stripe_w = 6
    stripe_x = x_start - 18
    stripe_full_end = y_limit - 40
    draw.rectangle(
        [(stripe_x, y_start), (stripe_x + stripe_w, stripe_full_end)],
        fill=(*cover_accent, 60),
    )
    # 底部渐隐
    fade_h = 40
    for dy in range(fade_h):
        alpha = int(60 * (1.0 - dy / fade_h))
        y_pos = stripe_full_end + dy
        draw.rectangle(
            [(stripe_x, y_pos), (stripe_x + stripe_w, y_pos + 1)],
            fill=(*cover_accent, alpha),
        )

    bg_top = p["bg_top"]
    accent = p["accent"]
    highlight_bg = (
        int(cover_accent[0] * 0.40 + bg_top[0] * 0.60),
        int(cover_accent[1] * 0.40 + bg_top[1] * 0.60),
        int(cover_accent[2] * 0.40 + bg_top[2] * 0.60),
    )

    actual_para_spacing = para_spacing
    if LAYOUT["last_page_expand"] and page_num == total_pages:
        raw_height = _calc_page_height(page_blocks)
        usable_height = y_limit - y_start
        remaining = usable_height - raw_height
        text_block_count = sum(1 for b in page_blocks if b[0] != '__separator__')
        if text_block_count > 1 and remaining > 0:
            actual_para_spacing = para_spacing + remaining // text_block_count

    text_block_indices = [i for i, b in enumerate(page_blocks) if b[0] != '__separator__']
    anchor_allowed = set(text_block_indices[:LAYOUT["anchor_max_per_page"]])

    after_sep_or_first = True

    for block_idx, block in enumerate(page_blocks):
        if y >= y_limit:
            logger.warning("第 %d 页内容溢出 (y=%d >= %d)，截断剩余 %d 个 block",
                           page_num, y, y_limit, len(page_blocks) - block_idx)
            break

        tag, is_bold, line_count = block
        if tag == '__separator__':
            sep_height = int(line_height * LAYOUT["separator_height_ratio"])
            # 粗分割线 + 小圆点
            draw.rectangle(
                [(x_start, y + sep_height // 2 - 1), (x_start + 120, y + sep_height // 2 + 1)],
                fill=(*cover_accent, 180),
            )
            dot_r = 5
            dot_cx = x_start + 140
            dot_cy = y + sep_height // 2
            draw.ellipse(
                [(dot_cx - dot_r, dot_cy - dot_r), (dot_cx + dot_r, dot_cy + dot_r)],
                fill=(*cover_accent, 200),
            )
            y += sep_height + actual_para_spacing
            after_sep_or_first = True
            continue

        font = body_font_bold if is_bold else body_font

        last_text_idx = max((i for i, b in enumerate(page_blocks) if b[0] != '__separator__'), default=-1)
        is_last_text_block = (block_idx == last_text_idx)
        is_last_page = (page_num == total_pages)
        is_short = line_count <= 2 and sum(len(line) for line in tag) <= LAYOUT["last_block_max_chars"]

        # 最后一页最后一段：金句放大
        if is_last_page and is_last_text_block and is_short:
            decor_y = y - 20
            draw.rectangle(
                [((COVER_WIDTH - 80) // 2, decor_y), ((COVER_WIDTH + 80) // 2, decor_y + 3)],
                fill=(*cover_accent, 200),
            )
            y = decor_y + 30

            large_size = base_font_size + LAYOUT["last_block_font_boost"]
            large_font = _get_font(large_size, bold=True)
            large_lines = _wrap_text('\n'.join(tag), large_font, _MAX_TEXT_W)
            large_line_h = int(large_size * LAYOUT["line_height_ratio"])
            for line in large_lines:
                try:
                    bbox = large_font.getbbox(line)
                    lw = bbox[2] - bbox[0]
                except (AttributeError, TypeError):
                    lw = 0
                x = (COVER_WIDTH - lw) // 2
                draw.text((x, y), line, font=large_font, fill=p["highlight"])
                y += large_line_h
            y += actual_para_spacing
            continue

        # 加粗文字 — 左侧色块高亮
        if is_bold:
            max_line_w = 0
            for line in tag:
                try:
                    bbox = font.getbbox(line)
                    lw = bbox[2] - bbox[0]
                except (AttributeError, TypeError):
                    lw = 0
                max_line_w = max(max_line_w, lw)
            block_h = line_count * line_height
            pad_x = 20
            pad_y = 12
            rect_x1 = x_start - pad_x
            rect_y1 = y - pad_y
            rect_x2 = x_start + max_line_w + pad_x
            rect_y2 = y + block_h + pad_y
            rect_x2 = min(rect_x2, COVER_WIDTH - 60)
            draw.rectangle(
                [(rect_x1, rect_y1), (rect_x2, rect_y2)],
                fill=highlight_bg,
            )
            # 左侧色条
            draw.rectangle(
                [(rect_x1, rect_y1), (rect_x1 + 5, rect_y2)],
                fill=(*cover_accent, 200),
            )

        use_anchor = block_idx in anchor_allowed and not (is_last_page and is_last_text_block)

        dot_size = int(base_font_size * 0.48)
        dot_radius = dot_size // 2

        if is_bold:
            text_color = p["highlight"]
        elif after_sep_or_first:
            text_color = p["title"]
        else:
            text_color = p["body"]

        for i, line in enumerate(tag):
            if y >= y_limit:
                break
            if i == 0 and use_anchor:
                dot_x = x_start + dot_radius
                dot_y_center = y + dot_radius
                anchor_sym = ANCHOR_SYMBOLS[anchor_idx]
                if anchor_sym == "●":
                    draw.ellipse(
                        [(dot_x - dot_radius, dot_y_center - dot_radius),
                         (dot_x + dot_radius, dot_y_center + dot_radius)],
                        fill=cover_accent,
                    )
                else:
                    draw.ellipse(
                        [(dot_x - dot_radius, dot_y_center - dot_radius),
                         (dot_x + dot_radius, dot_y_center + dot_radius)],
                        outline=cover_accent,
                        width=2,
                    )
                anchor_x = x_start + dot_size + int(base_font_size * 0.5)
            else:
                anchor_x = x_start

            draw.text((anchor_x, y), line, font=font, fill=text_color)
            y += line_height

        y += actual_para_spacing
        after_sep_or_first = False

    # 页码
    page_font = _get_font(LAYOUT["page_number_font_size"])
    page_text = f"— {page_num} / {total_pages} —"
    try:
        bbox = page_font.getbbox(page_text)
        tw = bbox[2] - bbox[0]
    except (AttributeError, TypeError):
        tw = 0
    page_y = COVER_HEIGHT - LAYOUT["page_number_y_offset"]

    # 页码上方装饰线 + 两侧小圆点
    deco_y = page_y - 18
    deco_w = 50
    draw.rectangle(
        [((COVER_WIDTH - deco_w) // 2, deco_y), ((COVER_WIDTH + deco_w) // 2, deco_y + 2)],
        fill=(*cover_accent, 140),
    )
    for side in (-1, 1):
        dot_cx = (COVER_WIDTH + side * (deco_w + 12)) // 2
        draw.ellipse(
            [(dot_cx - 2, deco_y - 1), (dot_cx + 2, deco_y + 3)],
            fill=(*cover_accent, 100),
        )

    draw.text(((COVER_WIDTH - tw) // 2, page_y), page_text, font=page_font, fill=p["subtitle"])

    final = img.convert("RGB")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    final.save(output_path, quality=95)
    logger.info("内页图已保存: %s", output_path)
    return output_path


def generate_inner_pages(content: str, out_dir: str, style: str = "warm_grey") -> list[str]:
    """解析笔记正文，生成所有内页图。"""
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
    body = re.split(r'\n\s*(?:\*?【金句】\*?|#{1,6}\s*\[?金句\]?)', body, maxsplit=1)[0]

    blocks = _parse_to_blocks(body)

    if not blocks:
        logger.warning("正文解析后无有效内容，跳过内页生成")
        return []

    pages = _paginate_blocks(blocks)
    total_pages = len(pages)
    if total_pages == 0:
        logger.warning("分页后无内容，跳过内页生成")
        return []

    logger.info("📄 共 %d 页内页，开始生成...", total_pages)

    def _render_page(page_num: int) -> str | None:
        path = f"{out_dir}/inner_page_{page_num}.png"
        return generate_inner_page(body, page_num, total_pages, style=style,
                                   output_path=path, pre_parsed_blocks=blocks,
                                   pre_paginated_pages=pages)

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
