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

_SKIP_MARKERS = ['【金句】', '【互动钩子】', '【话题标签】', '【视觉风格】', '【标题候选】', '【封面页】', '【正文】']
_EMOJI_RE = re.compile(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0001F900-\U0001F9FF\U00002600-\U000026FF]+")
_BOLD_RE = re.compile(r'\*\*(.*?)\*\*')

# ── 对话气泡识别（D-05）──
# 主角方角色 → 右气泡；其余（对方）→ 左气泡
_BUBBLE_ROLES_RIGHT = {"她", "我", "女生", "女友", "老婆", "妈妈"}
_BUBBLE_RE = re.compile(
    r'^(她|他|我|妈妈|男生|女生|对方|前任|男友|女友|老公|老婆|爸爸|妈妈|爸|妈|闺蜜|朋友|同事|老板|领导|客户|舍友|室友)[：:]\s*(.*)$'
)


def _parse_bubble(text: str):
    """识别"角色：内容"格式的对话行，返回 (side, speaker, content) 或 None。"""
    m = _BUBBLE_RE.match(text)
    if not m:
        return None
    speaker = m.group(1)
    content = m.group(2).strip().strip('"""\'…— ').strip()
    if len(content) < 1:
        return None
    side = "right" if speaker in _BUBBLE_ROLES_RIGHT else "left"
    return (side, speaker, content)


def _parse_to_blocks(text: str) -> list:
    """解析文本为 block 列表：(text, is_bold, is_separator, side)。

    连续的叙述短句合并为一个段落（紧凑渲染，避免"每句一行散开"）；
    加粗金句、对话行、空行、--- 各自分段。向后兼容 3 元组访问。
    """
    blocks = []
    current_lines = []

    def _flush():
        if not current_lines:
            return
        para = '\n'.join(current_lines)
        clean = _BOLD_RE.sub(lambda m: m.group(1), para).strip()
        clean = _EMOJI_RE.sub('', clean).strip()
        if clean:
            blocks.append((clean, False, False, None))
        current_lines.clear()

    for raw in text.split('\n'):
        stripped = raw.strip()
        if not stripped:
            _flush()  # 空行 → 段落分隔
            continue
        if stripped == '---':
            _flush()
            blocks.append(('', False, True, None))
            continue
        if any(m in stripped for m in _SKIP_MARKERS):
            continue
        if re.match(r'^话题标签[：:]', stripped) or re.match(r'^视觉风格[：:]', stripped):
            continue
        if re.match(r'\[Image\s*#\d+\]', stripped) or re.match(r'^[（(]第?\d+页[）)]', stripped) or re.match(r'^第\d+页', stripped):
            continue
        if stripped in ('warm_grey', 'twilight', 'crimson', 'mist', 'cool', 'warm', 'blank'):
            continue
        words = stripped.split()
        if words and all(w.startswith('#') for w in words):
            continue
        clean_line = _BOLD_RE.sub(lambda m: m.group(1), stripped).strip()
        clean_line = _EMOJI_RE.sub('', clean_line).strip()
        if not clean_line:
            continue
        # 加粗金句单独成段（不与叙述合并，保留高亮/放大）
        if _BOLD_RE.search(stripped):
            _flush()
            blocks.append((clean_line, True, False, None))
            continue
        # 对话行（角色：内容）单独成段
        bubble = _parse_bubble(clean_line)
        if bubble:
            _flush()
            blocks.append((clean_line, False, False, bubble[0]))
            continue
        current_lines.append(clean_line)
    _flush()
    return blocks


