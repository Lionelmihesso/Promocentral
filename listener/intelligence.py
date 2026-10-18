"""Intelligence prix — fonctions pures, déterministes, testables. Aucune donnée inventée.

Entrée de base : une série quotidienne [(date, prix)] (jours sans observation valide absents).
"""
from bisect import bisect_left, bisect_right
from datetime import date, timedelta
from statistics import mean, median, pstdev

# Seuils configurables (percentiles de la fenêtre de référence)
DEFAULT = {
    "window_days": 90,          # fenêtre de référence pour l'état du prix
    "min_days": 14,             # en dessous : état UNKNOWN (pas assez d'historique)
    "exceptional_pct": 10, "good_pct": 30, "normal_pct": 70,
    "min_discount_vs_median": 0.05,   # un « bon prix » (par percentile) doit aussi être ≥ 5 % sous la médiane
    "regular_pct": 75,                # prix courant = 75e percentile de la fenêtre (robuste aux promotions fréquentes)
    "good_discount_vs_regular": 0.10, # ≥ 10 % sous le prix courant → GOOD même si la fenêtre contient des promos plus fortes
    "exceptional_discount_vs_regular": 0.20,
    "expensive_premium_vs_regular": 0.04,  # EXPENSIVE : percentile > 70 ET ≥ 4 % au-dessus du prix courant
}
STATES = ("EXCEPTIONAL", "GOOD", "NORMAL", "EXPENSIVE", "UNKNOWN")


def percentile_rank(values, x):
    """Rang percentile « mi-rang » de x dans values (0-100). Robuste aux prix en paliers (nombreux ex æquo)."""
    s = sorted(values)
    if not s:
        return None
    lo, hi = bisect_left(s, x), bisect_right(s, x)
    return round(100 * (lo + 0.5 * (hi - lo)) / len(s), 1)


def window(series, as_of, days):
    start = as_of - timedelta(days=days - 1)
    return [p for d, p in series if start <= d <= as_of]


def value_at(values, pct):
    """Valeur au percentile pct (rang le plus proche)."""
    s = sorted(values)
    return s[min(len(s) - 1, max(0, round(pct / 100 * len(s) + 0.5) - 1))] if s else None


def price_state(pct, vs_median, n_days, cfg=DEFAULT, vs_regular=None):
    """Déterministe. Deux lectures complémentaires :
    - position (percentile) dans la fenêtre : le prix est-il rare ?
    - écart au prix courant (p75) : le prix est-il nettement sous le niveau habituel hors promotions ?"""
    if pct is None or n_days < cfg["min_days"]:
        return "UNKNOWN"
    vr = vs_regular if vs_regular is not None else vs_median
    if (pct <= cfg["exceptional_pct"] and vs_median <= -cfg["min_discount_vs_median"]) or vr <= -cfg["exceptional_discount_vs_regular"]:
        return "EXCEPTIONAL"
    if (pct <= cfg["good_pct"] and vs_median <= -cfg["min_discount_vs_median"]) or vr <= -cfg["good_discount_vs_regular"]:
        return "GOOD"
    if pct > cfg["normal_pct"] and vr >= cfg["expensive_premium_vs_regular"]:
        return "EXPENSIVE"
    return "NORMAL"


def analyze(series, as_of, current=None, cfg=DEFAULT):
    """series : [(date, prix)] triée ; current : prix actuel (défaut = dernier point).

    → stats (min/médiane 7-365 j, moyenne, volatilité), position (percentile, écarts, jours depuis le plus bas), état.
    """
    series = [(d, p) for d, p in series if d <= as_of]
    if not series:
        return {"state": "UNKNOWN", "n_days": 0, "reason": "aucune observation"}
    cur = current if current is not None else series[-1][1]
    W = cfg["window_days"]
    w = {k: window(series, as_of, k) for k in (7, 30, 90, 365)}
    ref = window(series, as_of, W)
    st = {f"min_{k}": (min(v) if v else None) for k, v in w.items()}
    st.update({f"median_{k}": (median(v) if v else None) for k, v in w.items() if k != 7})
    st["mean_90"] = round(mean(w[90]), 2) if w[90] else None
    st["volatility_90"] = round(pstdev(w[90]) / mean(w[90]), 4) if len(w[90]) > 1 else 0.0
    med = median(ref)
    pct = percentile_rank(ref, cur)
    vs_med = (cur - med) / med
    low365 = st["min_365"]
    last_low = max((d for d, p in series if p == low365 and d >= as_of - timedelta(days=364)), default=None)
    regular = value_at(ref, cfg["regular_pct"])
    vs_reg = (cur - regular) / regular
    pos = {"percentile": pct, "window_days": W, "vs_median": round(vs_med, 4), "vs_regular": round(vs_reg, 4),
           "vs_low": round((cur - st[f"min_{W}"]) / st[f"min_{W}"], 4) if st.get(f"min_{W}") else None,
           "days_since_low_365": (as_of - last_low).days if last_low else None}
    n_days = len(ref)
    return {"current": cur, "n_days": n_days, "stats": st, "position": pos,
            "state": price_state(pct, vs_med, n_days, cfg, vs_reg), "reference_price": regular, "median_price": med}


