"""Un besoin → une sélection : la Recherche comprend-elle un besoin dit comme on le dit — « aspirateur pour un
appartement avec parquet et un chat, 300 € max » — et la sélection y répond-elle ?

Catalogue d'aspirateurs à VÉRITÉ CONNUE (160 produits, marques fictives) : chaque produit a ses vraies caractéristiques
(sous-famille, poids, autonomie, filtre HEPA, brosse pour les poils, bruit, sac, station de vidage, lavage…). Sa page
n'en dit qu'une partie, comme en vrai : le titre, et une fiche plus ou moins complète, aux noms et aux formats variés
(« Poids net : 2.6 », « Autonomie maximale : jusqu'à 60 minutes », « Filtration : HEPA H13 ») ; une page sur sept n'a
que le titre. Le code mesuré ne voit que la page : il lit les produits comme la collecte (market.match_product), publie
(publish), puis on lui pose chaque phrase (l'API, la première réponse, rien d'autre de touché).

La vérité est écrite à la main, AVANT le moteur de la v57, sur les vraies caractéristiques, d'après ce que disent les
guides d'achat : un chat ou un chien → une brosse faite pour les poils ; des allergies → un filtre HEPA ; silencieux →
70 dB au plus ; les escaliers, la voiture, les miettes → un aspirateur à main ou un balai qui en devient un ; laver le
sol → un laveur ou un robot laveur ; une grande maison → de quoi la couvrir d'une traite. Pour chaque phrase : ce qui
est exclu (budget, type nommé, usage impossible) et ce qui est bon.

Mesures
  besoins    bons parmi les 6 premières cartes (un écran de téléphone ; sur le nombre de bons s'il y en a moins de 6),
             exclus parmi elles, impasses (rien alors que des bons existent), rappel des bons dans la réponse (60 cartes),
             nDCG@6 (bon 2, admissible 1, exclu 0) ; besoins dits à la personne ; explications vérifiées sur la vérité
  vagues     une question est-elle proposée sans bloquer (des produits sont montrés), et utile (au moins deux réponses,
             chacune donne une autre sélection) ?
  précises   aucune question ; la référence exacte en premier ; aucune carte exclue ; rappel des admissibles
  conflits   un besoin impossible pour le type demandé (« robot aspirateur pour les escaliers ») : un autre type
             est-il proposé, avec sa raison ?
  lecture    ce que la page dit d'un produit : lu juste, lu faux, pas lu ; les faits faux (« 2,6 kg » lu comme une
             capacité de lave-linge)

  python -m bench.needs [--code <dossier du code>] [--json sortie.json] [-v]
"""
import argparse
import json
import math
import random
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--code", help="dossier d'un autre code à mesurer (le code d'avant)")
ap.add_argument("--json")
ap.add_argument("-v", action="store_true", help="le détail de chaque phrase")
ARGS = ap.parse_args() if __name__ == "__main__" else ap.parse_args([])
if ARGS.code:
    sys.path.insert(0, ARGS.code)

from deals import config  # noqa: E402
from deals.api import Api, Request  # noqa: E402
from deals.market import Market  # noqa: E402
from deals.publish import publish  # noqa: E402
from deals.sim import gtin  # noqa: E402
from deals.store import Store  # noqa: E402

NOW = datetime(2026, 10, 18, 20, tzinfo=timezone.utc)
TOP, SHOWN = 6, 60
BRANDS = ["Zephyr", "Brava", "Kessler", "Helio", "Ostra", "Vela", "Corvo", "Ondine", "Nimbo", "Maelis"]
COUNTS = {"balai": 60, "traineau": 35, "robot": 40, "laveur": 12, "main": 13}
MERCHANTS = ["Électro Plus", "Maison & Co", "Rapido", "Grand Bazar"]
SUBS = set(COUNTS)


# ------------------------------------------------------------------ le catalogue à vérité connue
def retail(x):
    """Un prix d'enseigne : 249, 299, 1 199…"""
    return max(29, int(round(x / 10.0)) * 10 - 1)


