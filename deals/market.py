"""Marché : produits, offres, prix. Seul module qui les écrit.

  track(url, retailer, merchant, category_hint) → offer_id     une adresse de fiche à suivre
  record(offer, ex) → changed | unchanged | suspect            le prix lu, enregistré au changement seulement
  touch(offer_id)                                              page inchangée (304) : le dernier prix est reconfirmé
  set_result(offer_id, status, ok, …)                          issue d'une lecture : statut, note, protection, ETag
  match_product(ex) → product_id                               EAN, sinon marque + référence, sinon titre (même marque)
  other_product(offer, ex) → bool                              la page relue montre-t-elle un autre produit ?
Les écritures se font dans la transaction de l'appelant (une par page relue). Une variation énorme (÷2, ×2) est mise
en attente et confirmée par une seconde lecture avant d'être enregistrée.
"""
import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

from . import extract as X

SUSPECT_LOW, SUSPECT_HIGH = 0.5, 2.0
SAME_TITLE = 0.8        # rapprochement par titre : 80 % de mots communs, même marque
OTHER_TITLE = 0.2       # en dessous, la page relue montre un autre produit


def utc_day(ts):
    return datetime.fromtimestamp(ts, timezone.utc).date()


def norm_title(t):
    return " ".join(sorted(set(re.sub(r"[^a-z0-9 ]", " ", X.plain(t)).split())))


def jaccard(a, b):
    A, B = set(a.split()), set(b.split())
    return len(A & B) / len(A | B) if A and B else 0.0


