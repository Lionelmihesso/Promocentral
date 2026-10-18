"""Moteur quotidien : idempotence, plan de collecte piloté par la demande réelle, fausses remises écartées, similarité.
Marché simulé à vérité connue (bench/market_sim) lu par le vrai moteur de collecte."""
import json
import tempfile
import unittest
import warnings
from datetime import date, timedelta

from bench.market_sim import MOVING_CATALOG, Market, SimClock, SimFetcher
from collect.pipeline import Collector
from listener.core import Listener
from radar.engine import Radar
from radar.shop import Shop

CAT = [c for c in MOVING_CATALOG if c[0] in ("lave_linge", "televiseur", "matelas", "lit")]
START = date(2026, 1, 5)


class Engine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = Market(start=START, days=200, seed=4, catalog=CAT)
        cls.clock = SimClock(START)
        cls.L = Listener(fetcher=SimFetcher(cls.m, cls.clock), clock=cls.clock, workers=1)
        sites = {"sim": {"name": "Sim", "home": "http://sim", "enabled": True, "product_url": ".", "sitemaps": []}}
        cls.C = Collector(cls.L, sites, report_dir=tempfile.mkdtemp(prefix="radar_reports_"))
        for o in cls.m.offers:
            oid = cls.L.track(o["url"], 2, o["merchant"])
            cls.L.q("INSERT OR IGNORE INTO collect_offers(offer_id, retailer, category_hint, added_at) VALUES (?,?,?,0)", (oid, "sim", None))
        cls.RD = Radar(cls.L)
        for k in range(90):                                         # 90 jours d'historique, tout relu chaque jour
            cls.day(k); cls.C.nightly()
        cls.k = 90
        cls.day(cls.k)
        cls.first = cls.RD.run_daily(cls.C)
        cls.shop = Shop(cls.RD)

    @classmethod
    def day(cls, k):
        cls.clock.t = SimClock(START + timedelta(days=k)).t

    @classmethod
    def tearDownClass(cls):
        cls.L.close()

    def offers_of(self, where, args=()):
        return {r["id"] for r in self.L.q(f"SELECT o.id FROM offers o JOIN products p ON p.id=o.product_id WHERE o.status!='gone' AND {where}", args)}

    def test_1_daily_runs_once_per_day(self):
        self.assertIn("signals", self.first)
        self.assertIn("refresh", self.first)
        self.assertIn("similarity", self.first)                                # première nuit de la semaine
        self.assertTrue(self.RD.run_daily(self.C)["skipped"])                   # relance : rien de refait
        self.assertEqual(self.L.q("SELECT COUNT(*) n FROM jobs WHERE name='daily' AND key=?", (self.L.today().isoformat(),), one=True)["n"], 1)

    def test_2_full_daily_refresh_while_it_fits_the_night(self):
        plan, tiers = self.RD.refresh_plan()
        live = {r["id"] for r in self.L.q("SELECT id FROM offers WHERE status!='gone'")}
        self.assertEqual(tiers["mode"], "full")                                 # petit catalogue : tout est relu chaque jour
        self.assertEqual(set(plan), live)
        self.assertEqual(len(plan), len(set(plan)))
        self.assertEqual(self.first["refresh"]["mode"], "full")

    def test_2b_adaptive_beyond_the_night_budget_keeps_deals_fresh(self):
        u = self.RD.user("demande@test.local")
        pid = self.L.q("SELECT id FROM products ORDER BY id LIMIT 1", one=True)["id"]
        self.L.q("INSERT OR IGNORE INTO saves(user_id, product_id, created_at) VALUES (?,?,0)", (u, pid))
        brand = self.L.q("SELECT brand FROM products WHERE id<>? AND brand IS NOT NULL ORDER BY id DESC LIMIT 1", (pid,), one=True)["brand"]
        self.RD.follow(u, "brand", brand)
        try:
            day = self.L.today()
            plan, tiers = self.RD.refresh_plan(day, budget_s=0)                 # catalogue trop gros pour la nuit (simulé)
            self.assertEqual(tiers["mode"], "adaptive")
            total = self.L.q("SELECT COUNT(*) n FROM offers WHERE status!='gone'", one=True)["n"]
            self.assertLessEqual(len(plan), total)
            self.assertEqual(len(plan), len(set(plan)))                         # chaque offre au plus une fois par jour
            self.assertTrue(self.offers_of("p.id=?", (pid,)) <= set(plan))      # un favori est relu chaque jour
            in_deal = {d["id"] for d in self.shop._deals()}
            for d in in_deal:                                                   # un deal affiché est relu le jour même : jamais périmé
                self.assertTrue(self.offers_of("p.id=?", (d,)) <= set(plan), d)
            three = set().union(*(set(self.RD.refresh_plan(day + timedelta(days=k), budget_s=0)[0]) for k in range(3)))
            self.assertTrue(self.offers_of("p.brand=?", (brand,)) <= three)      # marque suivie : au moins tous les 3 jours
        finally:
            self.L.q("DELETE FROM saves WHERE user_id=?", (u,))
            self.RD.follow(u, "brand", brand, on=False)

    def test_3_fake_discounts_are_never_listed(self):
        deals = self.shop._deals()
        self.assertTrue(deals)
        victim = deals[0]["id"]                                                 # on force une fausse remise sur un deal affiché
        self.L.q("INSERT OR REPLACE INTO market_signals(product_id, state, data, day) VALUES (?,?,?,?)",
                 (victim, "NORMAL", json.dumps({"inflated": True}), self.L.today().isoformat()))
        try:
            ids = {c["id"] for c in self.shop._deals()}
            self.assertNotIn(victim, ids)
            self.assertFalse(self.RD.inflated_products() & ids)
            item = self.shop.item({}, victim)                                   # la fiche reste visible, sans remise affichée
            self.assertEqual(item["pct"], 0)
            self.assertIsNone(item["was"])
        finally:
            self.L.q("DELETE FROM market_signals WHERE product_id=?", (victim,))

    def test_4_only_real_discounts(self):
        for c in self.shop._deals():
            self.assertGreater(c["pct"], 0)
            self.assertGreater(c["was"], c["price"])

    def test_5_similarity_stays_in_category(self):
        pairs = self.L.q("SELECT s.score, a.category ca, b.category cb FROM similarity s "
                         "JOIN products a ON a.id=s.product_id JOIN products b ON b.id=s.other_id")
        self.assertTrue(pairs)
        for p in pairs:
            self.assertEqual(p["ca"], p["cb"])
            self.assertTrue(0.5 <= p["score"] <= 0.99)
        pid = self.L.q("SELECT product_id FROM similarity ORDER BY score DESC LIMIT 1", one=True)["product_id"]
        best = self.L.q("SELECT other_id FROM similarity WHERE product_id=? ORDER BY score DESC, other_id LIMIT 1", (pid,), one=True)["other_id"]
        self.assertEqual(self.shop.item({}, pid)["similar"][0]["id"], best)     # la fiche suit la similarité calculée


class Lifecycle(unittest.TestCase):
    def test_connection_closed(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with Listener() as L:
                Radar(L).user("x")
            self.assertIsNone(L.db)
        self.assertFalse([x for x in w if issubclass(x.category, ResourceWarning)])


if __name__ == "__main__":
    unittest.main()
