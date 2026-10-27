"""Comprendre une recherche tapée comme on parle : « aspirateur balai sans fil sous 300 € » → un rayon, des fonctions,
une taille ou une capacité, une marque, un budget, une envie de promo ou de petit prix, et les mots qui restent
(« velours », « Lina »). Pur : même phrase, même lecture ; rien n'est deviné, ce qui n'est pas dit n'est pas demandé.
La Recherche (catalog.search) et les missions (missions.interpret) comprennent ainsi les mêmes phrases.

Dans un domaine qui a son ontologie (deals/ontology : les aspirateurs), la phrase dit aussi un type (sous-famille :
robot, balai, traîneau, laveur, à main), des caractéristiques exigées (« sans fil », « sans sac », « HEPA ») et des
besoins (« un chat », « des allergies », « les escaliers ») ; le rayon est alors le domaine entier (robots compris) tant
qu'aucun type n'est nommé. Une référence (« S109 », « V15 ») reste un mot cherché, pas une quantité.

  read(texte, marques)      → {category, room, brand, features, attrs, min_price, max_price, off, low, sort, rest, unsupported,
                               domain, sub, needs, props, said_needs}
  fits(critères, produit)   → le produit a-t-il le rayon, la marque, les fonctions et les tailles demandés ? (fitter :
                              la même règle, préparée une fois pour une demande)
  satisfies(clé, a, v)      → la valeur a d'une caractéristique répond-elle à la valeur demandée v ?
  chips(critères)           → les critères en mots, un par puce (« Balai », « 9 kg et plus », « Moins de 300 € »)
"""
import re

from . import ontology
from .alternatives import energy_rank
from .extract import attributes, categorize
from .extract.categories import CATEGORIES, FAMILY_OF, plain
from .labels import CATEGORY_LABEL, CATEGORY_ONE, FEATURE_LABEL, ROOMS

MAX_PRICE = 100_000
AT_LEAST = {"capacity_kg", "place_settings", "zones", "volume_l", "autonomy_min", "seats"}   # au moins ce qui est demandé
EXACT = {"bed_size"}
NEAR = {"width_cm": 0.06}                                  # un appareil s'encastre au centimètre près
AT_MOST = {"noise_db", "weight_kg"}
WANTED = AT_LEAST | EXACT | set(NEAR) | AT_MOST | {"energy_class"}
FORM = ("balai", "traineau", "angle", "americain", "encastrable")          # dans un libellé, la forme vient d'abord
# Une caractéristique qui n'a de sens que pour certaines catégories (« lit 2 places » n'est pas un nombre de places
# assises) : ailleurs, elle n'est pas retenue — sinon rien n'y répondrait jamais.
ONLY = {"seats": {"canape", "fauteuil", "table"}, "bed_size": {"lit", "matelas", "sommier"},
        "capacity_kg": {"lave_linge", "seche_linge", "lave_linge_sechant"}, "place_settings": {"lave_vaisselle"},
        "zones": {"plaque_cuisson", "cuisiniere"}, "autonomy_min": {"aspirateur", "robot_aspirateur"},
        "weight_kg": {"aspirateur", "robot_aspirateur"}}
DOMAIN_FEATURES = {"balai", "traineau", "laveur", "sans_fil"}  # dans un domaine à ontologie : un type ou une caractéristique
WEIGHT_RE = re.compile(r"(?:moins de|max(?:imum)?|sous|pas plus de|<|≤)\s*(\d{1,2}(?:[.,]\d{1,2})?)\s*kg\b|(\d{1,2}(?:[.,]\d{1,2})?)\s*kg\s*(?:max(?:imum)?|au plus)\b")
REF_RE = re.compile(r"^(?=.*[a-z])(?=.*\d)[a-z0-9]+$")       # « s109 », « v15 », « x5 » : une référence, pas une quantité
QTY_RE = re.compile(r"^\d+(?:[.,]\d+)?(?:kg|cm|mm|m2|m|l|w|db|min|mn|h|pa|aw|go|gb|po|tr|x\d+)?$|^\d+x\d+(?:x\d+)?$|^[a-g]\+*$")
UNIT_AFTER = r"(?![\d.,]*\s*(?:kg|cm|mm|m2|m\b|l\b|litres?|min|minutes|db|w\b|watts?|pa\b|aw\b|places?|couverts?|foyers?|pouces|go\b|x\d))"
AMOUNT = r"(\d[\d\s.]*\d|\d)"
CURRENCY = r"\s*(?:€|euros?\b|eur\b|balles\b)"
OFF_RE = re.compile(r"(?<!\d)(\d{1,2})\s*%(?:\s*(?:de remise|de reduction|minimum|au moins|et plus))?")   # « -30 % » : une remise
RANGE_RE = [re.compile(rf"entre\s+{AMOUNT}(?:{CURRENCY})?\s+et\s+{AMOUNT}(?:{CURRENCY})?{UNIT_AFTER}"),   # « entre 200 et 400 »
            re.compile(rf"(?<![\d\w]){AMOUNT}(?:{CURRENCY})?\s+a\s+{AMOUNT}{CURRENCY}")]            # « de 200 à 400 € »
