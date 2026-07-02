"""图片生成 — 向后兼容入口。

所有实现已拆分到 core.image 子包：
  - core.image.render   — 共享渲染工具（字体、渐变、排版常量）
  - core.image.cover    — 封面生成（AI 绘画 + 模板合成）
  - core.image.inner_page — 内页生成（分页、解析、渲染）

本文件仅做 re-export，保持 `from core.image_generator import ...` 不变。
"""

# 重新导出所有公开 API
from core.image.render import (  # noqa: F401
    COVER_WIDTH, COVER_HEIGHT, LAYOUT, PALETTE,
    FONT_REGULAR, FONT_BOLD,
    _get_font, _wrap_text, _draw_gradient_bg, _add_center_glow, _add_noise_texture,
    _calc_font_size,
    _BASE_FONT_SIZE, _LINE_HEIGHT, _PARA_SPACING, _MAX_TEXT_W,
)
from core.image.cover import (  # noqa: F401
    generate_cover_template, generate_cover_ai, generate_all_covers,
    _http_get_with_retry,
)
from core.image.inner_page import (  # noqa: F401
    generate_inner_page, generate_inner_pages,
    _paginate_blocks, _calc_page_height, _parse_to_blocks,
    _SKIP_MARKERS, _EMOJI_RE, _BOLD_RE,
)

# __main__ 入口保持不变
if __name__ == "__main__":
    from core.config import get_logger
    logger = get_logger(__name__)

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
