"""Alternatives — fonction pure : pour le produit regardé, des produits comparables, et ceux qui coûtent moins cher.

Comparable (ce qu'un acheteur attend d'un remplaçant), d'après l'ontologie du rayon (deals/ontology) et les mesures :
  - même catégorie (une console : de la même marque, ses jeux sont les siens) ; même type, ni plus ni moins (un téléviseur OLED, un canapé d'angle, un matelas latex ne sont
    remplacés que par un produit du même type ; un produit dont l'offre ne dit pas le type, que par un autre qui ne le
    dit pas : un canapé convertible n'est pas remplacé par un canapé d'angle) ;
  - ce que l'offre dit (ou ce que le type est par définition), selon l'attribut : oui est un plus (sans fil, No Frost,
    convertible, 5G, réduction de bruit…) — il le faut aussi ; une forme (sans sac, portes coulissantes) — la même ; oui
    est un moins (une console en édition numérique, sans lecteur) — seulement à la place d'une autre qui l'est ;
  - même usage : même taille d'écran à 5 % près (un téléviseur 55 pouces n'est remplacé que par un 55 pouces) ; même
    taille de literie ; largeur à 6 % près en électroménager (l'encastrement), à 20 % près en ameublement ; places à une
    près ;
  - pas moins bien : classe énergie au plus une lettre en dessous ; capacité, couverts, foyers, tiroirs au plus un de
    moins ; volume au plus 15 % de moins ; stockage, mémoire vive, fréquence d'écran au moins autant ; autonomie au moins
    les deux tiers ; bruit au plus 3 dB de plus.
Une mesure inconnue chez le candidat ne l'écarte que si elle dit l'usage (écran, taille, largeur, places).
Moins cher : au moins 10 % sous le prix du produit regardé, disponible. Classement : la plus forte économie d'abord, une
marque différente par ligne tant que c'est possible.

Un produit : dict(id, category, family, brand, price, in_stock, attrs) — attrs = extract.attributes(titre) complété des
caractéristiques déclarées.
"""
from . import ontology

CHEAPER = 0.90
COUNT = 3
WIDTH_TOLERANCE = {"ameublement": 0.20}          # sinon 6 % : un appareil s'encastre au centimètre près
SCREEN_TOLERANCE = 0.05
SAME_BRAND = {"console"}                         # les jeux d'une console sont ceux de sa marque
NOT_FEWER = {"capacity_kg": 1, "place_settings": 1, "zones": 1, "drawers": 1}
AT_LEAST = ("storage_gb", "ram_gb", "refresh_hz")


def energy_rank(c):
    """Classe énergie → rang comparable : A+++ = -3, A+ = -1, A = 0, B = 1 … G = 6 ; None si inconnue."""
    return "ABCDEFG".index(c[0]) - c.count("+") if c and c[0] in "ABCDEFG" else None


def _known(x):
    """Ce qui compte pour comparer un produit, lu une fois (la nuit, chaque produit est comparé à tous ceux de son rayon) :
    son rayon (domaine), sa marque, son type, ce que ses attributs oui/non exigent d'un remplaçant — oui est un plus :
    ceux qu'il a ; une forme : celles qu'il a dites ; oui est un moins : ceux qu'il a —, son rang énergie."""
    k = x.get("_known")
    if k is None:
        a, d = x["attrs"], ontology.domain_of(x["category"])
        f = d.facts(a) if d else {}
        mode = (lambda key: d.attrs[key].get("compare", "more")) if d else None
        more = frozenset(key for key, v in f.items() if v is True and mode(key) == "more")
        same = tuple((key, v) for key, v in f.items() if mode(key) == "same")
        less = frozenset(key for key, v in f.items() if v is True and mode(key) == "less")
        k = x["_known"] = (d, (x.get("brand") or "").lower(), a.get("sub"), f, more, same, less, energy_rank(a.get("energy_class")))
    return k


def comparable(a, b):
    """b peut-il remplacer a ?"""
    if a["id"] == b["id"] or not a["category"] or a["category"] != b["category"]:
        return False
    ka, kb = a.get("_known") or _known(a), b.get("_known") or _known(b)
    if ka[0] is not None:                              # son ontologie : le même type, ce que ses attributs exigent
        if ka[2] != kb[2] or not ka[4] <= kb[4] or not kb[6] <= ka[6]:
            return False
        for key, v in ka[5]:
            if kb[3].get(key) != v:
                return False
    if a["category"] in SAME_BRAND and ka[1] != kb[1]:
        return False
    A, B = a["attrs"], b["attrs"]
    if "screen_in" in A and ("screen_in" not in B or abs(B["screen_in"] - A["screen_in"]) > SCREEN_TOLERANCE * A["screen_in"]):
        return False
    if "bed_size" in A and B.get("bed_size") != A["bed_size"]:
        return False
    if "width_cm" in A:
        tol = WIDTH_TOLERANCE.get(a.get("family"), 0.06)
        if "width_cm" not in B or abs(B["width_cm"] - A["width_cm"]) > tol * A["width_cm"]:
            return False
    if "seats" in A and ("seats" not in B or abs(B["seats"] - A["seats"]) > 1):
        return False
    for k, n in NOT_FEWER.items():
        if k in A and k in B and B[k] < A[k] - n:
            return False
    for k in AT_LEAST:
        if k in A and k in B and B[k] < A[k]:
            return False
    if "volume_l" in A and "volume_l" in B and B["volume_l"] < 0.85 * A["volume_l"]:
        return False
    if "autonomy_min" in A and "autonomy_min" in B and B["autonomy_min"] < A["autonomy_min"] * 2 / 3:
        return False
    if "noise_db" in A and "noise_db" in B and B["noise_db"] > A["noise_db"] + 3:
        return False
    ea, eb = ka[7], kb[7]
    if ea is not None and eb is not None and eb > ea + 1:
        return False
    return True


def groups(items):
    """Les produits qui peuvent se remplacer, ensemble : même rayon et, quand il a son ontologie, même type (la nuit, chacun
    n'est comparé qu'à ceux-là)."""
    out = {}
    for x in items:
        if x["category"]:
            k = _known(x)
            out.setdefault((x["category"], k[2] if k[0] is not None else None), []).append(x)
    return list(out.values())


def _spread(ranked, count):
    """Les premiers du classement, une marque différente par ligne tant que c'est possible."""
    picks, brands = [], set()
    for x in ranked:
        if x["brand"] not in brands:
            picks.append(x)
            brands.add(x["brand"])
        if len(picks) == count:
            return picks
    return picks + [x for x in ranked if x not in picks][:count - len(picks)]


def pick(item, items, count=COUNT):
    """→ (moins chers, similaires). Moins chers : comparables, disponibles, au moins 10 % sous le prix, la plus forte
    économie d'abord. Similaires : les autres comparables, au prix le plus proche."""
    pool = [b for b in items if comparable(item, b)]
    cheap = _spread(sorted((b for b in pool if b["in_stock"] and b["price"] <= item["price"] * CHEAPER),
                           key=lambda b: (b["price"], b["id"])), count)
    shown = {b["id"] for b in cheap}
    near = sorted((b for b in pool if b["id"] not in shown), key=lambda b: (abs(b["price"] - item["price"]), b["id"]))[:count]
    return cheap, near
