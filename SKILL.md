---
name: travel-itinerary-mapper
description: This skill should be used when the user wants to generate an interactive travel itinerary HTML page with an embedded map, photo gallery, route planning, and weather forecast. It triggers on requests like "make a travel plan", "generate a trip itinerary", "create a travel guide with map", or when the user provides travel destination, dates, and preferences expecting a visual itinerary output.
agent_created: true
---

# 旅行计划地图可视化生成器 (Travel Itinerary Mapper)

## Overview

Generate a beautiful, interactive single-page HTML travel itinerary featuring:
- **Left panel**: city tabs + clickable POI (point-of-interest) list
- **Middle panel**: photo gallery, attraction intro, day-by-day timeline, and per-city 住宿范围建议
- **Right panel**: AMap (Gaode) embedded map with markers, route planning, and layer switch
- **Top banner**: trip title, city badges, and Open-Meteo weather forecast cards

The output is a self-contained `.html` file that runs entirely in the browser.

## HARD RULES（违反任何一条即视为任务失败）

1. **生成前必须先完成用户访谈**（用 AskUserQuestion 工具**弹窗选择题**让用户点选，禁止让用户手动打字作答；九项必问内容见 Step 1。不许跳过、不许自行假设）。
2. **左侧景点列表中的每一个 POI 都必须有实拍配图**（2~4 张经验证的图片 URL），不允许出现"暂无照片"。沙箱网络受限、外部图床全部不可达时，允许按下方 Environment Notes 的替代方案：每 POI 放一个干净占位图 + 页面运行时用 `AMap.PlaceSearch` 拉高德实拍图（用使用者已配置好的那把 JS Key，不要因此反复索要密钥）。
3. **本开源版不内置任何密钥**：渲染前必须先配置使用者自己的高德双密钥——`python scripts/setup_amap.py`（Agent 用非交互写法 `--key <KEY> --security <JSCODE> --scope user`），或环境变量 `AMAP_JS_KEY`/`AMAP_SECURITY_CODE`，或调用参数 `--amap-key/--amap-security`。Key 与 jscode 必须成对（只给 Key 不给 jscode 地图会静默白屏）。未配置时脚本 exit 5；加 `--allow-missing-key` 可生成无地图页面（地图区显示配置指引）。**严禁把真实密钥提交进仓库或写进会分享出去的文件**。

4. **产物必须收敛在独立文件夹 + 交付前必问终版**：一次行程任务的**所有**文件（行程 JSON、搜图/验证记录、测试渲染页、草稿、最终 HTML）必须统一放进一个**独立的产物文件夹**（在用户当前工作区根下新建，命名如 `旅行计划产物-<目的地>-<MMDD>/`），禁止散落在工作区根目录、skill 自身目录或其他目录。**首次交付前必须用 AskUserQuestion 弹窗确认「是否作为终版」**；确认为终版后，删除产物文件夹内全部中间产物（默认只留最终 HTML，用户可选保留行程 JSON），并在弹窗中列出将被删除的文件清单；非终版则保留继续迭代。详细规则见「Step 6: 终版确认与产物清理」。

## Workflow

```
用户提出旅行规划需求
    ↓
Step 0  检查高德密钥（python scripts/render_itinerary.py --check-config；未配置先用 scripts/setup_amap.py 引导配置）
    ↓
Step 1  强制弹窗访谈（AskUserQuestion 选择题，共 9 项：出发地/目的地/出发日期/游玩天数/交通方式/人数/偏好/住宿/返程地点）
    ↓     用户消息里已明确给出的项才可跳过，其余必须问
Step 2  设计行程（以"抵达目标城市"为起点、以"离开"为终点；每城住宿片区建议）
    ↓
Step 3  联网配图：每城 1 张 heroImage 背景大图 + 逐个 POI 搜图验证 URL（ImageSearch + curl）
    ↓
Step 4  组装 JSON 数据（含 photos、accommodation；amap 双密钥块可选，一般走配置文件/环境变量）
    ↓
Step 5  python scripts/render_itinerary.py 渲染（脚本内置三道硬校验）
    ↓
Step 6  终版确认与产物清理：AskUserQuestion 询问是否作为终版；终版则删除产物文件夹内全部中间产物
    ↓
Step 7  交付前自检清单 → present_files
```

## Step 1: 强制用户访谈（MUST USE AskUserQuestion）

在收集任何数据、生成任何内容之前，**必须先用 AskUserQuestion 工具做弹窗式访谈**。硬性要求：

