"""Lecture d'une fiche et passe de nuit : fetch → extract → décision → market, une transaction courte par page.

Décision pour une page lue :
  page liste, page introuvable, autre produit à la même adresse → offre « gone », rien n'est enregistré
  première lecture hors catalogue (accessoire, autre famille, sous le seuil) → « out_of_scope », jamais enregistrée
  aucun prix fiable → « no_price » : l'offre reste suivie ;  sinon → prix enregistré (au changement seulement)
Passe de nuit : un fil par site, à son rythme poli ; par site, ordre de valeur (prix en quarantaine à revérifier, deal en
cours, favori, clic récent, puis le plus ancien relu) ; 5 refus de suite → arrêt du site pour la nuit ; budget de nuit
atteint → arrêt, ce qui n'est pas relu garde son prix, qui vieillit (au-delà de 3 jours il n'est plus montré).
Chaque passe laisse une ligne dans runs : identifiant de corrélation de la nuit, état (succeeded, partial_success : au
moins une enseigne sous le seuil ou interrompue, retry : relance d'une enseigne par l'agent), bilan.
"""
import json
import threading
import time
from collections import Counter, defaultdict

from .. import extract as X
from ..labels import CATEGORY_LABEL
from .report import previous_retailers, summarize
from .retailers import BREAKER, FAMILY_OF, MIN_PRICE, MIN_PRICE_CATEGORY, RETAILERS

REFUSALS = ("blocked", "rate_limited", "error")
KEEPS = {"gone", "blocked", "disallowed", "out_of_scope"}


def in_scope(ex):
    """Première lecture d'une fiche : None si elle entre au catalogue, sinon la raison."""
    cat, src = X.categorize(ex.get("title"), ex.get("category"))
    fam = FAMILY_OF.get(cat)
    if fam is None:
        return "accessoire" if src == "accessory" else f"hors des familles suivies ({cat or 'catégorie inconnue'})"
    floor = MIN_PRICE_CATEGORY.get(cat, MIN_PRICE[fam])
    if ex["price"] < floor:
        return f"{ex['price']:.2f} € : sous le seuil de {floor:.0f} € ({CATEGORY_LABEL.get(cat, fam).lower()}), accessoire probable"
    return None


