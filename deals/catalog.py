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

from . import profile as P
from .errors import NotFound
from .extract.categories import FAMILY_OF

TODAY_LIMIT = 60
POSITION_DAYS = 14                                         # en dessous, trop peu de relevés pour juger un prix
SORTS = ("relevance", "price", "discount")                 # Recherche : pertinence, prix croissant, remise
TOP_LIMIT = 10                                             # accueil : top deals (et « pour vous »)
TOP_SAME = 3                                               # top deals suivant les goûts : au plus trois places par rayon
LOW_DAYS = 60                                              # « depuis longtemps » : au moins 2 mois de prix relevés
LOW_DROP = 0.10                                            # et au moins 10 % sous le prix habituel
PROMO_STEPS = (1, 10, 20, 30, 40, 50)                      # filtre Promo : en promo, puis −10 % et plus, −20 %…
RECENT_SEARCHES = 4                                        # feed : les dernières recherches gardées par le navigateur
RECENT_EACH = 6                                            # feed : produits au plus par recherche récente, en tête
FAMILY_LABEL = {"electromenager": "Électroménager", "ameublement": "Ameublement", "literie": "Literie"}
CATEGORY_LABEL = {
    "lave_linge": "Lave-linge", "lave_linge_sechant": "Lave-linge séchants", "seche_linge": "Sèche-linge",
    "lave_vaisselle": "Lave-vaisselle", "refrigerateur": "Réfrigérateurs", "congelateur": "Congélateurs", "four": "Fours",
    "plaque_cuisson": "Plaques de cuisson", "hotte": "Hottes", "cuisiniere": "Cuisinières", "micro_ondes": "Micro-ondes",
    "machine_cafe": "Machines à café", "canape": "Canapés", "fauteuil": "Fauteuils", "lit": "Lits", "armoire": "Armoires",
    "table": "Tables", "buffet": "Buffets", "meuble_tv": "Meubles TV", "commode": "Commodes", "luminaire": "Luminaires",
    "matelas": "Matelas", "sommier": "Sommiers", "televiseur": "Téléviseurs", "smartphone": "Smartphones",
    "ordinateur_portable": "Ordinateurs portables", "casque_audio": "Casques", "enceinte": "Enceintes", "tablette": "Tablettes",
    "robot_aspirateur": "Robots aspirateurs", "aspirateur": "Aspirateurs", "montre_connectee": "Montres connectées"}
CATEGORY_ONE = {
    "lave_linge": "Lave-linge", "lave_linge_sechant": "Lave-linge séchant", "seche_linge": "Sèche-linge",
    "lave_vaisselle": "Lave-vaisselle", "refrigerateur": "Réfrigérateur", "congelateur": "Congélateur", "four": "Four",
    "plaque_cuisson": "Plaque de cuisson", "hotte": "Hotte", "cuisiniere": "Cuisinière", "micro_ondes": "Micro-ondes",
    "machine_cafe": "Machine à café", "canape": "Canapé", "fauteuil": "Fauteuil", "lit": "Lit", "armoire": "Armoire",
    "table": "Table", "buffet": "Buffet", "meuble_tv": "Meuble TV", "commode": "Commode", "luminaire": "Luminaire",
    "matelas": "Matelas", "sommier": "Sommier", "televiseur": "Téléviseur", "smartphone": "Smartphone",
    "ordinateur_portable": "Ordinateur portable", "casque_audio": "Casque", "enceinte": "Enceinte", "tablette": "Tablette",
    "robot_aspirateur": "Robot aspirateur", "aspirateur": "Aspirateur", "montre_connectee": "Montre connectée"}
FEATURE_LABEL = {"sans_fil": "Sans fil", "balai": "Balai", "traineau": "Traîneau", "laveur": "Laveur", "convertible": "Convertible",
                 "angle": "D'angle", "induction": "Induction", "encastrable": "Encastrable", "americain": "Américain",
                 "electrique": "Électrique"}
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


