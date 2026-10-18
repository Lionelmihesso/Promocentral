"""Contrat de l'app grand public (produit, marques, catégories) — préfixe /api/r/.

Entrée par produit ; la marque et la catégorie sont des entrées secondaires ; l'enseigne n'est qu'un attribut de l'offre.
Une liste de deals ne montre que des remises réelles : prix barré au-dessus du prix, et jamais une fausse remise
(prix barré gonflé au-dessus du prix habituel, détecté par le moteur quotidien).
Lecture ouverte (sans compte) ; favoris et marques suivies : session requise (→ 401).

  GET  today?category=&q=       deals classés : remise, × 1,5 si la marque est suivie ; filtres catégorie et texte (synonymes)
  GET  categories               catégories et nombre de deals
  GET  brands                   marques, nombre de deals, suivie ou non
  GET  brand/<name>             deals d'une marque, par remise
  GET  item/<id>                fiche : offres par enseigne (meilleure en premier), produits similaires
  GET  out/<offer_id>?from=     clic vers l'enseigne : tracé (avec ou sans compte), puis redirection vers l'offre connue
  POST save {product_id, on}    favori                      (session)
  GET  saves                    favoris                     (session)
  POST brand/follow {brand, on} suivre une marque           (session)
  GET  follows                  marques suivies             (session)
Interne (console /admin uniquement) :
  GET  /api/admin/metrics       clics sortants par jour et par source, nombre de comptes
"""
import re
import time
from urllib.parse import unquote

from . import accounts
from . import search as SE

FOLLOW_BOOST = 1.5
TODAY_LIMIT = 60
SIMILAR_LIMIT = 3
CLICK_SOURCES = {"item", "hero", "today", "explore", "brand", "similar", "saved"}


def display_name(title, brand):
    """Le titre sans la marque (affichée à part) : « Lave-linge 7 kg Kessler classe C » → « Lave-linge 7 kg classe C »."""
    if not brand:
        return title
    name = re.sub(rf"(?<!\w){re.escape(brand)}(?!\w)", " ", title or "", flags=re.I)
    name = re.sub(r"\s{2,}", " ", name).strip(" -–·,")
    return name or title


class NotFound(LookupError):
    """Ressource inconnue : HTTP 404."""