def truth_of(rng, sub):
    """Les vraies caractéristiques d'un aspirateur de la sous-famille sub."""
    p = {"sub": sub, "cordless": False, "weight_kg": None, "autonomy_min": None, "noise_db": None, "hepa": False, "bagless": True,
         "motor_brush": False, "pet_tool": False, "soft_roller": False, "handheld": False, "removable_battery": False,
         "dust_l": None, "reach_m": None, "power_w": None, "navigation": None, "mapping": False, "auto_empty": False, "mop": False,
         "suction_pa": None, "suction_aw": None, "climb_mm": None, "self_clean": False}
    r = rng.random
    if sub == "balai":
        p["cordless"] = r() < 0.9
        p["weight_kg"] = round(rng.uniform(1.8, 3.6), 1)
        p["autonomy_min"] = rng.choice([25, 30, 35, 40, 45, 50, 60, 60, 70, 80, 90]) if p["cordless"] else None
        p["hepa"], p["motor_brush"] = r() < 0.45, r() < 0.75
        p["pet_tool"] = p["motor_brush"] and r() < 0.45
        p["soft_roller"], p["handheld"] = r() < 0.3, r() < 0.6
        p["removable_battery"] = p["cordless"] and r() < 0.4
        p["noise_db"], p["dust_l"], p["suction_aw"] = rng.randint(70, 84), round(rng.uniform(0.3, 0.9), 1), rng.randint(80, 240)
        price = (110 + 4 * ((p["autonomy_min"] or 45) - 25) + 90 * p["hepa"] + 60 * p["motor_brush"] + 50 * p["pet_tool"]
                 + 40 * p["soft_roller"] + 30 * p["removable_battery"] + 0.8 * (p["suction_aw"] - 80) - 40 * (p["weight_kg"] - 2.5))
    elif sub == "traineau":
        p["cordless"] = r() < 0.05
        p["bagless"] = r() < 0.65
        p["weight_kg"], p["noise_db"] = round(rng.uniform(4.5, 8.5), 1), rng.randint(58, 80)
        p["hepa"], p["motor_brush"] = r() < 0.55, r() < 0.3
        p["pet_tool"] = r() < 0.25
        p["soft_roller"] = r() < 0.5
        p["reach_m"] = None if p["cordless"] else rng.choice([7, 8, 9, 10, 11, 12])
        p["autonomy_min"] = rng.choice([40, 50, 60]) if p["cordless"] else None
        p["power_w"] = None if p["cordless"] else rng.choice([450, 550, 650, 700, 750, 800, 850, 900])
        p["dust_l"] = round(rng.uniform(1.5, 4.5), 1)
        price = (90 + 60 * p["hepa"] + 30 * p["bagless"] + 40 * p["motor_brush"] + 30 * p["pet_tool"] + 4 * (80 - p["noise_db"])
                 + 0.1 * ((p["power_w"] or 700) - 450) + 120 * p["cordless"])
    elif sub == "robot":
        p["cordless"] = True
        p["navigation"] = rng.choices(["aleatoire", "gyroscope", "laser", "camera"], [15, 25, 45, 15])[0]
        p["mapping"] = p["navigation"] in ("laser", "camera")
        p["auto_empty"], p["mop"] = r() < 0.35, r() < 0.55
        p["autonomy_min"], p["noise_db"] = rng.choice([90, 100, 120, 150, 180, 200, 240]), rng.randint(55, 70)
        p["pet_tool"], p["hepa"] = r() < 0.3, r() < 0.4
        p["suction_pa"], p["climb_mm"] = rng.choice([1500, 2000, 2700, 3000, 4000, 5000, 6000, 8000]), rng.choice([15, 18, 20, 22])
        p["weight_kg"], p["dust_l"] = round(rng.uniform(3.0, 4.2), 1), round(rng.uniform(0.3, 0.6), 1)
        price = (160 + {"aleatoire": 0, "gyroscope": 50, "laser": 150, "camera": 200}[p["navigation"]] + 200 * p["auto_empty"]
                 + 120 * p["mop"] + 0.03 * p["suction_pa"] + 40 * p["pet_tool"] + 0.5 * (p["autonomy_min"] - 90))
    elif sub == "laveur":
        p["cordless"], p["mop"] = r() < 0.85, True
        p["weight_kg"], p["noise_db"] = round(rng.uniform(3.5, 5.5), 1), rng.randint(75, 82)
        p["autonomy_min"] = rng.choice([25, 30, 35, 40, 45]) if p["cordless"] else None
        p["self_clean"], p["hepa"], p["pet_tool"] = r() < 0.6, r() < 0.2, r() < 0.1
        p["dust_l"] = round(rng.uniform(0.5, 0.9), 1)
        price = 220 + 120 * p["self_clean"] + 3 * ((p["autonomy_min"] or 30) - 25) + 40 * p["hepa"]
    else:  # main
        p["cordless"] = True
        p["weight_kg"], p["noise_db"] = round(rng.uniform(0.6, 1.6), 1), rng.randint(70, 80)
        p["autonomy_min"] = rng.choice([10, 12, 15, 20, 25, 30])
        p["pet_tool"], p["hepa"], p["motor_brush"] = r() < 0.3, r() < 0.3, r() < 0.3
        p["suction_aw"], p["dust_l"] = rng.randint(15, 60), round(rng.uniform(0.2, 0.5), 1)
        price = 35 + 30 * p["pet_tool"] + 2.5 * p["autonomy_min"] + 20 * p["hepa"] + 0.5 * p["suction_aw"]
    p["price"] = retail(price * rng.uniform(0.92, 1.12))
    return p


