"""Alternatives moins chères, mesurées contre une grille indépendante du code de DEALS.

La grille dit ce qu'un acheteur attend d'un remplaçant ; elle a été écrite avant le moteur (deals/alternatives.py) et
ne partage rien avec lui : ni l'extraction des attributs (ici, des expressions régulières sur le titre), ni les règles.
Même catégorie ; même usage (même taille de literie ; largeur à 6 % près en électroménager, à 20 % en ameublement ;
places à une près ; au moins les fonctions sans fil, balai, traîneau, convertible, d'angle, induction, encastrable,
américain, électrique du produit regardé) ; pas moins bien (classe énergie au plus une lettre en dessous ; capacité,
couverts, foyers au plus un de moins ; volume au plus 15 % de moins ; bruit au plus 3 dB de plus). Moins chère : au moins
10 % sous le prix, disponible.

Pour chaque fiche, ce que montre l'app (« Moins cher, comparable », sinon « Produits similaires ») est jugé par la
grille : suggestions incompatibles ; fiches pour lesquelles une alternative moins chère existe et part de ces fiches qui
en montrent une ; économie moyenne possible (la meilleure) et montrée. Sur la démo (59 produits, vraie chaîne) et sur
le catalogue synthétique de bench.scale (3 000 produits).

  python -m bench.alternatives
"""
import re
import statistics
import tempfile
import unicodedata
from functools import lru_cache
from pathlib import Path

from deals import demo
from deals.publish import publish
from deals.store import Store

from .scale import NOW, generate

NUM = {"width_cm": r"\b(\d{2,3})\s*cm\b", "capacity_kg": r"\b(\d{1,2}(?:[.,]\d)?)\s*kg\b", "place_settings": r"\b(\d{1,2})\s*couverts\b",
       "noise_db": r"\b(\d{2})\s*db\b", "seats": r"\b(\d{1,2})\s*places\b", "volume_l": r"\b(\d{2,3})\s*l\b", "zones": r"\b(\d)\s*foyers?\b"}
FLAGS = {"sans_fil": r"\bsans fil\b", "balai": r"\bbalai\b", "traineau": r"\btraineau\b", "convertible": r"\bconvertible\b",
         "angle": r"\bd'?angle\b", "induction": r"\binduction\b", "encastrable": r"\bencastrable\b", "americain": r"\bamericain\b",
         "electrique": r"\belectrique\b"}
FURNITURE = {"canape", "fauteuil", "lit", "armoire", "table", "buffet", "meuble_tv", "commode"}


def plain(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


@lru_cache(maxsize=None)
def spec(title):
    t, out = plain(title), {}
    for k, rx in NUM.items():
        m = re.search(rx, t)
        if m:
            out[k] = float(m.group(1).replace(",", "."))
    m = re.search(r"\b(\d{2,3})\s*x\s*(\d{3})\b", t)
    if m:
        out["bed_size"] = f"{m.group(1)}x{m.group(2)}"
    m = re.search(r"classe(?: energetique| energie)?\s*:?\s*([a-g])\b", t)
    if m:
        out["energy"] = "abcdefg".index(m.group(1))
    out["flags"] = {f for f, rx in FLAGS.items() if re.search(rx, t)}
    return out


def replaces(a, b):
    """Selon la grille : b remplace-t-il a ?"""
    if a["category"] != b["category"]:
        return False
    A, B = spec(a["title"]), spec(b["title"])
    if "bed_size" in A and A["bed_size"] != B.get("bed_size"):
        return False
    if "width_cm" in A:
        tol = 0.20 if a["category"] in FURNITURE else 0.06
        if "width_cm" not in B or abs(B["width_cm"] - A["width_cm"]) > tol * A["width_cm"]:
            return False
    if "seats" in A and ("seats" not in B or abs(B["seats"] - A["seats"]) > 1):
        return False
    if not A["flags"] <= B["flags"]:
        return False
    for k, d in (("capacity_kg", 1), ("place_settings", 1), ("zones", 1)):
        if k in A and k in B and B[k] < A[k] - d:
            return False
    if "volume_l" in A and "volume_l" in B and B["volume_l"] < 0.85 * A["volume_l"]:
        return False
    if "noise_db" in A and "noise_db" in B and B["noise_db"] > A["noise_db"] + 3:
        return False
    if "energy" in A and "energy" in B and B["energy"] > A["energy"] + 1:
        return False
    return True


def measure(store):
    cat = {r["product_id"]: dict(r) for r in store.q(
        "SELECT c.product_id, c.title, c.category, c.price, o.availability FROM catalog c "
        "JOIN catalog_offers o ON o.product_id=c.product_id AND o.rank=0")}
    shown = {}
    for table in ("alternatives", "similar"):                 # la fiche montre les alternatives, sinon les similaires
        rows = {}
        for r in store.q(f"SELECT product_id, other_id FROM {table} ORDER BY product_id, rank"):
            rows.setdefault(r["product_id"], []).append(r["other_id"])
        for pid, others in rows.items():
            shown.setdefault(pid, others)
    n = bad = empty = opp = covered = 0
    possible, got = [], []
    for pid, p in cat.items():
        s = [cat[o] for o in shown.get(pid, []) if o in cat]
        n += len(s)
        bad += sum(not replaces(p, o) for o in s)
        empty += not s
        cheaper = lambda xs: [p["price"] - o["price"] for o in xs if o["product_id"] != pid and o["availability"] != "out_of_stock"
                              and o["price"] <= 0.9 * p["price"] and replaces(p, o)]
        best = cheaper(cat.values())
        if best:
            opp += 1
            possible.append(max(best))
            mine = cheaper(s)
            got.append(max(mine, default=0))
            covered += bool(mine)
    return {"fiches": len(cat), "suggestions": n, "incompatibles": bad, "sans suggestion": empty, "moins cher possible": opp,
            "montré": covered, "économie possible": statistics.mean(possible) if possible else 0,
            "économie montrée": statistics.mean(got) if got else 0}


def main():
    tmp = tempfile.mkdtemp()
    demo_store = Store(Path(tmp, "demo.sqlite"))
    demo.build(demo_store)
    scale_store = Store(Path(tmp, "scale.sqlite"))
    generate(scale_store)
    publish(scale_store, NOW.date(), NOW.timestamp())
    for name, store in (("démo (vraie chaîne)", demo_store), ("catalogue synthétique", scale_store)):
        m = measure(store)
        print(f"{name} : {m['fiches']} fiches, {m['suggestions']} suggestions, {m['incompatibles']} incompatibles "
              f"({m['incompatibles'] / max(1, m['suggestions']):.0%}), {m['sans suggestion']} fiches sans suggestion")
        print(f"  alternative moins chère possible pour {m['moins cher possible']} fiches ; montrée pour {m['montré']} "
              f"({m['montré'] / max(1, m['moins cher possible']):.0%}) ; économie moyenne possible {m['économie possible']:.0f} €, "
              f"montrée {m['économie montrée']:.0f} €")


if __name__ == "__main__":
    main()
