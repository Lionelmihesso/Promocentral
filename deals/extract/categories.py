"""Catégorie et attributs d'un produit, déterministes : un attribut non trouvé est absent, jamais deviné.
Un titre qui commence par un accessoire n'a pas de catégorie (il n'entre pas au catalogue)."""
import re
import unicodedata

# slug -> mots-clés (titre ou catégorie déclarée, sans accents, minuscules). L'ordre compte : plus spécifique d'abord.
CATEGORIES = [
    # électroménager
    ("lave_linge_sechant", ["lave-linge sechant", "lave linge sechant", "lavante sechante", "lavante-sechante", "washer dryer"]),
    ("lave_vaisselle", ["lave-vaisselle", "lave vaisselle", "dishwasher"]),
    ("seche_linge", ["seche-linge", "seche linge", "tumble dryer", "dryer"]),
    ("lave_linge", ["lave-linge", "lave linge", "washing machine", "machine a laver"]),
    ("refrigerateur", ["refrigerateur", "frigo", "fridge", "refrigerator"]),
    ("congelateur", ["congelateur", "freezer"]),
    ("plaque_cuisson", ["plaque de cuisson", "plaque induction", "plaque a induction", "table de cuisson", "table induction",
                        "table a induction", "plaque vitroceramique", "plaque gaz", "plaque mixte", "domino induction"]),
    ("micro_ondes", ["micro-ondes", "micro ondes", "microwave"]),
    ("four", ["four encastrable", "four multifonction", "four pyrolyse", "four pyrolytique", "four a chaleur", "four vapeur",
              "four catalyse", "four electrique", "oven"]),
    ("hotte", ["hotte"]),
    ("cuisiniere", ["cuisiniere"]),
    ("machine_cafe", ["machine a cafe", "machine expresso", "expresso broyeur", "cafetiere", "machine a dosettes", "espresso"]),
    # literie
    ("matelas", ["matelas", "mattress"]),
    ("sommier", ["sommier", "box spring"]),
    # ameublement
    ("canape", ["canape", "sofa", "clic-clac", "clic clac", "banquette convertible", "meridienne"]),
    ("fauteuil", ["fauteuil"]),
    ("lit", ["lit double", "lit adulte", "cadre de lit", "lit coffre", "lit 90", "lit 140", "lit 160", "lit 180", "lit mezzanine",
             "lit superpose", "lit gigogne", "lit enfant", "bed frame"]),
    ("armoire", ["armoire", "dressing", "penderie"]),
    ("table", ["table a manger", "table de salle a manger", "table de salle", "table de repas", "table extensible", "dining table"]),
    ("buffet", ["buffet", "bahut", "vaisselier", "enfilade"]),
    ("meuble_tv", ["meuble tv", "meuble television", "banc tv"]),
    ("commode", ["commode"]),
    ("luminaire", ["luminaire", "suspension", "lampadaire", "plafonnier", "lampe"]),
    # tech (hors périmètre de collecte, reconnu pour ne pas mal classer)
    ("televiseur", ["televiseur", "tv led", "tv oled", "tv qled", "smart tv", "television"]),
    ("smartphone", ["smartphone", "iphone", "telephone portable"]),
    ("ordinateur_portable", ["ordinateur portable", "pc portable", "laptop", "macbook", "notebook"]),
    ("casque_audio", ["casque audio", "casque bluetooth", "ecouteurs", "headphones", "earbuds"]),
    ("robot_aspirateur", ["robot aspirateur", "robots aspirateurs", "aspirateur robot", "aspirateurs robots", "robot laveur",
                          "roomba"]),
    ("aspirateur", ["aspirateur", "vacuum", "nettoyeur de sol", "nettoyeurs de sol"]),
    ("tablette", ["tablette tactile", "ipad", "galaxy tab"]),
    ("montre_connectee", ["montre connectee", "apple watch", "galaxy watch", "smartwatch"]),
    ("enceinte", ["enceinte bluetooth", "enceinte connectee", "enceinte portable", "barre de son", "soundbar"]),
]
# Familles suivies → catégories (périmètre de la collecte, regroupement dans l'app)
FAMILIES = {
    "electromenager": ["lave_linge", "lave_linge_sechant", "seche_linge", "lave_vaisselle", "refrigerateur", "congelateur",
                       "four", "plaque_cuisson", "hotte", "cuisiniere", "robot_aspirateur", "aspirateur"],
    "ameublement": ["canape", "fauteuil", "lit", "armoire", "table", "buffet", "meuble_tv", "commode"],
    "literie": ["matelas", "sommier"],
}
FAMILY_OF = {c: f for f, cats in FAMILIES.items() for c in cats}

