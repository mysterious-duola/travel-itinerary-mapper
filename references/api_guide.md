# API Guide & Reference

## Data Schema

### POI (Point of Interest)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | POI name |
| lng | number | Yes | Longitude |
| lat | number | Yes | Latitude |
| category | string | Yes | `attraction` / `scenic` / `food` |
| day | int | Yes | Day number (1-based) |
| start_time | string | Yes | e.g. `"07:30"` |
| end_time | string | Yes | e.g. `"11:30"` |
| address | string | No | Full address |
| photos | string[] | **Yes** | 2~4 image URLs. MANDATORY: every POI must have web-searched real photos (see SKILL.md Step 3); render script exits with error on empty photos |
| intro | string | No | Description text |
| review | string | No | Review/suggestion text |
| price | string | No | e.g. `"¥55"` / `"免费"` / `"人均约80元"` |
| suggest | string | No | Suggested duration, e.g. `"3.5小时"` |
| booking | string | No | Booking hint |
| planned_duration | string | Yes | Planned stay time |
| meal_type | string | No | `"早餐"` / `"午餐"` / `"晚餐"` — for food POIs |
| color | string | No | Custom marker color (hex). If omitted, uses theme default. |

### Day Plan

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| city | string | Yes | City name |
| day | int | Yes | Day number |
| departure_time | string | Yes | Start time |
| departure_from | string | Yes | Departure location label |
| end_time | string | Yes | End time |
| summary | string | Yes | Day summary text |

### Route Segment

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| from | string | Yes | Origin POI name |
| to | string | Yes | Destination POI name |
| depart_time | string | Yes | Departure time |
| arrival_time | string | Yes | Arrival time |
| transport | string | Yes | Transport description |
| duration | string | Yes | Duration text |
| distance | string | Yes | Distance text |
| city | string | Yes | City name, or `"跨城"` for inter-city |
| day | int | Yes | Day number |
| from_city | string | No | For cross-city: origin city |
| to_city | string | No | For cross-city: destination city |
| arrival_day | int | No | For cross-city: arrival day |

### Accommodation (top-level, required by workflow)

`"accommodation": {"城市名": "住宿片区建议文本（片区+理由+避坑点）", ...}`

渲染为中栏顶部「🏨 住宿范围建议」卡片，随城市 tab 切换。内容应基于访谈得到的住宿偏好与该城每日动线撰写。

### AMap credentials (top-level, optional — built-in defaults exist)

```json
"amap": {"key": "Web端JS-API Key", "securityJsCode": "配对安全密钥"}
```

本仓库**不内置任何密钥**。密钥来源优先级：CLI `--amap-key/--amap-security` > JSON `amap` 字段 > 环境变量 `AMAP_JS_KEY`/`AMAP_SECURITY_CODE` > 配置文件（`scripts/setup_amap.py` 写入）。未配置时脚本 exit 5；若显式只给 key 不给 jscode 则渲染脚本直接报错退出（JS API 2.0 缺 jscode = 地图静默白屏）。

## Open-Meteo Weather API

Endpoint: `https://api.open-meteo.com/v1/forecast`

Parameters:
- `latitude`, `longitude` — City center coords
- `start_date`, `end_date` — ISO date strings
- `daily` — `weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max`
- `timezone` — `Asia/Shanghai`

Example:
```
https://api.open-meteo.com/v1/forecast?latitude=30.67&longitude=104.07&start_date=2026-08-13&end_date=2026-08-18&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=Asia/Shanghai
```

Weather code mapping (simplified):
- 0 = Clear sky (晴)
- 1-3 = Mainly clear / partly cloudy (多云)
- 45-48 = Fog (雾)
- 51-55 = Drizzle (毛毛雨)
- 61-65 = Rain (雨)
- 80-82 = Rain showers (阵雨)
- 95-99 = Thunderstorm (雷雨)
- 71-77 = Snow (雪)

## AMap JS API v2.0