def num(v, d=1):
    return f"{v:.{d}f}".rstrip("0").rstrip(".").replace(".", ",")


def page_of(rng, p, brand, model):
    """La page de l'enseigne : un titre et une fiche plus ou moins complète. → (titre, propriétés déclarées, catégorie
    déclarée, ce que la page dit : {caractéristique})"""
    r, sub, said = rng.random, p["sub"], set()
    if sub == "balai":
        head = "Aspirateur balai 2 en 1" if p["handheld"] and r() < 0.3 else "Aspirateur balai"
        said |= {"handheld"} if "2 en 1" in head else set()
        if p["cordless"] and r() < 0.8:
            head, _ = head + " sans fil", said.add("cordless")
        elif not p["cordless"] and r() < 0.6:
            head, _ = head + " filaire", said.add("cordless")
    elif sub == "traineau":
        head = "Aspirateur traîneau"
        if r() < 0.7:
            head, _ = head + (" sans sac" if p["bagless"] else " avec sac"), said.add("bagless")
        if p["cordless"]:
            head, _ = head + " sans fil", said.add("cordless")
    elif sub == "robot":
        head = "Robot aspirateur laveur" if p["mop"] and r() < 0.8 else "Robot aspirateur"
        said |= {"mop"} if "laveur" in head else set()
    elif sub == "laveur":
        head = "Nettoyeur de sols" if r() < 0.25 else "Aspirateur laveur"
        said.add("mop")
        if p["cordless"] and r() < 0.7:
            head, _ = head + " sans fil", said.add("cordless")
    else:
        head = "Aspirateur à main"
        if r() < 0.6:
            head, _ = head + " sans fil", said.add("cordless")
    tail = []
    if p["pet_tool"] and r() < 0.55:
        tail.append("Animal" if sub != "robot" else "Pet")
        said.add("pet_tool")
    if p["hepa"] and r() < 0.25:
        tail.append("Allergy")
        said.add("hepa")
    if sub == "balai" and p["weight_kg"] <= 2.3 and r() < 0.35:
        tail.append("Lite")
    if sub == "traineau" and p["noise_db"] <= 66 and r() < 0.4:
        tail.append("Silence")
    if sub == "traineau" and p["soft_roller"] and r() < 0.3:
        tail.append("Parquet")
        said.add("soft_roller")
    if sub == "robot" and p["navigation"] in ("laser", "camera") and r() < 0.6:
        tail.append({"laser": rng.choice(["navigation laser", "LiDAR"]), "camera": "caméra"}[p["navigation"]])
        said.add("navigation")
    if sub == "robot" and p["auto_empty"] and r() < 0.5:
        tail.append(rng.choice(["avec station de vidage", "+ station d'autovidage"]))
        said.add("auto_empty")
    if p["autonomy_min"] and sub in ("balai", "main", "laveur") and r() < 0.35:
        tail.append(f"{p['autonomy_min']} min")
        said.add("autonomy_min")
    if sub == "balai" and r() < 0.15:
        tail.append(f"{num(p['weight_kg'])} kg")
        said.add("weight_kg")
    if sub == "traineau" and p["power_w"] and r() < 0.35:
        tail.append(f"{p['power_w']} W")
        said.add("power_w")
    title = " ".join([head, brand, model] + tail)

    quality = rng.choices(["riche", "partielle", "aucune"], [55, 30, 15])[0]
    share = {"riche": 0.9, "partielle": 0.45, "aucune": 0.0}[quality]
    props = {}
    yes = lambda b: "Oui" if b else "Non"

    def declare(key, name, value):
        if r() < share:
            props[name] = value
            said.add(key)
    if p["weight_kg"] is not None:
        declare("weight_kg", rng.choice(["Poids", "Poids net", "Poids du produit", "Poids (kg)"]),
                rng.choice([f"{num(p['weight_kg'])} kg", f"{p['weight_kg']} kg", num(p["weight_kg"])]))
    if p["autonomy_min"] is not None:
        declare("autonomy_min", rng.choice(["Autonomie", "Autonomie maximale", "Autonomie (min)", "Durée d'autonomie"]),
                rng.choice([f"{p['autonomy_min']} min", f"Jusqu'à {p['autonomy_min']} minutes", str(p["autonomy_min"])]))
    declare("noise_db", rng.choice(["Niveau sonore", "Niveau sonore (dB)", "Puissance acoustique"]),
            rng.choice([f"{p['noise_db']} dB", f"{p['noise_db']} dB(A)", str(p["noise_db"])]))
    name = rng.choice(["Filtre HEPA", "Filtration HEPA", "Type de filtre", "Filtration"])
    declare("hepa", name, yes(p["hepa"]) if "HEPA" in name else
            (rng.choice(["HEPA H13", "HEPA", "Filtre HEPA lavable"]) if p["hepa"] else rng.choice(["Lavable", "Mousse et microfiltre", "Cyclonique"])))
    if sub in ("balai", "traineau", "main"):
        name = rng.choice(["Sac", "Type de collecteur", "Avec ou sans sac"])
        declare("bagless", name, ("Sans sac" if p["bagless"] else "Avec sac") if name != "Type de collecteur" else
                ("Bac" if p["bagless"] else "Sac"))
        declare("motor_brush", rng.choice(["Brosse motorisée", "Électrobrosse", "Brosse électrique"]), yes(p["motor_brush"]))
        declare("pet_tool", rng.choice(["Spécial animaux", "Brosse poils d'animaux", "Accessoire animaux", "Brosse anti-enchevêtrement"]),
                yes(p["pet_tool"]))
        declare("soft_roller", rng.choice(["Brosse parquet", "Brosse sols durs", "Brosse rouleau doux"]), yes(p["soft_roller"]))
    if sub == "balai":
        declare("handheld", rng.choice(["Utilisable en aspirateur à main", "Aspirateur à main intégré", "2 en 1"]), yes(p["handheld"]))
        if p["cordless"]:
            declare("removable_battery", "Batterie amovible", yes(p["removable_battery"]))
        declare("suction_aw", "Puissance d'aspiration", f"{p['suction_aw']} AW")
    if sub == "main":
        declare("suction_aw", "Puissance d'aspiration", f"{p['suction_aw']} AW")
    if p["dust_l"] is not None:
        declare("dust_l", rng.choice(["Capacité du réservoir", "Capacité du collecteur", "Capacité du bac à poussière"] +
                                     ([] if p["bagless"] else ["Volume du sac"])), f"{num(p['dust_l'])} L")
    if p["reach_m"]:
        declare("reach_m", "Rayon d'action", f"{p['reach_m']} m")
    if p["power_w"]:
        declare("power_w", rng.choice(["Puissance", "Puissance (W)"]), f"{p['power_w']} W")
    if sub == "robot":
        declare("navigation", rng.choice(["Navigation", "Type de navigation", "Système de navigation"]),
                {"aleatoire": "Aléatoire", "gyroscope": "Gyroscope", "laser": rng.choice(["Laser (LiDAR)", "Laser"]),
                 "camera": rng.choice(["Caméra", "Caméra et capteurs"])}[p["navigation"]])
        declare("mapping", rng.choice(["Cartographie", "Cartographie des pièces"]), yes(p["mapping"]))
        declare("auto_empty", rng.choice(["Station de vidage", "Vidage automatique", "Base d'autovidage"]), yes(p["auto_empty"]))
        declare("mop", rng.choice(["Fonction lavage", "Fonction serpillière", "Lavage des sols"]), yes(p["mop"]))
        declare("suction_pa", "Puissance d'aspiration", f"{p['suction_pa']} Pa")
        declare("climb_mm", rng.choice(["Franchissement d'obstacles", "Hauteur de franchissement"]), f"{p['climb_mm']} mm")
        declare("pet_tool", rng.choice(["Brosse anti-enchevêtrement", "Spécial animaux"]), yes(p["pet_tool"]))
    if sub == "laveur":
        declare("self_clean", rng.choice(["Auto-nettoyage", "Autonettoyage"]), yes(p["self_clean"]))
        declare("mop", "Fonction lavage", "Oui")
    if r() < 0.5:
        props["Couleur"] = rng.choice(["Gris", "Noir", "Blanc", "Bleu nuit"])
    if r() < 0.5:
        props["Garantie"] = rng.choice(["2 ans", "5 ans (moteur)"])
    category = "robot-aspirateur" if sub == "robot" else "aspirateur"
    return title, props, category, said


