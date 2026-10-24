"""Vraie ou fausse remise, mesurée de bout en bout contre une vérité connue.

Un an de marché simulé (deals/sim.py : promos des enseignes, Black Friday, soldes, fausses promos à prix gonflé,
hausses, ruptures), 30 produits × 3 enseignes, plusieurs tirages. Chaque nuit, la vraie chaîne tourne (collecte →
marché → publication), puis le catalogue publié est comparé à la vérité du jour : un produit est une OPPORTUNITÉ si
son meilleur prix en stock est à 92 % ou moins du meilleur prix normal du marché.

Sont comptés les jours où la meilleure offre en stock affiche un prix barré (sans prix barré, l'app ne montre pas de
remise, par conception) : vrais deals montrés, vrais deals cachés (→ rappel), remises montrées sans opportunité
réelle (→ précision). Le premier mois (démarrage, historique vide) est compté à part.

  python -m bench.deals_truth [--days 365] [--seeds 11 12 13]
"""
import argparse
import tempfile
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from deals import sim
from deals.collect.crawl import Crawler
from deals.demo import retailers
from deals.market import Market
from deals.publish import publish
from deals.store import Store

START = date(2025, 1, 6)
COLD_DAYS = 30


def run(seed, days, tmp):
    m = sim.Market(start=START, days=days, seed=seed)
    store = Store(Path(tmp, f"truth-{seed}.sqlite"))
    clock = sim.SimClock(START)
    market = Market(store, clock)
    crawler = Crawler(market, sim.SimFetcher(m, clock), retailers(sim.MERCHANTS), budget_s=10 ** 9, clock=clock)
    for o in m.offers:
        market.track(o["url"], sim.slug(o["merchant"]), o["merchant"])
    sim_id = {p["gtin"]: p["id"] for p in m.products}
    res = {"cold": Counter(), "warm": Counter()}
    for k in range(days):
        clock.set(START + timedelta(days=k))
        crawler.nightly()
        publish(store, market.today(), clock())
        rows = store.q("SELECT p.gtin, c.pct, c.verified, b.pct AS displayed, b.availability FROM catalog c "
                       "JOIN products p ON p.id=c.product_id JOIN catalog_offers b ON b.product_id=c.product_id AND b.rank=0")
        tally = res["cold" if k < COLD_DAYS else "warm"]
        for r in rows:
            if r["availability"] == "out_of_stock":
                continue
            opp = m.truth(sim_id[r["gtin"]], k)["opp"]
            if not r["displayed"]:
                tally["opportunité sans prix barré"] += opp
                continue
            shown = r["pct"] > 0
            tally["vrai deal montré" if shown and opp else "montré à tort" if shown else "vrai deal caché" if opp else "rien"] += 1
            tally["montré et confirmé par une preuve"] += shown and bool(r["verified"])
    store.close()
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--seeds", type=int, nargs="+", default=[11, 12, 13])
    a = ap.parse_args(argv)
    t0, tmp = time.time(), tempfile.mkdtemp()
    total = {"cold": Counter(), "warm": Counter()}
    for seed in a.seeds:
        for phase, tally in run(seed, a.days, tmp).items():
            total[phase].update(tally)
    print(f"{a.days} jours × {len(a.seeds)} tirages, chaîne complète ({time.time() - t0:.0f} s)")
    for phase, label in (("cold", f"démarrage ({COLD_DAYS} premiers jours)"), ("warm", "régime établi")):
        t = total[phase]
        tp, fn, fp = t["vrai deal montré"], t["vrai deal caché"], t["montré à tort"]
        print(f"  {label:30} rappel {tp / max(1, tp + fn):4.0%} ({tp} montrés, {fn} cachés) · précision {tp / max(1, tp + fp):4.0%} "
              f"({fp} à tort) · confirmés par une preuve {t['montré et confirmé par une preuve'] / max(1, tp + fp):4.0%} · "
              f"opportunités sans prix barré (invisibles) {t['opportunité sans prix barré']}")


if __name__ == "__main__":
    main()
