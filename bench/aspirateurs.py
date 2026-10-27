"""Les aspirateurs tels que les donne un flux affilié : lit-on juste ce que l'offre dit, et rien d'autre ?

Un flux affilié (ou l'API d'une enseigne) donne pour chaque offre un titre, une marque, un prix, un EAN et la catégorie
de l'enseigne (« Électroménager > Aspirateur > Aspirateur balai ») ; il ne donne pas de fiche technique complète. Ce banc
génère 160 aspirateurs à VÉRITÉ CONNUE (marques fictives) — leur type (balai, traîneau, robot, laveur, à main), sans fil
ou non, sans sac ou non — et leur offre comme un flux la donnerait : un titre qui dit parfois le type et les attributs
(« Aspirateur balai sans fil Brava X5 »), parfois seulement le modèle (« Brava X5 Max »), et une catégorie plus ou moins
précise. Le code mesuré lit les offres comme la collecte (market.match_product), publie, puis on lui pose des recherches.

Mesures
  types       l'offre dit le type (titre ou catégorie) : rangé juste, faux, pas rangé ; elle ne le dit pas : pas deviné
  attributs   sans fil, sans sac : l'offre le dit → lu juste, lu faux, pas lu ; elle ne le dit pas → inconnu (pas deviné)
  recherches  « aspirateur balai sans fil sous 300 € », « aspirateur traîneau sans sac »… : cartes qui conviennent parmi
              les 6 premières, rappel de ce qui convient et que l'offre dit
  variantes   des offres écrites comme on les trouve dans les flux (majuscules, tirets, « à sac », « aspirateur robot »,
              un type dit par la seule catégorie) et des pièges (sacs, batteries, filtres, une station de vidage, un balai
              vapeur) : un aspirateur reconnu et lu juste, un accessoire qui n'entre pas au rayon

  python -m bench.aspirateurs [--code <dossier du code>] [--json sortie.json]
"""
import argparse
import json
import random
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--code", help="dossier d'un autre code à mesurer (le code d'avant)")
ap.add_argument("--json")
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
HEAD = {"balai": "Aspirateur balai", "traineau": "Aspirateur traîneau", "robot": "Robot aspirateur", "laveur": "Aspirateur laveur",
        "main": "Aspirateur à main"}
PATH = {"balai": "Aspirateur balai", "traineau": "Aspirateur traîneau", "robot": "Robot aspirateur", "laveur": "Aspirateur laveur",
        "main": "Aspirateur à main"}


def truth_of(rng, sub):
    """Le vrai produit : son type, sans fil, sans sac, son prix."""
    cordless = {"balai": rng.random() < 0.9, "traineau": rng.random() < 0.05, "robot": True, "laveur": rng.random() < 0.85, "main": True}[sub]
    bagless = rng.random() < 0.65 if sub == "traineau" else True
    base = {"balai": 220, "traineau": 160, "robot": 380, "laveur": 360, "main": 70}[sub]
    return {"sub": sub, "cordless": cordless, "bagless": bagless, "price": max(29, int(round(base * rng.uniform(0.5, 1.8) / 10)) * 10 - 1)}


def offer_of(rng, p, brand, model):
    """L'offre telle qu'un flux la donne : un titre, une catégorie déclarée. → (titre, catégorie, ce que l'offre dit)"""
    said, words = set(), []
    if rng.random() < 0.75:                                # le plus souvent, le titre dit le type…
        words.append(HEAD[p["sub"]])
        said.add("sub")
        if p["sub"] in ("balai", "laveur", "main", "traineau") and rng.random() < 0.7:
            if p["cordless"]:
                words.append("sans fil")
                said.add("cordless")
            elif p["sub"] != "main":
                words.append("filaire")
                said.add("cordless")
        if p["sub"] == "traineau" and rng.random() < 0.7:
            words.append("sans sac" if p["bagless"] else "avec sac")
            said.add("bagless")
    title = " ".join(words + [brand, model])               # …sinon seulement la marque et le modèle
    generic = "Électroménager > " + ("Robot aspirateur" if p["sub"] == "robot" else "Aspirateur")   # un robot a son rayon
    path = rng.choice([generic, "Électroménager > Entretien des sols > " + PATH[p["sub"]], PATH[p["sub"]]])
    said |= {"sub"} if path.endswith(PATH[p["sub"]]) else set()
    return title, path, said


