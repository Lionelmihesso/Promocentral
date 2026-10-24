"""Actions des personnes : favoris, marques suivies, clics sortants (la mesure du produit).

Un clic sortant ne redirige que vers l'adresse d'une offre connue (pas de redirection ouverte) et il est tracé, avec ou
sans compte ; la source n'est gardée que si elle fait partie de la liste connue.
"""
import time

from .errors import BadRequest, NotFound
from .market import utc_day

# d'où vient le clic : la fiche (item), ou une fiche ouverte depuis « Moins cher, comparable » (alternative), les produits
# similaires (similar), une mission (mission), la page d'une marque (brand) ou d'une catégorie (category), la Recherche
# (search) ; les autres valeurs viennent des versions précédentes de l'app
CLICK_SOURCES = {"item", "alternative", "similar", "mission", "brand", "category", "search", "hero", "today", "explore", "saved"}


class Activity:
    def __init__(self, store, clock=time.time):
        self.s, self.clock = store, clock

    def save(self, uid, body):
        try:
            pid = int(body.get("product_id"))
        except (TypeError, ValueError):
            raise BadRequest("produit invalide")
        if not self.s.q("SELECT 1 FROM products WHERE id=?", (pid,), one=True):
            raise NotFound("produit inconnu")
        on = bool(body.get("on", True))
        if on:
            self.s.x("INSERT OR IGNORE INTO saves(user_id, product_id, created_at, price) "
                     "VALUES (?,?,?,(SELECT price FROM catalog WHERE product_id=?))", (uid, pid, self.clock(), pid))
        else:
            self.s.x("DELETE FROM saves WHERE user_id=? AND product_id=?", (uid, pid))
        return {"product_id": pid, "saved": on}

    def follow(self, uid, body):
        brand = (body.get("brand") or "").strip()
        if not brand or len(brand) > 80:
            raise BadRequest("marque invalide")
        on = bool(body.get("on", True))
        if on:
            self.s.x("INSERT OR IGNORE INTO follows(user_id, brand, created_at) VALUES (?,?,?)", (uid, brand, self.clock()))
        else:
            self.s.x("DELETE FROM follows WHERE user_id=? AND brand=?", (uid, brand))
        return {"brand": brand, "followed": on}

    def follows(self, uid):
        return {"brands": [r["brand"] for r in self.s.q("SELECT brand FROM follows WHERE user_id=? ORDER BY brand", (uid,))]}

    def click(self, uid, offer_id, source):
        o = self.s.q("SELECT id, product_id, merchant, url FROM offers WHERE id=?", (offer_id,), one=True)
        if not o or not o["product_id"] or not (o["url"] or "").startswith(("http://", "https://")):
            raise NotFound("offre inconnue")
        now = self.clock()
        self.s.x("INSERT INTO clicks(at, day, user_id, product_id, offer_id, merchant, source) VALUES (?,?,?,?,?,?,?)",
                 (now, utc_day(now).isoformat(), uid, o["product_id"], o["id"], o["merchant"], source if source in CLICK_SOURCES else None))
        return o["url"]

    def metrics(self, days=14):
        return {"total_clicks": self.s.q("SELECT COUNT(*) n FROM clicks", one=True)["n"],
                "by_day": self.s.q("SELECT day, COUNT(*) n, COUNT(DISTINCT product_id) products, SUM(user_id IS NOT NULL) signed "
                                   "FROM clicks GROUP BY day ORDER BY day DESC LIMIT ?", (days,)),
                "by_source": {r["source"] or "inconnue": r["n"] for r in self.s.q("SELECT source, COUNT(*) n FROM clicks GROUP BY source")},
                "accounts": self.s.q("SELECT COUNT(*) n FROM users", one=True)["n"]}
