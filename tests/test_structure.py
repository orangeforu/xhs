# -*- coding: utf-8 -*-
"""孵化台结构守卫（DoD 的机器化）：根目录即架构、五模块齐备、能力命名可 import、案例有档案。"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 宪法允许的根目录条目（目录 + 文件白名单）
ALLOWED_DIRS = {"cockpit", "capabilities", "ventures", "knowledge", "assets", "98-debt", "tests"}
# gitignored 的本地依赖目录（物理存在但不入 git）
IGNORED_LOCAL = {"node_modules", ".cache", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".workbuddy", ".zcode"}
ALLOWED_FILES = {
    "CLAUDE.md", "GLOSSARY.md", "README.md", "LICENSE",
    ".gitignore", "pyproject.toml", "requirements.txt", "requirements-dev.txt",
    ".env.example", ".env", ".claude",
}


def test_root_is_architecture():
    entries = {p.name for p in ROOT.iterdir()}
    illegal = {
        e for e in entries
        if e not in ALLOWED_DIRS | ALLOWED_FILES | IGNORED_LOCAL
        and not e.startswith(".")
    }
    assert not illegal, f"根目录出现架构外条目: {sorted(illegal)}"


def test_five_modules_exist():
    for d in ALLOWED_DIRS:
        assert (ROOT / d).is_dir(), f"缺少五模块目录: {d}"


def test_capability_dirs_are_importable():
    caps = ROOT / "capabilities"
    for d in caps.iterdir():
        if d.is_dir() and d.name not in {"_shared", "__pycache__"}:
            assert re.fullmatch(r"[a-z_]+", d.name), f"能力目录名不可 import: {d.name}"
        if d.is_dir() and d.name != "__pycache__":
            assert (d / "README.md").exists(), f"能力缺 README: {d.name}"


def test_ventures_have_venture_md():
    for d in (ROOT / "ventures").iterdir():
        if d.is_dir() and not d.name.startswith("_") and not d.name.startswith("__pycache__"):
            assert (d / "venture.md").exists(), f"案例缺 venture.md: {d.name}"
            text = (d / "venture.md").read_text(encoding="utf-8")
            assert "stop_loss" in text, f"案例缺止损线字段: {d.name}"


def test_cockpit_five_files():
    for f in ("ledger.md", "time-budget.md", "status.md", "report-card.md", "authorization.md"):
        assert (ROOT / "cockpit" / f).exists(), f"cockpit 缺 {f}"
