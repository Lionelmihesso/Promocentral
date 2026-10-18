"""Signaux de marché : interprétations déterministes des faits. Pas des recommandations utilisateur.

Entrée : un « instantané produit » construit par le moteur (intelligence produit + par offre + événements récents).
Sortie : liste de signaux lisibles par machine, chacun avec prix de référence, percentile, confiance et raisons.
"""
from .intelligence import days_to_next_event

CFG = {
    "emerging_window_h": 72, "emerging_min_offers": 2, "emerging_min_drop": 0.05,
    "wide_min_offers": 2, "wide_max_pct": 20, "wide_min_discount": 0.05,
    "high_min_premium": 0.05,
    "scarcity_drop_ratio": 0.5,
}


def confidence(snap):
    """0..1, déterministe : profondeur d'historique, nombre de marchands, fiabilité d'extraction, conflits."""
    n = snap["intel"].get("n_days", 0)
    depth = min(1.0, n / 60)
    merchants = min(snap.get("offers_in_stock", 0), 3) / 3
    extraction = snap.get("extraction_confidence", 0.8)
    c = 0.5 * depth + 0.2 * merchants + 0.3 * extraction
    if snap.get("quality") == "CONFLICTING":
        c *= 0.6
    return round(c, 2)


def _fmt(x):
    return f"{x:,.0f} €".replace(",", " ")


def evaluate(snap, cfg=CFG):
    intel = snap["intel"]
    if intel.get("state") in (None, "UNKNOWN") or snap.get("quality") == "SUSPECT":
        return []
    pos, cur, ref = intel["position"], intel["current"], intel["reference_price"]
    base = {"product_id": snap["product_id"], "current_price": cur, "current_merchant": snap.get("merchant"),
            "reference_price": ref, "median_price": intel.get("median_price"), "discount": round(-pos["vs_regular"], 4),
            "historical_percentile": pos["percentile"], "confidence": confidence(snap),
            "price_state": intel["state"], "window_days": pos["window_days"], "facts_days": intel["n_days"]}
    out = []

    if intel["state"] in ("EXCEPTIONAL", "GOOD"):
        r = [f"{-pos['vs_regular'] * 100:.0f} % sous le prix courant ({_fmt(ref)}, hors promotions, {pos['window_days']} j)",
             f"{pos['percentile']:.0f}e percentile des {pos['window_days']} derniers jours"]
        if pos.get("vs_low") is not None and pos["vs_low"] <= 0.02:
            r.append("au niveau du plus bas observé sur la période")
        promo = snap.get("promotion") or {}
        if promo.get("advertised_discount"):
            r.append(f"remise affichée {promo['advertised_discount'] * 100:.0f} %")
        out.append({**base, "type": "PRICE_OPPORTUNITY", "reasons": r})

    if intel["state"] == "EXPENSIVE" and pos["vs_regular"] >= cfg["high_min_premium"]:
        r = [f"{pos['vs_regular'] * 100:.0f} % au-dessus du prix courant ({_fmt(ref)})",
             f"{pos['percentile']:.0f}e percentile des {pos['window_days']} derniers jours"]
        n, ev = days_to_next_event(snap["as_of"])
        if n is not None:
            r.append(f"{ev.replace('_', ' ')} dans {n} j")
        out.append({**base, "type": "PRICE_HIGH", "reasons": r})

    drops = snap.get("recent_drops", {})  # offer_id -> baisse max sur la fenêtre
    movers = [o for o, d in drops.items() if d >= cfg["emerging_min_drop"]]
    if len(movers) >= cfg["emerging_min_offers"]:
        out.append({**base, "type": "EMERGING_PROMOTION",
                    "reasons": [f"{len(movers)} marchands ont baissé leur prix d'au moins {cfg['emerging_min_drop'] * 100:.0f} % en {cfg['emerging_window_h']} h"]})

    lows = [o for o in snap.get("offers", []) if o["availability"] == "in_stock" and o.get("percentile") is not None
            and o["percentile"] <= cfg["wide_max_pct"] and (o.get("vs_median") or 0) <= -cfg["wide_min_discount"]]
    if len(lows) >= cfg["wide_min_offers"]:
        out.append({**base, "type": "MARKET_WIDE_OPPORTUNITY",
                    "reasons": [f"{len(lows)} offres simultanément près de leur plus bas historique : "
                                + ", ".join(f"{o['merchant']} {_fmt(o['price'])}" for o in lows)]})

    was, now = snap.get("in_stock_7d_ago"), snap.get("offers_in_stock", 0)
    if intel["state"] in ("EXCEPTIONAL", "GOOD") and was and was >= 2 and now <= max(1, was * cfg["scarcity_drop_ratio"]):
        out.append({**base, "type": "SCARCITY",
                    "reasons": [f"prix attractif mais disponibilité en baisse : {now} marchand(s) en stock contre {was} il y a 7 jours"]})
    return out


# ------------------------------------------------------------------ surveillances par condition (§14)
def product_matches(watch, product, current_price):
    """Le produit entre-t-il dans le périmètre de la surveillance ? (contraintes dures)"""
    c = watch.get("constraints", {})
    if watch.get("category") and product.get("category") != watch["category"]:
        return False
    if watch.get("product_id") and product["id"] != watch["product_id"]:
        return False
    if c.get("brands") and (product.get("brand") or "").lower() not in {b.lower() for b in c["brands"]}:
        return False
    attrs = product.get("attributes") or {}
    for k, v in (c.get("attributes") or {}).items():
        if isinstance(v, dict):  # {"max": 44} / {"min": 12}
            a = attrs.get(k)
            if a is None or ("max" in v and a > v["max"]) or ("min" in v and a < v["min"]):
                return False
        elif str(attrs.get(k, "")).upper() != str(v).upper():
            return False
    if c.get("energy_class"):
        order = "ABCDEFG"
        e = attrs.get("energy_class")
        if not e or order.index(e) > order.index(c["energy_class"].upper()):
            return False
    if c.get("budget_max") and current_price is not None and current_price > c["budget_max"]:
        return False
    return True


def condition_met(watch, snap, signal_types):
    """Condition de marché : target | acceptable | opportunity | any_good_state."""
    cur = snap["intel"].get("current")
    cond = watch.get("condition", "opportunity")
    if cur is None:
        return False, None
    if cond == "target":
        ok = watch.get("target_price") is not None and cur <= watch["target_price"]
        return ok, f"prix {_fmt(cur)} ≤ cible {_fmt(watch.get('target_price') or 0)}" if ok else None
    if cond == "acceptable":
        lim = watch.get("acceptable_price") or watch.get("target_price")
        ok = lim is not None and cur <= lim
        return ok, f"prix {_fmt(cur)} ≤ acceptable {_fmt(lim or 0)}" if ok else None
    if cond == "any_good_state":
        ok = snap["intel"].get("state") in ("GOOD", "EXCEPTIONAL")
        return ok, f"état du prix {snap['intel'].get('state')}" if ok else None
    # opportunity : signal d'opportunité ET (si fourni) prix ≤ acceptable ; OU prix ≤ cible quoi qu'il arrive
    if watch.get("target_price") is not None and cur <= watch["target_price"]:
        return True, f"prix {_fmt(cur)} ≤ cible {_fmt(watch['target_price'])}"
    lim = watch.get("acceptable_price")
    ok = bool({"PRICE_OPPORTUNITY", "MARKET_WIDE_OPPORTUNITY"} & signal_types) and (lim is None or cur <= lim)
    return ok, "opportunité de marché" + (f" et prix ≤ {_fmt(lim)}" if lim else "") if ok else None