- Loader: `https://webapi.amap.com/maps?v=2.0&key=YOUR_KEY`
- **Key 必须是「Web端(JS API)」类型**；验证：`curl -s -o /dev/null -w "%{size_download}" "https://webapi.amap.com/maps?v=2.0&key=KEY"` — 约 1MB = 有效；约 90 字节（"Error key!"）= Key 无效/类型错。
- **安全密钥必须成对提供**（2021-12 后创建的 Key 无 jscode 必定白屏且不报错）：
  ```html
  <script>window._AMapSecurityConfig = { securityJsCode: "配对安全密钥" };</script>
  ```
  必须出现在 loader `<script src=...>` 之前（模板占位符 `{{AMAP_SECURITY_SCRIPT}}` 已保证顺序）。
- **域名白名单**：本地 `file://` 双击打开使用 → 控制台该 Key 的白名单必须留空；设置了白名单会导致瓦片鉴权失败、地图空白。
- **自动版本选择**：模板头部脚本先探测 WebGL（`canvas.getContext('webgl')`），可用则加载 `v=2.0`，不可用则 `document.write` 注入 `v=1.4.15`（Canvas 渲染、无需 jscode）。1.4.15 模式下**不得传自定义 mapStyle**（DOM 渲染器不支持，会导致瓦片永不加载），模板已按 `window.__AMAP_VERSION` 条件省略。
- 模板内置 10 秒瓦片渲染看门狗：未出图时地图区自动显示中文排查清单（jscode 配对 / 白名单 / Key 类型）；初始化抛异常时清单附真实 error.message。
- Map style: `amap://styles/fresh` (default in template)
- Route plugins: `AMap.Walking`, `AMap.Riding`, `AMap.Driving`, `AMap.Transfer`
- Layer plugins: `AMap.TileLayer.Satellite`, `AMap.TileLayer.RoadNet`

## Theme / city_branding 契约

整页视觉必须凸显目的地城市的具体特色：**配色 = 城市性格**（如北京=皇城红）、**头部 banner/标题区 = 代表性地标建筑**（如北京=天安门）。主题有两个来源：

1. **正路（必走）**：AI 为每次行程填写顶层 `theme_override`。脚本先解析**基底预设**（`theme_override.palette` 指定的预设名 > 城市自动检测 > default），再把 `theme_override` **浅合并**到基底之上：只覆盖你给的键，其余颜色键沿用基底，因此**允许部分覆盖**；任何新增品牌键（`landmark`/`landmarkEmoji`/`landmarkSvg`/`tagline`/`paletteReason`/`cityThemes`）都会原样到达模板。
2. 兜底：`theme_override` 为空时直接用自动检测的预设（多城只命中第一个；表外城市得到 `default`）。**禁止依赖兜底出片**。

### 预设主题表（含地标参考）

| City | Theme Name | primary | bannerGrad | landmark | landmarkEmoji | tagline 参考 |
|------|-----------|---------|------------|----------|---------------|--------------|
| 成都 | chengdu-bamboo | `#287F78` | `linear-gradient(112deg,#173F3B,#2E6765,#6F8792)` | 安顺廊桥/熊猫基地 | 🐼 | 竹影蓉城·烟火慢生活 |
| 重庆 | chongqing-red | `#B44735` | `linear-gradient(112deg,#5A1E1A,#8F3E2F,#C25B3F)` | 洪崖洞 | 🏮 | 山城雾都·火锅江湖 |
| 杭州 | hangzhou-tea | `#4A7C59` | `linear-gradient(112deg,#2D4A33,#4A7C59,#7BA376)` | 雷峰塔 | ⛩️ | 湖山龙井·淡妆浓抹 |
| 西安 | xian-ancient | `#8B6914` | `linear-gradient(112deg,#4A3B2A,#8B6914,#B89B72)` | 大雁塔 | 🛕 | 千年帝都·俑土青铜 |
| 北京 | beijing-imperial | `#8B1A1A` | `linear-gradient(112deg,#5C1A1A,#8B1A1A,#B85C5C)` | 天安门/故宫角楼 | 🏯 | 皇城红墙·中轴气象 |
| 上海 | shanghai-modern | `#2E5AAC` | `linear-gradient(112deg,#1A2E5A,#2E5AAC,#5C8AD9)` | 东方明珠/外滩 | 🗼 | 外滩万国·浦江夜色 |
| 通用 | default | `#176B5B` | `linear-gradient(118deg,#173B32,#214E43,#8F3E2F)` | — | — | — |

（各预设还含 pageBg/textColor/panelBg/panelBorder/hoverBg/primarySoft/highlight/accent/cityColors，见脚本 `THEME_MAP`。）

