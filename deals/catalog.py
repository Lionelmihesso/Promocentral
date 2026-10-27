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

from . import ontology
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
    """Une fiche publiée avant l'ontologie de son domaine (sans sous-catégorie) : la sous-catégorie déduite de son texte
    cherchable (le titre), en attendant la publication suivante, qui la relit."""
    d = ontology.domain_of(r.get("category"))
    if d is not None and "sub" not in a:
        a = {**a, "sub": d.sub_of(r["category"], (r.get("search") or "").strip())}
    return a


def matches(search, toks):
    """Chaque mot doit commencer un mot du produit ; un synonyme de plusieurs mots (« lave linge ») est cherché tel quel."""
    return all((t in search) if " " in t else (f" {t}" in search) for t in toks)


class Catalog:
    def __init__(self, store):
        self.s = store
        self._brands = ("?", [])                           # marques du catalogue, le temps d'une publication (« ? » : pas encore lues)
        self._attrs = ("?", {})                            # caractéristiques lues des produits publiés, le temps d'une publication

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

    def attrs_of(self, rows):
        """Les caractéristiques (JSON de catalog.attrs) des lignes données, lues une fois par publication."""
        at = self.published_at()
        if self._attrs[0] != at:
            self._attrs = (at, {})
        memo = self._attrs[1]
        return [memo.get(r["product_id"]) or memo.setdefault(r["product_id"], enrich(json.loads(r["attrs"] or "{}"), r)) for r in rows]

    def search(self, uid=None, q=None, category=None, lo=None, hi=None, off=None, sort=None, recent=(), low=False, prof=None,
               brand=None, features=(), attrs=None, room=None, domain=None, sub=None, props=None):
        """La Recherche répond à une intention précise, dans tout le catalogue suivi (pas seulement les remises).

        q est une phrase comprise (query.read) : « aspirateur balai sans fil sous 300 € » donne un rayon, un type, des
        attributs, un budget ; les critères choisis dans l'app (category, brand, features, attrs, lo ≤ prix ≤ hi, off :
        remise minimale, low : prix parmi les plus bas depuis longtemps, `cheap` ; dans un domaine qui a son ontologie :
        domain, sub — le type —, props — les attributs exigés) l'emportent sur ce que dit la phrase. Les mots qui restent
        (« velours ») filtrent s'ils trouvent quelque chose, sinon ils sont signalés (ignored) et la réponse garde le reste ;
        une phrase dont rien n'est compris est cherchée mot à mot (chaque mot doit commencer un mot du produit). Rien sous
        le budget : les plus proches au-dessus, du moins cher au plus cher (relaxed). offs : combien de produits pour chaque
        palier de promo et pour « prix bas », avant le filtre de promo ; categories : combien par catégorie, avant le
        filtre de catégorie (les filtres disent ce que chaque choix donnera).
        Tri : pertinence (`relevance`), prix croissant (« pas cher »), ou remise. Sans mot ni filtre, le feed : les
        produits des recherches récentes de la personne en tête (recent, gardées par son navigateur ; `lead`), puis, avec
        des goûts connus (prof), ceux de ses rayons et de ses marques, un sur quatre pris ailleurs (`profile.blend`), puis
        tout le catalogue, une catégorie à tour de rôle (`breadth`) ; recent dans la réponse : les recherches qui ont
        orienté le feed. said : ce que la phrase seule demande (l'app en fait des critères à elle quand on touche une puce)."""
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

        def select(top):
            base = [r for r in rows if (crit["min_price"] is None or r["price"] >= crit["min_price"]) and (top is None or r["price"] <= top)
                    and (not crit["brand"] or (r["brand"] or "").lower() == crit["brand"].lower()) and (not detailed or fit(r))]
            return base, within(base)

        base, here = select(crit["max_price"])
        ignored = []
        if toks:
            hit = [r for r in base if matches(r["search"], toks)]
            if within(hit) or not understood:               # rien n'est compris : la phrase est cherchée mot à mot
                base, here = hit, within(hit)
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
        used = []
        if relaxed:
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
        out["categories"] = sorted(({"key": k, "label": CATEGORY_LABEL.get(k, k), "count": n} for k, n in facet.items()),
                                   key=lambda c: (-c["count"], c["label"]))
        crit["words"] = words
        out["recent"], out["offs"], out["personal"] = used, offs, prof.personal      # hors du feed : jamais personnel
        out["criteria"], out["chips"], out["words"], out["ignored"] = crit, query.chips(crit), words, ignored
        out["unsupported"] = CATEGORY_LABEL.get(said["unsupported"]) if said["unsupported"] else None
        out["relaxed"] = relaxed
        out["options"] = self._options(crit, toks, promo, relaxed, rayons, d) if rayons else None
        out["said"] = {k: said[k] for k in ("category", "room", "brand", "features", "attrs", "min_price", "max_price", "off", "low", "sort",
                                            "domain", "sub", "props")}
        out["domain"] = {"key": d.key, "label": d.label} if d else None
        return out

    def _options(self, crit, toks, promo, relaxed, rayons, d=None):
        """Affiner une recherche dans un rayon : les fonctions, les tailles ou capacités et les marques qui y existent (dans
        une pièce : les marques). Chaque choix dit combien de produits la recherche donnerait avec lui, ses autres critères
        gardés (budget, promo, mots, fonctions, tailles, marque) : un choix qui ne donne rien, ou qui ne change rien, n'est
        pas proposé, sauf s'il est déjà pris (pour pouvoir le retirer). Dans un domaine à ontologie (d) : le type et les
        quelques attributs qui comptent pour lui."""
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
        """Affiner dans un domaine à ontologie : le type (chaque sous-catégorie, les autres critères gardés), puis ses
        attributs (sans fil, sans sac : oui ou non), chacun avec ce qu'il donnerait, et les marques. Sans type : les
        attributs communs à plusieurs types."""
        sub, props = crit["sub"], crit["props"]
        if sub in d.sub:
            keys = list(d.sub[sub]["attributes"])
        else:
            seen = Counter(k for s in d.subs for k in s["attributes"])
            keys = [k for k in dict.fromkeys(k for s in d.subs for k in s["attributes"]) if seen[k] >= 2]
        keys += [k for k in props if k not in keys]        # un attribut exigé reste proposé, pour le retirer
        info = []                                          # une fois par produit : ce qu'on sait, ce qu'il manque des exigences
        for p in rows:
            f = d.facts(p["attrs"])
            info.append((p, f, [k for k, v in props.items() if f.get(k) != v], not sub or p["attrs"].get("sub") == sub,
                         p["b"] and p["f"] and p["a"]))
        mine = [p for p, _, bad, _, ok in info if ok and not bad]
        scount = Counter(p["attrs"].get("sub") for p in mine)
        order = [s["key"] for s in d.subs]                 # le nom court (dans le rayon, « Balai » suffit), les plus fournis d'abord
        subs = sorted(({"key": s["key"], "label": s["label"], "count": scount[s["key"]]} for s in d.subs if scount[s["key"]] or s["key"] == sub),
                      key=lambda x: (-x["count"], order.index(x["key"])))
        bools = []
        for k in keys:
            a = d.attrs[k]
            pool = [f for p, f, bad, same, ok in info if ok and same and (not bad or bad == [k])]
            for v in (True, False):
                n = sum(f.get(k) == v for f in pool)
                if 0 < n < len(pool) or props.get(k) == v:
                    bools.append({"key": k, "value": v, "label": a["yes" if v else "no"], "count": n})
        bcount = Counter(p["brand"] for p, _, bad, same, _ in info if p["f"] and p["a"] and not bad and same and p["brand"])
        brand = crit["brand"]
        if brand and not any(b.lower() == brand.lower() for b in bcount):
            bcount[brand] = 0
        brands = [{"name": b, "count": n} for b, n in sorted(bcount.items(), key=lambda x: (-x[1], x[0]))]
        return {"features": [], "attrs": {}, "brands": brands, "subs": subs, "props": bools}

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
                "signed_in": uid is not None}

    def saves(self, uid):
        """Favoris : montrés même sans remise du jour (le prix reste utile), le plus récent d'abord, avec le prix du
        catalogue au moment où le favori a été posé (pour montrer une baisse)."""
        followed, saved = self._personal(uid)
        rows = self.s.q("SELECT c.*, s.price AS saved_price FROM saves s JOIN catalog c ON c.product_id=s.product_id "
                        "WHERE s.user_id=? ORDER BY s.created_at DESC, s.product_id", (uid,))
        return {"products": [{**self._card(r, followed, saved), "saved_price": r["saved_price"]} for r in rows]}
