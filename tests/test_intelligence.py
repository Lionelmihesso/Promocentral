"""Tests v0.2 : intelligence prix, signaux, normalisation, promotions, surveillances, motifs, migration."""
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta

from bench.market_sim import Market, SimClock, SimFetcher, run
from listener import intelligence as I
from listener import normalize as N
from listener import signals as S
from listener.core import Listener

D0 = date(2026, 6, 1)


def flat(days, price=500.0, start=D0):
    return [(start + timedelta(days=k), price) for k in range(days)]


class Intelligence(unittest.TestCase):
    def test_percentile_midrank_with_ties(self):
        self.assertEqual(I.percentile_rank([100] * 10, 100), 50.0)
        self.assertEqual(I.percentile_rank([100, 200, 300, 400], 100), 12.5)
        self.assertEqual(I.percentile_rank([100, 200, 300, 400], 50), 0.0)

    def test_stats_windows(self):
        s = [(D0 + timedelta(days=k), 500.0 - k) for k in range(100)]  # baisse régulière
        a = I.analyze(s, s[-1][0])
        self.assertEqual(a["stats"]["min_7"], 401.0)
        self.assertEqual(a["stats"]["min_90"], 401.0)
        self.assertEqual(a["stats"]["median_30"], 415.5)
        self.assertEqual(a["position"]["days_since_low_365"], 0)
        self.assertEqual(a["n_days"], 90)

    def test_states(self):
        base = flat(90)
        low = base[:-1] + [(base[-1][0], 380.0)]
        self.assertEqual(I.analyze(low, low[-1][0])["state"], "EXCEPTIONAL")      # -24 % vs courant
        rare = base[:-1] + [(base[-1][0], 470.0)]
        self.assertEqual(I.analyze(rare, rare[-1][0])["state"], "EXCEPTIONAL")    # jamais vu aussi bas en 90 j (≤ p10)
        good = [(d, 450.0 if k % 10 < 3 else 500.0) for k, (d, _) in enumerate(base)]
        good[-1] = (good[-1][0], 450.0)
        self.assertEqual(I.analyze(good, good[-1][0])["state"], "GOOD")           # 15e percentile, -10 %
        self.assertEqual(I.analyze(base, base[-1][0])["state"], "NORMAL")
        high = base[:-1] + [(base[-1][0], 560.0)]
        self.assertEqual(I.analyze(high, high[-1][0])["state"], "EXPENSIVE")      # +12 %
        self.assertEqual(I.analyze(flat(10), D0 + timedelta(days=9))["state"], "UNKNOWN")  # historique insuffisant

    def test_frequent_promos_do_not_make_normal_price_expensive(self):
        s = [(D0 + timedelta(days=k), 400.0 if k % 2 else 500.0) for k in range(90)]  # 50 % de jours en promo
        s[-1] = (s[-1][0], 500.0)
        self.assertEqual(I.analyze(s, s[-1][0])["state"], "NORMAL")

    def test_thresholds_configurable(self):
        base = flat(89) + [(D0 + timedelta(days=89), 470.0)]
        self.assertEqual(I.analyze(base, base[-1][0])["state"], "EXCEPTIONAL")
        cfg = {**I.DEFAULT, "good_discount_vs_regular": 0.08, "good_pct": 0, "exceptional_pct": 0}
        self.assertEqual(I.analyze(base, base[-1][0], cfg=cfg)["state"], "NORMAL")

    def test_promotion_three_notions(self):
        pos_normal = {"percentile": 55}
        fake = I.promotion(500, 650, 650, pos_normal)
        self.assertEqual((fake["advertised_discount"], fake["assessment"]), (0.2308, "ADVERTISED_NOT_HISTORICAL"))
        real = I.promotion(420, 500, 500, {"percentile": 5})
        self.assertIsNone(real["assessment"])
        self.assertEqual(real["observed_discount"], 0.16)

    def test_retail_calendar(self):
        self.assertEqual(I.retail_events(2026)["black_friday"], (date(2026, 11, 20), date(2026, 11, 30)))
        self.assertEqual(I.event_of(date(2026, 11, 27)), "black_friday")
        self.assertEqual(I.days_to_next_event(date(2026, 11, 15))[0], 5)


