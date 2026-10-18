"""DEALS — une seule ligne de commande.

  python deals.py serve [--port 8000]                l'app et son API (en production, derrière Caddy)
  python deals.py demo [--port 8000] [--days 90]     l'app sur un marché simulé (base temporaire)
  python deals.py nightly                            la nuit : collecte → publication → rapport du matin
  python deals.py publish                            republier le catalogue sans relire le web
  python deals.py discover|diagnose|sample|build <enseigne|all>     constituer et régler la base
  python deals.py explain <adresse>                  ce que l'extraction voit sur une page
  python deals.py rules <site> '<json>'              règle de lecture d'un site (sélecteurs)
  python deals.py review | estimate | metrics        rapprochements à vérifier, durée de la nuit, mesures
  python deals.py backup <dossier> [--keep 14]       sauvegarde à chaud vérifiée
Option commune, avant la commande : --db (défaut : DEALS_DB, sinon deals.sqlite). Réglages : deals/config.py.
Les commandes qui lisent les sites refusent de partir sans DEALS_USER_AGENT (nom du robot, page, contact).
"""
import argparse
import csv
import json
import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

from . import config
from .api import Api
from .backup import backup
from .collect import diagnose as D
from .collect import report
from .collect.crawl import Crawler
from .collect.discover import discover
from .collect.retailers import RETAILERS
from .fetch import Fetcher
from .market import Market
from .publish import publish
from .store import Store
from .web import make_server


NETWORK = ("nightly", "discover", "diagnose", "sample", "build", "explain")


def _serve(store, settings, port):
    srv = make_server(Api(store, settings), store, settings, port=port)
    print(f"App : http://127.0.0.1:{port}/")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


