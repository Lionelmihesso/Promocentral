"""Couche de décision grand public : ce que l'app consomme. Rien de nouveau côté marché, on expose le moteur réel.

Contrat (préfixe /api/r/). Authentification : cookie de session (radar/accounts.py), sans lui → 401.
  POST auth/request {email} · GET auth/verify?token= · GET auth/me · POST auth/logout
  GET  feed                 watch hits (prix atteint, alternative) · pour vous · hors de vos habitudes · vos surveillances
  GET  search?q=&category=&brand=   produits (avec ou sans promo), facettes, recherches récentes
  GET  product/<id>         prix, frise (plus bas / habituel / bon prix / plus haut sur 6 mois), offres, similaires, votre surveillance
  POST watch                {product_id, target_price, deadline?, alternatives?, brand_only?, min?} ou {search:{category,brand,text}, target_price}
  GET  watches              vos surveillances et leur état
  POST target               {watch_id, target_price}  · POST watch/<id>/stop
  POST interactions         {kind, product_id?, query?} (view save click search…)
  POST dismiss              {product_id}
  POST alternative          {watch_id, product_id, accept: bool, watch_it?: bool}
  GET  go/<product_id>      redirection vers la meilleure offre, avec trace du clic (mesure de l'étoile polaire)
  GET  alerts               récapitulatifs reçus
  GET  metrics              (interne) étoile polaire et sous-métriques
"""
import json
from datetime import date, timedelta

from listener import intelligence as I

from . import accounts
from . import search as SE


