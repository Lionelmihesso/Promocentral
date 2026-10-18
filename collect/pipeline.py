"""Collecte sans affiliation : on construit la base produits soi-même et on rafraîchit les prix une fois par jour.

  discover  plans de site (robots.txt → index → fichiers) → adresses de pages produit, rangées par catégorie
  diagnose  N pages par enseigne → part de pages lues, avec prix, prix barré, EAN, bloquées (et par quelle protection),
            d'où vient chaque donnée → garder / règle à écrire / abandonner
  sample    N pages brutes par enseigne, enregistrées telles quelles (samples/) pour une mise au point hors ligne
  build     première lecture des pages retenues → produits (rapprochés par EAN puis par titre), offres, historique
  nightly   une passe par nuit sur toutes les offres actives (requête conditionnelle : rien n'est retéléchargé si la page
            n'a pas changé) → seuls les changements de prix sont enregistrés → rapport du matin
Tout réutilise le moteur existant (listener/) : collecte polie, extraction, normalisation, rapprochement, historique.
"""
import gzip
import json
import re
import threading
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

from listener import normalize as N
from listener.extract import lowest_30d

from .retailers import BREAKER, CATEGORY_URL_HINTS, FAMILIES, FAMILY_OF, KEEP_THRESHOLD, MIN_PRICE, RETAILERS

SCHEMA = """
CREATE TABLE IF NOT EXISTS collect_offers (offer_id INTEGER PRIMARY KEY, retailer TEXT NOT NULL, category_hint TEXT, added_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS omnibus (offer_id INTEGER NOT NULL, day TEXT NOT NULL, price REAL NOT NULL, PRIMARY KEY (offer_id, day));
CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY, day TEXT NOT NULL, started REAL NOT NULL, ended REAL, stats TEXT);
"""
PRODUCT_SITEMAP_HINT = re.compile(r"product|produit|pdp|article|fiche|item|offer", re.I)


