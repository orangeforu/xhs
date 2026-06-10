"""一次性迁移脚本 — 把 docs_agent/ 下的笔记按状态分到 3 个子目录。

分类规则：
  docs_agent/pending/     新生成未发布（topics.json 中 status=generated，或未追踪的孤儿目录）
  docs_agent/published/   已发布但未录入数据（performance.json 中 entry 但 likes/collects/exposure 全 0）
  docs_agent/archived/    已发布且已录入数据（performance.json 中 entry 且 likes/collects/exposure 任一 > 0）

副作用：
  - 备份 data/topics.json 与 data/performance.json 到 data/*_backup_migrate_<ts>.json
  - 移动 docs_agent/<folder> → docs_agent/<subdir>/<folder>
  - 更新 topics.json[*].output_dir 与 performance.json.notes[*].output_dir 的路径前缀

幂等：已迁移到子目录的文件夹不会再次处理。
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_AGENT = ROOT / "docs_agent"
DATA_DIR = ROOT / "data"
TOPICS_PATH = DATA_DIR / "topics.json"
PERF_PATH = DATA_DIR / "performance.json"

SUBDIRS = ("pending", "published", "archived")


def _backup(path: Path) -> None:
    ts = int(time.time())
    dst = path.with_name(f"{path.stem}_backup_migrate_{ts}{path.suffix}")
    shutil.copy2(path, dst)
    print(f"  backup: {dst.name}")


def _has_data(note: dict) -> bool:
    return any(int(note.get(k) or 0) > 0 for k in ("likes", "collects", "exposure", "views"))


def _classify(folder_name: str, topics_by_dir: dict, perf_by_dir: dict) -> str:
    perf_note = perf_by_dir.get(folder_name)
    if perf_note is not None:
        return "archived" if _has_data(perf_note) else "published"
    if folder_name in topics_by_dir:
        return "pending"
    # 孤儿目录（未被任何 JSON 追踪）— 默认归到 pending 便于人工复查
    return "pending"


def _rewrite_output_dir(value: str, folder_name: str, subdir: str) -> str:
    """把形如 'docs_agent/<folder>' 或绝对路径改写为 'docs_agent/<subdir>/<folder>'。"""
    if not value:
        return value
    old_rel = f"docs_agent/{folder_name}"
    old_abs = str(ROOT / old_rel)
    new_rel = f"docs_agent/{subdir}/{folder_name}"
    new_abs = str(ROOT / new_rel)
    if value == old_abs:
        return new_abs
    if value == old_rel or value.endswith("/" + old_rel) or value.endswith("\\" + old_rel):
        return value[: -len(old_rel)] + new_rel
    return value


def main() -> int:
    if not DOCS_AGENT.exists():
        print(f"ERROR: {DOCS_AGENT} 不存在")
        return 1
    if not TOPICS_PATH.exists() or not PERF_PATH.exists():
        print(f"ERROR: 缺少 {TOPICS_PATH} 或 {PERF_PATH}")
        return 1

    # 创建子目录
    for s in SUBDIRS:
        (DOCS_AGENT / s).mkdir(exist_ok=True)

    # 加载 JSON
    topics_data = json.loads(TOPICS_PATH.read_text(encoding="utf-8"))
    perf_data = json.loads(PERF_PATH.read_text(encoding="utf-8"))

    # 备份
    print("Backing up JSON files...")
    _backup(TOPICS_PATH)
    _backup(PERF_PATH)

    # 构建查找索引 — 用目录 basename 作为 key（兼容绝对/相对路径）
    topics = topics_data.get("topics", [])
    notes = perf_data.get("notes", [])

    topics_by_dir: dict[str, dict] = {}
    for t in topics:
        od = t.get("output_dir", "")
        if od:
            topics_by_dir[Path(od).name] = t

    perf_by_dir: dict[str, dict] = {}
    for n in notes:
        od = n.get("output_dir", "")
        if od:
            perf_by_dir[Path(od).name] = n

    # 枚举 docs_agent/ 顶层目录（排除 3 个分类子目录本身）
    folders = sorted(
        d for d in DOCS_AGENT.iterdir()
        if d.is_dir() and d.name not in SUBDIRS
    )
    print(f"\nFound {len(folders)} note folders to classify.")

    moved = {"pending": 0, "published": 0, "archived": 0}
    for folder in folders:
        subdir = _classify(folder.name, topics_by_dir, perf_by_dir)
        dst = DOCS_AGENT / subdir / folder.name
        if dst.exists():
            print(f"  skip (already exists): {subdir}/{folder.name}")
            continue
        print(f"  {folder.name}  →  {subdir}/")
        shutil.move(str(folder), str(dst))
        moved[subdir] += 1

    # 更新 topics.json 中的 output_dir
    for t in topics:
        od = t.get("output_dir", "")
        if not od:
            continue
        folder_name = Path(od).name
        # 找到它被分到了哪个 subdir
        for s in SUBDIRS:
            candidate = DOCS_AGENT / s / folder_name
            if candidate.exists():
                t["output_dir"] = _rewrite_output_dir(od, folder_name, s)
                break

    # 更新 performance.json 中的 output_dir
    for n in notes:
        od = n.get("output_dir", "")
        if not od:
            continue
        folder_name = Path(od).name
        for s in SUBDIRS:
            candidate = DOCS_AGENT / s / folder_name
            if candidate.exists():
                n["output_dir"] = _rewrite_output_dir(od, folder_name, s)
                break

    TOPICS_PATH.write_text(
        json.dumps(topics_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    PERF_PATH.write_text(
        json.dumps(perf_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nDone. Moved: {dict(moved)}")
    print(f"  pending   : {moved['pending']}  (新生成未发布)")
    print(f"  published : {moved['published']}  (已发布未录入数据)")
    print(f"  archived  : {moved['archived']}  (已发布已录入数据)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
