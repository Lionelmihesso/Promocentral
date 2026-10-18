"""Collecte : tout le parcours sur de faux sites locaux (robots.txt, plans de site compressés, pages JSON-LD /
microdonnées, page bloquée par un anti-robot, accessoire écarté du catalogue, ETag/304, mention « plus bas 30 jours »)."""
import gzip
import hashlib
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from collect.pipeline import Collector
from listener.core import Listener
from listener.fetch import Fetcher

def ean(body12):
    """EAN-13 valide (clé de contrôle calculée)."""
    total = sum(int(x) * (3 if i % 2 else 1) for i, x in enumerate(body12))
    return body12 + str((10 - total % 10) % 10)


PRICES = {}   # (site, sku) -> prix courant ; modifiable entre deux « nuits »
CATALOG = {   # site -> [(sku, catégorie dans l'adresse, titre, marque, ean)]
    "a": [("1001", "lave-linge", "Lave-linge hublot Bosch Série 6 9 kg", "Bosch", ean("424200500002")),
          ("1002", "canape", "Canapé d'angle convertible Oslo", "Oslo", ean("366300000001")),
          ("1003", "matelas", "Matelas mousse 140x190 Bultex Integral 3", "Bultex", ean("366728702075")),
          ("1004", "matelas", "Protège-matelas 140x190 imperméable", "Dodo", ean("333333000004"))],
    "b": [("2001", "lave-linge", "Lave-linge Bosch Série 6 9kg hublot", "Bosch", ean("424200500002")),
          ("2002", "lit-coffre", "Lit coffre 160x200 Nils", "Nils", ean("366300000002")),
          ("2003", "refrigerateur", "Réfrigérateur combiné Samsung RB38", "Samsung", ean("880609500006"))],
    "c": [("3001", "lave-vaisselle", "Lave-vaisselle Bosch 60 cm", "Bosch", ean("424200500007")),
          ("3002", "canape", "Canapé 3 places velours Ines", "Ines", ean("366300000003"))],
}
for site, items in CATALOG.items():
    for sku, *_ in items:
        PRICES[(site, sku)] = {"1001": 649, "1002": 1299, "1003": 529, "1004": 29, "2001": 629, "2002": 459, "2003": 699,
                               "3001": 549, "3002": 899}[sku]


