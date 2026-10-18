"""Publication du catalogue du jour : calculé une fois après la collecte, écrit d'un bloc, lu ensuite sans calcul.

Pour chaque produit : la meilleure offre disponible et fraîche (prix relu il y a moins de 3 jours), le verdict de
judge.py (vraie remise, fausse remise ou pas de remise) et sa preuve, les offres par enseigne, trois produits similaires
(même catégorie, caractéristiques proches ; à défaut, prix le plus proche). Et ce qui fait revenir : depuis quand la
remise court (nouvelle depuis la publication d'hier ?), quand l'enseigne dit qu'elle finit, depuis combien de jours le
prix n'avait pas été aussi bas. Le tout remplace l'ancien catalogue en une transaction : l'app passe d'un catalogue
complet au suivant, jamais un état intermédiaire.
"""
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .catalog import haystack
from .judge import LOOKBACK, judge

FRESH_S = 3 * 86400          # un prix non relu depuis 3 jours n'est plus montré comme disponible
SIMILAR = 3
SIMILAR_MIN = 0.5
ENERGY = "ABCDEFG"


def day_start(d):
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()


def display_name(title, brand):
    """Le titre sans la marque (affichée à part) : « Lave-linge 7 kg Kessler classe C » → « Lave-linge 7 kg classe C »."""
    if not brand:
        return title
    name = re.sub(rf"(?<!\w){re.escape(brand)}(?!\w)", " ", title or "", flags=re.I)
    name = re.sub(r"\s{2,}", " ", name).strip(" -–·,")
    return name or title


def daily_best(offer_intervals, first, last):
    """Meilleur prix disponible de chaque jour [first, last], toutes offres confondues.
    offer_intervals : pour chaque offre, ses lignes de prix (first_seen, last_seen, price, availability) triées."""
    out, ptr, cur, d = [], [0] * len(offer_intervals), [None] * len(offer_intervals), first
    while d <= last:
        sod = day_start(d)
        best = None
        for i, rows in enumerate(offer_intervals):
            while ptr[i] < len(rows) and rows[ptr[i]]["first_seen"] <= sod + 86399:
                cur[i] = rows[ptr[i]]
                ptr[i] += 1
            r = cur[i]
            if r and r["last_seen"] >= sod - FRESH_S and r["availability"] != "out_of_stock":
                best = r["price"] if best is None else min(best, r["price"])
        if best is not None:
            out.append((d, best))
        d += timedelta(days=1)
    return out


def low_days(history, price, today):
    """Le prix du jour est le plus bas relevé depuis n jours (0 : un prix plus bas a été relevé la veille)."""
    n = 0
    for d, p in reversed(history):
        if p < price - 0.005:
            break
        n = (today - d).days
    return n


def similarity(a, b):
    """Similarité déterministe sur les caractéristiques ; même catégorie obligatoire."""
    if not a["category"] or a["category"] != b["category"]:
        return 0.0
    A, B = a["attributes"], b["attributes"]
    keys = set(A) & set(B)
    if not keys:
        return 0.6 if a["brand"] == b["brand"] else 0.55
    diffs = []
    for k in keys:
        x, y = A[k], B[k]
        if k == "energy_class":
            diffs.append(min(1, abs(ENERGY.index(x) - ENERGY.index(y)) / 3) if x in ENERGY and y in ENERGY else 1)
        elif isinstance(x, (int, float)) and isinstance(y, (int, float)):
            diffs.append(min(1, abs(x - y) / max(abs(x), abs(y), 1e-9)))
        else:
            diffs.append(0 if x == y else 1)
    return round(min(0.99, (1 - sum(diffs) / len(diffs)) * 0.95 + (0.05 if a["brand"] == b["brand"] else 0)), 3)


def _similar(items):
    """items : produits publiés d'une catégorie → {produit: [3 similaires]}."""
    out = {}
    for a in items:
        scored = sorted(((similarity(a, b), b["id"]) for b in items if b["id"] != a["id"]), key=lambda x: (-x[0], x[1]))
        picks = [i for s, i in scored if s >= SIMILAR_MIN][:SIMILAR]
        if len(picks) < SIMILAR:                       # à défaut : même catégorie, prix le plus proche
            rest = sorted((b for b in items if b["id"] != a["id"] and b["id"] not in picks), key=lambda b: (abs(b["price"] - a["price"]), b["id"]))
            picks += [b["id"] for b in rest[:SIMILAR - len(picks)]]
        out[a["id"]] = picks
    return out


