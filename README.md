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
| 不清楚羁绊里谁站前/中/后排 | 职业、起源两张矩阵：每个羁绊 × 前排 / 中排 / 后排，列出对应英雄 |
| 英雄费用一眼看不出 | 卡片按费用着色，并显示平均名次、前四率、选取率（最终棋盘统计，只宜同费用内参考，不代表强度） |
| 不知道带什么装 | 每个英雄列出出场最多的二件套 / 三件套，附吃鸡率（全体基线 12.5%）与场次 |
| 装备合成表过时 | 当前 Set 18 的 10×10 散件合成矩阵（含金铲铲 / 金锅锅），附纹章与冠冕清单 |
| 找某个英雄/羁绊太慢 | 顶部搜索框 + 费用/位置过滤器 |
| 名称是英文 | 英雄、羁绊、装备名称全部取自官方简体中文数据 |

## 怎么做的

```
tactics.tools（英雄出装 / 羁绊表现统计）  ┐
Community Dragon zh_cn（中文名称、图标、合成配方）┤→ Python 脚本 → 4 个 HTML 页面 → GitHub Pages
```

- **数据源**
  - [tactics.tools](https://tactics.tools/zh/units)：英雄名次、前四率、选取率、出装统计、羁绊表现
  - [Community Dragon](https://raw.communitydragon.org/)：英雄中文名、费用、羁绊归属、头像/装备图标、装备配方（`zh_cn.json`）
- **人工标注** `sets/set<N>.json`（官方数据里没有的部分）：羁绊类型（职业 / 种族）与行顺序、每个英雄的前/中/后排、要隐藏的 id（拉克丝的羁绊形态）、改名。按 id 写，名字只为方便阅读
- **生成脚本**（只用 Python 标准库，无第三方依赖）
  - `fetch_data.py`：每个数据源只请求一次，原始响应缓存在 `cache/raw/`（已 gitignore，6 小时内复用），只把页面用到的字段存成快照 `cache/snapshots/set<N>/<patch>.json`（带 set、版本、分段、tactics.tools 数据更新时间、抓取时间、来源）。快照**不入库**：仓库里只有由它生成的页面和它的 SHA-256（见「页面数据快照」）
  - `generate_tft_table.py`：抓取工具、组装英雄表（官方中文名与费用 + `sets/` 里的人工标注）、出装
  - `checks.py`：构建护栏，每次存快照和生成页面前都跑；不通过就退出、什么都不写（问题列表会打印出来，快照留在 `cache/failed_snapshot.json` 供排查）。检查：Community Dragon、tactics.tools 页面标题和 `sets/` 文件的赛季号一致；tactics.tools 的每个英雄 id 都在官方数据里；矩阵里每个英雄有中文名、1–5 费、图标、站位，人工标注里的名字和官方一致；用到的每个羁绊都标了职业或种族；棋盘数、阵容数、合成表大小在合理范围
  - `tests/`：`python3 -m unittest discover -s tests`（标准库，不联网；用 `tests/fixture.py` 生成的假快照：真实 id 和名字、编造的数字。本地 `cache/snapshots/` 里有真实快照时也检查它）
  - `craft.py`：从 Community Dragon 读取当前赛季配方，生成装备合成矩阵、纹章、冠冕
  - `build_site.py`：把以上内容组装成多页站点（共享顶部导航，内联 CSS/JS）：`index.html` 首页（下线说明 + 各页入口）、`class.html` 职业站位、`origin.html` 种族站位（只有 1 名英雄的种族合并为「单一英雄种族」一行）、`craft.html` 装备合成；页面间用相对链接互跳，旧的 `#craft` 等锚点会自动跳到新页面
- **部署**：4 个 `*.html` 推到 `main`，由 GitHub Pages 直接托管

### 数据从哪来（分工）
| 来源 | 角色 |
|---|---|
| **Riot Data Dragon**（官方，免 key） | 当前版本号、英雄/装备/羁绊官方中文名与费用、官方图标；目前构建不使用（`python3 -m data.riot.ddragon` 可单独拉取） |
| **Riot TFT Match API**（官方，需 key） | 本地小样本自检、与 tactics.tools 对比；不上页面（样本太小，而且开发 / 个人 key 的数据按 Riot 规定不能用于公开站点） |
| **Community Dragon** | 现有主数据：完整游戏文件解包（英雄中文名、费用、羁绊归属、羁绊效果数值、合成配方、技能描述、更全的图标），更新最快 |
| **tactics.tools** | 大样本统计：名次、出装 |

详见 [data/riot/README.md](data/riot/README.md)。

#### Riot 官方源 vs Community Dragon 对比

| 维度 | Riot Data Dragon | Riot Match API | Community Dragon |
|---|---|---|---|
| 字段 | id、中文名、费用、羁绊归属、图标路径；效果文案/数值不全 | 对局参与者：名次、等级、英雄+星级+装备、激活羁绊 | 游戏文件解包：技能描述与数值、羁绊各档效果、装备合成配方、完整图标 |
| 覆盖 | 当前及历史赛季静态数据（多语言） | 真实排位对局（需 key，限流 20/s、100/2min） | 当前赛季 + PBE，含未公开/测试数据 |
| 更新频率 | 随正式补丁发布，常滞后数天 | 实时 | 补丁/PBE 推送后很快更新 |
| 需要 key | 否 | 是（RIOT_API_KEY） | 否 |

**分工**：Community Dragon 是页面与合成表的主数据（中文名、费用、羁绊归属都从这里读）；Match API 小样本自检并与 tactics.tools 对比；tactics.tools 提供大样本名次与出装统计。

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
python3 build_site.py --data cache/snapshots/set18/18.5c.json   # 只用已有快照重新生成页面，不联网
# 把下面「页面数据快照」那一行换成新快照的文件名和 SHA-256（build_site.py 最后会打印）
git add *.html synergy README.md && git commit -m "refresh data" && git push
```

新赛季上线后，Community Dragon 与 tactics.tools 更新数据，重跑即可；赛季编号相关的过滤在脚本中自动检测/可调整。

### 页面数据快照

快照只存在本地（`cache/` 已 gitignore），不进仓库，也不会被 GitHub Pages 发布。现在的页面由这一份生成：

| 快照 | SHA-256 | 内容 |
|---|---|---|
| `cache/snapshots/set18/18.5c.json` | `febbbc2ab9df35edd4d35f105d9d812d4bc7d045a0c94515ac6ba55714b35f3f` | tactics.tools 18.5c · 排位 · 钻石以上，1,563,397 个棋盘，数据截至 2026-11-01 15:11 UTC；抓取于 2026-11-01 17:00 UTC |

核对：`python3 -c "import fetch_data; print(fetch_data.sha256('cache/snapshots/set18/18.5c.json'))"`。快照按 LF 换行写，同一份数据在任何系统上哈希相同；用它跑 `python3 build_site.py --data …` 应得到和仓库里一模一样的页面。

## 页面结构

1. **顶栏**：版本标识、搜索框、过滤器、区块导航
2. **首页说明**：已下线的板块和原因（见下文）
3. **职业矩阵 / 起源矩阵**：羁绊 × 前中后排的英雄卡片（费用、数据、二/三件套）
4. **装备合成**（`#craft`）：Set 18 散件 10×10 矩阵 + 纹章 + 冠冕

## 非目标

- 不是完整的阵容模拟器或棋盘编辑器
- 不替代游戏客户端或专业数据站，统计数据以来源站为准
- 站位为本站人工标注（`sets/set<N>.json`）的参考，不是唯一正确答案；以前写“按职业推断”，其实 65 个英雄全是手写的

## 致谢

数据与图标来自 tactics.tools 与 Community Dragon。本项目与 Riot Games 无关；《云顶之弈》及相关素材版权归 Riot Games 所有。

## Set 迁移清单（新赛季上线时）

代码里已经没有写死的赛季号：赛季从 Community Dragon 的图标路径识别，再和 tactics.tools 页面标题核对；装备 id 前缀按 `TFT<数字>_Item_` 通配。新赛季要做的：

1. `python3 build_site.py --no-cache`：护栏会报“缺少 sets/set19.json”并停下，快照留在 `cache/failed_snapshot.json`。
2. `python3 checks.py --skeleton cache/failed_snapshot.json`：生成 `sets/set19.json` 草稿，所有英雄站位是 `"?"`，所有羁绊在 `"untyped"` 里。
3. 手工编辑 `sets/set19.json`：
   - 把 `"untyped"` 里的羁绊分到 `"classes"`（职业）和 `"origins"`（种族），顺序就是页面上的行顺序，然后删掉 `"untyped"`；
   - 每个英雄填 `front` / `mid` / `back`；
   - 有多种形态、tactics.tools 分开统计的英雄（像 Set 18 的拉克丝），形态 id 放进 `"hide"`；基础形态要改名的放进 `"rename"`。
4. 再跑 `python3 build_site.py`，直到护栏通过；再跑 `python3 -m unittest discover -s tests`。
5. 护栏在这些情况也会停，需要改代码：
   - 基础散件不是 10 个（`craft.py` 的 `COMPS`）；
   - 英雄数、棋盘数等超出 `checks.py` 的 `BOUNDS`；
   - tactics.tools 页面上的筛选文字（「排位模式 钻石以上 18.5c」）或标题（「Set 18」）换了格式（`fetch_data.py` 的 `units_page`）。
6. 旧赛季的快照留在本地 `cache/snapshots/set18/`（不入库）；README 里 Set 18 的例子按需更新。

## 已下线的板块（2026-11-01）

首页的「最强阵容」「冷门高胜率」「三星价值」「羁绊强度」、种族页的「站位结论」和英雄卡上的「阵眼—三星 / 阵眼—装备」标签已删除。

- 它们都只看对局结束时的**最终棋盘**。三星、满 3 件装、高费卡、高档羁绊都要活得够久才凑得出，所以出现它们的棋盘名次本来就好，不论它们本身有没有用（幸存者偏差）；强阵容、运气和技术又同时带来这些状态和好名次（混杂）。
- 例（2026-10-30 的页面）：「三星价值」前 8 名全是 4 费、3★ 均名 1.1–1.4；「羁绊强度」取各档均名的最小值，最高档通常只有赢家能到；13 个「阵眼—装备」里有 6 个是本站标为前排的单位。
- 在已知真值的模拟检验里（tft-lab 项目），「三星价值」这种算法把三星的好处高估了 1.7–2.0 个名次，并且在追三星其实不划算的情形里总是建议追。
- 阵容强度目前还无法从最终棋盘可靠测出，测出之前首页不放阵容排行。
- 「阵眼—装备」换成英雄卡上的**满装率**：该英雄在场的棋盘里拿着 3 件成装的比例（tactics.tools 的 `itemCountData`）。它说明玩家把装备给谁，不说明给它装备更能赢。按阵容拆开的装备分配（每个阵容里各英雄拿了多少成装）需要逐局数据，tft-lab 已能算，但开发 / 个人 key 的数据不能上公开站点，所以暂不显示。

## 种族搭配（synergy.html）

`synergy.html` 是 种族 × 种族 矩阵，每格显示该搭配的**均名**和**选率**（不着色）；点格子进入静态详情页 `synergy/<hash>.html`，列出该搭配下所有英雄组合的均名 / 前四 / 吃鸡 / 场次 / 选率 / 格内占比。

- **“带了”某种族**：阵容中该种族英雄 ≥2 名（单一英雄种族 ≥1），阈值见 `synergy.py` 的 `MIN`
- **英雄组合（变体）**：阵容里属于这两个种族的英雄集合；相同集合合并统计
- **数据**：tactics.tools 主流阵容（team-compositions，按场次加权）；选率 = 场次 / 全部棋盘数。页面写明这些棋盘的平均名次（不是 4.5），格内均名要和它比
- 均名是最终棋盘统计：名次好的搭配多半是“这局本来就在赢”的棋盘，不说明照这样搭就能赢
- 以前只有 Riot 抽样（几个棋盘）的格子和详情页已删除
- 由 `python3 build_site.py` 一并生成
