# zmftft · 云顶攻略台

> 一张**当前版本、可一键刷新**的中文云顶之弈（TFT）参考页：羁绊 × 站位、推荐出装、装备合成，全在一页。

**在线访问：** https://cz999-1.github.io/zmftft/ （装备合成直达 [`#craft`](https://cz999-1.github.io/zmftft/#craft)）

---

## 核心诉求

中文玩家想查「这个羁绊谁站前排」「这张卡带什么装」「两个散件合成什么」时，往往要：

- 翻英文数据站，名字对不上中文客户端；
- 看网上流传的旧图，赛季早已更新，装备和羁绊都对不上。

zmftft 的目标很简单：**用最新数据自动生成一张中文、当前赛季的速查页**，换版本时重跑脚本即可，不靠手工做图。

## 解决了哪些问题

| 问题 | zmftft 的做法 |
| --- | --- |
| 不知道玩什么阵容 | 首页和「阵容」页：tactics.tools 主流阵容组按场次（人气）列出，op.gg 式卡片（羁绊、八人阵容、3★ / 成装标记）+ 每组详情页；不是强度排行，强度评级标「待验证」 |
| 开局拿了一手某羁绊，不知道往哪变 | 「变阵路线」页：每个有 1/2 费英雄的羁绊一页，5级开局 → 7级中期 → 终局的变阵树（OP.GG 官方数据接口的三阶段路线，带回合胜率与拿牌/换下差异；回看式统计，不是拿牌建议） |
| 不清楚羁绊里谁站前/中/后排 | 职业、起源两张矩阵：每个羁绊 × 前排 / 中排 / 后排，列出对应英雄 |
| 英雄费用一眼看不出 | 卡片按费用着色，并显示选取率和满装率（不再显示平均名次和前四率：它们来自最终棋盘，高费卡、后期才成型的卡天然名次更好） |
| 不知道带什么装 | 每个英雄列出出场最多的二件套 / 三件套，附吃鸡率（全体基线 12.5%）与场次 |
| 装备合成表过时 | 当前 Set 18 的 10×10 散件合成矩阵（含金铲铲 / 金锅锅），附纹章与冠冕清单 |
| 找某个英雄/羁绊太慢 | 顶部搜索框 + 费用/位置过滤器 |
| 名称是英文 | 英雄、羁绊、装备名称全部取自官方简体中文数据 |

## 怎么做的

```
tactics.tools（英雄出装 / 羁绊表现统计）  ┐
Community Dragon zh_cn（中文名称、图标、合成配方）┤→ Python 脚本 → 8 个 HTML 页面 + 详情页 → GitHub Pages
OP.GG 官方 MCP 接口（meta 阵容三阶段路线）  ┘
```

