"""DEALS — le radar personnel. MARCHÉ → OPPORTUNITÉ → UTILISATEUR → SUIVI → ALTERNATIVE (audit v15).

Le moteur de marché (listener/) dit ce qui s'est passé : « ce produit est 17 % sous son prix habituel ».
Ce module décide si cela compte pour UN utilisateur : « … et c'est probablement pertinent pour vous ».

Contraintes : un passage par jour, aucun LLM, calcul borné.
  - les signaux ne sont recalculés que pour les produits dont le prix a bougé, plus les produits suivis ;
  - les similarités (alternatives) sont précalculées une fois par semaine, catégorie par catégorie ;
  - la fréquence de relecture est adaptative MAIS plafonnée à une fois par jour : suivi → chaque jour,
    centres d'intérêt → tous les 3 jours, le reste → chaque semaine ;
  - chaque tâche est idempotente (clé = nom + jour) ; une relance ne crée aucun doublon.
"""
import json
import time
from datetime import date, timedelta

from .verify import verify

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, max_alerts_per_day INTEGER NOT NULL DEFAULT 3,
  budget_max REAL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS preferences (user_id INTEGER NOT NULL, kind TEXT NOT NULL, value TEXT NOT NULL, created_at REAL NOT NULL,
  PRIMARY KEY (user_id, kind, value));                                                   -- kind : brand | category
CREATE TABLE IF NOT EXISTS interactions (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, kind TEXT NOT NULL, product_id INTEGER,
  brand TEXT, category TEXT, query TEXT, at REAL NOT NULL);                              -- search view save dismiss click alt_accept alt_reject
CREATE INDEX IF NOT EXISTS interactions_user ON interactions(user_id, at);
CREATE TABLE IF NOT EXISTS user_watches (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, kind TEXT NOT NULL DEFAULT 'product',
  product_id INTEGER, spec TEXT NOT NULL DEFAULT '{}', target_price REAL NOT NULL,
  deadline TEXT, alternatives_allowed INTEGER NOT NULL DEFAULT 1, constraints TEXT NOT NULL DEFAULT '{}', rejected TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'active', created_at REAL NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS user_watch_product ON user_watches(user_id, product_id) WHERE kind='product';
CREATE TABLE IF NOT EXISTS opportunities (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, type TEXT NOT NULL,
  score REAL NOT NULL, reason TEXT, price REAL, reference_price REAL, day TEXT NOT NULL, expires_at TEXT, watch_id INTEGER,
  alt_of_product_id INTEGER, section TEXT, notified INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL,
  UNIQUE (user_id, product_id, type, day));
CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, day TEXT NOT NULL, title TEXT NOT NULL,
  body TEXT NOT NULL, opportunity_ids TEXT NOT NULL, created_at REAL NOT NULL, UNIQUE (user_id, day));
CREATE TABLE IF NOT EXISTS similarity (product_id INTEGER NOT NULL, other_id INTEGER NOT NULL, score REAL NOT NULL, computed_on TEXT NOT NULL,
  PRIMARY KEY (product_id, other_id));
