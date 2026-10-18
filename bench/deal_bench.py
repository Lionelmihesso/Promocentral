"""Vérification des deals sur vérité connue : que laisse passer un fil qui se fie à la remise affichée, que laisse passer la vérification ?

Cas générés sur le marché simulé (prix « normal » connu) :
  gros deal réel        prix 30 à 50 % sous le prix normal, prix barré = prix normal
  promo modeste réelle  prix 10 à 20 % sous le prix normal (vraies promos du simulateur)
  prix barré gonflé     prix proche du normal ou −10 %, prix barré = normal × 1,3 à 1,7 (affiche −30 à −45 %)
Vérité : « gros deal » si la remise réelle vs prix normal ≥ 30 %.
Usage : python -m bench.deal_bench
"""
import random
from datetime import date, timedelta

from bench.market_sim import MOVING_CATALOG, Market, SimClock, SimFetcher
from radar.verify import verify
from listener.core import Listener


def run(days=320, seed=3):
    m = Market(start=date(2025, 6, 1), days=days, seed=seed, catalog=MOVING_CATALOG)
    ck = SimClock(m.start)
    L = Listener(fetcher=SimFetcher(m, ck), clock=ck, workers=1)
    for o in m.offers:
        L.track(o["url"], 2, o["merchant"])
    pid = {}
    rng = random.Random(seed)
    cases = []
    for k in range(days):
        ck.t = SimClock(m.start + timedelta(days=k)).t
        L.q("UPDATE offers SET next_check_at=0 WHERE status='active'")
        L.run_due(limit=10000)
        if not pid:
            for o in m.offers:
                pid[o["pid"]] = L.q("SELECT product_id FROM offers WHERE url=?", (o["url"],), one=True)["product_id"]
        if k < 120 or k % 5:
            continue
        today = L.today()
        for o in m.offers:
            s = L._snap.get(pid[o["pid"]])
            typ = (s or {}).get("intel", {}).get("reference_price")
            if not typ or s["intel"].get("state") == "UNKNOWN":
                continue
            n = o["normal"][k]
            kinds = []
            if o["kind"][k] == "true_promo" and o["stock"][k]:
                kinds.append(("promo_reelle", o["price"][k], o["list"][k] or n))
            if o["kind"][k] == "fake_promo":
                kinds.append(("prix_barre_gonfle", o["price"][k], o["list"][k]))
            if rng.random() < 0.08:
                d = rng.uniform(0.30, 0.50)
                kinds.append(("gros_deal_reel", round(n * (1 - d)), n))
            if rng.random() < 0.08:
                kinds.append(("prix_barre_gonfle", round(n * rng.uniform(0.9, 1.0)), round(n * rng.uniform(1.3, 1.7))))
            for kind, price, ref in kinds:
                if not ref or ref <= price:
                    continue
                v = verify(price, ref, [], today, typ)
                real = 1 - price / n
                cases.append({"kind": kind, "truth_big": real >= 0.30, "real": real, "shown": 1 - price / ref,
                              "naive": 1 - price / ref >= 0.30, "engine": v["verdict"] == "GROS_DEAL",
                              "verdict": v["verdict"]})
    return cases


def report(cases):
    def stats(key):
        tp = sum(c[key] and c["truth_big"] for c in cases)
        fp = sum(c[key] and not c["truth_big"] for c in cases)
        fn = sum(not c[key] and c["truth_big"] for c in cases)
        return tp, fp, fn, tp / (tp + fp) if tp + fp else 0, tp / (tp + fn) if tp + fn else 0
    print(f"\n{len(cases)} deals testés : " + ", ".join(f"{k} {sum(c['kind'] == k for c in cases)}"
                                                    for k in ("gros_deal_reel", "promo_reelle", "prix_barre_gonfle")))
    print("\nMise en vitrine « gros deal »      vrais   faux   ratés   précision   rappel")
    for name, key in (("Remise affichée ≥ 30 %", "naive"), ("Vérification vs prix du marché", "engine")):
        tp, fp, fn, p, r = stats(key)
        print(f"  {name:<33} {tp:>5} {fp:>6} {fn:>7}   {p:>8.1%} {r:>8.1%}")
    inflated = [c for c in cases if c["kind"] == "prix_barre_gonfle"]
    print(f"\nPrix barrés gonflés (affichent en moyenne −{sum(c['shown'] for c in inflated) / len(inflated) * 100:.0f} %) :")
    print(f"  mis en vitrine par la remise affichée : {sum(c['naive'] for c in inflated) / len(inflated):.0%}")
    print(f"  mis en vitrine après vérification     : {sum(c['engine'] for c in inflated) / len(inflated):.0%}")
    print(f"  signalés « remise gonflée »            : {sum(c['verdict'] == 'REMISE_GONFLEE' for c in inflated) / len(inflated):.0%}")
    misses = [c for c in cases if c["truth_big"] and not c["engine"]]
    if misses:
        print(f"  gros deals ratés : remise réelle {min(c['real'] for c in misses) * 100:.0f}–{max(c['real'] for c in misses) * 100:.0f} % "
              f"(seuil 30 % ; prix de marché du moteur plus bas que le prix normal du marchand)")


if __name__ == "__main__":
    report(run())
