"""Recherche : trouve-t-on vite ce qu'on cherche ? Des phrases comme on les tape (celles des missions, les exemples de la
Recherche), et la première réponse de l'API à la phrase tapée, sans rien toucher d'autre, sur la démo ou sur 3 000
produits.

Pour chaque phrase, ce qu'elle demande est écrit à la main (bench.missions : catégorie, marque, fonctions, taille ou
capacité, prix maximum ; les exemples de la Recherche ici). Une carte répond à la demande si elle a tout ce qui est
demandé (mêmes règles que les missions : missions.matches, disponibilité mise à part). Mesures, sur les phrases dont
le catalogue a la réponse :
  impasse           la Recherche ne montre rien alors que des produits répondent (« Rien pour … »)
  1re juste         la première carte répond à la demande
  pertinence        part des n premières cartes qui répondent, n = le nombre de produits qui répondent (12 au plus)
  rappel            part des produits qui répondent (60 au plus) que la réponse montre
et sur les phrases sans réponse au catalogue : écran vide (rien à montrer, pas même le plus proche).
  python -m bench.search [--scale] [--code <dossier du code>] [--json sortie.json] [-v]
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--scale", action="store_true", help="3 000 produits (bench.scale) au lieu de la démo")
ap.add_argument("--code", help="dossier d'un autre code à mesurer (le code d'avant)")
ap.add_argument("--json")
ap.add_argument("-v", action="store_true", help="le détail de chaque phrase")
ARGS = ap.parse_args()
if ARGS.code:
    sys.path.insert(0, ARGS.code)

from bench.missions import PHRASES  # noqa: E402
from deals import config, demo  # noqa: E402
from deals.api import Api, Request  # noqa: E402
from deals.missions import matches  # noqa: E402
from deals.store import Store  # noqa: E402

K, SHOWN = 12, 60
# les exemples proposés par la Recherche (web/src/App.jsx, TRY) et quelques recherches courtes
EXTRA = [
    ("aspirateur balai", ("aspirateur", None, ["balai"], {}, None)),
    ("lave-linge 9 kg", ("lave_linge", None, [], {"capacity_kg": 9}, None)),
    ("matelas 160x200", ("matelas", None, [], {"bed_size": "160x200"}, None)),
    ("canapé d'angle", ("canape", None, ["angle"], {}, None)),
    ("réfrigérateur", ("refrigerateur", None, [], {}, None)),
    ("canapés", ("canape", None, [], {}, None)),
    ("Nordvik", (None, "Nordvik", [], {}, None)),
    ("lave vaisselle encastrable", ("lave_vaisselle", None, ["encastrable"], {}, None)),
]


def wanted():
    """(phrase, demande) des phrases comprises (les refus des missions ne sont pas des recherches à mesurer)."""
    out = []
    for text, want in PHRASES + EXTRA:
        if want[0] == "refus":
            continue
        cat, brand, feats, attrs, price, *extra = want
        out.append((text, {"category": cat, "brand": brand, "features": feats, "attrs": attrs, "max_price": price, **(extra[0] if extra else {})}))
    return out


def main():
    path = Path(tempfile.mkdtemp(), "search.sqlite")
    store = Store(path)
    if ARGS.scale:
        sys.path.insert(1, str(Path(__file__).resolve().parent.parent))
        from bench import scale
        from deals.publish import publish
        scale.generate(store)
        publish(store, scale.NOW.date(), scale.NOW.timestamp())
        now, rules = scale.NOW.timestamp() + 7200, None
    else:
        demo.build(store, partners=set(demo.RULES))
        now, rules = store.q("SELECT MAX(last_seen) t FROM prices", one=True)["t"] + 3600, demo.RULES
    api = Api(store, config.load({}, public_url="https://deals.test"), clock=lambda: now, rules=rules)
    catalog = {r["product_id"]: {"product_id": r["product_id"], "category": r["category"], "brand": r["brand"], "price": r["price"],
                                 "in_stock": True, "attrs": json.loads(r["attrs"] or "{}")}
               for r in store.q("SELECT product_id, category, brand, price, attrs FROM catalog")}
    rows, t = [], {"found": 0, "dead": 0, "first": 0, "precision": 0.0, "recall": 0.0, "none": 0, "blank": 0}
    for text, spec in wanted():
        r = api.handle(Request("GET", "/api/r/search", {"q": text}))
        got = r.body.get("products", []) if r.status == 200 else []
        good = {pid for pid, p in catalog.items() if matches(spec, p)}
        ok = [p["id"] in good for p in got]
        row = {"phrase": text, "results": r.body.get("total", 0) if r.status == 200 else 0, "relevant": len(good)}
        if good:
            n = min(K, len(good))
            row.update(precision=round(sum(ok[:n]) / n, 3), recall=round(sum(ok[:SHOWN]) / min(SHOWN, len(good)), 3),
                       first=bool(ok and ok[0]))
            t["found"] += 1
            t["dead"] += not got
            t["first"] += row["first"]
            t["precision"] += row["precision"]
            t["recall"] += row["recall"]
        else:
            t["none"] += 1
            t["blank"] += not got
        rows.append(row)
        if ARGS.v:
            print(f"{row['results']:4d} résultats · {len(good):3d} attendus · pertinence {row.get('precision', 0):4.0%} · "
                  f"rappel {row.get('recall', 0):4.0%}  {text}")
    f = t["found"] or 1
    out = {"phrases": len(rows), "avec réponse": t["found"], "impasses": t["dead"], "1re juste": t["first"],
           "pertinence": round(t["precision"] / f, 3), "rappel": round(t["recall"] / f, 3),
           "sans réponse": t["none"], "écrans vides": t["blank"], "détail": rows}
    print(f"{len(rows)} recherches tapées ({'3 000 produits' if ARGS.scale else f'démo, {len(catalog)} produits'})")
    print(f"  {t['found']} dont le catalogue a la réponse : impasses {t['dead']} · 1re carte juste {t['first']} · "
          f"pertinence {out['pertinence']:.0%} · rappel {out['rappel']:.0%}")
    print(f"  {t['none']} sans réponse au catalogue : écran vide {t['blank']}")
    if ARGS.json:
        Path(ARGS.json).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    store.close()


if __name__ == "__main__":
    main()
