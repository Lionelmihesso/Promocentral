"""Marché simulé avec VÉRITÉ CONNUE, pour mesurer la qualité des signaux.

Chaque offre suit un prix « normal » (érosion, bruit hebdomadaire, écart propre au marchand) et subit des épisodes :
  vraie promo marchand     ~1 fois / 70 j, 5-10 j, -10 à -20 %  (prix barré honnête 70 % du temps)
  Black Friday             85 % des offres, -12 à -25 %
  soldes d'hiver / d'été   50 % / 40 % des offres, -8 à -15 %
  FAUSSE promo             ~1 fois / 150 j : prix gonflé +30 % pendant 14 j, puis « -23 % » affiché
                           pendant 7 j… au prix normal (la remise affichée est réelle, l'opportunité non)
  hausse temporaire        ~1 fois / 200 j : +12 % pendant 10 j
  rupture                  ~1 fois / 100 j, 3-8 j
Vérité par produit et par jour :
  OPPORTUNITÉ  meilleur prix en stock ≤ 92 % du meilleur prix normal du marché
  FAUSSE PROMO une remise ≥ 15 % est affichée sans opportunité réelle
  CHER         meilleur prix en stock ≥ 108 % du meilleur prix normal
Usage : python -m bench.market_sim            (≈ 1 à 2 min)
"""
import json
import random
import sys
import time
from datetime import date, datetime, timedelta, timezone

from listener import intelligence as I
from listener.core import Listener

CATS = [("lave_vaisselle", "Lave-vaisselle", 520), ("lave_linge", "Lave-linge", 610), ("televiseur", "Téléviseur", 900)]
MOVING_CATS = [("canape", "Canapé 3 places", 1300), ("lit", "Lit 160 cadre de lit", 480), ("matelas", "Matelas 160x200", 650),
               ("refrigerateur", "Réfrigérateur combiné", 780), ("lave_linge", "Lave-linge", 560), ("lave_vaisselle", "Lave-vaisselle", 520),
               ("table", "Table à manger 6 places", 720), ("televiseur", "Téléviseur", 850), ("luminaire", "Luminaire suspension", 160)]
EXTRA = {"lave_vaisselle": "60 cm 14 couverts 42 dB", "lave_linge": "9 kg 1400 tr/min", "televiseur": '55" 4K'}
# (catégorie, titre avec attributs, prix de base) — 36 modèles, 10 catégories
MOVING_CATALOG = [
    ("canape", "Canapé 2 places tissu", 750), ("canape", "Canapé 3 places velours", 1150), ("canape", "Canapé 3 places convertible", 1350),
    ("canape", "Canapé d'angle 5 places", 1850),
    ("lit", "Lit 140x190 cadre de lit bois", 320), ("lit", "Lit 160x200 cadre de lit", 460), ("lit", "Lit 160x200 coffre de rangement", 640),
    ("lit", "Lit 180x200 cadre de lit", 690),
    ("matelas", "Matelas 140x190 mousse", 420), ("matelas", "Matelas 160x200 mousse", 590), ("matelas", "Matelas 160x200 ressorts ensachés", 820),
    ("matelas", "Matelas 180x200 mousse", 790),
    ("refrigerateur", "Réfrigérateur combiné 55 cm classe E", 480), ("refrigerateur", "Réfrigérateur combiné 60 cm classe D", 640),
    ("refrigerateur", "Réfrigérateur combiné 60 cm classe B", 820), ("refrigerateur", "Réfrigérateur combiné 70 cm classe C", 960),
    ("four", "Four encastrable multifonction classe A", 360), ("four", "Four encastrable pyrolyse classe A", 560),
    ("lave_linge", "Lave-linge 7 kg classe C", 390), ("lave_linge", "Lave-linge 8 kg classe B", 490), ("lave_linge", "Lave-linge 9 kg classe A", 640),
    ("lave_vaisselle", "Lave-vaisselle 45 cm 10 couverts classe E", 410), ("lave_vaisselle", "Lave-vaisselle 60 cm 13 couverts classe D", 470),
    ("lave_vaisselle", "Lave-vaisselle 60 cm 14 couverts 42 dB classe B", 620),
    ("table", "Table à manger 4 places", 380), ("table", "Table à manger 6 places chêne", 690), ("table", "Table à manger extensible 8 places", 940),
    ("televiseur", 'Téléviseur 43" 4K', 430), ("televiseur", 'Téléviseur 55" 4K', 690), ("televiseur", 'Téléviseur 65" 4K', 1090),
    ("luminaire", "Luminaire suspension métal", 110), ("luminaire", "Luminaire lampadaire arc", 170), ("luminaire", "Luminaire plafonnier LED", 80),
    ("lave_linge", "Lave-linge 10 kg classe A", 760), ("table", "Table à manger 6 places extensible", 820), ("canape", "Canapé 3 places cuir", 1990),
]
BRANDS = ["Nordvik", "Aurel", "Kessler", "Solenne"]
MERCHANTS = ["electroplus", "maisonco", "rapido", "bigbox"]


