# -*- coding: utf-8 -*-
"""legacy-pipeline 路径垫片：让本目录内的代码保持 `from core...` / `import pipeline`
原样可用（零改动封存）。根目录 pytest 不收集本目录（testpaths=tests）；
要手动跑遗产测试：cd capabilities/xhs_content/legacy-pipeline && python -m pytest tests/
"""
import sys
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
