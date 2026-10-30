#!/usr/bin/env python3
"""
产品 PDF 构建脚本 — 把 products/ 下的 markdown 产品渲染成可上架 PDF
====================================================================

产物（输出到 products/dist/）：
  1. 9to5-ai-workflow-kit-en.pdf      英文全套（10 工作流 + 速查表 + 封面页）
  2. workflow-01-free-sample-en.pdf   英文免费样张（单独上架 Gumroad $0+）
  3. dagongren-ai-kit-cn.pdf          中文全套（面包多上架）
  4. 9to5-kit-en-bundle.zip           英文交付包（PDF + 全部 .md 源文件）

用法:
    python products/build_pdfs.py            # 构建全部
    python products/build_pdfs.py --cn       # 只构建中文版

    python products/build_pdfs.py --check    # 仅检查路径，不导入渲染器、不生成文件

依赖: pymupdf、markdown2、共享字体 capabilities/_shared/fonts/NotoSansSC-{Regular,Bold}.ttf
"""

import argparse
import sys
import zipfile
from pathlib import Path
from string import Template

CASE = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[3]
KIT_DIR = CASE / "products" / "ai-office-workflows"
DIST_DIR = CASE / "products" / "dist"
FONT_REG = REPO / "capabilities" / "_shared" / "fonts" / "NotoSansSC-Regular.ttf"
FONT_BOLD = FONT_REG.with_name("NotoSansSC-Bold.ttf")

CSS = Template("""
@font-face { font-family: noto; src: url("$font_regular"); }
@font-face { font-family: noto; src: url("$font_bold"); font-weight: bold; }
body { font-family: noto; font-size: 10.5pt; line-height: 1.55; color: #1a1a1a; }
h1 { font-size: 22pt; color: #1a1a1a; margin-bottom: 4pt; }
h2 { font-size: 15pt; color: #c0392b; margin-top: 14pt; }
h3 { font-size: 12pt; color: #333333; margin-top: 10pt; }
p  { margin-top: 4pt; }
pre { background-color: #f5f2ec; font-size: 9.5pt; padding: 8pt; margin-top: 6pt; }
code { font-family: noto; background-color: #f5f2ec; font-size: 9.5pt; }
blockquote { color: #666666; margin-left: 12pt; }
table { font-size: 9.5pt; }
th { color: #666666; }
li { margin-top: 2pt; }
hr { color: #cccccc; }
.cover-title { font-size: 34pt; font-weight: bold; color: #1a1a1a; }
.cover-sub   { font-size: 15pt; color: #c0392b; }
.cover-meta  { font-size: 10pt; color: #666666; }
""").substitute(font_regular=FONT_REG.as_posix(), font_bold=FONT_BOLD.as_posix())


def check_paths() -> None:
    """只检查本地路径，失败时必须早于任何输出文件创建。"""
    missing = [str(font) for font in (FONT_REG, FONT_BOLD) if not font.is_file()]
    if not KIT_DIR.is_dir():
        missing.append(str(KIT_DIR))
    if missing:
        raise FileNotFoundError("缺少构建路径: " + "; ".join(missing))


def md_to_html(md_path: Path) -> str:
    import markdown2

    text = md_path.read_text(encoding="utf-8")
    return markdown2.markdown(text, extras=["tables", "fenced-code-blocks", "strike"])


def cover(title: str, sub: str, meta: str) -> str:
    return (
        f'<p class="cover-title">{title}</p>'
        f'<p class="cover-sub">{sub}</p>'
        f'<p class="cover-meta">{meta}</p><hr>'
    )


