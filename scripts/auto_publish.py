#!/usr/bin/env python3
"""
自动发布脚本 — 将 approved/ 目录下的笔记发布到小红书创作者平台
===============================================================

用法:
    python scripts/auto_publish.py              # 发布所有待发布笔记
    python scripts/auto_publish.py --dry-run    # 预览模式，不实际发布
    python scripts/auto_publish.py --limit 3    # 最多发布 3 篇

流程:
    1. 读取 docs_agent/approved/ 目录下的笔记
    2. 登录小红书创作者平台（二维码）
    3. 上传封面图和内页图
    4. 发布图文笔记
    5. 移动到 docs_agent/published/
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

# 将项目根目录加入路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.config import get_logger, PROJECT_ROOT as CONF_ROOT

logger = get_logger(__name__)

# ── 导入 Spider_XHS ──
from spider_xhs import XHS_Creator_Apis

# ── 导入 Cookie 持久化工具 ──
from scripts.xhs_auth_helper import get_creator_auth

# ── 废笔记健康检查（防 LLM 思考链泄漏被发布）──
from core.utils import check_note_health


# ═══════════════════════════════════════════════════════════
# 路径配置
# ═══════════════════════════════════════════════════════════

APPROVED_DIR = PROJECT_ROOT / "docs_agent" / "approved"
PUBLISHED_DIR = PROJECT_ROOT / "docs_agent" / "published"


# ═══════════════════════════════════════════════════════════
# 笔记解析
# ═══════════════════════════════════════════════════════════

def extract_title(content: str) -> str:
    """从 note.md 提取标题。"""
    # 匹配 # 标题 或 YAML frontmatter 的 title
    m = re.search(r'^title:\s*(.+?)$', content, re.MULTILINE | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r'^#\s+(.+?)$', content, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return "未命名笔记"


def extract_desc(content: str) -> str:
    """从 note.md 提取正文描述（去掉 frontmatter 和标题）。"""
    # 去掉 YAML frontmatter
    content = re.sub(r'^---\s*\n.*?---\s*\n', '', content, flags=re.DOTALL)
    # 去掉第一个 # 标题
    content = re.sub(r'^#\s+.+?\n', '', content)
    # 去掉 Markdown 图片标记
    content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
    # 去掉特殊标记
    content = re.sub(r'\[.*?\]\(.*?\)', '', content)
    # 取前 500 字作为描述
    desc = content.strip()[:500]
    return desc


def extract_tags(content: str) -> list:
    """从 note.md 提取话题标签。"""
    # 匹配 #标签 格式
    tags = re.findall(r'#(\w+)', content)
    # 去重
    return list(dict.fromkeys(tags))


def parse_note(note_dir: Path) -> dict:
    """解析笔记目录，返回发布所需数据。"""
    note_md = note_dir / "note.md"
    if not note_md.exists():
        logger.warning(f"跳过 {note_dir.name}: 缺少 note.md")
        return None

    with open(note_md, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取信息
    title = extract_title(content)
    desc = extract_desc(content)
    tags = extract_tags(content)

    # 查找图片文件
    cover = note_dir / "cover_ai.png"
    if not cover.exists():
        # 尝试其他封面命名
        for alt in ["cover.png", "cover.jpg", "cover.jpeg"]:
            alt_path = note_dir / alt
            if alt_path.exists():
                cover = alt_path
                break

    inner_pages = sorted([
        p for p in note_dir.iterdir()
        if p.name.startswith("inner_page") and p.suffix.lower() in ('.png', '.jpg', '.jpeg')
    ])

    if not cover.exists():
        logger.warning(f"跳过 {note_dir.name}: 缺少封面图")
        return None

    # 废笔记前置校验：LLM 思考链泄漏/无标签段等异常拒绝发布
    health_issues = check_note_health(content)
    if health_issues:
        logger.warning(f"跳过 {note_dir.name}: 健康检查未过 - {'; '.join(health_issues)}")
        return None

    return {
        "dir": note_dir,
        "title": title,
        "desc": desc,
        "tags": tags,
        "cover": str(cover),
        "images": [str(cover)] + [str(p) for p in inner_pages],
    }


# ═══════════════════════════════════════════════════════════
# 发布逻辑
# ═══════════════════════════════════════════════════════════

def publish_note(api: XHS_Creator_Apis, note: dict, dry_run: bool = False) -> tuple[bool, str | None]:
    """发布单篇笔记，返回 (是否成功, 笔记URL)。"""
    title = note["title"]
    desc = note["desc"]
    tags = note["tags"]
    images = note["images"]

    # 构造话题标签字符串
    tag_str = " ".join([f"#{t}" for t in tags]) if tags else ""
    full_desc = f"{desc}\n\n{tag_str}".strip()

    logger.info(f"{'[预览] ' if dry_run else ''}准备发布: {title}")
    logger.info(f"  封面: {note['cover']}")
    logger.info(f"  内页: {len(images) - 1} 张")
    logger.info(f"  标签: {tags}")

    if dry_run:
        logger.info("  [dry-run] 跳过实际发布")
        return True, None

    try:
        # 发布图文笔记
        success, msg, result = api.post_note({
            "title": title,
            "desc": full_desc,
            "media_type": "image",
            "images": images,
        })

        if success:
            logger.info(f"  ✅ 发布成功: {title}")
            # 提取笔记 URL
            note_url = _extract_note_url_from_result(result, api, title)
            return True, note_url
        else:
            logger.error(f"  ❌ 发布失败: {msg}")
            return False, None
    except Exception as e:
        logger.error(f"  ❌ 发布异常: {e}")
        return False, None


def _extract_note_url_from_result(result: dict, api, title: str) -> str | None:
    """从 post_note 结果或已发布列表中提取笔记 URL。"""
    if not result:
        return None

    # 尝试直接从响应中提取 note_id
    note_id = None
    data = result.get("data", {})
    if isinstance(data, dict):
        for key in ("note_id", "id", "noteId"):
            if key in data:
                note_id = str(data[key])
                break

    # 如果直接提取失败，从已发布列表中按标题匹配
    if not note_id:
        try:
            success, msg, notes = api.get_all_posted_notes()
            if success and notes:
                for n in reversed(notes):
                    note_title = n.get("title", "")
                    if note_title and (title in note_title or note_title in title):
                        note_id = n.get("note_id") or n.get("id")
                        if note_id:
                            break
        except Exception as e:
            logger.warning(f"  从已发布列表获取 note_id 失败: {e}")

    if note_id:
        return f"https://www.xiaohongshu.com/explore/{note_id}"
    return None


def _append_url_to_note_md(note_dir: Path, note_url: str) -> None:
    """将笔记 URL 追加到 note.md 末尾。"""
    note_md = note_dir / "note.md"
    if not note_md.exists():
        return
    try:
        with open(note_md, "a", encoding="utf-8") as f:
            f.write(f"\n\n## 发布记录\n\n")
            f.write(f"**笔记 URL**: {note_url}\n")
            f.write(f"**发布时间**: {datetime.now().isoformat()}\n")
        logger.info(f"  📝 已追加 URL 到 note.md")
    except Exception as e:
        logger.warning(f"  追加 URL 到 note.md 失败: {e}")


def move_to_published(note_dir: Path):
    """将笔记目录移动到 published/。"""
    target = PUBLISHED_DIR / note_dir.name
    # 如果目标已存在，添加序号
    if target.exists():
        i = 1
        while True:
            target = PUBLISHED_DIR / f"{note_dir.name}_{i}"
            if not target.exists():
                break
            i += 1

    shutil.move(str(note_dir), str(target))
    logger.info(f"  📁 已移动到: {target}")


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="自动发布笔记到小红书")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际发布")
    parser.add_argument("--limit", type=int, default=0, help="最多发布数量（0=不限）")
    args = parser.parse_args()

    # 检查目录
    if not APPROVED_DIR.exists():
        logger.error(f"approved/ 目录不存在: {APPROVED_DIR}")
        return

    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)

    # 获取待发布笔记列表
    note_dirs = [d for d in APPROVED_DIR.iterdir() if d.is_dir()]
    if not note_dirs:
        logger.info("approved/ 目录下没有待发布的笔记")
        return

    logger.info(f"发现 {len(note_dirs)} 篇待发布笔记")

    if not args.dry_run:
        # 登录创作者平台（带 Cookie 持久化）
        logger.info("正在登录小红书创作者平台...")
        auth = get_creator_auth()
        api = XHS_Creator_Apis(auth).bootstrap()
        logger.info("登录成功！")
    else:
        api = None

    # 发布笔记
    published_count = 0
    failed_count = 0

    for i, note_dir in enumerate(note_dirs):
        if args.limit > 0 and published_count >= args.limit:
            logger.info(f"已达到发布上限 {args.limit}，停止")
            break

        logger.info(f"\n[{i+1}/{len(note_dirs)}] 处理: {note_dir.name}")

        note = parse_note(note_dir)
        if not note:
            failed_count += 1
            continue

        success, note_url = publish_note(api, note, dry_run=args.dry_run)

        if success and not args.dry_run:
            if note_url:
                _append_url_to_note_md(note_dir, note_url)
            move_to_published(note_dir)
            published_count += 1
        elif not success:
            failed_count += 1

    # 总结
    logger.info("\n" + "="*50)
    if args.dry_run:
        logger.info("[预览模式] 未实际发布")
    else:
        logger.info(f"发布完成: 成功 {published_count} 篇, 失败 {failed_count} 篇")
    logger.info("="*50)


if __name__ == "__main__":
    main()
