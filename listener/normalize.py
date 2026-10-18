"""Normalisation déterministe : catégorie, attributs produit, qualité de la donnée.

Aucune supposition silencieuse : un attribut non trouvé est absent (pas deviné) ;
la qualité d'un fait est explicite (KNOWN / CONFLICTING / UNKNOWN / SUSPECT).
"""
import re
import unicodedata

# slug -> mots-clés (titre ou catégorie déclarée, sans accents, minuscules). L'ordre compte : plus spécifique d'abord.
CATEGORIES = [
    ("lave_linge_sechant", ["lave-linge sechant", "lave linge sechant", "washer dryer"]),
    ("lave_vaisselle", ["lave-vaisselle", "lave vaisselle", "dishwasher"]),
    ("lave_linge", ["lave-linge", "lave linge", "washing machine", "machine a laver"]),
    ("seche_linge", ["seche-linge", "seche linge", "tumble dryer", "dryer"]),
    ("refrigerateur", ["refrigerateur", "frigo", "fridge", "refrigerator", "congelateur", "freezer"]),
    ("micro_ondes", ["micro-ondes", "micro ondes", "microwave"]),
    ("four", ["four encastrable", "four multifonction", "four pyrolyse", "four a chaleur", "oven"]),
    ("machine_cafe", ["machine a cafe", "machine expresso", "expresso broyeur", "cafetiere", "machine a dosettes", "espresso"]),
    ("televiseur", ["televiseur", "tv led", "tv oled", "tv qled", "smart tv", "television"]),
    ("matelas", ["matelas", "mattress"]),
    ("canape", ["canape", "sofa"]),
    ("lit", ["lit double", "lit adulte", "cadre de lit", "lit 140", "lit 160", "lit 180", "sommier", "bed frame"]),
    ("table", ["table a manger", "table de salle", "table de repas", "dining table"]),
    ("luminaire", ["luminaire", "suspension", "lampadaire", "plafonnier", "lampe"]),
    ("smartphone", ["smartphone", "iphone", "telephone portable"]),
    ("ordinateur_portable", ["ordinateur portable", "pc portable", "laptop", "macbook", "notebook"]),
    ("casque_audio", ["casque audio", "casque bluetooth", "ecouteurs", "headphones", "earbuds"]),
    ("robot_aspirateur", ["robot aspirateur", "aspirateur robot", "robot laveur", "roomba"]),
    ("aspirateur", ["aspirateur", "vacuum"]),
    ("tablette", ["tablette tactile", "ipad", "galaxy tab"]),
    ("montre_connectee", ["montre connectee", "apple watch", "galaxy watch", "smartwatch"]),
    ("enceinte", ["enceinte bluetooth", "enceinte connectee", "enceinte portable", "barre de son", "soundbar"]),
]

ATTR_PATTERNS = {
    "energy_class": re.compile(r"(?:classe(?: energetique| energie)?|energie|energy class)\s*:?\s*([a-g])\b"),
    "width_cm": re.compile(r"\b(\d{2,3})\s*cm\b"),
    "capacity_kg": re.compile(r"\b(\d{1,2}(?:[.,]\d)?)\s*kg\b"),
    "place_settings": re.compile(r"\b(\d{1,2})\s*couverts\b"),
    "noise_db": re.compile(r"\b(\d{2})\s*db\b"),
    "screen_in": re.compile(r"\b(\d{2,3})\s*(?:\"|''|pouces|po|inch)"),
    "storage_gb": re.compile(r"\b(\d{2,4})\s*(?:go|gb)\b"),
    "bed_width_cm": re.compile(r"\b(1[2-9]0)\s*x\s*(?:19|20)0\b"),
    "seats": re.compile(r"\b(\d{1,2})\s*places\b"),
}
PROP_ALIASES = {
    "classe energetique": "energy_class", "classe d'efficacite energetique": "energy_class", "energy class": "energy_class",
    "largeur": "width_cm", "width": "width_cm", "capacite": "capacity_kg", "nombre de couverts": "place_settings",
    "niveau sonore": "noise_db", "noise level": "noise_db", "taille de l'ecran": "screen_in",
}


def plain(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def categorize(title=None, declared=None):
    """→ (slug | None, source). La catégorie déclarée par le site prime sur le titre."""
    for text, src in ((declared, "declared"), (title, "title")):
        t = plain(text)
        if not t:
            continue
        for slug, kws in CATEGORIES:
            if any(k in t for k in kws):
                return slug, src
    return None, None


def _num(v):
    try:
        f = float(str(v).replace(",", "."))
        return int(f) if f.is_integer() else f
    except ValueError:
        return None


def attributes(title=None, properties=None):
    """Attributs trouvés dans les propriétés déclarées (prioritaires) puis dans le titre."""
    out = {}
    for k, v in (properties or {}).items():
        key = PROP_ALIASES.get(plain(k))
        if not key:
            continue
        pv = plain(v)
        if key == "energy_class":
            m = re.search(r"\b([a-g])\b", pv)
            if m:
                out[key] = m.group(1).upper()
        else:
            m = re.search(r"(\d+(?:[.,]\d+)?)", pv)
            if m and _num(m.group(1)) is not None:
                out[key] = _num(m.group(1))
    t = plain(title)
    for key, rx in ATTR_PATTERNS.items():
        if key in out:
            continue
        m = rx.search(t)
        if m:
            out[key] = m.group(1).upper() if key == "energy_class" else _num(m.group(1))
    return out


def quality(ex, pending=False):
    """Qualité d'un fait observé."""
    if pending:
        return "SUSPECT"
    if ex.get("consistent") is False:
        return "CONFLICTING"
    if not ex.get("currency_known", True) or ex.get("availability") in (None, "unknown"):
        return "UNKNOWN"   # prix connu, mais une dimension manque (devise ou stock) : dit tel quel
    return "KNOWN"