def publish(store, today, now):
    """Recalcule et remplace le catalogue publié. → statistiques de publication."""
    products = {r["id"]: r for r in store.q("SELECT id, title, brand, category, attributes, created_at FROM products")}
    before = {r["product_id"]: r for r in store.q("SELECT product_id, pct, since FROM catalog")}
    offers = store.q("SELECT id, product_id, merchant FROM offers WHERE product_id IS NOT NULL AND status NOT IN ('gone', 'out_of_scope')")
    since = day_start(today - timedelta(days=LOOKBACK + 1)) - FRESH_S
    intervals = defaultdict(list)
    for r in store.q("SELECT offer_id, first_seen, last_seen, price, was, availability, lowest_30d, valid_until FROM prices "
                     "WHERE last_seen >= ? ORDER BY offer_id, first_seen, id", (since,)):
        intervals[r["offer_id"]].append(r)
    by_product = defaultdict(list)
    for o in offers:
        if intervals.get(o["id"]):
            by_product[o["product_id"]].append(o)

    catalog, catalog_offers, published = [], [], []
    stats = {"products": 0, "deals": 0, "verified": 0, "fake": 0, "new": 0}
    day = today.isoformat()
    for pid, offs in sorted(by_product.items()):
        fresh = [(o, intervals[o["id"]][-1]) for o in offs if intervals[o["id"]][-1]["last_seen"] >= now - FRESH_S]
        if not fresh:
            continue
        fresh.sort(key=lambda x: (x[1]["availability"] == "out_of_stock", x[1]["price"], x[0]["id"]))
        for rank, (o, r) in enumerate(fresh):
            pct = round((1 - r["price"] / r["was"]) * 100) if r["was"] and r["was"] > r["price"] else 0
            catalog_offers.append((pid, o["id"], o["merchant"], r["price"], r["was"] if pct else None, pct, r["availability"], rank))
        best_o, best = fresh[0]
        verdict, history = None, []
        if best["availability"] != "out_of_stock":
            history = daily_best([intervals[o["id"]] for o in offs], today - timedelta(days=LOOKBACK), today - timedelta(days=1))
            verdict = judge(best["price"], best["was"], history, today, best["lowest_30d"])
        p = products[pid]
        deal = bool(verdict and verdict.deal)
        fake = bool(verdict and not verdict.deal and verdict.reason.startswith("fausse"))
        prev = before.get(pid)
        since = ((prev["since"] if prev and prev["pct"] > 0 and prev["since"] else day) if deal else None)
        ends = best["valid_until"] if deal and (best["valid_until"] or "") >= day else None
        tracked = max(0, (today - datetime.fromtimestamp(p["created_at"], timezone.utc).date()).days)
        stats["products"] += 1
        stats["deals"] += deal
        stats["verified"] += bool(deal and verdict.verified)
        stats["fake"] += fake
        stats["new"] += since == day
        catalog.append((pid, display_name(p["title"], p["brand"]), p["title"], p["brand"], p["category"], best["price"],
                        verdict.was if deal else None, verdict.pct if deal else 0, best_o["merchant"], best_o["id"],
                        int(bool(deal and verdict.verified)), haystack(p["title"], p["brand"], best_o["merchant"], p["category"]),
                        day, since, ends, low_days(history, best["price"], today) if verdict else 0,
                        verdict.ref if verdict and (deal or fake) else None, (verdict.proof or None) if verdict and (deal or fake) else None,
                        int(fake), len(fresh), tracked))
        published.append({"id": pid, "category": p["category"], "brand": p["brand"], "price": best["price"],
                          "attributes": json.loads(p["attributes"] or "{}")})

    by_cat = defaultdict(list)
    for item in published:
        if item["category"]:
            by_cat[item["category"]].append(item)
    similar = [(pid, other, rank) for items in by_cat.values() for pid, picks in _similar(items).items() for rank, other in enumerate(picks)]
    with store.tx() as c:
        c.execute("DELETE FROM catalog")
        c.execute("DELETE FROM catalog_offers")
        c.execute("DELETE FROM similar")
        c.executemany("INSERT INTO catalog(product_id, name, title, brand, category, price, was, pct, merchant, offer_id, verified, "
                      "search, published_on, since, ends, low_days, usual, proof, fake, n_offers, tracked) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", catalog)
        c.executemany("INSERT INTO catalog_offers(product_id, offer_id, merchant, price, was, pct, availability, rank) "
                      "VALUES (?,?,?,?,?,?,?,?)", catalog_offers)
        c.executemany("INSERT INTO similar(product_id, other_id, rank) VALUES (?,?,?)", similar)
    return stats
