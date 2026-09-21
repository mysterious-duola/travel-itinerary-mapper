# travel-itinerary-mapper 🗺️

一个面向 AI Agent（WorkBuddy / Claude 等）的 **Skill**：输入行程 JSON，一键生成自包含的交互式旅行计划 HTML 页面——内嵌高德地图、照片画廊、逐日游玩时间线、天气卡片，并且**整页背景随目的地城市自动换肤**（成都=熊猫竹林、重庆=洪崖洞夜景、北京=皇城红……）。

> 双击即可用浏览器打开成品页面，无需服务器。地图与图片需联网。

## ✨ 特性

- **三栏工作台布局**：左侧城市 Tab + 景点列表（点击联动），中间照片画廊/景点介绍/每日游玩计划，右侧高德地图（标记、路线规划步行/骑行/驾车/公交、图例、图层切换）
- **城市主题背景**：`cityThemes[城市].heroImage` 驱动全屏城市背景图 + 横幅全透明 + 半透明玻璃卡片，切城市整套换肤
- **城市性格配色**：内置 成都/重庆/杭州/西安/北京/上海 六套预设 + `theme_override` 自由覆盖（主色/渐变/地标/标语）
- **天气卡片**：自动抓取 Open-Meteo 按行程日期逐日预报
- **等高对齐 + 自适应缩放**：三栏 800px 设计高度顶底对齐；`fitPage()` 按视口等比缩放，小显示器完整可见、大显示器观感一致
- **渲染硬闸门**：密钥配对校验 / POI 缺图校验 / 占位符残留校验，非 0 退出即阻止交付残缺页面
- **地图双保险**：无 WebGL 自动降级 JS API 1.4；瓦片 10 秒未出图在页面上直接显示中文排查清单

## 📦 安装

### 作为 WorkBuddy Skill 使用

把整个文件夹放到以下任一位置，Agent 会自动识别：

```
~/.workbuddy/skills/travel-itinerary-mapper/          # 用户级（推荐）
<项目>/.workbuddy/skills/travel-itinerary-mapper/     # 项目级
```

然后在对话里说「帮我做一个 XX 的旅行计划页面」即可触发。

### 独立使用（纯 Python，无 Agent）

```bash
git clone https://github.com/<你的用户名>/travel-itinerary-mapper.git
cd travel-itinerary-mapper
python scripts/setup_amap.py    # 配置高德密钥（见下节）
python scripts/render_itinerary.py --input examples/sample-chengdu-chongqing.json --output my_trip.html
```

## 🔑 配置高德地图密钥（必须）

页面里的地图由 [高德开放平台](https://console.amap.com/) JS API 驱动，**本仓库不含任何密钥**，需要你自己的：

1. 注册/登录高德开放平台 → 控制台 → 应用管理 → **创建新应用**；
2. 应用下 **添加 Key**，服务平台选 **「Web端(JS API)」**（不是"Web服务"，选错地图必白屏）；
3. 在该 Key 详情页复制 **安全密钥（jscode）**——2021-12 之后创建的 Key 必须与 Key 成对使用；
4. 配置到本地（任选其一）：

```bash
# 方式一：向导（人类终端交互）
python scripts/setup_amap.py

# 方式二：一条命令写好（Agent / CI 推荐）
python scripts/setup_amap.py --key <你的KEY> --security <你的jscode> --scope user

# 方式三：环境变量
export AMAP_JS_KEY=<你的KEY>
export AMAP_SECURITY_CODE=<你的jscode>

# 检查状态 / 在线校验
python scripts/render_itinerary.py --check-config
python scripts/setup_amap.py --check
```

> ⚠️ 密钥等同密码：配置文件已被 `.gitignore` 排除，**不要**把 Key/jscode 提交进任何仓库或写进会分享出去的文件。本地 `file://` 打开页面时，高德控制台中该 Key 的域名白名单必须**留空**。

## 📝 行程 JSON 快览

完整 schema 见 [`references/api_guide.md`](references/api_guide.md)。最小可用示例：

```json
{
  "title": "成都&重庆双城6日游",
  "subtitle": "均衡节奏 · 8.13-8.18",
  "start_date": "2026-08-13",
  "cities": ["成都", "重庆"],
  "city_centers": {"成都": [104.0858, 30.6974], "重庆": [106.5672, 29.5630]},
  "theme_override": {
    "palette": "chengdu-bamboo",
    "landmark": "安顺廊桥",
    "landmarkEmoji": "🐼",
    "tagline": "竹影蓉城·烟火慢生活",
    "cityThemes": {
      "成都": { "primary": "#1E7F5C", "heroImage": "https://…熊猫竹林横版大图…" },
      "重庆": { "primary": "#B3272D", "heroImage": "https://…洪崖洞夜景横版大图…" }
    }
  },
  "pois": {
    "成都": [
      { "name": "成都大熊猫繁育研究基地", "lng": 104.138176, "lat": 30.740573,
        "category": "scenic", "day": 1, "start_time": "07:30", "end_time": "11:30",
        "address": "熊猫大道1375号", "photos": ["https://…实拍图…"],
        "intro": "全球最大的大熊猫圈养繁育基地。", "price": "¥55", "suggest": "3.5小时" }
    ]
  },
  "days": [
    { "city": "成都", "day": 1, "departure_time": "07:30", "departure_from": "酒店",
      "end_time": "19:00", "summary": "上午熊猫基地，下午宽窄巷子。" }
  ],
  "routes": [
    { "from": "成都大熊猫繁育研究基地", "to": "宽窄巷子景区",
      "depart_time": "11:30", "arrival_time": "13:30", "transport": "地铁3号线",
      "duration": "约40分钟", "distance": "约12公里", "city": "成都", "day": 1 }
  ]
}
```

要点：
- 坐标用 **GCJ-02**（高德坐标系），每个 POI 精确到门口，不要用城市中心凑数；
- `photos` 每个 POI 至少 1 张（建议 2~4 张）可直连的图片 URL，否则渲染脚本 exit 3；
- 多城行程在 `cityThemes` 里给每城配 `heroImage`，页面切城市 Tab 时整套换肤。

## 🧪 无密钥自检

验证 Python + 模板链路是否正常（不需要高德 Key，地图区显示配置指引）：

```bash
python scripts/render_itinerary.py -i examples/sample-chengdu-chongqing.json -o smoke.html --allow-missing-key
```

## 📁 目录结构

```
travel-itinerary-mapper/
├── SKILL.md                  # Agent 读取的技能说明（工作流、硬规则、自检清单）
├── assets/template.html      # 自包含 HTML 模板（数据经 {{...}} 占位符注入）
├── references/api_guide.md   # 行程 JSON 完整 schema、主题契约、密钥排错
├── scripts/render_itinerary.py  # 主渲染器（天气抓取 + 主题合并 + 三道校验闸门）
├── scripts/setup_amap.py     # 高德密钥配置向导
└── examples/                 # 示例行程 JSON
```

## ❓ FAQ

**地图白屏？**
按顺序查：① 是否只给了 Key 没给配对 jscode；② Key 平台类型是否为「Web端(JS API)」；③ 本地 file:// 打开时控制台域名白名单是否留空。页面上的看门狗提示与 F12 Console 会给出具体原因。

**天气卡片为空？**
Open-Meteo 只提供未来 16 日预报，出发日期超出范围时显示"待更新"，不影响其他功能。

**图片不显示？**
图片 URL 需允许浏览器直连（无防盗链）。高德系 CDN（`store.is.autonavi.com`、`aos-cdn-image.amap.com`）在国内最稳定。

## 📄 License

[MIT](LICENSE)
