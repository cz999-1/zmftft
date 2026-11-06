"""构建护栏：快照和人工标注不通过就不生成页面、不存快照 (stdlib only).
用法: python3 checks.py [cache/snapshots/set18/18.5c.json]  # 单独检查一个快照（默认最新的）
      python3 checks.py --images [快照]                      # 联网：逐个检查页面引用的图片能否打开
      python3 checks.py --skeleton cache/failed_snapshot.json  # 新赛季：生成 sets/set<N>.json 草稿
build_site.py 每次构建前都会调用 check()（不联网）。"""
import contextlib, io, json, re, sys, tempfile, time, urllib.request
from pathlib import Path
from generate_tft_table import load_manual, SETS, CD_ROOT, UA

# 合理范围（Set 18 的实际值见括号）：超出就说明数据源变了或抓取出错
BOUNDS = {"roster": (40, 90),          # 矩阵里的英雄数（65）
          "total": (10_000, None),     # tactics.tools 棋盘总数（1,563,397）
          "comps": (10, None),         # 主流阵容数（45）
          "comp_groups": (2, 12),      # 阵容组数（5）
          "opgg_decks": (3, 30),       # OP.GG 官方接口的 meta 阵容数（10）
          "craft_components": (10, 10),  # 基础散件（10）
          "craft_recipes": (40, None)}   # 合成表格子（55）
POSITIONS = {"front", "mid", "back"}
# 阵容页的阵容组块（fetch_data.comp_groups）只许有这些字段，按 tactics.tools 原名复制。
# 不复制：topPlayers（玩家名）、lpDelta*、日期/地区分布、itemDeltas/unitDeltas（未调整的“效果差”）、
# starUnits（目标星级随费用变，五费记的是 2★）、winCons（计数超过组内棋盘数，口径不明）。
GROUP_FIELDS = ("group", "count", "place", "top4", "win", "code", "placementDistribution", "levels",
                "carryUnits", "units", "unitItemCounts", "traits", "unitItems", "unitItemPairs")
# 变阵路线页（trees.py）的数据：OP.GG 官方 MCP 接口 tft_list_meta_decks（opgg.py），同样按白名单复制。
# 不复制：badge、priority、stat.label（和 stat.deck 同口径的组级数字，页面不用）。接口数据不含玩家字段，
# 但照样扫（puuid/gameName/tagLine/recentWins 出现即不写快照）。
OPGG_DECK_FIELDS = ("id", "name", "cost", "teamCode", "units", "traits", "stat", "early", "middle")
OPGG_UNIT_FIELDS = ("key", "characterId", "items", "tier", "cell", "isCore")
OPGG_STAGE_FIELDS = ("deckId", "finalDeckId", "level", "units", "traits", "play", "win", "lose")
OPGG_TRAIT_FIELDS = ("key", "style", "numUnits")
OPGG_STAT_FIELDS = ("opTier", "opScore", "labelNumber", "representative", "deck")
OPGG_DECK_STAT_FIELDS = ("totalCount", "compsCount", "avgPlacement", "winCount", "top4Count", "winRate", "top4Rate", "pickRate")
OPGG_NAME_LOCALES = ("zh_CN", "en_US")
# OP.GG 把战斗中的召唤物也算进棋盘（商店里买不到，官方英雄表里没有）：页面过滤不显示，护栏按这张表放行。
# 新赛季出现新召唤物会在这里大声报错，人工确认后再登记。
OPGG_SUMMONS = ("DA_Elderwood18_Lifeblossom", "DA_Elderwood18_StonebarkTree")


def _between(name, v, problems):
    lo, hi = BOUNDS[name]
    if v < lo or (hi is not None and v > hi):
        problems.append("%s = %s，超出合理范围 [%s, %s]" % (name, v, lo, hi if hi is not None else "∞"))