class Collector:
    def __init__(self, listener, retailers=None, report_dir="reports"):
        self.L, self.q = listener, listener.q
        self.R = retailers or RETAILERS
        self.report_dir = Path(report_dir)
        with listener.lock:
            listener.db.executescript(SCHEMA)
            listener.db.commit()
        listener.extract_hooks.append(self._omnibus_hook)
        listener.accept = self.in_scope

    def in_scope(self, ex):
        """Première lecture d'une fiche : None si elle entre au catalogue, sinon la raison (hors familles, accessoire)."""
        cat, src = N.categorize(ex.get("title"), ex.get("category"))
        fam = FAMILY_OF.get(cat)
        if fam is None:
            return "accessoire" if src == "accessory" else f"hors des familles suivies ({cat or 'catégorie inconnue'})"
        if ex["price"] < MIN_PRICE.get(fam, 0):
            return f"{ex['price']:.2f} € : sous le seuil de {MIN_PRICE[fam]:.0f} € ({fam}), accessoire probable"
        return None

    def _omnibus_hook(self, offer_id, ex, html):
        v = lowest_30d(html)
        if v:
            self.q("INSERT OR REPLACE INTO omnibus(offer_id, day, price) VALUES (?,?,?)", (offer_id, self.L.today().isoformat(), v))

    # ------------------------------------------------------------ découverte par les plans de site
    def _bytes(self, url):
        """Fichier brut (plans de site, éventuellement compressés), avec les mêmes règles de politesse que les pages."""
        f = self.L.fetcher
        if not f.allowed(url):
            return None
        host = f._host(url)
        with f._host_lock(host):
            f._wait_turn(host)
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": f.ua}), timeout=f.timeout) as r:
                    raw = r.read()
            except Exception:
                return None
        return gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw

    def robots_sitemaps(self, key):
        raw = self._bytes(self.R[key]["home"].rstrip("/") + "/robots.txt")
        if not raw:
            return []
        return [l.split(":", 1)[1].strip() for l in raw.decode("utf-8", "replace").splitlines() if l.lower().startswith("sitemap:")]

    @staticmethod
    def parse_sitemap(raw):
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return None, []
        tag = root.tag.split("}")[-1]
        locs = [e.text.strip() for e in root.iter() if e.tag.split("}")[-1] == "loc" and e.text]
        return ("index" if tag == "sitemapindex" else "urlset"), locs

    def discover(self, key, per_category=40, categories=None, max_files=60):
        """→ {catégorie: [adresses]} ; s'arrête dès que chaque catégorie a son quota ou après `max_files` fichiers."""
        cfg = self.R[key]
        fams = cfg.get("families")
        cats = categories or ([c for f in fams for c in FAMILIES.get(f, []) if c in CATEGORY_URL_HINTS] if fams else list(CATEGORY_URL_HINTS))
        pat = re.compile(cfg["product_url"])
        queue = list(dict.fromkeys(self.robots_sitemaps(key) + cfg.get("sitemaps", [])))
        found, seen_files, read = defaultdict(list), set(), 0
        while queue and read < max_files and any(len(found[c]) < per_category for c in cats):
            queue.sort(key=lambda u: 0 if PRODUCT_SITEMAP_HINT.search(u) else 1)   # fichiers « produits » d'abord
            sm = queue.pop(0)
            if sm in seen_files:
                continue
            seen_files.add(sm)
            raw = self._bytes(sm)
            read += 1
            if not raw:
                continue
            kind, locs = self.parse_sitemap(raw)
            if kind == "index":
                queue.extend(l for l in locs if l not in seen_files)
                continue
            for u in locs:
                if not pat.search(u):
                    continue
                low = u.lower()
                for c in cats:
                    if len(found[c]) < per_category and any(h in low for h in CATEGORY_URL_HINTS[c]):
                        found[c].append(u)
                        break
        found = {c: v for c, v in found.items() if v}
        return {"retailer": key, "files_read": read, "by_category": found, "total": sum(len(v) for v in found.values())}

    # ------------------------------------------------------------ diagnostic par lot
    def diagnose(self, key, urls):
        rows = []
        for u in urls:
            d = self.L.diagnose(u)
            ex = d.get("extraction") or {}
            rows.append({"url": u, "status": d["status"], "code": d.get("code"), "page": d.get("page_kind"),
                         "protection": d.get("protection"), "price": ex.get("price"), "was": ex.get("list_price"),
                         "was_method": ex.get("was_method"), "availability": ex.get("availability"), "gtin": ex.get("gtin"),
                         "title": ex.get("title"), "brand": ex.get("brand"), "method": ex.get("method"), "seller": ex.get("seller"),
                         "category": ex.get("category"), "reasons": " ; ".join(d.get("reasons") or []), "ms": d.get("elapsed_ms")})
        n = len(rows) or 1
        c = Counter(r["status"] for r in rows)
        rate = lambda f: round(sum(1 for r in rows if f(r)) / n, 3)
        s = {"retailer": key, "pages": len(rows), "read_ok": rate(lambda r: r["status"] == "ok"), "with_price": rate(lambda r: r["price"]),
             "with_was": rate(lambda r: r["was"]), "with_gtin": rate(lambda r: r["gtin"]), "with_brand": rate(lambda r: r["brand"]),
             "availability_known": rate(lambda r: r["availability"] not in (None, "unknown")),
             "blocked": rate(lambda r: r["status"] == "blocked"), "disallowed": rate(lambda r: r["status"] == "disallowed"),
             "gone": rate(lambda r: r["status"] == "gone"), "methods": dict(Counter(r["method"] for r in rows if r["method"])),
             "was_methods": dict(Counter(r["was_method"] for r in rows if r["was_method"])),
             "protections": dict(Counter(r["protection"] for r in rows if r["protection"])),
             "statuses": dict(c), "median_ms": sorted(r["ms"] or 0 for r in rows)[len(rows) // 2] if rows else None}
        s["verdict"] = ("garder" if s["with_price"] >= KEEP_THRESHOLD else
                        "abandonner (bloqué)" if s["blocked"] + s["disallowed"] >= 0.5 else
                        "règle de site à écrire" if s["read_ok"] >= KEEP_THRESHOLD else "abandonner")
        return {"summary": s, "rows": rows}

    def sample(self, key, urls, out_dir="samples"):
        """Pages brutes (HTML compressé) + index : de quoi régler l'extraction hors ligne, sur de vraies pages."""
        d = Path(out_dir) / key
        d.mkdir(parents=True, exist_ok=True)
        index = []
        for i, u in enumerate(urls):
            r = self.L.fetcher.get(u)
            name = f"{i:03d}.html.gz"
            if r.get("html"):
                (d / name).write_bytes(gzip.compress(r["html"].encode("utf-8")))
            index.append({"file": name if r.get("html") else None, "url": u, "final_url": r.get("final_url"), "status": r["status"],
                          "code": r.get("code"), "protection": r.get("protection")})
        (d / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"retailer": key, "saved": sum(1 for x in index if x["file"]), "pages": len(index), "dir": str(d)}

    # ------------------------------------------------------------ construction du catalogue
    def build(self, key, urls_by_category):
        cfg = self.R[key]
        before = self.q("SELECT COUNT(*) n FROM products", one=True)["n"]
        res = Counter()
        for cat, urls in urls_by_category.items():
            for u in urls:
                oid = self.L.track(u, 2, cfg["name"])
                self.q("INSERT OR IGNORE INTO collect_offers(offer_id, retailer, category_hint, added_at) VALUES (?,?,?,?)", (oid, key, cat, time.time()))
                r = self.L.check(oid)
                res[r["status"]] += 1
        after = self.q("SELECT COUNT(*) n FROM products", one=True)["n"]
        return {"retailer": key, "offers": sum(res.values()), "statuses": dict(res), "new_products": after - before,
                "to_review": self.q("SELECT COUNT(*) n FROM products WHERE needs_review=1", one=True)["n"]}

    # ------------------------------------------------------------ passe de nuit
    def nightly(self, retailers=None, offer_ids=None):
        """Une passe sur toutes les offres actives des enseignes activées. Un fil par site (les sites en parallèle,
        chaque site à son rythme poli). Les changements suspects (forte variation) sont relus une fois en fin de passe."""
        day = self.L.today().isoformat()
        run = self.q("INSERT INTO runs(day, started) VALUES (?,?)", (day, time.time()))
        keys = [k for k in (retailers or self.R) if self.R[k]["enabled"]]
        offers = self.q("SELECT o.id, o.host, c.retailer FROM offers o JOIN collect_offers c ON c.offer_id=o.id "
                        f"WHERE o.status NOT IN ('gone', 'out_of_scope') AND c.retailer IN ({','.join('?' * len(keys))})", keys) if keys else []
        if offer_ids is not None:                          # fréquence adaptative : seulement les offres prévues ce jour-là
            keep = set(offer_ids)
            offers = [o for o in offers if o["id"] in keep]
        by_host, results = defaultdict(list), []
        for o in offers:
            by_host[o["host"]].append(o)
        lock = threading.Lock()

        interrupted = {}

        def worker(items):
            refusals = 0
            for k, o in enumerate(items):
                try:
                    r = self.L.check(o["id"])
                except Exception as e:                    # une page cassée n'arrête pas la passe
                    r = {"status": "error", "outcome": None, "error": type(e).__name__}
                with lock:
                    results.append({**r, "retailer": o["retailer"], "offer_id": o["id"]})
                refusals = refusals + 1 if r["status"] in ("blocked", "rate_limited", "error") else 0
                if refusals >= BREAKER and k + 1 < len(items):   # le site refuse : on n'insiste pas cette nuit
                    with lock:
                        interrupted[o["retailer"]] = len(items) - k - 1
                    break
        threads = [threading.Thread(target=worker, args=(items,)) for items in by_host.values()]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        pending = self.q("SELECT id FROM offers WHERE pending_price IS NOT NULL")
        for p in pending:                                  # confirmation des changements suspects
            self.L.check(p["id"])
        stats = self._stats(day, results, len(pending))
        for k, left in interrupted.items():
            stats["retailers"].setdefault(k, {"name": self.R[k]["name"]})["interrupted"] = left
        self.q("UPDATE runs SET ended=?, stats=? WHERE id=?", (time.time(), json.dumps(stats, ensure_ascii=False), run))
        self._write_report(stats)
        return stats

    def _stats(self, day, results, confirmed):
        per = defaultdict(Counter)
        for r in results:
            per[r["retailer"]][r["status"]] += 1
            if r.get("outcome") == "changed":
                per[r["retailer"]]["changed"] += 1
            if r["status"] == "ok" and r.get("was"):
                per[r["retailer"]]["with_was"] += 1
        prev = self.q("SELECT stats FROM runs WHERE day<? AND stats IS NOT NULL ORDER BY id DESC LIMIT 1", (day,), one=True)
        prev = json.loads(prev["stats"])["retailers"] if prev else {}
        retail = {}
        for k, c in per.items():
            total = sum(v for s, v in c.items() if s not in ("changed", "with_was"))
            good = c["ok"] + c["not_modified"]
            was_rate = round(c["with_was"] / c["ok"], 3) if c["ok"] else None
            before = (prev.get(k) or {}).get("was_rate")
            retail[k] = {"name": self.R[k]["name"], "pages": total, "ok": c["ok"], "unchanged_304": c["not_modified"], "changed": c["changed"],
                         "blocked": c["blocked"], "gone": c["gone"], "no_price": c["no_price"], "errors": c["error"] + c["rate_limited"],
                         "out_of_scope": c["out_of_scope"], "was_rate": was_rate,
                         # le prix barré n'est presque plus lu alors qu'il l'était : la page a sans doute changé
                         "was_drop": bool(before and before >= 0.10 and was_rate is not None and c["ok"] >= 10 and was_rate < before * 0.3),
                         "success": round(good / total, 3) if total else None, "alert": bool(total) and good / total < KEEP_THRESHOLD}
        drops = []
        for r in results:
            if r.get("outcome") != "changed":
                continue
            obs = self.q("SELECT price FROM observations WHERE offer_id=? ORDER BY id DESC LIMIT 2", (r["offer_id"],))
            if len(obs) == 2 and obs[0]["price"] and obs[1]["price"] and obs[0]["price"] < obs[1]["price"]:
                o = self.q("SELECT o.url, p.title, p.brand FROM offers o LEFT JOIN products p ON p.id=o.product_id WHERE o.id=?", (r["offer_id"],), one=True)
                drops.append({"title": o["title"], "brand": o["brand"], "retailer": self.R[r["retailer"]]["name"], "before": obs[1]["price"],
                              "after": obs[0]["price"], "drop": round(1 - obs[0]["price"] / obs[1]["price"], 3), "url": o["url"]})
        drops.sort(key=lambda x: -x["drop"])
        return {"day": day, "offers": len(results), "retailers": retail, "price_drops": drops[:30], "confirmed_suspects": confirmed,
                "products": self.q("SELECT COUNT(*) n FROM products", one=True)["n"],
                "to_review": self.q("SELECT COUNT(*) n FROM products WHERE needs_review=1", one=True)["n"],
                "omnibus_today": self.q("SELECT COUNT(*) n FROM omnibus WHERE day=?", (day,), one=True)["n"]}

    def _write_report(self, s):
        self.report_dir.mkdir(parents=True, exist_ok=True)
        e = lambda v: f"{v:,.2f} €".replace(",", " ").replace(".", ",")
        lines = [f"# Collecte du {s['day']}", "", f"{s['offers']} pages relues · {s['products']} produits · {s['to_review']} à vérifier · "
                 f"{s['omnibus_today']} « plus bas 30 jours » relevés", "", "| Enseigne | Pages | Lues | Inchangées (304) | Prix changés | Bloquées | Disparues | Sans prix | Erreurs | Réussite |",
                 "|---|---|---|---|---|---|---|---|---|---|"]
        for k, r in sorted(s["retailers"].items()):
            lines.append(f"| {'⚠ ' if r['alert'] else ''}{r['name']} | {r['pages']} | {r['ok']} | {r['unchanged_304']} | {r['changed']} | {r['blocked']} | "
                         f"{r['gone']} | {r['no_price']} | {r['errors']} | {r['success'] * 100:.0f} % |")
        if s["price_drops"]:
            lines += ["", "## Plus fortes baisses", ""] + [f"- {d['brand'] or ''} {d['title'] or d['url']} ({d['retailer']}) : {e(d['before'])} → {e(d['after'])} "
                                                          f"(−{d['drop'] * 100:.0f} %)" for d in s["price_drops"][:15]]
        for r in s["retailers"].values():
            if r.get("was_drop"):
                lines.append(f"⚠ {r['name']} : le prix barré n'est presque plus lu ({r['was_rate'] * 100:.0f} % des pages) : "
                             "changement de page probable (python collect.py explain <adresse>).")
            if r.get("interrupted"):
                lines.append(f"⚠ {r['name']} : passe interrompue après {BREAKER} refus de suite ({r['interrupted']} pages non relues).")
        alerts = [r["name"] for r in s["retailers"].values() if r.get("alert")]
        if alerts:
            lines += ["", f"⚠ Sous le seuil de {KEEP_THRESHOLD * 100:.0f} % : {', '.join(alerts)}. Vérifier un blocage ou un changement de page (python collect.py diagnose)."]
        # une relance le même jour n'écrase pas le rapport de la passe précédente
        name, k = s["day"], 2
        while (self.report_dir / f"{name}.md").exists():
            name, k = f"{s['day']}-{k}", k + 1
        s["report"] = name
        (self.report_dir / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (self.report_dir / f"{name}.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------ vérification manuelle des rapprochements douteux
    def review_queue(self, limit=50):
        out = []
        for p in self.q("SELECT id, title, brand, gtin, category FROM products WHERE needs_review=1 LIMIT ?", (limit,)):
            offers = self.q("SELECT url, merchant FROM offers WHERE product_id=?", (p["id"],))
            out.append({**p, "offers": offers})
        return out

    def resolve(self, product_id, ok=True, merge_into=None):
        if merge_into:
            self.q("UPDATE offers SET product_id=? WHERE product_id=?", (merge_into, product_id))
            self.q("DELETE FROM products WHERE id=?", (product_id,))
        else:
            self.q("UPDATE products SET needs_review=0 WHERE id=?", (product_id,))

    def estimate(self, min_interval):
        """Durée estimée de la passe de nuit : le site le plus chargé fixe la durée (les sites tournent en parallèle)."""
        per = self.q("SELECT o.host, COUNT(*) n FROM offers o JOIN collect_offers c ON c.offer_id=o.id WHERE o.status!='gone' GROUP BY o.host")
        worst = max((r["n"] for r in per), default=0)
        return {"sites": len(per), "offers": sum(r["n"] for r in per), "minutes": round(worst * min_interval / 60, 1)}
