"""Actions des personnes : favoris, marques suivies, fiches vues et clics sortants (la mesure du produit).

Un clic sortant ne redirige que vers l'adresse d'une offre connue (pas de redirection ouverte). Il est tracé, avec ou
sans compte, et part chez l'enseigne partenaire par son lien affilié, avec l'identifiant du clic (affiliate.py) : la
vente que le réseau rapporte se rattache au clic, donc à l'écran, à la mission et à la personne d'où il est parti. Les
fiches vues donnent le taux de clic de chaque écran. La source n'est gardée que si elle fait partie de la liste connue.
"""
import time

from . import affiliate
from .errors import BadRequest, NotFound
from .market import utc_day

# d'où vient le clic : la fiche (item), ou une fiche ouverte depuis les top deals de l'accueil (top), les favoris du profil
# (saved), « Moins cher, comparable » (alternative), les produits
# similaires (similar), une mission dans l'app (mission) ou son e-mail (mail), la page d'une marque (brand) ou d'une
# catégorie (category), les résultats d'une recherche (search) ou le feed de la Recherche avant toute recherche (feed) :
# la part de « search » dit si l'on cherche vraiment ; les autres valeurs viennent des versions précédentes de l'app
CLICK_SOURCES = {"item", "top", "alternative", "similar", "mission", "mail", "brand", "category", "search", "feed", "saved",
                 "hero", "today", "explore"}
SEGMENT = ("CASE WHEN user_id IS NULL THEN 'sans compte' WHEN user_id IN (SELECT user_id FROM missions) THEN 'avec mission' "
           "ELSE 'connecté, sans mission' END")


class Activity:
    def __init__(self, store, clock=time.time, rules=None):
        """rules : enseigne → règle d'affiliation (affiliate.py) ; None en développement (liens directs)."""
        self.s, self.clock, self.rules = store, clock, rules

    @staticmethod
    def _mission(value):
        """L'identifiant de mission porté par un lien (e-mail, carte de mission), ou None."""
        try:
            return int(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

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

    def click(self, uid, offer_id, source, mission=None):
        """Trace le clic → l'adresse où envoyer la personne : le lien affilié de l'enseigne, avec l'identifiant du clic."""
        o = self.s.q("SELECT id, product_id, retailer, merchant, url FROM offers WHERE id=?", (offer_id,), one=True)
        if not o or not o["product_id"] or not (o["url"] or "").startswith(("http://", "https://")):
            raise NotFound("offre inconnue")
        now, rule = self.clock(), (self.rules or {}).get(o["retailer"])
        cid = self.s.x("INSERT INTO clicks(at, day, user_id, product_id, offer_id, merchant, source, partner, mission_id) "
                       "VALUES (?,?,?,?,?,?,?,?,?)", (now, utc_day(now).isoformat(), uid, o["product_id"], o["id"], o["merchant"],
                                                     source if source in CLICK_SOURCES else None,
                                                     None if self.rules is None else int(rule is not None), self._mission(mission)))
        return affiliate.link(o["url"], rule, cid) or o["url"]

    def view(self, uid, body):
        """Une fiche ouverte, et d'où (même liste que les clics) : le dénominateur du taux de clic."""
        try:
            pid = int((body or {}).get("product_id"))
        except (TypeError, ValueError):
            raise BadRequest("produit invalide")
        if not self.s.q("SELECT 1 FROM catalog WHERE product_id=?", (pid,), one=True):
            raise NotFound("produit inconnu")
        now, source = self.clock(), body.get("from")
        self.s.x("INSERT INTO views(at, day, user_id, product_id, source, mission_id) VALUES (?,?,?,?,?,?)",
                 (now, utc_day(now).isoformat(), uid, pid, source if source in CLICK_SOURCES else None, self._mission(body.get("m"))))
        return {"ok": True}

    def funnel(self, group):
        """Fiches vues → clics vers l'enseigne, et le taux de clic, par valeur de `group` (une expression SQL)."""
        seen = {r["k"]: r["n"] for r in self.s.q(f"SELECT {group} k, COUNT(*) n FROM views GROUP BY k")}
        sent = {r["k"]: r["n"] for r in self.s.q(f"SELECT {group} k, COUNT(*) n FROM clicks GROUP BY k")}
        return {k or "inconnue": {"views": seen.get(k, 0), "clicks": sent.get(k, 0),
                                  "ctr": round(sent.get(k, 0) / seen[k], 3) if seen.get(k) else None}
                for k in sorted(set(seen) | set(sent), key=lambda k: (k is None, k or ""))}

    def metrics(self, days=14):
        """La conversion vue d'ici : par écran (source) et selon la personne (avec mission, connectée sans mission, sans
        compte), les fiches vues, les clics vers l'enseigne et le taux de clic ; la part des clics partis chez un partenaire
        (rémunérables) ; les clics venus des missions, dans l'app ou par e-mail. Les ventes viennent des rapports du
        réseau, rattachées par l'identifiant du clic."""
        paid = self.s.q("SELECT SUM(partner = 1) p, COUNT(partner) n FROM clicks", one=True)
        missions = self.s.q("SELECT COUNT(*) n, COUNT(DISTINCT mission_id) m FROM clicks WHERE mission_id IS NOT NULL", one=True)
        return {"total_clicks": self.s.q("SELECT COUNT(*) n FROM clicks", one=True)["n"],
                "by_day": self.s.q("SELECT day, COUNT(*) n, COUNT(DISTINCT product_id) products, SUM(user_id IS NOT NULL) signed "
                                   "FROM clicks GROUP BY day ORDER BY day DESC LIMIT ?", (days,)),
                "by_source": self.funnel("source"), "by_person": self.funnel(SEGMENT),
                "partner_share": round(paid["p"] / paid["n"], 3) if paid["n"] else None,
                "from_missions": {"clicks": missions["n"], "missions": missions["m"]},
                "accounts": self.s.q("SELECT COUNT(*) n FROM users", one=True)["n"]}