def matches(search, toks):
    """Chaque mot doit commencer un mot du produit ; un synonyme de plusieurs mots (« lave linge ») est cherché tel quel."""
    return all((t in search) if " " in t else (f" {t}" in search) for t in toks)


class Catalog:
    def __init__(self, store):
        self.s = store

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

    def search(self, uid=None, q=None, category=None, lo=None, hi=None, off=None, sort="relevance", recent=(), low=False, prof=None):
        """La Recherche répond à une intention précise, dans tout le catalogue suivi (pas seulement les remises).

        Filtres : catégorie, budget (lo ≤ prix ≤ hi), promo : remise minimale (off, en %) ou prix parmi les plus bas
        depuis longtemps (low, `cheap`) ; sans mot, les filtres suffisent. offs : combien de produits pour chaque palier
        de promo et pour « prix bas », avant le filtre de promo (le filtre dit ce que chaque choix donnera).
        Tri : pertinence (`relevance`), prix croissant, ou remise. Sans mot ni filtre, la pertinence donne le feed : les
        produits des recherches récentes de la personne en tête (recent, gardées par son navigateur ; `lead`), puis tout
        le catalogue, une catégorie à tour de rôle (`breadth`) ; avec des goûts connus (prof), après les recherches
        récentes, les produits de vos rayons et de vos marques, un sur quatre pris ailleurs (`profile.blend`) ; recent dans
        la réponse : les recherches qui ont orienté le feed. categories : combien de produits trouvés par catégorie, avant
        le filtre de catégorie (le filtre propose ce qui existe)."""
        toks = tokens(q) if q else []
        feed = not toks and not (category or lo is not None or hi is not None or off or low)
        followed, saved = self._personal(uid)
        prof = self._profile(prof if feed else None, followed)
        base = [r for r in self.s.q("SELECT product_id, pct, brand, price, category, search, level, span, usual FROM catalog")
                if (not toks or matches(r["search"], toks)) and (lo is None or r["price"] >= lo) and (hi is None or r["price"] <= hi)]
        promo = lambda r: (not off or r["pct"] >= off) and (not low or cheap(r))
        here = [r for r in base if not category or r["category"] == category]
        facet = Counter(r["category"] for r in base if promo(r))
        offs = {**{str(k): sum(r["pct"] >= k for r in here) for k in PROMO_STEPS}, "low": sum(cheap(r) for r in here)}
        hits = [r for r in here if promo(r)]
        score = lambda r: r["pct"] * prof.boost(r["category"], r["brand"])
        used = []
        if sort == "price":
            hits.sort(key=lambda r: (r["price"], r["product_id"]))
        elif sort == "discount":
            hits.sort(key=lambda r: (-r["pct"], r["price"], r["product_id"]))
        elif feed:
            head, used = lead(hits, recent, score)
            seen = {r["product_id"] for r in head}
            rest = [r for r in hits if r["product_id"] not in seen]
            yours = P.diversify(sorted(P.mine(rest, prof), key=lambda r: (r["pct"] <= 0, -score(r), -prof.direct(r["category"], r["brand"]),
                                                                          r["price"], r["product_id"])))
            taken = {r["product_id"] for r in yours}
            hits = head + P.blend(yours, breadth([r for r in rest if r["product_id"] not in taken], relevance(toks, score)))
        else:
            hits.sort(key=relevance(toks, score))
        out = self._page(hits, score, uid, followed, saved)
        out["categories"] = sorted(({"key": k, "label": CATEGORY_LABEL.get(k, k), "count": n} for k, n in facet.items()),
                                   key=lambda c: (-c["count"], c["label"]))
        out["recent"], out["offs"], out["personal"] = used, offs, prof.personal      # hors du feed : jamais personnel
        return out

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
        return {**self._card(r, followed, saved), "history": history, "position": position(history, r["price"]),
                "attrs": json.loads(r["attrs"] or "{}"), "offers": offers,
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
