"""Market Intelligence Engine — cœur.

  MARCHÉ (pages web, flux marchands)
    → INGESTION (fetch.py, parse_feed)          collecte, politesse, provenance
    → NORMALISATION (extract.py, normalize.py)  prix, stock, identifiants, catégorie, attributs, qualité
    → GRAPHE PRODUIT / OFFRES                   un produit, n offres marchandes
    → FAITS (observations)                      traçables : source, heure, méthode, prix brut, qualité
    → INTELLIGENCE (intelligence.py)            statistiques, percentile, état du prix, promotions
    → ÉVÉNEMENTS normalisés + SIGNAUX (signals.py)
    → SURVEILLANCES par condition               (le futur moteur de décision consommera les signaux)
Aucun LLM : tout est déterministe et testable.
"""
import csv
import io
import json
import queue
import re
import sqlite3
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit

from . import extract as X
from . import intelligence as I
from . import normalize as N
from . import signals as S
from .fetch import Fetcher

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY, gtin TEXT UNIQUE, brand TEXT, mpn TEXT, title TEXT, norm_title TEXT,
  needs_review INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS offers (
  id INTEGER PRIMARY KEY, url TEXT UNIQUE NOT NULL, host TEXT NOT NULL, merchant TEXT, product_id INTEGER,
  source TEXT NOT NULL DEFAULT 'web', feed_id INTEGER, priority INTEGER NOT NULL DEFAULT 2,
  status TEXT NOT NULL DEFAULT 'active', etag TEXT, last_modified TEXT,
  interval_s REAL, next_check_at REAL NOT NULL, last_check_at REAL, fail_count INTEGER NOT NULL DEFAULT 0,
  pending_price REAL, last_method TEXT, created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS offers_due ON offers(status, next_check_at);
CREATE TABLE IF NOT EXISTS observations (
  id INTEGER PRIMARY KEY, offer_id INTEGER NOT NULL, first_seen REAL NOT NULL, last_seen REAL NOT NULL,
  price REAL, currency TEXT, availability TEXT, method TEXT, n INTEGER NOT NULL DEFAULT 1);
CREATE INDEX IF NOT EXISTS obs_offer ON observations(offer_id, first_seen);
CREATE TABLE IF NOT EXISTS checks (
  id INTEGER PRIMARY KEY, offer_id INTEGER, host TEXT, at REAL, status TEXT, code INTEGER, elapsed_ms INTEGER, method TEXT);
CREATE INDEX IF NOT EXISTS checks_host ON checks(host, at);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY, at REAL NOT NULL, type TEXT NOT NULL, offer_id INTEGER, product_id INTEGER, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS events_type ON events(type, at);
CREATE TABLE IF NOT EXISTS webhooks (id INTEGER PRIMARY KEY, url TEXT NOT NULL, types TEXT NOT NULL DEFAULT '[]');
CREATE TABLE IF NOT EXISTS feeds (
  id INTEGER PRIMARY KEY, source TEXT NOT NULL, merchant TEXT NOT NULL, interval_s REAL NOT NULL,
  next_run_at REAL NOT NULL, last_status TEXT, last_count INTEGER);
CREATE TABLE IF NOT EXISTS site_rules (host TEXT PRIMARY KEY, rules TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS signals (
  id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL, type TEXT NOT NULL, status TEXT NOT NULL,
  raised_at REAL NOT NULL, updated_at REAL NOT NULL, cleared_at REAL, payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS signals_active ON signals(status, product_id, type);
CREATE TABLE IF NOT EXISTS watches (id INTEGER PRIMARY KEY, spec TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS watch_matches (
  id INTEGER PRIMARY KEY, watch_id INTEGER NOT NULL, product_id INTEGER NOT NULL, active INTEGER NOT NULL,
  matched_at REAL NOT NULL, cleared_at REAL, reason TEXT, price REAL);
"""
# Colonnes ajoutées en v0.2 (migration sans perte d'une base v0.1)
MIGRATIONS = {
    "products": {"category": "TEXT", "category_source": "TEXT", "attributes": "TEXT NOT NULL DEFAULT '{}'",
                 "gap_active": "INTEGER NOT NULL DEFAULT 0", "image": "TEXT"},
    "offers": {"promo_active": "INTEGER NOT NULL DEFAULT 0", "schedule_reason": "TEXT", "quality": "TEXT"},
    "observations": {"raw_price": "TEXT", "list_price": "REAL", "confidence": "REAL", "quality": "TEXT", "found": "TEXT"},
    "events": {"entity_type": "TEXT", "entity_id": "INTEGER", "previous": "TEXT", "new": "TEXT",
               "confidence": "REAL", "source": "TEXT"},
}

PRIORITY_BASE = {1: 15 * 60, 2: 6 * 3600, 3: 24 * 3600}
MIN_INTERVAL_S = 10 * 60     # plancher absolu : jamais plus d'une vérification toutes les 10 min par page
SUSPECT_DROP, SUSPECT_RISE = 0.5, 2.0
SIGNIFICANT = 0.01
STALE_S = 3 * 86400          # un prix non reconfirmé depuis 3 jours n'entre plus dans le « prix du jour »
GAP_THRESHOLD = 0.15         # écart entre marchands jugé significatif
PROMO_ADVERTISED_MIN = 0.05
PROMO_OBSERVED_MIN = 0.10

EVENT_TYPES = ("NEW_PRODUCT", "NEW_OFFER", "PRICE_DROP", "PRICE_INCREASE", "NEW_LOW", "BACK_IN_STOCK", "OUT_OF_STOCK",
               "PROMOTION_STARTED", "PROMOTION_ENDED", "MERCHANT_PRICE_GAP", "PRICE_ANOMALY", "OFFER_REMOVED",
               "PRODUCT_DISCONTINUED", "SIGNAL_RAISED", "SIGNAL_CLEARED", "WATCH_MATCHED", "WATCH_UNMATCHED",
               "SOURCE_BLOCKED", "SOURCE_DISALLOWED", "EXTRACTION_FAILED")


def utc_day(ts):
    return datetime.fromtimestamp(ts, timezone.utc).date()


def day_start(d):
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()


def _host(url):
    return urlsplit(url).netloc.lower()


def norm_title(t):
    t = re.sub(r"[^a-z0-9 ]", " ", N.plain(t))
    return " ".join(sorted(set(t.split())))


def jaccard(a, b):
    A, B = set(a.split()), set(b.split())
    return len(A & B) / len(A | B) if A and B else 0.0


BATCH_COMMIT_S = 1.0   # durée maximale de détention du verrou d'écriture pendant une passe groupée
BATCH_YIELD_S = 0.1    # pause après chaque validation groupée : un favori ou un clic passe en moins d'une seconde

class Bus:
    def __init__(self):
        self.subs, self.lock = [], threading.Lock()

    def subscribe(self):
        q = queue.Queue(maxsize=1000)
        with self.lock:
            self.subs.append(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            if q in self.subs:
                self.subs.remove(q)

    def publish(self, ev):
        with self.lock:
            for q in list(self.subs):
                try:
                    q.put_nowait(ev)
                except queue.Full:
                    pass


class Listener:
    def __init__(self, path=":memory:", fetcher=None, clock=time.time, workers=8, intel_cfg=None):
        # timeout : une écriture du serveur web attend (au lieu d'échouer) pendant une validation de la passe de nuit
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=15)
        self.db.row_factory = sqlite3.Row
        if path != ":memory:":
            self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        self._migrate()
        self.lock = threading.RLock()
        self.fetcher = fetcher or Fetcher()
        self.clock = clock
        self.bus = Bus()
        self.workers = workers
        self.intel_cfg = {**I.DEFAULT, **(intel_cfg or {})}
        self._snap = {}  # product_id -> dernier instantané calculé (lecture rapide pour l'API)
        # Demande partagée : les couches supérieures (missions) déclarent les produits qui comptent.
        # Une seule observation par offre, quel que soit le nombre d'utilisateurs intéressés.
        self.demand_providers = []
        self.extract_hooks = []  # rappels (offer_id, extraction, html) après chaque page lue avec succès

    def _migrate(self):
        for table, cols in MIGRATIONS.items():
            have = {r[1] for r in self.db.execute(f"PRAGMA table_info({table})")}
            for c, typ in cols.items():
                if c not in have:
                    self.db.execute(f"ALTER TABLE {table} ADD COLUMN {c} {typ}")
        self.db.commit()

    # ------------------------------------------------------------ SQL
    # cycle de vie explicite de la connexion (audit v15) : with Listener(...) as L: …  ou  L.close()
    def close(self):
        with self.lock:
            if self.db is not None:
                self.db.close()
                self.db = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # transactions groupées : with L.batch(): … → un seul COMMIT (et ROLLBACK si erreur) au lieu d'un par requête
    def batch(self):
        L = self

        class _Batch:
            # le verrou n'est PAS gardé pendant le bloc : la collecte de nuit écrit depuis un fil par site
            def __enter__(self):
                with L.lock:
                    L._depth = getattr(L, "_depth", 0) + 1
                    L._last_commit = time.monotonic()
                return L

            def __exit__(self, exc_type, *a):
                with L.lock:
                    L._depth -= 1
                    if L._depth == 0:
                        (L.db.rollback if exc_type else L.db.commit)()
                return False
        return _Batch()

    def __del__(self):
        try:
            if getattr(self, "db", None) is not None:
                self.db.close()
        except Exception:
            pass

    def q(self, sql, args=(), one=False):
        with self.lock:
            cur = self.db.execute(sql, args)
            if not getattr(self, "_depth", 0):
                self.db.commit()
            elif time.monotonic() - self._last_commit >= BATCH_COMMIT_S:
                # passe de nuit : validation au plus toutes les secondes, pour que le verrou d'écriture ne soit jamais
                # tenu plus longtemps (sinon favoris, clics et connexions échouent pendant la collecte)
                self.db.commit()
                time.sleep(BATCH_YIELD_S)        # fenêtre laissée aux autres processus (sinon la passe reprend le verrou aussitôt)
                self._last_commit = time.monotonic()
            if sql.lstrip()[:6].upper() == "INSERT":
                return cur.lastrowid
            rows = [dict(r) for r in cur.fetchall()]
            return (rows[0] if rows else None) if one else rows

    def today(self):
        return utc_day(self.clock())

    # ------------------------------------------------------------ offres suivies
    def track(self, url, priority=2, merchant=None):
        if not re.match(r"https?://", url or ""):
            raise ValueError("URL invalide")
        ex = self.q("SELECT id FROM offers WHERE url=?", (url,), one=True)
        if ex:
            self.q("UPDATE offers SET priority=?, status='active', next_check_at=? WHERE id=?", (priority, self.clock(), ex["id"]))
            return ex["id"]
        return self.q("INSERT INTO offers(url, host, merchant, priority, interval_s, next_check_at, created_at) VALUES (?,?,?,?,?,?,?)",
                      (url, _host(url), merchant or _host(url), priority, PRIORITY_BASE[priority], self.clock(), self.clock()))

    def set_rules(self, host, rules):
        for sel in (v for v in rules.values() if isinstance(v, str)):
            X._compile_selector(sel)
        self.q("INSERT INTO site_rules(host, rules) VALUES (?,?) ON CONFLICT(host) DO UPDATE SET rules=excluded.rules",
               (host.lower(), json.dumps(rules)))

    def rules_for(self, host):
        r = self.q("SELECT rules FROM site_rules WHERE host=?", (host,), one=True)
        return json.loads(r["rules"]) if r else None

    def diagnose(self, url):
        r = self.fetcher.get(url)
        out = {"url": url, "status": r["status"], "code": r.get("code"), "elapsed_ms": r.get("elapsed_ms")}
        if r["status"] == "ok":
            ex = X.extract(r["html"], self.rules_for(_host(url)))
            if ex:
                ex["category"], _ = N.categorize(ex.get("title"), ex.get("category"))
                ex["attributes"] = N.attributes(ex.get("title"), ex.get("properties"))
                ex["quality"] = N.quality(ex)
            out["extraction"] = ex
            out["hint"] = None if ex else ("Aucun prix structuré trouvé : ajoutez une règle pour ce site "
                                           "(sélecteur du prix, ex. div.prix-final) via le formulaire « Règle » "
                                           "ou la commande : python run.py rules <site> '{\"price\": \"div.prix\"}'")
        return out

    # ------------------------------------------------------------ graphe produit
    def match_product(self, ex):
        # recherche puis création doivent être atomiques : les threads de collecte tournent en parallèle
        with self.lock:
            return self._match_product(ex)

    def _match_product(self, ex):
        cat, cat_src = N.categorize(ex.get("title"), ex.get("category"))
        attrs = N.attributes(ex.get("title"), ex.get("properties"))
        pid = self._find_product(ex)
        if pid:
            p = self.q("SELECT category, attributes FROM products WHERE id=?", (pid,), one=True)
            merged = {**attrs, **json.loads(p["attributes"] or "{}")}  # les attributs déjà connus priment
            self.q("UPDATE products SET category=COALESCE(category, ?), category_source=COALESCE(category_source, ?), attributes=?, "
                   "image=COALESCE(image, ?) WHERE id=?", (cat, cat_src, json.dumps(merged), ex.get("image"), pid))
            return pid
        nt = norm_title(ex.get("title"))
        review = 0 if ex.get("gtin") or (ex.get("brand") and ex.get("mpn")) else 1
        pid = self.q("INSERT INTO products(gtin, brand, mpn, title, norm_title, needs_review, created_at, category, category_source, attributes, image) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (ex.get("gtin"), ex.get("brand"), ex.get("mpn"), ex.get("title"), nt, review, self.clock(), cat, cat_src,
                      json.dumps(attrs), ex.get("image")))
        self._event("NEW_PRODUCT", entity=("product", pid), product_id=pid,
                    new={"title": ex.get("title"), "gtin": ex.get("gtin"), "category": cat},
                    confidence=0.95 if ex.get("gtin") else 0.7)
        return pid

    def _find_product(self, ex):
        if ex.get("gtin"):
            p = self.q("SELECT id FROM products WHERE gtin=?", (ex["gtin"],), one=True)
            if p:
                return p["id"]
        brand, mpn = (ex.get("brand") or "").strip().lower(), (ex.get("mpn") or "").strip().lower()
        if brand and mpn:
            p = self.q("SELECT id FROM products WHERE lower(brand)=? AND lower(mpn)=?", (brand, mpn), one=True)
            if p:
                if ex.get("gtin"):
                    self.q("UPDATE products SET gtin=COALESCE(gtin, ?) WHERE id=?", (ex["gtin"], p["id"]))
                return p["id"]
        nt = norm_title(ex.get("title"))
        if nt and not ex.get("gtin"):
            rows = self.q("SELECT id, norm_title FROM products WHERE lower(COALESCE(brand,''))=?", (brand,)) if brand else \
                self.q("SELECT id, norm_title FROM products")
            best = max(rows, key=lambda r: jaccard(nt, r["norm_title"] or ""), default=None)
            if best and jaccard(nt, best["norm_title"] or "") >= 0.8:
                return best["id"]
        return None

    # ------------------------------------------------------------ FAITS
    def record(self, offer_id, ex, method=None):
        """Enregistre un fait observé (avec provenance). → (événements, issue) ; issue ∈ changed|unchanged|suspect"""
        now = self.clock()
        o = self.q("SELECT * FROM offers WHERE id=?", (offer_id,), one=True)
        pid = o["product_id"] or self.match_product(ex)
        if not o["product_id"]:
            self.q("UPDATE offers SET product_id=? WHERE id=?", (pid, offer_id))
            o["product_id"] = pid
        price, avail, cur = ex["price"], ex.get("availability") or "unknown", ex.get("currency") or "EUR"
        conf = ex.get("confidence", 0.9 if (method or ex.get("method")) == "feed" else 0.8)
        src_method = method or ex.get("method")
        prev = self.q("SELECT * FROM observations WHERE offer_id=? ORDER BY first_seen DESC, id DESC LIMIT 1", (offer_id,), one=True)
        events = []

        if prev and prev["price"]:
            ratio = price / prev["price"]
            if (ratio < SUSPECT_DROP or ratio > SUSPECT_RISE) and o["pending_price"] != price:
                self.q("UPDATE offers SET pending_price=?, quality='SUSPECT' WHERE id=?", (price, offer_id))
                events.append(self._event("PRICE_ANOMALY", offer=o, previous={"price": prev["price"]}, new={"price": price},
                                          confidence=0.3, method=src_method,
                                          data={"note": "variation inhabituelle, re-vérification programmée avant enregistrement"}))
                return events, "suspect"
        q = N.quality(ex)
        self.q("UPDATE offers SET pending_price=NULL, quality=? WHERE id=?", (q, offer_id))

        if prev and prev["price"] == price and prev["availability"] == avail and (prev["list_price"] or None) == (ex.get("list_price") or None):
            self.q("UPDATE observations SET last_seen=?, n=n+1 WHERE id=?", (now, prev["id"]))
            events += self._promotion_transition(o, price, ex.get("list_price"))
            return events, "unchanged"
        self.q("INSERT INTO observations(offer_id, first_seen, last_seen, price, currency, availability, method, raw_price, list_price, "
               "confidence, quality, found) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
               (offer_id, now, now, price, cur, avail, src_method, str(ex.get("raw_price") or price), ex.get("list_price"),
                conf, q, json.dumps(ex.get("found") or {})))
        if not prev:
            events.append(self._event("NEW_OFFER", offer=o, new={"price": price, "availability": avail}, confidence=conf,
                                      method=src_method, data={"title": ex.get("title")}))
        else:
            if abs(price - prev["price"]) / prev["price"] >= SIGNIFICANT:
                chg = round((price - prev["price"]) / prev["price"] * 100, 1)
                typ = "PRICE_DROP" if price < prev["price"] else "PRICE_INCREASE"
                events.append(self._event(typ, offer=o, previous={"price": prev["price"]}, new={"price": price},
                                          confidence=conf, method=src_method, data={"change_pct": chg}))
                if price < prev["price"]:
                    low = self.q("SELECT MIN(price) m FROM observations WHERE offer_id=? AND last_seen>=? AND id<>(SELECT MAX(id) FROM observations WHERE offer_id=?)",
                                 (offer_id, now - 90 * 86400, offer_id), one=True)["m"]
                    if low is None or price < low:
                        events.append(self._event("NEW_LOW", offer=o, previous={"low_90d": low}, new={"price": price},
                                                  confidence=conf, method=src_method, data={"window_days": 90}))
            if prev["availability"] != "in_stock" and avail == "in_stock":
                events.append(self._event("BACK_IN_STOCK", offer=o, previous={"availability": prev["availability"]},
                                          new={"availability": avail, "price": price}, confidence=conf, method=src_method))
            if prev["availability"] == "in_stock" and avail == "out_of_stock":
                events.append(self._event("OUT_OF_STOCK", offer=o, previous={"availability": "in_stock"},
                                          new={"availability": avail}, confidence=conf, method=src_method))
        events += self._promotion_transition(o, price, ex.get("list_price"))
        return events, "changed"

    def _promotion_transition(self, o, price, list_price):
        """Promotion d'une offre : affichée (prix barré ≥ 5 %) ou observée (≥ 10 % sous sa médiane 30 j)."""
        adv = (1 - price / list_price) if list_price and list_price > price else 0.0
        series = self.offer_series(o["id"], self.today(), 31)
        prior = [p for d, p in series if d < self.today()]
        obs = (1 - price / I.median(prior)) if len(prior) >= 14 else 0.0
        active = adv >= PROMO_ADVERTISED_MIN or obs >= PROMO_OBSERVED_MIN
        was = bool(self.q("SELECT promo_active FROM offers WHERE id=?", (o["id"],), one=True)["promo_active"])
        if active == was:
            return []
        self.q("UPDATE offers SET promo_active=? WHERE id=?", (int(active), o["id"]))
        kind = "advertised+observed" if adv >= PROMO_ADVERTISED_MIN and obs >= PROMO_OBSERVED_MIN else \
            "advertised" if adv >= PROMO_ADVERTISED_MIN else "observed" if active else None
        typ = "PROMOTION_STARTED" if active else "PROMOTION_ENDED"
        return [self._event(typ, offer=o, previous={"promo": was}, new={"promo": active, "price": price},
                            confidence=0.9 if kind != "advertised" else 0.7,
                            data={"kind": kind, "advertised_discount": round(adv, 3) or None,
                                  "observed_vs_median_30d": round(obs, 3) if obs else None, "list_price": list_price})]

    # ------------------------------------------------------------ événements
    def _event(self, typ, offer=None, entity=None, product_id=None, previous=None, new=None, confidence=1.0,
               method=None, data=None):
        assert typ in EVENT_TYPES, typ
        now = self.clock()
        if offer:
            entity = entity or ("offer", offer["id"])
            product_id = product_id or offer.get("product_id")
            source = {"url": offer["url"], "merchant": offer["merchant"], "method": method or offer.get("last_method")}
        else:
            source = {"engine": "market-intelligence"}
        payload = {**(data or {}), "url": source.get("url"), "merchant": source.get("merchant")}
        payload.update({k: v for k, v in (new or {}).items() if k in ("price", "availability")})
        if previous and "price" in previous:
            payload["previous"] = previous["price"]
        eid = self.q("INSERT INTO events(at, type, offer_id, product_id, data, entity_type, entity_id, previous, new, confidence, source) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (now, typ, offer["id"] if offer else None, product_id, json.dumps(payload, ensure_ascii=False, default=str),
                      entity[0] if entity else None, entity[1] if entity else None,
                      json.dumps(previous, default=str) if previous is not None else None,
                      json.dumps(new, ensure_ascii=False, default=str) if new is not None else None, confidence,
                      json.dumps(source, ensure_ascii=False)))
        ev = {"id": eid, "at": now, "type": typ, "entity": {"type": entity[0], "id": entity[1]} if entity else None,
              "offer_id": offer["id"] if offer else None, "product_id": product_id, "previous": previous, "new": new,
              "confidence": confidence, "source": source, "data": payload}
        self.bus.publish(ev)
        self._webhooks(ev)
        return ev

    def _webhooks(self, ev):
        for h in self.q("SELECT * FROM webhooks"):
            types = json.loads(h["types"])
            if types and ev["type"] not in types:
                continue
            threading.Thread(target=_post, args=(h["url"], ev), daemon=True).start()

    def add_webhook(self, url, types=()):
        return self.q("INSERT INTO webhooks(url, types) VALUES (?,?)", (url, json.dumps(list(types))))

    # ------------------------------------------------------------ séries temporelles
    def _rows(self, offer_id, since_ts):
        return self.q("SELECT first_seen, last_seen, price, availability, list_price FROM observations "
                      "WHERE offer_id=? AND last_seen>=? ORDER BY first_seen, id", (offer_id, since_ts))

    def _state_on(self, rows, d, i_hint=0):
        """État d'une offre le jour d : dernier fait connu ce jour-là, s'il n'est pas périmé."""
        eod = day_start(d) + 86399
        i, cur = i_hint, None
        while i < len(rows) and rows[i]["first_seen"] <= eod:
            cur = rows[i]
            i += 1
        if cur is None or cur["last_seen"] < day_start(d) - STALE_S:
            return None, max(i - 1, 0)
        return cur, max(i - 1, 0)

    def offer_series(self, offer_id, as_of, days, in_stock_only=True):
        start = as_of - timedelta(days=days - 1)
        rows = self._rows(offer_id, day_start(start) - STALE_S)
        out, hint, d = [], 0, start
        while d <= as_of:
            r, hint = self._state_on(rows, d, hint)
            if r and (not in_stock_only or r["availability"] != "out_of_stock"):
                out.append((d, r["price"]))
            d += timedelta(days=1)
        return out

    def best_series(self, product_id, as_of, days=365):
        """Meilleur prix quotidien toutes offres (en stock, non périmées)."""
        start = as_of - timedelta(days=days - 1)
        offers = self.q("SELECT id FROM offers WHERE product_id=?", (product_id,))
        rows = {o["id"]: self._rows(o["id"], day_start(start) - STALE_S) for o in offers}
        hints = {k: 0 for k in rows}
        out, d = [], start
        while d <= as_of:
            best = None
            for oid, rr in rows.items():
                r, hints[oid] = self._state_on(rr, d, hints[oid])
                if r and r["availability"] != "out_of_stock":
                    best = r["price"] if best is None else min(best, r["price"])
            if best is not None:
                out.append((d, best))
            d += timedelta(days=1)
        return out

    # ------------------------------------------------------------ INTELLIGENCE (lecture pure, sans effet)
    def snapshot(self, product_id):
        as_of = self.today()
        p = self.q("SELECT * FROM products WHERE id=?", (product_id,), one=True)
        if not p:
            return None
        p["attributes"] = json.loads(p["attributes"] or "{}")
        offers = []
        stale_limit = self.clock() - STALE_S
        for o in self.q("SELECT * FROM offers WHERE product_id=?", (product_id,)):
            last = self.q("SELECT * FROM observations WHERE offer_id=? ORDER BY first_seen DESC, id DESC LIMIT 1", (o["id"],), one=True)
            if not last:
                continue
            fresh = last["last_seen"] >= stale_limit and o["status"] not in ("gone",)
            own = self.offer_series(o["id"], as_of, self.intel_cfg["window_days"])
            a = I.analyze(own, as_of, last["price"], self.intel_cfg) if own else {}
            offers.append({"offer_id": o["id"], "merchant": o["merchant"], "url": o["url"], "price": last["price"],
                           "list_price": last["list_price"], "availability": last["availability"] if fresh else "stale",
                           "observed_at": last["last_seen"], "method": last["method"], "quality": o["quality"] or last["quality"],
                           "confidence": last["confidence"], "promo_active": bool(o["promo_active"]),
                           "percentile": (a.get("position") or {}).get("percentile"),
                           "vs_median": (a.get("position") or {}).get("vs_median"), "state": a.get("state", "UNKNOWN")})
        live = [x for x in offers if x["availability"] == "in_stock" or (x["availability"] == "unknown")]
        best = min(live, key=lambda x: x["price"], default=None)
        series = self.best_series(product_id, as_of, 365)
        intel = I.analyze(series, as_of, best["price"] if best else None, self.intel_cfg) if best and series else \
            {"state": "UNKNOWN", "n_days": len(series), "current": best["price"] if best else None}
        prev_price = None
        if best:
            pr = self.q("SELECT price FROM observations WHERE offer_id=? ORDER BY first_seen DESC, id DESC LIMIT 1 OFFSET 1",
                        (best["offer_id"],), one=True)
            prev_price = pr["price"] if pr else None
        promo = I.promotion(best["price"], prev_price, best["list_price"], intel.get("position")) if best else None
        in_stock = [x for x in offers if x["availability"] == "in_stock"]
        disp = None
        if len(in_stock) >= 2:
            lo, hi = min(x["price"] for x in in_stock), max(x["price"] for x in in_stock)
            disp = {"offers": len(in_stock), "min": lo, "max": hi, "spread_pct": round((hi - lo) / lo, 4)}
        d7 = as_of - timedelta(days=7)
        was = 0
        for o in offers:
            r, _ = self._state_on(self._rows(o["offer_id"], day_start(d7) - STALE_S), d7)
            was += bool(r and r["availability"] == "in_stock")
        drops = {}
        for e in self.q("SELECT offer_id, data FROM events WHERE type='PRICE_DROP' AND product_id=? AND at>=?",
                        (product_id, self.clock() - S.CFG["emerging_window_h"] * 3600)):
            chg = -json.loads(e["data"]).get("change_pct", 0) / 100
            drops[e["offer_id"]] = max(drops.get(e["offer_id"], 0), chg)
        qualities = {x["quality"] for x in offers if x["quality"]}
        quality = "SUSPECT" if best and best["quality"] == "SUSPECT" else "CONFLICTING" if "CONFLICTING" in qualities else \
            (best or {}).get("quality") or "UNKNOWN"
        snap = {"product_id": product_id, "as_of": as_of, "product": p, "intel": intel, "promotion": promo,
                "merchant": best["merchant"] if best else None, "offers": offers, "offers_in_stock": len(in_stock),
                "in_stock_7d_ago": was, "dispersion": disp, "recent_drops": drops, "quality": quality,
                "extraction_confidence": (best or {}).get("confidence") or 0.8}
        snap["signals"] = S.evaluate(snap)
        return snap

    # ------------------------------------------------------------ SIGNAUX + SURVEILLANCES (effets)
    def refresh_product(self, product_id):
        snap = self.snapshot(product_id)
        if not snap:
            return None
        now = self.clock()
        # écart entre marchands
        gap = bool(snap["dispersion"] and snap["dispersion"]["spread_pct"] >= GAP_THRESHOLD)
        if gap != bool(snap["product"]["gap_active"]):
            self.q("UPDATE products SET gap_active=? WHERE id=?", (int(gap), product_id))
            if gap:
                self._event("MERCHANT_PRICE_GAP", entity=("product", product_id), product_id=product_id,
                            new=snap["dispersion"], confidence=0.9)
        # cycle de vie des signaux : un seul signal actif par (produit, type)
        active = {r["type"]: r for r in self.q("SELECT * FROM signals WHERE product_id=? AND status='active'", (product_id,))}
        seen = set()
        for sig in snap["signals"]:
            seen.add(sig["type"])
            payload = json.dumps(sig, ensure_ascii=False, default=str)
            if sig["type"] in active:
                self.q("UPDATE signals SET updated_at=?, payload=? WHERE id=?", (now, payload, active[sig["type"]]["id"]))
            else:
                sid = self.q("INSERT INTO signals(product_id, type, status, raised_at, updated_at, payload) VALUES (?,?,?,?,?,?)",
                             (product_id, sig["type"], "active", now, now, payload))
                self._event("SIGNAL_RAISED", entity=("signal", sid), product_id=product_id, new=sig,
                            confidence=sig["confidence"], data={"signal": sig["type"], "price": sig["current_price"],
                                                                "reasons": sig["reasons"]})
        for typ, row in active.items():
            if typ not in seen:
                self.q("UPDATE signals SET status='cleared', cleared_at=? WHERE id=?", (now, row["id"]))
                self._event("SIGNAL_CLEARED", entity=("signal", row["id"]), product_id=product_id,
                            previous=json.loads(row["payload"]), confidence=1.0, data={"signal": typ})
        self._evaluate_watches(snap)
        self._snap[product_id] = snap
        return snap

    def add_watch(self, spec):
        cond = spec.get("condition", "opportunity")
        if cond not in ("opportunity", "target", "acceptable", "any_good_state"):
            raise ValueError("condition inconnue : " + cond)
        if not (spec.get("category") or spec.get("product_id")):
            raise ValueError("une surveillance porte sur une catégorie ou un produit")
        wid = self.q("INSERT INTO watches(spec, created_at) VALUES (?,?)", (json.dumps(spec, ensure_ascii=False), self.clock()))
        for p in self.q("SELECT id FROM products"):
            self.refresh_product(p["id"])
        return wid

    def _evaluate_watches(self, snap):
        now = self.clock()
        pid = snap["product_id"]
        types = {s["type"] for s in snap["signals"]}
        for w in self.q("SELECT * FROM watches WHERE active=1"):
            spec = json.loads(w["spec"])
            in_scope = S.product_matches(spec, snap["product"], snap["intel"].get("current"))
            ok, reason = S.condition_met(spec, snap, types) if in_scope else (False, None)
            m = self.q("SELECT * FROM watch_matches WHERE watch_id=? AND product_id=? AND active=1", (w["id"], pid), one=True)
            if ok and not m:
                self.q("INSERT INTO watch_matches(watch_id, product_id, active, matched_at, reason, price) VALUES (?,?,?,?,?,?)",
                       (w["id"], pid, 1, now, reason, snap["intel"].get("current")))
                self._event("WATCH_MATCHED", entity=("watch", w["id"]), product_id=pid,
                            new={"price": snap["intel"].get("current"), "state": snap["intel"].get("state")},
                            confidence=max([s["confidence"] for s in snap["signals"]] or [0.8]),
                            data={"watch_id": w["id"], "reason": reason, "merchant": snap.get("merchant"),
                                  "title": snap["product"]["title"], "price": snap["intel"].get("current")})
            elif m and not ok:
                self.q("UPDATE watch_matches SET active=0, cleared_at=? WHERE id=?", (now, m["id"]))
                self._event("WATCH_UNMATCHED", entity=("watch", w["id"]), product_id=pid, previous={"price": m["price"]},
                            new={"price": snap["intel"].get("current")}, data={"watch_id": w["id"]})

    def watched_products(self):
        """Produits dans le périmètre d'au moins une surveillance active (→ surveillés plus souvent)."""
        ws = [json.loads(w["spec"]) for w in self.q("SELECT spec FROM watches WHERE active=1")]
        out = set()
        for provider in self.demand_providers:
            out |= set(provider())
        if not ws:
            return out
        for p in self.q("SELECT * FROM products"):
            p["attributes"] = json.loads(p["attributes"] or "{}")
            if any(S.product_matches(w, p, None) for w in ws):
                out.add(p["id"])
        return out

    # ------------------------------------------------------------ vérification
    def check(self, offer_id, refresh=True):
        o = self.q("SELECT * FROM offers WHERE id=?", (offer_id,), one=True)
        now = self.clock()
        confirming = o["pending_price"] is not None
        r = self.fetcher.get(o["url"], None if confirming else o["etag"], None if confirming else o["last_modified"])
        st, method, outcome = r["status"], None, None
        if st == "ok":
            ex = X.extract(r["html"], self.rules_for(o["host"]))
            if ex:
                method = ex["method"]
                _, outcome = self.record(offer_id, ex)
                for hook in self.extract_hooks:
                    hook(offer_id, ex, r["html"])
                self.q("UPDATE offers SET etag=?, last_modified=?, last_method=?, status='active' WHERE id=?",
                       (r.get("etag"), r.get("last_modified"), method, offer_id))
            else:
                st = "no_price"
        elif st == "not_modified":
            last = self.q("SELECT id, price, list_price FROM observations WHERE offer_id=? ORDER BY id DESC LIMIT 1", (offer_id,), one=True)
            if last:
                self.q("UPDATE observations SET last_seen=?, n=n+1 WHERE id=?", (now, last["id"]))
                self._promotion_transition(self.q("SELECT * FROM offers WHERE id=?", (offer_id,), one=True), last["price"], last["list_price"])
            outcome = "unchanged"
        self.q("INSERT INTO checks(offer_id, host, at, status, code, elapsed_ms, method) VALUES (?,?,?,?,?,?,?)",
               (offer_id, o["host"], now, st, r.get("code"), r.get("elapsed_ms"), method))
        pid = self.q("SELECT product_id FROM offers WHERE id=?", (offer_id,), one=True)["product_id"]
        if refresh and pid and outcome in ("changed", "unchanged", "suspect"):
            self.refresh_product(pid)
        self._schedule(self.q("SELECT * FROM offers WHERE id=?", (offer_id,), one=True), st, outcome, r.get("retry_after"))
        return {"offer_id": offer_id, "product_id": pid, "status": st, "outcome": outcome, "method": method}

    def schedule_factors(self, o, watched=None):
        """Facteurs de fréquence (§15), explicites pour l'observabilité."""
        watched = self.watched_products() if watched is None else watched
        prio = 1 if o["product_id"] in watched else o["priority"]
        f, why = 1.0, [f"priorité {prio}" + (" (demande active)" if prio < o["priority"] else "")]
        snap = self._snap.get(o["product_id"])
        if snap:
            vol = ((snap["intel"].get("stats") or {}).get("volatility_90")) or 0
            if vol >= 0.05:
                f *= 0.7
                why.append(f"volatil ({vol * 100:.0f} %)")
            if snap["in_stock_7d_ago"] >= 2 and snap["offers_in_stock"] <= 1:
                f *= 0.5
                why.append("stock en baisse")
        today = self.today()
        n, ev = I.days_to_next_event(today, horizon=7)
        if I.event_of(today) or n is not None:
            f *= 0.5
            why.append(f"période commerciale ({(I.event_of(today) or ev).replace('_', ' ')})")
        return prio, f, why

    def _schedule(self, o, st, outcome, retry_after, watched=None):
        now = self.clock()
        prio, factor, why = self.schedule_factors(o, watched)
        base = PRIORITY_BASE[prio]
        interval, fails, status = min(o["interval_s"] or base, base * 2), o["fail_count"], o["status"]
        if st in ("ok", "not_modified"):
            fails = 0
            if outcome == "suspect":
                nxt, why = now + 120, ["re-vérification d'un prix suspect"]
            else:
                interval = interval * 0.5 if outcome == "changed" else interval * 1.25
                interval = max(base / 4, min(base * 2, interval))
                eff = max(base / 4, interval * factor, MIN_INTERVAL_S)
                nxt = now + eff
                why.append(f"toutes les {eff / 3600:.1f} h" if eff >= 3600 else f"toutes les {eff / 60:.0f} min")
        elif st == "rate_limited":
            fails += 1
            nxt = now + max(retry_after or 0, base * 2)
            why = ["limitation de débit du site (429)"]
        elif st in ("gone", "disallowed"):
            status, nxt = st, now + 7 * 86400
            if o["status"] != st:
                self._event("OFFER_REMOVED" if st == "gone" else "SOURCE_DISALLOWED", offer=o, previous={"status": o["status"]},
                            new={"status": st})
                if st == "gone" and o["product_id"]:
                    alive = self.q("SELECT COUNT(*) n FROM offers WHERE product_id=? AND status NOT IN ('gone') AND id<>?",
                                   (o["product_id"], o["id"]), one=True)["n"]
                    if alive == 0:
                        self._event("PRODUCT_DISCONTINUED", entity=("product", o["product_id"]), product_id=o["product_id"],
                                    new={"offers_alive": 0}, confidence=0.6,
                                    data={"note": "plus aucune offre active connue pour ce produit"})
            why = [st]
        elif st == "blocked":
            fails += 1
            status, nxt = "blocked", now + 24 * 3600
            if o["status"] != "blocked":
                self._event("SOURCE_BLOCKED", offer=o, previous={"status": o["status"]}, new={"status": "blocked"},
                            data={"hint": "Site protégé : passer par un flux marchand ou une API partenaire"})
            why = ["site bloquant, nouvel essai dans 24 h"]
        else:
            fails += 1
            nxt = now + min(base * 2 ** fails, 48 * 3600)
            if st == "no_price" and fails == 3:
                self._event("EXTRACTION_FAILED", offer=o, data={"hint": "Aucun prix trouvé 3 fois : ajouter une règle de site"})
            why = [f"erreur ({st}), recul exponentiel"]
        self.q("UPDATE offers SET interval_s=?, next_check_at=?, last_check_at=?, fail_count=?, status=?, schedule_reason=? WHERE id=?",
               (interval, nxt, now, fails, status, ", ".join(why), o["id"]))

    def run_due(self, limit=500):
        now = self.clock()
        due = self.q("SELECT id FROM offers WHERE source='web' AND status IN ('active','blocked') AND next_check_at<=? "
                     "ORDER BY priority, next_check_at LIMIT ?", (now, limit))
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            results = list(pool.map(lambda r: self.check(r["id"], refresh=False), due))
        for f in self.q("SELECT id FROM feeds WHERE next_run_at<=?", (now,)):
            results.append(self.run_feed(f["id"], refresh=False))
        pids = {r.get("product_id") for r in results if r.get("product_id")} | \
            {p for r in results for p in r.get("product_ids", [])}
        for pid in sorted(pids):
            self.refresh_product(pid)
        # re-planifie après rafraîchissement : les facteurs dépendent de l'intelligence à jour
        watched = self.watched_products()
        for r in results:
            if r.get("offer_id") and r["status"] in ("ok", "not_modified") and r.get("outcome") != "suspect":
                o = self.q("SELECT * FROM offers WHERE id=?", (r["offer_id"],), one=True)
                self._reschedule_only(o, watched)
        return results

    def _reschedule_only(self, o, watched):
        prio, factor, why = self.schedule_factors(o, watched)
        base = PRIORITY_BASE[prio]
        eff = max(base / 4, min(base * 2, o["interval_s"] or base) * factor, MIN_INTERVAL_S)
        why.append(f"toutes les {eff / 3600:.1f} h" if eff >= 3600 else f"toutes les {eff / 60:.0f} min")
        self.q("UPDATE offers SET next_check_at=?, schedule_reason=? WHERE id=?", (o["last_check_at"] + eff, ", ".join(why), o["id"]))

    # ------------------------------------------------------------ flux marchands
    def add_feed(self, source, merchant, interval_s=6 * 3600):
        return self.q("INSERT INTO feeds(source, merchant, interval_s, next_run_at) VALUES (?,?,?,?)",
                      (source, merchant, interval_s, self.clock()))

    def run_feed(self, feed_id, refresh=True):
        f = self.q("SELECT * FROM feeds WHERE id=?", (feed_id,), one=True)
        pids = set()
        try:
            if re.match(r"https?://", f["source"]):
                req = urllib.request.Request(f["source"], headers={"User-Agent": self.fetcher.ua})
                with urllib.request.urlopen(req, timeout=60) as r:
                    text = r.read().decode("utf-8", "replace")
            else:
                with open(f["source"], encoding="utf-8") as fh:
                    text = fh.read()
            n = 0
            for it in parse_feed(text):
                if not it.get("link") or it.get("price") is None:
                    continue
                oid = self._feed_offer(it["link"], f)
                self.record(oid, {**it, "confidence": 0.9}, method="feed")
                self.q("UPDATE offers SET last_check_at=?, last_method='feed' WHERE id=?", (self.clock(), oid))
                pids.add(self.q("SELECT product_id FROM offers WHERE id=?", (oid,), one=True)["product_id"])
                n += 1
            status = "ok"
        except Exception as e:
            n, status = 0, f"error: {type(e).__name__}: {e}"
        self.q("UPDATE feeds SET next_run_at=?, last_status=?, last_count=? WHERE id=?",
               (self.clock() + f["interval_s"], status, n, feed_id))
        if refresh:
            for pid in pids:
                self.refresh_product(pid)
        return {"feed_id": feed_id, "status": status, "items": n, "product_ids": sorted(p for p in pids if p)}

    def _feed_offer(self, link, f):
        ex = self.q("SELECT id FROM offers WHERE url=?", (link,), one=True)
        if ex:
            return ex["id"]
        return self.q("INSERT INTO offers(url, host, merchant, source, feed_id, priority, next_check_at, created_at) "
                      "VALUES (?,?,?,?,?,?,?,?)", (link, _host(link), f["merchant"], "feed", f["id"], 2, 1e18, self.clock()))

    # ------------------------------------------------------------ lecture (API)
    def offers(self):
        return self.q("""SELECT o.*, p.title AS product_title, p.gtin, p.category,
            (SELECT price FROM observations WHERE offer_id=o.id ORDER BY id DESC LIMIT 1) AS price,
            (SELECT availability FROM observations WHERE offer_id=o.id ORDER BY id DESC LIMIT 1) AS availability,
            (SELECT list_price FROM observations WHERE offer_id=o.id ORDER BY id DESC LIMIT 1) AS list_price
            FROM offers o LEFT JOIN products p ON p.id=o.product_id ORDER BY o.id DESC""")

    def _snapshot_cached(self, pid):
        s = self._snap.get(pid)
        return s if s and s["as_of"] == self.today() else self.snapshot(pid)

    def products(self, category=None):
        out = []
        sql = "SELECT p.*, COUNT(o.id) AS offers FROM products p LEFT JOIN offers o ON o.product_id=p.id " + \
              ("WHERE p.category=? " if category else "") + "GROUP BY p.id ORDER BY p.id DESC"
        for p in self.q(sql, (category,) if category else ()):
            s = self._snapshot_cached(p["id"])
            p["attributes"] = json.loads(p["attributes"] or "{}")
            p["best_price"] = s["intel"].get("current") if s else None
            p["best_merchant"] = s["merchant"] if s else None
            p["state"] = s["intel"].get("state") if s else "UNKNOWN"
            p["percentile"] = ((s["intel"].get("position") or {}).get("percentile")) if s else None
            p["signals"] = [x["type"] for x in self.q("SELECT type FROM signals WHERE product_id=? AND status='active'", (p["id"],))]
            out.append(p)
        return out

    def intelligence(self, product_id):
        s = self._snapshot_cached(product_id)
        if not s:
            return None
        return {k: v for k, v in s.items() if k not in ("recent_drops",)} | {"as_of": s["as_of"].isoformat()}

    def history(self, product_id, days=365):
        as_of = self.today()
        series = self.best_series(product_id, as_of, days)
        offers = self.q("SELECT id, merchant, url FROM offers WHERE product_id=?", (product_id,))
        per = {o["id"]: [{"d": d.isoformat(), "p": p} for d, p in self.offer_series(o["id"], as_of, days, in_stock_only=False)]
               for o in offers}
        a = I.analyze(series, as_of, None, self.intel_cfg) if series else {}
        st = a.get("stats") or {}
        return {"product": self.q("SELECT * FROM products WHERE id=?", (product_id,), one=True), "offers": offers,
                "series": per, "daily": [{"d": d.isoformat(), "best": p} for d, p in series],
                "stats": {"current": a.get("current"), "typical_90d": st.get("median_90"), "low_90d": st.get("min_90"),
                          "low_all": min((p for _, p in series), default=None), **st}}

    def facts(self, product_id=None, offer_id=None, limit=200):
        """Faits observés, avec leur provenance complète (§5.1, §16)."""
        where, args = [], []
        if offer_id:
            where.append("ob.offer_id=?"); args.append(offer_id)
        if product_id:
            where.append("o.product_id=?"); args.append(product_id)
        rows = self.q("SELECT ob.*, o.url, o.merchant, o.product_id FROM observations ob JOIN offers o ON o.id=ob.offer_id "
                      + ("WHERE " + " AND ".join(where) if where else "") + " ORDER BY ob.first_seen DESC LIMIT ?", (*args, limit))
        for r in rows:
            r["found"] = json.loads(r["found"] or "{}")
            r["observed_from"] = datetime.fromtimestamp(r["first_seen"], timezone.utc).isoformat()
            r["observed_to"] = datetime.fromtimestamp(r["last_seen"], timezone.utc).isoformat()
            r["confirmations"] = r.pop("n")
        return rows

    def signals(self, active=True, type_=None, product_id=None):
        sql, args = "SELECT * FROM signals WHERE 1=1", []
        if active:
            sql += " AND status='active'"
        if type_:
            sql += " AND type=?"; args.append(type_)
        if product_id:
            sql += " AND product_id=?"; args.append(product_id)
        rows = self.q(sql + " ORDER BY updated_at DESC", args)
        for r in rows:
            r["payload"] = json.loads(r["payload"])
        return rows

    def watches(self):
        out = []
        for w in self.q("SELECT * FROM watches ORDER BY id DESC"):
            w["spec"] = json.loads(w["spec"])
            w["matches"] = self.q("SELECT m.*, p.title FROM watch_matches m JOIN products p ON p.id=m.product_id "
                                  "WHERE watch_id=? AND m.active=1", (w["id"],))
            out.append(w)
        return out

    def patterns(self, by="category", days=730):
        as_of = self.today()
        groups = {}
        for p in self.q("SELECT id, category, brand FROM products"):
            if by == "merchant":
                for o in self.q("SELECT id, merchant FROM offers WHERE product_id=?", (p["id"],)):
                    groups.setdefault(o["merchant"], []).append(self.offer_series(o["id"], as_of, days))
            else:
                key = p[by] or "non classé"
                groups.setdefault(key, []).append(self.best_series(p["id"], as_of, days))
        return I.patterns(groups)

    def events(self, since_id=0, limit=200, type_=None):
        rows = self.q("SELECT * FROM events WHERE id>?" + (" AND type=?" if type_ else "") + " ORDER BY id DESC LIMIT ?",
                      (since_id, type_, limit) if type_ else (since_id, limit))
        for r in rows:
            for k in ("data", "previous", "new", "source"):
                r[k] = json.loads(r[k]) if r.get(k) else None
        return rows

    def health(self, hours=24):
        since = self.clock() - hours * 3600
        out = {}
        for r in self.q("SELECT host, status, method, elapsed_ms FROM checks WHERE at>=?", (since,)):
            h = out.setdefault(r["host"], {"checks": 0, "ok": 0, "statuses": {}, "methods": {}, "ms": [], "quality": {}})
            h["checks"] += 1
            h["ok"] += r["status"] in ("ok", "not_modified")
            h["statuses"][r["status"]] = h["statuses"].get(r["status"], 0) + 1
            if r["method"]:
                h["methods"][r["method"]] = h["methods"].get(r["method"], 0) + 1
            if r["elapsed_ms"] is not None:
                h["ms"].append(r["elapsed_ms"])
        for r in self.q("SELECT host, quality, COUNT(*) n FROM offers WHERE quality IS NOT NULL GROUP BY host, quality"):
            out.setdefault(r["host"], {"checks": 0, "ok": 0, "statuses": {}, "methods": {}, "ms": [], "quality": {}})["quality"][r["quality"]] = r["n"]
        for h in out.values():
            h["success_rate"] = round(h["ok"] / h["checks"], 3) if h["checks"] else None
            ms = h.pop("ms")
            h["median_ms"] = I.median(ms) if ms else None
        return out

    def metrics(self):
        """Observabilité globale : volumes, couverture d'historique, signaux, bruit."""
        prods = self.q("SELECT id FROM products")
        cov = sum(1 for p in prods if len(self.best_series(p["id"], self.today(), 90)) >= self.intel_cfg["min_days"])
        ev = {r["type"]: r["n"] for r in self.q("SELECT type, COUNT(*) n FROM events WHERE at>=? GROUP BY type", (self.clock() - 86400,))}
        return {
            "products": len(prods), "offers": self.q("SELECT COUNT(*) n FROM offers", one=True)["n"],
            "facts": self.q("SELECT COUNT(*) n FROM observations", one=True)["n"],
            "confirmations": self.q("SELECT COALESCE(SUM(n),0) n FROM observations", one=True)["n"],
            "products_with_enough_history": cov,
            "active_signals": {r["type"]: r["n"] for r in self.q("SELECT type, COUNT(*) n FROM signals WHERE status='active' GROUP BY type")},
            "events_24h": ev,
            "quality": {r["quality"] or "—": r["n"] for r in self.q("SELECT quality, COUNT(*) n FROM offers GROUP BY quality")},
            "watches": self.q("SELECT COUNT(*) n FROM watches WHERE active=1", one=True)["n"],
        }


def _post(url, ev, tries=3):
    body = json.dumps(ev, ensure_ascii=False).encode()
    for k in range(tries):
        try:
            req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10):
                return True
        except Exception:
            time.sleep(2 ** k)
    return False


# ------------------------------------------------------------------ parsing des flux
_G = "{http://base.google.com/ns/1.0}"


def _feed_price(v, currency_hint=None):
    p = X.parse_price(v)
    cur = X.parse_currency((re.search(r"[A-Z]{3}", v or "") or [None])[0] if isinstance(v, str) else None, v or "")
    return p, cur or currency_hint


def parse_feed(text):
    """Flux Google Merchant (XML RSS/Atom avec g:) ou CSV/TSV avec en-têtes équivalents."""
    items = []
    s = text.lstrip()
    if s.startswith("<"):
        root = ET.fromstring(s)
        for it in root.iter():
            if it.tag not in ("item", "{http://www.w3.org/2005/Atom}entry"):
                continue
            g = lambda k: (it.findtext(_G + k) or it.findtext(k) or "").strip() or None
            items.append(_feed_row({"id": g("id"), "title": g("title"), "link": g("link"), "price": g("price"),
                                    "sale_price": g("sale_price"), "availability": g("availability"),
                                    "gtin": g("gtin"), "brand": g("brand"), "mpn": g("mpn")}))
    else:
        dialect = csv.Sniffer().sniff(s[:2000], delimiters=",;\t|")
        for row in csv.DictReader(io.StringIO(s), dialect=dialect):
            row = {k.strip().lower().replace("g:", ""): (v or "").strip() for k, v in row.items() if k}
            items.append(_feed_row(row))
    return items


def _feed_row(r):
    price, cur = _feed_price(r.get("price"))
    sale, cur2 = _feed_price(r.get("sale_price")) if r.get("sale_price") else (None, None)
    final = sale if sale and price and sale < price else price
    return {"link": r.get("link"), "title": r.get("title"), "price": final, "list_price": price if sale else None,
            "currency": cur2 or cur or "EUR", "availability": X.parse_availability(r.get("availability")) or "unknown",
            "gtin": X.clean_gtin(r.get("gtin")), "brand": r.get("brand"), "mpn": r.get("mpn"), "method": "feed"}
