"""Lectures de l'app — sur le catalogue publié, sans aucun calcul de marché.

Chaque lecture = une ou deux requêtes indexées ; l'ordre (le profil de goûts, profile.py : au plus × 1,5) et les signets
dépendent de la personne. L'accueil sans filtre, les top deals, « pour vous » et le feed de la Recherche suivent ses goûts ;
une recherche, un filtre, une pièce, une marque ou une catégorie répondent à ce qui est demandé (seule la marque suivie y
compte, comme avant). La recherche est insensible aux accents, à la casse et aux tirets ; chaque mot cherché doit
commencer un mot du produit (titre, marque, enseigne, catégorie) ; quelques synonymes du langage courant.

Une carte porte la marque et la catégorie au singulier (`kind`). La fiche dit où se situe le prix du jour sur les trois
derniers mois (`position`, pur) ; les caractéristiques techniques et les autres enseignes restent chez l'enseigne.

La Recherche n'est jamais vide : sans mot ni filtre, elle montre un feed (`lead` puis `breadth`, purs) que chaque mot,
filtre ou tri resserre ou réordonne. L'accueil commence par les top deals (`top`) : les plus fortes remises et les prix
parmi les plus bas depuis longtemps (`cheap`, pur), à tour de rôle.
"""
import json
import re
import unicodedata
from collections import Counter, defaultdict
from functools import lru_cache
from itertools import zip_longest

from . import journey, ontology
from . import profile as P
from . import query
from .errors import NotFound
from .extract.categories import FAMILY_OF
from .labels import CATEGORY_LABEL, CATEGORY_ONE, FEATURE_LABEL, ROOMS  # noqa: F401  (relus par missions, profile)

TODAY_LIMIT = 60
POSITION_DAYS = 14                                         # en dessous, trop peu de relevés pour juger un prix
SORTS = ("relevance", "price", "discount")                 # Recherche : pertinence, prix croissant, remise
TOP_LIMIT = 10                                             # accueil : top deals (et « pour vous »)
TOP_SAME = 3                                               # top deals suivant les goûts : au plus trois places par rayon
LOW_DAYS = 60                                              # « depuis longtemps » : au moins 2 mois de prix relevés
LOW_DROP = 0.10                                            # et au moins 10 % sous le prix habituel
PROMO_STEPS = (1, 10, 20, 30, 40, 50)                      # filtre Promo : en promo, puis −10 % et plus, −20 %…
OPTION_ATTRS = {"capacity_kg": "Capacité", "place_settings": "Couverts", "zones": "Foyers", "seats": "Places", "bed_size": "Taille",
                "width_cm": "Largeur", "volume_l": "Volume", "autonomy_min": "Autonomie", "energy_class": "Classe énergie"}   # Affiner
RECENT_SEARCHES = 4                                        # feed : les dernières recherches gardées par le navigateur
RECENT_EACH = 6                                            # feed : produits au plus par recherche récente, en tête
FAMILY_LABEL = {"electromenager": "Électroménager", "ameublement": "Ameublement", "literie": "Literie"}
SYNONYMS = {
    "frigo": "refrigerateur", "refrigerateurs": "refrigerateur", "congelo": "congelateur", "congel": "congelateur",
    "lavevaisselle": "lave vaisselle", "lavelinge": "lave linge", "laver": "lave linge", "induction": "plaque", "plaques": "plaque",
    "hottes": "hotte", "sofa": "canape", "canapes": "canape", "clicclac": "canape", "bz": "canape", "convertible": "canape",
    "fauteuils": "fauteuil", "lits": "lit", "dressing": "armoire", "armoires": "armoire", "buffets": "buffet", "commodes": "commode",
    "sommiers": "sommier", "lampe": "luminaire", "lampadaire": "luminaire", "tele": "televiseur", "tv": "televiseur",
    "televiseurs": "televiseur", "ordi": "ordinateur", "pc": "ordinateur", "ecouteurs": "casque", "cafetiere": "cafe",
    "expresso": "cafe"}
STOP = {"a", "de", "la", "le", "les", "du", "des", "en", "et", "pour"}


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def tokens(q):
    return [SYNONYMS.get(t, t) for t in norm(q).split() if t not in STOP]


def haystack(title, brand, merchant, category):
    """Texte cherchable d'un produit (calculé à la publication)."""
    return " " + norm(" ".join([title or "", brand or "", merchant or "", CATEGORY_LABEL.get(category or "", ""),
                                (category or "").replace("_", " ")])) + " "


