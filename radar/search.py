"""Recherche et filtres de la page deals — déterministe, sans dépendance.

Recherche : insensible aux accents, à la casse et aux tirets ; tous les mots doivent être trouvés (titre, marque,
enseigne, catégorie) ; quelques synonymes du langage courant (frigo → réfrigérateur, télé → téléviseur…).
"""
import re
import unicodedata

CATEGORY_LABEL = {"ordinateur_portable": "Ordinateurs portables", "smartphone": "Smartphones", "casque_audio": "Casques", "enceinte": "Enceintes",
                  "tablette": "Tablettes", "micro_ondes": "Micro-ondes", "robot_aspirateur": "Robots aspirateurs", "machine_cafe": "Machines à café",
                  "montre_connectee": "Montres connectées", "lave_linge_sechant": "Lave-linge séchants", "canape": "Canapés", "lit": "Lits", "matelas": "Matelas", "refrigerateur": "Réfrigérateurs", "four": "Fours",
                  "lave_linge": "Lave-linge", "lave_vaisselle": "Lave-vaisselle", "televiseur": "Téléviseurs", "luminaire": "Luminaires",
                  "table": "Tables", "seche_linge": "Sèche-linge", "aspirateur": "Aspirateurs"}
SYNONYMS = {"frigo": "refrigerateur", "refrigerateurs": "refrigerateur", "tele": "televiseur", "tv": "televiseur", "televiseurs": "televiseur",
            "sofa": "canape", "canapes": "canape", "lampe": "luminaire", "lampadaire": "luminaire", "matelas": "matelas",
            "lavevaisselle": "lave vaisselle", "lavelinge": "lave linge", "laver": "lave linge", "ordi": "ordinateur", "pc": "ordinateur",
            "portable": "portable", "ecouteurs": "casque", "cafetiere": "cafe", "expresso": "cafe"}


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def tokens(q):
    out = []
    for t in norm(q).split():
        if t in ("a", "de", "la", "le", "les", "du", "des", "en", "et", "pour"):
            continue
        out.append(SYNONYMS.get(t, t))
    return out


def haystack(d):
    return " " + norm(" ".join([d.get("title") or "", d.get("brand") or "", d.get("retailer") or "",
                                CATEGORY_LABEL.get(d.get("category") or "", ""), (d.get("category") or "").replace("_", " ")])) + " "


def matches(d, toks):
    h = haystack(d)
    return all(any(f" {part}" in h for part in [t]) if " " not in t else t in h for t in toks)


def apply(cards, q=None, category=None, retailer=None, channel=None, min_discount=None, max_price=None, radius_km=None):
    toks = tokens(q) if q else []
    out = []
    for c in cards:
        if toks and not matches(c, toks):
            continue
        if category and c["category"] != category:
            continue
        if retailer and c["retailer"] != retailer:
            continue
        if channel and c["channel"] not in (channel, "both"):
            continue
        if min_discount and (c["real_discount"] or 0) < min_discount:
            continue
        if max_price and c["price"] > max_price:
            continue
        if radius_km and c["channel"] != "online" and (c["nearest_km"] is None or c["nearest_km"] > radius_km):
            continue
        out.append(c)
    return out


def facets(cards):
    cat, ret = {}, {}
    for c in cards:
        if c["category"]:
            cat[c["category"]] = cat.get(c["category"], 0) + 1
        ret[c["retailer"]] = ret.get(c["retailer"], 0) + 1
    return {"categories": [{"key": k, "label": CATEGORY_LABEL.get(k, k), "count": n} for k, n in sorted(cat.items(), key=lambda x: -x[1])],
            "retailers": [{"key": k, "count": n} for k, n in sorted(ret.items(), key=lambda x: -x[1])]}
