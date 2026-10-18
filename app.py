"""DEALS — serveur de l'app grand public (/) et de la console interne (/admin).

  python app.py serve [--db deals.sqlite] [--port 8000]   base réelle (alimentée par collect.py + radar.py daily)
  python app.py demo  [--port 8000]                       marché simulé (électroménager, TV, literie) avec un bouton « jour suivant »
"""
import os
import tempfile
import argparse
import threading
from datetime import date, timedelta

from collect.pipeline import Collector
from listener.core import Listener
from listener.server import serve
from radar.api import admin_routes, routes as radar_routes
from radar.engine import Radar


def build_demo(warmup_days=90, start=date(2026, 1, 5)):
    from bench.market_sim import MOVING_CATALOG, Market, SimClock, SimFetcher
    cat = [c for c in MOVING_CATALOG if c[0] in ("lave_linge", "lave_vaisselle", "refrigerateur", "televiseur", "four", "matelas")]
    m = Market(start=start, days=warmup_days + 120, seed=4, catalog=cat)
    clock = SimClock(start)
    L = Listener(fetcher=SimFetcher(m, clock), clock=clock, workers=1)
    C = Collector(L, {"sim": {"name": "Simulé", "home": "http://sim", "enabled": True, "product_url": ".", "sitemaps": []}}, report_dir=os.path.join(tempfile.gettempdir(), "deals_demo_reports"))
    for o in m.offers:
        oid = L.track(o["url"], 2, o["merchant"])
        L.q("INSERT OR IGNORE INTO collect_offers(offer_id, retailer, category_hint, added_at) VALUES (?,?,?,0)", (oid, "sim", None))
    R = Radar(L)
    state = {"k": 0}

    def goto(k):
        clock.t = SimClock(start + timedelta(days=k)).t
        state["k"] = k
    for k in range(warmup_days):
        goto(k)
        with L.batch():
            C.nightly()
    me = R.user("moi", budget_max=1500)
    R.follow(me, "category", "televiseur")
    goto(warmup_days)
    R.run_daily(C)

    def next_day():
        goto(state["k"] + 1)
        with L.batch():
            return R.run_daily(C)
    demo_routes = [("GET", r"/api/demo/day", lambda b, q: {"day": L.today().isoformat()}),
                   ("POST", r"/api/demo/next", lambda b, q: next_day())]
    return L, R, demo_routes


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["serve", "demo"])
    ap.add_argument("--db", default="deals.sqlite")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--admin", action="store_true", help="expose la console et l'API marché (outil interne, à ne pas publier)")
    a = ap.parse_args(argv)
    if a.cmd == "demo":
        print("Préparation du marché simulé (90 jours d'historique)…")
        L, R, extra = build_demo()
    else:
        L = Listener(a.db, workers=1)
        R, extra = Radar(L), []
    admin = a.admin or a.cmd == "demo"
    srv = serve(L, a.port, extra=radar_routes(R) + (admin_routes(R) + extra if admin else []), admin=admin)
    print(f"App : http://127.0.0.1:{a.port}/" + (f"   ·   console interne : http://127.0.0.1:{a.port}/admin" if admin else ""))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
        L.close()


if __name__ == "__main__":
    main()
