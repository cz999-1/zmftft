# data/riot · Riot 官方 TFT 数据源

| 模块 | 数据 | 需要 key | 命令 |
|---|---|---|---|
| `ddragon.py` | Data Dragon 静态数据：英雄 `tft-champion.json`、装备 `tft-item.json`、羁绊 `tft-trait.json`（另有 augments / tactician 等） | 否 | `python3 -m data.riot.ddragon --lang zh_CN` |
| `match_api.py` | TFT Match API 样本对局（tft-league-v1 → tft-match-v1） | 是 | `python3 -m data.riot.match_api --platform kr --region asia` |
| `compare.py` | 样本对局 平均名次 vs tactics.tools | 是（间接） | `python3 -m data.riot.compare` |

输出都写到 `data/riot/cache/`（已 gitignore）。

## 端点
- 版本：`https://ddragon.leagueoflegends.com/api/versions.json`（取第 0 个）
- 静态：`https://ddragon.leagueoflegends.com/cdn/{ver}/data/{lang}/tft-champion.json` 等；图标 `/cdn/{ver}/img/tft-champion/{image.full}`
- 当前赛季按 key 里的 `TFTSet{N}` / `_{N}_` 自动识别（目前 16.21.1 → Set 18）
- Match API（header `X-Riot-Token`）：
  - `https://{platform}.api.riotgames.com/tft/league/v1/challenger`（platform：kr / na1 / euw1 …）
  - `https://{region}.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids?count=N`（region：asia / americas / europe / sea）
  - `https://{region}.api.riotgames.com/tft/match/v1/matches/{matchId}` → `info.participants[].placement / units[].character_id / tier / itemNames / traits`

## API key 申请
1. 用 Riot 账号登录 https://developer.riotgames.com
2. 首页自动生成 **Development API Key**（`RGAPI-…`，**24 小时过期**，过期点 Regenerate）
3. 长期使用可在 Register Product 申请 Personal API Key（不过期，需审核）

## 配置 key（绝不提交）
```bash
export RIOT_API_KEY=RGAPI-xxxx
# 或 data/riot/riot.local.json： {"api_key": "RGAPI-xxxx"}  （已 gitignore）
```
没有 key 时 `match_api` 直接跳过，站点构建不受影响。

## 限流
开发 key：**20 次/1 秒、100 次/2 分钟**（按 platform/region 分别计）。`Client` 用滑动窗口限到 18/1s、95/2min，遇 429 按 `Retry-After` 等待重试，5xx 重试。默认 5 名玩家 × 4 场 ≈ 1 + 5 + ≤20 = 26 次请求，一次跑完不触限。