# Un titre qui COMMENCE par un accessoire n'est pas le produit (« Housse de canapé », « Pieds de lit », « Filtre hotte ») ;
# « Lit coffre avec tête de lit » reste un lit.
ACCESSORY = re.compile(r"^(?:housse|protege|protection|alese|surmatelas|sur-matelas|drap|oreiller|couette|piece|filtre|"
                       r"joint|tuyau|pied|pieds|poignee|kit|support|accessoire|coussin|plaid|tete de lit|cache|rallonge|bac|"
                       r"panier|grille|ampoule|resistance|courroie|thermostat|carte|module|lot de|set de|nettoyant|detartrant|brosse|batterie|"
                       r"sacs?|chargeur|embout|station)\b")

ATTR_PATTERNS = {
    "energy_class": re.compile(r"(?:classe(?: energetique| energie)?|energie|energy class)\s*:?\s*([a-g]\+{0,3})(?![a-z0-9+])"),
    "width_cm": re.compile(r"\b(\d{2,3})\s*cm\b"),
    "capacity_kg": re.compile(r"\b(\d{1,2}(?:[.,]\d)?)\s*kg\b"),
    "place_settings": re.compile(r"\b(\d{1,2})\s*couverts\b"),
    "noise_db": re.compile(r"\b(\d{2})\s*db\b"),
    "screen_in": re.compile(r"\b(\d{2,3})\s*(?:\"|''|pouces|po|inch)"),
    "storage_gb": re.compile(r"\b(\d{2,4})\s*(?:go|gb)\b"),
    "bed_width_cm": re.compile(r"\b(1[2-9]0)\s*x\s*(?:19|20)0\b"),
    "bed_size": re.compile(r"\b((?:2\s*x\s*)?\d{2,3}\s*x\s*\d{3})\b"),  # « 160x200 », « 2x80x200 » : literie de même taille seulement
    "seats": re.compile(r"\b(\d{1,2})\s*places\b"),
    "volume_l": re.compile(r"\b(\d{2,3})\s*l\b"),
    "zones": re.compile(r"\b(\d)\s*foyers?\b"),
    "autonomy_min": re.compile(r"\b(\d{2,3})\s*min\b"),
}
# Fonctions d'usage lues dans le titre : une alternative doit les avoir aussi (un aspirateur sans fil ne se remplace pas
# par un aspirateur à fil, ni une plaque à induction par une plaque gaz).
FEATURES = {
    "sans_fil": re.compile(r"\bsans fil\b"), "balai": re.compile(r"\bbalai\b"), "traineau": re.compile(r"\btraineau\b"),
    "laveur": re.compile(r"\blaveur\b"), "convertible": re.compile(r"\bconvertible\b"), "angle": re.compile(r"\bd['\s]?angle\b"),
    "induction": re.compile(r"\binduction\b"), "encastrable": re.compile(r"\bencastrable\b"),
    "americain": re.compile(r"\bamericain\b"), "electrique": re.compile(r"\belectrique\b"),
}
PROP_ALIASES = {
    "classe energetique": "energy_class", "classe d'efficacite energetique": "energy_class", "energy class": "energy_class",
    "largeur": "width_cm", "width": "width_cm", "capacite": "capacity_kg", "nombre de couverts": "place_settings",
    "niveau sonore": "noise_db", "noise level": "noise_db", "taille de l'ecran": "screen_in",
}


APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'", "\u02bc": "'", "\u00b4": "'"})


