"""Alternatives — fonction pure : pour le produit regardé, des produits comparables, et ceux qui coûtent moins cher.

Comparable (ce qu'un acheteur attend d'un remplaçant) :
  - même catégorie ;
  - même usage : même taille de literie ; largeur à 6 % près en électroménager (l'encastrement), à 20 % près en
    ameublement ; places à une près ; même forme (balai, traîneau, encastrable, d'angle, américain : ni plus, ni moins) ;
    au moins les mêmes fonctions (sans fil, laveur, convertible, induction, électrique) ;
  - pas moins bien : classe énergie au plus une lettre en dessous ; capacité, couverts, foyers au plus un de moins ;
    volume au plus 15 % de moins ; autonomie au moins les deux tiers ; bruit au plus 3 dB de plus.
Une caractéristique inconnue chez le candidat ne l'écarte que si elle dit l'usage (taille, largeur, places).
Moins cher : au moins 10 % sous le prix du produit regardé, disponible. Classement : la plus forte économie d'abord, une
marque différente par ligne tant que c'est possible.

Un produit : dict(id, category, family, brand, price, in_stock, attrs) — attrs = extract.attributes(titre) complété des
caractéristiques déclarées.
"""
ENERGY = {c: i for i, c in enumerate("ABCDEFG")}
CHEAPER = 0.90
COUNT = 3
WIDTH_TOLERANCE = {"ameublement": 0.20}          # sinon 6 % : un appareil s'encastre au centimètre près
NOT_FEWER = {"capacity_kg": 1, "place_settings": 1, "zones": 1}
SAME_FORM = {"balai", "traineau", "encastrable", "angle", "americain"}    # un canapé droit ne remplace pas un canapé d'angle


def comparable(a, b):
    """b peut-il remplacer a ?"""
    if a["id"] == b["id"] or not a["category"] or a["category"] != b["category"]:
        return False
    A, B = a["attrs"], b["attrs"]
    if "bed_size" in A and B.get("bed_size") != A["bed_size"]:
        return False
    if "width_cm" in A:
        tol = WIDTH_TOLERANCE.get(a.get("family"), 0.06)
        if "width_cm" not in B or abs(B["width_cm"] - A["width_cm"]) > tol * A["width_cm"]:
            return False
    if "seats" in A and ("seats" not in B or abs(B["seats"] - A["seats"]) > 1):
        return False
    fa, fb = set(A.get("features", ())), set(B.get("features", ()))
    if not fa <= fb or fa & SAME_FORM != fb & SAME_FORM:
        return False
    for k, d in NOT_FEWER.items():
        if k in A and k in B and B[k] < A[k] - d:
            return False
    if "volume_l" in A and "volume_l" in B and B["volume_l"] < 0.85 * A["volume_l"]:
        return False
    if "autonomy_min" in A and "autonomy_min" in B and B["autonomy_min"] < A["autonomy_min"] * 2 / 3:
        return False
    if "noise_db" in A and "noise_db" in B and B["noise_db"] > A["noise_db"] + 3:
        return False
    ea, eb = ENERGY.get(A.get("energy_class")), ENERGY.get(B.get("energy_class"))
    if ea is not None and eb is not None and eb > ea + 1:
        return False
    return True


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
