"""Collecte DEALS — ligne de commande.

  python collect.py discover all --per 20            trouve des pages produit dans les plans de site (urls/<enseigne>.json)
  python collect.py diagnose all --n 20              teste 20 pages par enseigne → garder / règle / abandonner (reports/diagnostic.md)
  python collect.py sample all --n 5                 enregistre 5 pages brutes par enseigne (samples/) pour une mise au point hors ligne
  python collect.py explain <adresse>                ce que l'extraction voit sur une page : sources, prix, prix barré, raisons
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
    for c in ("discover", "diagnose", "build", "sample"):
        s = sub.add_parser(c)
        s.add_argument("retailer", help="clé d'enseigne ou « all »")
        s.add_argument("--per", type=int, default=20, help="discover : pages par catégorie")
        s.add_argument("--n", type=int, default=20, help="diagnose / sample : pages par enseigne")
    e = sub.add_parser("explain", help="analyse d'une seule page")
    e.add_argument("url")
    sub.add_parser("nightly")
    sub.add_parser("review")
    sub.add_parser("estimate")
    r = sub.add_parser("rules", help="règle d'extraction d'un site, ex. rules www.site.fr '{\"price\": \".prix\"}'")
    r.add_argument("host")
    r.add_argument("rules", help="JSON : sélecteurs CSS (price, list_price, title, gtin…)")
    a = ap.parse_args(argv)
    L = Listener(a.db, Fetcher(user_agent=USER_AGENT, min_interval=a.interval), workers=1)
    C = Collector(L)
    keys = lambda: [k for k in RETAILERS if RETAILERS[k]["enabled"]] if a.retailer == "all" else [a.retailer]

    def sample_urls(k, n):
        f = Path(f"urls/{k}.json")
        if not f.exists():
            print(f"{k} : lancez d'abord « python collect.py discover {k} »")
            return None
        urls = [u for v in json.loads(f.read_text(encoding="utf-8")).values() for u in v]
        return urls[::max(1, len(urls) // n)][:n]
    Path("urls").mkdir(exist_ok=True)
    Path("reports").mkdir(exist_ok=True)

    if a.cmd == "rules":
        L.set_rules(a.host, json.loads(a.rules))
        print(f"règle enregistrée pour {a.host} : relancez « python collect.py diagnose <enseigne> »")
        return 0
    if a.cmd == "discover":
        for k in keys():
            r = C.discover(k, per_category=a.per)
            Path(f"urls/{k}.json").write_text(json.dumps(r["by_category"], ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"{RETAILERS[k]['name']:<14} {r['total']:>5} pages produit · {r['files_read']} plans de site lus · "
                  + ", ".join(f"{c} {len(v)}" for c, v in r["by_category"].items()))
    elif a.cmd == "diagnose":
        lines = ["| Enseigne | Pages | Lues | Avec prix | Prix barré | EAN | Bloquées | Protection | Verdict |", "|---|---|---|---|---|---|---|---|---|"]
        for k in keys():
            urls = sample_urls(k, a.n)
            if urls is None:
                continue
            res = C.diagnose(k, urls)
            s = res["summary"]
            with open(f"reports/diagnostic-{k}.csv", "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(res["rows"][0]) if res["rows"] else ["url"]); w.writeheader(); w.writerows(res["rows"])
            p = lambda x: f"{x * 100:.0f} %"
            prot = ", ".join(f"{v} ({n})" for v, n in s["protections"].items()) or "—"
            lines.append(f"| {RETAILERS[k]['name']} | {s['pages']} | {p(s['read_ok'])} | {p(s['with_price'])} | {p(s['with_was'])} | "
                         f"{p(s['with_gtin'])} | {p(s['blocked'])} | {prot} | {s['verdict']} |")
            print(lines[-1])
            print(f"    prix : {s['methods'] or '—'} · prix barré : {s['was_methods'] or '—'} · statuts : {s['statuses']}")
        Path("reports/diagnostic.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif a.cmd == "sample":
        for k in keys():
            urls = sample_urls(k, a.n)
            if urls:
                r = C.sample(k, urls)
                print(f"{RETAILERS[k]['name']:<16} {r['saved']}/{r['pages']} pages enregistrées dans {r['dir']}")
        print("Compressez le dossier samples/ et joignez-le : l'extraction se règle alors sur vos vraies pages.")
    elif a.cmd == "explain":
        d = L.diagnose(a.url)
        print(f"statut {d['status']} (HTTP {d.get('code')}) · page {d.get('page_kind')} · protection {d.get('protection') or '—'}")
        for c in d.get("candidates") or []:
            print(f"  source {c['method']:<10} prix {c['price']} · barré {c['list_price']} · {c['currency']} · {c['availability']} · EAN {c['gtin']}")
        ex = d.get("extraction")
        if ex:
            print(f"→ retenu : {ex['price']} € ({ex['method']}) · prix barré {ex.get('list_price')} ({ex.get('was_method') or '—'}) · "
                  f"{ex['availability']} · {ex.get('title')} · vendeur {ex.get('seller') or '—'}")
        for r in d.get("reasons") or []:
            print(f"  ! {r}")
        if d.get("hint"):
            print(d["hint"])
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