def plain(s):
    s = unicodedata.normalize("NFD", (s or "").lower()).translate(APOSTROPHES)      # « d’angle » (clavier de téléphone) = « d'angle »
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def categorize(title=None, declared=None):
    """→ (slug | None, source). La catégorie déclarée par le site prime sur le titre ; un accessoire n'a pas de catégorie."""
    if ACCESSORY.match(plain(title).strip()):
        return None, "accessory"
    for text, src in ((declared, "declared"), (title, "title")):
        t = _words(text)
        if not t:
            continue
        for slug, kws in _KEYWORDS:                  # d'abord le début du titre : « Lit coffre … avec sommier » est un lit
            if any(t.startswith(k) for k in kws):
                return slug, src
        for slug, kws in _KEYWORDS:
            if any(k in t for k in kws):
                return slug, src
    return None, None


def _words(s):
    """Sans accents, minuscules, tirets lus comme des espaces : « Robot-aspirateur » (catégorie déclarée) = « robot aspirateur »."""
    return " ".join(plain(s).replace("-", " ").split())


_KEYWORDS = [(slug, [_words(k) for k in kws]) for slug, kws in CATEGORIES]


def _num(v):
    try:
        f = float(str(v).replace(",", "."))
        return int(f) if f.is_integer() else f
    except ValueError:
        return None


def attributes(title=None, properties=None, category=None, declared=None):
    """Attributs trouvés dans les propriétés déclarées (prioritaires) puis dans le titre. Une catégorie qui a son
    ontologie (deals/ontology : les aspirateurs) y lit sa sous-catégorie et ses attributs, dans le titre et la catégorie
    déclarée de l'offre (declared) ; ce qui n'a pas de sens pour elle est écarté (« 2,6 kg » n'est pas la capacité d'un
    lave-linge)."""
    out = {}
    for k, v in (properties or {}).items():
        key = PROP_ALIASES.get(plain(k))
        if not key:
            continue
        pv = plain(v)
        if key == "energy_class":
            m = re.search(r"\b([a-g]\+{0,3})(?![a-z0-9+])", pv)              # « A+++ » : les + comptent
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
            out[key] = m.group(1).upper() if key == "energy_class" else re.sub(r"\s+", "", m.group(1)) if key == "bed_size" \
                else _num(m.group(1))
    features = sorted(f for f, rx in FEATURES.items() if rx.search(t))
    if features:
        out["features"] = features
    if category:
        from ..ontology import domain_of                 # l'ontologie lit avec plain : importée à l'usage
        d = domain_of(category)
        if d:
            _domain(d, out, title, category, declared)
    return out


def _domain(d, out, title, category, declared):
    """La sous-catégorie et les attributs que l'ontologie du domaine lit dans l'offre (titre, catégorie déclarée) ; la
    fonction « sans fil » aussi quand seule la catégorie déclarée le dit."""
    for k in d.drops:
        out.pop(k, None)
    vals = d.read(title, declared)
    out.update(vals)
    feats = set(out.get("features", ()))
    if vals.get("cordless") is True:
        feats.add("sans_fil")
    out["sub"] = d.sub_of(category, title, declared)
    if feats:
        out["features"] = sorted(feats)
    else:
        out.pop("features", None)


CAT_LEN = 120                                          # la catégorie déclarée gardée : 120 caractères au plus


def product_attributes(title, category, stored=None, props=None, declared=None):
    """Les caractéristiques d'un produit (marché, publication), relues avec les règles en vigueur : une ontologie révisée
    s'applique sans relire les offres. Hors ontologie, ce qui est déjà connu prime (comme avant). Dans un domaine qui a
    son ontologie, elle relit le titre et la catégorie déclarée de l'offre (celle du jour, sinon celle gardée : _cat) et
    écarte ce qui n'a pas de sens pour lui (les lectures d'une version d'avant comprises)."""
    stored = stored or {}
    from ..ontology import domain_of
    d = domain_of(category)
    cat = ((declared or stored.get("_cat") or "").strip()[:CAT_LEN] or None) if d else None
    fresh = attributes(title, props, category, cat)
    if d is None:
        return {**fresh, **{k: v for k, v in stored.items() if not k.startswith("_")}}
    out = {**fresh, **{k: v for k, v in stored.items() if not k.startswith("_") and k != "features" and not d.owns(k) and k not in d.drops}}
    if cat:
        out["_cat"] = cat
    return out