class Normalization(unittest.TestCase):
    def test_category(self):
        self.assertEqual(N.categorize("Lave-vaisselle pose libre 60 cm")[0], "lave_vaisselle")
        self.assertEqual(N.categorize("LAVE LINGE SÉCHANT 9 kg")[0], "lave_linge_sechant")
        self.assertEqual(N.categorize("Produit X", "Électroménager > Réfrigérateurs")[:2], ("refrigerateur", "declared"))
        self.assertIsNone(N.categorize("Objet mystère")[0])

    def test_attributes_no_invention(self):
        a = N.attributes("Lave-vaisselle 60 cm 14 couverts 42 dB classe B")
        self.assertEqual(a, {"energy_class": "B", "width_cm": 60, "place_settings": 14, "noise_db": 42})
        self.assertEqual(N.attributes("Produit sans détails"), {})
        self.assertEqual(N.attributes("x", {"Classe énergétique": "A", "Largeur": "59,8 cm"}), {"energy_class": "A", "width_cm": 59.8})

    def test_quality(self):
        self.assertEqual(N.quality({"consistent": True, "currency_known": True, "availability": "in_stock"}), "KNOWN")
        self.assertEqual(N.quality({"consistent": False, "availability": "in_stock"}), "CONFLICTING")
        self.assertEqual(N.quality({"consistent": True, "availability": "unknown"}), "UNKNOWN")
        self.assertEqual(N.quality({}, pending=True), "SUSPECT")


def snap(state="GOOD", pct=12, vs=-0.15, n=90, **kw):
    return {"product_id": 1, "as_of": D0, "merchant": "M", "offers_in_stock": 3, "quality": "KNOWN", "extraction_confidence": 0.95,
            "intel": {"state": state, "current": 425.0, "reference_price": 500.0, "median_price": 495.0, "n_days": n,
                      "position": {"percentile": pct, "vs_median": vs, "vs_regular": vs, "vs_low": 0.0, "window_days": 90}},
            **kw}


class Signals(unittest.TestCase):
    def test_opportunity_schema(self):
        sig = S.evaluate(snap())[0]
        self.assertEqual(sig["type"], "PRICE_OPPORTUNITY")
        for k in ("product_id", "current_price", "reference_price", "discount", "historical_percentile", "confidence", "reasons"):
            self.assertIn(k, sig)
        self.assertEqual(sig["discount"], 0.15)
        self.assertGreater(sig["confidence"], 0.9)

    def test_no_signal_without_history_or_suspect(self):
        self.assertEqual(S.evaluate(snap(state="UNKNOWN")), [])
        self.assertEqual(S.evaluate(snap(quality="SUSPECT")), [])

    def test_confidence_decreases_with_short_history(self):
        self.assertLess(S.evaluate(snap(n=20))[0]["confidence"], S.evaluate(snap(n=90))[0]["confidence"])

    def test_market_wide_emerging_scarcity_high(self):
        offers = [{"merchant": m, "price": 430, "availability": "in_stock", "percentile": 8, "vs_median": -0.12} for m in "AB"]
        types = {s["type"] for s in S.evaluate(snap(offers=offers, recent_drops={1: 0.12, 2: 0.08}, in_stock_7d_ago=4, offers_in_stock=1))}
        self.assertEqual(types, {"PRICE_OPPORTUNITY", "MARKET_WIDE_OPPORTUNITY", "EMERGING_PROMOTION", "SCARCITY"})
        high = S.evaluate(snap(state="EXPENSIVE", pct=90, vs=0.12))
        self.assertEqual([s["type"] for s in high], ["PRICE_HIGH"])

    def test_watch_matching(self):
        p = {"id": 1, "category": "lave_vaisselle", "brand": "Nordvik", "attributes": {"energy_class": "B", "noise_db": 42}}
        w = {"category": "lave_vaisselle", "constraints": {"budget_max": 600, "brands": ["nordvik"], "energy_class": "C",
                                                            "attributes": {"noise_db": {"max": 44}}}}
        self.assertTrue(S.product_matches(w, p, 550))
        self.assertFalse(S.product_matches(w, p, 650))                                         # hors budget
        self.assertFalse(S.product_matches({**w, "constraints": {"energy_class": "A"}}, p, 500))  # classe B > A
        self.assertTrue(S.condition_met({"condition": "target", "target_price": 430}, snap(), set())[0])
        self.assertFalse(S.condition_met({"condition": "opportunity", "acceptable_price": 400}, snap(), {"PRICE_OPPORTUNITY"})[0])
        self.assertTrue(S.condition_met({"condition": "opportunity", "acceptable_price": 450}, snap(), {"PRICE_OPPORTUNITY"})[0])


class EngineIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res, cls.L, cls.m = run(n_products=3, days=260, warmup=120, verbose=False)

    def test_detection_quality_on_ground_truth(self):
        e = self.res["engine"]
        self.assertGreaterEqual(e["precision"], 0.85)
        self.assertGreaterEqual(e["recall"], 0.85)
        self.assertEqual(self.res["fake_ignored_engine"], 1.0)
        self.assertLess(self.res["opportunity_alerts_per_product_month"], self.res["price_drop_events_per_product_month"])

    def test_product_graph(self):
        prods = self.L.products()
        self.assertEqual(len(prods), 3)                       # 9 offres → 3 produits (GTIN)
        self.assertTrue(all(p["offers"] == 3 for p in prods))
        self.assertTrue(all(p["category"] and p["attributes"].get("energy_class") for p in prods))

    def test_facts_have_provenance(self):
        f = self.L.facts(limit=5)[0]
        for k in ("url", "merchant", "method", "raw_price", "price", "currency", "availability", "confidence", "quality",
                  "observed_from", "observed_to", "confirmations"):
            self.assertIn(k, f)

    def test_events_normalized(self):
        ev = self.L.events(limit=500)
        self.assertTrue({"NEW_PRODUCT", "NEW_OFFER", "PRICE_DROP", "PRICE_INCREASE", "PROMOTION_STARTED",
                         "PROMOTION_ENDED", "SIGNAL_RAISED", "SIGNAL_CLEARED"} <= {e["type"] for e in self.L.events(limit=100000)})
        for e in ev:
            self.assertIn(e["entity_type"], ("offer", "product", "signal", "watch"))
            self.assertIsNotNone(e["confidence"])
            self.assertIsNotNone(e["source"])

    def test_intelligence_api(self):
        pid = self.L.products()[0]["id"]
        it = self.L.intelligence(pid)
        for k in ("current", "stats", "position", "state", "reference_price"):
            self.assertIn(k, it["intel"])
        for k in ("min_7", "min_30", "min_90", "min_365", "median_30", "median_90", "median_365", "mean_90", "volatility_90"):
            self.assertIn(k, it["intel"]["stats"])

    def test_patterns_find_black_friday(self):
        pat = self.L.patterns("category")
        # 260 j depuis juin : un Black Friday observé ; son taux de promo doit dépasser nettement la base
        bf = [v["by_event"].get("black_friday") for v in pat.values() if v["by_event"].get("black_friday")]
        self.assertTrue(bf and max(x["lift"] for x in bf) > 2)


class Watches(unittest.TestCase):
    def test_category_watch_lifecycle(self):
        m = Market(n_products=3, days=200, seed=3)
        clock = SimClock(m.start)
        L = Listener(fetcher=SimFetcher(m, clock), clock=clock, workers=1)
        for o in m.offers:
            L.track(o["url"], 3, o["merchant"])
        wid = None
        for k in range(200):
            clock.t = SimClock(m.start + timedelta(days=k)).t
            L.q("UPDATE offers SET next_check_at=0 WHERE status='active'")
            L.run_due()
            if k == 5:
                wid = L.add_watch({"category": "lave_vaisselle", "constraints": {"budget_max": 2000}, "condition": "opportunity"})
        types = [e["type"] for e in L.events(limit=100000)]
        self.assertIn("WATCH_MATCHED", types)
        self.assertIn("WATCH_UNMATCHED", types)
        # périmètre respecté : seuls des lave-vaisselle déclenchent la surveillance
        cats = {L.q("SELECT category FROM products WHERE id=?", (e["product_id"],), one=True)["category"]
                for e in L.events(limit=100000, type_="WATCH_MATCHED")}
        self.assertEqual(cats, {"lave_vaisselle"})
        # un produit surveillé passe en priorité 1
        o = L.q("SELECT o.* FROM offers o JOIN products p ON p.id=o.product_id WHERE p.category='lave_vaisselle' LIMIT 1", one=True)
        self.assertIn("demande active", o["schedule_reason"])
        self.assertRaises(ValueError, L.add_watch, {"condition": "opportunity"})


class Migration(unittest.TestCase):
    def test_v01_database_upgrades_in_place(self):
        path = os.path.join(tempfile.mkdtemp(), "v01.sqlite")
        db = sqlite3.connect(path)
        db.executescript("""CREATE TABLE products (id INTEGER PRIMARY KEY, gtin TEXT UNIQUE, brand TEXT, mpn TEXT, title TEXT,
            norm_title TEXT, needs_review INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL);
            INSERT INTO products(title, created_at) VALUES ('ancien produit', 1);""")
        db.commit(); db.close()
        L = Listener(path)
        self.assertEqual(L.q("SELECT title, attributes FROM products", one=True), {"title": "ancien produit", "attributes": "{}"})


if __name__ == "__main__":
    unittest.main()
