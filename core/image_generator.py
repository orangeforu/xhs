"""图片生成 — 向后兼容入口（稳定薄封装）。

所有实现已拆分到 core.image 子包：
  - core.image.render     — 共享渲染工具（字体、渐变、排版常量）
  - core.image.cover      — 封面生成（AI 绘画 + 模板合成）
  - core.image.inner_page — 内页生成（分页、解析、渲染）

本文件仅 re-export 外部真正在用的符号，保持
``from core.image_generator import ...`` 调用不变。需要其它内部细节时
请直接从对应子模块导入（如 ``from core.image.inner_page import _parse_to_blocks``）。
"""

from core.image.render import COVER_WIDTH, COVER_HEIGHT, LAYOUT, PALETTE, _wrap_text
from core.image.cover import (
    generate_cover_template,
    generate_cover_ai,
    generate_all_covers,
)
from core.image.inner_page import (
    generate_inner_page,
    generate_inner_pages,
    _paginate_blocks,
    _parse_to_blocks,
)

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
    # 内部符号：历史上有外部/测试直接从此入口引用，保留兼容
    "_wrap_text",
    "_paginate_blocks",
    "_parse_to_blocks",
]

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
