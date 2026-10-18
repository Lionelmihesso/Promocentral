"""Extraction « béton » : corpus publics (prix réels, JSON-LD mal formés, spécification robots.txt), pages-pièges
construites sur des motifs réels, signatures de blocage, encodages, Crawl-delay, et comportement de la passe de nuit
(fiche devenue page liste, autre produit à la même adresse, accessoire hors catalogue, site qui refuse)."""
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from collect.pipeline import Collector
from listener import extract as X
from listener.core import Listener
from listener.fetch import Fetcher, classify, decode
from listener.structured import jsonld_items
from listener.vendor.protego import Protego
from tests.pages import HELDOUT, PAGES

CORPUS = Path(__file__).parent / "corpus"


def outcome(p):
    st, vendor = classify(p.get("status", 200), p.get("headers") or {}, p["html"])
    if st == "blocked":
        return {"status": "blocked", "vendor": vendor}
    a = X.analyze(p["html"], p.get("rules"), url=p.get("url"))
    if a["page_kind"] == "listing":
        return {"status": "not_product"}
    if a["page_kind"] == "not_found":
        return {"status": "gone"}
    ex = a["best"]
    if not ex:
        return {"status": "no_price"}
    return {"status": "ok", "price": ex["price"], "was": ex.get("list_price"), "availability": ex.get("availability"),
            "kind": ex.get("kind"), "valid_until": ex.get("valid_until"), "lowest_30d": ex.get("lowest_30d")}


class Corpus(unittest.TestCase):
    def test_price_strings(self):
        ex = json.loads((CORPUS / "price_strings.json").read_text(encoding="utf-8"))["examples"]
        ok = 0
        for e in ex:
            got, want = X.parse_price(e["price_raw"]), e["amount"]
            ok += (got in (None, 0)) if want == 0 else (got is None if want is None else got is not None and abs(got - want) < 1e-6 * max(1, want))
        self.assertGreaterEqual(ok / len(ex), 0.996)                       # mesuré : 1036/1040 (les 4 écarts : '.75 €', 'PTE 120 000 000'…)
        self.assertIsNone(X.parse_price("40% OFF"))
        self.assertIsNone(X.parse_price("-40 %"))
        self.assertEqual(X.parse_price("279€98"), 279.98)

    def test_jsonld_malformed(self):
        cases = json.loads((CORPUS / "jsonld_cases.json").read_text(encoding="utf-8"))["cases"]
        bad = [c["name"] for c in cases if jsonld_items(c["html"]) != c["expected"]]
        self.assertEqual(bad, [])                                          # 36/36 (l'ancien lecteur : 5/36)

    def test_robots_spec(self):
        spec = json.loads((CORPUS / "robots_spec.json").read_text(encoding="utf-8"))["cases"]
        prec = ("user-agent: hedwig-news\ndisallow: /\nallow: /group1\nuser-agent: *\ndisallow: /\nallow: /group2\n"
                "user-agent: hedwig\ndisallow: /\nallow: /group3\n")
        for path, ua in spec["test_user_agent_precedence"]:
            rp = Protego.parse(prec)
            self.assertEqual(next((p for p in ("/group1", "/group2", "/group3") if rp.can_fetch(p, ua)), None), path)
        for robots_ua, crawler_ua, applies in spec["test_user_agent_boundary_matching"]:
            rp = Protego.parse(f"User-Agent: {robots_ua}\nDisallow: /private\n")
            self.assertEqual(not rp.can_fetch("http://example.com/private", crawler_ua), applies)
        for pattern, path, match in spec["test_path_matching"]:
            self.assertEqual(not Protego.parse(f"User-Agent: *\ndisallow: {pattern}\n").can_fetch(path, "*"), match, (pattern, path))
        for rules, url, allowed in spec["test_record_precedence"]:
            rp = Protego.parse("User-Agent: *\n" + "\n".join(r.strip() for r in rules.split("\n")))
            self.assertEqual(rp.can_fetch(url, "*"), allowed)


class TrapPages(unittest.TestCase):
    def check(self, pages):
        for name, p in pages.items():
            with self.subTest(page=name):
                got = outcome(p)
                for k, v in p["expect"].items():
                    self.assertEqual(got.get(k), v, f"{name} : {k}")
                if p.get("vendor"):
                    self.assertEqual(got.get("vendor"), p["vendor"])
                if p.get("kind"):
                    self.assertEqual(got.get("kind"), p["kind"])

    def test_tuned_pages(self):
        self.check(PAGES)                                                  # avant : 9/25 ; après : 25/25

    def test_heldout_pages(self):
        self.check(HELDOUT)                                                # écrites après réglage : avant 3/8, après 8/8

    def test_member_price_kept_aside(self):
        ex = X.extract(PAGES["membre_et_barre"]["html"])
        self.assertEqual((ex["price"], ex["list_price"], ex["member_price"]), (899.0, 1099.0, 849.0))

    def test_provenance_of_struck_price(self):
        self.assertEqual(X.extract(PAGES["jsonld_barre_google"]["html"])["was_method"], "jsonld")
        self.assertEqual(X.extract(PAGES["barre_en_html_seulement"]["html"])["was_method"], "html (classe)")
        self.assertEqual(X.extract(PAGES["barre_mention_reference"]["html"])["was_method"], "html (mention)")

    def test_marketplace_seller(self):
        html = PAGES["offre_reconditionnee_moins_chere"]["html"]
        self.assertFalse(X.extract(html, merchant="Enseigne")["marketplace"])
        self.assertEqual(X.extract(html, merchant="Autre enseigne")["seller"], "Enseigne")


