"""Catégorie et attributs d'un produit, déterministes : un attribut non trouvé est absent, jamais deviné.
Un titre qui commence par un accessoire n'a pas de catégorie (il n'entre pas au catalogue) ; un produit reconditionné ou
d'occasion non plus : ses prix ne se comparent pas à ceux du neuf."""
import re
import unicodedata

# slug -> mots-clés (titre ou catégorie déclarée, sans accents, minuscules). L'ordre compte : plus spécifique d'abord.
CATEGORIES = [
    # électroménager
    ("lave_linge_sechant", ["lave-linge sechant", "lave linge sechant", "lavante sechante", "lavante-sechante", "lavantes sechantes",
                            "washer dryer"]),
    ("lave_vaisselle", ["lave-vaisselle", "lave vaisselle", "dishwasher"]),
    ("seche_linge", ["seche-linge", "seche linge", "tumble dryer", "dryer"]),
    ("lave_linge", ["lave-linge", "lave linge", "washing machine", "machine a laver", "machines a laver"]),
    ("refrigerateur", ["refrigerateur", "frigo", "fridge", "refrigerator"]),
    ("congelateur", ["congelateur", "freezer"]),
    ("plaque_cuisson", ["plaque de cuisson", "plaque induction", "plaque a induction", "table de cuisson", "table induction",
                        "table a induction", "plaque vitroceramique", "plaque gaz", "plaque mixte", "domino induction",
                        "tables de cuisson", "plaques de cuisson", "plaques gaz", "plaques induction"]),
    ("micro_ondes", ["micro-ondes", "micro ondes", "microwave"]),
    ("four", ["four encastrable", "four multifonction", "four pyrolyse", "four pyrolytique", "four a chaleur", "four vapeur",
              "four catalyse", "four electrique", "four posable", "fours posables", "four pose libre", "fours encastrables", "oven"]),
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
    ("table", ["table a manger", "table de salle a manger", "table de salle", "table de repas", "table extensible", "dining table",
               "table ronde", "table carree", "table rectangulaire", "table ovale", "salle a manger > tables"]),
    ("buffet", ["buffet", "bahut", "vaisselier", "enfilade"]),
    ("meuble_tv", ["meuble tv", "meuble television", "banc tv"]),
    ("commode", ["commode", "chiffonnier", "semainier"]),
    ("luminaire", ["luminaire", "suspension", "lampadaire", "plafonnier", "lampe"]),
    # électronique
    # reconnus pour ne pas être mal classés (ni écran, ni casque audio) ; pas suivis
    ("babyphone", ["babyphone", "moniteur bebe", "ecoute bebe"]),
    ("sante", ["tensiometre", "moniteur de pression", "moniteur de tension", "moniteur cardiaque", "moniteur de frequence",
               "cardiofrequencemetre", "oxymetre"]),
    ("casque_protection", ["casque de moto", "casque moto", "casque integral", "casque jet", "casque de velo", "casque velo",
                           "casque de ski", "casque de chantier", "casque de protection", "casque d'equitation", "casque anti bruit",
                           "casque antibruit", "casque vr", "casque de realite virtuelle", "casque de coiffure"]),
    ("televiseur", ["televiseur", "tv led", "tv oled", "tv qled", "tv mini led", "tv neo qled", "tv 4k", "tv uhd", "tv 8k",
                    "tv full hd", "tv hd", "smart tv", "television"]),
    ("smartphone", ["smartphone", "iphone", "telephone portable", "telephones portables", "telephone mobile", "telephones mobiles",
                    "mobile senior"]),
    ("ordinateur_portable", ["ordinateur portable", "ordinateurs portables", "pc portable", "pc portables", "laptop", "macbook",
                             "notebook", "chromebook", "ultraportable", "ultrabook"]),
    ("casque_audio", ["casque audio", "casques audio", "casque bluetooth", "casque sans fil", "casque a reduction", "casque arceau",
                      "casque gaming", "casque gamer", "casque filaire", "casque hifi", "casque hi fi", "casque nomade",
                      "casque circum", "casque supra", "casque micro", "casque avec micro", "casque tv", "casque dj",
                      "ecouteurs", "headphones", "earbuds"]),
    ("console", ["console de jeux", "console de jeu", "consoles de jeux", "console portable", "consoles portables", "console de salon",
                 "consoles de salon", "playstation 5", "ps5", "xbox series", "nintendo switch", "steam deck",
                 "jeux video > consoles", "jeux video > console", "gaming > consoles"]),     # « Console … » sous « Jeux vidéo »
    ("ecran_pc", ["ecran pc", "ecrans pc", "ecran gaming", "ecrans gaming", "ecran gamer", "ecran incurve", "ecrans incurves",
                  "ecran ordinateur", "ecran d'ordinateur", "moniteur"]),
    ("robot_aspirateur", ["robot aspirateur", "robots aspirateurs", "aspirateur robot", "aspirateurs robots", "robot laveur",
                          "roomba"]),
    ("aspirateur", ["aspirateur", "vacuum", "nettoyeur de sol", "nettoyeurs de sol"]),
    ("tablette", ["tablette tactile", "tablettes tactiles", "ipad", "galaxy tab", "tablette android", "tablettes android",
                  "tablette enfant", "tablettes enfant", "tablette windows", "tablette 4g", "tablette 5g", "tablette wi fi"]),
    ("montre_connectee", ["montre connectee", "montres connectees", "bracelet connecte", "bracelets connectes", "montre gps",
                          "montres gps", "apple watch", "galaxy watch", "smartwatch", "montre de sport", "montres de sport",
                          "montre multisport", "montre running"]),
    ("enceinte", ["enceinte bluetooth", "enceintes bluetooth", "enceinte connectee", "enceintes connectees", "enceinte portable",
                  "enceintes portables", "enceinte sans fil", "enceintes sans fil", "enceinte wi fi", "barre de son", "barres de son",
                  "soundbar"]),
]
# Familles suivies → catégories (périmètre de la collecte, regroupement dans l'app)
FAMILIES = {
    "electromenager": ["lave_linge", "lave_linge_sechant", "seche_linge", "lave_vaisselle", "refrigerateur", "congelateur",
                       "four", "plaque_cuisson", "hotte", "cuisiniere", "robot_aspirateur", "aspirateur"],
    "electronique": ["televiseur", "smartphone", "ordinateur_portable", "tablette", "casque_audio", "enceinte", "montre_connectee",
                     "console", "ecran_pc"],
    "ameublement": ["canape", "fauteuil", "lit", "armoire", "table", "buffet", "meuble_tv", "commode"],
    "literie": ["matelas", "sommier"],
}
FAMILY_OF = {c: f for f, cats in FAMILIES.items() for c in cats}