- **只能用选择题**：每个问题给 2~4 个（最多 4）个候选选项让用户**点选**，每题末尾由系统自带"其他（自由输入）"兜底；**严禁**要求用户手动打字回答、**严禁**把开放问题丢在聊天里让用户自己敲。
- **不许跳过**：只有用户在需求里已明确写出的那一项才可省略该题，其余必问；不许因为"用户好像很急"就跳过访谈直接生成。
- **分批问**：AskUserQuestion 单次调用最多 4 题，下面 9 个必问项按 **4 + 4 + 1** 分两~三次调用问完。

**必问九项（全部用弹窗选择题）：**

第 1 批（行程骨架，4 题）：
1. **出发地**：「你从哪个城市出发？」选项如 北京 / 上海 / 广州 / 深圳（或据上下文推断的常见城市）+ 其他。→ 落入 Day1 `summary`（出发城市）。
2. **目的地**：「想去哪些城市玩？（可多选，跨城行程）」选项如 成都 / 重庆 / 西安 / 昆明 等 + 其他。→ 落入 `cities` 数组。
3. **出发日期**：「计划哪天出发？」选项如 本周末 / 下周 / 下个月具体日 + 其他。→ 换算 `start_date`，用于天气与抢票策略。
4. **游玩天数**：「一共玩几天（含首日抵达与末日返程）？」选项如 3 天 / 4~5 天 / 6~7 天 / 8 天以上 + 其他。→ 决定 `days` 数组长度与 `subtitle` 日期区间。

第 2 批（交通·人数·偏好·住宿，4 题）：
5. **交通方式**：「倾向什么交通？（影响往返及游玩期间**城市之间的切换**）」选项如 高铁优先 / 飞机可接受 / 自驾 / 高铁+飞机混合 + 其他。多城时据此确定每段城际衔接，写入 `routes[].transport`（含 `from_city`/`to_city` 跨城路线）。
6. **游玩人数**：「几个人同行？」选项如 1~2 人 / 3~4 人 / 5~8 人含老人小孩 / 9 人以上团队 + 其他。→ 影响每日节奏、POI 取舍与餐厅推荐，可在 `subtitle` 或当日 `summary` 体现。
7. **游玩偏好**（multiSelect）：「更偏向哪种玩法？」选项如 自然风景 / 美食探店 / 网红经典打卡 / 均衡节奏 + 其他。→ 决定 POI 权重与强度。
8. **住宿要求**：「住宿偏好？（用于每城住宿范围推荐）」选项如 经济连锁 / 舒适型300~600 / 高端600+ / 由AI按行程就近推荐 + 其他。→ 写入 `accommodation`。

第 3 批（返程，1 题）：
9. **返程地点**：「最后一天从哪里返回？」选项如 返回出发城市（往返） / 从另一城市返程（异地开口，具体用其他填写） / 暂未确定 + 其他。→ 写入末日 `departure_from`（返程车站/机场方向）与接驳安排。

**访谈结果 → 产出映射（务必逐条落地，字段真实存在，勿臆造）**：
- 出发地 / 目的地 / 返程地 → `cities` + 首日、末日 `summary` 与末日 `departure_from`；
- 出发日期 / 游玩天数 → `start_date` 与 `days` 天数、`subtitle` 日期区间；
- 交通方式 → `routes[].transport`（市内 + 跨城 `city:"跨城"`/`from_city`/`to_city`/`arrival_day`）；
- 游玩人数 / 游玩偏好 → POI 筛选权重、每日强度、餐厅与住宿片区，文字体现于 `subtitle`/`summary`；
- 住宿要求 → 每城 `accommodation` 文本。

## Step 2: 行程设计规则

- **以抵达为锚点**：Day 1 从抵达时间+抵达站点写起（如「23:30 抵达成都东站，接驳入住」），抵达当日不硬塞景点；最后一天按返程班次倒推，只留去车站/机场的接驳时间。
- **动线优先**：同日 POI 按地理就近串联，减少来回折返；跨城日写清城际班次时段。
- **每城住宿范围推荐（必须）**：根据该城每日动线，推荐 1~2 个住宿片区，说明理由（近地铁/近夜市/次日出发顺路）与避坑点。写入 JSON 的 `accommodation` 字段，页面中栏顶部会以「🏨 住宿范围建议」卡片展示。文本示例：「推荐住春熙路-太古里片区：地铁2/3/4号线交汇，去熊猫基地、高铁站都直达；夜间可逛太古里但临街酒店偏吵，预算敏感可选骡马市片区」。
- 结合访谈的旅行偏好分配 POI 类型配比；美食、网红点按偏好权重排。

