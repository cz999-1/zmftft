"""OP.GG 官方 MCP 接口的最小客户端（stdlib only）：只调用 tft_list_meta_decks（当前 meta 阵容 + 每套的
5级开局 / 7级中期 / 终局三阶段棋盘与回合胜负计数），给变阵路线页（trees.py）用。

这是 OP.GG 自己提供给 AI 代理的数据接口（仓库 github.com/opgginc/opgg-mcp，MIT；端点 MCP_URL，
Streamable HTTP）——按文档调用是授权访问。相反，OP.GG 网站条款明文禁止抓取页面
（policies/agreement：“scraping or data mining … automated scripts to collect information”，
2026-11-05 读取），所以本站不抓 op.gg 网页，只用这个官方接口，并在页面上注明来源。
礼貌约定：每次刷新只调用一次（fetch_data 的 6 小时缓存照常生效），不轮询。

extract_decks() 按白名单复制字段（checks.OPGG_* 元组）：玩家相关字段（puuid/gameName/tagLine 等）
永远不进快照——这份接口数据本来也不含，但照样设护栏。接口返回结构变了就大声报错，
原始响应在 cache/raw/opgg_meta_decks.json 里可离线排查。"""
import json
import re
import time
import urllib.request

import checks

MCP_URL = "https://mcp-api.op.gg/mcp"
UA = "zmftft/1.0 (+https://github.com/cz999-1/zmftft; static fan site build)"
PROTOCOL = "2025-03-26"


def _post(payload, session_id=None, timeout=60):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "User-Agent": UA}
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(MCP_URL, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        sid = r.headers.get("Mcp-Session-Id") or session_id
        body = r.read().decode("utf-8", "replace")
        ctype = r.headers.get("Content-Type") or ""
    if "text/event-stream" in ctype:
        msgs = [json.loads(line[5:].strip()) for line in body.splitlines() if line.startswith("data:")]
    else:
        msgs = [json.loads(body)] if body.strip() else []
    for m in msgs:
        if m.get("error"):
            raise RuntimeError("OP.GG MCP 返回错误：%s" % json.dumps(m["error"], ensure_ascii=False)[:300])
    hit = [m for m in msgs if "result" in m]
    return (hit[-1] if hit else None), sid


def _call_tool(name, arguments, tries=3):
    err = None
    for t in range(tries):  # 每次重试都重新握手；失败后等 2s/4s
        try:
            init, sid = _post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                               "params": {"protocolVersion": PROTOCOL, "capabilities": {},
                                          "clientInfo": {"name": "zmftft", "version": "1.0"}}})
            _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
            res, _ = _post({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                            "params": {"name": name, "arguments": arguments}}, sid)
            r = (res or {}).get("result") or {}
            if r.get("isError"):
                raise RuntimeError("OP.GG MCP 工具 %s isError=true" % name)
            text = "".join(c.get("text", "") for c in r.get("content") or [] if c.get("type") == "text")
            if not text.strip():
                raise RuntimeError("OP.GG MCP 工具 %s 返回空内容" % name)
            return json.loads(text)
        except Exception as e:
            err = e
            if t < tries - 1:
                time.sleep(2 * (t + 1))
    raise RuntimeError("OP.GG MCP 调用 %s 失败（%d 次）：%s" % (name, tries, err))


def fetch_meta_decks():
    """官方接口的 meta 阵容原始数据（整体进 cache/raw/，白名单复制在 extract_decks）。"""
    doc = _call_tool("tft_list_meta_decks", {})
    if not isinstance(doc, dict) or not isinstance(doc.get("data"), list):
        raise RuntimeError("OP.GG MCP meta decks 返回结构变了：顶层键 %s" % (sorted(doc) if isinstance(doc, dict) else type(doc).__name__))
    return doc


def _pick(d, fields, ctx):
    if not isinstance(d, dict):
        raise ValueError("OP.GG 数据结构变了：%s 不是对象（%r）" % (ctx, type(d).__name__))
    return {k: d[k] for k in fields if k in d}


def _unit(u, ctx):
    out = _pick(u, checks.OPGG_UNIT_FIELDS, ctx)
    key = out.get("key") or out.get("characterId")
    if not key:
        raise ValueError("OP.GG 数据结构变了：%s 的英雄行没有 key/characterId（字段：%s）" % (ctx, sorted(u)))
    out["items"] = [i for i in (u.get("items") or []) if i]
    cell = u.get("cell") or {}
    out["cell"] = {"x": cell.get("x"), "y": cell.get("y")} if isinstance(cell, dict) else {}
    return out


def _stage(s, ctx):
    out = _pick(s, checks.OPGG_STAGE_FIELDS, ctx)
    for k in ("level", "units", "play", "win", "lose"):
        if k not in out:
            raise ValueError("OP.GG 数据结构变了：%s 缺字段 %s（有：%s）" % (ctx, k, sorted(s)))
    try:  # 接口把 level 给成字符串（'5'）；回合计数偶尔也可能是字符串——统一成 int，转不动就大声报错
        for k in ("level", "play", "win", "lose"):
            out[k] = int(out[k])
    except (TypeError, ValueError):
        raise ValueError("OP.GG 数据结构变了：%s 的 level/play/win/lose 不是数（%r）" % (ctx, {k: s.get(k) for k in ("level", "play", "win", "lose")}))
    out["units"] = [_unit(u, ctx) for u in s["units"]]
    out["traits"] = [_pick(t, checks.OPGG_TRAIT_FIELDS, ctx) for t in s.get("traits") or []]
    return out


def extract_decks(raw):
    """白名单复制：快照里的 opgg_decks。结构对不上就 ValueError（大声失败，别静默吞掉改版）。"""
    decks = []
    for i, d in enumerate(raw["data"]):
        ctx = "opgg deck[%d]" % i
        for k in ("id", "name", "units", "stat", "early", "middle", "teamCode"):
            if k not in d:
                raise ValueError("OP.GG 数据结构变了：%s 缺字段 %s（有：%s）" % (ctx, k, sorted(d)))
        name = {k: d["name"].get(k) for k in checks.OPGG_NAME_LOCALES if d["name"].get(k)}
        if "zh_CN" not in name:
            raise ValueError("OP.GG 数据结构变了：%s 没有 zh_CN 名字（locales：%s）" % (ctx, sorted(d["name"])))
        stat = _pick(d["stat"], checks.OPGG_STAT_FIELDS, ctx + ".stat")
        stat["deck"] = _pick((d["stat"] or {}).get("deck") or {}, checks.OPGG_DECK_STAT_FIELDS, ctx + ".stat.deck")
        deck = {"id": d["id"], "name": name, "teamCode": d["teamCode"], "cost": d.get("cost"),
                "units": [_unit(u, ctx) for u in d["units"]],
                "traits": [_pick(t, checks.OPGG_TRAIT_FIELDS, ctx) for t in d.get("traits") or []],
                "stat": stat, "early": _stage(d["early"], ctx + ".early"), "middle": _stage(d["middle"], ctx + ".middle")}
        decks.append(deck)
    blob = json.dumps(decks, ensure_ascii=False)
    hits = [w for w in ("puuid", "gameName", "tagLine", "recentWins") if re.search(w, blob, re.I)]
    if hits:
        raise ValueError("OP.GG 数据里混进了玩家字段 %s：白名单漏了，不写快照" % hits)
    return decks
