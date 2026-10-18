"""Lectures de l'app — sur le catalogue publié, sans aucun calcul de marché.

Chaque lecture = une ou deux requêtes indexées ; seuls l'ordre (marque suivie × 1,5) et les signets dépendent de la
personne connectée. La recherche est insensible aux accents, à la casse et aux tirets ; chaque mot cherché doit
commencer un mot du produit (titre, marque, enseigne, catégorie) ; quelques synonymes du langage courant.
"""
import re
import unicodedata

from .errors import NotFound

FOLLOW_BOOST = 1.5
TODAY_LIMIT = 60
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
                "pct": r["pct"], "merchant": r["merchant"], "followed": r["brand"] in followed, "saved": r["product_id"] in saved}

    def today(self, uid=None, category=None, q=None):
        followed, saved = self._personal(uid)
        rows = self.s.q("SELECT * FROM catalog WHERE pct > 0" + (" AND category=?" if category else ""), (category,) if category else ())
        toks = tokens(q) if q else []
        cards = []
        for r in rows:
            if toks and not matches(r["search"], toks):
                continue
            c = self._card(r, followed, saved)
            c["score"] = c["pct"] * (FOLLOW_BOOST if c["followed"] else 1)
            cards.append(c)
        cards.sort(key=lambda c: (-c["score"], c["id"]))
        return {"products": cards[:TODAY_LIMIT], "total": len(cards), "signed_in": uid is not None}

    def categories(self):
        rows = self.s.q("SELECT category, COUNT(*) n FROM catalog WHERE pct > 0 GROUP BY category")
        out = [{"key": r["category"], "label": CATEGORY_LABEL.get(r["category"], r["category"]), "count": r["n"]} for r in rows]
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
        return {**self._card(r, followed, saved), "offers": offers, "similar": [self._card(x, followed, saved) for x in similar],
                "signed_in": uid is not None}

    def saves(self, uid):
        """Favoris : montrés même sans remise du jour (le prix reste utile), le plus récent d'abord."""
        followed, saved = self._personal(uid)
        rows = self.s.q("SELECT c.* FROM saves s JOIN catalog c ON c.product_id=s.product_id WHERE s.user_id=? "
                        "ORDER BY s.created_at DESC, s.product_id", (uid,))
        return {"products": [self._card(r, followed, saved) for r in rows]}