MIN_RE = re.compile(rf"(?<!pas )\b(?:plus de|a partir de|des|minimum|au moins)\s+{AMOUNT}{CURRENCY}")   # « dès 300 € »
PRICE_RE = [re.compile(rf"(?:sous|moins de|max(?:imum)?|jusqu'?a|en dessous de|pas plus de|budget|<|≤)\s*:?\s*{AMOUNT}{UNIT_AFTER}"),
            re.compile(rf"{AMOUNT}{CURRENCY}")]
SIZE_RE = re.compile(r"\b(\d{2,3})\s*(?:sur|par|x|×)\s*(\d{3})\b")   # « 160 sur 200 », « 160 × 200 » → 160x200
PROMO_RE = re.compile(r"\b(?:en )?(?:promos?|promotions?|soldes?|soldees?|remises?|reductions?|bons? plans?|deals?|bonnes? affaires?)\b")
LOW_RE = re.compile(r"\b(?:au )?prix (?:le )?plus bas\b|\bau plus bas\b|\bprix bas\b")
CHEAP_RE = re.compile(r"\b(?:pas|moins) chere?s?\b|\bpetits? prix\b|\bbon marche\b|\bpremiers? prix\b|\beconomiques?\b"
                      r"|\bprix croissants?\b")
# Mots du langage courant → catégorie (« lit », « canapés », « aspi », « meuble télé »…), en plus des mots-clés de
# l'extraction (« frigo », « lit coffre »…), y compris pour les catégories non suivies : on dit alors qu'elles ne le sont
# pas encore. Les plus longs d'abord.
SLANG = {"aspi": "aspirateur", "aspis": "aspirateur", "meuble tele": "meuble_tv", "tele": "televiseur", "tv": "televiseur",
         "sofa": "canape", "clic clac": "canape", "frigo": "refrigerateur", "congelo": "congelateur", "lampe": "luminaire",
         "lampadaire": "luminaire", "ordi": "ordinateur_portable", "pc portable": "ordinateur_portable", "ecouteurs": "casque_audio"}
WORDS = sorted({**{w: k for k in CATEGORY_LABEL for w in {plain(CATEGORY_LABEL[k]).replace("-", " "),
                                                          plain(CATEGORY_ONE.get(k, k)).replace("-", " "), k.replace("_", " ")}},
                **SLANG}.items(), key=lambda kv: -len(kv[0]))
KEYWORDS = {slug: {w for k in kws for w in plain(k).replace("-", " ").split()} for slug, kws in CATEGORIES}
FEATURE_WORDS = {"sans_fil": {"sans", "fil"}, "angle": {"d", "angle"}}
# Les mots qui disent une taille comprise (« autonomie 40 min ») : expliqués, pas cherchés en plus.
ATTR_WORDS = {"capacity_kg": {"capacite", "charge"}, "width_cm": {"largeur", "large"},   # l'autonomie : la langue des aspirateurs
              "noise_db": {"bruit", "silencieux", "silencieuse"}, "volume_l": {"volume", "contenance"}, "seats": {"assises"},
              "bed_size": {"taille", "dimensions"}, "energy_class": {"energie", "energetique"}}
