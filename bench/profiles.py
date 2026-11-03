"""Personnalisation, mesurée sur des personnes simulées aux goûts connus : ce que montrent les top deals, la sélection de
l'accueil et le feed de la Recherche, selon ce que la personne a fait avant.

Chaque personne simulée s'intéresse à une ou deux catégories du catalogue de la démo (59 produits). Sept situations :
nouvelle (aucun signal), a ouvert 3 fiches de ses rayons, a cherché son rayon puis ouvert 2 fiches, a cherché son rayon
avec une précision (« canapés pas cher ») sans rien ouvrir, a choisi ses rayons dans l'accueil, a un compte avec un
historique (une marque suivie, un favori, 2 clics vers l'enseigne, 5 fiches), a une mission en cours. Tout passe par l'API, comme l'app : le même banc mesure le code d'avant (les paramètres inconnus
y sont ignorés) et celui d'après.

Écrans : les 10 top deals, « pour vous » (accueil, code d'après seulement), les 12 premières cartes de notre sélection et
du feed de la Recherche, et l'accueil entier dans l'ordre où il se lit (top deals, pour vous, sélection : 20 cartes).
Mesures :
  pertinence       part des cartes dans les rayons de la personne
  1re pertinente   rang de la première carte de ses rayons (1 = en tête)
  clics attendus   modèle simple : attrait de la carte × biais de position (1 / log2(rang + 1)) ; attrait = 1 pour ses
                   rayons, 0,3 pour la même famille, 0,1 sinon, × (0,4 + 0,6 × remise / 50, plafonné) ; 0,3 sans remise
  remise moyenne   l'intérêt des deals montrés (ne doit pas baisser beaucoup)
  rayons           nombre de catégories différentes (diversité)

Deux catalogues : la démo au 14 décembre 2025 (un jour ordinaire : 13 remises pour 59 produits ; --end AAAA-MM-JJ pour un
autre jour, 2025-11-28 : Black Friday), ou --scale : 3 000 produits, 8 rayons, ~750 remises (bench.scale).

  python -m bench.profiles [--people 120] [--end 2025-12-14 | --scale] [--code <dossier du code>] [--json sortie.json]
"""
import argparse
import hashlib
import json
import math
import random
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--people", type=int, default=120)
ap.add_argument("--code", help="dossier d'un autre code à mesurer (le code d'avant)")
ap.add_argument("--json")
ap.add_argument("--end", default="2025-12-14", help="démo : dernière nuit simulée")
ap.add_argument("--scale", action="store_true", help="3 000 produits (bench.scale) au lieu de la démo")
ARGS = ap.parse_args()
if ARGS.code:
    sys.path.insert(0, ARGS.code)

from datetime import date  # noqa: E402

from deals import config, demo  # noqa: E402
from deals.api import Api, Request  # noqa: E402
from deals.extract.categories import FAMILY_OF  # noqa: E402
from deals.store import Store  # noqa: E402

SITUATIONS = ("nouvelle", "3 fiches vues", "a cherché", "a cherché (précis)", "rayons choisis", "compte avec historique",
              "mission en cours")
K = 12
END = date.fromisoformat(ARGS.end)
NOW = datetime(END.year, END.month, END.day, 12, tzinfo=timezone.utc).timestamp()     # deux heures après la dernière nuit


def attract(p, likes):
    fam = {FAMILY_OF.get(c) for c in likes}
    rel = 1.0 if p["category"] in likes else 0.3 if FAMILY_OF.get(p["category"]) in fam else 0.1
    quality = 0.4 + 0.6 * min(p["pct"], 50) / 50 if p["pct"] > 0 else 0.3
    return rel * quality


def measure(cards, likes):
    rel = [p["category"] in likes for p in cards]
    first = next((i + 1 for i, r in enumerate(rel) if r), None)
    return {"pertinence": sum(rel) / len(cards) if cards else 0, "first": first,
            "clicks": sum(attract(p, likes) / math.log2(i + 2) for i, p in enumerate(cards)),
            "pct": sum(p["pct"] for p in cards) / len(cards) if cards else 0, "rayons": len({p["category"] for p in cards}),
            "cards": len(cards)}


class Client:
    """Ce que fait l'app pour une personne : ses appels, ses traces gardées dans le navigateur (fiches vues, rayons choisis,
    recherches récentes), sa session si elle a un compte."""

    def __init__(self, api, session=None):
        self.api, self.session, self.events, self.picks, self.recent = api, session, [], [], []

    def call(self, method, path, query=None, body=None):
        r = self.api.handle(Request(method, path, {k: v for k, v in (query or {}).items() if v}, body or {}, self.session or ""))
        return r.body if r.status == 200 else None

    def taste(self):
        """Les paramètres de goût qu'envoie l'app (ignorés par un code qui ne les connaît pas)."""
        return {"p": ",".join(f"{k}{i}.0" for k, i in reversed(self.events)) if not self.session else "",
                "i": ",".join(self.picks) if not self.session else "", "recent": "|".join(self.recent)}

    def view(self, pid):
        self.events.append(("v", pid))
        self.call("POST", "/api/r/view", body={"product_id": pid, "from": "item"})

    def surfaces(self):
        q = self.taste()
        get = lambda path: (self.call("GET", path, q) or {}).get("products", [])
        top, foryou, today, feed = get("/api/r/top"), get("/api/r/foryou"), get("/api/r/today"), get("/api/r/search")
        seen = {p["id"] for p in top}
        you = [p for p in foryou if p["id"] not in seen]              # comme l'app : sans répéter les top deals
        seen |= {p["id"] for p in you}
        selection = [p for p in today if p["id"] not in seen][:K]
        return {"top": top, "pour vous": you, "sélection": selection, "accueil": (top + you + selection)[:20], "feed": feed[:K]}