CREATE TABLE IF NOT EXISTS market_signals (product_id INTEGER PRIMARY KEY, state TEXT NOT NULL, data TEXT NOT NULL, day TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs (name TEXT NOT NULL, key TEXT NOT NULL, started REAL NOT NULL, ended REAL, status TEXT NOT NULL, stats TEXT,
  PRIMARY KEY (name, key));
"""
PRIORITY = ["TARGET_REACHED", "ALTERNATIVE", "EXCEPTIONAL_PRICE", "PRICE_DROP", "BACK_IN_STOCK", "NEW_OPPORTUNITY"]
COOLDOWN_DAYS = 7          # opportunités : pas deux fois le même produit en 7 jours, sauf prix encore plus bas
WATCH_COOLDOWN_DAYS = 14   # prix atteint / alternative : pas de rappel avant 14 jours…
WATCH_REPEAT_DROP = 0.05   # … sauf si le prix baisse encore d'au moins 5 %
MAX_OPP_PER_DAY = 8        # opportunités retenues par utilisateur et par jour (le fil reste court)
DISCOVERY_MIN_BELOW = 0.15 # « Vous ne cherchiez pas ça » : très bon prix ET ≥ 15 % sous l'habituel (même définition que bench/refresh_policy)
MAX_OPPORTUNITY_ALERTS_PER_WEEK = 2   # alertes « une offre pourrait vous intéresser » ; prix atteint et alternatives ne sont pas plafonnés ici
ENERGY = "ABCDEFG"


class Radar:
    def __init__(self, listener):
        self.L, self.q = listener, listener.q
        with listener.lock:
            listener.db.executescript(SCHEMA)
            listener.db.commit()
        # une seule source de vérité : la priorité de collecte du moteur de marché lit les surveillances des utilisateurs
        listener.demand_providers.append(lambda: {r["product_id"] for r in self.q(
            "SELECT DISTINCT product_id FROM user_watches WHERE status='active' AND kind='product'")})

    def today(self):
        return self.L.today()

    # ============================================================ COUCHE UTILISATEUR
    def user(self, name, budget_max=None, max_alerts_per_day=3):
        u = self.q("SELECT id FROM users WHERE name=?", (name,), one=True)
        return u["id"] if u else self.q("INSERT INTO users(name, budget_max, max_alerts_per_day, created_at) VALUES (?,?,?,?)",
                                        (name, budget_max, max_alerts_per_day, time.time()))

    def follow(self, user_id, kind, value, on=True):
        if kind not in ("brand", "category"):
            raise ValueError("kind : brand | category")
        if on:
            self.q("INSERT OR IGNORE INTO preferences(user_id, kind, value, created_at) VALUES (?,?,?,?)", (user_id, kind, value, time.time()))
        else:
            self.q("DELETE FROM preferences WHERE user_id=? AND kind=? AND value=?", (user_id, kind, value))

    def interact(self, user_id, kind, product_id=None, query=None):
        p = self.q("SELECT brand, category FROM products WHERE id=?", (product_id,), one=True) if product_id else None
        self.q("INSERT INTO interactions(user_id, kind, product_id, brand, category, query, at) VALUES (?,?,?,?,?,?,?)",
               (user_id, kind, product_id, p and p["brand"], p and p["category"], query, self.L.clock()))

    def watch(self, user_id, product_id, target_price, deadline=None, alternatives=True, constraints=None):
        """Surveiller un produit précis (« je l'achète à 999 € »)."""
        if float(target_price) <= 0:
            raise ValueError("prix cible invalide")
        if not self.q("SELECT 1 FROM products WHERE id=?", (product_id,), one=True):
            raise ValueError("produit inconnu")
        ex = self.q("SELECT id FROM user_watches WHERE user_id=? AND product_id=? AND kind='product'", (user_id, product_id), one=True)
        args = (float(target_price), deadline, int(alternatives), json.dumps(constraints or {}))
        if ex:
            self.q("UPDATE user_watches SET target_price=?, deadline=?, alternatives_allowed=?, constraints=?, status='active' WHERE id=?", (*args, ex["id"]))
            return ex["id"]
        return self.q("INSERT INTO user_watches(user_id, kind, product_id, target_price, deadline, alternatives_allowed, constraints, created_at) "
                      "VALUES (?, 'product', ?,?,?,?,?,?)", (user_id, product_id, *args, time.time()))

    def watch_search(self, user_id, spec, max_price, deadline=None):
        """Surveiller une recherche (« un lave-linge Bosch sous 500 € ») : même entité, autre cible."""
        spec = {k: v for k, v in (spec or {}).items() if k in ("category", "brand", "text") and v}
        if not spec or float(max_price) <= 0:
            raise ValueError("recherche ou budget invalide")
        return self.q("INSERT INTO user_watches(user_id, kind, spec, target_price, deadline, alternatives_allowed, created_at) VALUES (?, 'search', ?,?,?,0,?)",
                      (user_id, json.dumps(spec, ensure_ascii=False), float(max_price), deadline, time.time()))

    def reject_alternative(self, watch_id, product_id):
        w = self.q("SELECT * FROM user_watches WHERE id=?", (watch_id,), one=True)
        rej = sorted(set(json.loads(w["rejected"])) | {product_id})
        self.q("UPDATE user_watches SET rejected=? WHERE id=?", (json.dumps(rej), watch_id))
        self.interact(w["user_id"], "alt_reject", product_id)

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
        """Produits dont un prix a changé (ou est apparu) ce jour-là : les seuls à recalculer, plus les produits suivis."""
        t0 = time.mktime(day.timetuple())
        rows = self.q("SELECT DISTINCT o.product_id FROM observations ob JOIN offers o ON o.id=ob.offer_id WHERE ob.first_seen>=? AND o.product_id IS NOT NULL", (t0,))
        watched = self.q("SELECT DISTINCT product_id FROM user_watches WHERE status='active'")
        return sorted({r["product_id"] for r in rows} | {r["product_id"] for r in watched})

    # ============================================================ SIMILARITÉ (alternatives) — hebdomadaire
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

    @staticmethod
    def satisfies(constraints, base, cand):
        """Contraintes dures de l'utilisateur : uniquement la marque, minimums / maximums de caractéristiques."""
        if constraints.get("brand_only") and cand["brand"] != base["brand"]:
            return False
        A = cand["attributes"] or {}
        for k, v in (constraints.get("min") or {}).items():
            if k == "energy_class":
                if A.get(k) not in ENERGY or ENERGY.index(A[k]) > ENERGY.index(v):
                    return False
            elif (A.get(k) or 0) < v:
                return False
        for k, v in (constraints.get("max") or {}).items():
            if A.get(k) is None or A[k] > v:
                return False
        return True

    # ============================================================ MOTEUR D'OPPORTUNITÉS PERSONNELLES
    def _user_ctx(self, user_id, now):
        follows = self.q("SELECT kind, value FROM preferences WHERE user_id=?", (user_id,))
        aff_b, aff_c, dismissed = {}, {}, set()
        w = {"view": 0.5, "save": 1.5, "click": 1.0, "search": 0.8, "alt_accept": 1.0, "dismiss": -1.5, "alt_reject": -0.3}
        for it in self.q("SELECT * FROM interactions WHERE user_id=? AND at>=?", (user_id, now - 60 * 86400)):
            decay = 0.5 ** ((now - it["at"]) / (21 * 86400))                   # demi-vie de 3 semaines
            if it["brand"]:
                aff_b[it["brand"]] = aff_b.get(it["brand"], 0) + w.get(it["kind"], 0) * decay
            if it["category"]:
                aff_c[it["category"]] = aff_c.get(it["category"], 0) + w.get(it["kind"], 0) * decay
            if it["kind"] == "dismiss" and it["product_id"]:
                dismissed.add(it["product_id"])
        u = self.q("SELECT * FROM users WHERE id=?", (user_id,), one=True)
        return {"brands": {f["value"] for f in follows if f["kind"] == "brand"}, "cats": {f["value"] for f in follows if f["kind"] == "category"},
                "aff_b": aff_b, "aff_c": aff_c, "dismissed": dismissed, "budget": u["budget_max"],
                "watched": {r["product_id"] for r in self.q("SELECT product_id FROM user_watches WHERE user_id=? AND status='active'", (user_id,))}}

    def score(self, ctx, sig):
        """→ (score, raison, section) ou None. Pertinence + qualité du prix + nouveauté + fraîcheur, tout explicable."""
        if sig["product_id"] in ctx["dismissed"] or sig["product_id"] in ctx["watched"] or sig["inflated"]:
            return None
        quality = {"VERY_GOOD_PRICE": 2.0, "GOOD_PRICE": 1.0}.get(sig["state"], 0) + (0.5 if sig["back_in_stock"] else 0)
        if quality == 0:
            return None                                                        # prix normal : pas une opportunité
        rel, why = 0.0, None
        if sig["brand"] in ctx["brands"]:
            rel += 3; why = why or f"Vous suivez {sig['brand']}"
        if sig["category"] in ctx["cats"]:
            rel += 2.5; why = why or "Catégorie suivie"
        ab, ac = ctx["aff_b"].get(sig["brand"], 0), ctx["aff_c"].get(sig["category"], 0)
        rel += max(-2, min(2, ab)) + max(-2, min(2, ac))
        if not why and ab + ac >= 0.8:
            why = "Proche de ce que vous avez consulté"
        if ctx["budget"] and sig["price"] > ctx["budget"] * 1.2:
            rel -= 1.5
        seen = self.q("SELECT MIN(price) p FROM opportunities WHERE user_id=? AND product_id=? AND day>=?",
                      (ctx["user_id"], sig["product_id"], (self.today() - timedelta(days=COOLDOWN_DAYS)).isoformat()), one=True)["p"]
        novelty = -2.0 if seen is not None and sig["price"] >= seen else 0.5   # déjà montré à ce prix : on n'insiste pas
        fresh = 1.0 if sig["drop"] >= 0.05 else 0
        total = rel + quality + sig["below_ref"] * 4 + novelty + fresh
        if rel > 0.5:
            return total, why or "Pour vous", "foryou"
        if sig["state"] == "VERY_GOOD_PRICE" and sig["below_ref"] >= DISCOVERY_MIN_BELOW and rel > -0.5 and novelty >= 0:
            return total - 1, "Hors de vos habitudes", "discovery"                # « Vous ne cherchiez pas ça »
        return None

    def opportunities_for(self, user_id, signals):
        day, now = self.today().isoformat(), self.L.clock()
        ctx = {**self._user_ctx(user_id, now), "user_id": user_id}
        picked = []
        for sig in signals:
            r = self.score(ctx, sig)
            if r:
                typ = "EXCEPTIONAL_PRICE" if sig["state"] == "VERY_GOOD_PRICE" else "PRICE_DROP" if sig["drop"] >= 0.05 \
                    else "BACK_IN_STOCK" if sig["back_in_stock"] else "NEW_OPPORTUNITY"
                picked.append((r[0], typ, r[1], r[2], sig))
        picked.sort(key=lambda x: -x[0])
        out = []
        for sc, typ, why, section, sig in picked[:MAX_OPP_PER_DAY]:
            self.q("INSERT OR IGNORE INTO opportunities(user_id, product_id, type, score, reason, price, reference_price, day, section, created_at) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?)", (user_id, sig["product_id"], typ, round(sc, 3), why, sig["price"], sig["reference_price"], day, section, now))
            out.append({"product_id": sig["product_id"], "type": typ, "score": round(sc, 2), "reason": why, "section": section})
        return out

    # ============================================================ MOTEUR DE SUIVI (prix cible, alternatives, échéance)
    def evaluate_watches(self, signals_by_pid):
        out = []
        for w in self.q("SELECT * FROM user_watches WHERE status='active'"):
            out += self.evaluate_watch(w, signals_by_pid)
        return out

    def evaluate_watch(self, w, signals_by_pid=None):
        signals_by_pid = signals_by_pid or {}
        sig_of = lambda pid: signals_by_pid.get(pid) or self.market_signal(pid)
        if w["deadline"] and date.fromisoformat(w["deadline"]) < self.today():
            self.q("UPDATE user_watches SET status='expired' WHERE id=?", (w["id"],))
            return []
        if w["kind"] == "search":                                              # recherche : le meilleur produit qui passe sous le budget
            spec = json.loads(w["spec"])
            rows = self.q("SELECT id FROM products WHERE (? IS NULL OR category=?) AND (? IS NULL OR brand=?)",
                          (spec.get("category"), spec.get("category"), spec.get("brand"), spec.get("brand")))
            hits = [x for x in (sig_of(r["id"]) for r in rows) if x and x["price"] <= w["target_price"] and x["state"] != "NORMAL" and not x["inflated"]
                    and (not spec.get("text") or all(t in (x["title"] or "").lower() for t in spec["text"].lower().split()))]
            if hits:
                best = min(hits, key=lambda x: x["price"])
                if self._cooled(w["user_id"], best["product_id"], "TARGET_REACHED", best["price"]):
                    return [self._opp(w, best["product_id"], "TARGET_REACHED", 90, "Votre recherche a trouvé son prix", best)]
            return []
        sig = sig_of(w["product_id"])
        if not sig:
            return []
        if sig["price"] <= w["target_price"]:
            if self._cooled(w["user_id"], w["product_id"], "TARGET_REACHED", sig["price"]):
                return [self._opp(w, w["product_id"], "TARGET_REACHED", 100, "Votre prix est atteint", sig)]
            return []
        if not w["alternatives_allowed"]:
            return []
        base = {"brand": sig["brand"], "attributes": sig["attributes"], "price": sig["price"]}
        cons, rejected = json.loads(w["constraints"]), set(json.loads(w["rejected"]))
        watched = {r["product_id"] for r in self.q("SELECT product_id FROM user_watches WHERE user_id=? AND status='active' AND kind='product'", (w["user_id"],))}
        prof = self.alt_profile(w["user_id"])
        cands = []
        for c in self.q("SELECT other_id, score FROM similarity WHERE product_id=?", (w["product_id"],)):
            if c["other_id"] in rejected or c["other_id"] in watched:       # une alternative gardée devient un suivi à part entière
                continue
            cs = sig_of(c["other_id"])
            if not cs or cs["inflated"] or cs["price"] > w["target_price"] or (cs["state"] == "NORMAL" and cs["price"] > sig["price"] * 0.85):
                continue
            if not self.satisfies(cons, base, cs):
                continue
            cands.append((self.rank_alternative(c["score"], base, cs, prof), c["score"], cs))
        if not cands:
            return []
        rank, sim, cs = max(cands, key=lambda t: t[0])                         # une seule alternative à la fois, la mieux classée
        if not self._cooled(w["user_id"], cs["product_id"], "ALTERNATIVE", cs["price"]):
            return []
        o = self._opp(w, cs["product_id"], "ALTERNATIVE", 50 + rank * 40, f"{round(sim * 100)} % de correspondance", cs)
        return [{**o, "alt_of": w["product_id"]}]

    # profil appris des alternatives acceptées / refusées (vecteur utilisateur V0, sans apprentissage machine)
    def alt_profile(self, user_id):
        rows = self.q("SELECT i.kind, i.product_id, i.brand, o.alt_of_product_id base FROM interactions i "
                      "LEFT JOIN opportunities o ON o.user_id=i.user_id AND o.product_id=i.product_id AND o.type='ALTERNATIVE' "
                      "WHERE i.user_id=? AND i.kind IN ('alt_accept','alt_reject') GROUP BY i.id", (user_id,))
        other_rej = other_acc = savings_acc = 0
        for r in rows:
            base = self.q("SELECT brand FROM products WHERE id=?", (r["base"],), one=True) if r["base"] else None
            other_brand = base and r["brand"] != base["brand"]
            if r["kind"] == "alt_reject" and other_brand:
                other_rej += 1
            if r["kind"] == "alt_accept":
                other_acc += bool(other_brand)
                savings_acc += 1
        return {"brand_loyal": other_rej >= 2 and other_acc == 0, "price_driven": savings_acc >= 2}

    @staticmethod
    def rank_alternative(sim, base, cand, prof):
        r = sim
        if prof["brand_loyal"]:
            r += 0.3 if cand["brand"] == base["brand"] else -0.3              # « il refuse les autres marques »
        if prof["price_driven"]:
            r += 0.3 * max(0, 1 - cand["price"] / base["price"])              # « il accepte quand ça fait économiser »
        return r

    def _cooled(self, user_id, product_id, typ, price):
        last = self.q("SELECT price, day FROM opportunities WHERE user_id=? AND product_id=? AND type=? ORDER BY day DESC LIMIT 1",
                      (user_id, product_id, typ), one=True)
        if not last:
            return True
        watch_alert = typ in ("TARGET_REACHED", "ALTERNATIVE")
        days, drop = (WATCH_COOLDOWN_DAYS, WATCH_REPEAT_DROP) if watch_alert else (COOLDOWN_DAYS, 0.02)
        recent = date.fromisoformat(last["day"]) >= self.today() - timedelta(days=days)
        return not recent or price < last["price"] * (1 - drop)               # renotifier seulement si nettement plus bas

    def _opp(self, w, product_id, typ, score, why, sig):
        self.q("INSERT OR IGNORE INTO opportunities(user_id, product_id, type, score, reason, price, reference_price, day, watch_id, alt_of_product_id, section, created_at) "
               "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (w["user_id"], product_id, typ, score, why, sig["price"], sig["reference_price"], self.today().isoformat(),
                                                     w["id"], w["product_id"] if typ == "ALTERNATIVE" else None, "watch", self.L.clock()))
        return {"user_id": w["user_id"], "product_id": product_id, "type": typ, "watch_id": w["id"], "price": sig["price"]}

    # ============================================================ NOTIFICATIONS : un récapitulatif par jour, plafonné
    def digest(self):
        day, sent = self.today().isoformat(), 0
        for u in self.q("SELECT * FROM users"):
            if self.q("SELECT 1 FROM notifications WHERE user_id=? AND day=?", (u["id"], day), one=True):
                continue                                                       # idempotent : un seul envoi par jour
            opps = self.q("SELECT o.*, p.title, p.brand FROM opportunities o JOIN products p ON p.id=o.product_id "
                          "WHERE o.user_id=? AND o.day=? AND o.notified=0", (u["id"], day))
            # seulement ce qui change une décision : prix atteint, alternative, ou opportunité d'une marque / catégorie suivie
            eligible = [o for o in opps if o["type"] in ("TARGET_REACHED", "ALTERNATIVE") or (o["section"] == "foryou" and o["reason"] in
                        (f"Vous suivez {o['brand']}", "Catégorie suivie") and o["type"] in ("EXCEPTIONAL_PRICE", "PRICE_DROP"))]
            # rareté : un produit déjà notifié il y a moins de 7 jours ne l'est plus, sauf prix encore plus bas ;
            # et pas plus de 2 alertes « opportunité » par semaine
            since = (self.today() - timedelta(days=COOLDOWN_DAYS)).isoformat()
            def fresh(o):
                last = self.q("SELECT MIN(price) p FROM opportunities WHERE user_id=? AND product_id=? AND notified=1 AND day>=? AND day<?",
                              (u["id"], o["product_id"], since, day), one=True)["p"]
                return last is None or o["price"] < last * 0.98
            eligible = [o for o in eligible if fresh(o)]
            week_opps = self.q("SELECT COUNT(*) n FROM opportunities WHERE user_id=? AND notified=1 AND day>=? AND type NOT IN ('TARGET_REACHED','ALTERNATIVE')",
                               (u["id"], since), one=True)["n"]
            room = max(0, MAX_OPPORTUNITY_ALERTS_PER_WEEK - week_opps)
            watch_alerts = [o for o in eligible if o["type"] in ("TARGET_REACHED", "ALTERNATIVE")]
            other = sorted([o for o in eligible if o not in watch_alerts], key=lambda o: -o["score"])[:room]
            eligible = watch_alerts + other
            eligible.sort(key=lambda o: (PRIORITY.index(o["type"]), -o["score"]))
            keep = eligible[:u["max_alerts_per_day"]]
            if not keep:
                continue
            top = keep[0]
            title = {"TARGET_REACHED": "Votre prix est atteint", "ALTERNATIVE": "Une alternative intéressante vient d'apparaître"}.get(
                top["type"], "Une offre pourrait vous intéresser")
            body = " · ".join(f"{o['brand']} {o['title']} — {o['price']:.0f} €" for o in keep)
            self.q("INSERT INTO notifications(user_id, day, title, body, opportunity_ids, created_at) VALUES (?,?,?,?,?,?)",
                   (u["id"], day, title, body, json.dumps([o["id"] for o in keep]), time.time()))
            self.q(f"UPDATE opportunities SET notified=1 WHERE id IN ({','.join('?' * len(keep))})", [o["id"] for o in keep])
            sent += 1
        return sent

    # ============================================================ FRÉQUENCE ADAPTATIVE (plafond : 1 fois par jour)
    def refresh_plan(self, day=None):
        """→ (offer_ids à relire aujourd'hui, répartition par rythme). Suivi, opportunité récente ou produit volatil : chaque jour ;
        centre d'intérêt d'un utilisateur : tous les 3 jours ; le reste : chaque semaine. Étalement déterministe par identifiant."""
        day = day or self.today()
        idx = day.toordinal()
        watched = {r["product_id"] for r in self.q("SELECT product_id FROM user_watches WHERE status='active'")}
        recent = {r["product_id"] for r in self.q("SELECT DISTINCT product_id FROM opportunities WHERE day>=?", ((day - timedelta(days=3)).isoformat(),))}
        brands = {r["value"] for r in self.q("SELECT value FROM preferences WHERE kind='brand'")}
        cats = {r["value"] for r in self.q("SELECT value FROM preferences WHERE kind='category'")}
        since = time.mktime((day - timedelta(days=30)).timetuple())
        volatile = {r["pid"] for r in self.q("SELECT o.product_id pid, COUNT(*) n FROM observations ob JOIN offers o ON o.id=ob.offer_id "
                                             "WHERE ob.first_seen>=? GROUP BY o.product_id HAVING n>=3", (since,))}
        plan, tiers = [], {"daily": 0, "every_3_days": 0, "weekly": 0}
        for o in self.q("SELECT o.id, o.product_id, p.brand, p.category FROM offers o LEFT JOIN products p ON p.id=o.product_id WHERE o.status!='gone'"):
            pid = o["product_id"]
            period, tier = (1, "daily") if pid in watched or pid in recent or pid in volatile else \
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
        by_pid = {s["product_id"]: s for s in sigs}
        # état de marché conservé par produit : recalculé seulement quand le prix bouge, mais une bonne affaire
        # en cours depuis plusieurs jours reste candidate (sinon elle disparaît du radar le lendemain)
        for sg in sigs:
            self.q("INSERT OR REPLACE INTO market_signals(product_id, state, data, day) VALUES (?,?,?,?)",
                   (sg["product_id"], sg["state"], json.dumps(sg, default=str), key))
        fresh_since = (day - timedelta(days=7)).isoformat()
        live = {r["product_id"]: json.loads(r["data"]) for r in self.q("SELECT product_id, data FROM market_signals WHERE state!='NORMAL' AND day>=?", (fresh_since,))}
        candidates = list({**live, **by_pid}.values())
        stats["signals"] = {"products": len(pids), "good_or_better": sum(s["state"] != "NORMAL" for s in sigs), "inflated": sum(s["inflated"] for s in sigs)}
        stats["watch_events"] = len(self.evaluate_watches(by_pid))
        stats["opportunities"] = sum(len(self.opportunities_for(u["id"], candidates)) for u in self.q("SELECT id FROM users"))
        stats["notifications"] = self.digest()
        self.q("UPDATE jobs SET ended=?, status='done', stats=? WHERE name='daily' AND key=?", (time.time(), json.dumps(stats), key))
        return stats

    # ============================================================ LECTURE POUR L'APP (Pour vous / Surveiller)
    def feed(self, user_id):
        """Deux cas distincts : l'opportunité ATTENDUE (watch hit : prix atteint, alternative) et l'opportunité INCONNUE
        (découverte : pertinente pour vous, ou hors de vos habitudes)."""
        since = (self.today() - timedelta(days=2)).isoformat()
        rows = self.q("SELECT o.*, p.title, p.brand, p.category FROM opportunities o JOIN products p ON p.id=o.product_id "
                      "WHERE o.user_id=? AND o.day>=? ORDER BY o.score DESC", (user_id, since))
        dismissed = {r["product_id"] for r in self.q("SELECT product_id FROM interactions WHERE user_id=? AND kind='dismiss'", (user_id,))}
        seen, hits, foryou, discovery = set(), [], [], []
        for r in rows:
            if r["product_id"] in seen or r["product_id"] in dismissed:
                continue
            seen.add(r["product_id"])
            (hits if r["section"] == "watch" else foryou if r["section"] == "foryou" else discovery).append(r)
        watches = []
        for w in self.q("SELECT w.*, p.title, p.brand FROM user_watches w LEFT JOIN products p ON p.id=w.product_id WHERE w.user_id=? AND w.status='active' ORDER BY w.id DESC", (user_id,)):
            last = self.q("SELECT type, price, product_id FROM opportunities WHERE watch_id=? AND day>=? ORDER BY score DESC LIMIT 1", (w["id"], since), one=True)
            sig = self.market_signal(w["product_id"]) if w["product_id"] else None
            watches.append({**w, "spec": json.loads(w["spec"]), "current_price": sig and sig["price"], "state": last["type"] if last else "WAITING", "event": last})
        return {"watch_hits": hits, "foryou": foryou[:5], "discovery": discovery[:3], "watches": watches}
