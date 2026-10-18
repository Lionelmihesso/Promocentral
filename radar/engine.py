"""DEALS — moteur quotidien.

Le marché (listener/) dit ce qui s'est passé ; ce module en tire, une fois par jour :
  - le signal de marché des produits dont un prix a bougé : bon prix, très bon prix, fausse remise (prix barré gonflé) ;
  - les similarités entre produits (caractéristiques, même catégorie), une fois par semaine ;
  - le plan de relecture des offres : tout, chaque jour, tant que la passe tient dans la nuit ; au-delà, adaptatif
    (jamais plus d'une fois par jour, et un deal en cours est toujours relu le jour même).
Il porte aussi les tables du produit, lues et écrites par radar/shop.py : comptes, marques suivies, favoris, clics sortants.

Contraintes : un passage par jour, aucun LLM, calcul borné, tâches idempotentes (clé = nom + jour).
Pas de surveillance de prix ni d'opportunités personnelles : un deal est un deal, le même pour tout le monde ;
seule la marque suivie change l'ordre (radar/shop.py).
"""
import json
import os
import time
from collections import Counter
from datetime import timedelta

from collect.retailers import MIN_INTERVAL_S

from .verify import verify

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS preferences (user_id INTEGER NOT NULL, kind TEXT NOT NULL, value TEXT NOT NULL, created_at REAL NOT NULL,
  PRIMARY KEY (user_id, kind, value));                                                   -- kind : brand (catégorie possible, non exposée)
CREATE TABLE IF NOT EXISTS saves (user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, created_at REAL NOT NULL,
  PRIMARY KEY (user_id, product_id));
CREATE TABLE IF NOT EXISTS clicks (id INTEGER PRIMARY KEY, at REAL NOT NULL, day TEXT NOT NULL, user_id INTEGER,
  product_id INTEGER NOT NULL, offer_id INTEGER NOT NULL, merchant TEXT, source TEXT);
CREATE INDEX IF NOT EXISTS clicks_day ON clicks(day);
CREATE TABLE IF NOT EXISTS similarity (product_id INTEGER NOT NULL, other_id INTEGER NOT NULL, score REAL NOT NULL, computed_on TEXT NOT NULL,
  PRIMARY KEY (product_id, other_id));