def gtin(n):
    body = f"{300000000000 + n:012d}"
    total = sum(int(x) * (3 if i % 2 else 1) for i, x in enumerate(body))
    return body + str((10 - total % 10) % 10)


class Market:
    def __init__(self, n_products=12, start=date(2025, 6, 1), days=460, seed=7, cats=None, promo_scale=1.0, catalog=None):
        self.promo_scale = promo_scale
        self.catalog = catalog
        self.start, self.days = start, days
        rng = random.Random(seed)
        self.products, self.offers = [], []
        for i in range(len(catalog) if catalog else n_products):
            if catalog:
                slug, label, base = catalog[i]
                brand = BRANDS[i % len(BRANDS)]
                m = __import__("re").search(r"classe ([A-G])", label)
                cls = m.group(1) if m else None
                p = {"id": i, "category": slug, "brand": brand, "gtin": gtin(i), "base": base * rng.uniform(0.92, 1.08),
                     "title": label.replace(" classe", f" {brand} classe") if cls else f"{label} {brand}", "energy": cls}
            else:
                cl = cats or CATS
                slug, label, base = cl[i % len(cl)]
                brand = BRANDS[(i // len(cl) + i) % len(BRANDS)]
                extra = EXTRA.get(slug, "")
                cls = "ABCD"[i % 4]
                p = {"id": i, "category": slug, "brand": brand, "gtin": gtin(i), "base": base * rng.uniform(0.7, 1.5),
                     "title": f"{label} {brand} Série {i} {extra} classe {cls}", "energy": cls}
            self.products.append(p)
            for m in rng.sample(MERCHANTS, 3):
                self.offers.append({"pid": i, "merchant": m, "url": f"https://{m}.sim/p/{i}",
                                    "factor": rng.uniform(0.97, 1.06)})
        self._simulate(rng)

    def _simulate(self, rng):
        D = self.days
        for o in self.offers:
            p = self.products[o["pid"]]
            normal, price, listp, stock, kind = [], [], [], [], []
            noise = 1.0
            for k in range(D):
                d = self.start + timedelta(days=k)
                if d.weekday() == 0:
                    noise = rng.uniform(0.98, 1.025)
                normal.append(round(p["base"] * o["factor"] * (1 - 0.06 * k / 365) * noise))
            price, listp, stock, kind = normal[:], [None] * D, [True] * D, ["normal"] * D

            def paint(a, b, fn, label):
                for j in range(max(0, a), min(D, b)):
                    if kind[j] == "normal":
                        fn(j)
                        kind[j] = label
            # événements commerciaux
            for y in (self.start.year, self.start.year + 1):
                for name, (a, b) in I.retail_events(y).items():
                    prob, lo, hi = {"black_friday": (0.85, .12, .25), "soldes_hiver": (0.5, .08, .15), "soldes_ete": (0.4, .08, .15)}[name]
                    if rng.random() < prob:
                        dep = rng.uniform(lo, hi)
                        ka, kb = (a - self.start).days, (b - self.start).days + 1

                        def f(j, dep=dep):
                            price[j] = round(normal[j] * (1 - dep))
                            listp[j] = normal[j]
                        paint(ka, kb, f, "true_promo")
            k = 0
            while k < D:
                r = rng.random()
                if r < self.promo_scale / 70:
                    n, dep, honest = rng.randint(5, 10), rng.uniform(.10, .20), rng.random() < 0.7

                    def f(j, dep=dep, honest=honest):
                        price[j] = round(normal[j] * (1 - dep))
                        listp[j] = normal[j] if honest else None
                    paint(k, k + n, f, "true_promo")
                    k += n
                elif r < self.promo_scale / 70 + 1 / 150:
                    def up(j):
                        price[j] = round(normal[j] * 1.30)

                    def fake(j):
                        price[j] = round(normal[j] * rng.uniform(0.98, 1.02))
                        listp[j] = round(normal[j] * 1.30)
                    paint(k, k + 14, up, "inflated")
                    paint(k + 14, k + 21, fake, "fake_promo")
                    k += 21
                elif r < self.promo_scale / 70 + 1 / 150 + 1 / 200:
                    def hike(j):
                        price[j] = round(normal[j] * 1.12)
                    paint(k, k + 10, hike, "hike")
                    k += 10
                elif r < self.promo_scale / 70 + 1 / 150 + 1 / 200 + 1 / 100:
                    n = rng.randint(3, 8)
                    for j in range(k, min(D, k + n)):
                        stock[j] = False
                    k += n
                else:
                    k += 1
            o.update(normal=normal, price=price, list=listp, stock=stock, kind=kind)

    def truth(self, pid, k):
        offs = [o for o in self.offers if o["pid"] == pid]
        normal_best = min(o["normal"][k] for o in offs)
        live = [o for o in offs if o["stock"][k]]
        if not live:
            return {"opp": False, "fake": False, "high": False, "best": None, "advertised": 0.0}
        best = min(o["price"][k] for o in live)
        opp = best <= normal_best * 0.92
        fake = (not opp) and any(o["kind"][k] == "fake_promo" and o["stock"][k] for o in offs)
        return {"opp": opp, "fake": fake, "high": best >= normal_best * 1.08, "best": best,
                "advertised": max(((1 - o["price"][k] / o["list"][k]) for o in live if o["list"][k]), default=0.0)}

    def html(self, url, k):
        o = next(x for x in self.offers if x["url"] == url)
        p = self.products[o["pid"]]
        offer = {"@type": "Offer", "price": f"{o['price'][k]:.2f}", "priceCurrency": "EUR",
                 "availability": "https://schema.org/" + ("InStock" if o["stock"][k] else "OutOfStock")}
        if o["list"][k]:
            offer["priceSpecification"] = [{"@type": "UnitPriceSpecification", "price": o["price"][k], "priceCurrency": "EUR"},
                                           {"@type": "UnitPriceSpecification", "priceType": "https://schema.org/ListPrice",
                                            "price": o["list"][k], "priceCurrency": "EUR"}]
        ld = {"@context": "https://schema.org", "@type": "Product", "name": p["title"], "gtin13": p["gtin"],
              "brand": {"@type": "Brand", "name": p["brand"]}, "category": p["category"].replace("_", "-"),
              "additionalProperty": [{"@type": "PropertyValue", "name": "Classe énergétique", "value": p["energy"]}] if p["energy"] else [],
              "offers": offer}
        return f"<html><head><script type='application/ld+json'>{json.dumps(ld, ensure_ascii=False)}</script></head><body></body></html>"


class SimClock:
    def __init__(self, d):
        self.t = datetime(d.year, d.month, d.day, 10, tzinfo=timezone.utc).timestamp()

    def __call__(self):
        return self.t


class SimFetcher:
    ua = "sim"

    def __init__(self, market, clock):
        self.m, self.clock = market, clock

    def get(self, url, etag=None, last_modified=None):
        k = (datetime.fromtimestamp(self.clock(), timezone.utc).date() - self.m.start).days
        return {"status": "ok", "code": 200, "html": self.m.html(url, k), "elapsed_ms": 0}


def run(n_products=12, days=460, warmup=120, seed=7, verbose=True):
    t0 = time.time()
    m = Market(n_products, days=days, seed=seed)
    clock = SimClock(m.start)
    L = Listener(fetcher=SimFetcher(m, clock), clock=clock, workers=1)
    for o in m.offers:
        L.track(o["url"], 2, o["merchant"])
    pid_map = {}
    rows = []
    for k in range(days):
        clock.t = SimClock(m.start + timedelta(days=k)).t
        L.q("UPDATE offers SET next_check_at=0 WHERE status='active'")
        L.run_due(limit=10000)
        if not pid_map:
            for o in m.offers:
                pid_map[o["pid"]] = L.q("SELECT product_id FROM offers WHERE url=?", (o["url"],), one=True)["product_id"]
        if k < warmup:
            continue
        for sp, pid in pid_map.items():
            act = {s["type"] for s in L.signals(product_id=pid)}
            snap = L._snap.get(pid)
            tr = m.truth(sp, k)
            b7 = m.truth(sp, k - 7)["best"]
            rows.append({"k": k, "pid": sp, **tr, "state": snap["intel"]["state"] if snap else None,
                         "opp_sig": bool(act & {"PRICE_OPPORTUNITY", "MARKET_WIDE_OPPORTUNITY"}),
                         "wide": "MARKET_WIDE_OPPORTUNITY" in act, "high_sig": "PRICE_HIGH" in act,
                         "naive_adv": tr["advertised"] >= 0.15,
                         "naive_drop": bool(tr["best"] and b7 and tr["best"] <= b7 * 0.9),
                         "event": I.event_of(m.start + timedelta(days=k))})
    res = evaluate(rows, L, m, days - warmup, time.time() - t0)
    if verbose:
        report(res)
    return res, L, m


def prf(rows, pred, truth):
    tp = sum(1 for r in rows if r[pred] and r[truth])
    fp = sum(1 for r in rows if r[pred] and not r[truth])
    fn = sum(1 for r in rows if not r[pred] and r[truth])
    p = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(p, 3), "recall": round(rc, 3), "f1": round(2 * p * rc / (p + rc), 3) if p + rc else 0.0,
            "flagged_days": tp + fp}


def evaluate(rows, L, m, eval_days, secs):
    rows = [r for r in rows if r["best"] is not None]
    fake = [r for r in rows if r["fake"]]
    ev = {r["type"]: r["n"] for r in L.q("SELECT type, COUNT(*) n FROM events GROUP BY type")}
    months = eval_days / 30 * len(m.products)
    raised = L.q("SELECT COUNT(*) n FROM events WHERE type='SIGNAL_RAISED' AND json_extract(data,'$.signal') IN "
                 "('PRICE_OPPORTUNITY','MARKET_WIDE_OPPORTUNITY')", one=True)["n"]
    bf = [r for r in rows if r["event"] == "black_friday" and r["opp"]]
    return {
        "product_days": len(rows), "truth_opportunity_days": sum(r["opp"] for r in rows),
        "engine": prf(rows, "opp_sig", "opp"),
        "naive_advertised_15pct": prf(rows, "naive_adv", "opp"),
        "naive_drop_10pct_vs_7d": prf(rows, "naive_drop", "opp"),
        "fake_promo_days": len(fake),
        "fake_ignored_engine": round(sum(not r["opp_sig"] for r in fake) / len(fake), 3) if fake else None,
        "fake_ignored_naive_adv": round(sum(not r["naive_adv"] for r in fake) / len(fake), 3) if fake else None,
        "price_high": prf(rows, "high_sig", "high"),
        "black_friday_recall": round(sum(r["opp_sig"] for r in bf) / len(bf), 3) if bf else None,
        "opportunity_alerts_per_product_month": round(raised / months, 2),
        "price_drop_events_per_product_month": round(ev.get("PRICE_DROP", 0) / months, 2),
        "events": ev, "seconds": round(secs, 1),
        "state_distribution": {s: sum(1 for r in rows if r["state"] == s) for s in I.STATES},
    }


def report(r):
    e, a, d = r["engine"], r["naive_advertised_15pct"], r["naive_drop_10pct_vs_7d"]
    print(f"\nMarché simulé : {r['product_days']} produit-jours évalués, {r['truth_opportunity_days']} jours de vraie opportunité ({r['seconds']} s)")
    print("\nDétection d'opportunité             précision  rappel   F1   jours signalés")
    for name, x in (("Moteur (signaux de marché)", e), ("Naïf : remise affichée ≥ 15 %", a), ("Naïf : -10 % vs il y a 7 j", d)):
        print(f"  {name:<34} {x['precision']:>6.1%}  {x['recall']:>6.1%}  {x['f1']:.2f}  {x['flagged_days']:>6}")
    print(f"\nFausses promos (« -23 % » au prix normal) : {r['fake_promo_days']} jours")
    print(f"  ignorées par le moteur : {r['fake_ignored_engine']:.0%}   | par la règle « remise affichée » : {r['fake_ignored_naive_adv']:.0%}")
    h = r["price_high"]
    print(f"\nSignal « prix élevé » : précision {h['precision']:.0%}, rappel {h['recall']:.0%}")
    print(f"Black Friday : {r['black_friday_recall']:.0%} des jours d'opportunité couverts")
    print(f"Bruit : {r['opportunity_alerts_per_product_month']} alerte(s) d'opportunité par produit et par mois, "
          f"contre {r['price_drop_events_per_product_month']} baisses de prix brutes")
    print("États du prix :", r["state_distribution"])


if __name__ == "__main__":
    run(n_products=int(sys.argv[1]) if len(sys.argv) > 1 else 12)
