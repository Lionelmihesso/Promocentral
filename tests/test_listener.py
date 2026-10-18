"""python -m unittest discover -s tests -v"""
import json
import threading
import time
import unittest
import urllib.request

from listener import extract as X
from listener.core import Listener, parse_feed
from listener.fetch import Fetcher
from listener.server import serve
from tests.fakeweb import FIXTURES, RULE_FIXTURE, FakeWeb

T0 = 1790000000.0  # 2026-09-21


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


def listener(clock=None):
    return Listener(fetcher=Fetcher(min_interval=0, timeout=5), clock=clock or Clock(), workers=4)


class Extraction(unittest.TestCase):
    def test_corpus(self):
        for name, (html, exp) in FIXTURES.items():
            r = X.extract(html)
            if exp is None:
                self.assertIsNone(r, name)
            else:
                for k, v in exp.items():
                    self.assertEqual(r.get(k), v, f"{name}.{k}")

    def test_site_rule(self):
        name, rules, exp = RULE_FIXTURE
        r = X.extract(FIXTURES[name][0], rules)
        self.assertEqual({k: r[k] for k in exp}, exp)

    def test_price_formats(self):
        cases = {"1 299,99 €": 1299.99, "1.299,99": 1299.99, "1,299.99": 1299.99, "299€99": 299.99,
                 "1.299": 1299.0, "EUR 89,9": 89.9, "Prix : 1\u202f049,00 €": 1049.0, "gratuit": None, "0": None}
        for s, v in cases.items():
            self.assertEqual(X.parse_price(s), v, s)

    def test_gtin_checksum(self):
        self.assertEqual(X.clean_gtin("4006381333931"), "4006381333931")
        self.assertIsNone(X.clean_gtin("4006381333932"))


class Fetching(unittest.TestCase):
    def test_statuses(self):
        with FakeWeb() as w:
            f = Fetcher(min_interval=0, timeout=5)
            self.assertEqual(f.get(w.url + "/f/jsonld_simple")["status"], "ok")
            self.assertEqual(f.get(w.url + "/private/x")["status"], "disallowed")
            self.assertEqual(f.get(w.url + "/blocked")["status"], "blocked")
            self.assertEqual(f.get(w.url + "/soft-blocked")["status"], "blocked")
            r = f.get(w.url + "/rate")
            self.assertEqual((r["status"], r["retry_after"]), ("rate_limited", 600))
            self.assertEqual(f.get(w.url + "/nope")["status"], "gone")
            self.assertEqual(f.get(w.url + "/boom")["status"], "error")
            self.assertEqual(w.hits.get("/private/x"), None)  # jamais demandé

    def test_conditional_get(self):
        with FakeWeb() as w:
            w.live["a"] = (449.0, "InStock", None)
            f = Fetcher(min_interval=0)
            r1 = f.get(w.url + "/live/a")
            self.assertEqual(f.get(w.url + "/live/a", etag=r1["etag"])["status"], "not_modified")

    def test_politeness(self):
        with FakeWeb() as w:
            f = Fetcher(min_interval=0.3)
            t = time.monotonic()
            for _ in range(4):
                f.get(w.url + "/f/opengraph")
            self.assertGreaterEqual(time.monotonic() - t, 0.9)