- **数据源**
  - [tactics.tools](https://tactics.tools/zh/units)：英雄选取率、成装数分布（满装率）、出装统计、主流阵容
  - [Community Dragon](https://raw.communitydragon.org/)：英雄中文名、费用、羁绊归属、头像/装备图标、装备配方（`zh_cn.json`）
  - [OP.GG 官方 MCP 接口](https://github.com/opgginc/opgg-mcp)（`mcp-api.op.gg/mcp`，MIT）：meta 阵容与各套的 5级/7级/终局三阶段棋盘、回合胜负计数（变阵路线页）。**op.gg 网站条款明文禁止抓取页面**（policies/agreement，2026-11-05 读取），本站因此只用这个它家主动提供的程序接口，不抓网页，页面注明来源
- **人工标注** `sets/set<N>.json`（官方数据里没有的部分）：羁绊类型（职业 / 种族）与行顺序、每个英雄的前/中/后排、要隐藏的 id（拉克丝的羁绊形态）、改名。按 id 写，名字只为方便阅读
- **生成脚本**（只用 Python 标准库，无第三方依赖）
  - `fetch_data.py`：每个数据源只请求一次，原始响应缓存在 `cache/raw/`（已 gitignore，6 小时内复用），只把页面用到的字段存成快照 `cache/snapshots/set<N>/<patch>.json`（带 set、版本、分段、tactics.tools 数据更新时间、抓取时间、来源）。快照**不入库**：仓库里只有由它生成的页面和它的 SHA-256（见「页面数据快照」）
  - `generate_tft_table.py`：抓取工具、组装英雄表（官方中文名与费用 + `sets/` 里的人工标注）、出装
  - `checks.py`：构建护栏，每次存快照和生成页面前都跑；不通过就退出、什么都不写（问题列表会打印出来，快照留在 `cache/failed_snapshot.json` 供排查）。检查：Community Dragon、tactics.tools 页面标题和 `sets/` 文件的赛季号一致；tactics.tools 的每个英雄 id 都在官方数据里；矩阵里每个英雄有中文名、1–5 费、图标、站位，人工标注里的名字和官方一致；用到的每个羁绊都标了职业或种族；棋盘数、阵容数、合成表大小在合理范围；阵容组块（`comp_groups`）的分组和 `comps` 一致、只有白名单字段（`checks.GROUP_FIELDS`，玩家名 `topPlayers` 等永远不进快照）、名次分布与终局等级分布的合计对得上棋盘数；羁绊图标固定在版本目录
  - `tests/`：`python3 -m unittest discover -s tests`（标准库，不联网；用 `tests/fixture.py` 生成的假快照：真实 id 和名字、编造的数字。本地 `cache/snapshots/` 里有真实快照时也检查它）
  - `craft.py`：从 Community Dragon 读取当前赛季配方，生成装备合成矩阵、纹章、冠冕
  - `comps.py`：阵容卡片、阵容页和每组详情页 `comps/<hash>.html`（见「阵容」）
  - `opgg.py`：OP.GG 官方 MCP 接口的最小客户端（一次 `tft_list_meta_decks` 调用）+ 白名单抽取（`checks.OPGG_*`）
  - `trees.py`：变阵路线页和每个开局羁绊的详情页 `trees/<hash>.html`（见「变阵路线」）
  - `build_site.py`：把以上内容组装成多页站点（共享顶部导航，内联 CSS/JS）：`index.html` 首页（阵容卡片 + 下线说明 + 各页入口）、`comps.html` 阵容、`class.html` 职业站位、`origin.html` 种族站位（只有 1 名英雄的种族合并为「单一英雄种族」一行）、`heroes.html` 英雄数据（见「英雄数据」）、`craft.html` 装备合成；页面间用相对链接互跳，旧的 `#craft` 等锚点会自动跳到新页面；有装备图标的页面上悬停（手机上点按）图标显示合成配方：两件散件和效果，取自快照里的合成表（tactics.tools 用新 id、合成表用 Riot 的旧 api 名的装备按中文名对上；`#itd` 按页生成，恰好覆盖该页显示的装备）
- **部署**：根目录的 `*.html` 和 `comps/`、`synergy/`、`trees/` 三个详情页目录推到 `main`，由 GitHub Pages 直接托管
  - 根目录的 `riot.txt` 是 Riot 开发者平台验证本站网址用的：申请 production key 时 Riot 给的验证码，文件里只有这串码。2026-11-01 重填申请后换过一次码。构建不碰它；只在 Riot 换码时改它，同时改 `tests/test_site.py` 里的 `RIOT_TXT`。测试会检查它还在、内容没变（只忽略结尾一个换行）

### 数据从哪来（分工）
| 来源 | 角色 |
|---|---|
| **Riot Data Dragon**（官方，免 key） | 当前版本号、英雄/装备/羁绊官方中文名与费用、官方图标；目前构建不使用（`python3 -m data.riot.ddragon` 可单独拉取） |
| **Riot TFT Match API**（官方，需 key） | 本地小样本自检、与 tactics.tools 对比；不上页面（样本太小，而且开发 / 个人 key 的数据按 Riot 规定不能用于公开站点） |
| **Community Dragon** | 现有主数据：完整游戏文件解包（英雄中文名、费用、羁绊归属、羁绊效果数值、合成配方、技能描述、更全的图标），更新最快 |
| **tactics.tools** | 大样本统计：选取率、成装数、出装、主流阵容 |
| **OP.GG 官方 MCP 接口** | meta 阵容的三阶段路线（5级/7级/终局 + 回合胜负计数），变阵路线页专用；它家应用的对局内采集，是 Riot Match API 没有的过程数据 |

详见 [data/riot/README.md](data/riot/README.md)。

#### Riot 官方源 vs Community Dragon 对比

| 维度 | Riot Data Dragon | Riot Match API | Community Dragon |
|---|---|---|---|
| 字段 | id、中文名、费用、羁绊归属、图标路径；效果文案/数值不全 | 对局参与者：名次、等级、英雄+星级+装备、激活羁绊 | 游戏文件解包：技能描述与数值、羁绊各档效果、装备合成配方、完整图标 |
| 覆盖 | 当前及历史赛季静态数据（多语言） | 真实排位对局（需 key，限流 20/s、100/2min） | 当前赛季 + PBE，含未公开/测试数据 |
| 更新频率 | 随正式补丁发布，常滞后数天 | 实时 | 补丁/PBE 推送后很快更新 |
| 需要 key | 否 | 是（RIOT_API_KEY） | 否 |

**分工**：Community Dragon 是页面与合成表的主数据（中文名、费用、羁绊归属都从这里读）；Match API 小样本自检并与 tactics.tools 对比；tactics.tools 提供大样本选取率与出装统计。

#### 配置 Riot key（只在本地）
`cp .env.example .env`，填 `RIOT_API_KEY=`（`.env`、`config.local*`、`data/riot/riot.local.json`、`data/riot/cache/` 均已 gitignore）。然后：
```bash
./scripts/refresh_riot.sh   # = python3 -m data.riot.refresh；无 key 时只拉 Data Dragon 并跳过 Match API
```

### 刷新数据

```bash
python3 -m data.riot.match_api   # 可选，需 RIOT_API_KEY；随后 python3 -m data.riot.compare
python3 build_site.py            # 抓取 → 存快照 cache/snapshots/set<N>/<patch>.json → 只从快照生成页面
python3 build_site.py --no-cache # 强制重新抓取（不用 cache/raw/）
python3 build_site.py --data cache/snapshots/set18/18.6.json   # 只用已有快照重新生成页面，不联网
# 把下面「页面数据快照」那一行换成新快照的文件名和 SHA-256（build_site.py 最后会打印）
git add *.html comps synergy trees README.md && git commit -m "refresh data" && git push
```

`fetch_data.py --offline` 需要 `cache/raw/` 里有全部原始响应（包括 `opgg_meta_decks.json`）：加上 OP.GG 源之后，先联网跑过一次才能离线重建。

新赛季上线后，Community Dragon 与 tactics.tools 更新数据，重跑即可；赛季编号相关的过滤在脚本中自动检测/可调整。

### 页面数据快照

快照只存在本地（`cache/` 已 gitignore），不进仓库，也不会被 GitHub Pages 发布。现在的页面由这一份生成：

| 快照 | SHA-256 | 内容 |
|---|---|---|
| `cache/snapshots/set18/18.6.json` | `fe2a587da1e5cf7af95ee410093aa958df96281bd1dbffce7d5321a893d1bdbb` | tactics.tools 18.6 · 排位 · 钻石以上，513,646 个棋盘（18.6 刚上线，样本还在累积），数据截至 2026-11-06 01:50 UTC；抓取于 2026-11-06 02:45 UTC。新增 `opgg_decks`：OP.GG 官方 MCP 接口的 10 套 meta 阵容三阶段路线（白名单字段 `checks.OPGG_*`，无任何玩家字段）。Community Dragon 数据取自 latest（16.22.8348910），图片固定在 `16.22` 目录（18.5c 页面用的是 16.21：钉目录就是为了换版本后旧图不被 latest 带走）。上一份 18.5c 快照（sha `424cd584…`）留在本地 `cache/snapshots/` |

核对：`python3 -c "import fetch_data; print(fetch_data.sha256('cache/snapshots/set18/18.6.json'))"`。快照按 LF 换行写，同一份数据在任何系统上哈希相同；用它跑 `python3 build_site.py --data …` 应得到和仓库里一模一样的页面。

**图片地址固定在版本目录。** 页面里的头像和装备图都指向 `raw.communitydragon.org/<版本>/…`（抓取时 latest 对应的补丁目录，例如 `16.21`），不指向 `latest/`：游戏换到 Set 19 后，latest 里的 Set 18 图会变或消失，固定目录里的不会。护栏会拒绝没有版本目录的快照。推送前可以联网检查一遍：`python3 checks.py --images`（每个图片地址发一次 HEAD 请求，约 160 个，40 秒左右）。以后自托管图片时再换掉。

## 页面结构

1. **顶栏**：版本标识、搜索框、过滤器、区块导航
2. **首页**：阵容卡片（同「阵容」页）+ 已下线的板块和原因（见下文）+ 各页入口
3. **阵容**（`comps.html` + `comps/<hash>.html`）：主流阵容组按场次排列 + 每组详情（见下文「阵容」）
4. **变阵路线**（`trees.html` + `trees/<hash>.html`）：每个 1/2 费开局羁绊的变阵树（见下文「变阵路线」）
5. **职业矩阵 / 起源矩阵**：羁绊 × 前中后排的英雄卡片（费用、数据、二/三件套）
6. **英雄数据**（`heroes.html`）：全英雄 选率 / 吃鸡率 / 均名 排序 + 最高吃鸡出装 + 悬停面板（见下文「英雄数据」）
7. **装备合成**（`#craft`）：Set 18 散件 10×10 矩阵 + 纹章 + 冠冕

## 非目标

- 不是完整的阵容模拟器或棋盘编辑器
- 不替代游戏客户端或专业数据站，统计数据以来源站为准
- 站位为本站人工标注（`sets/set<N>.json`）的参考，不是唯一正确答案；以前写“按职业推断”，其实 65 个英雄全是手写的

## 致谢

数据与图标来自 tactics.tools、Community Dragon 与 OP.GG（变阵路线页，经其官方 MCP 接口）。本项目与 Riot Games 无关；《云顶之弈》及相关素材版权归 Riot Games 所有。每个页面的页脚都有 Riot 对粉丝作品要求的声明，原文照抄自 [riotgames.com/en/legal](https://www.riotgames.com/en/legal)（Legal Jibber Jabber 第 6 条），只填入了本站名称。页脚还有 Riot 开发者政策要求第三方产品展示的法律声明（legal boilerplate），原文照抄自 [developer.riotgames.com/policies/general](https://developer.riotgames.com/policies/general)（Core Policies，2025-05-29 版），同样只填入了本站名称。

## Set 迁移清单（新赛季上线时）

代码里已经没有写死的赛季号：赛季从 Community Dragon 的图标路径识别，再和 tactics.tools 页面标题核对；装备 id 前缀按 `TFT<数字>_Item_` 通配。新赛季要做的：

1. `python3 build_site.py --no-cache`：护栏会报“缺少 sets/set19.json”并停下，快照留在 `cache/failed_snapshot.json`。
2. `python3 checks.py --skeleton cache/failed_snapshot.json`：生成 `sets/set19.json` 草稿，所有英雄站位是 `"?"`，所有羁绊在 `"untyped"` 里。
3. 手工编辑 `sets/set19.json`：
   - 把 `"untyped"` 里的羁绊分到 `"classes"`（职业）和 `"origins"`（种族），顺序就是页面上的行顺序，然后删掉 `"untyped"`；
   - 每个英雄填 `front` / `mid` / `back`；
   - 有多种形态、tactics.tools 分开统计的英雄（像 Set 18 的拉克丝），形态 id 放进 `"hide"`；基础形态要改名的放进 `"rename"`。
4. 再跑 `python3 build_site.py`，直到护栏通过；再跑 `python3 -m unittest discover -s tests` 和 `python3 checks.py --images`。
5. 护栏在这些情况也会停，需要改代码：
   - 基础散件不是 10 个（`craft.py` 的 `COMPS`）；
   - 英雄数、棋盘数等超出 `checks.py` 的 `BOUNDS`；
   - tactics.tools 页面上的筛选文字（「排位模式 钻石以上 18.5c」）或标题（「Set 18」）换了格式（`fetch_data.py` 的 `units_page`）。
6. 旧赛季的快照留在本地 `cache/snapshots/set18/`（不入库）；README 里 Set 18 的例子按需更新。
7. 变阵路线页自动跟随：OP.GG 官方接口只给当前赛季，英雄/羁绊 id 经新赛季的官方数据解析，开局羁绊从「有 1/2 费英雄」推导。两种情况要人工动手：护栏报「不在官方表里（新召唤物？）」时在 `checks.py` 的 `OPGG_SUMMONS` 登记新战斗召唤物；接口返回结构变了时 `opgg.py` 会大声报错（原始响应在 `cache/raw/opgg_meta_decks.json` 可离线排查）。

## 已下线的板块（2026-11-01）

首页的「最强阵容」「冷门高胜率」「三星价值」「羁绊强度」、种族页的「站位结论」和英雄卡上的「阵眼—三星 / 阵眼—装备」标签已删除。

- 它们都只看对局结束时的**最终棋盘**。三星、满 3 件装、高费卡、高档羁绊都要活得够久才凑得出，所以出现它们的棋盘名次本来就好，不论它们本身有没有用（幸存者偏差）；强阵容、运气和技术又同时带来这些状态和好名次（混杂）。
- 例（2026-10-30 的页面）：「三星价值」前 8 名全是 4 费、3★ 均名 1.1–1.4；「羁绊强度」取各档均名的最小值，最高档通常只有赢家能到；13 个「阵眼—装备」里有 6 个是本站标为前排的单位。
- 在已知真值的模拟检验里（tft-lab 项目），「三星价值」这种算法把三星的好处高估了 1.7–2.0 个名次，并且在追三星其实不划算的情形里总是建议追。
- 阵容强度目前还无法从最终棋盘可靠测出，测出之前首页不放阵容排行。2026-11-03 起首页和「阵容」页按**场次（人气）**列出主流阵容组：这是描述，不是排行，每组强度评级标「待验证」（见下文「阵容」）。
- 「阵眼—装备」换成英雄卡上的**满装率**：该英雄在场的棋盘里拿着 3 件成装的比例（tactics.tools 的 `itemCountData`）。它说明玩家把装备给谁，不说明给它装备更能赢。按阵容拆开的装备分配（每个阵容里各英雄拿了多少成装）从 2026-11-03 起在「阵容」页显示，数据取自 tactics.tools 的阵容组（`carryUnits` / `unitItemCounts`）；tft-lab 自采的同类数据（开发 / 个人 key，不能上公开站点）只在本地 `--riot-comps` 预览构建里渲染（heroes.html 的「3★ 满装 · 所在阵容」面板同理：只在 `--riot` 预览里有，线上构建显示「暂无自采样本」）。
- 「英雄数据」页（2026-11-01）重新给出全英雄的 选率 / 吃鸡率 / 均名 与最高吃鸡出装：同样是最终棋盘统计，页顶与每行都带偏差说明、样本量与 C 级标注——它描述玩家行为与结果，不是强度结论。

## 阵容（首页 + comps.html，2026-11-03）

照 op.gg 阵容页的呈现方式（https://op.gg/zh-cn/tft/meta-trends/comps），数据是 tactics.tools 阵容页的 5 个阵容组（每组一套阵容 + 最多 9 个展示变体，快照 `comp_groups` 与 `comps`；tactics.tools 的变体列表里有逐字重复的行，构建时去重，所以页面上是 6–9 个）。首页和 `comps.html` 是同一组卡片，`comps.html` 多一段口径说明；每组有详情页 `comps/<hash>.html`（`comps.py`，每次构建清空重写）。

- **排序**：按场次（人气），**不是强度排行**；每张卡写「强度评级：待验证」。阵容强度要等 tft-lab 的阵容表合并和新的预注册检验（tft-lab `reports/comp_merge_instructions.md`）
- **卡片**：场次、选率（场次 / 全部棋盘）、均名、前四率、吃鸡率，每项旁边写主流阵容组的加权基线（随快照变动，页面上注明；均匀基线 4.50 / 50% / 12.5%）；本组 ≥ 50% 棋盘激活的羁绊（官方激活人数，如 峡谷野怪 7）；八人阵容（出场最多的变体，按费用排）
- **★★★**：该英雄 3★（含 4★）占本组棋盘 ≥ 50% 金色、20%–50% 灰色，取自 tactics.tools 的星级行。tactics.tools 自己的 `starUnits` 不用：它的目标星级随费用变（五费记的是 2★）。**1st / 2nd / 3rd**：本组每盘平均持有成装最多的三个英雄，头像下是它最常带的 3 件。两者都描述玩家怎么玩，页面写明不是“该追三星 / 该给谁装备”的建议
- **详情页**：羁绊各档（高亮最常见档位）、英雄与装备（出场、星级分布、每盘成装、满装率、常带成装与两件组合的场次和占比——不给均名，场次 < 500 淡化）、名次分布（虚线 = 12.5%）、终局等级**只给分布**（各等级均名几乎由活了多久决定，不放）、去重后的变体（附“差别主要反映棋盘成型到哪一步”的说明，场次 < 500 淡化）、站位示意（**人工标注**，非实测站位）、相似阵容、tactics.tools 阵容码（可复制）
- **为什么没有**：「重置次数」「推荐强化符文」和实测站位需要对局过程中的逐阶段数据；本站的数据源只有最终棋盘（Set 18 的对局数据里也没有强化符文字段），页面用一个灰框说明。逐等级路线由「变阵路线」页部分补上（OP.GG 官方接口的 5级/7级/终局三阶段，外部数据、非本站实测），灰框也这么写

## 变阵路线（trees.html + trees/<hash>.html，2026-11-05）

每个**有 1/2 费英雄的种族/职业**一张卡（开局羁绊，逐赛季从官方数据推导；Set 18 有 21 个），有数据的链接到该羁绊的变阵树页：**树根 = 5级开局棋盘**（该羁绊 ≥ 2 名英雄），往下是 **7级中期**，叶子 = **终局阵容**；同一开局/中期（OP.GG 的 deckId 相同）只画一个节点，于是不同终局在它下面分叉——例如 峡谷野怪 开局 → 同一个 7级中期 → 三种终局（远古巨龙+纳尔塔里克 / 远古巨龙+茂凯德莱文 / 九野怪 reroll，含深红锋喙鸟）。分叉节点的回合计数为走到下方任一终局的对局共用，页面原文注明。

- **数据**：OP.GG 官方 MCP 接口的 meta 阵容（当前 10 套；见「数据源」的合规说明——网页抓取被其条款禁止，本站只用官方接口）。覆盖不到的开局羁绊标「暂无路线」
- **每个节点**：棋盘（按费用排，亮框 = 相比上一阶段新增）、**回合胜率**（该阶段 board 的战斗回合 win/play，带回合数）、拿牌/换下差异行、羁绊行；终局行另有 3★ 标记、常带装备（悬停看配方）、场次 / 均名 / 前四 / 吃鸡 / 每局选取与「OP.GG 评级」徽章、可复制的阵容码
- **口径（页面原文注明）**：回看式统计——样本是最终成型为该阵容的对局，含幸存者偏差，描述“成型者当时拿了什么”，不是拿牌建议；终局行按 OP.GG 均名排序（**OP.GG 数据，非本站评级**），本站的强度评级仍为「待验证」；战斗召唤物不显示（脚注计数）；评级 C（描述性）
- 这一页的页脚来源行是 OP.GG 官方接口，不是 tactics.tools（`build_site.py` 按页替换）

### 自采阵容数据（仅本地预览，2026-11-03）

传入 `--riot-comps`（tft-lab 的 comps 导出）时，`comps.html` 加一张「自采对局对照」表（行顺序同卡片），每个详情页加「自采数据」一节：棋盘、自采选率、均名、前四率、吃鸡率（都带 95% 区间，按“场”整群自助法）、名次与终局等级分布、羁绊档位、每个英雄的出场 / 3★ / 成装份额 / 满装率和常见成装组合。阈值与口径预注册于 tft-lab `reports/comps_prereg.md`（SHA-256 `ca351f23…`），方法见 `reports/comps_na_master_18_5.md`。

```bash
# tft-lab 仓库里（读冻结的第一轮自采库，不联网；快照提供阵容分组）：
python -m tftlab.report.comps_export --db data/frozen/tftlab_first_crawl_2026-10-31.sqlite --set 18 --host americas \
    --start 2026-10-22 --end 2026-11-04 --patch 18.5 --snapshot "../zmftft/cache/snapshots/set18/18.5c.json" \
    --out "../zmftft/cache/riot/comps_set18_18.5_americas.json"
# 本仓库里，仅本地预览（开发 / 个人 key 的数据不能上公开站点）：
python3 build_site.py --data cache/snapshots/set18/18.5c.json --riot cache/riot/heroes_set18_18.5_americas.json \
    --riot-synergy cache/riot/synergy_set18_18.5_americas.json --riot-comps cache/riot/comps_set18_18.5_americas.json --out cache/preview
```

不带 `--riot-comps` 构建（= 推上线的版本）时这些都不出现，首页也从不放自采数据。构建护栏核对 schema、赛季号、导出记下的快照 SHA-256 必须等于这份快照（`main`）、阵容组的组号 / 展示阵容 / 变体数 / 场次都和快照一致、英雄和羁绊 id 都在官方表里（`check_riot_comps`）。带任何自采参数（`--riot` / `--riot-synergy` / `--riot-comps`）时，`--out` 只能指向 `cache/` 下，否则构建直接停下（`check_out`），自采数据写不进要提交的页面。

## 英雄数据（heroes.html，2026-11-01）

全部英雄一行一个，可按 **选率 / 吃鸡率 / 均名** 排序、按费用筛选、搜索；每行给出「场数 ≥ 500 的二/三件装组合里**吃鸡率最高**者」（带 `*` 的样本不足，改显示最常见组合）。悬停（手机上点按）头像出面板：各星级的 场数 / 均名 / 吃鸡率（tactics.tools），以及「3★ 满装 · 所在阵容」。页顶注明：均为**最终棋盘的描述统计（C 级）**，高数值主要说明“这局本来就在赢”；跨费用对比主要反映费用差异；每个数字带样本量，页首给出最小样本下的 95% 区间上界。

「3★ 满装 · 所在阵容」的数据**不来自 tactics.tools**（它没有这个联合条件），而来自 tft-lab 的自采对局导出：

```bash
# tft-lab 仓库里（读本地 SQLite，不联网；快照提供阵容分组）：
python -m tftlab.report.heroes_export --db data/frozen/tftlab_first_crawl_2026-10-31.sqlite --set 18 --host americas --start 2026-10-22 --end 2026-11-04 \
    --patch 18.5 --snapshot "../zmftft/cache/snapshots/set18/18.5c.json"
# 本仓库里，仅本地预览（开发 / 个人 key 的数据不能上公开站点，见「数据从哪来」）：
python3 build_site.py --data cache/snapshots/set18/18.5c.json --riot cache/riot/heroes_set18_18.5_americas.json --out cache/preview
```

不带 `--riot` 构建（= 推上线的版本）时，该面板显示「暂无自采样本」。导出文件自带 `publishable: false` 与人群说明（NA · 种子大师+ · 补丁窗口 · 棋盘数）；构建护栏核对 schema、赛季号与阵容组引用。n < 20 的格子一律「不显示」，未归入任何阵容组的棋盘单独计数。

## 羁绊搭配（synergy.html）

`synergy.html` 有两个矩阵：**种族 × 种族** 和 **种族 × 职业**（行 = 种族，列 = 职业）。每格显示**均名**或**吃鸡率**（页顶按钮切换，两个矩阵一起切；不开 JS 时固定显示均名）加**选率**（不着色）；点格子进入静态详情页 `synergy/<hash>.html`，列出该搭配下所有英雄组合的均名 / 前四 / 吃鸡 / 场次 / 选率 / 格内占比。

- **“带了”某羁绊**（种族或职业同一口径）：阵容中该羁绊英雄 ≥2 名（单一英雄羁绊 ≥1），阈值见 `synergy.py` 的 `MIN`
- **英雄组合（变体）**：阵容里属于这两个羁绊的英雄集合；相同集合合并统计
- **数据**：tactics.tools 主流阵容（team-compositions，按场次加权）；选率 = 场次 / 全部棋盘数。页面写明这些棋盘的平均名次（不是 4.5）和总吃鸡率（对 12.5% 均匀基线），格内数字要和这两个数比
- 均名和吃鸡率都是最终棋盘统计：数字好的搭配多半是“这局本来就在赢”的棋盘，不说明照这样搭就能赢
- 行/列标题悬停显示该羁绊**前/中/后排各有几个不同英雄**（站位是 `sets/set<N>.json` 的人工标注）
- **只有一个五费英雄的羁绊**整行/列标橙（标题 title 注明原因）：五费英雄搭配什么都强，这类格子参考价值低。判定从数据推导（恰好一个英雄且费用 ≥5），见 `synergy.py` 的 `_solo5`
- **协同差**（第三个指标）：格内均名 −（两羁绊各自边际均名之和 − 基线），负数 = 好于“两边平均水平叠加”的预期；边际含该格自身，是描述性对比，不是因果交互，仅在跨多个阵容组的格子里才略有参考。一个羁绊的棋盘全部同时带另一个时（嵌套），协同差恒等于“基线 − 另一羁绊的边际均名”，无从定义，格子显示 —
- **灰字格** = 该格棋盘全部来自同一个阵容组（tactics.tools 的主流阵容分组，格子 title 写了组数）：数字只描述那一套阵容的最终棋盘（不代表强度），不是这对羁绊的性质；橙色行里的灰字格保留橙色底、文字变灰；**淡化格** = 场次 < 1000（`synergy.py` 的 `THIN`）
- 以前只有 Riot 抽样（几个棋盘）的格子和详情页已删除
- 由 `python3 build_site.py` 一并生成

### 自采对局搭配矩阵（仅本地预览，2026-11-01）

传入 `--riot-synergy`（tft-lab 的 synergy 导出）时，页面在两个矩阵下方追加「自采对局搭配矩阵」：
同样的 种族×种族 / 种族×职业 两张表、同一个指标切换按钮，但**口径不同**——“带了”=对局结束时游戏
判定该羁绊已激活（Riot 字段 `tier_current ≥ 1`，纹章也算），统计自采的全部排位棋盘，不限主流阵容。
每格悬停显示 均名 / 吃鸡率 / 协同差 的 95% 区间（按“场”整群自助法）与 盘数/场数；格子没有详情页。
职业×职业与未展示羁绊的配对只计数不入矩阵；n 低于导出阈值的配对在导出时已隐去（页面写明删了多少）。

```bash
# tft-lab 仓库里（读本地 SQLite，不联网；阈值与口径预注册于 tft-lab reports/synergy_pairs_prereg.md）：
python -m tftlab.report.synergy_export --db data/frozen/tftlab_first_crawl_2026-10-31.sqlite --set 18 --host americas --start 2026-10-22 --end 2026-11-04 \
    --patch 18.5 --out "../zmftft/cache/riot/synergy_set18_18.5_americas.json"
# 本仓库里，仅本地预览（开发 / 个人 key 的数据不能上公开站点）：
python3 build_site.py --data cache/snapshots/set18/18.5c.json --riot cache/riot/heroes_set18_18.5_americas.json \
    --riot-synergy cache/riot/synergy_set18_18.5_americas.json --out cache/preview
```

不带 `--riot-synergy` 构建（= 推上线的版本）时整节不出现。导出自带 `publishable: false`、评级 C、
估计量说明与人群说明；构建护栏（`check_riot_synergy`）核对 schema、赛季号，并逐一核对羁绊 apiName
都在快照的官方羁绊表里，对不上就拒绝构建。