def position(history, price):
    """Le prix du jour face aux relevés de la courbe (meilleur prix de chaque jour, 90 jours, aujourd'hui exclu).

    level : « lowest » au plus bas (aucun jour moins cher, et plus cher au moins un jour sur deux), « low » parmi les plus
    bas (moins cher qu'au moins 2 jours sur 3), « high » plus cher que d'habitude (plus cher qu'au moins 2 jours sur 3),
    « usual » sinon (un prix qui ne bouge pas compris). low et high bornent la jauge (aujourd'hui compris), usual est la
    médiane, days le nombre de jours depuis le premier relevé ; rank place le prix du jour parmi les jours relevés (0 :
    le moins cher, 1 : le plus cher ; les jours au même prix comptent pour moitié) : le point de la jauge suit ainsi le
    verdict. None s'il y a moins de 14 jours relevés."""
    p = (history or {}).get("p") or []
    days = [v for v in p[:-1] if v is not None]
    if len(days) < POSITION_DAYS:
        return None
    higher = sum(v > price + 0.5 for v in days) / len(days)     # prix arrondis à l'euro dans la courbe
    lower = sum(v < price - 0.5 for v in days) / len(days)
    level = "lowest" if lower == 0 and higher >= 0.5 else "low" if higher >= 2 / 3 else "high" if lower >= 2 / 3 else "usual"
    first = next(i for i, v in enumerate(p) if v is not None)
    rank = 0.0 if level == "lowest" else round(lower + (1 - lower - higher) / 2, 2)   # place parmi les jours : 0 le moins cher
    return {"level": level, "rank": rank, "low": min(min(days), round(price)), "high": max(max(days), round(price)),
            "usual": sorted(days)[len(days) // 2], "days": len(p) - first}


@lru_cache(maxsize=4096)
def names(category, brand):
    """Les mots qui nomment un produit sans le décrire : sa catégorie (au pluriel, au singulier) et sa marque (peu de
    couples catégorie × marque : gardés en mémoire)."""
    return " " + norm(" ".join([CATEGORY_LABEL.get(category or "", ""), CATEGORY_ONE.get(category or "", ""),
                                (category or "").replace("_", " "), brand or ""])) + " "


def cheap(r):
    """Un prix parmi les plus bas observés depuis au moins 2 mois (au plus bas, ou moins cher que 2 jours relevés sur 3 :
    le verdict de la fiche, calculé à la publication) et au moins 10 % sous le prix habituel (la médiane des jours)."""
    return (r["level"] in ("lowest", "low") and (r["span"] or 0) >= LOW_DAYS and bool(r["usual"])
            and (r["usual"] - r["price"]) / r["usual"] >= LOW_DROP)


def relevance(toks, score):
    """Clé de pertinence : d'abord les produits dont la requête nomme la catégorie ou la marque, puis les remises (score :
    la remise, × 1,5 pour une marque suivie), puis le prix croissant."""
    def named(r):
        n = names(r["category"], r["brand"])
        return any((t in n) if " " in t else (f" {t}" in n) for t in toks)
    if not toks:                                           # le feed : aucun mot ne nomme rien
        return lambda r: (r["pct"] <= 0, -score(r), r["price"], r["product_id"])
    return lambda r: (not named(r), r["pct"] <= 0, -score(r), r["price"], r["product_id"])


def breadth(rows, key):
    """Feed sans requête : l'étendue du catalogue, une carte par catégorie à tour de rôle ; d'abord les catégories qui
    offrent le plus de choix, et dans chacune le meilleur produit selon key (la remise, puis le prix)."""
    by = defaultdict(list)
    for r in sorted(rows, key=key):
        by[r["category"]].append(r)
    queues, out = sorted(by.values(), key=lambda g: (-len(g), key(g[0]))), []
    while queues:
        out += [g.pop(0) for g in queues]
        queues = [g for g in queues if g]
    return out


def lead(rows, recent, score):
    """Tête du feed : les produits des recherches récentes (la plus récente d'abord), une recherche à tour de rôle, les
    plus pertinents de chacune, RECENT_EACH au plus par recherche. → (produits, recherches qui ont trouvé quelque chose)"""
    lists, used = [], []
    for text in list(recent)[:RECENT_SEARCHES]:
        toks = tokens(text)
        hits = sorted((r for r in rows if toks and matches(r["search"], toks)), key=relevance(toks, score))[:RECENT_EACH]
        if hits:
            lists.append(hits)
            used.append(text)
    out, seen = [], set()
    for r in (r for turn in zip_longest(*lists) for r in turn if r):
        if r["product_id"] not in seen:
            seen.add(r["product_id"])
            out.append(r)
    return out, used


def enrich(a, r):
    """Une fiche publiée avant l'ontologie de son domaine (sans sous-famille) : la sous-famille déduite de son texte
    cherchable (le titre), en attendant la publication suivante, qui la relit."""
    d = ontology.domain_of(r.get("category"))
    if d is not None and "sub" not in a:
        a = {**a, "sub": d.sub_of(r["category"], (r.get("search") or "").strip(), a)}
    return a


def matches(search, toks):
    """Chaque mot doit commencer un mot du produit ; un synonyme de plusieurs mots (« lave linge ») est cherché tel quel."""
    return all((t in search) if " " in t else (f" {t}" in search) for t in toks)


class Catalog:
    def __init__(self, store):
        self.s = store
        self._brands = ("?", [])                           # marques du catalogue, le temps d'une publication (« ? » : pas encore lues)
        self._attrs = ("?", {})                            # caractéristiques lues des produits publiés, le temps d'une publication
        self._verdicts = ("?", {})                         # verdicts des critères (domaines à ontologie), le temps d'une publication

    def _personal(self, uid):
        if uid is None:
            return set(), set()
        return ({r["brand"] for r in self.s.q("SELECT brand FROM follows WHERE user_id=?", (uid,))},
                {r["product_id"] for r in self.s.q("SELECT product_id FROM saves WHERE user_id=?", (uid,))})

    @staticmethod
    def _card(r, followed, saved):
        return {"id": r["product_id"], "title": r["title"], "name": r["name"], "brand": r["brand"], "category": r["category"],
                "category_label": CATEGORY_LABEL.get(r["category"], r["category"]),
                "kind": CATEGORY_ONE.get(r["category"], CATEGORY_LABEL.get(r["category"], r["category"])),
                "price": r["price"], "was": r["was"],
                "pct": r["pct"], "merchant": r["merchant"], "offer_id": r["offer_id"], "since": r["since"], "ends": r["ends"], "published_on": r["published_on"],
                "followed": r["brand"] in followed, "saved": r["product_id"] in saved}

    def _profile(self, prof, followed):
        """Le profil de la lecture ; sans profil (appel interne), l'ordre d'avant : la marque suivie compte 1,5 fois."""
        return prof if prof is not None else P.Profile(follows=frozenset(followed))

    def today(self, uid=None, category=None, q=None, prof=None):
        """Remises du jour ; category : une catégorie ou plusieurs, séparées par des virgules (univers, pièce). Sans filtre,
        l'ordre suit les goûts (profile.arrange) ; avec, il répond à ce qui est demandé."""
        followed, saved = self._personal(uid)
        cats = [c for c in (category or "").split(",") if c]
        where, args = (f" AND category IN ({','.join('?' * len(cats))})", tuple(cats)) if cats else ("", ())
        toks = tokens(q) if q else []
        prof = self._profile(None if cats or toks else prof, followed)
        # colonnes légères pour filtrer et classer, lignes complètes pour le seul haut de liste montré
        rows = self.s.q("SELECT product_id, pct, brand, category" + (", search" if toks else "") + " FROM catalog WHERE pct > 0" + where, args)
        hits = P.arrange([r for r in rows if not toks or matches(r["search"], toks)], lambda r: r["pct"], prof)
        score = lambda r: r["pct"] * prof.boost(r["category"], r["brand"])
        return {**self._page(hits, score, uid, followed, saved), "published_at": self.published_at(), "personal": prof.personal}

    def top(self, uid=None, prof=None):
        """Top deals, en tête de l'accueil : les plus fortes remises réelles et les prix parmi les plus bas depuis longtemps
        (`cheap`, ce qu'ils font économiser sur le prix habituel d'abord), à tour de rôle, sans doublon ; les goûts de la
        personne pèsent au plus × 1,5 (une marque suivie aussi) et un même rayon n'y prend pas plus de trois places.
        why : pourquoi chacun est là (la remise ; le prix bas, son verdict et depuis combien de jours)."""
        followed, saved = self._personal(uid)
        prof = self._profile(prof, followed)
        rows = self.s.q("SELECT product_id, pct, brand, category, price, level, span, usual FROM catalog")
        drop = lambda r: (r["usual"] - r["price"]) / r["usual"]
        if prof.personal:
            deals = P.arrange([r for r in rows if r["pct"] > 0], lambda r: r["pct"], prof)
            low = P.arrange([r for r in rows if cheap(r)], drop, prof)
        else:                                              # l'ordre d'avant, à l'identique
            score = lambda r: r["pct"] * prof.boost(r["category"], r["brand"])
            deals = sorted((r for r in rows if r["pct"] > 0), key=lambda r: (-score(r), r["price"], r["product_id"]))
            low = sorted((r for r in rows if cheap(r)), key=lambda r: (-drop(r), r["product_id"]))
        picked, seen, per = [], set(), Counter()
        for r in (r for turn in zip_longest(deals, low) for r in turn if r):
            if r["product_id"] not in seen and len(picked) < TOP_LIMIT and (not prof.personal or per[r["category"]] < TOP_SAME):
                seen.add(r["product_id"])
                per[r["category"]] += 1
                picked.append(r)
        full = {r["product_id"]: r for r in self.s.q(f"SELECT * FROM catalog WHERE product_id IN ({','.join('?' * len(picked))})",
                                                     [r["product_id"] for r in picked])} if picked else {}
        return {"products": [{**self._card(full[r["product_id"]], followed, saved),
                              "why": {"pct": r["pct"], "low": r["level"] if cheap(r) else None, "days": r["span"] if cheap(r) else None}}
                             for r in picked]}

    def published_at(self):
        """Heure de la dernière publication (horodatage), pour « mis à jour à … »."""
        r = self.s.q("SELECT value FROM meta WHERE key='published_at'", one=True)
        return float(r["value"]) if r else None

    def brand_names(self):
        """Les marques du catalogue publié (pour comprendre une phrase), relues à chaque publication."""
        at = self.published_at()
        if self._brands[0] != at:
            self._brands = (at, [r["brand"] for r in self.s.q("SELECT DISTINCT brand FROM catalog WHERE brand IS NOT NULL")])
        return self._brands[1]

    def verdicts(self, d):
        """Les faits et les verdicts gardés pour le domaine d, le temps d'une publication (journey.Verdicts)."""
        at = self.published_at()
        if self._verdicts[0] != at:
            self._verdicts = (at, {})
        return self._verdicts[1].setdefault(d.key, journey.Verdicts(d))

    def attrs_of(self, rows):
        """Les caractéristiques (JSON de catalog.attrs) des lignes données, lues une fois par publication."""
        at = self.published_at()
        if self._attrs[0] != at:
            self._attrs = (at, {})
        memo = self._attrs[1]
        return [memo.get(r["product_id"]) or memo.setdefault(r["product_id"], enrich(json.loads(r["attrs"] or "{}"), r)) for r in rows]

    def search(self, uid=None, q=None, category=None, lo=None, hi=None, off=None, sort=None, recent=(), low=False, prof=None,
               brand=None, features=(), attrs=None, room=None, domain=None, sub=None, needs=(), props=None, noq=False):
        """La Recherche répond à une intention précise, dans tout le catalogue suivi (pas seulement les remises).

        q est une phrase comprise (query.read) : « aspirateur balai sans fil sous 300 € » donne un rayon, des fonctions, un
        budget ; les critères choisis dans l'app (category, brand, features, attrs, lo ≤ prix ≤ hi, off : remise minimale,
        low : prix parmi les plus bas depuis longtemps, `cheap`) l'emportent sur ce que dit la phrase. Les mots qui restent
        (« velours ») filtrent s'ils trouvent quelque chose, sinon ils sont signalés (ignored) et la réponse garde le reste ;
        une phrase dont rien n'est compris est cherchée mot à mot (chaque mot doit commencer un mot du produit). Rien sous
        le budget : les plus proches au-dessus, du moins cher au plus cher (relaxed). offs : combien de produits pour chaque
        palier de promo et pour « prix bas », avant le filtre de promo ; categories : combien par catégorie, avant le
        filtre de catégorie (les filtres disent ce que chaque choix donnera).
        Tri : pertinence (`relevance`), prix croissant (« pas cher »), ou remise. Sans mot ni filtre, le feed : les
        produits des recherches récentes de la personne en tête (recent, gardées par son navigateur ; `lead`), puis, avec
        des goûts connus (prof), ceux de ses rayons et de ses marques, un sur quatre pris ailleurs (`profile.blend`), puis
        tout le catalogue, une catégorie à tour de rôle (`breadth`) ; recent dans la réponse : les recherches qui ont
        orienté le feed. said : ce que la phrase seule demande (l'app en fait des critères à elle quand on touche une puce).

        Dans un domaine qui a son ontologie (les aspirateurs) : domain, sub (le type), props (caractéristiques exigées),
        needs (besoins). Le moteur de parcours (journey.py) classe par adéquation aux besoins puis par l'ordre demandé,
        écarte ce qu'un besoin éliminatoire exclut (excluded, avec la raison), explique chaque carte (why : critère, verdict,
        fait, source) ; question : la question utile si la demande est vague (noq : la personne a passé les questions) ;
        suggest : un autre type quand celui demandé ne peut pas répondre à un besoin ; exact : la référence demandée."""
        said = query.read(q, self.brand_names()) if q else query.read("")
        d = ontology.domain_of(category) if category else ontology.DOMAINS.get(domain or said["domain"])
        if category and d:                                 # un rayon d'un domaine à ontologie : le domaine, et son type s'il en est un
            sub = sub or next((x["key"] for x in d.subs if x["match"]["category"] == [category] and not x["match"].get("any")), None)
            category, domain = None, d.key
        crit = {"category": category or (None if domain else said["category"]),
                "room": None if category or d else room or said["room"], "brand": brand or said["brand"],
                "features": sorted(set(features) | set(said["features"])), "attrs": {**said["attrs"], **(attrs or {})},
                "min_price": lo if lo is not None else said["min_price"], "max_price": hi if hi is not None else said["max_price"],
                "off": off or said["off"], "low": bool(low or said["low"]), "sort": sort or said["sort"] or "relevance",
                "domain": d.key if d else None, "sub": (sub or said["sub"]) if d else None,
                "needs": list(dict.fromkeys(list(needs) + said["needs"])) if d else [],
                "props": {**said["props"], **(props or {})} if d else {}}
        understood = any(crit[k] for k in ("category", "room", "brand", "features", "attrs", "off", "low", "domain")) or \
            crit["min_price"] is not None or crit["max_price"] is not None
        words = said["rest"]
        feed = not q and not understood
        followed, saved = self._personal(uid)
        prof = self._profile(prof if feed else None, followed)
        spec = {"brand": crit["brand"], "features": crit["features"], "attrs": crit["attrs"], "domain": crit["domain"], "sub": crit["sub"],
                "props": crit["props"]}
        detailed = bool(crit["features"] or crit["attrs"] or d)
        near = sorted({crit["category"]} if crit["category"] else set(d.categories) if d else ()) if detailed else []
        rows = self.s.q("SELECT product_id, pct, brand, price, category, search, level, span, usual" + (", attrs" if detailed else "")
                        + " FROM catalog" + (f" WHERE category IN ({','.join('?' * len(near))})" if near else ""), near)
        if detailed:                                       # fonctions et tailles : lues pour les seuls produits du rayon
            rows = [{**r, "attrs": a} for r, a in zip(rows, self.attrs_of(rows))]
        toks = tokens(" ".join(words))
        promo = lambda r: (not crit["off"] or r["pct"] >= crit["off"]) and (not crit["low"] or cheap(r))

        rayons = {crit["category"]} if crit["category"] else set(d.categories) if d else set(ROOMS[crit["room"]][1]) if crit["room"] in ROOMS else None
        within = lambda rs: [r for r in rs if rayons is None or r["category"] in rayons]

        fit = query.fitter(spec)

        def select(top, fit=fit):
            base = [r for r in rows if (crit["min_price"] is None or r["price"] >= crit["min_price"]) and (top is None or r["price"] <= top)
                    and (not crit["brand"] or (r["brand"] or "").lower() == crit["brand"].lower()) and (not detailed or fit(r))]
            return base, within(base)

        base, here = select(crit["max_price"])
        ignored, exact = [], None
        if toks:
            hit = [r for r in base if matches(r["search"], toks)]
            if within(hit) or not understood:               # rien n'est compris : la phrase est cherchée mot à mot
                base, here = hit, within(hit)
                refs = [w for w in words if query.REF_RE.match(w)]
                if (refs or crit["brand"]) and len(here) == 1:   # « Zephyr V15 », « S109 », « Kessler Aero » : la référence demandée, seule
                    exact = here[0]["product_id"]
            else:
                ignored, words, toks = words, [], []       # « dyson » : rien de tel ; le reste de la demande tient
        hits = [r for r in here if promo(r)] if not said["unsupported"] else []
        relaxed = None
        if not hits and crit["max_price"] is not None and not said["unsupported"]:
            _, over = select(None)                         # rien sous le budget : les plus proches au-dessus
            over = sorted((r for r in over if promo(r) and (not toks or matches(r["search"], toks))), key=lambda r: (r["price"], r["product_id"]))
            if over:
                hits, relaxed = over, {"max_price": crit["max_price"], "from": over[0]["price"]}
        facet = Counter(r["category"] for r in base if promo(r))
        offs = {**{str(k): sum(r["pct"] >= k for r in here) for k in PROMO_STEPS}, "low": sum(cheap(r) for r in here)}
        score = lambda r: r["pct"] * prof.boost(r["category"], r["brand"])
        order = (lambda r: (r["price"], r["product_id"])) if relaxed or crit["sort"] == "price" else \
            (lambda r: (-r["pct"], r["price"], r["product_id"])) if crit["sort"] == "discount" else relevance(toks, score)
        used, judged, journey_out = [], {}, {}
        if d:                                              # le moteur de parcours : besoins, type, questions
            hits, judged, journey_out = self._journey(d, crit, said, hits, order, spec, select, promo, toks, noq, words)
        elif relaxed:
            pass                                           # déjà du moins cher au plus cher
        elif crit["sort"] in ("price", "discount"):
            hits.sort(key=order)
        elif feed:
            head, used = lead(hits, recent, score)
            seen = {r["product_id"] for r in head}
            rest = [r for r in hits if r["product_id"] not in seen]
            yours = P.diversify(sorted(P.mine(rest, prof), key=lambda r: (r["pct"] <= 0, -score(r), -prof.direct(r["category"], r["brand"]),
                                                                          r["price"], r["product_id"])))
            taken = {r["product_id"] for r in yours}
            hits = head + P.blend(yours, breadth([r for r in rest if r["product_id"] not in taken], relevance(toks, score)))
        else:
            hits.sort(key=order)
        out = self._page(hits, score, uid, followed, saved)
        if judged:
            for c in out["products"]:
                j = judged.get(c["id"])
                if j:
                    c["why"] = j["why"][:journey.WHY_SHOWN]
        out["categories"] = sorted(({"key": k, "label": CATEGORY_LABEL.get(k, k), "count": n} for k, n in facet.items()),
                                   key=lambda c: (-c["count"], c["label"]))
        crit["words"] = words
        out["recent"], out["offs"], out["personal"] = used, offs, prof.personal      # hors du feed : jamais personnel
        out["criteria"], out["chips"], out["words"], out["ignored"] = crit, query.chips(crit), words, ignored
        out["unsupported"] = CATEGORY_LABEL.get(said["unsupported"]) if said["unsupported"] else None
        out["relaxed"] = relaxed
        out["options"] = self._options(crit, toks, promo, relaxed, rayons, d) if rayons else None
        out["said"] = {k: said[k] for k in ("category", "room", "brand", "features", "attrs", "min_price", "max_price", "off", "low", "sort",
                                            "domain", "sub", "needs", "props")}
        out["exact"] = exact
        out["domain"] = {"key": d.key, "label": d.label} if d else None
        out["needs"] = [{"key": k, "label": d.needs[k]["label"], "say": d.needs[k]["say"], "from": said["said_needs"].get(k, [])}
                        for k in crit["needs"] if k in d.needs] if d else []
        out["question"], out["suggest"] = journey_out.get("question"), journey_out.get("suggest")
        out["excluded"], out["conflicts"] = journey_out.get("excluded"), journey_out.get("conflicts", [])
        return out

    def _journey(self, d, crit, said, hits, order, spec, select, promo, toks, noq, words):
        """Le domaine à ontologie : classer par adéquation aux besoins (journey.Plan), écarter ce qu'un besoin
        éliminatoire exclut, poser la question utile si la demande est vague, proposer un autre type si celui demandé ne
        peut pas répondre à un besoin. → (produits classés, jugements, {plan, question, suggest, excluded, conflicts})"""
        clash = journey.conflict(d, crit["sub"], crit["needs"])
        plan = journey.Plan(d, crit["needs"], drop={c for c, _, _ in journey.conflict(d, crit["sub"], crit["needs"], weak=True)})   # dit à part
        out = {"plan": plan, "conflicts": [{"c": c, "why": why} for c, why, _ in clash]}
        judged, verdicts = {}, self.verdicts(d)
        if plan:
            hits, judged, dropped = plan.rank(hits, order, verdicts)
            if dropped:
                why, n = max(dropped.items(), key=lambda kv: kv[1])
                out["excluded"] = {"count": sum(dropped.values()), "why": why}
        else:
            hits.sort(key=order)
        if clash:                                          # un autre type, pour un besoin que celui-ci ne peut pas satisfaire
            free = query.fitter({**spec, "sub": None})
            _, pool = select(crit["max_price"], fit=free)
            count = Counter((r["attrs"] or {}).get("sub") for r in pool if promo(r) and (not toks or matches(r["search"], toks)))
            out["suggest"] = journey.suggest(d, crit["sub"], crit["needs"], count)
        phrase = said["sub"] or said["needs"] or said["props"] or said["attrs"] or said["features"] or said["brand"] or words
        app = crit["needs"] or crit["props"] or crit["attrs"] or crit["features"] or crit["brand"]
        if not noq and not phrase and not app and hits:   # une demande vague : la question utile, si elle change la sélection
            for when in ("sub", "need"):                   # le type d'abord (un type choisi : aucune réponse ne le changerait), puis l'usage
                out["question"] = journey.question(d, hits, [r["product_id"] for r in hits[:journey.TOP]], order, when, verdicts)
                if out["question"]:
                    break
        return hits, judged, out

    def _options(self, crit, toks, promo, relaxed, rayons, d=None):
        """Affiner une recherche dans un rayon : les fonctions, les tailles ou capacités et les marques qui y existent (dans
        une pièce : les marques). Chaque choix dit combien de produits la recherche donnerait avec lui, ses autres critères
        gardés (budget, promo, mots, fonctions, tailles, marque) : un choix qui ne donne rien, ou qui ne change rien, n'est
        pas proposé, sauf s'il est déjà pris (pour pouvoir le retirer). Dans un domaine à ontologie (d) : le type, les
        usages (besoins) et les caractéristiques qui comptent pour ce type, dans l'ordre où elles décident."""
        category, chosen, feats, brand = crit["category"], crit["attrs"], set(crit["features"]), crit["brand"]
        top = None if relaxed else crit["max_price"]          # rien sous le budget : les plus proches, au-dessus, sont montrés
        cats = sorted(rayons)
        found = [r for r in self.s.q(f"SELECT product_id, brand, price, pct, level, span, usual, search, attrs, category FROM catalog WHERE category "
                                     f"IN ({','.join('?' * len(cats))})", cats)
                 if (crit["min_price"] is None or r["price"] >= crit["min_price"]) and (top is None or r["price"] <= top) and promo(r)
                 and (not toks or matches(r["search"], toks))]
        rows = []
        for r, a in zip(found, self.attrs_of(found)):
            ok = {k: query.satisfies(k, a.get(k), v) for k, v in chosen.items()}       # chaque taille demandée, une fois
            rows.append({"brand": r["brand"], "attrs": a, "ok": ok, "a": all(ok.values()), "product_id": r["product_id"],
                         "b": not brand or (r["brand"] or "").lower() == brand.lower(), "f": feats <= set(a.get("features", ()))})
        if d:
            return self._domain_options(d, crit, rows)
        now = sum(p["b"] and p["f"] and p["a"] for p in rows)
        fcount = Counter(f for p in rows if p["b"] and p["f"] and p["a"] for f in p["attrs"].get("features", ()) if f in FEATURE_LABEL)
        features = [{"key": f, "label": FEATURE_LABEL[f], "count": fcount[f]}
                    for f in sorted(set(fcount) | (feats & set(FEATURE_LABEL)), key=lambda f: (-fcount[f], f))
                    if f in feats or 0 < fcount[f] < now] if category else []
        attrs = {}
        for k in OPTION_ATTRS if category else ():
            if category not in query.ONLY.get(k, {category}):
                continue
            pool = [p for p in rows if p["b"] and p["f"] and all(ok for x, ok in p["ok"].items() if x != k)]   # la recherche sans cette taille
            have = Counter(p["attrs"][k] for p in pool if p["attrs"].get(k) is not None)                      # quelques valeurs distinctes
            count = {v: sum(n for a, n in have.items() if query.satisfies(k, a, v)) for v in have}
            keep = [v for v, n in count.items() if 0 < n < len(pool) or chosen.get(k) == v]
            if chosen.get(k) is not None and chosen[k] not in keep:
                keep.append(chosen[k]); count[chosen[k]] = 0
            order = sorted(keep, key=lambda v: (query.energy_rank(v) or 0) if k == "energy_class" else
                           [int(x) for x in re.findall(r"\d+", v)] if k == "bed_size" else v)
            if order:
                attrs[k] = {"title": OPTION_ATTRS[k], "values": [{"value": v, "label": query.ATTR_CHIP[k](v), "count": count[v]} for v in order][:8]}
        bcount = Counter(p["brand"] for p in rows if p["f"] and p["a"] and p["brand"])
        if brand and not any(b.lower() == brand.lower() for b in bcount):
            bcount[brand] = 0
        brands = [{"name": b, "count": n} for b, n in sorted(bcount.items(), key=lambda x: (-x[1], x[0]))]
        return {"features": features, "attrs": attrs, "brands": brands}

    def _domain_options(self, d, crit, rows):
        """Affiner dans un domaine à ontologie : Type (chaque sous-famille, les autres critères gardés), Usage (les besoins
        qui ont des produits qui leur conviennent tout à fait), les caractéristiques qui décident pour ce type (oui/non, avec
        leur nombre de produits ; fait ou déduction), poids, bruit et autonomie par paliers, les marques."""
        sub, props, needs = crit["sub"], crit["props"], crit["needs"]
        verdicts = self.verdicts(d)
        if sub in d.sub:                                   # ce qui décide pour ce type ; sans type, ce qui compte pour la plupart
            keys = d.sub[sub]["decision"]
        else:
            seen = Counter(k for s in d.subs for k in s["decision"])
            keys = [k for k in dict.fromkeys(k for s in d.subs for k in s["decision"]) if seen[k] >= 3]
        keys = keys + [k for k in props if k not in keys]  # une caractéristique exigée reste proposée, pour la retirer
        look = set(keys)
        info = []                                          # une fois par produit : ses valeurs, ce qu'il manque des exigences
        for p in rows:
            f = verdicts.facts(p["product_id"], p["attrs"])
            vals = {k: f[k][0] for k in look if k in f}
            info.append((p, vals, [k for k, v in props.items() if vals.get(k) != v], not sub or p["attrs"].get("sub") == sub,
                         p["b"] and p["f"] and p["a"]))
        mine = [p for p, _, bad, _, ok in info if ok and not bad]
        here = [p for p, _, bad, same, ok in info if ok and not bad and same]
        scount = Counter(p["attrs"].get("sub") for p in mine)
        subs = [{"key": s["key"], "label": s["plural"], "count": scount[s["key"]]} for s in d.subs if scount[s["key"]] or s["key"] == sub]
        usage = []
        for n in d.needs.values():
            good = len(verdicts.good(n["key"], here))
            if good or n["key"] in needs:
                usage.append({"key": n["key"], "label": n["label"], "count": good})
        bools = []
        for k in keys:
            prop = d.props[k]
            if prop["type"] != "bool":
                continue
            pool = [vals for p, vals, bad, same, ok in info if ok and same and (not bad or bad == [k])]
            for v in ((True, False) if prop.get("words") and False in prop["words"].values() else (True,)):
                n = sum(vals.get(k) == v for vals in pool)
                if 0 < n < len(pool) or props.get(k) == v:
                    bools.append({"key": k, "value": v, "label": prop["yes" if v else "no"], "count": n})
        steps = {}
        for k, values in (("weight_kg", (1.5, 2, 2.5, 3, 4)), ("noise_db", (65, 70, 75)), ("autonomy_min", (30, 45, 60, 90, 150))):
            if k not in keys and k not in crit["attrs"]:
                continue
            pool = [p["attrs"].get(k) for p, _, bad, same, _ in info if p["b"] and p["f"] and not bad and same
                    and all(good for y, good in p["ok"].items() if y != k)]
            known = [a for a in pool if a is not None]
            count = {v: sum(a <= v for a in known) if k in query.AT_MOST else sum(a >= v for a in known) for v in values}
            shown = [v for v in values if 0 < count[v] < len(pool) or crit["attrs"].get(k) == v]
            if shown:
                steps[k] = {"title": d.props[k]["label"], "values": [{"value": v, "label": query.ATTR_CHIP[k](v), "count": count[v]} for v in shown]}
        bcount = Counter(p["brand"] for p, _, bad, same, _ in info if p["f"] and p["a"] and not bad and same and p["brand"])
        brand = crit["brand"]
        if brand and not any(b.lower() == brand.lower() for b in bcount):
            bcount[brand] = 0
        brands = [{"name": b, "count": n} for b, n in sorted(bcount.items(), key=lambda x: (-x[1], x[0]))]
        return {"features": [], "attrs": steps, "brands": brands, "subs": subs, "needs": usage, "props": bools}

    def explore(self, domain=None):
        """Explorer, sans rien configurer : les domaines qui ont leur ontologie (ou celui demandé) — chemin, nombre de
        produits, prix de départ, remises ; chacune de ses sous-familles (combien, dès quel prix, ce qu'elle fait de mieux,
        et le produit de sa meilleure remise pour l'illustrer) ; les usages qui ont des produits qui leur conviennent tout
        à fait, et combien."""
        doms = [ontology.DOMAINS[domain]] if domain else list(ontology.DOMAINS.values())
        if domain and domain not in ontology.DOMAINS:
            raise NotFound("domaine inconnu")
        out = []
        for d in doms:
            cats = list(d.categories)
            rows = self.s.q(f"SELECT product_id, category, price, pct, search, attrs FROM catalog WHERE category IN "
                            f"({','.join('?' * len(cats))})", cats)
            rows = [{**r, "attrs": a} for r, a in zip(rows, self.attrs_of(rows))]
            subs = []
            for x in d.subs:
                mine = [r for r in rows if r["attrs"].get("sub") == x["key"]]
                if not mine:
                    continue
                best = min(mine, key=lambda r: (-r["pct"], r["price"], r["product_id"]))
                subs.append({"key": x["key"], "label": x["plural"], "pitch": x["pitch"], "count": len(mine),
                             "from": min(r["price"] for r in mine), "art": best["category"], "seed": best["product_id"]})
            item = {"key": d.key, "label": d.label, "path": d.path, "count": len(rows), "deals": sum(r["pct"] > 0 for r in rows),
                    "from": min((r["price"] for r in rows), default=None), "subs": subs}
            needs, verdicts = [], self.verdicts(d)
            for n in d.needs.values():
                good = len(verdicts.good(n["key"], rows))
                if good:
                    needs.append({"key": n["key"], "label": n["label"], "count": good})
            item["needs"] = needs
            out.append(item)
        return out[0] if domain else {"domains": out}

    def foryou(self, uid=None, prof=None):
        """« Pour vous », sur l'accueil : les deals et les prix bas de vos rayons et de vos marques (affinité directe d'au
        moins 0,3), les meilleurs d'abord selon l'intérêt du deal × vos goûts, deux au plus d'un même rayon sur quatre,
        TOP_LIMIT au plus ; rien sans goûts connus. taste : ce que l'app a compris, pour le dire."""
        followed, saved = self._personal(uid)
        prof = self._profile(prof, followed)
        rows = self.s.q("SELECT product_id, pct, brand, category, price, level, span, usual FROM catalog")
        value = lambda r: r["pct"] if r["pct"] > 0 else round(100 * (r["usual"] - r["price"]) / r["usual"])
        good = [r for r in P.mine(rows, prof) if r["pct"] > 0 or cheap(r)]
        picked = P.diversify(sorted(good, key=lambda r: (-value(r) * prof.boost(r["category"], r["brand"]), r["price"],
                                                         r["product_id"])))[:TOP_LIMIT]
        full = {r["product_id"]: r for r in self.s.q(f"SELECT * FROM catalog WHERE product_id IN ({','.join('?' * len(picked))})",
                                                     [r["product_id"] for r in picked])} if picked else {}
        return {"products": [{**self._card(full[r["product_id"]], followed, saved),
                              "why": {"pct": r["pct"], "low": r["level"] if cheap(r) else None, "days": r["span"] if cheap(r) else None}}
                             for r in picked], "taste": self.taste(prof)}

    def taste(self, prof):
        """Ce que l'app a compris des goûts, pour le dire et le corriger : rayons (choisis ou vus) et marques (suivies ou
        vues) d'affinité directe d'au moins 0,3, les plus forts d'abord (quatre rayons, trois marques au plus)."""
        if not prof.personal:
            return {"cats": [], "brands": [], "personal": False}
        cats = sorted(((a, c) for c, a in prof.cats.items() if a >= P.MINE), key=lambda x: (-x[0], x[1]))[:4]
        brands = sorted(((a, b) for b, a in prof.brands.items() if a >= P.MINE), key=lambda x: (-x[0], x[1]))[:3]
        return {"cats": [{"key": c, "label": CATEGORY_LABEL.get(c, c), "chosen": a >= 1} for a, c in cats],   # choisi : 1 ; vu : 0,8 au plus
                "brands": [{"name": b, "chosen": a >= 1} for a, b in brands], "personal": True}

    def _page(self, hits, score, uid, followed, saved):
        """Lignes complètes et cartes pour le seul haut de liste montré."""
        top = hits[:TODAY_LIMIT]
        full = {r["product_id"]: r for r in self.s.q(f"SELECT * FROM catalog WHERE product_id IN ({','.join('?' * len(top))})",
                                                     [r["product_id"] for r in top])} if top else {}
        cards = [{**self._card(full[r["product_id"]], followed, saved), "score": score(r)} for r in top]
        return {"products": cards, "total": len(hits), "signed_in": uid is not None}

    def categories(self, every=False):
        """Catégories avec des remises aujourd'hui (count, best) ; every : aussi celles sans remise (onglet Recherche).
        products : nombre de produits suivis."""
        rows = self.s.q("SELECT category, COUNT(*) products, SUM(pct > 0) n, MAX(pct) best FROM catalog GROUP BY category")
        out = [{"key": r["category"], "label": CATEGORY_LABEL.get(r["category"], r["category"]), "count": r["n"], "best": r["best"],
                "products": r["products"], "family": FAMILY_OF.get(r["category"]),
                "family_label": FAMILY_LABEL.get(FAMILY_OF.get(r["category"]))} for r in rows if every or r["n"]]
        return sorted(out, key=lambda e: (-e["count"], e["label"] or ""))

    def brands(self, uid=None, every=False):
        """Marques avec des remises aujourd'hui : combien (count), la meilleure (best), dans quelles catégories, et le
        produit de la meilleure remise (top : le visuel de la carte) ; every : aussi celles sans remise (on entre par
        la marque depuis l'onglet Recherche). products : nombre de produits suivis."""
        followed, _ = self._personal(uid)
        rows = self.s.q("SELECT brand, COUNT(*) products, SUM(pct > 0) n, MAX(pct) best FROM catalog WHERE brand IS NOT NULL GROUP BY brand")
        top, cats = {}, defaultdict(list)
        for r in self.s.q("SELECT brand, product_id, category FROM catalog WHERE pct > 0 AND brand IS NOT NULL ORDER BY pct DESC, product_id"):
            top.setdefault(r["brand"], {"id": r["product_id"], "category": r["category"]})
            label = CATEGORY_LABEL.get(r["category"], r["category"])
            if label not in cats[r["brand"]]:
                cats[r["brand"]].append(label)
        out = [{"name": r["brand"], "count": r["n"], "best": r["best"], "products": r["products"], "followed": r["brand"] in followed,
                "top": top.get(r["brand"]), "categories": cats.get(r["brand"], [])} for r in rows if every or r["n"]]
        return sorted(out, key=lambda e: (-e["followed"], -e["count"], e["name"]))

    def brand(self, uid, name):
        """Tout ce que la marque a dans le catalogue suivi, les remises d'abord : depuis une fiche, on continue par la
        marque, même quand elle n'a aucune remise aujourd'hui."""
        followed, saved = self._personal(uid)
        rows = self.s.q("SELECT * FROM catalog WHERE brand=? ORDER BY pct > 0 DESC, pct DESC, price, product_id LIMIT ?",
                        (name, TODAY_LIMIT))
        if not rows:
            raise NotFound("marque inconnue")
        return {"brand": name, "followed": name in followed, "deals": sum(r["pct"] > 0 for r in rows),
                "products": [self._card(r, followed, saved) for r in rows]}

    def category(self, uid, key):
        """Tous les produits d'une catégorie, les remises d'abord, puis du moins cher au plus cher."""
        followed, saved = self._personal(uid)
        rows = self.s.q("SELECT * FROM catalog WHERE category=? ORDER BY pct > 0 DESC, pct DESC, price, product_id LIMIT ?",
                        (key, TODAY_LIMIT))
        if not rows:
            raise NotFound("catégorie inconnue")
        return {"key": key, "label": CATEGORY_LABEL.get(key, key), "kind": CATEGORY_ONE.get(key, key),
                "deals": sum(r["pct"] > 0 for r in rows), "products": [self._card(r, followed, saved) for r in rows]}

    def cards(self, uid, rows):
        """Cartes d'autres modules (missions), avec les signets et marques suivies de la personne."""
        followed, saved = self._personal(uid)
        return [self._card(r, followed, saved) for r in rows]

    def item(self, uid, product_id):
        r = self.s.q("SELECT * FROM catalog WHERE product_id=?", (product_id,), one=True)
        if not r:
            raise NotFound("produit inconnu")
        followed, saved = self._personal(uid)
        offers = [{"offer_id": o["offer_id"], "merchant": o["merchant"], "price": o["price"], "was": o["was"], "pct": o["pct"],
                   "availability": o["availability"], "best": o["rank"] == 0}
                  for o in self.s.q("SELECT * FROM catalog_offers WHERE product_id=? ORDER BY rank", (product_id,))]
        similar = self.s.q("SELECT c.* FROM similar s JOIN catalog c ON c.product_id=s.other_id WHERE s.product_id=? ORDER BY s.rank",
                           (product_id,))
        cheaper = self.s.q("SELECT c.* FROM alternatives a JOIN catalog c ON c.product_id=a.other_id WHERE a.product_id=? "
                           "ORDER BY a.rank", (product_id,))
        history = json.loads(r["history"] or "null")
        attrs = json.loads(r["attrs"] or "{}")
        return {**self._card(r, followed, saved), "history": history, "position": position(history, r["price"]),
                "attrs": attrs, "offers": offers,
                "similar": [self._card(x, followed, saved) for x in similar],
                "alternatives": [{**self._card(x, followed, saved), "saving": round(r["price"] - x["price"])} for x in cheaper],
                "signed_in": uid is not None, **self._essentials(r, attrs)}

    @staticmethod
    def _essentials(r, attrs):
        """La fiche d'un produit d'un domaine à ontologie : son type, et ce qui décide pour ce type, dans l'ordre où ça
        décide — chaque caractéristique avec sa valeur et sa source (fiche, titre, nom du modèle, déduite, selon le
        type), ou « non précisé » : une donnée manquante reste dite manquante."""
        d = ontology.domain_of(r["category"])
        if d is None:
            return {}
        a = enrich(attrs, r)
        facts, sub = d.facts(a), a.get("sub")
        def say(k):
            p, v = d.props[k], facts[k][0]
            if p["type"] == "bool":
                return (p["yes"] if v else p["no"]) if p.get("show") == "label" else "Oui" if v else "Non"
            return p["format"].format(ontology.show(v)) if p["type"] == "number" else ontology.show(v, p)
        keys = d.sub[sub]["decision"] if sub in d.sub else []
        return {"sub": {"key": sub, "label": d.sub[sub]["one"]} if sub in d.sub else None,
                "facts": [{"key": k, "label": d.props[k]["label"], "value": say(k) if k in facts else None,
                           "src": facts[k][1] if k in facts else None} for k in keys],
                "read_at": a.get("_at")}

    def saves(self, uid):
        """Favoris : montrés même sans remise du jour (le prix reste utile), le plus récent d'abord, avec le prix du
        catalogue au moment où le favori a été posé (pour montrer une baisse)."""
        followed, saved = self._personal(uid)
        rows = self.s.q("SELECT c.*, s.price AS saved_price FROM saves s JOIN catalog c ON c.product_id=s.product_id "
                        "WHERE s.user_id=? ORDER BY s.created_at DESC, s.product_id", (uid,))
        return {"products": [{**self._card(r, followed, saved), "saved_price": r["saved_price"]} for r in rows]}
