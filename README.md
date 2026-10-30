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
| 不知道该往哪个方向玩 | 「洞察速览」与「站位结论」汇总表现较好的羁绊与站位方向 |
| 装备合成表过时 | 当前 Set 18 的 10×10 散件合成矩阵（含金铲铲 / 金锅锅），附纹章与冠冕清单 |
| 找某个英雄/羁绊太慢 | 顶部搜索框 + 费用/位置过滤器 |
| 名称是英文 | 英雄、羁绊、装备名称全部取自官方简体中文数据 |

## 怎么做的

```
tactics.tools（英雄出装 / 羁绊表现统计）  ┐
Community Dragon zh_cn（中文名称、图标、合成配方）┤→ Python 脚本 → index.html → GitHub Pages
```

- **数据源**
  - [tactics.tools](https://tactics.tools/zh/units)：英雄名次、前四率、选取率、出装统计、羁绊表现
  - [Community Dragon](https://raw.communitydragon.org/)：简体中文名称、头像/装备图标、装备配方（`zh_cn.json`）
- **生成脚本**（只用 Python 标准库，无第三方依赖）
  - `generate_tft_table.py`：抓取数据、映射中文名、推断站位、计算推荐出装与站位结论
  - `craft.py`：从 Community Dragon 读取当前赛季配方，生成装备合成矩阵、纹章、冠冕
  - `build_site.py`：把以上内容组装成单页 `index.html`（内联 CSS/JS）
- **部署**：`index.html` 推到 `main`，由 GitHub Pages 直接托管

### 刷新数据

```bash
python3 build_site.py            # 生成 index.html（会缓存出装数据到 /tmp）
python3 build_site.py --no-cache # 强制重新抓取
git add index.html && git commit -m "refresh data" && git push
```

新赛季上线后，Community Dragon 与 tactics.tools 更新数据，重跑即可；赛季编号相关的过滤在脚本中自动检测/可调整。

## 页面结构

1. **顶栏**：版本标识、搜索框、过滤器、区块导航
2. **洞察速览**：当前表现较好的羁绊与英雄要点
3. **站位结论**：前排 / 后排推荐方向
4. **职业矩阵 / 起源矩阵**：羁绊 × 前中后排的英雄卡片（费用、数据、二/三件套）
5. **装备合成**（`#craft`）：Set 18 散件 10×10 矩阵 + 纹章 + 冠冕

## 非目标

- 不是完整的阵容模拟器或棋盘编辑器
- 不替代游戏客户端或专业数据站，统计数据以来源站为准
- 站位为根据职业推断的参考，不是唯一正确答案

## 致谢

数据与图标来自 tactics.tools 与 Community Dragon。本项目与 Riot Games 无关；《云顶之弈》及相关素材版权归 Riot Games 所有。