def _paginate_blocks(blocks: list) -> list:
    """将 blocks 分页，返回 list[list[block]]。兼容 3 元组与 4 元组（含气泡 side）。

    超长段落会自动跨页分割，避免硬截断。
    """
    body_font = _get_font(_BASE_FONT_SIZE, bold=False)
    body_font_bold = _get_font(_BASE_FONT_SIZE + LAYOUT["bold_extra"], bold=True)
    bubble_pad = LAYOUT.get("bubble_pad_y", 28)  # 气泡上下内边距总高

    y_start = LAYOUT["page_top"]
    y_end = COVER_HEIGHT - LAYOUT["page_bottom_margin"]
    usable_height = y_end - y_start
    sep_height = int(_LINE_HEIGHT * LAYOUT["separator_height_ratio"])

    # 预计算每个 block 的换行结果和高度
    render_blocks = []
    for block in blocks:
        para_text, is_bold, is_sep = block[0], block[1], block[2]
        side = block[3] if len(block) >= 4 else None
        if is_sep:
            render_blocks.append(('__separator__', False, 0, None, 0))
            continue
        font = body_font_bold if is_bold else body_font
        wrap_width = int(_MAX_TEXT_W * 0.72) if side else _MAX_TEXT_W
        wrapped = _wrap_text(para_text, font, wrap_width)
        line_count = len(wrapped)
        block_height = line_count * _LINE_HEIGHT + (bubble_pad if side else 0)
        render_blocks.append((wrapped, is_bold, line_count, side, block_height))

    pages = []
    current_page = []
    current_height = 0

    for item in render_blocks:
        tag, is_bold, line_count, side, block_height = item

        if tag == '__separator__':
            # LLM 用 `---` 主动分页 → 尊重其语义决策，强制分页
            # separator 本身不占用页面空间（它只是分页符，不是内容）
            if current_page:
                pages.append(current_page)
                current_page = []
                current_height = 0
            continue

        # 超长段落跨页分割
        # 单页可容纳的最大行数（每个 block 后都加 _PARA_SPACING，包括最后一个，与渲染层一致）
        max_lines_per_page = int((usable_height - _PARA_SPACING - (bubble_pad if side else 0)) // _LINE_HEIGHT)
        if line_count > max_lines_per_page:
            # 段落太长，需要分割到多页
            lines = tag if isinstance(tag, list) else [tag]
            start_idx = 0
            while start_idx < line_count:
                # 计算当前页还能放多少行
                if current_page:
                    # 已有内容 → 当前 block 前需要加 _PARA_SPACING
                    remaining_height = usable_height - current_height - _PARA_SPACING
                else:
                    # 空页 → 第一个 block 后才加 _PARA_SPACING
                    remaining_height = usable_height - _PARA_SPACING
                lines_this_page = min(int(remaining_height // _LINE_HEIGHT), line_count - start_idx)
                if lines_this_page <= 0 or lines_this_page > max_lines_per_page:
                    # 当前页已满或计算异常，开新页
                    if current_page:
                        pages.append(current_page)
                        current_page = []
                        current_height = 0
                    lines_this_page = max_lines_per_page

                end_idx = start_idx + lines_this_page
                page_lines = lines[start_idx:end_idx]
                partial_height = lines_this_page * _LINE_HEIGHT + (bubble_pad if side else 0) + _PARA_SPACING

                current_page.append((page_lines, is_bold, lines_this_page, side))
                current_height += partial_height
                start_idx = end_idx

                # 如果还有剩余行，开启新页
                if start_idx < line_count:
                    pages.append(current_page)
                    current_page = []
                    current_height = 0
        else:
            # 正常段落
            if current_page:
                block_height += _PARA_SPACING
            if current_height + block_height > usable_height and current_page:
                pages.append(current_page)
                current_page = []
                current_height = 0
                block_height = line_count * _LINE_HEIGHT + (bubble_pad if side else 0)
            current_page.append((tag, is_bold, line_count, side))
            current_height += block_height

    if current_page:
        pages.append(current_page)

    # 相邻极短页合并：LLM 有时把行动句/短句单独用 --- 分页，产生"孤页"
    # 如果前后两页合并后高度不超过可用高度，就合并
    if len(pages) >= 2:
        short_page_lines = 3  # ≤3 行的页面算"极短页"
        merged_pages = []
        i = 0
        while i < len(pages):
            page = pages[i]
            page_lines = sum(b[2] for b in page if b[0] != '__separator__')
            if page_lines <= short_page_lines and i > 0:
                # 尝试合并到前一页
                prev = merged_pages[-1]
                combined = prev + [b for b in page if b[0] != '__separator__']
                combined_h = _calc_page_height(combined)
                if combined_h <= usable_height:
                    merged_pages[-1] = combined
                    i += 1
                    continue
            merged_pages.append(page)
            i += 1
        pages = merged_pages

    return pages


def _calc_page_height(page_blocks: list) -> int:
    """计算一页 blocks 的实际渲染高度。"""
    h = 0
    sep_height = int(_LINE_HEIGHT * LAYOUT["separator_height_ratio"])
    bubble_pad = LAYOUT.get("bubble_pad_y", 28)
    for i, block in enumerate(page_blocks):
        tag = block[0]
        line_count = block[2]
        side = block[3] if len(block) >= 4 else None
        if tag == '__separator__':
            h += sep_height
        else:
            h += line_count * _LINE_HEIGHT + (bubble_pad if side else 0)
        h += _PARA_SPACING  # 渲染每 block 后都加 spacing（含最后），对齐渲染层
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

    # 高级感由背景渐变+光晕+留白+文字层次承担，不加任何装饰符号
    bg_top = p["bg_top"]
    accent = p["accent"]
    highlight_bg = (
        int(cover_accent[0] * 0.40 + bg_top[0] * 0.60),
        int(cover_accent[1] * 0.40 + bg_top[1] * 0.60),
        int(cover_accent[2] * 0.40 + bg_top[2] * 0.60),
    )

    actual_para_spacing = para_spacing
    raw_height = _calc_page_height(page_blocks)
    usable_height = y_limit - y_start
    fill_ratio = raw_height / usable_height
    # 短页面自动撑开，避免大片留白（但限制最大间距，防止过度拉伸）
    if fill_ratio < 0.50:
        target_height = int(usable_height * 0.50)
        remaining = target_height - raw_height
        block_count = max(len(page_blocks), 1)
        if remaining > 0:
            extra = min(remaining // block_count, para_spacing)  # 最大 2x
            actual_para_spacing = para_spacing + extra
        # 单 block 短页面：将内容从页顶下移，实现垂直居中
        if len(page_blocks) == 1 and fill_ratio < 0.35:
            y_shift = (usable_height - raw_height - actual_para_spacing) // 3
            y += y_shift

    text_block_indices = [i for i, b in enumerate(page_blocks) if b[0] != '__separator__']
    last_text_idx = text_block_indices[-1] if text_block_indices else -1

    after_sep_or_first = True

    for block_idx, block in enumerate(page_blocks):
        if y >= y_limit:
            logger.warning("第 %d 页内容溢出 (y=%d >= %d)，截断剩余 %d 个 block",
                           page_num, y, y_limit, len(page_blocks) - block_idx)
            break

        tag = block[0]
        is_bold = block[1]
        line_count = block[2]
        side = block[3] if len(block) >= 4 else None
        if tag == '__separator__':
            sep_height = int(line_height * LAYOUT["separator_height_ratio"])
            # 纯留白分页（原粗分割线+圆点被反馈"横杠丑"，已移除，靠留白区分段落）
            y += sep_height + actual_para_spacing
            after_sep_or_first = True
            continue

        # 对话不再渲染为气泡（用户反馈"气泡丑"，回归普通文字）
        font = body_font_bold if is_bold else body_font

        is_last_text_block = (block_idx == last_text_idx)
        is_last_page = (page_num == total_pages)
        is_short = line_count <= 2 and sum(len(line) for line in tag) <= LAYOUT["last_block_max_chars"]

        # 金句海报放大（D-06）：
        # 只在"前面有其他内容垫底"时才放大显示——避免整页一句话时莫名放大
        # 保持左对齐，与页面其他文字一致；仅通过字号+装饰线区分重要度
        has_lead_in = len(text_block_indices) >= 2
        if is_last_text_block and is_short and has_lead_in:
            large_size = base_font_size + LAYOUT["last_block_font_boost"]
            large_font = _get_font(large_size, bold=True)
            large_lines = _wrap_text('\n'.join(tag), large_font, _MAX_TEXT_W)
            large_line_h = int(large_size * LAYOUT["line_height_ratio"])
            for line in large_lines:
                draw.text((x_start, y), line, font=large_font, fill=p["highlight"])
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

        if is_bold:
            text_color = p["highlight"]
        elif after_sep_or_first:
            text_color = p["title"]
        else:
            text_color = p["body"]

        for i, line in enumerate(tag):
            if y >= y_limit:
                break
            draw.text((x_start, y), line, font=font, fill=text_color)
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

    # 页码上方细分隔线
    deco_y = page_y - 18
    deco_w = 40
    draw.rectangle(
        [((COVER_WIDTH - deco_w) // 2, deco_y), ((COVER_WIDTH + deco_w) // 2, deco_y + 1)],
        fill=(*cover_accent, 80),
    )

    draw.text(((COVER_WIDTH - tw) // 2, page_y), page_text, font=page_font, fill=p["subtitle"])

    final = img.convert("RGB")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    final.save(output_path, quality=95)
    logger.info("内页图已保存: %s", output_path)
    return output_path


def generate_inner_pages(content: str, out_dir: str, style: str = "warm_grey") -> list[str]:
    """解析笔记正文，生成所有内页图。"""
    # 正文提取结束标记：【...】或 ## 非【的 markdown 标题（如 ## 封面文件）
    end_pattern = r'(?=\n\s*(?:\*?【|#{1,6}\s*【|#{1,6}\s+[^【\n])|$)'
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

    # 剥离结尾的 CTA 行（"今天就把..."、"来评论区打卡"等行动号召不属于正文内页）
    _CTA_PATTERNS = [
        r'(?:今天|现在|立刻|马上)\w*就把?\w+',
        r'来评论区\w*打卡',
        r'来打卡',
        r'做了的\w*打卡',
        r'评论区\w*见',
        r'试试\w*看',
        r'扣[12].*$',
    ]
    body_lines = body.split('\n')
    while body_lines:
        last = body_lines[-1].strip()
        if not last:
            body_lines.pop()
            continue
        is_cta = any(re.search(p, last) for p in _CTA_PATTERNS)
        if is_cta and len(last) < 30:
            body_lines.pop()
        else:
            break
    body = '\n'.join(body_lines).strip()

    blocks = _parse_to_blocks(body)

    if not blocks:
        logger.warning("正文解析后无有效内容，跳过内页生成")
        return []

    pages = _paginate_blocks(blocks)
    total_pages = len(pages)
    if total_pages == 0:
        logger.warning("分页后无内容，跳过内页生成")
        return []

    # 页面填充率平衡：拆分填充率最高的页，使 max-min 差距 ≤ 30%
    y_start = LAYOUT["page_top"]
    y_limit = COVER_HEIGHT - LAYOUT["page_bottom_margin"]
    usable_height = y_limit - y_start
    for _balance_pass in range(3):  # 最多 3 轮平衡
        page_heights = [_calc_page_height(p) for p in pages]
        if len(page_heights) < 2:
            break
        max_h, min_h = max(page_heights), min(page_heights)
        if max_h <= 0 or (max_h - min_h) / usable_height <= 0.30:
            break
        # 拆分填充率最高的页
        max_idx = page_heights.index(max_h)
        max_page = pages[max_idx]
        text_blocks_in_page = [(i, b) for i, b in enumerate(max_page) if b[0] != '__separator__']
        if len(text_blocks_in_page) < 2:
            break  # 只有 1 个 block，无法拆分
        # 在 block 中间位置切开
        split_pos = text_blocks_in_page[len(text_blocks_in_page) // 2][0]
        first = max_page[:split_pos]
        second = max_page[split_pos:]
        if first and second:
            pages[max_idx:max_idx+1] = [first, second]

    total_pages = len(pages)
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
