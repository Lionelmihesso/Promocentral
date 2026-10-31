"""Alternatives moins chères, mesurées contre une grille indépendante du code de DEALS.

La grille dit ce qu'un acheteur attend d'un remplaçant ; elle a été écrite avant le moteur (deals/alternatives.py) et
ne partage rien avec lui : ni l'extraction des attributs (ici, des expressions régulières sur le titre), ni les règles.
Même catégorie ; même usage (même taille de literie ; largeur à 6 % près en électroménager, à 20 % en ameublement ;
places à une près ; au moins les fonctions sans fil, balai, traîneau, convertible, d'angle, induction, encastrable,
américain, électrique du produit regardé) ; pas moins bien (classe énergie au plus une lettre en dessous ; capacité,
couverts, foyers au plus un de moins ; volume au plus 15 % de moins ; bruit au plus 3 dB de plus). Moins chère : au moins
10 % sous le prix, disponible.

v59, ce que la grille ajoute (toujours lu dans le seul titre, par ses propres expressions) : le même type quand le titre
le dit, ni un autre ni un type non dit (TYPES : un matelas latex n'est pas remplacé par un matelas à ressorts, un
canapé convertible par un canapé d'angle) ; la même forme (sans sac ou avec sac, portes coulissantes ou battantes) ;
tiroirs au plus un de moins ; l'électronique : la même taille d'écran à 5 % près (pouces, ou centimètres d'un
téléviseur ; celle d'un téléviseur, d'un écran PC, d'un ordinateur portable ou d'une tablette — un smartphone la dit
rarement : elle n'est pas comparée), stockage, mémoire vive et fréquence au moins autant, au moins 5G, 4K, réduction de bruit, GPS, réseau
mobile, étanche, Dolby Atmos s'il les a ; une console en édition numérique ne remplace qu'une console en édition
numérique, et une console, seulement une console de la même marque (ses jeux).

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
# v59 : les fonctions de l'électronique, rayon par rayon (« 4G » d'une montre est son réseau mobile ; d'un smartphone, non)
CAT_FLAGS = {"televiseur": {"uhd": r"\b(?:4k|8k|uhd)\b"}, "smartphone": {"5g": r"\b5g\b"},
             "casque_audio": {"sans_fil": r"\bsans fil\b|bluetooth|true wireless", "anc": r"reduction (?:active )?de bruit|\banc\b"},
             "montre_connectee": {"gps": r"\bgps\b", "cellular": r"\b4g\b|\besim\b|cellular"},
             "enceinte": {"waterproof": r"\betanche\b|\bip6[78]\b|\bipx[4-8]\b", "atmos": r"dolby atmos"}}
# Le type dit par le titre, rayon par rayon (le premier de la liste qui y est) : un remplaçant a le même.
TYPES = {
    "lave_linge": [("top", r"\btop\b|par le dessus"), ("hublot", r"hublot|frontal")],
    "seche_linge": [("pac", r"pompe a chaleur"), ("condensation", r"condensation"), ("evacuation", r"evacuation")],
    "lave_vaisselle": [("encastrable", r"encastrable"), ("compact", r"\bcompact"), ("pose libre", r"pose libre")],
    "refrigerateur": [("americain", r"americain"), ("multi", r"multi.?portes"), ("combine", r"combine"),
                      ("2 portes", r"\b(?:2|deux) portes|double porte"), ("1 porte", r"\b(?:1|une) porte|table top")],
    "congelateur": [("armoire", r"armoire"), ("coffre", r"coffre"), ("table top", r"table top")],
    "four": [("encastrable", r"encastrable"), ("pose libre", r"pose libre|posable")],
    "plaque_cuisson": [("mixte", r"mixte|gaz et induction|induction et gaz"), ("induction", r"induction"),
                       ("vitro", r"vitroceramique|radiant"), ("gaz", r"\bgaz\b")],
    "hotte": [("ilot", r"\bilot\b"), ("plan", r"plan de travail"), ("plafond", r"plafond"), ("tiroir", r"tiroir"),
              ("casquette", r"casquette"), ("murale", r"murale|decorative")],
    "aspirateur": [("laveur", r"laveur|nettoyeur"), ("main", r"\ba main\b"), ("balai", r"\bbalai\b"), ("traineau", r"traineau")],
    "canape": [("angle", r"d'?angle"), ("modulable", r"modulable"), ("droit", r"\bdroit\b")],
    "fauteuil": [("relax", r"relax"), ("club", r"\bclub\b"), ("bascule", r"bascule"), ("bureau", r"bureau")],
    "lit": [("coffre", r"coffre"), ("mezzanine", r"mezzanine"), ("superpose", r"superpose"), ("gigogne", r"gigogne"),
            ("enfant", r"enfant")],
    "armoire": [("dressing", r"dressing"), ("penderie", r"penderie")],
    "table": [("ronde", r"\bronde\b"), ("carree", r"\bcarree\b"), ("rectangulaire", r"rectangulaire"), ("ovale", r"ovale")],
    "commode": [("chiffonnier", r"chiffonnier"), ("semainier", r"semainier"), ("langer", r"a langer")],
    "matelas": [("hybride", r"hybrid"), ("ressorts", r"ressorts"), ("memoire", r"memoire de forme"), ("latex", r"latex"),
                ("mousse", r"mousse")],
    "sommier": [("electrique", r"electrique"), ("coffre", r"coffre"), ("tapissier", r"tapissier"), ("lattes", r"lattes")],
    "televiseur": [("oled", r"\boled\b"), ("mini led", r"mini ?led"), ("qled", r"qled"), ("led", r"\bled\b")],
    "smartphone": [("pliable", r"pliable|fold|flip")],
    "ordinateur_portable": [("gamer", r"gam(?:er|ing)"), ("2 en 1", r"2 en 1|convertible"), ("chromebook", r"chromebook"),
                            ("ultraportable", r"ultraportable|ultrabook")],
    "tablette": [("enfant", r"enfant|kids")],
    "casque_audio": [("ecouteurs", r"ecouteurs|intra|earbuds"), ("casque", r"casque")],
    "enceinte": [("barre", r"barre de son|soundbar"), ("connectee", r"connectee|wi.?fi"), ("portable", r"portable|nomade")],
    "montre_connectee": [("bracelet", r"bracelet"), ("sport", r"sport|gps")],
    "console": [("portable", r"portable|hybride"), ("salon", r"salon")],
    "ecran_pc": [("gaming", r"gaming|gamer"), ("incurve", r"incurve")],
}
LESS = {"digital": r"digital|edition numerique"}
SCREENS = {"televiseur", "ecran_pc", "ordinateur_portable", "tablette"}      # oui est un moins : seulement à la place d'un produit qui l'est aussi


def plain(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


@lru_cache(maxsize=None)
def spec(title, category=None):
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
    out["flags"] = {f for f, rx in {**FLAGS, **CAT_FLAGS.get(category, {})}.items() if re.search(rx, t)}
    out["less"] = {f for f, rx in LESS.items() if re.search(rx, t)}
    out["bag"] = "sans" if "sans sac" in t else "avec" if re.search(r"\b(?:avec|a) sac\b", t) else None
    out["doors"] = "coulissantes" if "coulissant" in t else "battantes" if "battant" in t else None
    m = re.search(r"\b(\d{1,2})\s*tiroirs\b", t)
    if m:
        out["drawers"] = int(m.group(1))
    m = re.search(r"\b(\d{1,2}(?:[.,]\d)?)\s*(?:pouces|\"|''|″)", t)
    if m:
        out["screen"] = float(m.group(1).replace(",", "."))
    if category == "televiseur":
        cm = out.pop("width_cm", None)                     # les centimètres d'un téléviseur : sa diagonale
        if cm and "screen" not in out:
            out["screen"] = round(cm / 2.54)
    sizes = [(float(v.replace(",", ".")) * (1000 if u in ("to", "tb") else 1), k.start()) for k in
             re.finditer(r"\b(\d{1,4}(?:[.,]\d)?)\s*(go|gb|to|tb)\b(?!\s*(?:de\s*)?ram)", t) for v, u in [k.groups()]]
    if sizes:
        out["storage"] = max(v for v, _ in sizes)
    m = re.search(r"\b(\d{1,2})\s*go\s*(?:de\s*)?ram\b", t)
    if m:
        out["ram"] = int(m.group(1))
    m = re.search(r"\b(\d{2,3})\s*hz\b", t)
    if m:
        out["hz"] = int(m.group(1))
    return out


def kind(category, title):
    """Le type que le titre dit (TYPES), None s'il n'en dit pas."""
    t = plain(title).replace("-", " ")
    return next((k for k, rx in TYPES.get(category, ()) if re.search(rx, t)), None)


def replaces(a, b):
    """Selon la grille : b remplace-t-il a ?"""
    if a["category"] != b["category"] or a["category"] == "console" and a["brand"] != b["brand"]:
        return False
    A, B = spec(a["title"], a["category"]), spec(b["title"], b["category"])
    if "bed_size" in A and A["bed_size"] != B.get("bed_size"):
        return False
    if "width_cm" in A:
        tol = 0.20 if a["category"] in FURNITURE else 0.06
        if "width_cm" not in B or abs(B["width_cm"] - A["width_cm"]) > tol * A["width_cm"]:
            return False
    if "seats" in A and ("seats" not in B or abs(B["seats"] - A["seats"]) > 1):
        return False
    if not A["flags"] <= B["flags"] or not B["less"] <= A["less"]:
        return False
    if kind(a["category"], a["title"]) != kind(b["category"], b["title"]):
        return False
    for k in ("bag", "doors"):
        if A[k] and B[k] != A[k]:
            return False
    if "screen" in A and a["category"] in SCREENS and ("screen" not in B or abs(B["screen"] - A["screen"]) > 0.05 * A["screen"]):
        return False
    if any(k in A and k in B and B[k] < A[k] for k in ("storage", "ram", "hz")):
        return False
    if "drawers" in A and "drawers" in B and B["drawers"] < A["drawers"] - 1:
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
        "SELECT c.product_id, c.title, c.category, c.brand, c.price, o.availability FROM catalog c "
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