class Fetching(unittest.TestCase):
    def test_signatures(self):
        product = "<script type='application/ld+json'>{\"@type\":\"Product\"}</script>"
        self.assertEqual(classify(200, {}, product + "<script src='https://js.datadome.co/tags.js'></script>"), (None, "datadome"))
        self.assertEqual(classify(200, {}, product + "<script src='/cdn-cgi/challenge-platform/scripts/jsd/main.js'></script>"),
                         (None, "cloudflare"))                             # script présent sur toutes les pages : information
        self.assertEqual(classify(503, {"Server": "cloudflare"}, "<title>Just a moment...</title>"), ("blocked", "cloudflare"))
        self.assertEqual(classify(200, {}, "<html><body>Access Denied ... Reference&#32;#18.2f3e1b17.1697040000.5a1</body></html>"),
                         ("blocked", "akamai"))
        self.assertEqual(classify(200, {}, "<iframe src='/_Incapsula_Resource?x=1'></iframe>"), ("blocked", "imperva"))
        self.assertEqual(classify(200, {}, "<html>Vérifiez que vous êtes humain</html>"), ("blocked", "captcha"))
        self.assertEqual(classify(429, {}, ""), ("rate_limited", None))

    def test_decode(self):
        self.assertEqual(decode("prix : 12 €".encode("cp1252"), "text/html; charset=ISO-8859-1"), "prix : 12 €")  # latin-1 = windows-1252
        self.assertEqual(decode(b"<meta charset='iso-8859-1'>caf\xe9"), "<meta charset='iso-8859-1'>café")
        self.assertEqual(decode(b"\xef\xbb\xbfcaf\xc3\xa9"), "café")
        self.assertEqual(decode(b"caf\xe9 sans d\xe9claration"), "café sans déclaration")       # UTF-8 impossible → windows-1252
        self.assertEqual(decode("café".encode(), "text/html; charset=inconnu"), "café")

    def test_robots_wildcards_and_crawl_delay(self):
        robots = "User-agent: *\nDisallow: /*?sort=\nDisallow: /*.pdf$\nCrawl-delay: 1.5\nUser-agent: AutreBot\nDisallow: /\n"

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def do_GET(self):
                body = robots.encode() if self.path == "/robots.txt" else b"<html></html>"
                self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers(); self.wfile.write(body)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            base = f"http://127.0.0.1:{srv.server_address[1]}"
            f = Fetcher(user_agent="DealsBot/0.1 (+https://deals.example/robot)", min_interval=0, timeout=5)
            self.assertFalse(f.allowed(base + "/canapes?sort=prix"))        # joker : lu correctement quelle que soit la version de Python
            self.assertFalse(f.allowed(base + "/notice.pdf"))
            self.assertTrue(f.allowed(base + "/notice.pdf?v=2"))            # « $ » : fin d'adresse
            self.assertTrue(f.allowed(base + "/p/canape-oslo"))
            self.assertEqual(f.delay_for(base), 1.5)                        # le site demande 1,5 s : on attend 1,5 s
        finally:
            srv.shutdown(); srv.server_close()


# --------------------------------------------------------------------- passe de nuit sur un faux site
PAGESITE = {}


def product_page(name, gtin, price):
    return ("<html><head><title>" + name + "</title><script type='application/ld+json'>" +
            json.dumps({"@type": "Product", "name": name, "gtin13": gtin, "offers": {"@type": "Offer", "price": price, "priceCurrency": "EUR",
                                                                                   "availability": "https://schema.org/InStock"}}) +
            "</script></head><body><h1>" + name + "</h1></body></html>")


