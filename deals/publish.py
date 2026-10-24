"""Publication du catalogue du jour : calculé une fois après la collecte, écrit d'un bloc, lu ensuite sans calcul.

Pour chaque produit : la meilleure offre disponible et fraîche (prix relu il y a moins de 3 jours), le verdict de
judge.py (vraie remise, fausse remise ou pas de remise), depuis quand la remise court et jusqu'à quand l'enseigne la
déclare (montrés dans la fiche), la description (caractéristiques lues), la courbe du prix sur 90 jours, les offres
par enseigne, et, par
alternatives.py, jusqu'à trois produits comparables moins chers et trois produits comparables au prix le plus proche.
Le tout remplace l'ancien catalogue en une transaction : l'app passe d'un catalogue complet au suivant, jamais un état
intermédiaire.
"""
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .alternatives import pick
from .catalog import haystack, specs
from .extract import attributes
from .extract.categories import FAMILY_OF
from .judge import LOOKBACK, judge

FRESH_S = 3 * 86400          # un prix non relu depuis 3 jours n'est plus montré comme disponible
CHART_DAYS = 90              # courbe de la fiche : meilleur prix de chaque jour, aujourd'hui compris


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


def publish(store, today, now):
    """Recalcule et remplace le catalogue publié. → statistiques de publication."""
    products = {r["id"]: r for r in store.q("SELECT id, title, brand, category, attributes FROM products")}
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
        verdict = None
        series = daily_best([intervals[o["id"]] for o in offs], today - timedelta(days=LOOKBACK), today)
        if best["availability"] != "out_of_stock":
            verdict = judge(best["price"], best["was"], [x for x in series if x[0] < today], today, best["lowest_30d"])
        p = products[pid]
        deal = bool(verdict and verdict.deal)
        fake = bool(verdict and not verdict.deal and verdict.reason.startswith("fausse"))
        prev = before.get(pid)
        deal_since = (prev["since"] if prev and prev["pct"] > 0 and prev["since"] else day) if deal else None
        ends = best["valid_until"] if deal and (best["valid_until"] or "") >= day else None
        stats["products"] += 1
        stats["deals"] += deal
        stats["verified"] += bool(deal and verdict.verified)
        stats["fake"] += fake
        stats["new"] += deal_since == day
        attrs = {**attributes(p["title"]), **json.loads(p["attributes"] or "{}")}
        catalog.append((pid, display_name(p["title"], p["brand"]), p["title"], p["brand"], p["category"], best["price"],
                        verdict.was if deal else None, verdict.pct if deal else 0, best_o["merchant"], best_o["id"],
                        int(bool(deal and verdict.verified)), haystack(p["title"], p["brand"], best_o["merchant"], p["category"]),
                        day, deal_since, ends, json.dumps(specs(attrs), ensure_ascii=False), chart(series, today),
                        json.dumps(attrs, ensure_ascii=False)))
        published.append({"id": pid, "category": p["category"], "family": FAMILY_OF.get(p["category"]), "brand": p["brand"],
                          "price": best["price"], "in_stock": best["availability"] != "out_of_stock", "attrs": attrs})

    by_cat = defaultdict(list)
    for item in published:
        if item["category"]:
            by_cat[item["category"]].append(item)
    cheaper_rows, similar = [], []
    for items in by_cat.values():
        for a in items:
            cheap, near = pick(a, items)
            cheaper_rows += [(a["id"], b["id"], rank) for rank, b in enumerate(cheap)]
            similar += [(a["id"], b["id"], rank) for rank, b in enumerate(near)]
    with store.tx() as c:
        c.execute("DELETE FROM catalog")
        c.execute("DELETE FROM catalog_offers")
        c.execute("DELETE FROM similar")
        c.execute("DELETE FROM alternatives")
        c.executemany("INSERT INTO catalog(product_id, name, title, brand, category, price, was, pct, merchant, offer_id, verified, "
                      "search, published_on, since, ends, specs, history, attrs) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", catalog)
        c.executemany("INSERT INTO catalog_offers(product_id, offer_id, merchant, price, was, pct, availability, rank) "
                      "VALUES (?,?,?,?,?,?,?,?)", catalog_offers)
        c.executemany("INSERT INTO similar(product_id, other_id, rank) VALUES (?,?,?)", similar)
        c.executemany("INSERT INTO alternatives(product_id, other_id, rank) VALUES (?,?,?)", cheaper_rows)
        c.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('published_at', ?)", (str(now),))
    return stats


def chart(series, today):
    """Courbe de la fiche : {"from": premier jour, "p": prix arrondi de chaque jour (None si aucun prix ce jour-là)}."""
    first = today - timedelta(days=CHART_DAYS - 1)
    by_day = {d: p for d, p in series if d >= first}
    return json.dumps({"from": first.isoformat(), "p": [round(by_day[first + timedelta(days=k)]) if first + timedelta(days=k) in by_day
                                                         else None for k in range(CHART_DAYS)]})
