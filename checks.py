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
          "craft_components": (10, 10),  # 基础散件（10）
          "craft_recipes": (40, None)}   # 合成表格子（55）
POSITIONS = {"front", "mid", "back"}


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
        pl, t4, n = s.get("place"), s.get("top4"), s.get("count")
        if pl is None or t4 is None or not n or not (1 <= pl <= 8 and 0 <= t4 <= 100):
            p.append("%s：统计值不合理 %s" % (u, s))
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