class Consumer:
    def __init__(self, radar):
        self.R, self.L, self.q = radar, radar.L, radar.q
        self.A = accounts.of(radar)

    def uid(self, q, b=None):
        # identité uniquement par la session : aucun paramètre client ne désigne un utilisateur
        return self.A.user_for(q.get("_session"))

    # ------------------------------------------------------------ recherche
    def _card(self, pid):
        s = self.L._snapshot_cached(pid)
        if not s or s["intel"].get("current") is None:
            return None
        it, p = s["intel"], s["product"]
        best = min((o for o in s["offers"] if o["availability"] in ("in_stock", "unknown")), key=lambda o: o["price"], default=None)
        lst = best and best.get("list_price")
        return {"id": pid, "title": p["title"], "brand": p["brand"], "category": p["category"], "category_label": SE.CATEGORY_LABEL.get(p["category"], p["category"]),
                "price": it["current"], "was": lst if lst and lst > it["current"] else None,
                "discount": round(1 - it["current"] / lst, 3) if lst and lst > it["current"] else None, "merchant": s["merchant"]}

    def search(self, user_id, q="", category=None, brand=None, limit=40):
        q = (q or "").strip()
        rows = self.q("SELECT id, title, brand, category FROM products WHERE title IS NOT NULL")
        toks = SE.tokens(q) if q else []
        hits = [r for r in rows if (not toks or SE.matches({**r, "retailer": ""}, toks)) and (not category or r["category"] == category) and (not brand or r["brand"] == brand)]
        cards = [c for c in (self._card(r["id"]) for r in hits) if c]
        cards.sort(key=lambda c: (-(c["discount"] or 0), c["price"]))
        if q:
            self.R.interact(user_id, "search", query=q)
        recent = []
        for r in self.q("SELECT query FROM interactions WHERE user_id=? AND kind='search' AND query IS NOT NULL ORDER BY id DESC LIMIT 30", (user_id,)):
            if r["query"] not in recent:
                recent.append(r["query"])
        facets = {"categories": sorted({(c["category"], c["category_label"]) for c in cards if c["category"]}), "brands": sorted({c["brand"] for c in cards if c["brand"]})}
        return {"q": q, "count": len(cards), "products": cards[:limit], "facets": facets, "recent": recent[:5]}

    # ------------------------------------------------------------ fiche produit
    def product(self, user_id, pid):
        s = self.L.snapshot(pid)
        if not s:
            raise ValueError("produit inconnu")
        it = s["intel"]
        series = [v for _, v in self.L.best_series(pid, self.R.today(), 180)] if hasattr(self.L, "best_series") else []
        vals = sorted(v for v in series if v)
        rng = None
        if vals and it.get("current") is not None:
            rng = {"low": min(vals + [it["current"]]), "high": max(vals + [it["current"]]), "typical": it.get("reference_price"),
                   "good": round(I.value_at(vals, 25), 2) if len(vals) >= 10 else None, "days": len(vals)}
        sig = self.R.market_signal(pid)
        w = self.q("SELECT * FROM user_watches WHERE user_id=? AND product_id=? AND kind='product' AND status='active'", (user_id, pid), one=True)
        watch = None
        if w:
            ev = self.q("SELECT type, product_id, price, reason FROM opportunities WHERE watch_id=? AND day>=? ORDER BY score DESC LIMIT 1",
                        (w["id"], (self.R.today() - timedelta(days=2)).isoformat()), one=True)
            alt = self._card(ev["product_id"]) if ev and ev["type"] == "ALTERNATIVE" else None
            watch = {"id": w["id"], "target_price": w["target_price"], "deadline": w["deadline"], "alternatives": bool(w["alternatives_allowed"]),
                     "constraints": json.loads(w["constraints"]), "state": ev["type"] if ev else "WAITING", "alternative": alt and {**alt, "reason": ev["reason"]}}
        similar = [c for c in (self._card(r["other_id"]) for r in self.q("SELECT other_id FROM similarity WHERE product_id=? ORDER BY score DESC LIMIT 3", (pid,))) if c]
        self.R.interact(user_id, "view", pid)
        card = self._card(pid) or {}
        return {**card, "state": sig and sig["state"], "range": rng, "offers": [{"merchant": o["merchant"], "price": o["price"], "availability": o["availability"]}
                for o in sorted(s["offers"], key=lambda o: o["price"])], "attributes": s["product"]["attributes"], "watch": watch, "similar": similar}

    # ------------------------------------------------------------ surveiller
    def create_watch(self, user_id, b):
        if b.get("search"):
            wid = self.R.watch_search(user_id, b["search"], b["target_price"], b.get("deadline"))
        else:
            cons = {"brand_only": bool(b.get("brand_only")), "min": b.get("min") or {}}
            wid = self.R.watch(user_id, int(b["product_id"]), b["target_price"], b.get("deadline"), b.get("alternatives", True), cons)
            self.R.interact(user_id, "save", int(b["product_id"]))
        w = self.q("SELECT * FROM user_watches WHERE id=?", (wid,), one=True)
        events = self.R.evaluate_watch(w)                    # réponse immédiate : prix déjà atteint ? alternative déjà là ?
        return {"watch_id": wid, "immediate": events}

    def set_target(self, user_id, b):
        w = self.q("SELECT * FROM user_watches WHERE id=? AND user_id=?", (int(b["watch_id"]), user_id), one=True)
        if not w:
            raise ValueError("surveillance inconnue")
        if float(b["target_price"]) <= 0:
            raise ValueError("prix cible invalide")
        self.q("UPDATE user_watches SET target_price=? WHERE id=?", (float(b["target_price"]), w["id"]))
        return {"watch_id": w["id"], "immediate": self.R.evaluate_watch(self.q("SELECT * FROM user_watches WHERE id=?", (w["id"],), one=True))}

    def stop_watch(self, user_id, wid):
        self.q("UPDATE user_watches SET status='stopped' WHERE id=? AND user_id=?", (wid, user_id))
        return {"ok": True}

    def alternative(self, user_id, b):
        wid, pid = int(b["watch_id"]), int(b["product_id"])
        if b.get("accept"):
            self.R.interact(user_id, "alt_accept", pid)
            if b.get("watch_it"):
                sig = self.R.market_signal(pid)
                self.R.watch(user_id, pid, b.get("target_price") or (sig and sig["price"]) or 1)
        else:
            self.R.reject_alternative(wid, pid)
        return {"ok": True}

    def dismiss(self, user_id, pid):
        self.R.interact(user_id, "dismiss", int(pid))
        return {"ok": True}

    def go(self, user_id, pid, q):
        s = self.L.snapshot(pid)
        best = min((o for o in (s or {}).get("offers", []) if o["availability"] in ("in_stock", "unknown")), key=lambda o: o["price"], default=None)
        if not best:
            raise ValueError("aucune offre disponible")
        self.R.interact(user_id, "click", pid, query=q.get("from"))   # origine : feed, watch_hit, discovery, search, product…
        return {"__redirect__": best["url"]}

    def alerts(self, user_id):
        return [{**r, "opportunity_ids": json.loads(r["opportunity_ids"])} for r in
                self.q("SELECT * FROM notifications WHERE user_id=? ORDER BY day DESC LIMIT 30", (user_id,))]

    # ------------------------------------------------------------ étoile polaire et sous-métriques
    def metrics(self, window_days=3):
        opps = self.q("SELECT id, user_id, product_id, type, section, day FROM opportunities")
        clicks = self.q("SELECT user_id, product_id, at FROM interactions WHERE kind='click'")
        by = {}
        for c in clicks:
            by.setdefault((c["user_id"], c["product_id"]), []).append(date.fromtimestamp(c["at"]))
        def clicked(o):
            d0 = date.fromisoformat(o["day"])
            return any(d0 <= d <= d0 + timedelta(days=window_days) for d in by.get((o["user_id"], o["product_id"]), []))
        useful = [o for o in opps if clicked(o)]
        watches = self.q("SELECT id FROM user_watches")
        hit_w = {r["watch_id"] for r in self.q("SELECT DISTINCT watch_id FROM opportunities WHERE type='TARGET_REACHED' AND watch_id IS NOT NULL")}
        acc = self.q("SELECT COUNT(*) n FROM interactions WHERE kind='alt_accept'", one=True)["n"]
        rej = self.q("SELECT COUNT(*) n FROM interactions WHERE kind='alt_reject'", one=True)["n"]
        notif = self.q("SELECT user_id, day, opportunity_ids FROM notifications")
        conv = sum(1 for n in notif if any(clicked(o) for o in self.q(
            f"SELECT * FROM opportunities WHERE id IN ({','.join('?' * len(json.loads(n['opportunity_ids'])))})", json.loads(n["opportunity_ids"]))))
        delays = []
        for w in self.q("SELECT user_id, product_id, created_at FROM user_watches WHERE kind='product'"):
            ts = [c["at"] for c in clicks if c["user_id"] == w["user_id"] and c["product_id"] == w["product_id"] and c["at"] >= w["created_at"]]
            if ts:
                delays.append((min(ts) - w["created_at"]) / 86400)
        return {"north_star_useful_opportunities": len(useful),
                "useful_by_kind": {"watch_hit": sum(o["section"] == "watch" for o in useful), "discovery": sum(o["section"] != "watch" for o in useful)},
                "watch_hit_rate": round(len(hit_w) / len(watches), 3) if watches else None,
                "click_after_opportunity": round(len(useful) / len(opps), 3) if opps else None,
                "alternative_acceptance": round(acc / (acc + rej), 3) if acc + rej else None,
                "alert_conversion": round(conv / len(notif), 3) if notif else None,
                "intent_to_click_days": round(sorted(delays)[len(delays) // 2], 1) if delays else None,
                "opportunities": len(opps), "alerts": len(notif)}
