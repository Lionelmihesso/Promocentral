"""Vraie ou fausse remise (judge.py) et meilleur prix quotidien (publish.daily_best) — fonctions pures."""
import unittest
from datetime import date, timedelta

from deals.judge import judge
from deals.publish import daily_best, day_start, low_days

TODAY = date(2026, 10, 18)


def days(n, price, end=TODAY - timedelta(days=1)):
    """n jours consécutifs au même prix, finissant `end`."""
    return [(end - timedelta(days=n - 1 - i), price) for i in range(n)]


class Judge(unittest.TestCase):
    def test_no_strike_price_no_deal(self):
        self.assertFalse(judge(500, None, [], TODAY).deal)
        self.assertFalse(judge(500, 503, [], TODAY).deal)               # moins de 1 % : pas une remise

    def test_without_evidence_the_retailer_is_believed(self):
        v = judge(529.99, 879.99, [], TODAY)                              # premier jour, aucun historique
        self.assertEqual((v.deal, v.pct, v.was, v.verified), (True, 40, 879.99, False))
        v = judge(529.99, 879.99, days(10, 879.99), TODAY)                # 10 jours seulement : pas encore une preuve
        self.assertTrue(v.deal and not v.verified)

    def test_honest_promo_is_confirmed(self):
        v = judge(850, 1000, days(30, 1000), TODAY)
        self.assertEqual((v.deal, v.pct, v.verified), (True, 15, True))

    def test_inflated_strike_price_is_fake(self):
        history = days(76, 1000, TODAY - timedelta(days=15)) + days(14, 1300)   # prix gonflé 14 jours, puis « -23 % »
        v = judge(1000, 1300, history, TODAY)
        self.assertFalse(v.deal)
        self.assertIn("fausse remise", v.reason)

    def test_big_real_deal_survives_an_exaggerated_display(self):
        v = judge(650, 1500, days(30, 1000), TODAY)                       # affichée -57 %, réelle -35 % : gros deal quand même
        self.assertTrue(v.deal and v.verified)

    def test_permanent_strike_price_is_the_price(self):
        self.assertFalse(judge(499, 999, days(60, 499), TODAY).deal)       # « -50 % » depuis deux mois
        self.assertTrue(judge(499, 999, days(59, 499), TODAY).deal)        # 59 jours : on ne sait pas encore

    def test_legal_lowest_30_days_is_evidence(self):
        self.assertFalse(judge(600, 800, [], TODAY, lowest_30d=600).deal)  # pas sous son propre plus bas 30 jours
        self.assertTrue(judge(600, 800, [], TODAY, lowest_30d=790).verified)

    def test_verdict_carries_its_proof(self):                              # ce que la fiche explique
        v = judge(850, 1000, days(30, 1000), TODAY)
        self.assertEqual((v.proof, v.ref), ("historique", 1000))
        v = judge(600, 800, [], TODAY, lowest_30d=790)
        self.assertEqual((v.proof, v.ref), ("plus_bas_30j", 790))
        self.assertEqual(judge(529.99, 879.99, [], TODAY).proof, "")       # crue sans preuve : rien à montrer

    def test_promo_started_days_ago_is_judged_against_before(self):
        history = days(20, 1000, TODAY - timedelta(days=6)) + days(5, 800)   # promo commencée il y a 5 jours
        self.assertTrue(judge(800, 1000, history, TODAY).verified)


class DailyBest(unittest.TestCase):
    def test_best_available_price_per_day(self):
        d0 = TODAY - timedelta(days=5)
        t = lambda k, h=10: day_start(d0 + timedelta(days=k)) + h * 3600
        a = [{"first_seen": t(0), "last_seen": t(2), "price": 500, "availability": "in_stock"},
             {"first_seen": t(3), "last_seen": t(5), "price": 450, "availability": "in_stock"}]
        b = [{"first_seen": t(0), "last_seen": t(5), "price": 480, "availability": "out_of_stock"}]
        self.assertEqual(daily_best([a, b], d0, TODAY), [(d0 + timedelta(days=k), p) for k, p in
                                                       [(0, 500), (1, 500), (2, 500), (3, 450), (4, 450), (5, 450)]])

    def test_lowest_price_streak(self):                                   # « prix le plus bas relevé depuis n jours »
        h = [(TODAY - timedelta(days=k), 500) for k in range(20, 0, -1)]
        self.assertEqual(low_days(h, 450, TODAY), 20)
        h[-8] = (h[-8][0], 440)                                           # 440 € il y a 8 jours
        self.assertEqual(low_days(h, 450, TODAY), 7)
        self.assertEqual(low_days([], 450, TODAY), 0)

    def test_stale_prices_stop_counting(self):
        d0 = TODAY - timedelta(days=10)
        a = [{"first_seen": day_start(d0) + 3600, "last_seen": day_start(d0) + 3600, "price": 500, "availability": "in_stock"}]
        self.assertEqual([d for d, _ in daily_best([a], d0, TODAY)], [d0 + timedelta(days=k) for k in range(4)])   # 3 jours de tolérance


if __name__ == "__main__":
    unittest.main()