class _Site(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        if self.path == "/robots.txt":
            body, code = b"User-agent: *\nAllow: /\n", 200
        elif self.path.startswith("/refus/"):
            body, code = b"<html><body>Please complete the captcha (DataDome)</body></html>", 403
        else:
            html = PAGESITE.get(self.path)
            body, code = (html.encode(), 200) if html else (b"not found", 404)
        self.send_response(code); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(body)


class NightCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), _Site)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        cls.L = Listener(fetcher=Fetcher(user_agent="DealsTest/1.0", min_interval=0, timeout=5), workers=1)
        cls.R = {"s": {"name": "Site S", "home": cls.base, "enabled": True, "product_url": ".", "sitemaps": []},
                 "r": {"name": "Site R", "home": cls.base, "enabled": True, "product_url": ".", "sitemaps": []}}
        cls.C = Collector(cls.L, cls.R, report_dir=tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close()

    def track(self, path, retailer="s"):
        oid = self.L.track(self.base + path, 2, self.R[retailer]["name"])
        self.L.q("INSERT OR IGNORE INTO collect_offers(offer_id, retailer, category_hint, added_at) VALUES (?,?,?,0)", (oid, retailer, None))
        return oid

    def test_listing_redirect_and_other_product(self):
        from tests.pages import LISTING, ld, page
        PAGESITE["/p/canape-1"] = product_page("Canapé d'angle convertible Oslo", "3663000000017", 1299)
        PAGESITE["/p/lave-linge-2"] = product_page("Lave-linge hublot Bosch Série 6 9 kg", "4242005000029", 649)
        a, b = self.track("/p/canape-1"), self.track("/p/lave-linge-2")
        self.assertEqual((self.L.check(a)["status"], self.L.check(b)["status"]), ("ok", "ok"))
        n = self.L.q("SELECT COUNT(*) n FROM observations", one=True)["n"]
        PAGESITE["/p/canape-1"] = page(ld(LISTING), "<h1>Canapés</h1>")     # la fiche renvoie maintenant vers une liste
        PAGESITE["/p/lave-linge-2"] = product_page("Lave-linge hublot Bosch Série 8 10 kg", "4242005000036", 899)  # autre produit
        ra, rb = self.L.check(a), self.L.check(b)
        self.assertEqual((ra["status"], ra["note"]), ("gone", "page liste"))
        self.assertEqual((rb["status"], rb["note"]), ("gone", "l'adresse montre un autre produit"))
        self.assertEqual(self.L.q("SELECT COUNT(*) n FROM observations", one=True)["n"], n)   # rien d'enregistré
        self.assertEqual({r["status"] for r in self.L.q("SELECT status FROM offers WHERE id IN (?,?)", (a, b))}, {"gone"})

    def test_accessory_never_enters(self):
        PAGESITE["/p/housse-3"] = product_page("Housse de canapé extensible", None, 39)
        PAGESITE["/p/hotte-4"] = product_page("Hotte décorative 90 cm", None, 59)
        h, k = self.track("/p/housse-3"), self.track("/p/hotte-4")
        self.assertEqual(self.L.check(h)["status"], "out_of_scope")          # accessoire
        self.assertEqual(self.L.check(k)["status"], "out_of_scope")          # 59 € : sous le seuil de la famille
        self.assertIsNone(self.L.q("SELECT product_id FROM offers WHERE id=?", (h,), one=True)["product_id"])

    def test_breaker_stops_a_refusing_site(self):
        for i in range(8):
            self.track(f"/refus/{i}", retailer="r")
        stats = self.C.nightly(retailers=["r"])
        self.assertEqual(stats["retailers"]["r"]["blocked"], 5)              # 5 refus de suite…
        self.assertEqual(stats["retailers"]["r"]["interrupted"], 3)          # … puis on arrête ce site pour la nuit


class StruckPriceDrift(unittest.TestCase):
    """Un site change sa page et le prix barré n'est plus lu : le rapport du matin le signale."""

    def test_alert_when_struck_price_disappears(self):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), _Site)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        now = [1_790_000_000.0]
        L = Listener(fetcher=Fetcher(user_agent="DealsTest/1.0", min_interval=0, timeout=5), clock=lambda: now[0], workers=1)
        tmp = tempfile.mkdtemp()
        C = Collector(L, {"d": {"name": "Site D", "home": base, "enabled": True, "product_url": ".", "sitemaps": []}}, report_dir=tmp)
        try:
            def publish(with_strike):
                for i in range(12):
                    offers = {"@type": "Offer", "price": 500 + i, "priceCurrency": "EUR", "availability": "https://schema.org/InStock"}
                    if with_strike:
                        offers["priceSpecification"] = {"@type": "UnitPriceSpecification", "price": 800 + i,
                                                        "priceType": "https://schema.org/StrikethroughPrice"}
                    PAGESITE[f"/d/canape-{i}"] = ("<html><head><title>Canapé modèle " + str(i) + "</title><script type='application/ld+json'>" +
                                                  json.dumps({"@type": "Product", "name": f"Canapé 3 places modèle {i}", "offers": offers}) +
                                                  "</script></head><body></body></html>")
            publish(True)
            for i in range(12):
                oid = L.track(f"{base}/d/canape-{i}", 2, "Site D")
                L.q("INSERT OR IGNORE INTO collect_offers(offer_id, retailer, category_hint, added_at) VALUES (?,?,?,0)", (oid, "d", None))
            s1 = C.nightly()
            self.assertEqual(s1["retailers"]["d"]["was_rate"], 1.0)
            publish(False)                                                  # la nuit suivante, la page a changé
            now[0] += 86400
            s2 = C.nightly()
            self.assertTrue(s2["retailers"]["d"]["was_drop"])
            self.assertIn("le prix barré n'est presque plus lu", Path(tmp, f"{s2['report']}.md").read_text(encoding="utf-8"))
        finally:
            srv.shutdown(); srv.server_close()


if __name__ == "__main__":
    unittest.main()