UNITS = {"kg", "cm", "l", "litre", "litres", "couverts", "couvert", "places", "place", "foyers", "foyer", "db", "min", "minutes",
         "pouces", "po", "tours", "tour", "tr", "rpm", "w", "watts", "x", "classe", "energie", "energetique", "m2", "mm", "pa", "aw", "m"}
# Les mots qui ne disent rien du produit (« je cherche un… pas cher ») ; ceux qui restent sont cherchés tels quels.
STOP = {"je", "j", "cherche", "recherche", "cherchons", "veux", "voudrais", "aimerais", "souhaite", "besoin", "faut", "il", "me",
        "moi", "mon", "ma", "mes", "un", "une", "des", "de", "du", "d", "le", "la", "les", "l", "pour", "avec", "a", "au", "aux",
        "en", "et", "ou", "sur", "dans", "chez", "qui", "que", "quel", "quelle", "svp", "stp", "merci", "acheter", "trouver",
        "achat", "neuf", "neuve", "nouveau", "nouvelle", "bien", "bon", "bonne", "top", "meilleur", "meilleure", "meilleurs",
        "qualite", "pas", "cher", "chere", "euro", "euros", "eur", "balles", "max", "maximum", "budget", "sous", "moins", "plus",
        "environ", "partir", "minimum", "prix", "modele", "marque", "produit", "article", "vers", "type", "genre", "style",
        "truc", "machin", "chose", "quelque", "sympa", "joli", "jolie", "beau", "belle", "chouette", "cool", "super",
        "mieux", "croissant", "qu", "est", "aujourd", "hui", "importe"}


def _price(text):
    v = float(re.sub(r"[\s.]", "", text))
    return v if 1 <= v <= MAX_PRICE else None             # impossible : pas retenu (une mission le demandera)