def promotion(current, previous, list_price, position):
    """Trois notions distinctes (§10) :
    advertised  : remise affichée par le marchand (prix barré)
    observed    : baisse par rapport au prix précédemment observé
    historical  : position du prix dans l'historique (le seul vrai signal d'opportunité)
    """
    adv = round(1 - current / list_price, 4) if list_price and list_price > current else None
    obs = round(1 - current / previous, 4) if previous and previous > current else 0.0
    hist_pct = (position or {}).get("percentile")
    verdict = None
    if adv and adv >= 0.15 and hist_pct is not None and hist_pct > 30:
        verdict = "ADVERTISED_NOT_HISTORICAL"   # « -30 % » affiché, mais prix ordinaire au regard de l'historique
    return {"advertised_discount": adv, "observed_discount": obs, "historical_percentile": hist_pct,
            "assessment": verdict}


# ------------------------------------------------------------------ calendrier commercial FR
def retail_events(year):
    nov1 = date(year, 11, 1)
    bf = nov1 + timedelta(days=(4 - nov1.weekday()) % 7 + 21)
    jan1 = date(year, 1, 1)
    winter = jan1 + timedelta(days=(2 - jan1.weekday()) % 7 + 7)
    jun30 = date(year, 6, 30)
    summer = jun30 - timedelta(days=(jun30.weekday() - 2) % 7)
    return {"black_friday": (bf - timedelta(days=7), bf + timedelta(days=3)),
            "soldes_hiver": (winter, winter + timedelta(days=27)),
            "soldes_ete": (summer, summer + timedelta(days=27))}


def event_of(d):
    for name, (a, b) in retail_events(d.year).items():
        if a <= d <= b:
            return name
    return None


def days_to_next_event(d, horizon=60):
    best = None
    for y in (d.year, d.year + 1):
        for name, (a, _) in retail_events(y).items():
            if a >= d and (a - d).days <= horizon and (best is None or a < best[1]):
                best = (name, a)
    return ((best[1] - d).days, best[0]) if best else (None, None)


# ------------------------------------------------------------------ motifs promotionnels (§11)
def promo_days(series, threshold=0.10, lookback=90, min_prior=30):
    """Jours où le prix est ≥ threshold sous la médiane des `lookback` jours précédents."""
    out = []
    dates = [d for d, _ in series]
    prices = [p for _, p in series]
    for i, (d, p) in enumerate(series):
        j = bisect_left(dates, d - timedelta(days=lookback))
        prior = prices[j:i]
        if len(prior) < min_prior:
            continue
        m = median(prior)
        out.append((d, p <= m * (1 - threshold), round(1 - p / m, 4)))
    return out


def patterns(groups):
    """groups : {clé (catégorie, marque ou marchand) : [séries]}.
    → par clé : taux de jours en promo par mois et par événement commercial, profondeur moyenne, « lift » vs hors événement."""
    res = {}
    for key, series_list in groups.items():
        by_month, by_event, base = {}, {}, [0, 0, []]
        for s in series_list:
            for d, is_promo, depth in promo_days(s):
                m = by_month.setdefault(d.month, [0, 0, []])
                m[0] += 1
                m[1] += is_promo
                ev = event_of(d)
                bucket = by_event.setdefault(ev, [0, 0, []]) if ev else base
                bucket[0] += 1
                bucket[1] += is_promo
                if is_promo:
                    m[2].append(depth)
                    bucket[2].append(depth)
        if base[0] == 0 and not by_event:
            continue
        base_rate = base[1] / base[0] if base[0] else 0
        res[key] = {
            "observed_days": sum(v[0] for v in by_month.values()),
            "baseline_promo_rate": round(base_rate, 3),
            "by_event": {e: {"promo_rate": round(v[1] / v[0], 3), "lift": round((v[1] / v[0]) / base_rate, 1) if base_rate else None,
                             "avg_depth": round(mean(v[2]), 3) if v[2] else None, "days": v[0]} for e, v in by_event.items()},
            "by_month": {m: {"promo_rate": round(v[1] / v[0], 3), "avg_depth": round(mean(v[2]), 3) if v[2] else None}
                         for m, v in sorted(by_month.items())},
        }
    return res
