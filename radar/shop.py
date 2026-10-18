"""Contrat de l'app grand public (produit, marques, catégories) — préfixe /api/r/.

Entrée par produit ; la marque et la catégorie sont des entrées secondaires ; l'enseigne n'est qu'un attribut de l'offre.
Lecture ouverte (sans compte) ; favoris et marques suivies : session requise (→ 401).

  GET  today?category=&q=       produits classés : remise, × 1,5 si la marque est suivie ; filtres catégorie et texte
  GET  categories               catégories et nombre de produits
  GET  brands                   marques, nombre de produits, suivie ou non
  GET  brand/<name>             produits d'une marque, par remise
  GET  item/<id>                fiche : offres par enseigne (meilleure en premier), produits similaires
  POST save {product_id, on}    favori                      (session)
  GET  saves                    favoris                     (session)
  POST brand/follow {brand, on} suivre une marque           (session)
  GET  follows                  marques suivies             (session)
"""
import time
import unicodedata
from urllib.parse import unquote

from . import accounts

FOLLOW_BOOST = 1.5
TODAY_LIMIT = 60


class Shop:
    def __init__(self, radar, consumer):
        self.R, self.L, self.q, self.C = radar, radar.L, radar.q, consumer
        self.A = accounts.of(radar)
        with self.L.lock:
            self.L.db.executescript("""
                CREATE TABLE IF NOT EXISTS saves (user_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
                  created_at REAL NOT NULL, PRIMARY KEY (user_id, product_id));""")
            self.L.db.commit()

    # ------------------------------------------------------------ identité optionnelle
    def _uid(self, q):
        try:
            return self.A.user_for(q.get("_session"))
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
    def _all_cards(self):
        cards = []
        for r in self.q("SELECT id FROM products"):
            c = self.C._card(r["id"])
            if c:
                c["pct"] = round((c["discount"] or 0) * 100)
                cards.append(c)
        return cards

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
        terms = [t for t in _fold(q.get("q", "")).split() if t]
        cards = []
        for c in self._decorate(self._all_cards(), uid, followed, self._saved(uid)):
            if category and c["category"] != category:
                continue
            if terms and not all(t in _fold(f"{c['brand']} {c['title']} {c['category_label']}") for t in terms):
                continue
            c["score"] = c["pct"] * (FOLLOW_BOOST if c["followed"] else 1)
            cards.append(c)
        cards.sort(key=lambda c: (-c["score"], c["id"]))
        return {"products": cards[:TODAY_LIMIT], "total": len(cards), "signed_in": uid is not None}

    def categories(self, q):
        out = {}
        for c in self._all_cards():
            e = out.setdefault(c["category"], {"key": c["category"], "label": c["category_label"], "count": 0})
            e["count"] += 1
        return sorted(out.values(), key=lambda e: (-e["count"], e["label"]))

    def brands(self, q):
        uid = self._uid(q)
        followed = self._followed(uid)
        out = {}
        for c in self._all_cards():
            e = out.setdefault(c["brand"], {"name": c["brand"], "count": 0, "followed": c["brand"] in followed})
            e["count"] += 1
        return sorted(out.values(), key=lambda e: (-e["followed"], -e["count"], e["name"]))

    def brand(self, q, name):
        name = unquote(name)
        uid = self._uid(q)
        followed = self._followed(uid)
        cards = [c for c in self._decorate(self._all_cards(), uid, followed, self._saved(uid)) if c["brand"] == name]
        if not cards:
            raise NotFound()
        cards.sort(key=lambda c: (-c["pct"], c["id"]))
        return {"brand": name, "followed": name in followed, "products": cards}

    def item(self, q, pid):
        uid = self._uid(q)
        card = self.C._card(pid)
        if not card:
            raise NotFound()
        s = self.L._snapshot_cached(pid)
        offers = []
        for o in s["offers"]:
            lst = o.get("list_price")
            offers.append({"merchant": o["merchant"], "url": o["url"], "price": o["price"], "was": lst if lst and lst > o["price"] else None,
                           "pct": round((1 - o["price"] / lst) * 100) if lst and lst > o["price"] else 0,
                           "availability": o["availability"]})
        offers.sort(key=lambda o: (o["availability"] != "in_stock", o["price"]))
        if offers:
            offers[0]["best"] = True
        others = [c for c in (self.C._card(r["id"]) for r in self.q("SELECT id FROM products WHERE category=? AND id<>?",
                                                                     (card["category"], pid))) if c]
        similar = self._decorate(others, uid)
        similar.sort(key=lambda c: abs(c["price"] - card["price"]))
        card["pct"] = round((card["discount"] or 0) * 100)
        card["followed"] = card["brand"] in self._followed(uid)
        card["saved"] = pid in self._saved(uid)
        return {**card, "offers": offers, "similar": similar[:3], "signed_in": uid is not None}

    # ------------------------------------------------------------ session requise
    def save(self, uid, b):
        pid = int(b.get("product_id"))
        if not self.q("SELECT 1 FROM products WHERE id=?", (pid,), one=True):
            raise NotFound()
        if b.get("on", True):
            self.q("INSERT OR IGNORE INTO saves(user_id, product_id, created_at) VALUES (?,?,?)", (uid, pid, time.time()))
        else:
            self.q("DELETE FROM saves WHERE user_id=? AND product_id=?", (uid, pid))
        return {"product_id": pid, "saved": bool(b.get("on", True))}

    def saves(self, uid):
        pids = sorted(self._saved(uid))
        cards = [c for c in (self.C._card(p) for p in pids) if c]
        for c in cards:
            c["pct"] = round((c["discount"] or 0) * 100)
        return {"products": self._decorate(cards, uid)}

    def follow(self, uid, b):
        brand = (b.get("brand") or "").strip()
        if not brand or len(brand) > 80:
            raise ValueError("marque invalide")
        on = bool(b.get("on", True))
        self.R.follow(uid, "brand", brand, on=on)
        return {"brand": brand, "followed": on}

    def follows(self, uid):
        return {"brands": sorted(self._followed(uid))}


def _fold(text):
    """Minuscules, sans accents : « Réfrigérateur » trouve « refrigerateur »."""
    return "".join(ch for ch in unicodedata.normalize("NFD", text or "").lower() if unicodedata.category(ch) != "Mn")


class NotFound(LookupError):
    """Ressource inconnue : HTTP 404."""