def read(text, brands=()):
    """Une phrase → ce qu'elle demande, et les mots qui restent. category : un rayon suivi (unsupported : un rayon reconnu
    mais pas suivi, « smartphone ») ; brand : une marque du catalogue (brands) ; features, attrs : fonctions et tailles
    (règles de missions.matches) ; min_price, max_price : le budget ; off : remise minimale (1 : « en promo ») ;
    low : « prix bas » ; sort : « price » pour « pas cher » ; rest : les autres mots, sans les mots vides."""
    out = {"category": None, "room": None, "brand": None, "features": [], "attrs": {}, "min_price": None, "max_price": None,
           "off": None, "low": False, "sort": None, "rest": [], "unsupported": None,
           "domain": None, "sub": None, "needs": [], "props": {}, "said_needs": {}}
    raw = (text or "").strip()[:200]
    if not raw:
        return out
    t = re.sub(r"(?<!\d)[,.](?!\d)|[!?;:()\"«»…/]", " ", plain(raw).replace("-", " ").replace("−", " "))   # la ponctuation, pas les décimales
    t = SIZE_RE.sub(r"\1x\2", " ".join(t.split()))
    cut = lambda m: t[:m.start()] + " " + t[m.end():]
    m = OFF_RE.search(t)
    if m and 1 <= int(m.group(1)) <= 90:
        out["off"], t = int(m.group(1)), cut(m)
    for rx in RANGE_RE:
        m = rx.search(t)
        if m:
            lo, hi = _price(m.group(1)), _price(m.group(2))
            if lo and hi and lo < hi:
                out["min_price"], out["max_price"] = lo, hi
            t = cut(m)
            break
    m = MIN_RE.search(t)
    if m and out["min_price"] is None:
        out["min_price"], t = _price(m.group(1)), cut(m)
    for rx in PRICE_RE:
        m = rx.search(t)
        if m and out["max_price"] is None:
            out["max_price"], t = _price(m.group(1)), cut(m)
            break
    for rx, key, value in ((PROMO_RE, "off", 1), (LOW_RE, "low", True), (CHEAP_RE, "sort", "price")):
        m = rx.search(t)
        if m:
            out[key] = out[key] or value
            t = rx.sub(" ", t)
    t = " ".join(t.split())
    category, _ = categorize(t)
    if not category:
        category = next((k for w, k in WORDS if re.search(rf"(?<!\w){re.escape(w)}s?(?!\w)", t)), None)
    if category and category not in FAMILY_OF:
        out["unsupported"], category = category, None
    d = ontology.domain_of(category) if category else None if out["unsupported"] else ontology.detect(ontology.text(t))
    u = d.understand(ontology.text(t)) if d else None
    if not category and not out["unsupported"] and not d:  # « pour le salon » : les rayons de la pièce
        out["room"] = next((k for k in ROOMS if re.search(rf"(?<!\w){k}s?(?!\w)", t)), None)
    out["brand"] = next((b for b in sorted(brands, key=len, reverse=True)
                         if b and re.search(rf"(?<!\w){re.escape(plain(b))}(?!\w)", t)), None)
    a = attributes(t)
    named = category or out["unsupported"] or (d.categories[0] if d else None)
    if d:                                                  # le domaine entier tant qu'aucun type n'est nommé
        m = WEIGHT_RE.search(t)
        if m:
            a["weight_kg"] = float((m.group(1) or m.group(2)).replace(",", "."))
            t = cut(m)
        sub = u["sub"] or next((x["key"] for x in d.subs if x["match"]["category"] == [category] and not x["match"].get("any")), None)
        out.update(domain=d.key, sub=sub, needs=[k for k, _ in u["needs"]], said_needs={k: ws for k, ws in u["needs"]}, props=dict(u["props"]))
        if "autonomy_min" in a and "autonomie" in out["needs"]:      # « autonomie 40 min » : la durée dite suffit
            out["needs"].remove("autonomie")
            out["said_needs"].pop("autonomie")
        category = None
    out["category"] = category
    out["features"] = [f for f in a.get("features", []) if f in FEATURE_LABEL and not (d and f in DOMAIN_FEATURES)]
    out["attrs"] = {k: v for k, v in a.items() if k in WANTED and (not named or named in ONLY.get(k, {named}))}
    said = set(u["said"]) if d else set()                  # les mots expliqués par ce qui a été compris
    if named:
        said |= KEYWORDS.get(named, set()) | {w for k in (CATEGORY_LABEL, CATEGORY_ONE) for w in plain(k.get(named, "")).replace("-", " ").split()}
        said |= set(named.split("_")) | {w for s, k in SLANG.items() if k == named for w in s.split()}
    if out["brand"]:
        said |= set(plain(out["brand"]).split())
    said |= set(ROOMS) if named else {out["room"]} if out["room"] else set()   # « canapé pour le salon » : le canapé suffit
    for f in out["features"]:
        said |= FEATURE_WORDS.get(f, {f})
    for k in out["attrs"]:
        said |= ATTR_WORDS.get(k, set())
    energy = out["attrs"].get("energy_class") or a.get("energy_class")
    rest = []
    for w in t.replace("'", " ").split():                   # « d'angle » : « d » et « angle »
        bare = w.rstrip("s") if len(w) > 3 else w
        if (w in STOP or w in said or bare in said or w in UNITS or QTY_RE.match(w) or len(w) < 2
                or any(c.isdigit() for c in w) and not REF_RE.match(w) or (energy and w == energy.lower())):
            continue
        if w not in rest:
            rest.append(w)
    out["rest"] = rest
    return out


def fits(m, p):
    """p (category, brand, attrs) a-t-il ce que demande m : rayon (ou un rayon de la pièce), marque, fonctions, tailles ?
    Une caractéristique demandée mais inconnue du produit : pas de promesse. Le prix, la disponibilité et les mots se
    vérifient à part."""
    return fitter(m)(p)


def fitter(m):
    """fits, préparé une fois pour une même demande (la nuit : une mission, des milliers de produits). Dans un domaine à
    ontologie : ses rayons, le type demandé (sous-famille), les caractéristiques exigées — un fait ou une déduction de
    l'ontologie (« un robot est sans fil ») ; inconnue : pas de promesse. Les besoins classent (journey.py)."""
    cat, brand = m.get("category"), (m.get("brand") or "").lower()
    d = ontology.DOMAINS.get(m.get("domain")) if m.get("domain") else None
    rayons = ROOMS.get(m.get("room"), ("", ()))[1] if m.get("room") and not cat else d.categories if d and not cat else None
    feats, wanted = set(m.get("features") or ()), list((m.get("attrs") or {}).items())
    sub, props = (m.get("sub"), list((m.get("props") or {}).items())) if d else (None, [])

    def ok(p):
        if cat and p["category"] != cat or rayons is not None and p["category"] not in rayons:
            return False
        if brand and (p["brand"] or "").lower() != brand:
            return False
        a = p["attrs"] or {}
        if feats and not feats <= set(a.get("features", ())):
            return False
        for k, v in wanted:
            if not satisfies(k, a.get(k), v):
                return False
        if sub and a.get("sub") != sub:
            return False
        if props:
            facts = d.facts(a)
            if any(facts.get(k, (None,))[0] != v for k, v in props):
                return False
        return True
    return ok