# Un titre qui COMMENCE par un accessoire n'est pas le produit (« Housse de canapé », « Pieds de lit », « Filtre hotte »,
# « Coque pour smartphone », « Manette pour console ») ; « Lit coffre avec tête de lit » reste un lit, « Bracelet connecté »
# reste une montre.
ACCESSORY = re.compile(r"^(?:(?:housse|protege|protection|alese|surmatelas|sur-matelas|drap|oreiller|couette|piece|filtre|"
                       r"joint|tuyau|pied|pieds|poignee|kit|support|accessoire|coussin|plaid|tete de lit|cache|rallonge|bac|"
                       r"panier|grille|ampoule|resistance|courroie|thermostat|carte|module|lot de|set de|nettoyant|detartrant|brosse|batterie|"
                       r"sacs?|chargeur|embout|station|coque|etui|verre trempe|film|cable|adaptateur|telecommande|manette|jeux?|"
                       r"sacoche|souris|clavier|dock|hub)[sx]?|bracelet(?!s? connecte)s?)\b")
# Reconditionné, d'occasion : pas du neuf (dit n'importe où dans le titre ou la catégorie de l'enseigne).
REFURBISHED = re.compile(r"\b(?:reconditionne(?:e|s|es)?|occasion|seconde main|remis a neuf|refurbished|grade [abc])\b")

