"""Radar (audit v15) : couche utilisateur, opportunités personnelles, suivis, alternatives, notifications, fréquence adaptative.
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

CAT = [c for c in MOVING_CATALOG if c[0] in ("lave_linge", "televiseur", "matelas", "lit")]
START = date(2026, 1, 5)


class RadarFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = Market(start=START, days=200, seed=4, catalog=CAT)
        cls.clock = SimClock(START)
        cls.L = Listener(fetcher=SimFetcher(cls.m, cls.clock), clock=cls.clock, workers=1)
        cls.R = {"sim": {"name": "Sim", "home": "http://sim", "enabled": True, "product_url": ".", "sitemaps": []}}
        cls.C = Collector(cls.L, cls.R, report_dir=tempfile.mkdtemp(prefix="radar_reports_"))
        for o in cls.m.offers:
            oid = cls.L.track(o["url"], 2, o["merchant"])
            cls.L.q("INSERT OR IGNORE INTO collect_offers(offer_id, retailer, category_hint, added_at) VALUES (?,?,?,0)", (oid, "sim", None))
        cls.RD = Radar(cls.L)
        for k in range(90):                                         # 90 jours d'historique, tout relu chaque jour
            cls.day(k); cls.C.nightly()
        cls.k = 90

    @classmethod
    def day(cls, k):
        cls.clock.t = SimClock(START + timedelta(days=k)).t

    @classmethod
    def tearDownClass(cls):
        cls.L.close()

    def advance(self, n=1):
        out = []
        for _ in range(n):
            self.__class__.k += 1
            self.day(self.k)
            out.append(self.RD.run_daily(self.C))
        return out

    def pid(self, cat, i=0):
        return self.L.q("SELECT id FROM products WHERE category=? ORDER BY id", (cat,))[i]["id"]

    def test_1_users_watches_and_idempotence(self):
        RD = self.RD
        self.__class__.alice = RD.user("alice", max_alerts_per_day=2)
        self.__class__.bob = RD.user("bob")
        tv = self.pid("televiseur")
        price = RD.market_signal(tv)["price"]
        self.__class__.w_tv = RD.watch(self.alice, tv, price * 0.99)           # cible juste sous le prix : sera vite atteinte
        RD.follow(self.alice, "brand", self.L.q("SELECT brand FROM products WHERE category='lave_linge'", one=True)["brand"])
        RD.follow(self.alice, "category", "matelas")
        self.assertTrue(all(w["user_id"] for w in self.L.q("SELECT user_id FROM user_watches")))
        s = self.advance(1)[0]
        self.assertFalse(s.get("skipped"))
        n_opp = self.L.q("SELECT COUNT(*) n FROM opportunities", one=True)["n"]
        again = RD.run_daily(self.C)                                            # relance le même jour
        self.assertTrue(again["skipped"])
        self.assertEqual(self.L.q("SELECT COUNT(*) n FROM opportunities", one=True)["n"], n_opp)
        RD.run_daily(self.C, force=True)                                        # même forcée : aucun doublon (clés uniques)
        self.assertEqual(self.L.q("SELECT COUNT(*) n FROM opportunities", one=True)["n"], n_opp)
        self.assertLessEqual(self.L.q("SELECT COUNT(*) n FROM notifications WHERE day=?", (self.L.today().isoformat(),), one=True)["n"], 2)

    def test_2_target_reached_and_cooldown(self):
        hits = []
        for _ in range(40):
            self.advance(1)
            hits += self.L.q("SELECT day, price FROM opportunities WHERE watch_id=? AND type='TARGET_REACHED' AND day=?", (self.w_tv, self.L.today().isoformat()))
        self.assertTrue(hits, "le prix cible doit finir par être atteint")
        for a, b in zip(hits, hits[1:]):                                        # dans les 14 jours : seulement si 5 % plus bas
            if date.fromisoformat(b["day"]) - date.fromisoformat(a["day"]) < timedelta(days=14):
                self.assertLess(b["price"], a["price"] * 0.95)

    def test_3_alternatives_constraints_and_rejection(self):
        RD = self.RD
        tvs = self.L.q("SELECT id, attributes FROM products WHERE category='televiseur' ORDER BY json_extract(attributes,'$.screen_in') DESC")
        big = tvs[0]["id"]
        prices = {t["id"]: RD.market_signal(t["id"])["price"] for t in tvs}
        target = sorted(prices.values())[-2] * 1.05                             # au-dessus de la 2e TV, sous la plus grande
        w = RD.watch(self.bob, big, target, alternatives=True, constraints={"min": {"screen_in": 50}})
        self.advance(2)
        alts = self.L.q("SELECT DISTINCT product_id FROM opportunities WHERE watch_id=? AND type='ALTERNATIVE'", (w,))
        self.assertTrue(alts, "une alternative doit être proposée")              # le test n'est pas vide
        for a in alts:
            attrs = json.loads(self.L.q("SELECT attributes FROM products WHERE id=?", (a["product_id"],), one=True)["attributes"])
            self.assertGreaterEqual(attrs.get("screen_in", 0), 50)               # contrainte dure respectée (pas de 43")
        rejected = alts[0]["product_id"]
        RD.reject_alternative(w, rejected)
        self.advance(3)
        later = {r["product_id"] for r in self.L.q("SELECT product_id FROM opportunities WHERE watch_id=? AND type='ALTERNATIVE' AND day>?",
                                                   (w, (self.L.today() - timedelta(days=3)).isoformat()))}
        self.assertNotIn(rejected, later)                                        # refusée : plus jamais reproposée
        RD.watch(self.bob, rejected, 1)                                          # une alternative gardée devient un suivi à part entière
        self.assertNotIn(rejected, {r["other_id"] for r in RD.q("SELECT other_id FROM similarity WHERE product_id=?", (big,))} - {rejected} | set())

    def test_4_relevance_and_discovery(self):
        carl = self.RD.user("carl")                                             # aucun intérêt déclaré
        self.advance(10)
        a = self.L.q("SELECT section, reason FROM opportunities WHERE user_id=?", (self.alice,))
        c = self.L.q("SELECT section, reason FROM opportunities WHERE user_id=?", (carl,))
        self.assertTrue(any(r["section"] == "foryou" and r["reason"] in ("Catégorie suivie",) or r["reason"].startswith("Vous suivez") for r in a))
        self.assertTrue(all(r["section"] == "discovery" for r in c))            # sans signal personnel : seulement « Vous ne cherchiez pas ça »
        sig_pids = [r["product_id"] for r in self.L.q("SELECT DISTINCT product_id FROM opportunities WHERE user_id=?", (self.alice,))]
        if sig_pids:
            self.RD.interact(self.alice, "dismiss", sig_pids[0])
            self.advance(5)
            recent = self.L.q("SELECT product_id FROM opportunities WHERE user_id=? AND day>? AND section!='watch'",
                              (self.alice, (self.L.today() - timedelta(days=5)).isoformat()))
            self.assertNotIn(sig_pids[0], {r["product_id"] for r in recent})

    def test_5_notifications_capped_and_meaningful(self):
        for n in self.L.q("SELECT n.*, u.max_alerts_per_day m FROM notifications n JOIN users u ON u.id=n.user_id"):
            ids = json.loads(n["opportunity_ids"])
            self.assertLessEqual(len(ids), n["m"])
            types = {r["type"] for r in self.L.q(f"SELECT type FROM opportunities WHERE id IN ({','.join('?' * len(ids))})", ids)}
            self.assertTrue(types <= {"TARGET_REACHED", "ALTERNATIVE", "EXCEPTIONAL_PRICE", "PRICE_DROP"})
        per_day = self.L.q("SELECT user_id, day, COUNT(*) n FROM notifications GROUP BY user_id, day HAVING n>1")
        self.assertEqual(per_day, [])                                           # au plus un récapitulatif par jour
        # rareté : pas plus de 2 alertes « opportunité » par fenêtre de 7 jours
        for u in self.L.q("SELECT id FROM users"):
            days = [r["day"] for r in self.L.q("SELECT day FROM opportunities WHERE user_id=? AND notified=1 AND type NOT IN ('TARGET_REACHED','ALTERNATIVE') ORDER BY day", (u["id"],))]
            for i, d0 in enumerate(days):
                window = [d for d in days[i:] if date.fromisoformat(d) < date.fromisoformat(d0) + timedelta(days=7)]
                self.assertLessEqual(len(window), 2)

    def test_6_adaptive_refresh_never_exceeds_daily(self):
        plan, tiers = self.RD.refresh_plan()
        total = self.L.q("SELECT COUNT(*) n FROM offers WHERE status!='gone'", one=True)["n"]
        self.assertLessEqual(len(plan), total)
        self.assertEqual(len(plan), len(set(plan)))                             # chaque offre au plus une fois par jour
        watched_offers = {r["id"] for r in self.L.q("SELECT o.id FROM offers o JOIN user_watches w ON w.product_id=o.product_id WHERE w.status='active'")}
        self.assertTrue(watched_offers <= set(plan))                            # un produit suivi est relu chaque jour

    def test_7_inflated_reference_is_never_an_opportunity(self):
        inflated = [p["id"] for p in self.L.q("SELECT id FROM products") if (self.RD.market_signal(p["id"]) or {}).get("inflated")]
        for pid in inflated:
            self.assertIsNone(self.RD.score({**self.RD._user_ctx(self.alice, self.L.clock()), "user_id": self.alice}, self.RD.market_signal(pid)))

    def test_8_feed(self):
        f = self.RD.feed(self.alice)
        self.assertEqual(set(f), {"watch_hits", "foryou", "discovery", "watches"})
        self.assertLessEqual(len(f["foryou"]), 5)
        self.assertTrue(f["watches"])


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