class Pipeline(unittest.TestCase):
    def test_price_lifecycle_and_events(self):
        c = Clock()
        L = listener(c)
        with FakeWeb() as w:
            w.live["p1"] = (449.0, "InStock", "4006381333931")
            oid = L.track(w.url + "/live/p1", priority=1)
            L.run_due()
            c.advance(3600); w.live["p1"] = (449.0, "InStock", "4006381333931"); L.run_due()   # inchangé (304)
            c.advance(3600); w.live["p1"] = (399.0, "InStock", "4006381333931"); L.run_due()   # baisse
            c.advance(3600); w.live["p1"] = (399.0, "OutOfStock", "4006381333931"); L.run_due()
            c.advance(3600); w.live["p1"] = (419.0, "InStock", "4006381333931"); L.run_due()
        types = [e["type"] for e in reversed(L.events())]
        self.assertEqual(types, ["NEW_PRODUCT", "NEW_OFFER", "PRICE_DROP", "NEW_LOW", "OUT_OF_STOCK", "PRICE_INCREASE", "BACK_IN_STOCK"])
        obs = L.q("SELECT price, availability, n FROM observations WHERE offer_id=?", (oid,))
        self.assertEqual([(o["price"], o["availability"]) for o in obs],
                         [(449.0, "in_stock"), (399.0, "in_stock"), (399.0, "out_of_stock"), (419.0, "in_stock")])
        self.assertEqual(obs[0]["n"], 2)  # compression : 2 relevés, 1 ligne

    def test_suspect_price_needs_confirmation(self):
        c = Clock()
        L = listener(c)
        with FakeWeb() as w:
            w.live["p"] = (500.0, "InStock", None)
            oid = L.track(w.url + "/live/p", 1)
            L.run_due()
            c.advance(3600); w.live["p"] = (49.0, "InStock", None); L.run_due()     # erreur de saisie probable
            self.assertEqual(L.q("SELECT COUNT(*) n FROM observations WHERE offer_id=?", (oid,), one=True)["n"], 1)
            nxt = L.q("SELECT next_check_at FROM offers WHERE id=?", (oid,), one=True)["next_check_at"]
            self.assertAlmostEqual(nxt - c.t, 120)                                    # re-vérification rapide
            c.advance(120); L.run_due()                                               # confirmé → enregistré
        self.assertEqual(L.q("SELECT COUNT(*) n FROM observations WHERE offer_id=?", (oid,), one=True)["n"], 2)
        self.assertIn("PRICE_ANOMALY", [e["type"] for e in L.events()])

    def test_adaptive_schedule(self):
        c = Clock()
        L = listener(c)
        with FakeWeb() as w:
            w.live["s"] = (300.0, "InStock", None)
            oid = L.track(w.url + "/live/s", 2)   # base 6 h
            L.run_due()
            iv = lambda: L.q("SELECT interval_s FROM offers WHERE id=?", (oid,), one=True)["interval_s"]
            after_first = iv()
            for _ in range(4):
                c.advance(iv()); L.run_due()
            self.assertGreater(iv(), after_first)                   # stable → on espace
            c.advance(iv()); w.live["s"] = (280.0, "InStock", None); L.run_due()
            self.assertLess(iv(), 6 * 3600)                         # ça bouge → on rapproche

    def test_blocked_and_gone(self):
        c = Clock()
        L = listener(c)
        with FakeWeb() as w:
            b = L.track(w.url + "/blocked")
            g = L.track(w.url + "/live/unknown")
            L.run_due()
        st = {o["id"]: o["status"] for o in L.offers()}
        self.assertEqual((st[b], st[g]), ("blocked", "gone"))
        self.assertEqual({e["type"] for e in L.events()}, {"SOURCE_BLOCKED", "OFFER_REMOVED"})

    def test_product_matching(self):
        c = Clock()
        L = listener(c)
        with FakeWeb() as w:
            w.live["m1"] = (449.0, "InStock", "4006381333931")
            w.live["m2"] = (439.0, "InStock", "4006381333931")
            L.track(w.url + "/live/m1"); L.track(w.url + "/live/m2")
            L.run_due()
        self.assertEqual(len(L.products()), 1)
        self.assertEqual(L.products()[0]["best_price"], 439.0)

    def test_history(self):
        c = Clock()
        L = listener(c)
        with FakeWeb() as w:
            w.live["h"] = (500.0, "InStock", "4006381333931")
            L.track(w.url + "/live/h", 1)
            for price in [500, 500, 480, 480, 450, 470]:
                w.live["h"] = (float(price), "InStock", "4006381333931")
                L.run_due(); c.advance(86400)
        h = L.history(L.products()[0]["id"])
        self.assertEqual(h["stats"]["current"], 470.0)
        self.assertEqual(h["stats"]["low_all"], 450.0)
        self.assertGreaterEqual(len(h["daily"]), 6)

    def test_feeds(self):
        xml = """<?xml version="1.0"?><rss xmlns:g="http://base.google.com/ns/1.0"><channel>
          <item><g:id>1</g:id><title>Nordvik Clean 60</title><link>https://m.example/p/1</link><g:price>449.00 EUR</g:price>
          <g:sale_price>399.00 EUR</g:sale_price><g:availability>in stock</g:availability><g:gtin>4006381333931</g:gtin></item>
          <item><g:id>2</g:id><title>Kessler KD</title><link>https://m.example/p/2</link><g:price>329,00 EUR</g:price>
          <g:availability>out of stock</g:availability></item></channel></rss>"""
        items = parse_feed(xml)
        self.assertEqual([(i["price"], i["list_price"], i["availability"]) for i in items],
                         [(399.0, 449.0, "in_stock"), (329.0, None, "out_of_stock")])
        csv_ = "id;title;link;price;availability;gtin\n1;A;https://m.example/a;1 299,00 €;in stock;4006381333931\n"
        self.assertEqual(parse_feed(csv_)[0]["price"], 1299.0)
        import tempfile, os
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as fh:
            fh.write(xml)
        L = listener()
        fid = L.add_feed(fh.name, "Marchand X")
        self.assertEqual(L.run_feed(fid)["items"], 2)
        os.unlink(fh.name)

    def test_realtime_sse_and_webhook(self):
        c = Clock()
        L = listener(c)
        got_hook = []
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        class Hook(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                got_hook.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                self.send_response(204); self.end_headers()
        hook = ThreadingHTTPServer(("127.0.0.1", 0), Hook)
        threading.Thread(target=hook.serve_forever, daemon=True).start()
        L.add_webhook(f"http://127.0.0.1:{hook.server_address[1]}/", ["PRICE_DROP"])
        api = serve(L, 0)
        threading.Thread(target=api.serve_forever, daemon=True).start()
        received = []

        def listen():
            with urllib.request.urlopen(f"http://127.0.0.1:{api.server_address[1]}/api/stream", timeout=10) as r:
                for line in r:
                    if line.startswith(b"data: "):
                        received.append((time.perf_counter(), json.loads(line[6:])))
                        if len(received) >= 3:
                            return
        th = threading.Thread(target=listen, daemon=True); th.start(); time.sleep(0.3)
        with FakeWeb() as w:
            w.live["rt"] = (600.0, "InStock", None)
            oid = L.track(w.url + "/live/rt", 1); L.check(oid)
            w.live["rt"] = (540.0, "InStock", None)
            t = time.perf_counter(); L.check(oid)
        th.join(5)
        for _ in range(30):
            if got_hook:
                break
            time.sleep(0.1)
        self.assertEqual([e["type"] for _, e in received], ["NEW_PRODUCT", "NEW_OFFER", "PRICE_DROP"])
        self.assertLess(received[2][0] - t, 1.0)
        self.assertEqual(got_hook[0]["type"], "PRICE_DROP")
        api.shutdown(); api.server_close(); hook.shutdown(); hook.server_close()

    def test_diagnose(self):
        L = listener()
        with FakeWeb() as w:
            d = L.diagnose(w.url + "/f/text_only_needs_rule")
            self.assertIsNone(d["extraction"]); self.assertTrue(d["hint"])
            L.set_rules("127.0.0.1:" + w.url.rsplit(":", 1)[1], {"price": "div.prix-final"})
            self.assertEqual(L.diagnose(w.url + "/f/text_only_needs_rule")["extraction"]["price"], 299.99)


if __name__ == "__main__":
    unittest.main()
