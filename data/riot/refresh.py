"""One-shot refresh: Data Dragon always (no key); Match API + compare only if a key is present.
Usage: python3 -m data.riot.refresh
Key lookup: $RIOT_API_KEY -> .env -> data/riot/riot.local.json
"""
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def load_key():
    k = os.environ.get("RIOT_API_KEY", "").strip()
    if k: return k
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("RIOT_API_KEY="):
                k = line.split("=", 1)[1].strip().strip('"\'')
                if k: return k
    loc = ROOT / "data/riot/riot.local.json"
    if loc.exists():
        try: return (json.loads(loc.read_text()).get("api_key") or "").strip()
        except Exception: pass
    return ""

def run(mod, *args, env=None):
    return subprocess.call([sys.executable, "-m", mod, *args], cwd=ROOT, env=env)

def main():
    if run("data.riot.ddragon", "--lang", "zh_CN") != 0:
        print("[refresh] Data Dragon failed"); return 1
    key = load_key()
    if not key:
        print("[refresh] no RIOT_API_KEY -> skip Match API"); return 0
    env = dict(os.environ, RIOT_API_KEY=key)
    if run("data.riot.match_api", "--platform", "kr", "--region", "asia", env=env) == 0:
        run("data.riot.compare", env=env)
    else:
        print("[refresh] Match API failed (non-fatal)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