### 城市主题定制（必做，决定整页视觉）

**页面整体主题必须凸显目的地城市的具体特色，禁止套用通用默认配色。** 生成前必须为本次目的地填写 JSON 的 `theme_override`（脚本会把它浅合并到基底预设上——`palette` 指定的预设名或城市自动检测——**允许只写要覆盖的键**，其余颜色键沿用基底；字段契约见 `references/api_guide.md` 的「Theme / city_branding 契约」），至少包含：

1. **城市性格配色**：主色/渐变/点缀要能被一句话解释为该城市的象征。示例锚点——北京=皇城红（`primary` 深红 `#8B1A1A`、朱墙金瓦）、西安=青铜俑土黄、杭州=茶绿湖色、重庆=火锅红+山城雾、上海=外滩蓝/现代金融蓝、成都=竹林青+熊猫黑白。给出颜色时同时用 `paletteReason` 说明"为什么这套色代表这座城"。
2. **地标建筑（硬要求）**：每个目的地城市必须指定 1 个代表性地标并写进 `landmark`（如 北京→`天安门`/`故宫角楼`、杭州→`雷峰塔`、上海→`东方明珠`/`外滩`、西安→`大雁塔`、重庆→`洪崖洞`、成都→`安顺廊桥`/`熊猫`），同时提供 `landmarkEmoji`（模板兜底用的简易象形，如 🏯/🗼/⛩️）与可选 `landmarkSvg`（页面横幅/标题区的剪影装饰，单色 `fill="currentColor"`）。整页的头部 banner、标题区、关键卡片要呼应这套地标与配色，让"一眼看出这是哪座城"。
3. **城市背景大图（`heroImage`，硬要求）**：**整页背景就是该城的实景大图，不能用纯渐变凑数**——这是输出模板的默认风格基准（全屏城市背景 + 横幅全透明 + 半透明玻璃卡片）。**每个目的地城市由 AI 联网检索一张代表该城标志建筑/动物的实景大图**（北京→天安门/故宫景山俯瞰天际线，成都→大熊猫/竹林，杭州→西湖三潭印月，重庆→洪崖洞夜景天际线…）。检索与 URL 验证规则同 Step 3（ImageSearch + curl 验证 200 且 `image/*`，高德系 CDN 优先、国内可直连、横版高清无大水印），写入 `theme_override.heroImage`（单城）或 `theme_override.cityThemes[城市].heroImage`（多城，随城市 Tab 切换整套换肤）；某城缺图时该城回退 `bannerGrad` 渐变 + `landmarkEmoji`。可选联动键（放 cityThemes[城市] 内）：`tint`（背景上叠加的极淡城市色）、`ink`/`inkSoft`（玻璃面板上的正文/次级墨色，深色夜景图配浅色字）、`chipBg`（徽章底衬色）。
4. **城市短句**：`tagline`（4~10 字，如北京「皇城红墙·中轴气象」）。
5. **多城行程**：以主目的地决定全局 `theme_override`；每城各自的配色+地标+背景图写进 `theme_override.cityThemes`（键为城市名，值含 `primary`/`bannerGrad`/`heroImage`/`landmark`/`landmarkEmoji`/`landmarkSvg`/`tagline`），模板随城市 tab 切换整套换肤。**不要**依赖脚本的 `detect_theme` 自动配色（那只是缺省兜底，且多城只取第一个城市、不带背景图），必须主动填好。

## Step 3: 联网配图（强制：每城 heroImage + 逐个 POI）

**先配城市主题大图**：对每个目的地城市，按上面「城市主题定制」第 3 条，用 ImageSearch 检索该城标志景观（天安门/西湖/洪崖洞这类地标或天际线，横版大图），按同样规则 curl 验证后写入 `theme_override.heroImage`（多城则连同其他品牌键放入 `cityThemes[城市名]`）。检索词示例：`"北京 天安门 城楼 全景 风光"`、`"杭州西湖 三潭印月 日落 横版"`。

然后对行程中**每一个** POI（含餐厅、车站）执行：