def catalog(seed=58, start=0):
    """Les 160 aspirateurs : [{truth, title, category, brand, model, said}] ; start : le premier numéro de modèle."""
    rng = random.Random(seed)
    out, k = [], start
    for sub, n in COUNTS.items():
        for i in range(n):
            k += 1
            brand = BRANDS[rng.randrange(len(BRANDS))]
            model = f"{sub[0].upper()}{k}" + rng.choice(["", "", " Pro", " Max", " Plus"])
            p = truth_of(rng, sub)
            title, path, said = offer_of(rng, p, brand, model)
            out.append({"truth": p, "title": title, "category": path, "brand": brand, "model": model, "said": said})
    return out


def build(store, items, publish_after=True, first_gtin=50000):
    """Les offres lues comme la collecte (le code mesuré), deux enseignes chacune, 90 jours de prix, puis la
    publication. → {product_id: item}"""
    rng = random.Random(7)
    now = NOW.timestamp()
    market = Market(store, clock=lambda: now - 90 * 86400)
    by_id, offers, prices = {}, [], []
    oid = store.q("SELECT COALESCE(MAX(id), 0) n FROM offers", one=True)["n"]
    for n, it in enumerate(items):
        pid = market.match_product({"title": it["title"], "brand": it["brand"], "gtin": gtin(first_gtin + n), "category": it["category"]})
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


SEARCHES = [("aspirateur balai sans fil sous 300 €", {"sub": "balai", "cordless": True, "max_price": 300}),
            ("aspirateur traîneau sans sac", {"sub": "traineau", "bagless": True}),
            ("robot aspirateur", {"sub": "robot"}), ("aspirateur à main", {"sub": "main"}),
            ("aspirateur balai", {"sub": "balai"}), ("aspirateur laveur", {"sub": "laveur"})]