def render_pdf(html: str, out_path: Path) -> None:
    check_paths()
    import pymupdf as fitz

    story = fitz.Story(html=html, user_css=CSS, archive=fitz.Archive(str(REPO)))
    writer = fitz.DocumentWriter(str(out_path))
    mediabox = fitz.paper_rect("a4")
    where = mediabox + (42, 42, -42, -42)
    more = 1
    while more:
        device = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()
    # 显式释放 story/writer 句柄（Windows 下 GC 前 hold 文件锁，替换会 PermissionError）
    import gc
    del story, writer, device
    gc.collect()
    # 字体子集化 + 压缩（否则每份 PDF 全量嵌入 ~20MB 思源黑体）
    doc = fitz.open(out_path)
    doc.subset_fonts()
    tmp_path = out_path.with_suffix(".tmp.pdf")
    doc.save(tmp_path, garbage=4, deflate=True, clean=True)
    doc.close()
    # Windows 句柄释放有滞后，重试替换；目标被锁则先删再换
    import time
    for attempt in range(5):
        try:
            tmp_path.replace(out_path)
            break
        except PermissionError:
            try:
                out_path.unlink(missing_ok=True)
                tmp_path.replace(out_path)
                break
            except PermissionError:
                time.sleep(0.5 * (attempt + 1))
    else:
        raise RuntimeError(f"无法替换 {out_path}（文件被占用，请关闭 PDF 阅读器后重跑）")


def delivery_sources() -> list[Path]:
    """返回允许进入商品包的产品源稿；上架、推广、QA 草稿一律排除。"""
    workflows = []
    for i in range(1, 11):
        matches = sorted(KIT_DIR.glob(f"workflow-{i:02d}-*.md"))
        if len(matches) != 1 or not matches[0].is_file():
            raise ValueError(f"workflow {i:02d}: expected exactly one source file")
        workflows.append(matches[0])
    cheat_sheet = KIT_DIR / "anti-bs-cheat-sheet.md"
    if not cheat_sheet.is_file():
        raise FileNotFoundError(cheat_sheet)
    return [*workflows, cheat_sheet]


def build_en() -> None:
    # 只交付明确的产品源文件，禁止把内部上架、推广、QA草稿打进商品包。
    sources = delivery_sources()
    workflow_files = sources[:10]

    # 全套：封面 + 01-10 + 速查表
    parts = [cover(
        "The 9-to-5 AI Workflow Kit",
        "Prompts are free. Knowing when the AI is lying to you isn't.",
        "10 workflows + the Anti-BS Cheat Sheet · v1.0 · 2026 · Personal license",
    )]
    parts.extend(md_to_html(f) for f in sources)
    render_pdf("".join(parts), DIST_DIR / "9to5-ai-workflow-kit-en.pdf")
    print("OK  dist/9to5-ai-workflow-kit-en.pdf")

    # 免费样张：封面信息 + workflow-01
    sample = cover(
        "The 9-to-5 AI Workflow Kit — Free Sample",
        "Workflow 01: The weekly update that writes itself",
        "Full kit: 10 workflows + cheat sheet — link at the end of this PDF",
    ) + md_to_html(workflow_files[0])
    render_pdf(sample, DIST_DIR / "workflow-01-free-sample-en.pdf")
    print("OK  dist/workflow-01-free-sample-en.pdf")

    # 交付包：PDF + 已验证清单中的11份产品源稿（Gumroad 上传单文件）
    zip_path = DIST_DIR / "9to5-kit-en-bundle.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(DIST_DIR / "9to5-ai-workflow-kit-en.pdf", "9to5-ai-workflow-kit.pdf")
        for f in sources:
            z.write(f, f"markdown/{f.name}")
    print("OK  dist/9to5-kit-en-bundle.zip")


def build_cn() -> None:
    html = cover(
        "打工人 AI 提效工作流包",
        "整理材料，也核对事实、责任与时间。",
        "10 个工作流 + 人工核查 · v1.1 待复测稿 · 2026 · 非已验收交付",
    ) + md_to_html(KIT_DIR / "kit-cn-打工人AI提效工作流包.md")
    render_pdf(html, DIST_DIR / "dagongren-ai-kit-cn.pdf")
    print("OK  dist/dagongren-ai-kit-cn.pdf")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cn", action="store_true", help="只构建中文版")
    parser.add_argument("--check", action="store_true", help="仅检查路径，不生成交付文件")
    args = parser.parse_args(argv)
    try:
        check_paths()
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.check:
        for path in (KIT_DIR, FONT_REG, FONT_BOLD):
            print(f"OK  {path}")
        return 0
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    build_cn()
    if not args.cn:
        build_en()
    # 体积报告
    for f in sorted(DIST_DIR.iterdir()):
        print(f"    {f.name:42s} {f.stat().st_size / 1024:8.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