ATTR_PATTERNS = {
    # « classe A », « Classe énergétique : B » ; ou un « A++ » seul, ses + le disent (un « A » seul ne dit rien : « Série A »)
    "energy_class": re.compile(r"(?:classe(?: energetique| energie)?|energie|energy class)\s*:?\s*([a-g]\+{0,3})(?![a-z0-9+])"
                               r"|(?<![\w+])(a\+{1,3})(?![a-z0-9+])"),
    "width_cm": re.compile(r"\b(\d{2,3})\s*cm\b"),
    # « 9/6 kg », « 10 kg + 6 kg » (lave-linge séchant) : la capacité de lavage, la première
    "capacity_kg": re.compile(r"\b(\d{1,2}(?:[.,]\d)?)\s*(?:kg\b|(?=(?:kg)?\s*[/+]\s*\d{1,2}(?:[.,]\d)?\s*kg\b))"),
    "place_settings": re.compile(r"\b(\d{1,2})\s*couverts\b"),
    "noise_db": re.compile(r"\b(\d{2})\s*db\b"),
    "bed_width_cm": re.compile(r"\b(1[2-9]0)\s*x\s*(?:19|20)0\b"),
    "bed_size": re.compile(r"\b((?:2\s*x\s*)?\d{2,3}\s*x\s*\d{3})\b"),  # « 160x200 », « 2x80x200 » : literie de même taille seulement
    "seats": re.compile(r"\b(\d{1,2})\s*(?:places|personnes)\b"),
    "volume_l": re.compile(r"\b(\d{2,3})\s*l\b"),
    "zones": re.compile(r"\b(\d)\s*(?:foyers?|feux|bruleurs?|zones)\b"),
    "autonomy_min": re.compile(r"\b(\d{2,3})\s*min\b"),
    "drawers": re.compile(r"\b(\d{1,2})\s*tiroirs?\b"),
    "refresh_hz": re.compile(r"\b(\d{2,3})\s*hz\b"),
    "screen_in": re.compile(r"\b(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:\"|''|pouces?\b|po\b|inch(?:es)?\b)"),
    "ram_gb": re.compile(r"\b(\d{1,3})\s*go\s*(?:de\s+)?(?:ram|memoire vive)\b|\b(?:ram|memoire vive)\s*:?\s*(\d{1,3})\s*go\b"),
}
STORAGE = re.compile(r"\b(\d{1,4}(?:[.,]\d+)?)\s*(go|gb|to|tb)\b(?!\s*(?:de\s+)?(?:lpddr|ddr))")
TV_SIZES = (24, 32, 40, 42, 43, 48, 50, 55, 58, 65, 70, 75, 77, 83, 85, 86, 98, 100)   # téléviseurs : « 139 cm » → 55 pouces
# Les mesures lues dans le titre, et les rayons où chacune a un sens (« lit 2 places » n'est pas un nombre de places
# assises, « 139 cm » d'un téléviseur n'est pas sa largeur) : ailleurs, elle n'est ni lue ni demandée.
MEASURES = set(ATTR_PATTERNS) - {"bed_width_cm"} | {"storage_gb"}
ONLY = {"seats": {"canape", "fauteuil", "table"}, "bed_size": {"lit", "matelas", "sommier"},
        "capacity_kg": {"lave_linge", "seche_linge", "lave_linge_sechant"}, "place_settings": {"lave_vaisselle"},
        "zones": {"plaque_cuisson", "cuisiniere"}, "autonomy_min": {"aspirateur", "robot_aspirateur"},
        "volume_l": {"refrigerateur", "congelateur", "four"}, "drawers": {"commode"},
        "screen_in": {"televiseur", "ordinateur_portable", "tablette", "ecran_pc"},          # l'usage (un smartphone : non)
        "storage_gb": {"smartphone", "tablette", "console", "ordinateur_portable"}, "ram_gb": {"ordinateur_portable"},
        "refresh_hz": {"ecran_pc", "televiseur"},
        "width_cm": {c for c in ("lave_linge", "lave_linge_sechant", "seche_linge", "lave_vaisselle", "refrigerateur", "congelateur",
                                 "four", "plaque_cuisson", "hotte", "cuisiniere", "canape", "fauteuil", "lit", "armoire", "table",
                                 "buffet", "meuble_tv", "commode", "matelas", "sommier")},
        "noise_db": {c for c in ("lave_linge", "lave_linge_sechant", "seche_linge", "lave_vaisselle", "refrigerateur", "congelateur",
                                 "hotte", "aspirateur", "robot_aspirateur")}}


