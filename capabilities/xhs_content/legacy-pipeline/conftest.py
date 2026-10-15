"""legacy-pipeline 路径垫片：让本目录代码保持 `from core...` / `import pipeline` /
`from scripts...` 原样可用（遗产文件零改动）。根目录 pytest 不收集本目录
（testpaths=tests）；手动跑遗产测试：
  cd capabilities/xhs_content/legacy-pipeline && python -m pytest tests/
"""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[2]          # 仓库根（legacy-pipeline → xhs_content → capabilities → xhs）
_CAPS = _REPO / "capabilities"
_CASE3 = _REPO / "ventures" / "xhs_account_v1"
_CRAWLER = _CAPS / "xhs_crawler"

for p in (str(_HERE), str(_CASE3), str(_CAPS), str(_CRAWLER / "vendor")):
    if p not in sys.path:
        sys.path.insert(0, p)

# —— 遗产依赖已迁往能力层的，注册别名保持旧引用可用（零改动封存的代价清单）——
try:
    import _shared.note_schema as _ns

    import core

    core.note_schema = _ns
    sys.modules["core.note_schema"] = _ns
except ImportError:
    pass

# scripts.xhs_auth_helper → capabilities/xhs_crawler/xhs_auth_helper
try:
    import importlib.util as _iu

    _spec = _iu.spec_from_file_location(
        "scripts.xhs_auth_helper", _CRAWLER / "xhs_auth_helper.py"
    )
    _mod = _iu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    import scripts as _scripts_pkg

    _scripts_pkg.xhs_auth_helper = _mod
    sys.modules["scripts.xhs_auth_helper"] = _mod
except Exception:
    pass
