"""构建护栏：快照和人工标注不通过就不生成页面、不存快照 (stdlib only).
用法: python3 checks.py [data/set18/18.5c.json]   # 单独检查一个快照
build_site.py 每次构建前都会调用 check()。"""
import json, sys
from pathlib import Path
from generate_tft_table import load_manual

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


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else sorted(Path(__file__).resolve().parent.glob("data/set*/*.json"))[-1]
    problems = check(json.loads(Path(path).read_text(encoding="utf-8")))
    print("\n".join(problems) or "%s：通过" % path)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
