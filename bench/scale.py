"""Tenue en charge : publication de nuit et lectures de l'app sur un catalogue de 3 000 produits.

Données synthétiques du volume mesuré sur l'ancien moteur (docs/AUDIT.md) : 3 000 produits (120 marques, 8 catégories),
4 200 offres, ~40 000 lignes de prix sur 90 jours (un changement tous les 9 jours environ, prix barré sur une partie
des lignes). Elles sont écrites directement en base : on mesure la publication et les lectures, pas la collecte.

  python -m bench.scale                    base temporaire générée
  python -m bench.scale --db base.sqlite   base existante (déjà remplie), sans génération
"""
import argparse
import json
import random
import statistics
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from deals import config
from deals.api import Api, Request
from deals.extract import attributes
from deals.market import norm_title
from deals.publish import publish
from deals.sim import gtin
from deals.store import Store

NOW = datetime(2026, 10, 18, 20, tzinfo=timezone.utc)
FAMILIES = [("lave_linge", "Lave-linge hublot {n} kg classe {e}", (7, 8, 9, 10), 320, 900),
            ("refrigerateur", "Réfrigérateur combiné {n} cm classe {e}", (55, 60, 70), 450, 1300),
            ("lave_vaisselle", "Lave-vaisselle {n} couverts classe {e}", (10, 13, 14), 350, 850),
            ("four", "Four encastrable pyrolyse {n} L classe {e}", (65, 71, 72), 300, 900),
            ("canape", "Canapé {n} places convertible", (2, 3, 4, 5), 600, 2200),
            ("lit", "Lit {n}x200 coffre de rangement", (140, 160, 180), 300, 900),
            ("matelas", "Matelas {n}x200 ressorts ensachés", (140, 160, 180), 350, 1200),
            ("table", "Table à manger extensible {n} places", (4, 6, 8, 10), 300, 1100)]


def generate(store, products=3000, extra_offers=1200, days=90, seed=7):
    rng = random.Random(seed)
    now = NOW.timestamp()
    brands = [f"Marque{i:03d}" for i in range(120)]
    merchants = [f"Enseigne {i}" for i in range(6)]
    prods, offers, prices = [], [], []
    for i in range(products):
        cat, pattern, sizes, lo, hi = FAMILIES[i % len(FAMILIES)]
        brand = brands[rng.randrange(len(brands))]
        title = pattern.format(n=rng.choice(sizes), e=rng.choice("ABCDE")) + f" {brand} M{i:04d}"
        prods.append((i + 1, gtin(10000 + i), brand, title, norm_title(title), cat, json.dumps(attributes(title)), now - days * 86400))
    owners = list(range(1, products + 1)) + rng.sample(range(1, products + 1), extra_offers)
    for oid, pid in enumerate(owners, 1):
        m = merchants[(pid + oid) % len(merchants)]
        host = m.lower().replace(" ", "") + ".fr"
        offers.append((oid, f"https://{host}/p/{oid}", host, host, m, pid, "active", now, now - days * 86400))
        cat = prods[pid - 1][5]
        lo, hi = next((f[3], f[4]) for f in FAMILIES if f[0] == cat)
        base = rng.uniform(lo, hi)
        t = now - days * 86400
        while t < now:
            span = min(now - t, rng.expovariate(1 / (9 * 86400)) + 3600)
            promo = rng.random() < 0.25
            price = round(base * (rng.uniform(0.70, 0.92) if promo else rng.uniform(0.97, 1.05)), 2)
            prices.append((oid, t, t + span, price, round(base, 2) if promo else None,
                           "out_of_stock" if rng.random() < 0.05 else "in_stock"))
            t += span
    with store.tx() as c:
        c.executemany("INSERT INTO products(id, gtin, brand, title, norm_title, category, attributes, created_at) "
                      "VALUES (?,?,?,?,?,?,?,?)", prods)
        c.executemany("INSERT INTO offers(id, url, host, retailer, merchant, product_id, status, checked_at, created_at) "
                      "VALUES (?,?,?,?,?,?,?,?,?)", offers)
        c.executemany("INSERT INTO prices(offer_id, first_seen, last_seen, price, was, availability) VALUES (?,?,?,?,?,?)", prices)
    return len(prods), len(offers), len(prices)


def timed(fn, n):
    out = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        out.append(time.perf_counter() - t)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", help="base existante, déjà remplie")
    ap.add_argument("-n", type=int, default=200, help="lectures par route")
    a = ap.parse_args(argv)
    path = Path(a.db) if a.db else Path(tempfile.mkdtemp(), "scale.sqlite")
    store = Store(path)
    if not a.db:
        p, o, r = generate(store)
        print(f"données : {p} produits, {o} offres, {r} lignes de prix sur 90 jours")
    today, now = NOW.date(), NOW.timestamp()
    pub = timed(lambda: publish(store, today, now), 3)
    stats = publish(store, today, now)
    print(f"publication (une fois par nuit) : {statistics.median(pub) * 1000:.0f} ms · {stats['products']} produits publiés, "
          f"{stats['deals']} remises montrées, {stats['fake']} fausses écartées")

    api = Api(store, config.load({}), clock=lambda: now)
    api.accounts.request_link("bench@deals.test")
    session = api.accounts.verify(api.accounts.outbox.sent[-1][1].split("token=")[1])[1].split(";")[0].split("=", 1)[1]
    deals = api.handle(Request("GET", "/api/r/today")).body["products"]
    for b in {d["brand"] for d in deals[:3]}:
        api.handle(Request("POST", "/api/r/brand/follow", body={"brand": b}, session=session))
    for d in deals[:5]:
        api.handle(Request("POST", "/api/r/save", body={"product_id": d["id"]}, session=session))
    brand, cat, pid = deals[0]["brand"], deals[0]["category"], deals[0]["id"]
    routes = [("today", "/api/r/today", {}, ""), ("today?category", "/api/r/today", {"category": cat}, ""),
              ("today?q", "/api/r/today", {"q": "lave linge 9 kg"}, ""), ("search?q", "/api/r/search", {"q": "lave linge 9 kg"}, ""),
              ("categories", "/api/r/categories", {}, ""),
              ("brands", "/api/r/brands", {}, ""), ("brand/<nom>", f"/api/r/brand/{brand}", {}, ""),
              ("item/<id>", f"/api/r/item/{pid}", {}, ""), ("today (connecté)", "/api/r/today", {}, session),
              ("saves (connecté)", "/api/r/saves", {}, session)]
    print(f"lectures de l'app ({a.n} par route, réponse JSON comprise) :")
    for name, route, query, sess in routes:
        def call():
            r = api.handle(Request("GET", route, query=query, session=sess))
            assert r.status == 200, (route, r.status)
            json.dumps(r.body, ensure_ascii=False)
        xs = sorted(timed(call, a.n))
        print(f"  {name:18} médiane {statistics.median(xs) * 1000:6.2f} ms · 95e centile {xs[int(len(xs) * 0.95) - 1] * 1000:6.2f} ms")
    store.close()
    print(f"base : {path.stat().st_size / 1e6:.1f} Mo")


if __name__ == "__main__":
    main()