def catalog(seed=57, start=0):
    """Les 160 aspirateurs : [(vérité, titre, propriétés, catégorie déclarée, marque, modèle, ce que la page dit)] ; start :
    le premier numéro de modèle (plusieurs catalogues côte à côte, bench.scale)."""
    rng = random.Random(seed)
    out, k = [], start
    for sub, n in COUNTS.items():
        letters = {"balai": "VXA", "traineau": "TSE", "robot": "RSQ", "laveur": "WF", "main": "HM"}[sub]
        for i in range(n):
            k += 1
            brand = BRANDS[rng.randrange(len(BRANDS))]
            model = f"{letters[i % len(letters)]}{k}" + rng.choice(["", "", " Pro", " Max", " Plus"])
            p = truth_of(rng, sub)
            title, props, cat, said = page_of(rng, p, brand, model)
            out.append({"truth": p, "title": title, "props": props, "category": cat, "brand": brand, "model": model, "said": said})
    return out


def build(store, items, publish_after=True, first_gtin=50000):
    """Les produits lus comme la collecte (le code mesuré : catégorie, caractéristiques), deux offres chacun, 90 jours de
    prix, puis la publication. → {product_id: item}"""
    rng = random.Random(7)
    now = NOW.timestamp()
    market = Market(store, clock=lambda: now - 90 * 86400)
    by_id, offers, prices = {}, [], []
    oid = store.q("SELECT COALESCE(MAX(id), 0) n FROM offers", one=True)["n"]
    for n, it in enumerate(items):
        ex = {"title": it["title"], "brand": it["brand"], "gtin": gtin(first_gtin + n), "category": it["category"],
              "properties": {k.lower(): v for k, v in it["props"].items()}}
        pid = market.match_product(ex)
        by_id[pid] = it
        for m in rng.sample(MERCHANTS, 2):
            oid += 1
            host = m.lower().replace(" ", "").replace("&", "").replace("é", "e") + ".sim"
            offers.append((oid, f"https://{host}/p/{oid}", host, host, m, pid, "active", now, now - 90 * 86400))
            base, t = it["truth"]["price"] * rng.uniform(0.97, 1.06), now - 90 * 86400
            while t < now:
                span = min(now - t, rng.expovariate(1 / (9 * 86400)) + 3600)
                promo = rng.random() < 0.25
                prices.append((oid, t, t + span, round(base * (rng.uniform(0.70, 0.92) if promo else rng.uniform(0.98, 1.03)), 2),
                               round(base, 2) if promo else None, "out_of_stock" if rng.random() < 0.03 else "in_stock"))
                t += span
    with store.tx() as c:
        c.executemany("INSERT INTO offers(id, url, host, retailer, merchant, product_id, status, checked_at, created_at) "
                      "VALUES (?,?,?,?,?,?,?,?,?)", offers)
        c.executemany("INSERT INTO prices(offer_id, first_seen, last_seen, price, was, availability) VALUES (?,?,?,?,?,?)", prices)
    if publish_after:
        publish(store, NOW.date(), now)
    return by_id