def check(snap, manual=None):
    """返回问题列表（空 = 通过）。manual 默认读 sets/set<N>.json。"""
    m = snap["meta"]; p = []
    set_no = m["set"]
    if manual is None:
        manual = load_manual(set_no)
    off_units, off_traits = snap["official"]["units"], snap["official"]["traits"]
    # 1. 赛季号：Community Dragon 图标路径、tactics.tools 页面标题、人工标注文件要一致
    if m.get("tactics_set") != set_no:
        p.append("赛季不一致：Community Dragon 是 Set %s，tactics.tools 页面是 Set %s" % (set_no, m.get("tactics_set")))
    if manual.get("set") != set_no:
        p.append("sets/set%d.json 里写的是 set %s" % (set_no, manual.get("set")))
    if not m.get("patch_label") or not m.get("rank_label"):
        p.append("tactics.tools 页面上没找到版本号或分段（筛选栏文字可能改了）")
    # 1b. 图片地址固定在 Community Dragon 的版本目录（如 16.21），不用 latest：换赛季后 latest 里的旧图会变或消失
    folder = (m.get("cdragon") or {}).get("folder") or ""
    if not re.fullmatch(r"\d+\.\d+", folder):
        p.append("没记下 Community Dragon 的版本目录（%r）：图片会指向 latest" % folder)
    else:
        craft_icons = [c[2] for c in snap["craft"]["components"]] + [r["icon"] for r in snap["craft"]["recipes"]]
        off = [u for u in craft_icons if u and not u.startswith("%s/%s/" % (CD_ROOT, folder))]
        if off:
            p.append("合成表图片没用版本目录 %s：%s 等 %d 个" % (folder, off[0], len(off)))
        trait_icons = [t.get("icon") for t in (snap["official"].get("trait_meta") or {}).values()]
        off = [u for u in trait_icons if u and not u.startswith("%s/%s/" % (CD_ROOT, folder))]
        if off:
            p.append("羁绊图标没用版本目录 %s：%s 等 %d 个" % (folder, off[0], len(off)))
    # 2. tactics.tools 的每个英雄 id 都要在官方数据里（新 id 先登记再出页面）
    unseen = sorted(set(snap["unit_stats"]) - set(off_units))
    if unseen:
        p.append("tactics.tools 有官方数据里没有的英雄 id：%s" % ", ".join(unseen))
    # 3. 矩阵里每个英雄：有名字、费用（1-5）、图标、站位；人工标注的名字和官方一致
    hide = {i for i, _ in manual["hide"]}
    roster = [c["character_record"] for c in snap["champions"] if c["character_record"]["character_id"] not in hide]
    _between("roster", len(roster), p)
    for cr in roster:
        cid = cr["character_id"]; name = manual["rename"].get(cid) or cr.get("display_name")
        off = off_units.get(cid)
        if not off:
            p.append("%s：官方数据里没有" % cid); continue
        if not name: p.append("%s：没有中文名" % cid)
        if off["cost"] not in (1, 2, 3, 4, 5): p.append("%s %s：费用 %s 不在 1-5" % (cid, name, off["cost"]))
        if not cr.get("squareIconPath"): p.append("%s %s：没有图标" % (cid, name))
        pos = manual["positions"].get(cid)
        if not pos or pos[0] not in POSITIONS:
            p.append("%s %s：sets/set%d.json 里没有站位（front/mid/back）" % (cid, name, set_no))
        elif pos[1] != name:
            p.append("%s：sets/set%d.json 里写的是「%s」，官方名是「%s」" % (cid, set_no, pos[1], name))
        if cid not in snap["unit_builds"]:
            p.append("%s %s：没有出装数据" % (cid, name))
    # 4. 用到的每个羁绊都标了职业或种族，且名字和官方一致
    typed = {t: n for t, n in manual["classes"] + manual["origins"]}
    for t in sorted({t["id"] for cr in roster for t in (cr.get("traits") or [])}):
        if t not in typed:
            p.append("羁绊 %s（%s）没有在 sets/set%d.json 里标职业或种族" % (t, off_traits.get(t), set_no))
        elif off_traits.get(t) != typed[t]:
            p.append("羁绊 %s：sets/set%d.json 里写的是「%s」，官方名是「%s」" % (t, set_no, typed[t], off_traits.get(t)))
    # 5. 数量在合理范围
    _between("total", m["total"], p)
    _between("comps", len(snap["comps"]), p)
    _between("craft_components", len(snap["craft"]["components"]), p)
    _between("craft_recipes", len(snap["craft"]["recipes"]), p)
    for u, s in snap["unit_stats"].items():
        if not isinstance(s.get("count"), int) or not 0 < s["count"] <= m["total"]:
            p.append("%s：棋盘数不合理 %s（全部棋盘 %s）" % (u, s, m["total"]))
        elif not (isinstance(s.get("place"), (int, float)) and 1 <= s["place"] <= 8) or \
                any(not (isinstance(s.get(k), (int, float)) and 0 <= s[k] <= 100) for k in ("top4", "won")):
            p.append("%s：英雄页要用的 place/top4/won 缺失或出界：%s" % (u, s))
    # 6. 英雄页的字段：阵容分组、星级数据、最高吃鸡组合（fetch_data 写入；缺 = 数据源或抓取变了）
    if any(not isinstance(c.get("group"), int) for c in snap["comps"]):
        p.append("有阵容缺 group（tactics.tools 的分组序号）")
    for u, b in snap["unit_builds"].items():
        for k in ("bestPair", "bestTrio"):
            x = b.get(k)
            if x is not None and not (isinstance(x.get("count"), int) and isinstance(x.get("won"), (int, float))):
                p.append("%s：%s 缺 count/won" % (u, k))
        for srow in b.get("starLevelData") or []:
            n = srow.get("count")
            if not isinstance(n, int) or not 0 <= n <= m["total"] or \
                    (n > 0 and not (isinstance(srow.get("place"), (int, float)) and 0 < srow["place"] <= 8)):
                p.append("%s：starLevelData 数值出界 %s" % (u, srow))
                break
    # 7. 变阵路线页的 OP.GG 官方接口数据：只有白名单字段、英雄在官方表（或登记过的召唤物）、
    #    回合计数自洽、没有玩家字段。放在 comp_groups 块之前：那个块缺节时会提前 return。
    decks = snap.get("opgg_decks")
    if not isinstance(decks, list):
        p.append("快照缺 opgg_decks（变阵路线页的 OP.GG 官方接口数据）：用新版 fetch_data.py 重建快照")
    else:
        _between("opgg_decks", len(decks), p)
        if len({d.get("id") for d in decks}) != len(decks):
            p.append("opgg_decks 里有重复的阵容 id")
        blob = json.dumps(decks, ensure_ascii=False)
        bad_tokens = [w for w in ("puuid", "gameName", "tagLine", "recentWins") if re.search(w, blob, re.I)]
        if bad_tokens:
            p.append("opgg_decks 混进了玩家字段 %s（白名单漏了）" % ", ".join(bad_tokens))
        allowed_units = set(off_units) | set(OPGG_SUMMONS)
        for d in decks:
            did = (d.get("name") or {}).get("zh_CN") or d.get("id")
            extra = sorted(set(d) - set(OPGG_DECK_FIELDS))
            if extra:
                p.append("OP.GG 阵容 %s 含白名单外的字段 %s" % (did, ", ".join(extra))); continue
            if not (d.get("name") or {}).get("zh_CN"):
                p.append("OP.GG 阵容 %s：没有 zh_CN 名字" % d.get("id"))
            st = (d.get("stat") or {}).get("deck") or {}
            n = st.get("compsCount")
            if not isinstance(n, int) or n <= 0 or (isinstance(st.get("totalCount"), int) and n > st["totalCount"]):
                p.append("OP.GG 阵容 %s：场次不合理 %r" % (did, n)); continue
            if not (isinstance(st.get("avgPlacement"), (int, float)) and 1 <= st["avgPlacement"] <= 8) or \
                    any(not (isinstance(st.get(k), (int, float)) and 0 <= st[k] <= 1) for k in ("winRate", "top4Rate", "pickRate")):
                p.append("OP.GG 阵容 %s：avgPlacement/winRate/top4Rate/pickRate 缺失或出界" % did)
            code = d.get("teamCode") or ""
            if not code.endswith("TFTSet%d" % set_no):
                p.append("OP.GG 阵容 %s：阵容码 %r 不是 Set %d 的" % (did, code, set_no))
            stages = [("终局", {"units": d.get("units") or [], "level": 8, "play": 1, "win": 0, "lose": 0})] + \
                     [(k, d.get(k)) for k in ("early", "middle")]
            for sname, s in stages:
                if not isinstance(s, dict):
                    p.append("OP.GG 阵容 %s：缺 %s 阶段" % (did, sname)); continue
                if sname != "终局":
                    extra = sorted(set(s) - set(OPGG_STAGE_FIELDS))
                    if extra:
                        p.append("OP.GG 阵容 %s：%s 含白名单外的字段 %s" % (did, sname, ", ".join(extra)))
                    if not isinstance(s.get("level"), int) or not 2 <= s["level"] <= 10:
                        p.append("OP.GG 阵容 %s：%s 的等级 %r 不在 2-10" % (did, sname, s.get("level")))
                    if any(not isinstance(s.get(k), int) or s[k] < 0 for k in ("play", "win", "lose")) or \
                            s["win"] + s["lose"] > s["play"]:
                        p.append("OP.GG 阵容 %s：%s 的回合计数不自洽（play=%r win=%r lose=%r）" % (
                            did, sname, s.get("play"), s.get("win"), s.get("lose")))
                us = s.get("units") or []
                if not 1 <= len(us) <= 10:
                    p.append("OP.GG 阵容 %s：%s 的英雄数 %d 不在 1-10" % (did, sname, len(us)))
                for u in us:
                    uid = u.get("key") or u.get("characterId")
                    extra = sorted(set(u) - set(OPGG_UNIT_FIELDS) - {"cell"})
                    if extra:
                        p.append("OP.GG 阵容 %s：英雄行含白名单外的字段 %s" % (did, ", ".join(extra))); break
                    if uid not in allowed_units:
                        p.append("OP.GG 阵容 %s：英雄 %s 不在官方表里（新召唤物？先在 checks.OPGG_SUMMONS 登记）" % (did, uid)); break
                    tier = u.get("tier")
                    if tier is not None and tier not in (1, 2, 3, 4):
                        p.append("OP.GG 阵容 %s：英雄 %s 星级 %r 出界" % (did, uid, tier)); break
                for t in s.get("traits") or []:
                    if t.get("key") not in off_traits:
                        p.append("OP.GG 阵容 %s：羁绊 %s 不在官方表里" % (did, t.get("key"))); break
            for t in d.get("traits") or []:  # 终局行的羁绊标签也要在官方表里
                if t.get("key") not in off_traits:
                    p.append("OP.GG 阵容 %s：终局羁绊 %s 不在官方表里" % (did, t.get("key"))); break
        # 树的分叉节点直接取第一套的 board 和回合计数：同一 deckId 的阶段必须完全一致，不一致说明口径变了
        for which in ("early", "middle"):
            seen_stage = {}
            for d in decks:
                st = d.get(which) or {}
                key = st.get("deckId")
                body = json.dumps({k: st.get(k) for k in ("level", "units", "traits", "play", "win", "lose")},
                                  ensure_ascii=False, sort_keys=True)
                if key in seen_stage and seen_stage[key] != body:
                    p.append("OP.GG 两套阵容共用 %s 的 deckId %s 但阶段内容不同（接口口径变了？）" % (which, key)); break
                seen_stage[key] = body
    # 8. 阵容页的阵容组块：分组和 comps 一致、只有白名单字段（不含玩家名）、数值在合理范围
    groups = snap.get("comp_groups")
    if not isinstance(groups, list):
        p.append("快照缺 comp_groups（阵容页的阵容组块）：用新版 fetch_data.py 重建快照")
        return p
    _between("comp_groups", len(groups), p)
    want = sorted({c.get("group") for c in snap["comps"] if isinstance(c.get("group"), int)})
    if sorted(g.get("group") for g in groups) != want:
        p.append("comp_groups 的分组 %s 和 comps 的分组 %s 对不上" % (sorted(g.get("group") for g in groups), want))
    for g in groups:
        gid = g.get("group")
        extra = sorted(set(g) - set(GROUP_FIELDS))
        if extra:
            p.append("阵容组 %s 含白名单外的字段 %s（玩家名等不进快照）" % (gid, ", ".join(extra)))
        n = g.get("count")
        if not isinstance(n, int) or not 0 < n <= m["total"]:
            p.append("阵容组 %s：棋盘数不合理 %r" % (gid, n)); continue
        if not (isinstance(g.get("place"), (int, float)) and 1 <= g["place"] <= 8) or \
                any(not isinstance(g.get(k), int) or not 0 <= g[k] <= n for k in ("top4", "win")):
            p.append("阵容组 %s：place/top4/win 缺失或出界" % gid)
        dist = g.get("placementDistribution") or []
        if len(dist) != 8 or abs(sum(dist) - n) > 2:
            p.append("阵容组 %s：名次分布不是 8 档或合计对不上棋盘数（%s 对 %d）" % (gid, sum(dist), n))
        lv = g.get("levels") or []
        if not lv or any(len(r) != 3 or not 1 <= r[0] <= 10 or r[1] < 0 for r in lv) or abs(sum(r[1] for r in lv) - n) > 2:
            p.append("阵容组 %s：终局等级分布缺失或合计对不上棋盘数" % gid)
        bad = [r for r in g.get("units") or [] if len(r) != 4 or r[0] not in off_units or r[1] not in (1, 2, 3, 4)
               or not isinstance(r[2], int) or not 0 <= r[2] <= n]
        if not g.get("units") or bad:
            p.append("阵容组 %s：英雄星级行缺失或出界（%s）" % (gid, bad[:1]))
        bad = [r.get("unitId") for k in ("unitItems", "unitItemPairs", ) for r in g.get(k) or []
               if r.get("unitId") not in off_units or not isinstance(r.get("count"), int)]
        bad += [u for u, _ in g.get("carryUnits") or [] if u not in off_units]
        if bad:
            p.append("阵容组 %s：装备/主C 数据里有官方数据外的英雄或缺场次：%s" % (gid, bad[0]))
        code = g.get("code") or ""
        if code and not code.endswith("TFTSet%d" % set_no):
            p.append("阵容组 %s：阵容码 %r 不是 Set %d 的" % (gid, code, set_no))
    return p