def account(store, api, n):
    token = f"bench-{n}"
    uid = store.x("INSERT INTO users(email, created_at) VALUES (?, ?)", (f"p{n}@exemple.test", NOW - 30 * 86400))
    store.x("INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES (?,?,?,?)",
            (hashlib.sha256(token.encode()).hexdigest(), uid, NOW - 86400, NOW + 30 * 86400))
    return Client(api, token)


def main():
    global NOW
    path = Path(tempfile.mkdtemp(), "bench.sqlite")
    store = Store(path)
    if ARGS.scale:
        sys.path.insert(1, str(Path(__file__).resolve().parent.parent))
        from bench import scale                                # le catalogue de 3 000 produits
        from deals.publish import publish
        scale.generate(store)
        publish(store, scale.NOW.date(), scale.NOW.timestamp())
        NOW, rules = scale.NOW.timestamp() + 7200, None
    else:
        demo.build(store, end=END, nights=(END - demo.FIRST_NIGHT).days, partners=set(demo.RULES))
        rules = demo.RULES
    api = Api(store, config.load({}, public_url="https://deals.test"), clock=lambda: NOW, rules=rules)
    anon = Client(api)
    cats = [c for c in anon.call("GET", "/api/r/categories", {"all": "1"}) if c["products"] >= 3]
    # le choix des personnes simulées : tous les produits d'un rayon, les remises d'abord, puis du moins cher au plus cher
    # (la liste de l'ancienne route category/<clé>, retirée en v68 : le même tirage d'une version à l'autre)
    pool = lambda key: api.catalog.cards(None, store.q("SELECT * FROM catalog WHERE category=? ORDER BY pct > 0 DESC, pct DESC, "
                                                        "price, product_id LIMIT 60", (key,)))
    products = {c["key"]: pool(c["key"]) for c in cats}
    rng = random.Random(7)
    totals = defaultdict(lambda: defaultdict(list))
    for n in range(ARGS.people):
        likes = rng.sample([c["key"] for c in cats], rng.choice((1, 1, 1, 2, 2)))
        mine = [p for c in likes for p in products[c]]
        label = next(c["label"] for c in cats if c["key"] == likes[0]).lower()
        for situation in SITUATIONS:
            c = Client(api)
            if situation == "3 fiches vues":
                for p in rng.sample(mine, min(3, len(mine))):
                    c.view(p["id"])
            elif situation == "a cherché":
                c.recent = [label]
                for p in rng.sample(mine, min(2, len(mine))):
                    c.view(p["id"])
            elif situation == "a cherché (précis)":
                c.recent = [f"{label} pas cher"]
            elif situation == "rayons choisis":
                c.picks = likes
            elif situation in ("compte avec historique", "mission en cours"):
                c = account(store, api, f"{situation[:3]}{n}")
                if situation == "compte avec historique":
                    pick = rng.choice(mine)
                    c.call("POST", "/api/r/brand/follow", body={"brand": pick["brand"], "on": True})
                    c.call("POST", "/api/r/save", body={"product_id": rng.choice(mine)["id"], "on": True})
                    for p in rng.sample(mine, min(2, len(mine))):
                        c.call("GET", f"/api/r/out/{p['offer_id']}", {"from": "item"})
                    for p in [rng.choice(mine) for _ in range(5)]:
                        c.view(p["id"])
                else:
                    c.call("POST", "/api/r/missions", body={"category": likes[0], "max_price": 5000})
            for surface, cards in c.surfaces().items():
                for k, v in measure(cards, set(likes)).items():
                    totals[(situation, surface)][k].append(v)
    out = {}
    print(f"{ARGS.people} personnes simulées · top deals (10), pour vous (10), sélection et feed ({K}), accueil (20)")
    print(f"{'situation':<24} {'écran':<10} {'cartes':>6} {'pertinence':>10} {'1re pert.':>9} {'clics att.':>10} {'remise':>7} {'rayons':>6}")
    for (situation, surface), m in totals.items():
        firsts = [f for f in m["first"] if f]
        row = {"pertinence": round(sum(m["pertinence"]) / len(m["pertinence"]), 3),
               "first": round(sum(firsts) / len(firsts), 1) if firsts else None,
               "clicks": round(sum(m["clicks"]) / len(m["clicks"]), 3), "pct": round(sum(m["pct"]) / len(m["pct"]), 1),
               "rayons": round(sum(m["rayons"]) / len(m["rayons"]), 1), "cards": round(sum(m["cards"]) / len(m["cards"]), 1)}
        out[f"{situation} | {surface}"] = row
        print(f"{situation:<24} {surface:<10} {row['cards']:>6} {row['pertinence']:>10.0%} {row['first'] or '—':>9} {row['clicks']:>10.2f} "
              f"{row['pct']:>6.1f}% {row['rayons']:>6.1f}")
    if ARGS.json:
        Path(ARGS.json).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    store.close()


if __name__ == "__main__":
    main()