class Shop:
    def __init__(self, radar):
        self.R, self.L, self.q = radar, radar.L, radar.q
        self.A = accounts.of(radar)

    # ------------------------------------------------------------ identité
    def uid(self, q):
        """Compte de la session courante ; PermissionError (→ 401) sinon."""
        return self.A.user_for(q.get("_session"))

    def _uid(self, q):
        try:
            return self.uid(q)
        except PermissionError:
            return None

    def _followed(self, uid):
        if uid is None:
            return set()
        return {r["value"] for r in self.q("SELECT value FROM preferences WHERE user_id=? AND kind='brand'", (uid,))}

    def _saved(self, uid):
        if uid is None:
            return set()
        return {r["product_id"] for r in self.q("SELECT product_id FROM saves WHERE user_id=?", (uid,))}

    # ------------------------------------------------------------ cartes
    def card(self, pid, inflated=frozenset()):
        """Un produit tel que l'app l'affiche : meilleure offre disponible, prix barré de cette offre, remise en %."""
        s = self.L._snapshot_cached(pid)
        if not s or s["intel"].get("current") is None:
            return None
        p, price = s["product"], s["intel"]["current"]
        best = min((o for o in s["offers"] if o["availability"] in ("in_stock", "unknown")), key=lambda o: o["price"], default=None)
        lst = best and best.get("list_price")
        real = bool(lst and lst > price) and pid not in inflated
        return {"id": pid, "title": p["title"], "name": display_name(p["title"], p["brand"]), "brand": p["brand"], "category": p["category"],
                "category_label": SE.CATEGORY_LABEL.get(p["category"], p["category"]),
                "price": price, "was": lst if real else None, "pct": round((1 - price / lst) * 100) if real else 0,
                "merchant": s["merchant"], "inflated": pid in inflated}

    def _deals(self):
        """Toutes les remises réelles du jour (hors fausses remises et produits sans remise)."""
        inflated = self.R.inflated_products()
        out = []
        for r in self.q("SELECT id FROM products"):
            c = self.card(r["id"], inflated)
            if c and c["pct"] > 0:
                out.append(c)
        return out

    def _decorate(self, cards, uid, followed=None, saved=None):
        followed = self._followed(uid) if followed is None else followed
        saved = self._saved(uid) if saved is None else saved
        for c in cards:
            c["followed"] = c["brand"] in followed
            c["saved"] = c["id"] in saved
        return cards

    # ------------------------------------------------------------ lecture ouverte
    def today(self, q):
        uid = self._uid(q)
        followed = self._followed(uid)
        category = q.get("category") or None
        toks = SE.tokens(q.get("q", "")) if q.get("q") else []
        cards = []
        for c in self._decorate(self._deals(), uid, followed, self._saved(uid)):
            if category and c["category"] != category:
                continue
            if toks and not SE.matches({**c, "retailer": c["merchant"]}, toks):
                continue
            c["score"] = c["pct"] * (FOLLOW_BOOST if c["followed"] else 1)
            cards.append(c)
        cards.sort(key=lambda c: (-c["score"], c["id"]))
        return {"products": cards[:TODAY_LIMIT], "total": len(cards), "signed_in": uid is not None}

    def categories(self, q):
        out = {}
        for c in self._deals():
            e = out.setdefault(c["category"], {"key": c["category"], "label": c["category_label"], "count": 0})
            e["count"] += 1
        return sorted(out.values(), key=lambda e: (-e["count"], e["label"]))

    def brands(self, q):
        followed = self._followed(self._uid(q))
        out = {}
        for c in self._deals():
            e = out.setdefault(c["brand"], {"name": c["brand"], "count": 0, "followed": c["brand"] in followed})
            e["count"] += 1
        return sorted(out.values(), key=lambda e: (-e["followed"], -e["count"], e["name"]))

    def brand(self, q, name):
        name = unquote(name)
        uid = self._uid(q)
        followed = self._followed(uid)
        cards = [c for c in self._decorate(self._deals(), uid, followed, self._saved(uid)) if c["brand"] == name]
        if not cards:
            raise NotFound()
        cards.sort(key=lambda c: (-c["pct"], c["id"]))
        return {"brand": name, "followed": name in followed, "products": cards}

    def item(self, q, pid):
        uid = self._uid(q)
        inflated = self.R.inflated_products()
        card = self.card(pid, inflated)
        if not card:
            raise NotFound()
        offers = []
        for o in self.L._snapshot_cached(pid)["offers"]:
            lst = o.get("list_price")
            real = bool(lst and lst > o["price"]) and pid not in inflated
            offers.append({"offer_id": o["offer_id"], "merchant": o["merchant"], "price": o["price"],
                           "was": lst if real else None, "pct": round((1 - o["price"] / lst) * 100) if real else 0,
                           "availability": o["availability"]})
        offers.sort(key=lambda o: (o["availability"] not in ("in_stock", "unknown"), o["price"]))
        if offers:
            offers[0]["best"] = True
        return {**self._decorate([card], uid)[0], "offers": offers, "similar": self._similar(card, uid, inflated),
                "signed_in": uid is not None}

    def _similar(self, card, uid, inflated):
        """Similarité calculée chaque semaine sur les caractéristiques ; à défaut, même catégorie au prix le plus proche."""
        ids = [r["other_id"] for r in self.q("SELECT other_id FROM similarity WHERE product_id=? ORDER BY score DESC, other_id", (card["id"],))]
        cards = [c for c in (self.card(i, inflated) for i in ids) if c]
        if len(cards) < SIMILAR_LIMIT:
            seen = {card["id"]} | {c["id"] for c in cards}
            rest = [c for c in (self.card(r["id"], inflated) for r in self.q("SELECT id FROM products WHERE category=?", (card["category"],)))
                    if c and c["id"] not in seen]
            rest.sort(key=lambda c: abs(c["price"] - card["price"]))
            cards += rest
        return self._decorate(cards[:SIMILAR_LIMIT], uid)

    # ------------------------------------------------------------ session requise
    def save(self, uid, b):
        pid = int(b.get("product_id"))
        if not self.q("SELECT 1 FROM products WHERE id=?", (pid,), one=True):
            raise NotFound()
        on = bool(b.get("on", True))
        if on:
            self.q("INSERT OR IGNORE INTO saves(user_id, product_id, created_at) VALUES (?,?,?)", (uid, pid, time.time()))
        else:
            self.q("DELETE FROM saves WHERE user_id=? AND product_id=?", (uid, pid))
        return {"product_id": pid, "saved": on}

    def saves(self, uid):
        """Favoris : affichés même sans remise du jour (le prix reste utile), dans l'ordre d'ajout le plus récent."""
        inflated = self.R.inflated_products()
        pids = [r["product_id"] for r in self.q("SELECT product_id FROM saves WHERE user_id=? ORDER BY created_at DESC, product_id", (uid,))]
        return {"products": self._decorate([c for c in (self.card(p, inflated) for p in pids) if c], uid)}

    def follow(self, uid, b):
        brand = (b.get("brand") or "").strip()
        if not brand or len(brand) > 80:
            raise ValueError("marque invalide")
        on = bool(b.get("on", True))
        self.R.follow(uid, "brand", brand, on=on)
        return {"brand": brand, "followed": on}

    def follows(self, uid):
        return {"brands": sorted(self._followed(uid))}

    # ------------------------------------------------------------ clics sortants (mesure du produit)
    def out(self, q, offer_id):
        """Redirige uniquement vers l'URL d'une offre connue (pas de redirection ouverte) et trace le clic."""
        o = self.q("SELECT id, product_id, merchant, url FROM offers WHERE id=?", (offer_id,), one=True)
        if not o or not o["product_id"] or not (o["url"] or "").startswith(("http://", "https://")):
            raise NotFound()
        source = q.get("from") if q.get("from") in CLICK_SOURCES else None
        self.q("INSERT INTO clicks(at, day, user_id, product_id, offer_id, merchant, source) VALUES (?,?,?,?,?,?,?)",
               (self.L.clock(), self.L.today().isoformat(), self._uid(q), o["product_id"], o["id"], o["merchant"], source))
        return {"__redirect__": o["url"]}

    def metrics(self, days=14):
        by_day = self.q("SELECT day, COUNT(*) n, COUNT(DISTINCT product_id) products, SUM(user_id IS NOT NULL) signed "
                        "FROM clicks GROUP BY day ORDER BY day DESC LIMIT ?", (days,))
        by_source = {r["source"] or "inconnue": r["n"] for r in self.q("SELECT source, COUNT(*) n FROM clicks GROUP BY source")}
        return {"north_star": "clics sortants vers une enseigne",
                "total_clicks": self.q("SELECT COUNT(*) n FROM clicks", one=True)["n"],
                "by_day": by_day, "by_source": by_source,
                "accounts": self.q("SELECT COUNT(*) n FROM users WHERE name LIKE '%@%'", one=True)["n"],
                "deals_today": len(self._deals()), "inflated_excluded": len(self.R.inflated_products())}
