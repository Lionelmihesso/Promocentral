"""Marché simulé à VÉRITÉ CONNUE : démo de l'app (SHOWCASE) et mesure des règles (bench/deals_truth.py, CATALOG).

Chaque offre suit un prix « normal » (érosion, bruit hebdomadaire, écart propre à l'enseigne) et subit des épisodes :
  vraie promo de l'enseigne  ~1 fois / 70 j, 5-10 j, -10 à -20 % (prix barré honnête 70 % du temps)
  Black Friday               85 % des offres, -12 à -25 % ; soldes d'hiver / d'été : 50 % / 40 % des offres, -8 à -15 %
  FAUSSE promo               ~1 fois / 150 j : prix gonflé de 30 % pendant 14 j, puis « -23 % » affiché pendant 7 j au
                             prix normal
  hausse temporaire          ~1 fois / 200 j : +12 % pendant 10 j ;   rupture : ~1 fois / 100 j, 3 à 8 j
Vérité par produit et par jour : OPPORTUNITÉ = meilleur prix en stock ≤ 92 % du meilleur prix normal du marché.
Deux offres sur trois déclarent la fin de leur promotion (priceValidUntil), comme beaucoup d'enseignes. Marques et
enseignes sont fictives.
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

# Démo : titres et prix proches de ceux des enseignes, marques fictives — (catégorie, titre, prix de base, marque)
SHOWCASE = [
    ("lave_linge", "Lave-linge hublot {brand} WM8 8 kg 1400 tr/min classe A", 549, "Kessler"),
    ("lave_linge", "Lave-linge hublot {brand} Série 6 9 kg classe A", 689, "Brava"),
    ("lave_linge", "Lave-linge top {brand} T65 6,5 kg classe C", 449, "Helio"),
    ("lave_linge", "Lave-linge hublot {brand} Silence 10 kg classe A", 799, "Ostra"),
    ("seche_linge", "Sèche-linge pompe à chaleur {brand} DH8 8 kg classe A++", 699, "Kessler"),
    ("seche_linge", "Sèche-linge pompe à chaleur {brand} DH9 9 kg classe A+++", 849, "Brava"),
    ("lave_vaisselle", "Lave-vaisselle {brand} 60 cm 13 couverts 44 dB classe C", 529, "Helio"),
    ("lave_vaisselle", "Lave-vaisselle encastrable {brand} 60 cm 14 couverts classe B", 749, "Ostra"),
    ("lave_vaisselle", "Lave-vaisselle {brand} 45 cm 10 couverts classe D", 449, "Kessler"),
    ("refrigerateur", "Réfrigérateur combiné {brand} 60 cm No Frost 331 L classe C", 699, "Brava"),
    ("refrigerateur", "Réfrigérateur américain {brand} 91 cm 635 L classe E", 1499, "Helio"),
    ("refrigerateur", "Réfrigérateur multi-portes {brand} 70 cm 450 L classe D", 1199, "Ostra"),
    ("congelateur", "Congélateur armoire {brand} No Frost 242 L classe E", 649, "Kessler"),
    ("four", "Four encastrable pyrolyse {brand} 71 L classe A+", 599, "Brava"),
    ("four", "Four vapeur combiné {brand} 70 L classe A", 899, "Helio"),
    ("plaque_cuisson", "Plaque induction {brand} 4 foyers 60 cm", 449, "Ostra"),
    ("plaque_cuisson", "Plaque induction {brand} 3 foyers flex 60 cm", 549, "Kessler"),
    ("hotte", "Hotte décorative murale {brand} 90 cm 700 m³/h", 499, "Brava"),
    ("canape", "Canapé d'angle convertible {brand} Oslo 5 places tissu", 1290, "Nordvik"),
    ("canape", "Canapé 3 places {brand} Lina velours côtelé", 899, "Varenne"),
    ("canape", "Canapé 2 places {brand} Milo cuir pleine fleur", 1490, "Aurel"),
    ("canape", "Canapé convertible {brand} Bergen couchage 140x190", 749, "Lumen"),
    ("canape", "Canapé d'angle {brand} Ravel méridienne réversible", 1690, "Varenne"),
    ("fauteuil", "Fauteuil relax {brand} Nils électrique cuir", 899, "Aurel"),
    ("fauteuil", "Fauteuil {brand} Louise bouclette", 399, "Varenne"),
    ("fauteuil", "Fauteuil {brand} Oscar velours pieds laiton", 349, "Lumen"),
    ("lit", "Lit coffre {brand} Aria 160x200 avec tête de lit", 699, "Nordvik"),
    ("lit", "Lit adulte {brand} Kara 140x190 chêne massif", 549, "Lumen"),
    ("lit", "Lit adulte {brand} Tilda 180x200 tête capitonnée", 899, "Nordvik"),
    ("armoire", "Armoire {brand} Lund 3 portes 150 cm", 649, "Nordvik"),
    ("armoire", "Dressing {brand} Modulo 200 cm portes coulissantes", 899, "Lumen"),
    ("table", "Table à manger extensible {brand} Viggo 6 à 10 places chêne", 899, "Varenne"),
    ("table", "Table à manger {brand} Roma céramique 8 places", 1190, "Aurel"),
    ("table", "Table à manger {brand} Nora ronde 4 places", 499, "Nordvik"),
    ("buffet", "Buffet {brand} Siena 3 portes 180 cm noyer", 749, "Varenne"),
    ("meuble_tv", "Meuble TV {brand} Halden 200 cm chêne clair", 449, "Nordvik"),
    ("commode", "Commode {brand} Ella 6 tiroirs", 399, "Lumen"),
    ("matelas", "Matelas {brand} Hybrid 160x200 ressorts ensachés", 899, "Dormea"),
    ("matelas", "Matelas {brand} Mémoire 140x190 mousse à mémoire de forme", 599, "Solenne"),
    ("matelas", "Matelas {brand} Confort+ 180x200 ressorts ensachés", 1190, "Dormea"),
    ("matelas", "Matelas {brand} Latex 160x200 latex naturel", 1290, "Solenne"),
    ("matelas", "Matelas {brand} Essentiel 90x190 mousse", 299, "Dormea"),
    ("matelas", "Matelas {brand} Ressorts 140x190 ferme", 449, "Solenne"),
    ("matelas", "Matelas {brand} Air 160x200 mousse respirante", 749, "Dormea"),
    ("matelas", "Matelas {brand} Enfant 90x190 mousse", 199, "Solenne"),
    ("sommier", "Sommier tapissier {brand} 160x200 lattes", 399, "Dormea"),
    ("sommier", "Sommier électrique {brand} relaxation 2x80x200", 1190, "Solenne"),
    ("sommier", "Sommier {brand} à lattes 140x190 pieds inclus", 249, "Dormea"),
]
SHOWCASE_MERCHANTS = ["Électro Plus", "Maison & Co", "Rapido", "Grand Bazar"]


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


def slug(name):
    return re.sub(r"[^a-z0-9]", "", name.lower().replace("é", "e").replace("&", ""))


class Market:
    def __init__(self, start=date(2026, 1, 5), days=200, seed=4, catalog=CATALOG, merchants=MERCHANTS):
        self.start, self.days = start, days
        rng = random.Random(seed)
        self.products, self.offers = [], []
        for i, (slug_, label, base, *named) in enumerate(catalog):
            brand = named[0] if named else BRANDS[i % len(BRANDS)]
            cls = re.search(r"classe ([A-G])", label)
            title = label.format(brand=brand) if "{brand}" in label else \
                label.replace(" classe", f" {brand} classe") if cls else f"{label} {brand}"
            self.products.append({"id": i, "category": slug_, "brand": brand, "gtin": gtin(i), "base": base * rng.uniform(0.92, 1.08),
                                  "title": title, "energy": cls.group(1) if cls else None})
            for m in rng.sample(merchants, 3):
                self.offers.append({"pid": i, "merchant": m, "url": f"https://{slug(m)}.sim/p/{i}", "factor": rng.uniform(0.97, 1.06)})
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
            price, listp, stock, kind, until = normal[:], [None] * D, [True] * D, ["normal"] * D, [None] * D

            def paint(a, b, fn, label):
                for j in range(max(0, a), min(D, b)):
                    if kind[j] == "normal":
                        fn(j)
                        kind[j] = label
                        until[j] = b - 1 if label in ("true_promo", "fake_promo") else None
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
            o.update(normal=normal, price=price, list=listp, stock=stock, kind=kind, until=until,
                     declares=int(o["factor"] * 1000) % 3 != 0)      # deux offres sur trois annoncent la fin (sans tirage)

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
        if o["list"][k] and o["declares"] and o["until"][k] is not None:
            offer["priceValidUntil"] = (self.start + timedelta(days=o["until"][k])).isoformat()
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