1. 用 **ImageSearch 工具**搜索实景照片，查询词用「POI全名 + 城市 + 类型词」，如 `"洪崖洞 夜景 实拍"`、`"成都大熊猫基地 幼崽"`。每个 POI 选 **2~4 张**，封面优先清晰、横版、无大水印。
2. **逐张验证 URL 可直连**（浏览器会带 Referer 吗？本地 file:// 打开通常不带，但仍以实际可访问为准）：
   ```bash
   curl -s -o /dev/null -w "%{http_code} %{content_type}" "图片URL"
   ```
   只保留 `HTTP 200` 且 `content_type` 以 `image/` 开头的 URL；失败/403 的换一张或换查询词重搜，不许硬凑。
3. 经验上可稳定外链的图床：`store.is.autonavi.com`、`aos-comment.amap.com`、`aos-cdn-image.amap.com`（高德系）、Wikimedia、部分政府/景区官网 CDN。小红书/大众点评 CDN 大多防盗链，慎用；拿不准就 curl 验证。
4. **禁止**：留空 photos（渲染脚本会拒收）、编造 URL、复用别的 POI 的图。
5. 若用户另有「Web服务」类型的高德 Key，可用 place/detail 接口的照片作为补充图源，但这不是默认路径，默认路径就是 ImageSearch。

## Step 4: 组装 JSON 数据

Schema 见 `references/api_guide.md`。关键字段示例（省略部分重复字段）：

```json
{
  "title": "重庆&成都双城6日游",
  "subtitle": "均衡节奏 · 8.13-8.18 · 含三星堆一日",
  "start_date": "2026-08-13",
  "cities": ["成都", "重庆"],
  "city_centers": {"成都": [104.085857, 30.697403], "重庆": [106.567257, 29.563037]},
  "amap": {"key": "高德JS-API-Key", "securityJsCode": "与该Key配对的安全密钥"},  // 可选，一般用环境变量/配置文件，不写进行程JSON
  "accommodation": {
    "成都": "推荐住春熙路-太古里片区：…",
    "重庆": "推荐住解放碑-较场口片区：…"
  },
  "theme_override": {},
  "pois": {
    "成都": [
      {"name": "成都大熊猫繁育研究基地", "lng": 104.138176, "lat": 30.740573,
       "category": "scenic", "day": 2, "start_time": "07:30", "end_time": "11:30",
       "address": "熊猫大道1375号", "photos": ["https://…200且image/*验证过的URL", "…"],
       "intro": "…", "review": "…", "price": "¥55", "suggest": "3.5小时",
       "booking": "官方公众号提前1~7天预约", "planned_duration": "4小时"}
    ]
  },
  "days": [
    {"city": "成都", "day": 1, "departure_time": "23:30", "departure_from": "成都东站",
     "end_time": "23:59", "summary": "全天在途，凌晨抵达，接驳入住休息。"}
  ],
  "routes": [
    {"from": "A", "to": "B", "depart_time": "11:30", "arrival_time": "12:10",
     "transport": "地铁3号线→4号线", "duration": "约40分钟", "distance": "约16公里",
     "city": "成都", "day": 2}
  ]
}
```

数据收集要点：
- **坐标**：Web 搜索或高德站外接口确定每个 POI 精确 `lng/lat`（GCJ-02 坐标系），不许用城市中心近似景点。
- **photos**：Step 3 的产物，必填。
- **category**：`attraction` / `scenic` / `food`；餐厅加 `meal_type`。
- **跨城路线**：`city: "跨城"` + `from_city` + `to_city` + `arrival_day`。
- **主题**：`theme_override` **必须显式填写**（见 Step 2「城市主题定制」）——主色/渐变体现目的地城市性格，带上代表性地标 `landmark`/`landmarkEmoji`/`landmarkSvg`/`tagline` 与城市实景背景大图 `heroImage`（Step 3 联网检索并验证）；多城写 `cityThemes`。脚本的 `detect_theme` 仅作缺省兜底，别依赖。

## Step 5: 渲染

```bash
python scripts/render_itinerary.py --input itinerary.json --output "旅行计划.html"
# 密钥来源优先级：--amap-key/--amap-security > JSON 的 amap 字段 > 环境变量 AMAP_JS_KEY/AMAP_SECURITY_CODE > 配置文件（setup_amap.py 写入）。
# 未配置密钥时报 exit 5 并给出配置指引；仅想出无地图页面时加 --allow-missing-key。
```

