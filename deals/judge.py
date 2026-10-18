"""Vraie ou fausse remise — fonction pure, sans base ni réseau.

Une remise affichée par l'enseigne est crue, SAUF PREUVE du contraire. Preuves acceptées :
  1. notre historique du meilleur prix du produit AVANT l'épisode de prix en cours : au moins 14 jours observés sur
     les 90 précédents ; le prix habituel est leur 75e centile (robuste aux promotions fréquentes) ;
  2. la mention légale de la page « prix le plus bas des 30 derniers jours », donnée par l'enseigne elle-même ;
  3. un « prix barré » au même prix depuis 60 jours ou plus : ce n'est plus une remise, c'est le prix.
Fausse remise : la remise affichée dépasse la remise réelle de 10 points ou plus — sauf si la remise réelle atteint
30 % (un gros deal reste un gros deal). Sans preuve, la remise affichée est montrée.

Pourquoi « sauf preuve » : sans cette exigence, un produit sans historique a pour « prix habituel » son prix promo, et
toute remise de plus de 10 % passe pour fausse. Mesuré de bout en bout sur un an de marché simulé à vérité connue
(bench/deals_truth.py, 3 tirages) : le premier mois, 89 % des vrais deals montrés et 81 % de précision (ancienne
règle : 46 % et 75 %) ; ensuite 98 % et 90 % (ancienne règle : 98 % et 91 %).
Limite connue : une hausse artificielle qui dure plus du quart de l'historique observé avant la promotion déplace le
« prix habituel » (75e centile) ; la mention légale « plus bas 30 jours », quand la page la donne, couvre ce cas.
"""
from dataclasses import dataclass
from datetime import timedelta

FAKE_GAP = 0.10        # écart affichée − réelle qui fait une fausse remise
BIG = 0.30             # au-delà, gros deal même si l'affichage exagère
MIN_DAYS = 14          # jours observés hors épisode pour connaître le prix habituel
LOOKBACK = 90
PERMANENT = 60         # jours au même prix « barré » : c'est le prix
LEVEL = 0.01           # même épisode de prix : à 1 % près


PROOF = {"historique": "historique", "plus bas 30 jours affiché": "plus_bas_30j", "prix barré permanent": "permanent"}


@dataclass(frozen=True)
class Verdict:
    deal: bool
    pct: int = 0                 # remise montrée, en %
    was: float | None = None     # prix barré montré
    verified: bool = False       # confrontée à une preuve
    reason: str = ""
    ref: float | None = None     # prix de référence de la preuve retenue (prix habituel relevé, plus bas 30 jours affiché)
    proof: str = ""              # historique | plus_bas_30j | permanent ; vide sans preuve


def episode_start(history, price, today):
    """Premier jour de l'épisode de prix en cours (jours consécutifs au prix actuel ou en dessous)."""
    start = today
    for d, p in reversed(history):
        if p > price * (1 + LEVEL):
            break
        start = d
    return start


def usual_price(history, start):
    """Prix habituel avant l'épisode : 75e centile des jours observés sur les 90 précédents, s'il y en a au moins 14."""
    before = sorted(p for d, p in history if start - timedelta(days=LOOKBACK) <= d < start)
    if len(before) < MIN_DAYS:
        return None
    return before[min(len(before) - 1, max(0, round(0.75 * len(before) + 0.5) - 1))]


def judge(price, was, history, today, lowest_30d=None):
    """price : meilleur prix disponible aujourd'hui ; was : prix barré de cette offre ; history : [(jour, meilleur prix)]
    observés AVANT aujourd'hui ; lowest_30d : mention légale relevée sur la page."""
    if not price or not was or was <= price * 1.01:
        return Verdict(False, reason="pas de prix barré")
    displayed = 1 - price / was
    start = episode_start(history, price, today)
    evidence = []
    if (today - start).days >= PERMANENT:
        evidence.append(("prix barré permanent", price))
    else:
        usual = usual_price(history, start)
        if usual:
            evidence.append(("historique", usual))
    if lowest_30d:
        evidence.append(("plus bas 30 jours affiché", lowest_30d))
    if not evidence:
        return Verdict(True, round(displayed * 100), was, False, "remise de l'enseigne, sans preuve contraire")
    real, source, ref = min((1 - price / ref, name, ref) for name, ref in evidence)
    if displayed - max(real, 0) >= FAKE_GAP and real < BIG:
        return Verdict(False, reason=f"fausse remise : affichée {displayed:.0%}, réelle {max(real, 0):.0%} ({source})",
                       ref=ref, proof=PROOF[source])
    return Verdict(True, round(displayed * 100), was, True, f"remise confirmée ({source})", ref=ref, proof=PROOF[source])
