"""Marché : produits, offres, prix. Seul module qui les écrit.

  track(url, retailer, merchant, category_hint) → offer_id     une adresse de fiche à suivre
  record(offer, ex) → changed | unchanged | suspect            le prix lu, enregistré au changement seulement
  touch(offer_id)                                              page inchangée (304) : le dernier prix est reconfirmé
  mark(offer_id, source, external_id, tracking_url, batch_id)  d'où vient l'offre (ingestion par flux)
  set_result(offer_id, status, ok, …)                          issue d'une lecture : statut, note, protection, ETag
  match_product(ex) → product_id                               EAN, sinon marque + référence ; sinon un produit neuf
  candidates(product_id) → [(produit, ressemblance)]           les produits au titre semblable, à revoir (jamais fusionnés)
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
SAME_TITLE = 0.8        # titre semblable (80 % de mots communs, même marque) : un candidat à revoir, jamais une fusion
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
        self.batch_of = {}            # enseigne → lot en cours (ingest/collector.py) : chaque prix relevé dit son lot

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

    def mark(self, offer_id, source=None, external_id=None, tracking_url=None, batch_id=None):
        """La provenance d'une offre lue dans un flux : sa source, son identifiant dans le flux, le lien de suivi du réseau
        (gardé à part de l'adresse de la fiche), le dernier lot qui l'a vue."""
        self.s.x("UPDATE offers SET source=COALESCE(?, source), external_id=COALESCE(?, external_id), tracking_url=?, "
                 "batch_id=COALESCE(?, batch_id) WHERE id=?", (source, external_id, tracking_url, batch_id, offer_id))

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
        """Le produit de la page (retrouvé ou créé) ; ses caractéristiques relues de l'offre du jour (titre, catégorie
        déclarée, caractéristiques), la catégorie déclarée gardée pour qu'une ontologie révisée s'applique sans relire
        l'offre (extract.product_attributes)."""
        cat, _ = X.categorize(ex.get("title"), ex.get("category"))
        pid = self._find(ex)
        if pid:
            p = self.s.q("SELECT category, attributes FROM products WHERE id=?", (pid,), one=True)
            merged = X.product_attributes(ex.get("title"), p["category"] or cat, json.loads(p["attributes"] or "{}"),
                                          ex.get("properties"), ex.get("category"))     # hors ontologie, ce qui est déjà connu prime
            self.s.x("UPDATE products SET category=COALESCE(category, ?), attributes=?, image=COALESCE(image, ?) WHERE id=?",
                     (cat, json.dumps(merged, ensure_ascii=False), ex.get("image"), pid))
            return pid
        attrs = X.product_attributes(ex.get("title"), cat, None, ex.get("properties"), ex.get("category"))
        review = 0 if ex.get("gtin") else int(not (ex.get("brand") and ex.get("mpn")) or bool(self._similar(ex)))
        return self.s.x("INSERT INTO products(gtin, brand, mpn, title, norm_title, category, attributes, image, needs_review, created_at) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (ex.get("gtin"), ex.get("brand"), ex.get("mpn"), ex.get("title") or "?", norm_title(ex.get("title")), cat,
                         json.dumps(attrs, ensure_ascii=False), ex.get("image"), review, self.clock()))

    def _find(self, ex):
        """Le produit déjà connu de l'offre, sur preuve seulement : le même EAN, sinon la même marque et la même référence
        fabricant (et pas d'EAN différent). Un titre semblable n'en est pas une : deux références d'une même gamme se
        ressemblent à un caractère près (WGG244Z0FR, WGG244Z1FR) ; il fait un candidat à revoir (candidates)."""
        if ex.get("gtin"):
            p = self.s.q("SELECT id FROM products WHERE gtin=?", (ex["gtin"],), one=True)
            if p:
                return p["id"]
        brand, mpn = (ex.get("brand") or "").strip().lower(), (ex.get("mpn") or "").strip().lower()
        if brand and mpn:
            p = self.s.q("SELECT id, gtin FROM products WHERE lower(brand)=? AND lower(mpn)=?", (brand, mpn), one=True)
            if p and not (ex.get("gtin") and p["gtin"] and p["gtin"] != ex["gtin"]):     # deux EAN : deux produits
                if ex.get("gtin"):
                    self.s.x("UPDATE products SET gtin=COALESCE(gtin, ?) WHERE id=?", (ex["gtin"], p["id"]))
                return p["id"]
        return None

    def _similar(self, ex, exclude=None):
        """Les produits de même marque au titre semblable (≥ SAME_TITLE), les plus proches d'abord : des candidats à
        revoir, jamais fusionnés."""
        nt, brand = norm_title(ex.get("title")), (ex.get("brand") or "").strip().lower()
        if not nt:
            return []
        rows = self.s.q("SELECT id, norm_title FROM products WHERE lower(COALESCE(brand, ''))=? AND id IS NOT ?", (brand, exclude))
        near = [(r["id"], round(jaccard(nt, r["norm_title"] or ""), 2)) for r in rows]
        return sorted([x for x in near if x[1] >= SAME_TITLE], key=lambda x: (-x[1], x[0]))

    def candidates(self, product_id):
        """Les produits que le titre de celui-ci rappelle (deals.py review) : [(id, ressemblance)]."""
        p = self.s.q("SELECT title, brand FROM products WHERE id=?", (product_id,), one=True)
        return self._similar(p, exclude=product_id) if p else []

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
            self.s.x("UPDATE prices SET last_seen=?, seller=?, valid_until=?, lowest_30d=COALESCE(?, lowest_30d), "
                     "shipping=COALESCE(?, shipping) WHERE id=?",
                     (now, ex.get("seller"), ex.get("valid_until"), ex.get("lowest_30d"), ex.get("shipping"), prev["id"]))
            return "unchanged"
        self.s.x("INSERT INTO prices(offer_id, first_seen, last_seen, price, was, availability, seller, valid_until, lowest_30d, "
                 "source, was_source, batch_id, shipping) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (offer["id"], now, now, price, was, avail, ex.get("seller"), ex.get("valid_until"), ex.get("lowest_30d"),
                  ex.get("method"), ex.get("was_method"), ex.get("batch_id") or self.batch_of.get(offer["retailer"]),
                  ex.get("shipping")))
        return "changed"

    def touch(self, offer_id):
        self.s.x("UPDATE prices SET last_seen=? WHERE id=(SELECT id FROM prices WHERE offer_id=? ORDER BY first_seen DESC, id DESC LIMIT 1)",
                 (self.clock(), offer_id))

    def last_prices(self, offer_id, n=2):
        return self.s.q("SELECT price, was, first_seen FROM prices WHERE offer_id=? ORDER BY first_seen DESC, id DESC LIMIT ?", (offer_id, n))
