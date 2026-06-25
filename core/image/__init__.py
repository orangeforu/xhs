"""图片生成包 — 封面 + 内页渲染。

为了向后兼容，所有公开 API 从子模块重新导出。
外部代码应继续使用 `from core.image_generator import ...`。
"""

from core.image.render import (
    COVER_WIDTH, COVER_HEIGHT, LAYOUT, PALETTE, FONT_REGULAR, FONT_BOLD,
    _get_font, _wrap_text, _draw_gradient_bg, _add_center_glow, _add_noise_texture,
    _calc_font_size,
    _BASE_FONT_SIZE, _LINE_HEIGHT, _PARA_SPACING, _MAX_TEXT_W,
)
from core.image.cover import (
    generate_cover_template, generate_cover_ai, generate_all_covers,
    _http_get_with_retry,
)
from core.image.inner_page import (
    generate_inner_page, generate_inner_pages,
    _paginate_blocks, _calc_page_height, _parse_to_blocks,
    ANCHOR_SYMBOLS, _SKIP_MARKERS, _EMOJI_RE, _BOLD_RE,
)

__all__ = [
    "COVER_WIDTH", "COVER_HEIGHT", "LAYOUT", "PALETTE",
    "generate_cover_template", "generate_cover_ai", "generate_all_covers",
    "generate_inner_page", "generate_inner_pages",
]
