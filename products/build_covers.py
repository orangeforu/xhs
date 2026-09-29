#!/usr/bin/env python3
"""生成产品封面图（Gumroad 1280x720 + 面包多 800x800），风格延续产品 PDF：米白底/墨色大字/红点缀"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent.parent
DIST = ROOT / "products" / "dist"
FONT_BOLD = str(ROOT / "assets" / "fonts" / "NotoSansSC-Bold.ttf")
FONT_REG = str(ROOT / "assets" / "fonts" / "NotoSansSC-Regular.ttf")

INK = (26, 26, 26)
RED = (192, 57, 43)
CREAM = (255, 253, 249)
DIM = (102, 102, 102)


def cover_en(path: str, w: int, h: int) -> None:
    img = Image.new("RGB", (w, h), CREAM)
    d = ImageDraw.Draw(img)
    pad = int(w * 0.07)
    f_kicker = ImageFont.truetype(FONT_BOLD, int(w * 0.022))
    f_title = ImageFont.truetype(FONT_BOLD, int(w * 0.085))
    f_tag = ImageFont.truetype(FONT_REG, int(w * 0.036))
    f_meta = ImageFont.truetype(FONT_REG, int(w * 0.024))

    d.text((pad, pad), "FOR OPS / PM / ADMIN / FINANCE", font=f_kicker, fill=RED)
    d.text((pad, int(h * 0.16)), "The 9-to-5", font=f_title, fill=INK)
    d.text((pad, int(h * 0.16 + w * 0.105)), "AI Workflow Kit", font=f_title, fill=INK)
    d.text((pad, int(h * 0.60)), "Prompts are free.", font=f_tag, fill=DIM)
    d.text((pad, int(h * 0.60 + w * 0.055)), "Knowing when the AI is lying to you isn't.", font=f_tag, fill=DIM)
    d.text((pad, int(h * 0.88)), "10 workflows + the Anti-BS Cheat Sheet", font=f_meta, fill=INK)
    d.rectangle([pad, int(h * 0.845), pad + int(w * 0.09), int(h * 0.855)], fill=RED)
    img.save(DIST / path)


def cover_cn(path: str, w: int, h: int) -> None:
    img = Image.new("RGB", (w, h), CREAM)
    d = ImageDraw.Draw(img)
    pad = int(w * 0.07)
    f_kicker = ImageFont.truetype(FONT_BOLD, int(w * 0.026))
    f_title = ImageFont.truetype(FONT_BOLD, int(w * 0.105))
    f_tag = ImageFont.truetype(FONT_BOLD, int(w * 0.052))
    f_meta = ImageFont.truetype(FONT_REG, int(w * 0.030))

    d.text((pad, pad), "打工人自救系列", font=f_kicker, fill=RED)
    d.text((pad, int(h * 0.14)), "打工人", font=f_title, fill=INK)
    d.text((pad, int(h * 0.14 + w * 0.13)), "AI 提效", font=f_title, fill=INK)
    d.text((pad, int(h * 0.14 + w * 0.26)), "工作流包", font=f_title, fill=INK)
    d.text((pad, int(h * 0.70)), "AI 编的不是内容，是因果。", font=f_tag, fill=RED)
    d.text((pad, int(h * 0.88)), "10 个工作流 + 通用防坑五条", font=f_meta, fill=INK)
    d.rectangle([pad, int(h * 0.845), pad + int(w * 0.09), int(h * 0.855)], fill=RED)
    img.save(DIST / path)


if __name__ == "__main__":
    DIST.mkdir(parents=True, exist_ok=True)
    cover_en("cover-en-1280x720.png", 1280, 720)
    cover_en("thumb-en-600x600.png", 600, 600)
    cover_cn("cover-cn-800x800.png", 800, 800)
    print("OK  cover-en-1280x720.png / thumb-en-600x600.png / cover-cn-800x800.png -> products/dist/")
