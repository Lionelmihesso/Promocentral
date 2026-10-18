"""Marché simulé à VÉRITÉ CONNUE : démo de l'app et mesure des règles (bench/deals_truth.py).

Chaque offre suit un prix « normal » (érosion, bruit hebdomadaire, écart propre à l'enseigne) et subit des épisodes :
  vraie promo de l'enseigne  ~1 fois / 70 j, 5-10 j, -10 à -20 % (prix barré honnête 70 % du temps)
  Black Friday               85 % des offres, -12 à -25 % ; soldes d'hiver / d'été : 50 % / 40 % des offres, -8 à -15 %
  FAUSSE promo               ~1 fois / 150 j : prix gonflé de 30 % pendant 14 j, puis « -23 % » affiché pendant 7 j au
                             prix normal
  hausse temporaire          ~1 fois / 200 j : +12 % pendant 10 j ;   rupture : ~1 fois / 100 j, 3 à 8 j
Vérité par produit et par jour : OPPORTUNITÉ = meilleur prix en stock ≤ 92 % du meilleur prix normal du marché.
"""
import json
import random
import re
from datetime import date, datetime, timedelta, timezone

# (catégorie, titre avec attributs, prix de base)
CATALOG = [
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
    ("lave_linge", "Lave-linge 10 kg classe A", 760), ("table", "Table à manger 6 places extensible", 820), ("canape", "Canapé 3 places cuir", 1990),
]
BRANDS = ["Nordvik", "Aurel", "Kessler", "Solenne"]
MERCHANTS = ["electroplus", "maisonco", "rapido", "bigbox"]


def gtin(n):
    body = f"{300000000000 + n:012d}"
    total = sum(int(x) * (3 if i % 2 else 1) for i, x in enumerate(body))
    return body + str((10 - total % 10) % 10)


def retail_events(year):
    """Calendrier commercial français : Black Friday, soldes d'hiver et d'été."""
    nov1 = date(year, 11, 1)
    bf = nov1 + timedelta(days=(4 - nov1.weekday()) % 7 + 21)
    jan1 = date(year, 1, 1)
    winter = jan1 + timedelta(days=(2 - jan1.weekday()) % 7 + 7)
    jun30 = date(year, 6, 30)
    summer = jun30 - timedelta(days=(jun30.weekday() - 2) % 7)
    return {"black_friday": (bf - timedelta(days=7), bf + timedelta(days=3)),
            "soldes_hiver": (winter, winter + timedelta(days=27)),
            "soldes_ete": (summer, summer + timedelta(days=27))}


class Market:
    def __init__(self, start=date(2026, 1, 5), days=200, seed=4, catalog=CATALOG):
        self.start, self.days = start, days
        rng = random.Random(seed)
        self.products, self.offers = [], []
        for i, (slug, label, base) in enumerate(catalog):
            brand = BRANDS[i % len(BRANDS)]
            cls = re.search(r"classe ([A-G])", label)
            self.products.append({"id": i, "category": slug, "brand": brand, "gtin": gtin(i), "base": base * rng.uniform(0.92, 1.08),
                                  "title": label.replace(" classe", f" {brand} classe") if cls else f"{label} {brand}",
                                  "energy": cls.group(1) if cls else None})
            for m in rng.sample(MERCHANTS, 3):
                self.offers.append({"pid": i, "merchant": m, "url": f"https://{m}.sim/p/{i}", "factor": rng.uniform(0.97, 1.06)})
        self._simulate(rng)

    def _simulate(self, rng):
        D = self.days
        for o in self.offers:
            p = self.products[o["pid"]]
            normal, noise = [], 1.0
            for k in range(D):
                if (self.start + timedelta(days=k)).weekday() == 0:
                    noise = rng.uniform(0.98, 1.025)
                normal.append(round(p["base"] * o["factor"] * (1 - 0.06 * k / 365) * noise))
            price, listp, stock, kind = normal[:], [None] * D, [True] * D, ["normal"] * D

            def paint(a, b, fn, label):
                for j in range(max(0, a), min(D, b)):
                    if kind[j] == "normal":
                        fn(j)
                        kind[j] = label
            for y in (self.start.year, self.start.year + 1):
                for name, (a, b) in retail_events(y).items():
                    prob, lo, hi = {"black_friday": (0.85, .12, .25), "soldes_hiver": (0.5, .08, .15), "soldes_ete": (0.4, .08, .15)}[name]
                    if rng.random() < prob:
                        dep = rng.uniform(lo, hi)

                        def f(j, dep=dep):
                            price[j] = round(normal[j] * (1 - dep))
                            listp[j] = normal[j]
                        paint((a - self.start).days, (b - self.start).days + 1, f, "true_promo")
            k = 0
            while k < D:
                r = rng.random()
                if r < 1 / 70:
                    n, dep, honest = rng.randint(5, 10), rng.uniform(.10, .20), rng.random() < 0.7

                    def f(j, dep=dep, honest=honest):
                        price[j] = round(normal[j] * (1 - dep))
                        listp[j] = normal[j] if honest else None
                    paint(k, k + n, f, "true_promo")
                    k += n
                elif r < 1 / 70 + 1 / 150:
                    def up(j):
                        price[j] = round(normal[j] * 1.30)

                    def fake(j):
                        price[j] = round(normal[j] * rng.uniform(0.98, 1.02))
                        listp[j] = round(normal[j] * 1.30)
                    paint(k, k + 14, up, "inflated")
                    paint(k + 14, k + 21, fake, "fake_promo")
                    k += 21
                elif r < 1 / 70 + 1 / 150 + 1 / 200:
                    def hike(j):
                        price[j] = round(normal[j] * 1.12)
                    paint(k, k + 10, hike, "hike")
                    k += 10
                elif r < 1 / 70 + 1 / 150 + 1 / 200 + 1 / 100:
                    n = rng.randint(3, 8)
                    for j in range(k, min(D, k + n)):
                        stock[j] = False
                    k += n
                else:
                    k += 1
            o.update(normal=normal, price=price, list=listp, stock=stock, kind=kind)

    def truth(self, pid, k):
        """Vérité du jour k pour un produit : opportunité réelle ?"""
        offs = [o for o in self.offers if o["pid"] == pid]
        live = [o for o in offs if o["stock"][k]]
        if not live:
            return {"opp": False, "best": None}
        best = min(o["price"][k] for o in live)
        return {"opp": best <= min(o["normal"][k] for o in offs) * 0.92, "best": best}

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
    """Horloge réglable (10 h UTC du jour courant)."""

    def __init__(self, d):
        self.set(d)

    def set(self, d):
        self.t = datetime(d.year, d.month, d.day, 10, tzinfo=timezone.utc).timestamp()

    def __call__(self):
        return self.t


class SimFetcher:
    """Remplace fetch.Fetcher : sert la page simulée du jour de l'horloge."""
    ua = "sim"

    def __init__(self, market, clock):
        self.m, self.clock = market, clock

    def get(self, url, etag=None, last_modified=None):
        k = (datetime.fromtimestamp(self.clock(), timezone.utc).date() - self.m.start).days
        return {"status": "ok", "code": 200, "html": self.m.html(url, k), "final_url": url, "elapsed_ms": 0}

    def delay_for(self, host):
        return 0.0