class Crawler:
    def __init__(self, market, fetcher, retailers=None, budget_s=4 * 3600, clock=time.time):
        self.m, self.f, self.R, self.budget, self.clock = market, fetcher, retailers or RETAILERS, budget_s, clock

    # ------------------------------------------------------------ une page
    def read(self, o):
        confirming = o["pending_price"] is not None
        r = self.f.get(o["url"], None if confirming else o["etag"], None if confirming else o["last_modified"])
        st, note, ex, outcome = r["status"], None, None, None
        if st == "ok":
            a = X.analyze(r["html"], self.m.rules_for(o["host"]), url=r.get("final_url") or o["url"], merchant=o["merchant"])
            ex, note = a["best"], "; ".join(a["reasons"]) or None
            if a["page_kind"] in ("listing", "not_found"):
                st, note, ex = "gone", "page liste" if a["page_kind"] == "listing" else "page introuvable", None
            elif ex and self.m.other_product(o, ex):
                st, note, ex = "gone", "l'adresse montre un autre produit", None
            elif ex and not o["product_id"] and (why := in_scope(ex)):
                st, note, ex = "out_of_scope", why, None
            elif not ex:
                st = "no_price"
        with self.m.s.tx():
            if ex:
                outcome = self.m.record(o, ex)
            elif st == "not_modified":
                self.m.touch(o["id"])
                outcome = "unchanged"
            ok = st in ("ok", "not_modified")
            status = "active" if ok else st if st in KEEPS else o["status"]
            self.m.set_result(o["id"], status, ok, note, r.get("protection"), r.get("etag") if ex else None,
                              r.get("last_modified") if ex else None)
        return {"offer_id": o["id"], "retailer": o["retailer"], "status": st, "outcome": outcome, "note": note,
                "method": ex["method"] if ex else None, "was": ex.get("list_price") if ex else None}

    def inspect(self, url):
        """Ce que l'extraction voit sur une page, sans rien enregistrer (diagnostic)."""
        r = self.f.get(url)
        out = {"url": url, "status": r["status"], "code": r.get("code"), "elapsed_ms": r.get("elapsed_ms"),
               "protection": r.get("protection"), "final_url": r.get("final_url")}
        if r["status"] != "ok":
            return out
        host = (r.get("final_url") or url).split("/")[2].lower()
        a = X.analyze(r["html"], self.m.rules_for(host), url=r.get("final_url") or url)
        ex = a["best"]
        if ex:
            ex["category"], _ = X.categorize(ex.get("title"), ex.get("category"))
        out.update(extraction=ex, page_kind=a["page_kind"], reasons=a["reasons"], scope=in_scope(ex) if ex else None,
                   candidates=[{k: c.get(k) for k in ("method", "price", "list_price", "currency", "availability", "gtin")}
                               for c in a["candidates"]])
        if a["page_kind"] in ("listing", "not_found"):
            out["status"] = "gone"
        out["hint"] = None if ex or out["status"] == "gone" else (
            "Aucun prix structuré : ajoutez une règle pour ce site, par exemple "
            "python deals.py rules <site> '{\"price\": \"div.prix\", \"list_price\": \"del\"}'")
        return out

    # ------------------------------------------------------------ catalogue
    def build(self, key, urls_by_category):
        """Première lecture des fiches découvertes : produits rapprochés, hors catalogue écarté."""
        before = self.m.s.q("SELECT COUNT(*) n FROM products", one=True)["n"]
        res = Counter()
        for cat, urls in urls_by_category.items():
            for u in urls:
                res[self.read(self.m.offer(self.m.track(u, key, self.R[key]["name"], cat)))["status"]] += 1
        after = self.m.s.q("SELECT COUNT(*) n FROM products", one=True)["n"]
        return {"retailer": key, "offers": sum(res.values()), "statuses": dict(res), "new_products": after - before,
                "to_review": self.m.s.q("SELECT COUNT(*) n FROM products WHERE needs_review=1", one=True)["n"]}

    def plan(self, keys, day):
        """Offres à relire cette nuit, par ordre de valeur. Les fiches disparues sont revérifiées une nuit sur sept."""
        if not keys:
            return []
        rows = self.m.s.q(
            "SELECT o.*, COALESCE(c.pct, 0) AS deal, EXISTS(SELECT 1 FROM saves s WHERE s.product_id=o.product_id) AS saved, "
            "EXISTS(SELECT 1 FROM clicks k WHERE k.product_id=o.product_id AND k.at>?) AS clicked, "
            "EXISTS(SELECT 1 FROM quarantine q WHERE q.offer_id=o.id AND q.status='held') AS held "
            f"FROM offers o LEFT JOIN catalog c ON c.product_id=o.product_id WHERE o.retailer IN ({','.join('?' * len(keys))}) "
            "AND (o.status IN ('new', 'active', 'blocked', 'disallowed') OR (o.status='gone' AND (o.id + ?) % 7 = 0))",
            (self.clock() - 3 * 86400, *keys, day.toordinal()))
        rows.sort(key=lambda o: (not o["held"], o["deal"] <= 0, not o["saved"], not o["clicked"], o["checked_at"] or 0, o["id"]))
        return rows

    def estimate(self, keys=None):
        keys = keys or [k for k in self.R if self.R[k].get("enabled")]
        per = Counter(o["host"] for o in self.plan(keys, self.m.today()))
        worst = max((n * self.f.delay_for(h) for h, n in per.items()), default=0)
        return {"sites": len(per), "offers": sum(per.values()), "minutes": round(worst / 60, 1)}

    # ------------------------------------------------------------ la nuit
    def nightly(self, retailers=None, cid=None, retry=False):
        """La passe : retailers, les clés à lire (None : toutes les enseignes activées ; [] : aucune) ; cid, l'identifiant de
        corrélation de la nuit ; retry : relance d'une enseigne par l'agent. → bilan (collect/report.py), avec son numéro."""
        day, started = self.m.today(), self.clock()
        keys = [k for k in (self.R if retailers is None else retailers) if self.R[k].get("enabled")]
        run = self.m.s.x("INSERT INTO runs(day, started, cid, status) VALUES (?,?,?,'running')", (day.isoformat(), started, cid))
        by_host = defaultdict(list)
        for o in self.plan(keys, day):
            by_host[o["host"]].append(o)
        deadline = time.monotonic() + self.budget
        results, interrupted, not_read, lock = [], {}, Counter(), threading.Lock()

        def worker(items):
            refusals = 0
            try:
                for k, o in enumerate(items):
                    if time.monotonic() > deadline:
                        with lock:
                            not_read[o["retailer"]] += len(items) - k
                        break
                    try:
                        r = self.read(o)
                    except Exception as e:                  # une page cassée n'arrête pas la passe
                        r = {"offer_id": o["id"], "retailer": o["retailer"], "status": "error", "outcome": None, "note": type(e).__name__}
                    with lock:
                        results.append(r)
                    refusals = refusals + 1 if r["status"] in REFUSALS else 0
                    if refusals >= BREAKER and k + 1 < len(items):
                        with lock:
                            interrupted[o["retailer"]] = len(items) - k - 1
                        break
            finally:
                self.m.s.release()

        threads = [threading.Thread(target=worker, args=(items,)) for items in by_host.values()]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        pending = self.m.s.q(f"SELECT * FROM offers WHERE pending_price IS NOT NULL AND retailer IN ({','.join('?' * len(keys))})",
                             keys) if keys else []
        late = [self.read(o) for o in pending]               # variations énormes : relues une fois avant d'être crues
        stats = summarize(self.m, day, results, {k: self.R[k]["name"] for k in self.R}, interrupted, not_read, len(pending),
                          previous_retailers(self.m.s, day), late)
        status = "retry" if retry else "partial_success" if any(r["alert"] or r["interrupted"] for r in stats["retailers"].values()) \
            else "succeeded"
        self.m.s.x("UPDATE runs SET ended=?, stats=?, status=? WHERE id=?", (self.clock(), json.dumps(stats, ensure_ascii=False), status, run))
        return {**stats, "run": run}