# ------------------------------------------------------------------ la vérité, écrite à la main
def covers(p):
    """Une grande maison d'une traite : un balai à fil ou d'au moins 60 min, un traîneau à fil d'au moins 9 m de rayon
    d'action, un robot d'au moins 150 min."""
    s = p["sub"]
    return (s == "balai" and (not p["cordless"] or p["autonomy_min"] >= 60) or s == "traineau" and not p["cordless"] and p["reach_m"] >= 9
            or s == "robot" and p["autonomy_min"] >= 150)


GOOD = {
    "poils": lambda p: p["pet_tool"],                                   # une brosse faite pour les poils
    "allergies": lambda p: p["hepa"],                                   # un filtre HEPA
    "silence": lambda p: p["noise_db"] <= 70,                           # 70 dB au plus
    "leger": lambda p: p["sub"] != "robot" and p["weight_kg"] <= 2.5,   # se porte sans peine
    "escaliers": lambda p: p["sub"] == "main" or p["sub"] == "balai" and p["handheld"] and p["weight_kg"] <= 2.8,
    "a_main": lambda p: p["sub"] == "main" or p["sub"] == "balai" and p["handheld"],     # voiture, miettes, recoins
    "grande_surface": covers,
    "parquet": lambda p: p["soft_roller"] or p["sub"] == "robot",       # une brosse douce (un robot ne raye pas)
    "tapis": lambda p: p["motor_brush"] and p["sub"] in ("balai", "traineau"),
    "lavage": lambda p: p["mop"],
    "vidage": lambda p: p["auto_empty"],
    "cartographie": lambda p: p["mapping"],
    "autonomie": lambda p: (p["autonomy_min"] or 0) >= (150 if p["sub"] == "robot" else 60),
    "puissance": lambda p: (p["suction_aw"] or 0) >= 150 if p["sub"] in ("balai", "main") else (p["suction_pa"] or 0) >= 4000
    if p["sub"] == "robot" else (p["power_w"] or 0) >= 750 if p["sub"] == "traineau" else False,
    "sans_sac": lambda p: p["bagless"] and p["sub"] in ("balai", "traineau", "main", "robot", "laveur"),
    "avec_sac": lambda p: not p["bagless"],
    "sans_fil": lambda p: p["cordless"],
}
CARRIED = {"balai", "traineau", "main"}                                  # ce qu'on porte dans un escalier ou une voiture

