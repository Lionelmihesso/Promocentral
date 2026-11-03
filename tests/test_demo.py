"""La démo nourrie par des flux : les enseignes simulées donnent leur flux produits (XML Google Shopping, CSV à la
française), lu par le connecteur de flux, comme une enseigne partenaire. v63 : le catalogue publié était exactement celui
de la lecture de leurs fiches (la preuve que les flux nourrissent l'app sans rien changer de ce qu'elle montre) ; v68 :
les fiches ne sont plus lues, les flux seuls nourrissent l'app."""
import tempfile
import unittest
from pathlib import Path

from deals import demo
from deals.store import Store


class FeedsFeedTheApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = Store(str(Path(tempfile.mkdtemp()) / "demo.sqlite"))
        demo.build(cls.s, nights=24, partners=set(demo.RULES))

    @classmethod
    def tearDownClass(cls):
        cls.s.close()

    def test_the_catalog_is_published_from_the_feeds(self):
        self.assertEqual(self.s.q("SELECT COUNT(*) n FROM products", one=True)["n"], 127)
        for table in ("catalog", "catalog_offers", "alternatives", "similar"):
            self.assertTrue(self.s.q(f"SELECT 1 FROM {table} LIMIT 1"), table)
        self.assertEqual(self.s.q("SELECT COUNT(*) n FROM catalog_offers", one=True)["n"], 3 * 127)   # trois enseignes par produit

    def test_every_price_says_it_comes_from_a_feed_batch(self):
        self.assertEqual({r["source"] for r in self.s.q("SELECT DISTINCT source FROM prices")}, {"feed:xml", "feed:csv"})
        self.assertFalse(self.s.q("SELECT 1 FROM prices WHERE batch_id IS NULL"))

    def test_every_night_leaves_one_batch_per_source(self):
        rows = self.s.q("SELECT source, kind, COUNT(*) n, SUM(status='succeeded') ok FROM batches GROUP BY source, kind")
        self.assertEqual({(r["source"], r["kind"]): (r["n"], r["ok"]) for r in rows}, {(k, "feed"): (25, 25) for k in demo.RULES})
        self.assertEqual({r["kind"] for r in self.s.q("SELECT kind FROM sources")}, {"feed"})


if __name__ == "__main__":
    unittest.main()