def satisfies(k, a, v):
    """La valeur a du produit répond-elle à la valeur v demandée pour la caractéristique k ? Inconnue : non."""
    if a is None:
        return False
    if k in AT_LEAST and a < v or k in EXACT and a != v or k in AT_MOST and a > v:
        return False
    if k in NEAR and abs(a - v) > NEAR[k] * v:
        return False
    if k == "energy_class" and (energy_rank(a) is None or energy_rank(v) is None or energy_rank(a) > energy_rank(v)):
        return False
    return True


def euros(v):
    return f"{v:,.0f}".replace(",", " ") + " €"


ATTR_CHIP = {"capacity_kg": lambda v: f"{v:g} kg et plus".replace(".", ","), "place_settings": "{:g} couverts et plus".format,
             "zones": "{:g} foyers et plus".format, "seats": "{:g} places et plus".format, "volume_l": "{:g} L et plus".format,
             "autonomy_min": "{:g} min et plus".format, "bed_size": lambda v: v.replace("x", " × "), "width_cm": "{:g} cm".format,
             "noise_db": "{:g} dB au plus".format, "energy_class": "Classe {} ou mieux".format,
             "weight_kg": lambda v: f"{v:g} kg au plus".replace(".", ",")}


def chips(c):
    """Les critères appliqués, un par puce, dans l'ordre où on les dit : [{id, label}] (id : ce qu'on retire en la fermant)."""
    out = []
    d = ontology.DOMAINS.get(c.get("domain")) if c.get("domain") else None
    if c.get("category"):
        out.append({"id": "category", "label": CATEGORY_LABEL.get(c["category"], c["category"])})
    elif d and c.get("sub") in d.sub:
        out.append({"id": "sub", "label": d.sub[c["sub"]]["plural"]})
    elif d:
        out.append({"id": "domain", "label": d.label})
    elif c.get("room") in ROOMS:
        out.append({"id": "room", "label": ROOMS[c["room"]][0]})
    feats = c.get("features") or []
    out += [{"id": f"feature:{f}", "label": FEATURE_LABEL[f]} for f in [x for x in FORM if x in feats] + [x for x in feats if x not in FORM]
            if f in FEATURE_LABEL]
    if d:
        out += [{"id": f"prop:{k}", "label": d.props[k]["yes" if v else "no"]} for k, v in (c.get("props") or {}).items() if k in d.props]
    out += [{"id": f"attr:{k}", "label": ATTR_CHIP[k](v)} for k, v in (c.get("attrs") or {}).items() if k in ATTR_CHIP]
    if d:
        out += [{"id": f"need:{k}", "label": d.needs[k]["label"], "need": True} for k in c.get("needs") or [] if k in d.needs]
    if c.get("brand"):
        out.append({"id": "brand", "label": c["brand"]})
    lo, hi = c.get("min_price"), c.get("max_price")
    if lo is not None or hi is not None:
        out.append({"id": "price", "label": f"{euros(lo)[:-2]} à {euros(hi)}" if lo is not None and hi is not None
                    else f"Moins de {euros(hi)}" if hi is not None else f"Plus de {euros(lo)}"})
    if c.get("off"):
        out.append({"id": "off", "label": "En promo" if c["off"] <= 1 else f"−{c['off']:g} % et plus"})
    if c.get("low"):
        out.append({"id": "low", "label": "Prix bas"})
    if c.get("sort") in ("price", "discount"):
        out.append({"id": "sort", "label": "Prix croissant" if c["sort"] == "price" else "Plus forte promo"})
    out += [{"id": f"word:{w}", "label": f"« {w} »"} for w in c.get("words") or []]
    return out
