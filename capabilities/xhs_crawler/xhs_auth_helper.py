"""
小红书登录 Cookie 持久化工具
============================

解决每次运行脚本都要扫码的问题：
- 首次运行：扫码登录 → 保存 Cookie
- 后续运行：读取 Cookie → 直接登录
- Cookie 过期：自动重新扫码

用法:
    from scripts.xhs_auth_helper import get_pc_auth, get_creator_auth

    # PC 端（用于采集数据）
    auth = get_pc_auth()
    api = XHS_Apis(auth).bootstrap()

    # 创作者端（用于发布笔记）
    auth = get_creator_auth()
    api = XHS_Creator_Apis(auth).bootstrap()
"""

import json
import sys
from pathlib import Path

# Windows GBK 终端打不出 emoji/特殊字符（✅ ▀ 等），强制 UTF-8 输出
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 将项目根目录加入路径
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # 仓库根（.cache/ 所在）

# Cookie 保存路径
COOKIE_DIR = PROJECT_ROOT / ".cache"
PC_COOKIE_FILE = COOKIE_DIR / "xhs_pc_cookie.json"
CREATOR_COOKIE_FILE = COOKIE_DIR / "xhs_creator_cookie.json"


def _ensure_cache_dir():
    """确保缓存目录存在。"""
    COOKIE_DIR.mkdir(parents=True, exist_ok=True)


