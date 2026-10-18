"""Vérification d'un deal : est-ce vraiment un gros deal ? Déterministe, explicable, sans LLM.

Trois prix distincts (repris du moteur de marché §10) :
  prix barré affiché    ce que l'enseigne annonce (« 589 € »)
  prix du marché        ce que le même produit coûte ailleurs / habituellement (médiane des prix constatés récents)
  plus bas connu        le prix le plus bas déjà observé
Verdicts :
  GROS_DEAL          ≥ 30 % sous le prix du marché → mis en vitrine
  BON_DEAL           15 à 30 % sous le prix du marché → visible, pas en vitrine
  REMISE_GONFLEE     la remise affichée est ≥ 10 points plus forte que la remise réelle (prix barré au-dessus du marché)
  PAS_UN_DEAL        < 15 % sous le prix du marché
  NON_VERIFIE        pas assez de prix de marché pour juger (≥ 1 source récente requise)
"""
from datetime import date, timedelta
from statistics import median

CFG = {"big": 0.30, "good": 0.15, "inflation_gap": 0.10, "recent_days": 45, "lowest_margin": 0.03}


def _fmt(x):
    return f"{x:,.0f}".replace(",", "\u202f") + " €" if abs(x - round(x)) < 0.005 else f"{x:,.2f}".replace(",", "\u202f").replace(".", ",") + " €"


def verify(price, displayed_ref, facts, today, typical=None, cfg=CFG):
    """facts : [{price, observed_on (iso), seller, source_url, kind: 'current'|'promo'}] hors deal lui-même.
    typical : prix courant calculé par le moteur de marché si le produit est suivi (prioritaire).
    → {verdict, real_discount, displayed_discount, market_price, lowest_known, badges[], headline, details[]}"""
    recent = [f for f in facts if f.get("kind", "current") == "current"
              and date.fromisoformat(f["observed_on"]) >= today - timedelta(days=cfg["recent_days"])]
    market = typical or (median(f["price"] for f in recent) if recent else None)
    shown = (1 - price / displayed_ref) if displayed_ref and displayed_ref > price else None
    lows = [f for f in facts if f["price"] > 0]
    lowest = min(lows, key=lambda f: f["price"]) if lows else None
    out = {"market_price": round(market, 2) if market else None, "displayed_discount": round(shown, 4) if shown else None,
           "lowest_known": lowest, "sources": len({f.get("seller") for f in recent}), "badges": [], "details": []}
    if not market:
        return {**out, "verdict": "NON_VERIFIE", "real_discount": None,
                "headline": "Prix du marché inconnu : remise non vérifiée",
                "details": ["Aucun prix récent du même produit ailleurs"]}
    real = 1 - price / market
    out["real_discount"] = round(real, 4)
    out["details"].append(f"Prix du marché : {_fmt(market)} ({out['sources'] or 'historique'} source{'s' if out['sources'] > 1 else ''})")
    if shown is not None:
        out["details"].append(f"Remise affichée : −{shown * 100:.0f} % (prix barré {_fmt(displayed_ref)})")
    inflated = shown is not None and shown - max(real, 0) >= cfg["inflation_gap"]
    if lowest and lowest["price"] < price * (1 - cfg["lowest_margin"]):
        out["badges"].append("DEJA_VU_MOINS_CHER")
        out["details"].append(f"Déjà vu à {_fmt(lowest['price'])} ({lowest.get('seller', '')}, {lowest['observed_on'][:7]})")
    elif lowest:
        out["badges"].append("PLUS_BAS_CONNU")
    if real >= cfg["big"]:
        verdict, head = "GROS_DEAL", f"−{real * 100:.0f} % sous le prix du marché"
    elif real >= cfg["good"]:
        verdict, head = "BON_DEAL", f"−{real * 100:.0f} % sous le prix du marché"
    else:
        verdict, head = "PAS_UN_DEAL", ("Prix proche du marché" if real > -0.02 else "Plus cher que le marché")
    if inflated and verdict != "GROS_DEAL":
        verdict, head = "REMISE_GONFLEE", f"Remise affichée −{shown * 100:.0f} %, réelle −{max(real, 0) * 100:.0f} %"
    elif inflated:
        out["badges"].append("PRIX_BARRE_GONFLE")
    return {**out, "verdict": verdict, "headline": head}