def make_handler(site):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
            self.send_response(code); self.send_header("Content-Type", ctype)
            for k, v in (extra or {}).items(): self.send_header(k, v)
            self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            base = f"http://127.0.0.1:{self.server.server_port}"
            if self.path == "/robots.txt":
                return self.send(200, f"User-agent: *\nDisallow: /panier\nSitemap: {base}/sitemap_index.xml\n".encode(), "text/plain")
            if self.path == "/sitemap_index.xml":
                return self.send(200, f'<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>{base}/sitemap-categories.xml</loc></sitemap>'
                                 f'<sitemap><loc>{base}/sitemap-products-1.xml.gz</loc></sitemap></sitemapindex>'.encode(), "application/xml")
            if self.path == "/sitemap-categories.xml":
                return self.send(200, f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{base}/c/canape</loc></url></urlset>'.encode(), "application/xml")
            if self.path == "/sitemap-products-1.xml.gz":
                locs = "".join(f"<url><loc>{base}/p/{cat}-{sku}.html</loc></url>" for sku, cat, *_ in CATALOG[site]) + f"<url><loc>{base}/panier/1.html</loc></url>"
                return self.send(200, gzip.compress(f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>'.encode()), "application/gzip")
            if self.path.startswith("/p/"):
                sku = self.path.rsplit("-", 1)[1].split(".")[0]
                item = next(i for i in CATALOG[site] if i[0] == sku)
                if site == "c":
                    return self.send(403, b"<html><body>Please complete the captcha (DataDome)</body></html>")
                price = PRICES[(site, sku)]
                omni = '<p class="legal">Prix le plus bas pratiqué au cours des 30 derniers jours : 1 199,00 €</p>' if price < {"1002": 1299}.get(sku, 0) else ""
                if site == "a":
                    body = (f'<html><head><title>{item[2]}</title><script type="application/ld+json">{json.dumps({"@context": "https://schema.org", "@type": "Product", "name": item[2], "brand": {"@type": "Brand", "name": item[3]}, "gtin13": item[4], "offers": {"@type": "Offer", "price": str(price), "priceCurrency": "EUR", "availability": "https://schema.org/InStock"}})}</script>'
                            f'</head><body><h1>{item[2]}</h1>{omni}</body></html>')
                else:   # site b : microdonnées / balises meta, pas de JSON-LD
                    body = (f'<html><head><title>{item[2]}</title><meta property="og:title" content="{item[2]}"><meta property="product:price:amount" content="{price}">'
                            f'<meta property="product:price:currency" content="EUR"><meta property="product:brand" content="{item[3]}"></head>'
                            f'<body itemscope itemtype="https://schema.org/Product"><span itemprop="gtin13">{item[4]}</span><h1>{item[2]}</h1></body></html>')
                etag = '"' + hashlib.md5(body.encode()).hexdigest() + '"'
                if self.headers.get("If-None-Match") == etag:
                    self.send_response(304); self.end_headers(); return
                return self.send(200, body.encode(), extra={"ETag": etag})
            self.send(404, b"not found")
    return H


class CollectFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.servers = {}
        for site in CATALOG:
            srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(site))
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            cls.servers[site] = srv
        port = lambda s: cls.servers[s].server_port
        cls.R = {s: {"name": f"Site {s.upper()}", "home": f"http://127.0.0.1:{port(s)}", "enabled": True, "product_url": r"/p/[a-z-]+-\d+\.html", "sitemaps": []} for s in CATALOG}
        cls.tmp = tempfile.mkdtemp()
        cls.L = Listener(fetcher=Fetcher(user_agent="DealsTest/1.0", min_interval=0, timeout=5), workers=1)
        cls.C = Collector(cls.L, cls.R, report_dir=cls.tmp)

    @classmethod
    def tearDownClass(cls):
        for s in cls.servers.values():
            s.shutdown(); s.server_close()

    def test_1_discover(self):
        r = self.C.discover("a", per_category=10)
        self.assertEqual(r["total"], 4)                                   # 4 fiches ; page catégorie et panier interdit écartés
        self.assertEqual(set(r["by_category"]), {"lave_linge", "canape", "matelas"})
        self.assertFalse(any("/panier" in u for v in r["by_category"].values() for u in v))

    def test_2_diagnose_verdicts(self):
        verdict = {}
        for s in CATALOG:
            urls = [u for v in self.C.discover(s, 10)["by_category"].values() for u in v]
            verdict[s] = self.C.diagnose(s, urls)["summary"]
        self.assertEqual(verdict["a"]["verdict"], "garder")
        self.assertEqual((verdict["a"]["with_price"], verdict["a"]["with_gtin"]), (1.0, 1.0))
        self.assertEqual(verdict["b"]["verdict"], "garder")                # sans JSON-LD : microdonnées et balises meta suffisent
        self.assertEqual(verdict["c"]["verdict"], "abandonner (bloqué)")    # anti-robot : on n'insiste pas
        self.assertEqual(verdict["c"]["protections"], {"datadome": 2})      # et on sait lequel
        self.__class__.found = {s: self.C.discover(s, 10)["by_category"] for s in ("a", "b")}

    def test_3_build_and_match(self):
        for s in ("a", "b"):
            self.C.build(s, self.found[s])
        wm = self.L.q("SELECT p.id, COUNT(o.id) n FROM products p JOIN offers o ON o.product_id=p.id WHERE p.gtin=? GROUP BY p.id",
                      (CATALOG["a"][0][4],))
        self.assertEqual([r["n"] for r in wm], [2])                          # même EAN chez deux enseignes → un seul produit
        self.assertEqual(self.L.q("SELECT COUNT(*) n FROM products", one=True)["n"], 5)   # 7 fiches → 6 au catalogue → 5 produits
        acc = self.L.q("SELECT status FROM offers WHERE url LIKE '%1004.html'", one=True)
        self.assertEqual(acc["status"], "out_of_scope")                      # le protège-matelas (29 €) n'entre pas au catalogue
        self.assertIsNone(self.L.q("SELECT id FROM products WHERE title LIKE 'Protège%'", one=True))
        cats = {r["gtin"]: r["category"] for r in self.L.q("SELECT gtin, category FROM products")}
        self.assertEqual(cats[CATALOG["b"][2][4]], "refrigerateur")
        self.assertEqual(cats[CATALOG["b"][1][4]], "lit")

    def test_4_two_nights(self):
        s1 = self.C.nightly()
        self.assertEqual(s1["retailers"]["a"]["unchanged_304"], 3)          # rien n'a bougé : aucune page retéléchargée
        self.assertEqual(s1["price_drops"], [])
        n_obs = self.L.q("SELECT COUNT(*) n FROM observations", one=True)["n"]
        PRICES[("a", "1002")] = 999                                          # nuit suivante : une promo sur le canapé chez A
        s2 = self.C.nightly()
        self.C.nightly()                                                     # confirmation éventuelle d'une forte variation
        drop = next(d for d in self.C._stats(s2["day"], [{"retailer": "a", "offer_id": o["id"], "outcome": "changed", "status": "ok"}
                    for o in self.L.q("SELECT id FROM offers WHERE url LIKE '%1002.html'")], 0)["price_drops"])
        self.assertEqual((drop["before"], drop["after"]), (1299, 999))
        self.assertLessEqual(self.L.q("SELECT COUNT(*) n FROM observations", one=True)["n"], n_obs + 2)   # on n'enregistre que le changement
        self.assertEqual(self.L.q("SELECT price FROM omnibus", one=True)["price"], 1199.0)   # « plus bas 30 jours » relevé sur la page
        report = Path(self.tmp, f"{s2['report']}.md").read_text(encoding="utf-8")
        self.assertIn("Site A", report)
        self.assertIn("1 299,00 € → 999,00 €", report)                     # la baisse figure dans le rapport de sa nuit
        self.assertNotEqual(s1["report"], s2["report"])                      # deux passes le même jour : deux rapports
        best = self.L.snapshot(self.L.q("SELECT id FROM products WHERE gtin=?", (CATALOG["a"][1][4],), one=True)["id"])
        self.assertEqual(best["intel"]["current"], 999)                     # meilleur prix du produit, toutes enseignes

    def test_5_estimate(self):
        e = self.C.estimate(5.0)
        self.assertEqual(e["sites"], 2)
        self.assertLessEqual(e["minutes"], 1)


if __name__ == "__main__":
    unittest.main()