CREATE TABLE IF NOT EXISTS market_signals (product_id INTEGER PRIMARY KEY, state TEXT NOT NULL, data TEXT NOT NULL, day TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs (name TEXT NOT NULL, key TEXT NOT NULL, started REAL NOT NULL, ended REAL, status TEXT NOT NULL, stats TEXT,
  PRIMARY KEY (name, key));
"""
ENERGY = "ABCDEFG"
NIGHT_BUDGET_S = int(os.environ.get("DEALS_NIGHT_BUDGET_S", 4 * 3600))   # durée maximale de la passe de nuit
REQUEST_INTERVAL_S = MIN_INTERVAL_S                                     # politesse : la même valeur que la collecte


class Radar:
    def __init__(self, listener):
        self.L, self.q = listener, listener.q
        with listener.lock:
            listener.db.executescript(SCHEMA)
            listener.db.commit()
        # demande réelle → priorité de collecte : les produits gardés en favori par au moins un compte
        listener.demand_providers.append(lambda: {r["product_id"] for r in self.q("SELECT DISTINCT product_id FROM saves")})

    def today(self):
        return self.L.today()

    # ============================================================ COMPTES ET MARQUES SUIVIES
    def user(self, name):
        u = self.q("SELECT id FROM users WHERE name=?", (name,), one=True)
        return u["id"] if u else self.q("INSERT INTO users(name, created_at) VALUES (?,?)", (name, time.time()))

    def follow(self, user_id, kind, value, on=True):
        if kind not in ("brand", "category"):
            raise ValueError("kind : brand | category")
        if on:
            self.q("INSERT OR IGNORE INTO preferences(user_id, kind, value, created_at) VALUES (?,?,?,?)", (user_id, kind, value, time.time()))
        else:
            self.q("DELETE FROM preferences WHERE user_id=? AND kind=? AND value=?", (user_id, kind, value))

    # ============================================================ SIGNAUX DE MARCHÉ (objectifs, sans utilisateur)
    def market_signal(self, product_id):
        """Ce que le marché dit d'un produit aujourd'hui. La remise affichée et la qualité du prix sont deux choses distinctes."""
        s = self.L.snapshot(product_id)
        if not s or s["intel"].get("current") is None:
            return None
        it, p = s["intel"], s["product"]
        ref = it.get("reference_price")
        state = {"EXCEPTIONAL": "VERY_GOOD_PRICE", "GOOD": "GOOD_PRICE"}.get(it.get("state"), "NORMAL")
        best = min((o for o in s["offers"] if o["availability"] in ("in_stock", "unknown")), key=lambda o: o["price"], default=None)
        prev = self.q("SELECT price FROM observations WHERE offer_id=? ORDER BY first_seen DESC, id DESC LIMIT 1 OFFSET 1",
                      (best["offer_id"],), one=True) if best else None
        drop = round(1 - it["current"] / prev["price"], 4) if prev and prev["price"] and it["current"] < prev["price"] else 0
        inflated = False
        if best and best.get("list_price") and ref:   # prix barré affiché nettement au-dessus du prix habituel → fausse remise
            inflated = verify(it["current"], best["list_price"], [], self.today(), ref)["verdict"] == "REMISE_GONFLEE"
        st = it.get("stats") or {}
        return {"product_id": product_id, "brand": p["brand"], "category": p["category"], "title": p["title"], "price": it["current"],
                "reference_price": ref, "state": state, "below_ref": round(1 - it["current"] / ref, 4) if ref else 0,
                "drop": drop, "back_in_stock": s["offers_in_stock"] > 0 and s["in_stock_7d_ago"] == 0 and s["intel"].get("n_days", 0) > 7,
                "inflated": inflated, "merchant": s["merchant"], "url": best and best["url"],
                "low": st.get("min_365") or st.get("min_90"), "high": st.get("max_365") or st.get("max_90"), "attributes": p["attributes"]}

    def changed_products(self, day):
        """Produits dont un prix a changé (ou est apparu) ce jour-là : les seuls à recalculer, plus les favoris."""
        t0 = time.mktime(day.timetuple())
        rows = self.q("SELECT DISTINCT o.product_id FROM observations ob JOIN offers o ON o.id=ob.offer_id WHERE ob.first_seen>=? AND o.product_id IS NOT NULL", (t0,))
        saved = self.q("SELECT DISTINCT product_id FROM saves")
        return sorted({r["product_id"] for r in rows} | {r["product_id"] for r in saved})

    def inflated_products(self):
        """Produits dont le dernier signal connu est une fausse remise : exclus des listes de deals."""
        return {r["product_id"] for r in self.q("SELECT product_id, data FROM market_signals") if json.loads(r["data"]).get("inflated")}

    # ============================================================ SIMILARITÉ (produits similaires) — hebdomadaire
    @staticmethod
    def similarity(a, b):
        """Similarité déterministe sur les caractéristiques structurées ; même catégorie obligatoire."""
        if not a["category"] or a["category"] != b["category"]:
            return 0.0
        A, B = a["attributes"] or {}, b["attributes"] or {}
        keys = [k for k in set(A) & set(B)]
        if not keys:
            return 0.6 if a["brand"] == b["brand"] else 0.55
        diffs = []
        for k in keys:
            x, y = A[k], B[k]
            if k == "energy_class":
                diffs.append(min(1, abs(ENERGY.index(x) - ENERGY.index(y)) / 3) if x in ENERGY and y in ENERGY else 1)
            elif isinstance(x, (int, float)) and isinstance(y, (int, float)):
                diffs.append(min(1, abs(x - y) / max(abs(x), abs(y), 1e-9)))
            else:
                diffs.append(0 if x == y else 1)
        sim = 1 - sum(diffs) / len(diffs)
        return round(min(0.99, sim * 0.95 + (0.05 if a["brand"] == b["brand"] else 0)), 3)

    def compute_similarity(self, top=10, threshold=0.5):
        prods = self.q("SELECT id, brand, category, attributes FROM products WHERE category IS NOT NULL")
        for p in prods:
            p["attributes"] = json.loads(p["attributes"] or "{}")
        by_cat = {}
        for p in prods:
            by_cat.setdefault(p["category"], []).append(p)
        day, n = self.today().isoformat(), 0
        self.q("DELETE FROM similarity")
        for items in by_cat.values():
            for a in items:
                scores = sorted(((self.similarity(a, b), b["id"]) for b in items if b["id"] != a["id"]), reverse=True)
                for sc, oid in scores[:top]:
                    if sc >= threshold:
                        self.q("INSERT INTO similarity(product_id, other_id, score, computed_on) VALUES (?,?,?,?)", (a["id"], oid, sc, day))
                        n += 1
        return {"products": len(prods), "pairs": n}

    # ============================================================ FRÉQUENCE ADAPTATIVE (plafond : 1 fois par jour)
    def refresh_plan(self, day=None, budget_s=None):
        """→ (offer_ids à relire aujourd'hui, répartition par rythme).

        Promesse du produit : montrer les deals qui existent. Tant que la passe complète tient dans le budget de nuit
        (les sites sont lus en parallèle, chacun à son rythme poli), toutes les offres sont relues chaque jour.
        Au-delà seulement, mode adaptatif (bench/refresh_policy.py) : deal en cours, bon prix vu ces 3 derniers jours,
        favori, clic récent ou produit volatil → chaque jour ; marque suivie → tous les 3 jours ; le reste → chaque semaine."""
        day = day or self.today()
        budget_s = NIGHT_BUDGET_S if budget_s is None else budget_s
        offers = self.q("SELECT o.id, o.host, o.product_id, p.brand, p.category FROM offers o LEFT JOIN products p ON p.id=o.product_id "
                        "WHERE o.status!='gone'")
        per_host = Counter(o["host"] for o in offers)
        if (max(per_host.values()) if per_host else 0) * REQUEST_INTERVAL_S <= budget_s:
            return [o["id"] for o in offers], {"daily": len(offers), "every_3_days": 0, "weekly": 0, "mode": "full"}
        idx = day.toordinal()
        in_deal = {r["product_id"] for r in self.q(
            "SELECT o.product_id FROM offers o JOIN observations ob ON ob.id=(SELECT id FROM observations WHERE offer_id=o.id "
            "ORDER BY first_seen DESC, id DESC LIMIT 1) WHERE ob.list_price > ob.price AND o.product_id IS NOT NULL")}
        good = {r["product_id"] for r in self.q("SELECT product_id FROM market_signals WHERE state!='NORMAL' AND day>=?",
                                                ((day - timedelta(days=3)).isoformat(),))}
        saved = {r["product_id"] for r in self.q("SELECT DISTINCT product_id FROM saves")}
        clicked = {r["product_id"] for r in self.q("SELECT DISTINCT product_id FROM clicks WHERE day>=?", ((day - timedelta(days=3)).isoformat(),))}
        brands = {r["value"] for r in self.q("SELECT value FROM preferences WHERE kind='brand'")}
        cats = {r["value"] for r in self.q("SELECT value FROM preferences WHERE kind='category'")}
        since = time.mktime((day - timedelta(days=30)).timetuple())
        volatile = {r["pid"] for r in self.q("SELECT o.product_id pid, COUNT(*) n FROM observations ob JOIN offers o ON o.id=ob.offer_id "
                                             "WHERE ob.first_seen>=? GROUP BY o.product_id HAVING n>=3", (since,))}
        plan, tiers = [], {"daily": 0, "every_3_days": 0, "weekly": 0, "mode": "adaptive"}
        for o in offers:
            pid = o["product_id"]
            period, tier = (1, "daily") if pid in in_deal or pid in good or pid in saved or pid in clicked or pid in volatile else \
                (3, "every_3_days") if o["brand"] in brands or o["category"] in cats else (7, "weekly")
            if (idx + o["id"]) % period == 0:
                plan.append(o["id"])
                tiers[tier] += 1
        return plan, tiers

    # ============================================================ TÂCHE QUOTIDIENNE (idempotente)
    def run_daily(self, collector=None, force=False):
        day = self.today()
        key = day.isoformat()
        if not force and self.q("SELECT 1 FROM jobs WHERE name='daily' AND key=? AND status='done'", (key,), one=True):
            return {"skipped": True, "day": key}
        self.q("INSERT OR REPLACE INTO jobs(name, key, started, status) VALUES ('daily', ?, ?, 'running')", (key, time.time()))
        stats = {"day": key}
        if collector is not None:
            plan, tiers = self.refresh_plan(day)
            stats["refresh"] = {"offers": len(plan), **tiers}
            collector.nightly(offer_ids=plan)
        week = f"{day.isocalendar()[0]}-W{day.isocalendar()[1]}"
        if not self.q("SELECT 1 FROM jobs WHERE name='similarity' AND key=?", (week,), one=True):
            stats["similarity"] = self.compute_similarity()
            self.q("INSERT INTO jobs(name, key, started, ended, status) VALUES ('similarity', ?, ?, ?, 'done')", (week, time.time(), time.time()))
        pids = self.changed_products(day)
        sigs = [s for s in (self.market_signal(p) for p in pids) if s]
        for sg in sigs:     # état conservé par produit : recalculé seulement quand le prix bouge (ou pour un favori)
            self.q("INSERT OR REPLACE INTO market_signals(product_id, state, data, day) VALUES (?,?,?,?)",
                   (sg["product_id"], sg["state"], json.dumps(sg, default=str), key))
        stats["signals"] = {"products": len(pids), "good_or_better": sum(s["state"] != "NORMAL" for s in sigs),
                            "inflated": sum(s["inflated"] for s in sigs)}
        self.q("UPDATE jobs SET ended=?, status='done', stats=? WHERE name='daily' AND key=?", (time.time(), json.dumps(stats), key))
        return stats
