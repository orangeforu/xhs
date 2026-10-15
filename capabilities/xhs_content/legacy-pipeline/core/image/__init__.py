"""图片生成包 — 封面 + 内页渲染。

公开 API（稳定入口，外部代码优先用 ``from core.image import ...``）：
  - generate_cover_template / generate_cover_ai / generate_all_covers
  - generate_inner_page / generate_inner_pages
  - COVER_WIDTH / COVER_HEIGHT / LAYOUT / PALETTE

字体、渐变、分页解析等内部实现细节（``_get_font`` / ``_wrap_text`` /
``_paginate_blocks`` 等）不在此 re-export，请直接从对应子模块导入。

历史入口 ``core.image_generator`` 仍保留作为兼容壳，但它已退化为薄封装层。
"""

from core.image.render import COVER_WIDTH, COVER_HEIGHT, LAYOUT, PALETTE
from core.image.cover import (
    generate_cover_template,
    generate_cover_ai,
    generate_all_covers,
)
from core.image.inner_page import generate_inner_page, generate_inner_pages

__all__ = [
    "COVER_WIDTH",
    "COVER_HEIGHT",
    "LAYOUT",
    "PALETTE",
    "generate_cover_template",
    "generate_cover_ai",
    "generate_all_covers",
    "generate_inner_page",
    "generate_inner_pages",
]