脚本自带三道硬闸门（都会阻止交付残缺页面）：
1. 给了 Key 却没给配对 jscode → **exit 2 报错**（这正是"密钥加了地图仍白屏"的第一元凶）。
2. 任何 POI 的 photos 为空 → **exit 3** 并列出缺图名单。
3. 模板占位符有残留 → **exit 4**（残留占位符会让整页 JS 崩掉）。

### 高德密钥配置（开源版必读）

模板里是 `{{AMAP_KEY}}` 和 `{{AMAP_SECURITY_SCRIPT}}` 两个占位符，由渲染脚本按「CLI 参数 > JSON amap 字段 > 环境变量 > 配置文件」的优先级注入。**本仓库不含任何真实密钥**，使用者必须先配置自己的双密钥：

```bash
python scripts/render_itinerary.py --check-config      # 查看配置状态（exit 0=就绪 1=未配置）
python scripts/setup_amap.py                           # 人类终端：交互式向导
python scripts/setup_amap.py --key <KEY> --security <JSCODE> --scope user   # Agent/CI：非交互
python scripts/setup_amap.py --check                   # 在线校验 Key 有效性
```

仅当排查地图问题时注意：

- Key 平台类型必须是 **「Web端(JS API)」**（不是"Web服务"）。判别：用这把 Key 请求 `https://webapi.amap.com/maps?v=2.0&key=KEY`，返回 ~1MB JS 为有效；返回几十行 "Error key!" 则 Key 无效/类型错。
- **安全密钥 jscode** 在控制台该 Key 详情页，与 Key 一一配对，**必须同时提供**。所有 2021-12 之后创建的 Key 无 jscode 必定白屏。
- 本地双击 `file://` 打开使用 → 控制台里的**域名白名单必须留空**；设了白名单则只有白名单内站点能显示地图。
- 页面内置**双保险**：① 加载时自动探测 WebGL——有则用 JS API 2.0，无则自动降级 1.4.15（Canvas 渲染、不需要 jscode，此时自定义 mapStyle 会被忽略）；② 瓦片渲染看门狗：10 秒未出图会在地图上直接显示中文排查清单，初始化抛异常时清单会附上**真实错误消息**（F12 Console 亦有完整堆栈）。
- 排错对照：报「初始化抛出异常」→ 看横幅里的实际错误（多为 WebGL 被禁用/旧内核浏览器，新版会自动降级兜底）；报「10 秒未渲染」→ jscode 配对或域名白名单问题；报「脚本加载失败」→ Key 无效/网络问题。

## Step 6: 终版确认与产物清理（强制，防止垃圾文件散落）

- **统一产物文件夹**：任务开始时就确定产物文件夹（如 `旅行计划产物-成都重庆6日-0921/`，建在用户当前工作区根下），后续**所有**写入动作都只落在这个文件夹里。禁止把行程 JSON、临时脚本、测试页、.bak 等散落到工作区根目录、skill 自身目录或其他无关目录。
- **终版确认（必须弹窗选择题，不许跳过）**：首次渲染成功、准备交付前，用 AskUserQuestion 询问「本次是否作为终版？」，选项：
  1. 「终版：清理中间产物，只留最终页面」
  2. 「终版：保留行程 JSON（日后改行程可直接重新渲染）」
  3. 「非终版：继续迭代（保留全部中间产物）」
  同时在弹窗问题文案里列出将被删除的文件清单，让用户知情后确认。
- **终版清理动作**：用户选终版后，删除产物文件夹内除选择保留文件之外的一切中间产物（草稿/测试 JSON、测试渲染页、.bak、临时脚本、空子目录）；若曾在产物文件夹之外创建过任何临时文件，一并清理。清理后列举目录确认只剩目标文件。
- **再次迭代**：非终版继续迭代时沿用同一产物文件夹，不许新开散落文件；交付时告知用户产物文件夹路径与清理结果。

## Step 7: 交付前自检（逐项确认后再 present_files）

