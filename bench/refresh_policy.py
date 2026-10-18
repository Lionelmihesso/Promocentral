"""Coût de collecte et événements ratés : tout relire chaque jour vs fréquence adaptative (plafond : 1 fois par jour).

Marché simulé sur un an (vérité connue). Pour chaque produit et chaque jour, le meilleur prix en stock.
Épisodes mesurés :
  prix cible atteint   produits suivis (20 %), cible = 88 % du prix normal
  bonne affaire        meilleur prix ≤ 85 % du prix normal, produits des catégories suivies (centres d'intérêt)
  bonne affaire        idem, autres produits (découverte)
Politique adaptative : suivi → chaque jour ; centre d'intérêt → tous les 3 jours ; reste → chaque semaine ;
un produit où une bonne affaire vient d'être vue passe en quotidien pendant 3 jours.
Usage : python -m bench.refresh_policy
"""
import random
from collections import defaultdict
from datetime import date
from statistics import mean

from bench.market_sim import MOVING_CATALOG, Market


def run(seed=3, days=365):
    m = Market(start=date(2025, 1, 1), days=days, seed=seed, catalog=MOVING_CATALOG)
    rng = random.Random(seed)
    prods = m.products
    offers = defaultdict(list)
    for o in m.offers:
        offers[o["pid"]].append(o)
    watched = {p["id"] for p in rng.sample(prods, max(1, len(prods) // 5))}
    cats = sorted({p["category"] for p in prods})
    followed_cats = set(rng.sample(cats, 3))
    interest = {p["id"] for p in prods if p["category"] in followed_cats} - watched
    best = {p["id"]: [min([o["price"][k] for o in offers[p["id"]] if o["stock"][k]] or [None], key=lambda v: v if v is not None else 1e9) for k in range(days)] for p in prods}
    normal = {p["id"]: [min(o["normal"][k] for o in offers[p["id"]]) for k in range(days)] for p in prods}

    def episodes(pid, cond):
        out, start = [], None
        for k in range(days):
            ok = best[pid][k] is not None and cond(pid, k)
            if ok and start is None:
                start = k
            if not ok and start is not None:
                out.append((start, k - 1)); start = None
        if start is not None:
            out.append((start, days - 1))
        return out
    target = lambda pid, k: best[pid][k] <= normal[pid][k] * 0.88
    deal = lambda pid, k: best[pid][k] <= normal[pid][k] * 0.85

    def simulate(policy):
        checked = defaultdict(set)                 # produit → jours relus
        hot_until = {}
        requests = 0
        for k in range(days):
            for p in prods:
                pid = p["id"]
                if policy == "daily":
                    period = 1
                else:
                    period = 1 if pid in watched or hot_until.get(pid, -1) >= k else 3 if pid in interest else 7
                if (k + pid) % period == 0:
                    checked[pid].add(k)
                    requests += len(offers[pid])
                    if best[pid][k] is not None and deal(pid, k):
                        hot_until[pid] = k + 3
        def score(pids, cond):
            delays, missed, n = [], 0, 0
            for pid in pids:
                for a, b in episodes(pid, cond):
                    n += 1
                    seen = [d for d in checked[pid] if a <= d <= b]
                    if seen:
                        delays.append(min(seen) - a)
                    else:
                        missed += 1
            return {"episodes": n, "missed": missed, "missed_pct": round(missed / n * 100, 1) if n else 0,
                    "mean_delay_days": round(mean(delays), 2) if delays else 0}
        others = {p["id"] for p in prods} - watched - interest
        return {"requests_per_day": round(requests / days), "target": score(watched, target), "interest": score(interest, deal), "other": score(others, deal)}
    return {"products": len(prods), "offers": len(m.offers), "daily": simulate("daily"), "adaptive": simulate("adaptive")}


if __name__ == "__main__":
    for seed in (3, 7):
        r = run(seed)
        d, a = r["daily"], r["adaptive"]
        print(f"\nTirage {seed} — {r['products']} produits, {r['offers']} offres, 365 jours")
        print(f"  requêtes par jour            : tout chaque jour {d['requests_per_day']}  ·  adaptatif {a['requests_per_day']} "
              f"({(1 - a['requests_per_day'] / d['requests_per_day']) * 100:.0f} % de moins)")
        for k, label in (("target", "prix cible atteint (suivis)"), ("interest", "bonne affaire, centre d'intérêt"), ("other", "bonne affaire, découverte")):
            print(f"  {label:<32}: {a[k]['episodes']} épisodes · ratés {d[k]['missed_pct']} % → {a[k]['missed_pct']} % · "
                  f"délai moyen {d[k]['mean_delay_days']} j → {a[k]['mean_delay_days']} j")