def require(snap):
    """不通过就退出（不写快照、不生成页面）。"""
    problems = check(snap)
    if problems:
        raise SystemExit("构建护栏没通过，没有写快照和页面：\n- " + "\n- ".join(problems))


NOTE = ("人工标注：羁绊类型（职业/种族）、行顺序和英雄站位不在官方数据里，由本站维护。列表顺序 = 页面上的行顺序。"
        "名字只为方便阅读，页面用官方中文名；id 与名字对不上时构建会报错。")


def skeleton(snap):
    """新赛季的 sets/set<N>.json 草稿：站位都是 "?"，羁绊都在 "untyped"，等人工分到 classes / origins。"""
    roster = sorted((c["character_record"] for c in snap["champions"]), key=lambda cr: cr["character_id"])
    traits = sorted({(t["id"], t["name"]) for cr in roster for t in cr.get("traits") or []})
    return {"set": snap["meta"]["set"], "note": NOTE, "hide": [], "hide_note": "", "rename": {},
            "classes": [], "origins": [], "untyped": [list(t) for t in traits],
            "positions": {cr["character_id"]: ["?", cr["display_name"]] for cr in roster}}


def dump_manual(doc):
    """一行一条，方便手工编辑。"""
    J = lambda v: json.dumps(v, ensure_ascii=False)
    out, keys = ["{"], list(doc)
    for i, k in enumerate(keys):
        v, end = doc[k], ("," if i < len(keys) - 1 else "")
        if isinstance(v, (list, dict)) and v:
            rows = list(v.items()) if isinstance(v, dict) else v
            fmt = (lambda x: "%s: %s" % (J(x[0]), J(x[1]))) if isinstance(v, dict) else J
            out += [" %s: %s" % (J(k), "{" if isinstance(v, dict) else "[")]
            out += ["  %s%s" % (fmt(x), "," if j < len(rows) - 1 else "") for j, x in enumerate(rows)]
            out += [" %s%s" % ("}" if isinstance(v, dict) else "]", end)]
        else:
            out.append(" %s: %s%s" % (J(k), J(v), end))
    return "\n".join(out + ["}"]) + "\n"


