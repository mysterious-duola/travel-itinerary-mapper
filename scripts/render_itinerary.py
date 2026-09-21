#!/usr/bin/env python3
"""
Travel Itinerary HTML Generator (Open-Source Edition)
=====================================================
Reads itinerary JSON data, fetches weather from Open-Meteo, and renders a
self-contained interactive HTML page with an embedded AMap map.

This edition ships with NO built-in AMap credentials. You must configure your
own Key + securityJsCode (see scripts/setup_amap.py or README.md).

Credential resolution order:
    1. CLI args        --amap-key / --amap-security
    2. JSON "amap"     { "key": "...", "securityJsCode": "..." }
    3. Environment     AMAP_JS_KEY / AMAP_SECURITY_CODE
    4. Config file     $TRAVEL_MAPPER_CONFIG
                       <skill>/config.json
                       ~/.workbuddy/travel-itinerary-mapper.json
                       ~/.config/travel-itinerary-mapper/config.json
                       ~/.travel-itinerary-mapper.json

Usage:
    python render_itinerary.py --input plan.json --output trip.html
    python render_itinerary.py --check-config
    cat plan.json | python render_itinerary.py --output trip.html --allow-missing-key
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path


def _use_utf8_output():
    """Avoid Chinese diagnostics turning to mojibake when piped/redirected on Windows."""
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream.encoding and stream.encoding.lower() not in ("utf-8", "utf8"):
                stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


_use_utf8_output()

# ---------------------------------------------------------------------------
# Theme auto-detection mapping
# ---------------------------------------------------------------------------
THEME_MAP = {
    "chengdu-bamboo": {
        "pageBg": "#DDE6E3", "textColor": "#243633", "muted": "#70817D",
        "panelBg": "#F2F6F4", "panelBorder": "#C4D2CE", "hoverBg": "#E4ECE9",
        "bannerGrad": "linear-gradient(112deg,#173F3B 0%,#2E6765 58%,#6F8792 100%)",
        "primary": "#287F78", "primarySoft": "#D5E9E4",
        "highlight": "#D96752", "accent": "#E3974F",
        "cityColors": ["#D39A3B", "#D96752"],
        "landmark": "安顺廊桥", "landmarkEmoji": "🌉", "tagline": "竹影蓉城·烟火慢生活",
    },
    "chongqing-red": {
        "pageBg": "#F5EBE6", "textColor": "#2D1B18", "muted": "#7D6B66",
        "panelBg": "#FAF5F3", "panelBorder": "#DDD5D2", "hoverBg": "#F0E8E4",
        "bannerGrad": "linear-gradient(112deg,#5A1E1A 0%,#8F3E2F 58%,#C25B3F 100%)",
        "primary": "#B44735", "primarySoft": "#F5E4E0",
        "highlight": "#D96752", "accent": "#D39A3B",
        "cityColors": ["#D96752", "#D39A3B"],
        "landmark": "洪崖洞", "landmarkEmoji": "🏮", "tagline": "山城雾都·火锅江湖",
    },
    "hangzhou-tea": {
        "pageBg": "#E6EDE8", "textColor": "#1A2B1F", "muted": "#5E6E63",
        "panelBg": "#F5F8F6", "panelBorder": "#CDD8D1", "hoverBg": "#E2EBE5",
        "bannerGrad": "linear-gradient(112deg,#2D4A33 0%,#4A7C59 58%,#7BA376 100%)",
        "primary": "#4A7C59", "primarySoft": "#E2F0E6",
        "highlight": "#D96752", "accent": "#D39A3B",
        "cityColors": ["#5C9B73", "#D39A3B"],
        "landmark": "雷峰塔", "landmarkEmoji": "⛩️", "tagline": "湖山龙井·淡妆浓抹",
    },
    "xian-ancient": {
        "pageBg": "#EDE8E0", "textColor": "#2B2318", "muted": "#6E6659",
        "panelBg": "#FAF7F2", "panelBorder": "#DAD5CC", "hoverBg": "#F0EBE2",
        "bannerGrad": "linear-gradient(112deg,#4A3B2A 0%,#8B6914 58%,#B89B72 100%)",
        "primary": "#8B6914", "primarySoft": "#F5F0E0",
        "highlight": "#B44735", "accent": "#D39A3B",
        "cityColors": ["#B89B72", "#8B6914"],
        "landmark": "大雁塔", "landmarkEmoji": "🛕", "tagline": "千年帝都·俑土青铜",
    },
    "beijing-imperial": {
        "pageBg": "#F0E8E0", "textColor": "#2B1818", "muted": "#6E5959",
        "panelBg": "#FAF5F5", "panelBorder": "#DAD2D2", "hoverBg": "#F0E8E8",
        "bannerGrad": "linear-gradient(112deg,#5C1A1A 0%,#8B1A1A 58%,#B85C5C 100%)",
        "primary": "#8B1A1A", "primarySoft": "#F5E0E0",
        "highlight": "#B44735", "accent": "#D39A3B",
        "cityColors": ["#B85C5C", "#D39A3B"],
        "landmark": "天安门", "landmarkEmoji": "🏯", "tagline": "皇城红墙·中轴气象",
    },
    "shanghai-modern": {
        "pageBg": "#E8EBF0", "textColor": "#18212B", "muted": "#59636E",
        "panelBg": "#F5F7FA", "panelBorder": "#D2D5DA", "hoverBg": "#E2E6F0",
        "bannerGrad": "linear-gradient(112deg,#1A2E5A 0%,#2E5AAC 58%,#5C8AD9 100%)",
        "primary": "#2E5AAC", "primarySoft": "#E0E8F5",
        "highlight": "#D96752", "accent": "#D39A3B",
        "cityColors": ["#5C8AD9", "#D39A3B"],
        "landmark": "东方明珠", "landmarkEmoji": "🗼", "tagline": "外滩万国·浦江夜色",
    },
    "default": {
        "pageBg": "#F3F1EB", "textColor": "#18211D", "muted": "#69736D",
        "panelBg": "#FBFAF7", "panelBorder": "#DCDDD6", "hoverBg": "#ECEFEA",
        "bannerGrad": "linear-gradient(118deg,#173B32 0%,#214E43 52%,#8F3E2F 100%)",
        "primary": "#176B5B", "primarySoft": "#E4F0EC",
        "highlight": "#B44735", "accent": "#D27A32",
        "cityColors": ["#D39A3B", "#D96752"],
    },
}

CITY_THEME_HINTS = {
    "成都": "chengdu-bamboo",
    "重庆": "chongqing-red",
    "杭州": "hangzhou-tea",
    "西安": "xian-ancient",
    "北京": "beijing-imperial",
    "上海": "shanghai-modern",
}


def detect_theme(cities):
    """Auto-detect theme based on city names. Falls back to 'default'."""
    for city in cities:
        for hint, theme_name in CITY_THEME_HINTS.items():
            if hint in city:
                return theme_name
    return "default"


# ---------------------------------------------------------------------------
# AMap credential resolution (open-source edition: no built-in keys)
# ---------------------------------------------------------------------------
KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")

CONFIG_CANDIDATES = [
    os.environ.get("TRAVEL_MAPPER_CONFIG"),
    Path(__file__).parent.resolve() / "config.json",
    Path.home() / ".workbuddy" / "travel-itinerary-mapper.json",
    Path.home() / ".config" / "travel-itinerary-mapper" / "config.json",
    Path.home() / ".travel-itinerary-mapper.json",
]


def _load_config_file():
    for candidate in CONFIG_CANDIDATES:
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8")), path
            except Exception as e:
                print(f"[warn] 无法解析配置文件 {path}: {e}", file=sys.stderr)
    return None, None


def resolve_amap_credentials(cli_key=None, cli_security=None, json_amap=None,
                             want_source=False):
    """Resolve AMap key + securityJsCode. Returns (key, security) or with source."""
    json_amap = json_amap or {}
    config, config_path = _load_config_file()
    config = config or {}

    chain = [
        ("cli", cli_key, cli_security),
        ("json", json_amap.get("key"), json_amap.get("securityJsCode") or json_amap.get("jscode")),
        ("env", os.environ.get("AMAP_JS_KEY"), os.environ.get("AMAP_SECURITY_CODE")),
        ("config", config.get("key"), config.get("securityJsCode") or config.get("jscode")),
    ]
    for source, key, security in chain:
        if key and KEY_PATTERN.match(str(key)):
            key, security = str(key), (str(security) if security else "")
            return (key, security, source, config_path) if want_source else (key, security)
    return ("", "", None, config_path) if want_source else ("", "")


def print_check_config():
    key, security, source, config_path = resolve_amap_credentials(want_source=True)
    if not key:
        print("状态：未配置")
        print("配置方式（任选其一）：")
        print("  1) python scripts/setup_amap.py            # 交互式向导")
        print("  2) python scripts/setup_amap.py --key <KEY> --security <JSCODE> --scope user")
        print("  3) 环境变量 AMAP_JS_KEY / AMAP_SECURITY_CODE")
        return 1
    masked = key[:4] + "****" + key[-4:] if len(key) > 8 else "****"
    print(f"状态：已配置（来源：{source}）")
    print(f"Key：{masked}")
    print(f"安全密钥 jscode：{'已配置' if security else '⚠ 未配置（JS API 2.0 必须成对提供，否则地图白屏）'}")
    if source == "config" and config_path:
        print(f"配置文件：{config_path}")
    return 0


# ---------------------------------------------------------------------------
# Weather fetching (Open-Meteo)
# ---------------------------------------------------------------------------
WMO_CODE_MAP = {
    0: "晴",
    1: "多云", 2: "多云", 3: "多云",
    45: "雾", 48: "雾",
    51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨",
    56: "冻雨", 57: "冻雨",
    61: "雨", 63: "雨", 65: "雨",
    66: "冻雨", 67: "冻雨",
    71: "雪", 73: "雪", 75: "雪", 77: "雪",
    80: "阵雨", 81: "阵雨", 82: "阵雨",
    85: "阵雪", 86: "阵雪",
    95: "雷雨", 96: "雷雨", 99: "雷雨",
}


def fetch_weather(lat, lon, start_date, end_date):
    """Fetch daily forecast from Open-Meteo. Returns list of dicts."""
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&start_date={start_date}&end_date={end_date}"
        f"&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
        f"&timezone=Asia%2FShanghai"
    )
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[warn] Weather fetch failed: {e}", file=sys.stderr)
        return []

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    codes = daily.get("weathercode", [])
    tmax = daily.get("temperature_2m_max", [])
    tmin = daily.get("temperature_2m_min", [])
    pop = daily.get("precipitation_probability_max", [])

    results = []
    for i in range(len(dates)):
        results.append({
            "date": dates[i],
            "weather": WMO_CODE_MAP.get(codes[i], "多云"),
            "temp_max": round(tmax[i], 1) if i < len(tmax) else None,
            "temp_min": round(tmin[i], 1) if i < len(tmin) else None,
            "precip_probability": round(pop[i], 1) if i < len(pop) else None,
        })
    return results


def build_weather_data(cities, city_centers, start_date, days_count):
    """Build weather_data list for all cities in the trip."""
    if not start_date:
        return []
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
    except ValueError:
        return []
    end = start + timedelta(days=max(days_count - 1, 0))
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    all_data = []
    for city in cities:
        center = city_centers.get(city)
        if not center or len(center) != 2:
            continue
        lat, lon = center[1], center[0]  # Open-Meteo expects lat, lon
        forecasts = fetch_weather(lat, lon, start_str, end_str)
        for f in forecasts:
            all_data.append({
                "date": f["date"],
                "city": city,
                "weather": f["weather"],
                "temp_min": f["temp_min"],
                "temp_max": f["temp_max"],
                "precip_probability": f["precip_probability"],
            })
    return all_data


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

def render(data, template_text, amap_key, amap_security):
    """Substitute template placeholders with real data."""
    cities = data.get("cities", [])
    pois = data.get("pois", {})
    days = data.get("days", [])
    routes = data.get("routes", [])
    city_centers = data.get("city_centers", {})
    accommodation = data.get("accommodation", {})
    start_date = data.get("start_date", "")
    title = data.get("title", "旅行计划")
    subtitle = data.get("subtitle", "")
    # Resolve theme: base preset (explicit "palette" > city auto-detect > default),
    # then shallow-merge user's theme_override on top — partial overrides keep base
    # color keys; extra branding keys (landmark/landmarkEmoji/landmarkSvg/tagline/
    # paletteReason/cityThemes) pass through to the template untouched.
    theme_override = data.get("theme_override", {}) or {}
    base_name = theme_override.get("palette") or detect_theme(cities)
    theme = {**THEME_MAP.get(base_name, THEME_MAP["default"]), **theme_override}

    # Determine max day number
    max_day = max((d.get("day", 0) for d in days), default=0)

    # Build weather data
    weather_data = build_weather_data(cities, city_centers, start_date, max_day)
    weather_updated = datetime.now().strftime("%Y-%m-%dT%H:%M+08:00")

    trip_meta = {
        "start_date": start_date,
        "weather_data": weather_data,
        "weather_source": "Open-Meteo 16日预报",
        "weather_updated_at": weather_updated,
        "weather_note": "",
    }

    # Security script
    security_script = ""
    if amap_security:
        security_script = f'<script>\nwindow._AMapSecurityConfig = {{\n  securityJsCode: "{amap_security}"\n}};\n</script>'

    # JSON dumps for inline JS
    replacements = {
        "{{TITLE}}": title,
        "{{SUBTITLE}}": subtitle,
        "{{AMAP_KEY}}": amap_key,
        "{{AMAP_SECURITY_SCRIPT}}": security_script,
        "{{CITY_DATA_JSON}}": json.dumps(pois, ensure_ascii=False),
        "{{DAY_DATA_JSON}}": json.dumps(days, ensure_ascii=False),
        "{{ROUTE_DATA_JSON}}": json.dumps(routes, ensure_ascii=False),
        "{{CITY_CENTERS_JSON}}": json.dumps(city_centers, ensure_ascii=False),
        "{{TRIP_META_JSON}}": json.dumps(trip_meta, ensure_ascii=False),
        "{{ACCOMMODATION_JSON}}": json.dumps(accommodation, ensure_ascii=False),
        "{{THEME_OVERRIDE_JSON}}": json.dumps(theme, ensure_ascii=False),
    }

    output = template_text
    for placeholder, value in replacements.items():
        output = output.replace(placeholder, value)
    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate interactive travel itinerary HTML")
    parser.add_argument("--input", "-i", help="Input JSON file (or stdin if omitted)")
    parser.add_argument("--output", "-o", help="Output HTML file path")
    parser.add_argument("--amap-key", default=None,
                        help="Gaode Maps JS API key (Web端 JS API type)")
    parser.add_argument("--amap-security", default=None,
                        help="Gaode Maps securityJsCode paired with the key")
    parser.add_argument("--check-config", action="store_true",
                        help="Only report credential status (exit 0 = ready, 1 = not configured)")
    parser.add_argument("--allow-missing-security", action="store_true",
                        help="Skip the hard error when a key is given without securityJsCode")
    parser.add_argument("--allow-missing-key", action="store_true",
                        help="Render anyway without AMap credentials (map area shows setup guide)")
    parser.add_argument("--allow-empty-photos", action="store_true",
                        help="Skip the hard error when POIs have no photos")
    parser.add_argument("--template", help="Custom template.html path (default: bundled asset)")
    args = parser.parse_args()

    if args.check_config:
        sys.exit(print_check_config())

    if not args.output:
        parser.error("--output is required (unless --check-config)")

    # Read input JSON
    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    # AMap credentials: CLI args > JSON "amap" block > env > config file
    amap_key, amap_security = resolve_amap_credentials(
        cli_key=args.amap_key, cli_security=args.amap_security,
        json_amap=data.get("amap", {}) or {},
    )

    if amap_key and not amap_security:
        msg = ("[error] 高德 JS API v2.0 必须同时提供 Key 和配对的「安全密钥 jscode」，"
               "缺 jscode 时地图会静默白屏（瓦片鉴权失败）。"
               "请到 https://console.amap.com/ 该 Key 详情页复制安全密钥，"
               "用 --amap-security 传入（或写入配置/环境变量）；"
               "确知无需 jscode 的旧 Key 可加 --allow-missing-security 跳过。")
        if args.allow_missing_security:
            print("[warn] " + msg, file=sys.stderr)
        else:
            print(msg, file=sys.stderr)
            sys.exit(2)
    if not amap_key:
        msg = ("[error] 未配置高德密钥，无法渲染地图。配置方式（任选其一）：\n"
               "  1) python scripts/setup_amap.py\n"
               "  2) python scripts/setup_amap.py --key <KEY> --security <JSCODE> --scope user\n"
               "  3) 环境变量 AMAP_JS_KEY / AMAP_SECURITY_CODE\n"
               "  4) 本次调用加 --amap-key <KEY> --amap-security <JSCODE>\n"
               "（仅想生成无地图页面时，可加 --allow-missing-key 跳过）")
        if args.allow_missing_key:
            print("[warn] 未配置高德密钥，输出页面中的地图将不可见（其余内容正常）。", file=sys.stderr)
        else:
            print(msg, file=sys.stderr)
            sys.exit(5)

    # Read template
    if args.template:
        template_path = Path(args.template)
    else:
        # Locate bundled template relative to this script
        script_dir = Path(__file__).parent.resolve()
        template_path = script_dir.parent / "assets" / "template.html"

    with open(template_path, "r", encoding="utf-8") as f:
        template_text = f.read()

    # Photo gate: every planned POI must carry at least one web-sourced photo
    no_photo = [p.get("name", "?")
                for city_list in data.get("pois", {}).values()
                for p in city_list if not (p.get("photos") or [])]
    if no_photo:
        msg = ("[error] 以下 %d 个景点/地点缺少配图，请先用网络图片搜索（如 ImageSearch 工具）"
               "为每个 POI 填入 2~4 张已验证可直连的图片 URL 后再生成：\n  - "
               % (len(no_photo)) + "\n  - ".join(no_photo) +
               "\n（确实允许无图时加 --allow-empty-photos 跳过）")
        if args.allow_empty_photos:
            print("[warn] " + msg, file=sys.stderr)
        else:
            print(msg, file=sys.stderr)
            sys.exit(3)

    # Render
    html = render(data, template_text, amap_key, amap_security)

    # Guard: no placeholder may survive (a leftover one breaks all page JS)
    leftovers = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", html)))
    if leftovers:
        print("[error] 模板占位符未被替换: %s" % ", ".join(leftovers), file=sys.stderr)
        sys.exit(4)

    # Write output
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Generated: {out_path.resolve()}")


if __name__ == "__main__":
    main()
