#!/usr/bin/env python3
"""
AMap credential setup wizard for travel-itinerary-mapper.

Interactive (human terminal):
    python scripts/setup_amap.py

Non-interactive (agents / CI / scripts):
    python scripts/setup_amap.py --key <KEY> --security <JSCODE> --scope user
    python scripts/setup_amap.py --show        # print masked status
    python scripts/setup_amap.py --check       # validate key online against AMap JS API

Scopes:
    user     ~/.workbuddy/travel-itinerary-mapper.json   (recommended)
    project  <skill>/scripts/config.json                 (gitignored, do NOT commit)
"""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path


def _use_utf8_output():
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream.encoding and stream.encoding.lower() not in ("utf-8", "utf8"):
                stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


_use_utf8_output()

KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")

SKILL_ROOT = Path(__file__).parent.resolve().parent
USER_CONFIG = Path.home() / ".workbuddy" / "travel-itinerary-mapper.json"
PROJECT_CONFIG = SKILL_ROOT / "scripts" / "config.json"


def scope_path(scope):
    if scope == "project":
        return PROJECT_CONFIG
    return USER_CONFIG


def read_config(path):
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def write_config(path, key, security):
    path.parent.mkdir(parents=True, exist_ok=True)
    cfg = read_config(path)
    cfg["key"] = key
    cfg["securityJsCode"] = security
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def check_key_online(key):
    """A valid Web端(JS API) key returns ~1MB of JS; an invalid one returns a short error."""
    url = f"https://webapi.amap.com/maps?v=2.0&key={key}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "travel-itinerary-mapper-setup"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
        if len(body) > 100_000:
            return True, f"Key 有效（JS API 返回 {len(body)//1024} KB 脚本）"
        return False, "Key 无效或平台类型不是「Web端(JS API)」（返回内容过短）"
    except Exception as e:
        return None, f"在线校验失败（网络问题，不影响本地配置）：{e}"


def main():
    parser = argparse.ArgumentParser(description="Configure AMap credentials for travel-itinerary-mapper")
    parser.add_argument("--key", help="AMap JS API key (Web端 JS API type)")
    parser.add_argument("--security", "--security-jscode", dest="security",
                        help="securityJsCode paired with the key")
    parser.add_argument("--scope", choices=["user", "project"], default="user",
                        help="Where to store the config (default: user)")
    parser.add_argument("--show", action="store_true", help="Print masked current status and exit")
    parser.add_argument("--check", action="store_true", help="Validate the configured key online")
    args = parser.parse_args()

    # --show: masked status
    if args.show:
        for scope in ("user", "project"):
            cfg = read_config(scope_path(scope))
            key = cfg.get("key", "")
            masked = (key[:4] + "****" + key[-4:]) if len(key) > 8 else ("(未配置)" if not key else "****")
            print(f"[{scope}] {scope_path(scope)}")
            print(f"    key: {masked}  securityJsCode: {'已配置' if cfg.get('securityJsCode') else '未配置'}")
        return

    # --check: online validation
    if args.check:
        key = args.key or read_config(scope_path(args.scope)).get("key", "")
        if not key:
            print("[error] 没有可校验的 Key：先配置，或用 --key 临时指定。", file=sys.stderr)
            sys.exit(2)
        ok, detail = check_key_online(key)
        print(("✓ " if ok else "✗ ") + detail if ok is not None else "… " + detail)
        sys.exit(0 if ok else 1)

    # Non-interactive path: --key --security both required
    if args.key or args.security:
        if not (args.key and args.security):
            print("[error] 非交互配置必须同时提供 --key 和 --security（成对的 jscode）。"
                  "缺 jscode 时 JS API 2.0 地图会静默白屏。", file=sys.stderr)
            sys.exit(2)
        if not KEY_PATTERN.match(args.key):
            print("[error] Key 格式非法（仅允许字母/数字/_/-，长度 8~128）。", file=sys.stderr)
            sys.exit(2)
        write_config(scope_path(args.scope), args.key, args.security)
        print(f"✓ 已写入 {scope_path(args.scope)}")
        ok, detail = check_key_online(args.key)
        print(("✓ " if ok else "✗ ") + detail if ok is not None else "… " + detail)
        print("完成。现在可以运行：python scripts/render_itinerary.py --input <行程.json> --output <页面.html>")
        return

    # Interactive path: refuse when stdin is not a TTY (agents/CI would hang)
    if not sys.stdin.isatty():
        print("[error] 当前是非交互环境（无法键盘输入）。请改用非交互写法：\n"
              "  python scripts/setup_amap.py --key <KEY> --security <JSCODE> --scope user",
              file=sys.stderr)
        sys.exit(2)

    print("== 高德地图密钥配置向导（travel-itinerary-mapper）==\n")
    print("前提：到 https://console.amap.com/ 申请：")
    print("  1. 创建应用 → 添加 Key，平台选「Web端(JS API)」（不是 Web服务）")
    print("  2. 复制该 Key 详情页的「安全密钥 jscode」（2021-12 之后创建的 Key 必须成对使用）\n")
    key = input("粘贴 Key: ").strip()
    security = input("粘贴安全密钥 jscode: ").strip()
    if not key or not security:
        print("[error] 两项都必须提供。", file=sys.stderr)
        sys.exit(2)
    if not KEY_PATTERN.match(key):
        print("[error] Key 格式非法。", file=sys.stderr)
        sys.exit(2)
    scope = (input("保存位置 user/project [user]: ").strip() or "user").lower()
    if scope not in ("user", "project"):
        scope = "user"
    write_config(scope_path(scope), key, security)
    print(f"✓ 已写入 {scope_path(scope)}")
    ok, detail = check_key_online(key)
    print(("✓ " if ok else "✗ ") + detail if ok is not None else "… " + detail)
    print("完成。现在可以运行：python scripts/render_itinerary.py --input <行程.json> --output <页面.html>")


if __name__ == "__main__":
    main()
