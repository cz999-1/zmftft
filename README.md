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
| 英雄费用、强度一眼看不出 | 卡片按费用着色，显示平均名次、前四率、选取率 |
| 不知道带什么装 | 每个英雄给出胜率较高的二件套 / 三件套推荐 |
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
  - [Community Dragon](https://raw.communitydragon.org/)：简体中文名称、头像/装备图标、装备配方（`zh_cn.json`）
- **生成脚本**（只用 Python 标准库，无第三方依赖）
  - `fetch_data.py`：每个数据源只请求一次，原始响应缓存在 `cache/raw/`（已 gitignore，6 小时内复用），只把页面用到的字段存成快照 `data/<set>/<patch>.json`（带 set、版本、分段、tactics.tools 数据更新时间、抓取时间、来源）
  - `generate_tft_table.py`：抓取工具、映射中文名、推断站位、计算推荐出装
  - `craft.py`：从 Community Dragon 读取当前赛季配方，生成装备合成矩阵、纹章、冠冕
  - `build_site.py`：把以上内容组装成多页站点（共享顶部导航，内联 CSS/JS）：`index.html` 首页（下线说明 + 各页入口）、`class.html` 职业站位、`origin.html` 种族站位（只有 1 名英雄的种族合并为「单一英雄种族」一行）、`craft.html` 装备合成；页面间用相对链接互跳，旧的 `#craft` 等锚点会自动跳到新页面
- **部署**：4 个 `*.html` 推到 `main`，由 GitHub Pages 直接托管

### 数据从哪来（分工）
| 来源 | 角色 |
|---|---|
| **Riot Data Dragon**（官方，免 key） | 当前版本号、英雄/装备/羁绊官方中文名与费用、官方图标；`build_site.py` 每次自动拉取快照校验赛季 |
| **Riot TFT Match API**（官方，需 key） | 偶尔抽样高分段原始对局，算平均名次/三星/满装，用于验证阵容并与 tactics.tools 对比 |
| **Community Dragon** | 现有主数据：完整游戏文件解包（羁绊效果数值、合成配方、技能描述、更全的图标），更新最快 |
| **tactics.tools** | 大样本统计：名次、出装 |

详见 [data/riot/README.md](data/riot/README.md)。

#### Riot 官方源 vs Community Dragon 对比

| 维度 | Riot Data Dragon | Riot Match API | Community Dragon |
|---|---|---|---|
| 字段 | id、中文名、费用、羁绊归属、图标路径；效果文案/数值不全 | 对局参与者：名次、等级、英雄+星级+装备、激活羁绊 | 游戏文件解包：技能描述与数值、羁绊各档效果、装备合成配方、完整图标 |
| 覆盖 | 当前及历史赛季静态数据（多语言） | 真实排位对局（需 key，限流 20/s、100/2min） | 当前赛季 + PBE，含未公开/测试数据 |
| 更新频率 | 随正式补丁发布，常滞后数天 | 实时 | 补丁/PBE 推送后很快更新 |
| 需要 key | 否 | 是（RIOT_API_KEY） | 否 |

**分工**：Data Dragon 负责“官方口径”（版本号、中文名、费用校验）；Community Dragon 仍是页面与合成表主数据；Match API 小样本自检并与 tactics.tools 对比；tactics.tools 提供大样本名次与出装统计。

#### 配置 Riot key（只在本地）
`cp .env.example .env`，填 `RIOT_API_KEY=`（`.env`、`config.local*`、`data/riot/riot.local.json`、`data/riot/cache/` 均已 gitignore）。然后：
```bash
./scripts/refresh_riot.sh   # = python3 -m data.riot.refresh；无 key 时只拉 Data Dragon 并跳过 Match API
```

### 刷新数据

```bash
python3 -m data.riot.match_api   # 可选，需 RIOT_API_KEY；随后 python3 -m data.riot.compare
python3 build_site.py            # 抓取 → 存快照 data/<set>/<patch>.json → 只从快照生成页面
python3 build_site.py --no-cache # 强制重新抓取（不用 cache/raw/）
python3 build_site.py --data data/set18/18.5c.json   # 只用已有快照重新生成页面，不联网
git add *.html synergy data && git commit -m "refresh data" && git push
```

新赛季上线后，Community Dragon 与 tactics.tools 更新数据，重跑即可；赛季编号相关的过滤在脚本中自动检测/可调整。

## 页面结构

1. **顶栏**：版本标识、搜索框、过滤器、区块导航
2. **首页说明**：已下线的板块和原因（见下文）
3. **职业矩阵 / 起源矩阵**：羁绊 × 前中后排的英雄卡片（费用、数据、二/三件套）
4. **装备合成**（`#craft`）：Set 18 散件 10×10 矩阵 + 纹章 + 冠冕

## 非目标

- 不是完整的阵容模拟器或棋盘编辑器
- 不替代游戏客户端或专业数据站，统计数据以来源站为准
- 站位为根据职业推断的参考，不是唯一正确答案

## 致谢

数据与图标来自 tactics.tools 与 Community Dragon。本项目与 Riot Games 无关；《云顶之弈》及相关素材版权归 Riot Games 所有。

## 已下线的板块（2026-11-01）

首页的「最强阵容」「冷门高胜率」「三星价值」「羁绊强度」、种族页的「站位结论」和英雄卡上的「阵眼—三星 / 阵眼—装备」标签已删除。

- 它们都只看对局结束时的**最终棋盘**。三星、满 3 件装、高费卡、高档羁绊都要活得够久才凑得出，所以出现它们的棋盘名次本来就好，不论它们本身有没有用（幸存者偏差）；强阵容、运气和技术又同时带来这些状态和好名次（混杂）。
- 例（2026-10-30 的页面）：「三星价值」前 8 名全是 4 费、3★ 均名 1.1–1.4；「羁绊强度」取各档均名的最小值，最高档通常只有赢家能到；13 个「阵眼—装备」里有 6 个是本站标为前排的单位。
- 在已知真值的模拟检验里（tft-lab 项目），「三星价值」这种算法把三星的好处高估了 1.7–2.0 个名次，并且在追三星其实不划算的情形里总是建议追。
- 阵容强度目前还无法从最终棋盘可靠测出，测出之前首页不放阵容排行。

## 种族搭配（synergy.html）

`synergy.html` 是 种族 × 种族 矩阵，每格显示该搭配的**均名**（颜色：绿 <4.2，红 >4.7）和**选率**；点格子进入静态详情页 `synergy/<hash>.html`，列出该搭配下所有英雄组合的均名 / 前四 / 吃鸡 / 场次 / 选率 / 格内占比。

- **“带了”某种族**：阵容中该种族英雄 ≥2 名（单一英雄种族 ≥1），阈值见 `synergy.py` 的 `MIN`
- **英雄组合（变体）**：阵容里属于这两个种族的英雄集合；相同集合合并统计
- **主数据**：tactics.tools 主流阵容（team-compositions，按场次加权）；选率 = 场次 / 总棋盘数
- **对照**：Riot Match 抽样（`data/riot/cache/sample_matches.json`，本地有才用）单独一张表；矩阵里标 “R” 的格子只有 Riot 抽样数据，样本很小仅供参考
- 由 `python3 build_site.py` 一并生成
