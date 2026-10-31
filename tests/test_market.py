"""Rapprochement prudent (lot 1, docs/PRODUCTION.md) : un produit n'en absorbe un autre que sur preuve — le même EAN, ou
la même marque et la même référence fabricant —, jamais sur la ressemblance du titre, qui fait seulement un candidat à
revoir. Disponibilité : une alerte ne promet que ce qui est dit en stock ; à prix égal, la meilleure offre est celle dont
la disponibilité est dite."""
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from deals.market import Market
from deals.missions import Missions, matches
from deals.publish import publish
from deals.store import Store

NOW = datetime(2026, 10, 31, 3, 0, tzinfo=timezone.utc).timestamp()
TODAY = date(2026, 10, 31)


class Matching(unittest.TestCase):
    def setUp(self):
        self.store = Store(str(Path(tempfile.mkdtemp()) / "t.sqlite"))
        self.m = Market(self.store, clock=lambda: NOW)

    def product(self, title, brand=None, mpn=None, gtin=None):
        with self.store.tx():
            return self.m.match_product({"title": title, "brand": brand, "mpn": mpn, "gtin": gtin, "price": 500.0})

    def review(self, pid):
        return self.store.q("SELECT needs_review FROM products WHERE id=?", (pid,), one=True)["needs_review"]

    def test_two_references_of_a_range_stay_two_products(self):
        a = self.product("Lave-linge hublot Bosch Série 6 WGG244Z0FR 9 kg 1400 tours classe A", "Bosch", "WGG244Z0FR")
        b = self.product("Lave-linge hublot Bosch Série 6 WGG244Z1FR 9 kg 1400 tours classe A", "Bosch", "WGG244Z1FR")
        self.assertNotEqual(a, b)
        self.assertEqual(self.review(a), 0)                    # le premier n'avait pas de semblable
        self.assertEqual(self.review(b), 1)                    # le second rappelle le premier : à revoir
        self.assertEqual(self.m.candidates(b), [(a, 0.86)])

    def test_similar_titles_without_brand_nor_reference_are_never_merged(self):
        c = self.product("Canapé d'angle convertible réversible Oslo 5 places tissu chiné gris anthracite")
        d = self.product("Canapé d'angle convertible réversible Oslo 5 places tissu chiné beige anthracite")
        self.assertNotEqual(c, d)
        self.assertEqual((self.review(c), self.review(d)), (1, 1))

    def test_same_reference_joins_and_learns_the_ean(self):
        a = self.product("Réfrigérateur Brava R60 No Frost", "Brava", "R60")
        b = self.product("Brava R60 réfrigérateur combiné 331 L", "brava", "r60", "3700000000017")
        self.assertEqual(a, b)
        self.assertEqual(self.store.q("SELECT gtin FROM products WHERE id=?", (a,), one=True)["gtin"], "3700000000017")

    def test_same_reference_but_two_eans_are_two_products(self):
        a = self.product("Réfrigérateur Brava R60 blanc", "Brava", "R60", "3700000000017")
        b = self.product("Réfrigérateur Brava R60 noir", "Brava", "R60", "3700000000024")
        self.assertNotEqual(a, b)

    def test_same_ean_joins_whatever_the_title(self):
        a = self.product("TV QLED Samsung QE55Q60D", "Samsung", None, "8806095000000")
        b = self.product("Samsung Q60D 138 cm 4K", "Samsung", None, "8806095000000")
        self.assertEqual(a, b)


class Availability(unittest.TestCase):
    def setUp(self):
        self.store = Store(str(Path(tempfile.mkdtemp()) / "t.sqlite"))
        self.m = Market(self.store, clock=lambda: NOW)

    def offer(self, url, merchant, price, availability, gtin="3000000000017"):
        with self.store.tx():
            oid = self.m.track(url, merchant.lower(), merchant)
            self.m.record(self.m.offer(oid), {"title": "Lave-linge hublot Kessler WM8 8 kg 1400 tr/min classe A", "brand": "Kessler",
                                              "gtin": gtin, "price": price, "availability": availability, "category": "Lave-linge"})
        return oid

    def best(self):
        return self.store.q("SELECT offer_id, availability FROM catalog_offers WHERE rank=0", one=True)

    def alert_fires(self):
        rows = Missions._rows(SimpleNamespace(s=self.store), {"category": "lave_linge"})
        return bool(rows) and matches({"category": "lave_linge", "max_price": 600}, Missions._product(rows[0]))

    def test_unknown_availability_is_not_promised(self):
        self.offer("https://a.example/p/1", "Alpha", 549.0, "unknown")
        publish(self.store, TODAY, NOW)
        self.assertEqual(self.best()["availability"], "unknown")       # l'offre est montrée…
        self.assertFalse(self.alert_fires())                            # …mais aucune alerte ne la promet disponible

    def test_in_stock_is_promised(self):
        self.offer("https://a.example/p/1", "Alpha", 549.0, "in_stock")
        publish(self.store, TODAY, NOW)
        self.assertTrue(self.alert_fires())

    def test_preorder_is_not_promised(self):
        self.offer("https://a.example/p/1", "Alpha", 549.0, "preorder")
        publish(self.store, TODAY, NOW)
        self.assertFalse(self.alert_fires())

    def test_known_availability_wins_at_equal_price(self):
        unknown = self.offer("https://a.example/p/1", "Alpha", 549.0, "unknown")
        known = self.offer("https://b.example/p/1", "Beta", 549.0, "in_stock")
        self.assertLess(unknown, known)                                 # sans la règle, la plus ancienne gagnait
        publish(self.store, TODAY, NOW)
        self.assertEqual(self.best()["offer_id"], known)

    def test_a_cheaper_offer_still_wins_over_availability(self):
        cheaper = self.offer("https://a.example/p/1", "Alpha", 529.0, "unknown")
        self.offer("https://b.example/p/1", "Beta", 549.0, "in_stock")
        publish(self.store, TODAY, NOW)
        self.assertEqual(self.best()["offer_id"], cheaper)


if __name__ == "__main__":
    unittest.main()