def main(argv=None):
    try:
        settings = config.load()
    except ValueError as e:
        sys.exit(f"Réglage invalide : {e}")
    ap = argparse.ArgumentParser(prog="deals", description="DEALS — les bons deals du jour")
    ap.add_argument("--db", default=settings.db)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("serve", "demo"):
        s = sub.add_parser(name)
        s.add_argument("--port", type=int, default=settings.port)
        if name == "demo":
            s.add_argument("--days", type=int, default=90)
    sub.add_parser("nightly")
    sub.add_parser("publish")
    for name in ("discover", "diagnose", "sample", "build"):
        s = sub.add_parser(name)
        s.add_argument("retailer", help="clé d'enseigne ou « all »")
        s.add_argument("--per", type=int, default=40, help="discover : fiches par catégorie")
        s.add_argument("--n", type=int, default=20, help="diagnose / sample : pages par enseigne")
    sub.add_parser("explain").add_argument("url")
    r = sub.add_parser("rules")
    r.add_argument("host")
    r.add_argument("rules", help="JSON : sélecteurs (price, list_price, availability, title, gtin…)")
    for name in ("review", "estimate", "metrics"):
        sub.add_parser(name)
    b = sub.add_parser("backup")
    b.add_argument("dest")
    b.add_argument("--keep", type=int, default=14)
    a = ap.parse_args(argv)
    settings = replace(settings, db=a.db)
    if a.cmd in NETWORK and settings.user_agent == config.Settings.user_agent:
        sys.exit("Avant de lire les sites, réglez DEALS_USER_AGENT : nom du robot, page qui le décrit, contact "
                 "(voir deploy/deals.env.example). Les enseignes doivent savoir qui les lit.")

    if a.cmd == "demo":
        from .demo import build
        store = Store(os.path.join(tempfile.mkdtemp(prefix="deals-demo-"), "demo.sqlite"))
        print(f"Marché simulé : {a.days} jours d'historique…")
        build(store, days=a.days)
        return _serve(store, settings, a.port)
    if a.cmd == "backup":
        print(backup(settings.db, a.dest, a.keep))
        return 0
    store = Store(settings.db)
    if a.cmd == "serve":
        return _serve(store, settings, a.port)

    market = Market(store)
    fetcher = Fetcher(user_agent=settings.user_agent, min_interval=settings.min_interval_s)
    crawler = Crawler(market, fetcher, RETAILERS, settings.night_budget_s)
    keys = lambda: [k for k in RETAILERS if RETAILERS[k]["enabled"]] if a.retailer == "all" else [a.retailer]

    def urls(k, n=None):
        f = Path(f"urls/{k}.json")
        if not f.exists():
            print(f"{k} : lancez d'abord « python deals.py discover {k} »")
            return None
        by_cat = json.loads(f.read_text(encoding="utf-8"))
        if n is None:
            return by_cat
        flat = [u for v in by_cat.values() for u in v]
        return flat[::max(1, len(flat) // n)][:n]

    if a.cmd == "nightly":
        stats = crawler.nightly()
        name = report.write(stats, settings.reports_dir)
        stats["publish"] = publish(store, market.today(), market.clock())
        print(Path(settings.reports_dir, f"{name}.md").read_text(encoding="utf-8"))
        print("Catalogue publié :", json.dumps(stats["publish"], ensure_ascii=False))
    elif a.cmd == "publish":
        print(json.dumps(publish(store, market.today(), market.clock()), ensure_ascii=False))
    elif a.cmd == "discover":
        Path("urls").mkdir(exist_ok=True)
        for k in keys():
            res = discover(fetcher, RETAILERS[k], a.per)
            Path(f"urls/{k}.json").write_text(json.dumps(res["by_category"], ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"{RETAILERS[k]['name']:<16} {res['total']:>5} fiches · {res['files_read']} plans de site lus · "
                  + ", ".join(f"{c} {len(v)}" for c, v in res["by_category"].items()))
    elif a.cmd == "diagnose":
        Path(settings.reports_dir).mkdir(exist_ok=True)
        pct = lambda x: f"{x * 100:.0f} %"
        lines = ["| Enseigne | Pages | Lues | Avec prix | Prix barré | EAN | Bloquées | Protection | Verdict |", "|---|---|---|---|---|---|---|---|---|"]
        for k in keys():
            u = urls(k, a.n)
            if u is None:
                continue
            res = D.diagnose(crawler, k, u)
            s = res["summary"]
            with open(Path(settings.reports_dir, f"diagnostic-{k}.csv"), "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(res["rows"][0]) if res["rows"] else ["url"])
                w.writeheader()
                w.writerows(res["rows"])
            prot = ", ".join(f"{v} ({n})" for v, n in s["protections"].items()) or "—"
            lines.append(f"| {RETAILERS[k]['name']} | {s['pages']} | {pct(s['read_ok'])} | {pct(s['with_price'])} | {pct(s['with_was'])} | "
                         f"{pct(s['with_gtin'])} | {pct(s['blocked'])} | {prot} | {s['verdict']} |")
            print(lines[-1])
            print(f"    prix : {s['methods'] or '—'} · prix barré : {s['was_methods'] or '—'} · statuts : {s['statuses']}")
        Path(settings.reports_dir, "diagnostic.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif a.cmd == "sample":
        for k in keys():
            u = urls(k, a.n)
            if u:
                res = D.sample(fetcher, k, u)
                print(f"{RETAILERS[k]['name']:<16} {res['saved']}/{res['pages']} pages enregistrées dans {res['dir']}")
        print("Compressez le dossier samples/ et joignez-le : l'extraction se règle alors sur vos vraies pages.")
    elif a.cmd == "build":
        for k in keys():
            u = urls(k)
            if u:
                print(json.dumps(crawler.build(k, u), ensure_ascii=False))
    elif a.cmd == "explain":
        d = crawler.inspect(a.url)
        print(f"statut {d['status']} (HTTP {d.get('code')}) · page {d.get('page_kind')} · protection {d.get('protection') or '—'}")
        for c in d.get("candidates") or []:
            print(f"  source {c['method']:<10} prix {c['price']} · barré {c['list_price']} · {c['currency']} · {c['availability']} · EAN {c['gtin']}")
        ex = d.get("extraction")
        if ex:
            print(f"→ retenu : {ex['price']} € ({ex['method']}) · prix barré {ex.get('list_price')} ({ex.get('was_method') or '—'}) · "
                  f"{ex['availability']} · {ex.get('title')} · vendeur {ex.get('seller') or '—'} · catalogue : {d.get('scope') or 'oui'}")
        for reason in d.get("reasons") or []:
            print(f"  ! {reason}")
        if d.get("hint"):
            print(d["hint"])
    elif a.cmd == "rules":
        market.set_rules(a.host, json.loads(a.rules))
        print(f"règle enregistrée pour {a.host} : relancez « python deals.py diagnose <enseigne> »")
    elif a.cmd == "review":
        for p in store.q("SELECT id, title, brand, gtin FROM products WHERE needs_review=1 LIMIT 50"):
            merchants = " | ".join(o["merchant"] for o in store.q("SELECT merchant FROM offers WHERE product_id=?", (p["id"],)))
            print(f"[{p['id']}] {p['brand'] or ''} {p['title']} (EAN {p['gtin'] or '—'}) : {merchants}")
    elif a.cmd == "estimate":
        print(crawler.estimate())
    elif a.cmd == "metrics":
        from .activity import Activity
        last = store.q("SELECT day, stats FROM runs WHERE stats IS NOT NULL ORDER BY id DESC LIMIT 1", one=True)
        print(json.dumps({**Activity(store).metrics(),
                          "catalog": store.q("SELECT COUNT(*) products, SUM(pct > 0) deals, SUM(verified) verified FROM catalog", one=True),
                          "last_night": {"day": last["day"], **{k: v for k, v in json.loads(last["stats"]).items() if k in ("offers", "products")}}
                          if last else None}, ensure_ascii=False, indent=1, default=str))
    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