# (phrase, exclus : max_price, sub (types admis), must (éliminatoires) ; bons : ce que le besoin demande)
NEEDS = [
    ("aspirateur pour appartement avec parquet et un chat, 300 € max", {"max_price": 300}, ["poils", "parquet"]),
    ("aspirateur léger pour les escaliers", {"sub": CARRIED}, ["escaliers"]),
    ("aspirateur pour poils de chien", {}, ["poils"]),
    ("aspirateur silencieux", {}, ["silence"]),
    ("aspirateur pour allergique", {}, ["allergies"]),
    ("aspirateur pour une grande maison", {"sub": {"balai", "traineau", "robot"}}, ["grande_surface"]),
    ("aspirateur qui lave le sol", {"must": ["lavage"]}, ["lavage"]),
    ("robot aspirateur pour animaux", {"sub": {"robot"}}, ["poils"]),
    ("aspirateur pour moquette", {"sub": {"balai", "traineau", "robot"}}, ["tapis"]),
    ("robot aspirateur qui se vide tout seul", {"sub": {"robot"}, "must": ["vidage"]}, []),
    ("aspirateur pour la voiture", {"sub": CARRIED}, ["a_main"]),
    ("aspirateur sans sac", {"must": ["sans_sac"]}, []),
    ("aspirateur avec sac", {"must": ["avec_sac"]}, []),
    ("aspirateur balai avec une grande autonomie", {"sub": {"balai"}}, ["autonomie"]),
    ("aspirateur pour parquet", {}, ["parquet"]),
    ("robot aspirateur avec cartographie", {"sub": {"robot"}}, ["cartographie"]),
    ("aspirateur silencieux pour allergiques", {}, ["silence", "allergies"]),
    ("aspirateur balai pour chat sous 250 €", {"sub": {"balai"}, "max_price": 250}, ["poils"]),
    ("aspirateur pour les miettes", {"sub": CARRIED}, ["a_main"]),
    ("aspirateur pas bruyant pour le soir", {}, ["silence"]),
    ("aspirateur balai léger", {"sub": {"balai"}}, ["leger"]),
    ("aspirateur traîneau silencieux", {"sub": {"traineau"}}, ["silence"]),
    ("aspirateur puissant pour moquette", {"sub": {"balai", "traineau", "robot"}}, ["tapis", "puissance"]),
    ("aspirateur pour une maison avec deux chats et un enfant allergique", {}, ["poils", "allergies"]),
    ("aspirateur balai qui aspire et lave", {"sub": {"laveur"}}, ["lavage"]),
    ("aspirateur pour carrelage avec serpillière", {"must": ["lavage"]}, []),
    ("aspirateur sans fil pour 120 m2", {"must": ["sans_fil"]}, ["grande_surface"]),
]
VAGUE = ["aspirateur", "je cherche un bon aspirateur", "quel aspirateur choisir ?", "un aspirateur pour la maison"]
PRECISE = [
    ("aspirateur balai sans fil sous 300 €", {"sub": {"balai"}, "must": ["sans_fil"], "max_price": 300}),
    ("robot aspirateur laveur", {"sub": {"robot"}, "must": ["lavage"]}),
    ("aspirateur traîneau sans sac", {"sub": {"traineau"}, "must": ["sans_sac"]}),
    ("aspirateur à main", {"sub": {"main"}}),
]
CONFLICTS = [("robot aspirateur pour les escaliers", "robot"), ("aspirateur à main pour une grande maison", "main"),
             ("robot aspirateur pour la voiture", "robot")]
# Les critères que le moteur peut dire satisfaits, vérifiés sur la vérité (un « oui » doit être vrai)
CLAIMS = {"poils": GOOD["poils"], "filtration": GOOD["allergies"], "silence": GOOD["silence"], "maniabilite": GOOD["leger"],
          "couverture": covers, "parquet": GOOD["parquet"], "tapis": GOOD["tapis"], "lavage": GOOD["lavage"],
          "vidage": GOOD["vidage"], "cartographie": GOOD["cartographie"], "escaliers": GOOD["escaliers"],
          "petits_travaux": GOOD["a_main"], "aspiration": GOOD["puissance"]}
# Ce que la page peut dire, et la clé où le code mesuré le range (les clés de l'ontologie v57 ; sans_fil : une fonction)
READ = {"weight_kg": "weight_kg", "autonomy_min": "autonomy_min", "noise_db": "noise_db", "hepa": "hepa", "bagless": "bagless",
        "motor_brush": "motor_brush", "pet_tool": "pet_tool", "soft_roller": "soft_roller", "handheld": "handheld", "mop": "mop",
        "auto_empty": "auto_empty", "mapping": "mapping", "navigation": "navigation", "reach_m": "reach_m", "dust_l": "dust_l",
        "power_w": "power_w", "suction_pa": "suction_pa", "suction_aw": "suction_aw", "climb_mm": "climb_mm",
        "self_clean": "self_clean", "removable_battery": "removable_battery", "cordless": "sans_fil"}
FOREIGN = ("capacity_kg", "place_settings", "seats", "bed_size", "zones", "volume_l", "width_cm", "screen_in")   # pas des aspirateurs


def admissible(p, ex):
    return ((ex.get("max_price") is None or p["price"] <= ex["max_price"] * 1.03)     # le prix du jour bouge un peu autour du prix de base
            and (not ex.get("sub") or p["sub"] in ex["sub"]) and all(GOOD[k](p) for k in ex.get("must", ())))