def makes_sense(key, category):
    """La mesure key a-t-elle un sens pour ce rayon ? Un rayon inconnu : oui (rien n'est écarté sans savoir)."""
    return category is None or category in ONLY.get(key, {category})


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
    """→ (slug | None, source). La catégorie déclarée par le site prime sur le titre ; un accessoire n'a pas de catégorie,
    un produit reconditionné ou d'occasion non plus (refurbished)."""
    if ACCESSORY.match(plain(title).strip()):
        return None, "accessory"
    if REFURBISHED.search(_words(title)) or REFURBISHED.search(_words(declared)):
        return None, "refurbished"
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
            v = next(g for g in m.groups() if g is not None)
            out[key] = v.upper() if key == "energy_class" else re.sub(r"\s+", "", v) if key == "bed_size" else _num(v)
    if "storage_gb" not in out:
        size = storage(t)
        if size:
            out["storage_gb"] = size
    if category == "ordinateur_portable" and "ram_gb" not in out:     # « 8Go - 256Go SSD » : la mémoire, puis le stockage
        ram = laptop_ram(t)
        if ram:
            out["ram_gb"] = ram
    if category == "televiseur" and "screen_in" not in out:   # « TV LED 108 cm » : la diagonale, dite en centimètres
        inches = tv_inches(t)
        if inches:
            out["screen_in"] = inches
    features = sorted(f for f, rx in FEATURES.items() if rx.search(t))
    if features:
        out["features"] = features
    if category:
        for k in [k for k in out if k in MEASURES and not makes_sense(k, category)]:
            del out[k]                                   # « 139 cm » d'un téléviseur n'est pas une largeur
        from ..ontology import domain_of                 # l'ontologie lit avec plain : importée à l'usage
        d = domain_of(category)
        if d:
            _domain(d, out, title, category, declared)
    return out


RAM_SIZES = (2, 4, 6, 8, 12, 16, 24, 32, 48, 64)


def laptop_ram(t):
    """La mémoire vive d'un ordinateur portable que le titre dit sans le mot RAM, comme les enseignes l'écrivent : à côté
    d'un stockage nommé (SSD, eMMC, disque), une seule autre capacité, en Go, d'une taille de mémoire (« 8Go - 256Go SSD »,
    « 4 Go 64 Go eMMC ») ; sinon None (rien de deviné)."""
    if not re.search(r"\d\s*(?:go|to)\s*(?:ssd|emmc|hdd|nvme|ufs)\b", t):
        return None
    other = [int(m.group(1)) for m in re.finditer(r"\b(\d{1,2})\s*go\b(?!\s*(?:ssd|emmc|hdd|nvme|ufs)\b)", t)]
    return other[0] if len(other) == 1 and other[0] in RAM_SIZES else None


def tv_inches(t):
    """La diagonale d'un téléviseur dite en centimètres dans un texte simple (« 139 cm ») → la taille en pouces la plus
    proche (55) si elle tombe à 4 % près ; None sinon."""
    m = re.search(r"\b(\d{2,3})\s*cm\b", t)
    if not m:
        return None
    inches = int(m.group(1)) / 2.54
    near = min(TV_SIZES, key=lambda x: (abs(x - inches), -x))
    return near if abs(near - inches) <= 0.04 * near else None


def storage(t):
    """Le stockage (Go) dit dans un texte simple (plain) : la plus grande capacité en Go ou en To (1 To = 1 000 Go) qui
    n'est pas de la mémoire vive (« 8 Go RAM 256 Go » : 256) ; None si rien n'est dit."""
    best = None
    for m in STORAGE.finditer(ATTR_PATTERNS["ram_gb"].sub(" ", t)):     # la mémoire vive dite, mise de côté
        v = _num(m.group(1))
        v = v * 1000 if m.group(2) in ("to", "tb") else v
        if v and (best is None or v > best):
            best = int(v) if float(v).is_integer() else v
    return best


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
    # l'offre du jour l'emporte ; ce qu'elle ne dit plus (une mesure lue sur la fiche) reste connu, sauf ce que l'ontologie
    # lit elle-même (le type, les attributs oui/non) et ce qui n'a pas de sens pour ce rayon
    kept = {k: v for k, v in stored.items() if not k.startswith("_") and k != "features" and not d.owns(k) and k not in d.drops
            and not (k in MEASURES and not makes_sense(k, category))}
    out = {**kept, **fresh}
    if cat:
        out["_cat"] = cat
    return out