class Market:
    def __init__(self, store, clock=time.time):
        self.s, self.clock = store, clock

    def today(self):
        return utc_day(self.clock())

    # ------------------------------------------------------------ offres
    def track(self, url, retailer, merchant, category_hint=None):
        if not re.match(r"https?://", url or ""):
            raise ValueError("adresse invalide")
        row = self.s.q("SELECT id FROM offers WHERE url=?", (url,), one=True)
        if row:
            return row["id"]
        return self.s.x("INSERT INTO offers(url, host, retailer, merchant, category_hint, created_at) VALUES (?,?,?,?,?,?)",
                        (url, urlsplit(url).netloc.lower(), retailer, merchant, category_hint, self.clock()))

    def offer(self, offer_id):
        return self.s.q("SELECT * FROM offers WHERE id=?", (offer_id,), one=True)

    def set_result(self, offer_id, status, ok, note=None, protection=None, etag=None, last_modified=None):
        self.s.x("UPDATE offers SET status=?, note=?, protection=?, etag=COALESCE(?, etag), last_modified=COALESCE(?, last_modified), "
                 "fails=CASE WHEN ? THEN 0 ELSE fails + 1 END, checked_at=? WHERE id=?",
                 (status, note, protection, etag, last_modified, int(ok), self.clock(), offer_id))

    # ------------------------------------------------------------ règles de lecture par site
    def set_rules(self, host, rules):
        for sel in (v for v in rules.values() if isinstance(v, str)):
            X.compile_selector(sel)                      # refuse un sélecteur invalide avant de l'enregistrer
        self.s.x("INSERT INTO site_rules(host, rules) VALUES (?,?) ON CONFLICT(host) DO UPDATE SET rules=excluded.rules",
                 (host.lower(), json.dumps(rules)))

    def rules_for(self, host):
        r = self.s.q("SELECT rules FROM site_rules WHERE host=?", (host,), one=True)
        return json.loads(r["rules"]) if r else None

    # ------------------------------------------------------------ produits
    def match_product(self, ex):
        cat, _ = X.categorize(ex.get("title"), ex.get("category"))
        attrs = X.attributes(ex.get("title"), ex.get("properties"))
        pid = self._find(ex)
        if pid:
            p = self.s.q("SELECT attributes FROM products WHERE id=?", (pid,), one=True)
            merged = {**attrs, **json.loads(p["attributes"] or "{}")}      # ce qui est déjà connu prime
            self.s.x("UPDATE products SET category=COALESCE(category, ?), attributes=?, image=COALESCE(image, ?) WHERE id=?",
                     (cat, json.dumps(merged), ex.get("image"), pid))
            return pid
        review = 0 if ex.get("gtin") or (ex.get("brand") and ex.get("mpn")) else 1
        return self.s.x("INSERT INTO products(gtin, brand, mpn, title, norm_title, category, attributes, image, needs_review, created_at) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (ex.get("gtin"), ex.get("brand"), ex.get("mpn"), ex.get("title") or "?", norm_title(ex.get("title")), cat,
                         json.dumps(attrs), ex.get("image"), review, self.clock()))

    def _find(self, ex):
        if ex.get("gtin"):
            p = self.s.q("SELECT id FROM products WHERE gtin=?", (ex["gtin"],), one=True)
            if p:
                return p["id"]
        brand, mpn = (ex.get("brand") or "").strip().lower(), (ex.get("mpn") or "").strip().lower()
        if brand and mpn:
            p = self.s.q("SELECT id FROM products WHERE lower(brand)=? AND lower(mpn)=?", (brand, mpn), one=True)
            if p:
                if ex.get("gtin"):
                    self.s.x("UPDATE products SET gtin=COALESCE(gtin, ?) WHERE id=?", (ex["gtin"], p["id"]))
                return p["id"]
        nt = norm_title(ex.get("title"))
        if nt and not ex.get("gtin"):
            rows = self.s.q("SELECT id, norm_title FROM products WHERE lower(COALESCE(brand, ''))=?", (brand,))
            best = max(rows, key=lambda r: jaccard(nt, r["norm_title"] or ""), default=None)
            if best and jaccard(nt, best["norm_title"] or "") >= SAME_TITLE:
                return best["id"]
        return None

    def other_product(self, offer, ex):
        if not offer["product_id"]:
            return False
        p = self.s.q("SELECT gtin, title FROM products WHERE id=?", (offer["product_id"],), one=True)
        if p["gtin"] and ex.get("gtin"):
            return p["gtin"] != ex["gtin"]
        return bool(ex.get("title")) and jaccard(norm_title(p["title"]), norm_title(ex["title"])) < OTHER_TITLE

    # ------------------------------------------------------------ prix
    def record(self, offer, ex):
        now = self.clock()
        if not offer["product_id"]:
            offer = {**offer, "product_id": self.match_product(ex)}
            self.s.x("UPDATE offers SET product_id=? WHERE id=?", (offer["product_id"], offer["id"]))
        price, was, avail = ex["price"], ex.get("list_price"), ex.get("availability") or "unknown"
        prev = self.s.q("SELECT * FROM prices WHERE offer_id=? ORDER BY first_seen DESC, id DESC LIMIT 1", (offer["id"],), one=True)
        if prev and not SUSPECT_LOW <= price / prev["price"] <= SUSPECT_HIGH and offer["pending_price"] != price:
            self.s.x("UPDATE offers SET pending_price=? WHERE id=?", (price, offer["id"]))
            return "suspect"
        self.s.x("UPDATE offers SET pending_price=NULL WHERE id=?", (offer["id"],))
        if prev and prev["price"] == price and prev["availability"] == avail and (prev["was"] or None) == (was or None):
            self.s.x("UPDATE prices SET last_seen=?, seller=?, valid_until=?, lowest_30d=COALESCE(?, lowest_30d) WHERE id=?",
                     (now, ex.get("seller"), ex.get("valid_until"), ex.get("lowest_30d"), prev["id"]))
            return "unchanged"
        self.s.x("INSERT INTO prices(offer_id, first_seen, last_seen, price, was, availability, seller, valid_until, lowest_30d, "
                 "source, was_source) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (offer["id"], now, now, price, was, avail, ex.get("seller"), ex.get("valid_until"), ex.get("lowest_30d"),
                  ex.get("method"), ex.get("was_method")))
        return "changed"

    def touch(self, offer_id):
        self.s.x("UPDATE prices SET last_seen=? WHERE id=(SELECT id FROM prices WHERE offer_id=? ORDER BY first_seen DESC, id DESC LIMIT 1)",
                 (self.clock(), offer_id))

    def last_prices(self, offer_id, n=2):
        return self.s.q("SELECT price, was, first_seen FROM prices WHERE offer_id=? ORDER BY first_seen DESC, id DESC LIMIT ?", (offer_id, n))