- [ ] 打开生成的 HTML：地图区域 3 秒内出瓦片（最迟 10 秒内无看门狗红条提示）。
- [ ] 左侧每个 POI 点开后，中栏画廊有 2~4 张真实照片，无"暂无照片"。
- [ ] 页面主题凸显目的地城市特色：主色/渐变呼应城市性格（如北京=皇城红），**整页背景为该城实景大图（heroImage，如天安门/熊猫）且加载成功、非破图，多城行程切换 Tab 时背景与主色整套换肤**，头部/标题区有代表性地标元素，非通用默认皮。
- [ ] **三栏（左地点/中画廊/右地图）顶底对齐等高（设计高度 800px）**；**缩放自适应**：在小显示器（如 1366×768）上整页等比缩小完整可见、不出现裁切或滚动条。
- [ ] **产物文件夹干净**：终版已清理中间产物（文件夹内只剩最终 HTML 或 HTML+行程 JSON），工作区无散落的临时文件。
- [ ] 中栏顶部出现「🏨 住宿范围建议」卡片，内容与所选城市联动。
- [ ] Day 1 从抵达站/抵达时间写起；末日含返程接驳。
- [ ] 天气卡片与访谈日期一致（Open-Meteo 16 日预报内）。
- [ ] 九项访谈答案全部体现在页面（出发地/目的地/日期/天数/交通含跨城/人数/偏好/住宿/返程地点）。

交付时说明：文件自包含、双击即可打开；地图与图片需联网；更换 Trip 只需重生成 JSON；同时告知产物文件夹路径与终版清理结果。

## Environment Notes (observed 2026-09, Windows sandbox)

- This sandbox's Bash shell has **no outbound network by default**; even with `dangerouslyDisableSandbox` most image hosts are blocked. Verified reachable: `api.open-meteo.com` (weather ✓), `images.unsplash.com` (direct photos only), `live/farm*.staticflickr.com`, `picsum.photos`, `www.bing.com` (home only). **Blocked**: all `*.wikimedia.org` (incl. `upload.wikimedia.org`), `api.flickr.com`, `api.openverse.org`, `duckduckgo.com`, `source.unsplash.com` (503, deprecated), Bing image scraping (returns 175 B), `loremflickr.com` (500).
- `WebFetch` proxy is also heavily restricted (fails on wikipedia/commons/flickr). `WebSearch` works but returns page text, not raw image URLs.
- **Images for China-based users**: `*.wikimedia.org` is **blocked/unreachable in mainland China** — do NOT use Wikimedia Special:FilePath for CN users (images show blank for them even though they render elsewhere). Baidu Baike / Baidu Image / Duitang APIs are all bot-blocked from the sandbox too. **The reliable CN-accessible photo source is Amap's own CDN** (`aos-cdn-image.amap.com`).
  - Best pattern: keep `photos` as a single clean placeholder data-URI per POI (so the render gate passes without `--allow-empty-photos` and no broken images), then have the template fetch real POI photos at runtime via `AMap.PlaceSearch` (JS plugin) keyed on the **same JS API key** that powers the map. One key → map + real photos. Stripping parentheticals from POI names (e.g. `故宫博物院（午门进）`→`故宫博物院`) before the PlaceSearch query improves match rate.
  - If the user supplies an Amap **Web服务** key, you can also pre-fetch `poi.photos` via `restapi.amap.com/v3/place/text` from the sandbox (reachable) and embed the `aos-cdn-image.amap.com` URLs statically — deterministic and verifiable.
- Render with `dangerouslyDisableSandbox` so Open-Meteo weather is fetched live; without it weather is empty (script catches the failure gracefully).

## Resources

### scripts/
- `render_itinerary.py` — Main generator. `--input` (JSON file/stdin), `--output`；`--check-config` 查看密钥状态；`--amap-key`/`--amap-security`（或 JSON `amap` 字段 / 环境变量 / 配置文件）提供双密钥，未配置 exit 5。内置密钥校验、缺图校验、占位符残留校验；自动抓取 Open-Meteo 天气与主题。
- `setup_amap.py` — 高德双密钥配置向导（交互/非交互 `--key --security --scope`、`--show` 掩码展示、`--check` 在线校验）。

### assets/
- `template.html` — 完整 HTML 模板，CSS/JS 自包含；数据经 `{{...}}` 占位符注入；地图带渲染看门狗与失败排查提示；中栏含住宿建议卡片。**默认输出风格基准 = 城市主题背景玻璃风**：全屏城市背景图（`cityThemes[城市].heroImage` 驱动 `CITY_SKINS`，切城市整套换肤）+ 横幅全透明 + 约50%半透明玻璃卡片；左/中/右三栏以 800px 设计高度顶底对齐；`fitPage()` 按视口等比缩放（--app-zoom），小屏不裁切、大屏观感一致。

### references/
- `api_guide.md` — 完整字段 schema（含 accommodation/amap 块）、高德双密钥申请与排错、Open-Meteo 接口、主题映射表。
