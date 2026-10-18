"""Collecte DEALS — ligne de commande.

  python collect.py discover all --per 20            trouve des pages produit dans les plans de site (urls/<enseigne>.json)
  python collect.py diagnose all --n 20              teste 20 pages par enseigne → garder / règle / abandonner (reports/diagnostic.md)
  python collect.py build all                        première lecture des pages retenues → base produits
  python collect.py nightly                          passe de nuit (à lancer une fois par jour) → reports/AAAA-MM-JJ.md
  python collect.py review                           rapprochements de produits à vérifier
  python collect.py estimate                         durée estimée de la passe de nuit

Planification (une fois par jour, à 3 h) :  0 3 * * *  cd /chemin/deals && python3 collect.py nightly >> logs/nightly.log 2>&1
"""
import argparse
import csv
import json
import sys
from pathlib import Path

from collect.pipeline import Collector
from collect.retailers import MIN_INTERVAL_S, RETAILERS, USER_AGENT
from listener.core import Listener
from listener.fetch import Fetcher


def main(argv=None):
    ap = argparse.ArgumentParser(description="Collecte quotidienne DEALS")
    ap.add_argument("--db", default="deals.sqlite")
    ap.add_argument("--interval", type=float, default=MIN_INTERVAL_S, help="secondes minimum entre deux requêtes vers un même site")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("discover", "diagnose", "build"):
        s = sub.add_parser(c)
        s.add_argument("retailer", help="clé d'enseigne ou « all »")
        s.add_argument("--per", type=int, default=20, help="discover : pages par catégorie")
        s.add_argument("--n", type=int, default=20, help="diagnose : pages testées par enseigne")
    sub.add_parser("nightly")
    sub.add_parser("review")
    sub.add_parser("estimate")
    a = ap.parse_args(argv)
    L = Listener(a.db, Fetcher(user_agent=USER_AGENT, min_interval=a.interval), workers=1)
    C = Collector(L)
    keys = lambda: [k for k in RETAILERS if RETAILERS[k]["enabled"]] if a.retailer == "all" else [a.retailer]
    Path("urls").mkdir(exist_ok=True)
    Path("reports").mkdir(exist_ok=True)

    if a.cmd == "discover":
        for k in keys():
            r = C.discover(k, per_category=a.per)
            Path(f"urls/{k}.json").write_text(json.dumps(r["by_category"], ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"{RETAILERS[k]['name']:<14} {r['total']:>5} pages produit · {r['files_read']} plans de site lus · "
                  + ", ".join(f"{c} {len(v)}" for c, v in r["by_category"].items()))
    elif a.cmd == "diagnose":
        lines = ["| Enseigne | Pages | Lues | Avec prix | Avec EAN | Bloquées | Verdict |", "|---|---|---|---|---|---|---|"]
        for k in keys():
            f = Path(f"urls/{k}.json")
            if not f.exists():
                print(f"{k} : lancez d'abord « python collect.py discover {k} »"); continue
            urls = [u for v in json.loads(f.read_text(encoding="utf-8")).values() for u in v]
            step = max(1, len(urls) // a.n)
            res = C.diagnose(k, urls[::step][:a.n])
            s = res["summary"]
            with open(f"reports/diagnostic-{k}.csv", "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(res["rows"][0]) if res["rows"] else ["url"]); w.writeheader(); w.writerows(res["rows"])
            p = lambda x: f"{x * 100:.0f} %"
            lines.append(f"| {RETAILERS[k]['name']} | {s['pages']} | {p(s['read_ok'])} | {p(s['with_price'])} | {p(s['with_gtin'])} | {p(s['blocked'])} | {s['verdict']} |")
            print(lines[-1])
        Path("reports/diagnostic.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif a.cmd == "build":
        for k in keys():
            f = Path(f"urls/{k}.json")
            if f.exists():
                print(json.dumps(C.build(k, json.loads(f.read_text(encoding="utf-8"))), ensure_ascii=False))
    elif a.cmd == "nightly":
        s = C.nightly()
        print(Path(f"reports/{s['report']}.md").read_text(encoding="utf-8"))
        return 2 if any(r["alert"] for r in s["retailers"].values()) else 0
    elif a.cmd == "review":
        for p in C.review_queue():
            print(f"[{p['id']}] {p['brand']} {p['title']} (EAN {p['gtin'] or '—'}) : " + " | ".join(o["merchant"] for o in p["offers"]))
    elif a.cmd == "estimate":
        print(C.estimate(a.interval))
    return 0


if __name__ == "__main__":
    sys.exit(main())