def _save_cookie(cookie_file: Path, cookies: str, login_source: str = "qrcode"):
    """保存 Cookie 到文件。"""
    _ensure_cache_dir()
    data = {
        "cookies": cookies,
        "login_source": login_source,
    }
    with open(cookie_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_cookie(cookie_file: Path) -> str | None:
    """从文件读取 Cookie。"""
    if not cookie_file.exists():
        return None
    try:
        with open(cookie_file, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("cookies")
    except (json.JSONDecodeError, KeyError):
        return None


def _clear_cookie(cookie_file: Path):
    """清除 Cookie 文件。"""
    if cookie_file.exists():
        cookie_file.unlink()


def get_pc_auth():
    """获取 PC 端 Auth（带 Cookie 持久化）。

    流程:
        1. 尝试从 .cache/xhs_pc_cookie.json 读取 Cookie
        2. 如果 Cookie 有效，直接 from_cookie 登录
        3. 如果 Cookie 无效/不存在，扫码登录并保存
    """
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor"))  # spider_xhs 所在
    from spider_xhs import XHSPcAuth

    # 先尝试读取已保存的 Cookie
    saved_cookie = _load_cookie(PC_COOKIE_FILE)

    if saved_cookie:
        try:
            print("[xhs_auth] 尝试用已保存的 Cookie 登录 PC 端...")
            auth = XHSPcAuth.from_cookie(saved_cookie)
            # 简单验证：尝试获取未读消息
            from spider_xhs import XHS_Apis

            api = XHS_Apis(auth).bootstrap()
            success, msg, _ = api.get_unread_message()
            if success:
                print("[xhs_auth] ✅ PC 端 Cookie 登录成功！")
                return auth
            else:
                print(f"[xhs_auth] ⚠️ Cookie 已过期: {msg}")
                _clear_cookie(PC_COOKIE_FILE)
        except Exception as e:
            print(f"[xhs_auth] ⚠️ Cookie 登录失败: {e}")
            _clear_cookie(PC_COOKIE_FILE)

    # Cookie 不存在或已过期，扫码登录
    print("[xhs_auth] 请使用小红书 APP 扫描弹出的二维码（PC 端）...")
    auth = XHSPcAuth.from_qrcode_login(show_in_terminal=True)

    # 保存 Cookie
    _save_cookie(PC_COOKIE_FILE, auth.cookies)
    print(f"[xhs_auth] ✅ PC 端登录成功，Cookie 已保存到 {PC_COOKIE_FILE}")

    return auth


def get_creator_auth():
    """获取创作者端 Auth（带 Cookie 持久化）。

    流程:
        1. 尝试从 .cache/xhs_creator_cookie.json 读取 Cookie
        2. 如果 Cookie 有效，直接 from_cookie 登录
        3. 如果 Cookie 无效/不存在，扫码登录并保存
    """
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor"))  # spider_xhs 所在
    from spider_xhs import XHSCreatorAuth

    # 先尝试读取已保存的 Cookie
    saved_cookie = _load_cookie(CREATOR_COOKIE_FILE)

    if saved_cookie:
        try:
            print("[xhs_auth] 尝试用已保存的 Cookie 登录创作者端...")
            auth = XHSCreatorAuth.from_cookie(saved_cookie)
            # 简单验证：尝试获取已发布列表
            from spider_xhs import XHS_Creator_Apis

            api = XHS_Creator_Apis(auth).bootstrap()
            success, msg, _ = api.get_all_posted_notes()
            if success:
                print("[xhs_auth] ✅ 创作者端 Cookie 登录成功！")
                return auth
            else:
                print(f"[xhs_auth] ⚠️ Cookie 已过期: {msg}")
                _clear_cookie(CREATOR_COOKIE_FILE)
        except Exception as e:
            print(f"[xhs_auth] ⚠️ Cookie 登录失败: {e}")
            _clear_cookie(CREATOR_COOKIE_FILE)

    # Cookie 不存在或已过期，扫码登录
    print("[xhs_auth] 请使用小红书 APP 扫描弹出的二维码（创作者端）...")

    # Windows GBK 终端打不出 ASCII 二维码字符（▀ 等），
    # 改成保存 PNG 文件，手动打开扫描，跨平台稳定。
    import sys as _sys

    if _sys.platform.startswith("win"):
        from apis.xhs_creator_login_apis import XHSCreatorLoginApi

        _qr_path = PROJECT_ROOT / ".cache" / "xhs_creator_qrcode.png"
        _qr_path.parent.mkdir(parents=True, exist_ok=True)

        def _save_qr_image(url):
            import qrcode

            qr = qrcode.QRCode(box_size=10, border=4)
            qr.add_data(url)
            qr.make(fit=True)
            qr.make_image(fill_color="black", back_color="white").save(str(_qr_path))
            print(f"[xhs_auth] 二维码已保存为图片: {_qr_path}")
            print("[xhs_auth] 请打开该图片，用小红书 APP 扫码（5 分钟内有效）...")
            try:
                import os as _os

                _os.startfile(str(_qr_path))  # 自动用默认图片查看器打开
            except Exception:
                print("[xhs_auth] 自动打开失败，请手动双击该 PNG 文件")

        XHSCreatorLoginApi.show_qrcode_terminal = staticmethod(_save_qr_image)

    auth = XHSCreatorAuth.from_qrcode_login(show_in_terminal=True)

    # 保存 Cookie
    _save_cookie(CREATOR_COOKIE_FILE, auth.cookies)
    print(f"[xhs_auth] ✅ 创作者端登录成功，Cookie 已保存到 {CREATOR_COOKIE_FILE}")

    return auth


def clear_all_cookies():
    """清除所有保存的 Cookie（用于重新登录）。"""
    _clear_cookie(PC_COOKIE_FILE)
    _clear_cookie(CREATOR_COOKIE_FILE)
    print("[xhs_auth] 已清除所有保存的 Cookie，下次运行将重新扫码")


if __name__ == "__main__":
    # 测试：直接运行可以验证登录
    import argparse

    parser = argparse.ArgumentParser(description="小红书登录 Cookie 管理")
    parser.add_argument("--pc", action="store_true", help="测试 PC 端登录")
    parser.add_argument("--creator", action="store_true", help="测试创作者端登录")
    parser.add_argument("--clear", action="store_true", help="清除所有保存的 Cookie")
    args = parser.parse_args()

    if args.clear:
        clear_all_cookies()
    elif args.pc:
        get_pc_auth()
        print("PC 端认证成功（不输出 Cookie）")
    elif args.creator:
        get_creator_auth()
        print("创作者端认证成功（不输出 Cookie）")
    else:
        print("用法: python scripts/xhs_auth_helper.py --pc|--creator|--clear")
