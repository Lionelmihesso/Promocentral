"""Validation SQL requête par requête vs transaction groupée, sur une base fichier (comme en production).
Même travail : 30 nuits de collecte + la tâche radar quotidienne. Usage : python -m bench.transactions"""
import os
import tempfile
import time
from datetime import date, timedelta

from bench.market_sim import MOVING_CATALOG, Market, SimClock, SimFetcher
from collect.pipeline import Collector
from listener.core import Listener
from radar.engine import Radar


def run(batched, days=30):
    start = date(2026, 1, 5)
    m = Market(start=start, days=days, seed=4, catalog=[c for c in MOVING_CATALOG if c[0] in ("lave_linge", "televiseur", "refrigerateur")])
    path = os.path.join(tempfile.mkdtemp(), "b.sqlite")
    clock = SimClock(start)
    L = Listener(path, fetcher=SimFetcher(m, clock), clock=clock, workers=1)
    C = Collector(L, {"sim": {"name": "Sim", "home": "x", "enabled": True, "product_url": ".", "sitemaps": []}}, report_dir=tempfile.mkdtemp())
    for o in m.offers:
        oid = L.track(o["url"], 2, o["merchant"])
        L.q("INSERT OR IGNORE INTO collect_offers(offer_id, retailer, added_at) VALUES (?,?,0)", (oid, "sim"))
    R = Radar(L)
    u = R.user("a"); R.follow(u, "category", "televiseur")
    t0 = time.perf_counter()
    for k in range(days):
        clock.t = SimClock(start + timedelta(days=k)).t
        if batched:
            with L.batch():
                R.run_daily(C)
        else:
            R.run_daily(C)
    dt = time.perf_counter() - t0
    n = L.q("SELECT COUNT(*) n FROM observations", one=True)["n"]
    L.close()
    return dt, n


if __name__ == "__main__":
    a, na = run(False)
    b, nb = run(True)
    print(f"30 nuits, mêmes données ({na} = {nb} observations)")
    print(f"  validation à chaque requête : {a:.1f} s")
    print(f"  transaction par nuit        : {b:.1f} s  ({(1 - b / a) * 100:.0f} % plus rapide)")