# ------------------------------------------------------------------ mesurer
def main():
    path = Path(tempfile.mkdtemp(), "needs.sqlite")
    store = Store(path)
    items = catalog()
    by_id = build(store, items)
    now = NOW.timestamp() + 7200
    api = Api(store, config.load({}, public_url="https://deals.test"), clock=lambda: now)
    price = {r["product_id"]: r["price"] for r in store.q("SELECT product_id, price FROM catalog")}
    attrs = {r["product_id"]: json.loads(r["attrs"] or "{}") for r in store.q("SELECT product_id, attrs FROM catalog")}
    truth = {pid: {**it["truth"], "price": price[pid]} for pid, it in by_id.items() if pid in price}

    def ask(text, extra=None):
        r = api.handle(Request("GET", "/api/r/search", {"q": text, **(extra or {})}))
        return r.body if r.status == 200 else {}

    def ids(body):
        return [c["id"] for c in body.get("products", [])]

    out = {"catalogue": {"produits": len(truth), **{s: sum(t["sub"] == s for t in truth.values()) for s in COUNTS}}}
    # besoins
    rows, claims_ok, claims_all = [], 0, 0
    for text, ex, good_keys in NEEDS:
        body = ask(text)
        got = ids(body)
        adm = {pid for pid, p in truth.items() if admissible(p, ex)}
        good = {pid for pid in adm if all(GOOD[k](truth[pid]) for k in good_keys)}
        gain = lambda pid: 2 if pid in good else 1 if pid in adm else 0
        top = got[:TOP]
        ideal = sorted((gain(pid) for pid in truth), reverse=True)[:TOP]
        dcg = sum(gain(pid) / math.log2(i + 2) for i, pid in enumerate(top))
        idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal)) or 1
        row = {"phrase": text, "bons": len(good), "admissibles": len(adm), "réponse": body.get("total", 0),
               "bons@6": round(sum(pid in good for pid in top) / min(TOP, len(good)), 3) if good else None,
               "exclus@6": sum(pid not in adm for pid in top) if adm else 0, "impasse": bool(good) and not got,
               "rappel": round(sum(pid in good for pid in got[:SHOWN]) / min(SHOWN, len(good)), 3) if good else None,
               "ndcg@6": round(dcg / idcg, 3), "besoins dits": [n.get("key") for n in body.get("needs") or []],
               "ignorés": body.get("ignored") or [], "question": bool(body.get("question"))}
        for c in body.get("products", [])[:TOP]:
            for w in c.get("why") or []:                   # v : 1 satisfait, 0,5 en partie, 0 non, None non précisé
                if w.get("v") == 1 and w.get("c") in CLAIMS and c["id"] in truth:
                    claims_all += 1
                    claims_ok += bool(CLAIMS[w["c"]](truth[c["id"]]))
        rows.append(row)
        if ARGS.v:
            print(f"  {row['bons@6'] if row['bons@6'] is not None else '—'!s:5} bons@6 · {row['exclus@6']} exclus · nDCG {row['ndcg@6']:.2f} · "
                  f"{len(good):3d} bons / {len(adm):3d} admissibles · besoins {row['besoins dits']} · ignorés {row['ignorés']}  {text}")
    scored = [r for r in rows if r["bons@6"] is not None]
    out["besoins"] = {"phrases": len(rows), "bons@6": round(sum(r["bons@6"] for r in scored) / len(scored), 3),
                      "exclus@6": sum(r["exclus@6"] for r in rows), "impasses": sum(r["impasse"] for r in rows),
                      "rappel": round(sum(r["rappel"] for r in scored) / len(scored), 3),
                      "ndcg@6": round(sum(r["ndcg@6"] for r in rows) / len(rows), 3),
                      "besoins dits": sum(bool(r["besoins dits"]) for r in rows), "mots ignorés": sum(len(r["ignorés"]) for r in rows),
                      "questions": sum(r["question"] for r in rows),
                      "explications": {"oui vérifiés": claims_ok, "oui dits": claims_all}, "détail": rows}
    # vagues
    vrows = []
    for text in VAGUE:
        body = ask(text)
        q = body.get("question") or {}
        sels = []
        for o in q.get("options") or []:
            sels.append(frozenset(ids(ask(text, o.get("apply") or {}))[:TOP]))
        useful = len(sels) >= 2 and all(sels) and len(set(sels)) == len(sels)
        vrows.append({"phrase": text, "produits": len(ids(body)), "question": bool(q), "utile": useful,
                      "réponses": len(sels), "texte": q.get("text")})
        if ARGS.v:
            print(f"  vague : {len(ids(body))} produits · question {bool(q)} ({q.get('text')}) · utile {useful}  {text}")
    out["vagues"] = {"phrases": len(vrows), "avec produits": sum(r["produits"] > 0 for r in vrows),
                     "question": sum(r["question"] for r in vrows), "utile": sum(r["utile"] for r in vrows), "détail": vrows}
    # précises
    ref = next(pid for pid, it in sorted(by_id.items()) if it["truth"]["sub"] == "robot" and it["model"].endswith(" Max"))
    exact = f"{by_id[ref]['brand']} {by_id[ref]['model']}"
    prows = []
    body = ask(exact)
    prows.append({"phrase": exact, "question": bool(body.get("question")), "première juste": ids(body)[:1] == [ref]})
    for text, ex in PRECISE:
        body = ask(text)
        got = ids(body)
        adm = {pid for pid, p in truth.items() if admissible(p, ex)}
        prows.append({"phrase": text, "question": bool(body.get("question")),
                      "admissibles@6": round(sum(pid in adm for pid in got[:TOP]) / max(1, min(TOP, len(got))), 3),
                      "rappel": round(sum(pid in adm for pid in got[:SHOWN]) / max(1, min(SHOWN, len(adm))), 3)})
    if ARGS.v:
        for r in prows:
            print(f"  précise : {r}")
    out["précises"] = {"phrases": len(prows), "questions": sum(r["question"] for r in prows),
                       "référence en premier": prows[0]["première juste"],
                       "admissibles@6": round(sum(r["admissibles@6"] for r in prows[1:]) / len(prows[1:]), 3),
                       "rappel": round(sum(r["rappel"] for r in prows[1:]) / len(prows[1:]), 3), "détail": prows}
    # conflits
    crow = []
    for text, sub in CONFLICTS:
        body = ask(text)
        s = body.get("suggest") or {}
        crow.append({"phrase": text, "proposé": bool(s.get("sub") and s.get("sub") != sub and s.get("why")), "suggest": s})
        if ARGS.v:
            print(f"  conflit : {crow[-1]}")
    out["conflits"] = {"phrases": len(crow), "autre type proposé": sum(r["proposé"] for r in crow), "détail": crow}
    # lecture
    read = {k: {"sur la page": 0, "juste": 0, "faux": 0} for k in READ}
    foreign = 0
    for pid, it in by_id.items():
        a, t = attrs.get(pid, {}), it["truth"]
        foreign += sum(k in a for k in FOREIGN)
        for k, key in READ.items():
            if k not in it["said"]:
                continue
            read[k]["sur la page"] += 1
            if k == "cordless":                            # une fonction (« sans fil ») ; « filaire » lu : cordless faux
                v = True if "sans_fil" in a.get("features", ()) else a.get("cordless")
            else:
                v = a.get(key)
            if v is None:
                continue
            right = abs(float(v) - float(t[k])) <= 0.05 * abs(float(t[k])) + 1e-9 if isinstance(t[k], (int, float)) and not isinstance(t[k], bool) \
                else v == t[k]
            read[k]["juste" if right else "faux"] += 1
    on_page = sum(v["sur la page"] for v in read.values())
    out["lecture"] = {"sur la page": on_page, "lus justes": sum(v["juste"] for v in read.values()),
                      "lus faux": sum(v["faux"] for v in read.values()), "faits faux (autres rayons)": foreign, "détail": read}

    b, v, p, c, lu = out["besoins"], out["vagues"], out["précises"], out["conflits"], out["lecture"]
    print(f"{len(truth)} aspirateurs à vérité connue ({', '.join(f'{n} {s}' for s, n in COUNTS.items())})")
    print(f"  besoins ({b['phrases']} phrases) : bons parmi les 6 premières {b['bons@6']:.0%} · exclus {b['exclus@6']} · impasses "
          f"{b['impasses']} · rappel {b['rappel']:.0%} · nDCG@6 {b['ndcg@6']:.2f} · besoins dits {b['besoins dits']} · "
          f"mots ignorés {b['mots ignorés']} · explications vérifiées {claims_ok}/{claims_all}")
    print(f"  vagues ({v['phrases']}) : avec produits {v['avec produits']} · question {v['question']} · utile {v['utile']}")
    print(f"  précises ({p['phrases']}) : questions {p['questions']} · référence en premier {p['référence en premier']} · "
          f"admissibles parmi les 6 premières {p['admissibles@6']:.0%} · rappel {p['rappel']:.0%}")
    print(f"  conflits ({c['phrases']}) : autre type proposé {c['autre type proposé']}")
    print(f"  lecture : {lu['sur la page']} caractéristiques sur les pages · lues justes {lu['lus justes']} · lues fausses {lu['lus faux']} · "
          f"faits d'autres rayons {lu['faits faux (autres rayons)']}")
    if ARGS.json:
        Path(ARGS.json).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=list))
    store.close()


if __name__ == "__main__":
    main()