# Des offres écrites comme dans les flux, et des pièges. L'attendu : ce que l'offre dit (un attribut absent : elle ne le
# dit pas, il doit rester inconnu) ; None : ce n'est pas un aspirateur, il n'entre pas au rayon.
VARIANTES = [
    ("Aspirateur-balai sans-fil Brava X7", "Maison > Aspirateurs", {"sub": "balai", "cordless": True}),
    ("ASPIRATEUR BALAI SANS FIL ZEPHYR V12", "Électroménager > Aspirateur", {"sub": "balai", "cordless": True}),
    ("Aspirateur traineau sans sac Kessler C3", "Aspirateurs traîneaux", {"sub": "traineau", "bagless": True}),
    ("Aspirateur traîneau à sac Ostra S2", "Électroménager > Aspirateurs > Aspirateurs avec sac", {"sub": "traineau", "bagless": False}),
    ("Aspirateur à sac Ostra S3 750 W", "Aspirateurs traîneaux", {"sub": "traineau", "bagless": False}),
    ("Aspirateur robot Helio R9", "Électroménager > Aspirateurs > Robots aspirateurs", {"sub": "robot"}),
    ("Robot laveur de sols Vela W5", "Entretien des sols > Robots", {"sub": "robot"}),
    ("Aspirateur de table Nimbo T1", "Petit électroménager > Aspirateurs", {"sub": "main"}),
    ("Aspirateur à main sans fil Corvo H2", "Aspirateurs à main", {"sub": "main", "cordless": True}),
    ("Aspirateur 2 en 1 balai et main Maelis Duo", "Aspirateurs balais", {"sub": "balai"}),
    ("Aspirateur balai filaire Kessler F1", "Aspirateurs balais", {"sub": "balai", "cordless": False}),
    ("Aspirateur sans fil Brava Slim", "Électroménager > Aspirateurs > Aspirateurs balais", {"sub": "balai", "cordless": True}),
    ("Aspirateur eau et poussière Ondine WD20", "Bricolage > Aspirateurs eau et poussières", {}),
    ("Nettoyeur de sols sans fil Vela F8", "Électroménager > Nettoyeurs de sols", {"sub": "laveur", "cordless": True}),
    ("Aspirateur balai laveur sans fil Vela W2", "Aspirateurs balais", {"sub": "laveur", "cordless": True}),
    ("Zephyr V15 Detect Absolute", "Électroménager > Aspirateur balai sans fil", {"sub": "balai", "cordless": True}),
    ("Brava X5", "Électroménager > Aspirateur", {}),
    ("Aspirateur traîneau Ostra Compact Sans Sac 700W A+", None, {"sub": "traineau", "bagless": True}),
    ("Aspirateur balai sans fil et sans sac Helio Air", None, {"sub": "balai", "cordless": True, "bagless": True}),
    ("Aspirateur balai Brava avec fil 600 W", None, {"sub": "balai", "cordless": False}),
    ("Aspirateur traîneau filaire avec sac Kessler", None, {"sub": "traineau", "cordless": False, "bagless": False}),
    ("Aspirateur robot laveur Helio S8 avec station", None, {"sub": "robot"}),
    ("Aspirateur cyclonique Corvo 900 W", None, {}),
    ("Sacs aspirateur x10 compatibles Ostra", "Électroménager > Accessoires aspirateur", None),
    ("Batterie pour aspirateur balai Zephyr V10", "Accessoires aspirateur", None),
    ("Filtre HEPA pour robot aspirateur Helio", "Accessoires", None),
    ("Balai vapeur Vela Steam 1500 W", "Entretien des sols > Balais vapeur", None),
    ("Brosse turbo pour aspirateur traîneau", "Accessoires aspirateur", None),
    ("Station de vidage pour robot aspirateur Helio", None, None),
    ("Balai à franges microfibre", "Entretien > Balais", None),
    ("Nettoyeur vapeur multifonction Vela S10", "Entretien des sols > Nettoyeurs vapeur", None),
]
VACUUMS = {"aspirateur", "robot_aspirateur"}


def variantes():
    """Chaque offre lue comme la collecte (market.match_product) → {aspirateurs, pièges, écarts: [(titre, attendu, lu)]}."""
    store = Store(Path(tempfile.mkdtemp(), "variantes.sqlite"))
    market = Market(store, clock=lambda: NOW.timestamp())
    res = {"aspirateurs": 0, "reconnus": 0, "types justes": 0, "types attendus": 0, "attributs justes": 0, "attributs dits": 0,
           "attributs devinés": 0, "pièges": 0, "pièges écartés": 0, "écarts": []}
    for n, (title, declared, want) in enumerate(VARIANTES):
        pid = market.match_product({"title": title, "brand": title.split()[-1], "gtin": gtin(90000 + n), "category": declared})
        p = store.q("SELECT category, attributes FROM products WHERE id=?", (pid,), one=True)
        a = json.loads(p["attributes"] or "{}")
        got = {k: a.get(k) for k in ("sub", "cordless", "bagless") if a.get(k) is not None}
        if want is None:
            res["pièges"] += 1
            res["pièges écartés"] += p["category"] not in VACUUMS
            if p["category"] in VACUUMS:
                res["écarts"].append((title, "pas un aspirateur", p["category"]))
            continue
        res["aspirateurs"] += 1
        res["reconnus"] += p["category"] in VACUUMS
        if "sub" in want:
            res["types attendus"] += 1
            res["types justes"] += got.get("sub") == want["sub"]
        for k in ("cordless", "bagless"):
            if k in want:
                res["attributs dits"] += 1
                res["attributs justes"] += got.get(k) == want[k]
            elif k in got:
                res["attributs devinés"] += 1
        if p["category"] not in VACUUMS or {k: got.get(k) for k in want} != want or any(k in got for k in ("cordless", "bagless") if k not in want):
            res["écarts"].append((title, want, {"catégorie": p["category"], **got}))
    store.close()
    return res