def image_urls(snap):
    """页面会引用的全部图片地址（按快照渲染到临时目录后读出来）。"""
    import build_site
    urls = set()
    with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
        build_site.render(snap, Path(d))
        for f in Path(d).rglob("*.html"):
            urls |= set(re.findall(r'src="(https?://[^"]+)"', f.read_text(encoding="utf-8")))
    return sorted(urls)


def check_images(snap, pause=0.1):
    """联网：逐个 HEAD 页面引用的图片（每个地址只请求一次），返回打不开的。"""
    bad = []
    for u in image_urls(snap):
        try:
            urllib.request.urlopen(urllib.request.Request(u, method="HEAD", headers=UA), timeout=20).close()
        except Exception as err:
            bad.append("%s（%s）" % (u, err))
        time.sleep(pause)
    return bad


def main():
    if sys.argv[1:2] == ["--images"]:
        found = sorted(Path(__file__).resolve().parent.glob("cache/snapshots/set*/*.json"), key=lambda p: p.stat().st_mtime)
        path = Path(sys.argv[2]) if len(sys.argv) > 2 else found[-1]
        snap = json.loads(path.read_text(encoding="utf-8"))
        n, bad = len(image_urls(snap)), check_images(snap)
        print("\n".join(bad) or "%s：%d 个图片地址都能打开" % (path, n))
        return 1 if bad else 0
    if sys.argv[1:2] == ["--skeleton"]:
        snap = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        p = SETS / ("set%d.json" % snap["meta"]["set"])
        if p.exists():
            raise SystemExit("%s 已存在，不覆盖" % p)
        p.write_text(dump_manual(skeleton(snap)), encoding="utf-8", newline="\n")
        print("草稿 →", p, "（填站位、把 untyped 里的羁绊分到 classes / origins，见 README 的 Set 迁移清单）")
        return 0
    found = sorted(Path(__file__).resolve().parent.glob("cache/snapshots/set*/*.json"), key=lambda p: p.stat().st_mtime)
    if len(sys.argv) < 2 and not found:
        raise SystemExit("cache/snapshots/ 下没有快照：先运行 python3 fetch_data.py")
    path = sys.argv[1] if len(sys.argv) > 1 else found[-1]
    problems = check(json.loads(Path(path).read_text(encoding="utf-8")))
    print("\n".join(problems) or "%s：通过" % path)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