### theme_override 对象键（完整契约）

```js
{
  // —— 颜色/排版键（均可覆盖，兜底取自预设）——
  pageBg,           // 页面背景
  textColor,        // 主文字
  muted,            // 次级文字
  panelBg,          // 卡片背景
  panelBorder,      // 卡片描边
  hoverBg,          // hover 背景
  bannerGrad,       // 头部 banner 渐变 CSS
  primary,          // 主强调色（= 城市性格色）
  primarySoft,      // 主色浅底
  highlight,        // 高亮/激活 marker
  accent,           // 点缀色（时长等）
  fontFamily,       // 字体栈
  mapStyle,         // 高德地图样式 URL（JS API 2.0 才传；1.4.15 降级时被模板忽略）
  cityColors,       // string[] 城市徽章配色
  markerColors,     // {attraction, scenic, food}
  categoryLabels,   // {attraction, scenic, food}
  categoryIcons,    // {attraction, scenic, food}
  // —— 城市品牌键（新增，模板按此凸显特色）——
  paletteReason,    // string — 一句话解释配色为何代表该城
  landmark,         // string — 代表性地标建筑名（必填，如 "天安门"）
  landmarkEmoji,    // string — 兜底象形 emoji（如 🏯）
  landmarkSvg,      // string — 横幅/标题区剪影 SVG 源码；单色 fill="currentColor"，由模板着色
  heroImage,        // string — 头部背景实景图 URL（必填，预设不含此键）：AI 按目的地城市联网
                    //   检索的标志景观横版大图，须与 POI 图同样 curl 验证 200 且 image/*、
                    //   高德系 CDN 优先（国内 file:// 可直连）；加载失败时模板回退 bannerGrad+landmarkEmoji
  tagline,          // string — 4~10 字城市短句
  cityThemes: {     // 多城：城市名 → 覆盖以上品牌键（含 heroImage）+ primary/bannerGrad（随城市 tab 切换整套换肤）。
                    //   heroImage 同时驱动整页背景（CITY_SKINS 玻璃风基准层）；可选皮肤键：tint（背景叠加的极淡城市色）、
                    //   ink/inkSoft（玻璃面板正文/次级墨色，深色夜景图配浅色字）、chipBg（徽章/天气卡底衬），缺省自动推导
    "北京": { "primary": "...", "bannerGrad": "...", "heroImage": "https://…", "landmark": "天安门", "landmarkEmoji": "🏯", "landmarkSvg": "<svg>…</svg>", "tagline": "…" }
  }
}
```

### 示例：北京

```json
"theme_override": {
  "palette": "beijing-imperial",
  "primary": "#8B1A1A",
  "bannerGrad": "linear-gradient(112deg,#5C1A1A 0%,#8B1A1A 58%,#B85C5C 100%)",
  "paletteReason": "朱红宫墙+鎏金瓦当，紫禁城中轴色彩即北京的城市性格",
  "landmark": "天安门",
  "landmarkEmoji": "🏯",
  "landmarkSvg": "<svg viewBox=\"0 0 240 88\" fill=\"currentColor\"><path d=\"…城楼剪影…\"/></svg>",
  "heroImage": "https://store.is.autonavi.com/showpic/…（AI 检索并 curl 验证过的 天安门/景山天际线 横版大图）",
  "tagline": "皇城红墙·中轴气象"
}
```

## Render Script Usage

```bash
# 标准用法：密钥来自环境变量/配置文件（setup_amap.py 写入）
python scripts/render_itinerary.py --input plan.json --output trip.html

# From stdin
cat plan.json | python scripts/render_itinerary.py --output trip.html

# 临时换 Key 时才传（或用 JSON 的 amap 字段）
python scripts/render_itinerary.py --input plan.json --output trip.html \
  --amap-key JS_API_KEY --amap-security 安全密钥jscode
```

退出码闸门：`2` = 有 Key 无 jscode（可 `--allow-missing-security` 降级）；`3` = 有 POI 缺 photos（可 `--allow-empty-photos`）；`4` = 模板占位符残留；`5` = 未配置密钥（可 `--allow-missing-key` 出无地图页面）。任何非 0 退出都不允许把输出交付给用户。