def main():
    store = Store(Path(tempfile.mkdtemp(), "aspirateurs.sqlite"))
    by_id = build(store, catalog())
    now = NOW.timestamp() + 7200
    api = Api(store, config.load({}, public_url="https://deals.test"), clock=lambda: now)
    rows = {r["product_id"]: r for r in store.q("SELECT product_id, price, attrs FROM catalog")}
    out = {"produits": len(rows)}
    # types et attributs : ce que l'offre dit, lu juste ; ce qu'elle ne dit pas, pas deviné
    for key in ("sub", "cordless", "bagless"):
        res = {"dit": 0, "juste": 0, "faux": 0, "pas lu": 0, "non dit": 0, "deviné": 0}
        for pid, it in by_id.items():
            got = json.loads(rows[pid]["attrs"] or "{}").get(key)
            if key in it["said"]:
                res["dit"] += 1
                res["pas lu" if got is None else "juste" if got == it["truth"][key] else "faux"] += 1
            else:
                res["non dit"] += 1
                res["deviné"] += got is not None
        out[key] = res
    # recherches : justes parmi les 6 premières ; rappel de ce qui convient et que l'offre dit (le type dit, l'attribut dit
    # ou entraîné par le type : un robot est sans fil)
    implied = {"robot": {"cordless", "bagless"}, "main": {"cordless", "bagless"}, "laveur": {"bagless"}, "balai": {"bagless"}, "traineau": set()}
    found = []
    for text, want in SEARCHES:
        body = api.handle(Request("GET", "/api/r/search", {"q": text})).body
        got = [c["id"] for c in body.get("products", [])]
        ok = lambda pid: all(by_id[pid]["truth"][k] == v for k, v in want.items() if k != "max_price") and \
            (want.get("max_price") is None or rows[pid]["price"] <= want["max_price"])
        stated = lambda it: it["said"] | (implied[it["truth"]["sub"]] if "sub" in it["said"] else set())
        findable = {pid for pid, it in by_id.items() if ok(pid) and {k for k in want if k != "max_price"} <= stated(it)}
        top = got[:TOP]
        found.append({"recherche": text, "réponse": len(got), "justes@6": round(sum(ok(p) for p in top) / max(1, len(top)), 3),
                      "rappel (dit)": round(sum(p in findable for p in got[:SHOWN]) / max(1, min(SHOWN, len(findable))), 3)})
    out["recherches"] = found
    out["variantes"] = v = variantes()
    print(f"{out['produits']} aspirateurs, offres comme un flux affilié (titre, catégorie de l'enseigne)")
    for key, label in (("sub", "type"), ("cordless", "sans fil"), ("bagless", "sans sac")):
        r = out[key]
        print(f"  {label:9} dit par l'offre {r['dit']:3d} : lu juste {r['juste']:3d} · faux {r['faux']} · pas lu {r['pas lu']}"
              f"  |  non dit {r['non dit']:3d} : deviné {r['deviné']}")
    for f in found:
        print(f"  « {f['recherche']} » : {f['réponse']} produits · justes parmi les 6 premières {f['justes@6']:.0%} · rappel {f['rappel (dit)']:.0%}")
    print(f"  variantes : {v['reconnus']}/{v['aspirateurs']} aspirateurs reconnus · types {v['types justes']}/{v['types attendus']}"
          f" · attributs {v['attributs justes']}/{v['attributs dits']} (devinés {v['attributs devinés']})"
          f" · pièges écartés {v['pièges écartés']}/{v['pièges']}")
    for t, want, got in v["écarts"]:
        print(f"    écart : « {t} » attendu {want}, lu {got}")
    if ARGS.json:
        Path(ARGS.json).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    store.close()


if __name__ == "__main__":
    main()
