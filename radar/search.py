"""Recherche de l'app — déterministe, sans dépendance.

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
    """Chaque mot cherché doit commencer un mot du produit ; un synonyme de plusieurs mots (« lave linge ») est cherché tel quel."""
    h = haystack(d)
    return all((t in h) if " " in t else (f" {t}" in h) for t in toks)

