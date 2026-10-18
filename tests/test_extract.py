"""Lecture des pages et politesse — fonctions pures, vérifiées sur des corpus publics et des pages-pièges.

Corpus : 1 040 chaînes de prix réelles (price-parser), 36 JSON-LD mal formés tirés de bugs réels (extruct), 66 cas de la
spécification robots.txt (Protego). Pages-pièges : motifs relevés sur de vraies fiches (tests/pages.py), dont 8 écrites
après réglage pour mesurer la généralisation.
"""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from deals import extract as X
from deals.extract.page import jsonld_items
from deals.fetch import Fetcher, classify, decode
from deals.vendor.protego import Protego
from tests.pages import FORMATS, HELDOUT, PAGES, RULE_FORMAT

CORPUS = Path(__file__).parent / "corpus"


def outcome(p):
    """Ce que la collecte ferait d'une page : bloquée, page liste, introuvable, sans prix, ou l'offre lue."""
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
        self.assertGreaterEqual(ok, 1036)                                # 4 écarts connus : '.75 €', 'PTE 120 000 000'…
        for s, v in {"1 299,99 €": 1299.99, "1.299,99": 1299.99, "299€99": 299.99, "-40 %": None, "40% OFF": None, "gratuit": None}.items():
            self.assertEqual(X.parse_price(s), v, s)

    def test_jsonld_malformed(self):
        cases = json.loads((CORPUS / "jsonld_cases.json").read_text(encoding="utf-8"))["cases"]
        self.assertEqual([c["name"] for c in cases if jsonld_items(c["html"]) != c["expected"]], [])

    def test_robots_spec(self):
        spec = json.loads((CORPUS / "robots_spec.json").read_text(encoding="utf-8"))["cases"]
        prec = ("user-agent: hedwig-news\ndisallow: /\nallow: /group1\nuser-agent: *\ndisallow: /\nallow: /group2\n"
                "user-agent: hedwig\ndisallow: /\nallow: /group3\n")
        for path, ua in spec["test_user_agent_precedence"]:
            rp = Protego.parse(prec)
            self.assertEqual(next((p for p in ("/group1", "/group2", "/group3") if rp.can_fetch(p, ua)), None), path)
        for robots_ua, crawler_ua, applies in spec["test_user_agent_boundary_matching"]:
            self.assertEqual(not Protego.parse(f"User-Agent: {robots_ua}\nDisallow: /private\n").can_fetch("http://example.com/private", crawler_ua), applies)
        for pattern, path, match in spec["test_path_matching"]:
            self.assertEqual(not Protego.parse(f"User-Agent: *\ndisallow: {pattern}\n").can_fetch(path, "*"), match, (pattern, path))
        for rules, url, allowed in spec["test_record_precedence"]:
            self.assertEqual(Protego.parse("User-Agent: *\n" + "\n".join(r.strip() for r in rules.split("\n"))).can_fetch(url, "*"), allowed)


class Pages(unittest.TestCase):
    def check(self, pages):
        for name, p in pages.items():
            with self.subTest(page=name):
                got = outcome(p)
                for k, v in p["expect"].items():
                    self.assertEqual(got.get(k), v, f"{name} : {k}")
                for k in ("vendor", "kind"):
                    if p.get(k):
                        self.assertEqual(got.get(k), p[k], f"{name} : {k}")

    def test_trap_pages(self):
        self.check(PAGES)                                                # ancien extracteur : 9/25

    def test_pages_written_after_tuning(self):
        self.check(HELDOUT)                                              # ancien extracteur : 3/8

    def test_basic_formats_and_site_rule(self):
        for name, (html, exp) in FORMATS.items():
            with self.subTest(fmt=name):
                r = X.extract(html)
                if exp is None:
                    self.assertIsNone(r)
                else:
                    self.assertEqual({k: r.get(k) for k in exp}, exp)
        name, rules, exp = RULE_FORMAT
        self.assertEqual({k: X.extract(FORMATS[name][0], rules)[k] for k in exp}, exp)

    def test_provenance_and_member_price(self):
        self.assertEqual(X.extract(PAGES["jsonld_barre_google"]["html"])["was_method"], "jsonld")
        self.assertEqual(X.extract(PAGES["barre_en_html_seulement"]["html"])["was_method"], "html (classe)")
        ex = X.extract(PAGES["membre_et_barre"]["html"])
        self.assertEqual((ex["price"], ex["list_price"], ex["member_price"]), (899.0, 1099.0, 849.0))


class Fetching(unittest.TestCase):
    def test_block_signatures(self):
        product = "<script type='application/ld+json'>{\"@type\":\"Product\"}</script>"
        self.assertEqual(classify(200, {}, product + "<script src='https://js.datadome.co/tags.js'></script>"), (None, "datadome"))
        self.assertEqual(classify(200, {}, product + "<script src='/cdn-cgi/challenge-platform/scripts/jsd/main.js'></script>"), (None, "cloudflare"))
        self.assertEqual(classify(503, {}, "<title>Just a moment...</title>"), ("blocked", "cloudflare"))
        self.assertEqual(classify(200, {}, "Access Denied ... Reference&#32;#18.2f3e1b17.1697040000.5a1"), ("blocked", "akamai"))
        self.assertEqual(classify(200, {}, "<iframe src='/_Incapsula_Resource?x=1'></iframe>"), ("blocked", "imperva"))
        self.assertEqual(classify(200, {}, "<html>Vérifiez que vous êtes humain</html>"), ("blocked", "captcha"))
        self.assertEqual(classify(429, {}, ""), ("rate_limited", None))

    def test_decode(self):
        self.assertEqual(decode("12 €".encode("cp1252"), "text/html; charset=ISO-8859-1"), "12 €")     # latin-1 = windows-1252
        self.assertEqual(decode(b"<meta charset='iso-8859-1'>caf\xe9"), "<meta charset='iso-8859-1'>café")
        self.assertEqual(decode(b"\xef\xbb\xbfcaf\xc3\xa9"), "café")
        self.assertEqual(decode(b"caf\xe9"), "café")
        self.assertEqual(decode("café".encode(), "text/html; charset=inconnu"), "café")

    def test_robots_wildcards_and_crawl_delay(self):
        robots = "User-agent: *\nDisallow: /*?sort=\nDisallow: /*.pdf$\nCrawl-delay: 1.5\n"

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                body = robots.encode() if self.path == "/robots.txt" else b"<html></html>"
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            base = f"http://127.0.0.1:{srv.server_address[1]}"
            f = Fetcher(user_agent="DealsBot/0.1", min_interval=0, timeout=5)
            self.assertFalse(f.allowed(base + "/canapes?sort=prix"))
            self.assertFalse(f.allowed(base + "/notice.pdf"))
            self.assertTrue(f.allowed(base + "/notice.pdf?v=2"))
            self.assertTrue(f.allowed(base + "/p/canape-oslo"))
            self.assertEqual(f.delay_for(base), 1.5)
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
