"""装备合成表 — 从 Community Dragon zh_cn TFT 数据为当前赛季生成合成矩阵 HTML。"""
import re, html as H, json, urllib.request
CD_JSON = "https://raw.communitydragon.org/latest/cdragon/tft/zh_cn.json"
GAME = "https://raw.communitydragon.org/%s/game/"  # % Community Dragon folder: a patch such as 16.21 (pinned) or latest
COMPS = ["BFSword", "RecurveBow", "NeedlesslyLargeRod", "TearOfTheGoddess", "ChainVest",
         "NegatronCloak", "GiantsBelt", "SparringGloves", "Spatula", "FryingPan"]
e = lambda s: H.escape(str(s))

def icon(p, folder="latest"):
    return (GAME % folder) + p.lower().replace(".tex", ".png") if p else ""

def blurb(it):
    d = it.get("desc") or ""
    ef = it.get("effects") or {}
    def sub(m):
        k, mul = m.group(1), m.group(2)
        v = ef.get(k)
        if v is None:
            v = next((x for kk, x in ef.items() if kk.lower() == k.lower()), None)
        if v is None: return "?"
        if mul: v = v * float(mul)
        return ("%g" % round(v, 1))
    d = re.sub(r"@([A-Za-z0-9_]+)(?:\*([0-9.]+))?@", sub, d)
    d = re.sub(r"<tftitemrules>.*?</tftitemrules>", "", d, flags=re.S)
    d = re.sub(r"<br\s*/?>|<li>", " ", d)
    d = re.sub(r"<[^>]+>", "", d)
    d = re.sub(r"@[^@]*@", "", d)
    d = re.sub(r"\s+", " ", d).strip()
    if not d:
        st = [("AD","攻击力",100),("AP","法强",1),("AS","攻速",1)]
        d = " ".join("+%g%s" % (round(ef[k]*m,1), n) for k,n,m in st if ef.get(k)) or "纯属性装备"
    return d[:70] + ("…" if len(d) > 70 else "")

def fetch():
    return json.loads(urllib.request.urlopen(urllib.request.Request(CD_JSON, headers={"User-Agent": "zmftft"}), timeout=60).read())

def build(d, set_no, folder="latest"):
    """folder: Community Dragon folder for the icon URLs (the site build passes the snapshot's patch folder)."""
    im = {i["apiName"]: i for i in d["items"]}
    S = next(s for s in d["setData"] if s.get("number") == set_no and s.get("mutator") == "TFTSet%d" % set_no)
    names = set(S["items"])
    # core recipe items: TFT_Item_* in set list (fallback DA_*)
    table = {}
    for a in names:
        it = im.get(a)
        if not it or len(it.get("composition") or []) != 2: continue
        c = tuple(sorted(x.split("_")[-1] for x in it["composition"]))
        if not all(x in COMPS for x in c): continue
        if a.startswith("TFT_Item_") or c not in table or "Emblem" in a:
            if c in table and table[c]["api"].startswith("TFT_Item_") and not a.startswith("TFT_Item_") and "Emblem" not in a: continue
            table[c] = {"api": a, "name": it["name"], "icon": icon(it.get("icon"), folder), "desc": blurb(it), "emblem": "Emblem" in a}
    for c, v in table.items():
        if v["emblem"]:
            v["desc"] = "携带者获得【%s】羁绊" % v["name"].replace("纹章", "")
    comps = [(c, im["TFT_Item_" + c]["name"], icon(im["TFT_Item_" + c]["icon"], folder)) for c in COMPS]
    return comps, table

def section(comps, table, set_no):
    head ='<th></th>' + "".join('<th><img src="%s" alt=""><span>%s</span></th>' % (i, e(n)) for _, n, i in comps)
    rows = []
    for a, an, ai in comps:
        cells = []
        for b, _, _ in comps:
            v = table.get(tuple(sorted((a, b))))
            if not v: cells.append('<td class="na">—</td>'); continue
            cells.append('<td class="%s" title="%s"><img src="%s" alt=""><b>%s</b><small>%s</small></td>' % (
                "em" if v["emblem"] else "", e(v["desc"]), v["icon"], e(v["name"]), e(v["desc"])))
        rows.append('<tr><th><img src="%s" alt=""><span>%s</span></th>%s</tr>' % (ai, e(an), "".join(cells)))
    ems = sorted([(k, v) for k, v in table.items() if v["emblem"] or "Spatula" in k or "FryingPan" in k], key=lambda kv: (kv[0][0] != "FryingPan" and "FryingPan" in kv[0], kv[1]["name"]))
    cn = {c: (n, i) for c, n, i in comps}
    elist = "".join('<li><img src="%s"><span class="rc"><img src="%s"><img src="%s"></span><b>%s</b><small>%s + %s</small></li>' % (
        v["icon"], cn[k[0]][1], cn[k[1]][1], e(v["name"]), e(cn[k[0]][0]), e(cn[k[1]][0])) for k, v in ems)
    return ('<section id="craft"><h2>装备合成 <small class="hint">Set %d 当前版本 · %d 种基础散件 · 数据 Community Dragon</small></h2>'
            '<div class="cw"><table class="craft"><tr>%s</tr>%s</table></div>'
            '<h3>🥄 金铲铲 / 金锅锅 → 纹章与冠冕 <small>仅当前赛季羁绊</small></h3><ul class="emb">%s</ul></section>') % (
            set_no, len(comps), head, "".join(rows), elist), len(comps), table

CSS = """.cw{overflow-x:auto;border:1px solid var(--bd);border-radius:var(--r);background:var(--pn)}
.craft{border-collapse:collapse;min-width:1100px;font-size:11px}.craft th,.craft td{border:1px solid var(--bd);padding:4px;vertical-align:top;text-align:center;width:9%}
.craft th{background:var(--pn2);color:var(--ac)}.craft th img{width:30px;height:30px;display:block;margin:0 auto 2px;border-radius:4px}
.craft td img{width:34px;height:34px;border-radius:4px;display:block;margin:0 auto}.craft td b{display:block;font-size:12px;margin:2px 0}
.craft td small{color:var(--mu);display:block;line-height:1.3}.craft td.em{background:rgba(240,180,41,.08)}.craft td.na{color:var(--mu)}
.craft td:hover{background:var(--pn2)}.emb{list-style:none;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:8px}
.emb li{display:flex;align-items:center;gap:6px;background:var(--pn);border:1px solid var(--bd);border-radius:8px;padding:6px}
.emb li>img{width:32px;height:32px}.emb .rc img{width:18px;height:18px;opacity:.8}.emb small{color:var(--mu);margin-left:auto}"""

if __name__ == "__main__":
    d = fetch(); set_no = max(int(k) for k in d["sets"])  # newest set in the file (the site build uses the detected set)
    s, n, t = section(*build(d, set_no), set_no)
    print(n, len(t))
    for k in [("BFSword","BFSword"),("TearOfTheGoddess","TearOfTheGoddess"),("Spatula","Spatula"),("BFSword","Spatula"),("FryingPan","NegatronCloak")]:
        v=t[tuple(sorted(k))];print(k,v["name"],v["desc"])
