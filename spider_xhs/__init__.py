"""spider_xhs 二次封装 — 项目内统一导入入口
================================================

导出 4 个类（与 CLAUDE.md「自动发布与数据采集」一节一致）：

- ``XHS_Apis``：PC 端采集/搜索（``apis.xhs_pc_apis``）
- ``XHS_Creator_Apis``：创作者端发布（``apis.xhs_creator_apis``）
- ``XHSPcAuth`` / ``XHSCreatorAuth``：PC / 创作者两套登录认证
  （``xhs_utils.xhs_pc.auth`` / ``xhs_utils.xhs_creator.auth``）

上游 Spider_XHS 内部用顶层包 ``apis`` / ``xhs_utils`` 相互导入，
本封装把 spider_xhs 目录加入 ``sys.path`` 使其可用。

2026-09：上游仓库 force-push 导致 git 子模块锁定提交（daeb2f81）不可达，
改为 vendored 目录（89 文件）+ 本封装层重建导入入口。
导入用惰性 __getattr__：spider 依赖（curl_cffi/PyExecJS 等）未安装时
``import spider_xhs`` 本身不报错，只有真正取用类才触发 —— 避免 Streamlit
工作台因缺可选依赖而整体启动失败。

⚠️ 合规提醒：spider_xhs 为非官方接口。2026 年小红书严打 AI 托管账号
（自动注册/自动发布/模拟互动，已处置 42 万账号）。本项目约定：
发布环节保留人工确认，本库仅低频用于人工触发的发布与数据采集。
"""

import sys as _sys
from pathlib import Path as _Path

_SPIDER_DIR = _Path(__file__).parent
if str(_SPIDER_DIR) not in _sys.path:
    _sys.path.insert(0, str(_SPIDER_DIR))

# 惰性导出：PEP 562 module-level __getattr__
_EXPORTS = {
    "XHS_Apis": ("apis.xhs_pc_apis", "XHS_Apis"),
    "XHS_Creator_Apis": ("apis.xhs_creator_apis", "XHS_Creator_Apis"),
    "XHSPcAuth": ("xhs_utils.xhs_pc.auth", "XHSPcAuth"),
    "XHSCreatorAuth": ("xhs_utils.xhs_creator.auth", "XHSCreatorAuth"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    if name in _EXPORTS:
        import importlib

        module_name, attr = _EXPORTS[name]
        module = importlib.import_module(module_name)
        return getattr(module, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
