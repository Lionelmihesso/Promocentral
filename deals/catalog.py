"""Lectures de l'app — sur le catalogue publié, sans aucun calcul de marché.

Chaque lecture = une ou deux requêtes indexées ; seuls l'ordre (marque suivie × 1,5) et les signets dépendent de la
personne connectée. La recherche est insensible aux accents, à la casse et aux tirets ; chaque mot cherché doit
commencer un mot du produit (titre, marque, enseigne, catégorie) ; quelques synonymes du langage courant.
"""
import re
import unicodedata

from .errors import NotFound
from .extract.categories import FAMILY_OF

FOLLOW_BOOST = 1.5
TODAY_LIMIT = 60
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
                "category_label": CATEGORY_LABEL.get(r["category"], r["category"]), "price": r["price"], "was": r["was"],
                "pct": r["pct"], "merchant": r["merchant"], "since": r["since"], "ends": r["ends"], "published_on": r["published_on"],
                "followed": r["brand"] in followed, "saved": r["product_id"] in saved}

    def today(self, uid=None, category=None, q=None):
        followed, saved = self._personal(uid)
        where, args = (" AND category=?", (category,)) if category else ("", ())
        toks = tokens(q) if q else []
        # colonnes légères pour filtrer et classer, lignes complètes pour le seul haut de liste montré
        rows = self.s.q("SELECT product_id, pct, brand" + (", search" if toks else "") + " FROM catalog WHERE pct > 0" + where, args)
        hits = [r for r in rows if not toks or matches(r["search"], toks)]
        score = lambda r: r["pct"] * (FOLLOW_BOOST if r["brand"] in followed else 1)
        hits.sort(key=lambda r: (-score(r), r["product_id"]))
        return self._page(hits, score, uid, followed, saved)

    def search(self, uid=None, q=None):
        """Tout le catalogue suivi, pas seulement les remises : c'est l'entrée « je regarde ce produit » (sa fiche montre
        ses alternatives moins chères). Les remises d'abord, puis le reste, du moins cher au plus cher."""
        toks = tokens(q) if q else []
        if not toks:
            return {"products": [], "total": 0, "signed_in": uid is not None}
        followed, saved = self._personal(uid)
        hits = [r for r in self.s.q("SELECT product_id, pct, brand, price, search FROM catalog") if matches(r["search"], toks)]
        score = lambda r: r["pct"] * (FOLLOW_BOOST if r["brand"] in followed else 1)
        hits.sort(key=lambda r: (r["pct"] <= 0, -score(r), r["price"], r["product_id"]))
        return self._page(hits, score, uid, followed, saved)

    def _page(self, hits, score, uid, followed, saved):
        """Lignes complètes et cartes pour le seul haut de liste montré."""
        top = hits[:TODAY_LIMIT]
        full = {r["product_id"]: r for r in self.s.q(f"SELECT * FROM catalog WHERE product_id IN ({','.join('?' * len(top))})",
                                                     [r["product_id"] for r in top])} if top else {}
        cards = [{**self._card(full[r["product_id"]], followed, saved), "score": score(r)} for r in top]
        return {"products": cards, "total": len(hits), "signed_in": uid is not None}

    def categories(self):
        rows = self.s.q("SELECT category, COUNT(*) n FROM catalog WHERE pct > 0 GROUP BY category")
        out = [{"key": r["category"], "label": CATEGORY_LABEL.get(r["category"], r["category"]), "count": r["n"],
                "family": FAMILY_OF.get(r["category"]), "family_label": FAMILY_LABEL.get(FAMILY_OF.get(r["category"]))} for r in rows]
        return sorted(out, key=lambda e: (-e["count"], e["label"] or ""))

    def brands(self, uid=None):
        followed, _ = self._personal(uid)
        rows = self.s.q("SELECT brand, COUNT(*) n FROM catalog WHERE pct > 0 AND brand IS NOT NULL GROUP BY brand")
        out = [{"name": r["brand"], "count": r["n"], "followed": r["brand"] in followed} for r in rows]
        return sorted(out, key=lambda e: (-e["followed"], -e["count"], e["name"]))

    def brand(self, uid, name):
        followed, saved = self._personal(uid)
        rows = self.s.q("SELECT * FROM catalog WHERE pct > 0 AND brand=? ORDER BY pct DESC, product_id", (name,))
        if not rows:
            raise NotFound("marque inconnue")
        return {"brand": name, "followed": name in followed, "products": [self._card(r, followed, saved) for r in rows]}

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
        return {**self._card(r, followed, saved), "offers": offers, "similar": [self._card(x, followed, saved) for x in similar],
                "alternatives": [{**self._card(x, followed, saved), "saving": round(r["price"] - x["price"])} for x in cheaper],
                "signed_in": uid is not None}

    def saves(self, uid):
        """Favoris : montrés même sans remise du jour (le prix reste utile), le plus récent d'abord, avec le prix du
        catalogue au moment où le favori a été posé (pour montrer une baisse)."""
        followed, saved = self._personal(uid)
        rows = self.s.q("SELECT c.*, s.price AS saved_price FROM saves s JOIN catalog c ON c.product_id=s.product_id "
                        "WHERE s.user_id=? ORDER BY s.created_at DESC, s.product_id", (uid,))
        return {"products": [{**self._card(r, followed, saved), "saved_price": r["saved_price"]} for r in rows]}
