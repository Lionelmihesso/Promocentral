"""La démo nourrie par des flux (v63) : les enseignes simulées donnent leur flux produits (XML Google Shopping, CSV à la
française), lu par le connecteur de flux ; le catalogue publié est exactement celui de la lecture de leurs fiches. C'est
la preuve que l'ingestion par flux nourrit l'app sans rien changer de ce qu'elle montre."""
import tempfile
import unittest
from pathlib import Path

from deals import demo
from deals.store import Store

def keyed(s):
    """Le contenu publié, sous les clés naturelles (EAN du produit, adresse de l'offre) : les numéros internes dépendent
    de l'ordre de lecture (les fiches sont lues site par site en parallèle, un flux ligne à ligne)."""
    ean = {r["id"]: r["gtin"] for r in s.q("SELECT id, gtin FROM products")}
    url = {r["id"]: r["url"] for r in s.q("SELECT id, url FROM offers")}
    out = {"products": sorted((r["gtin"], r["brand"], r["title"], r["category"], r["attributes"], r["needs_review"])
                              for r in s.q("SELECT * FROM products"))}
    out["catalog"] = sorted(tuple((k, ean[v] if k == "product_id" else url[v] if k == "offer_id" else v) for k, v in r.items())
                            for r in s.q("SELECT * FROM catalog"))
    out["catalog_offers"] = sorted((ean[r["product_id"]], url[r["offer_id"]], r["merchant"], r["price"], r["was"], r["pct"],
                                    r["availability"], r["rank"]) for r in s.q("SELECT * FROM catalog_offers"))
    for t in ("alternatives", "similar"):
        out[t] = sorted((ean[r["product_id"]], ean[r["other_id"]], r["rank"]) for r in s.q(f"SELECT * FROM {t}"))
    out["prices"] = sorted((url[r["offer_id"]], r["first_seen"], r["last_seen"], r["price"], r["was"], r["availability"],
                            r["valid_until"]) for r in s.q("SELECT * FROM prices"))
    return out


def built(mode):
    s = Store(str(Path(tempfile.mkdtemp()) / f"{mode}.sqlite"))
    demo.build(s, nights=24, partners=set(demo.RULES), mode=mode)
    return s


class FeedsFeedTheSameApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site, cls.feed = built("site"), built("feed")
        cls.a, cls.b = keyed(cls.site), keyed(cls.feed)

    @classmethod
    def tearDownClass(cls):
        cls.site.close()
        cls.feed.close()

    def test_the_published_catalog_is_identical(self):
        for table in ("catalog", "catalog_offers", "alternatives", "similar"):
            self.assertTrue(self.a[table], table)
            self.assertEqual(self.a[table], self.b[table], table)

    def test_products_and_their_attributes_are_identical(self):
        self.assertEqual(len(self.a["products"]), 127)
        self.assertEqual(self.a["products"], self.b["products"])

    def test_the_price_history_is_identical_but_its_provenance_says_feed(self):
        self.assertEqual(self.a["prices"], self.b["prices"])
        self.assertEqual({r["source"] for r in self.feed.q("SELECT DISTINCT source FROM prices")}, {"feed:xml", "feed:csv"})
        self.assertFalse(self.feed.q("SELECT 1 FROM prices WHERE batch_id IS NULL"))

    def test_every_night_leaves_one_batch_per_source(self):
        rows = self.feed.q("SELECT source, COUNT(*) n, SUM(status='succeeded') ok FROM batches WHERE kind='feed' GROUP BY source")
        self.assertEqual({r["source"]: (r["n"], r["ok"]) for r in rows}, {k: (25, 25) for k in demo.RULES})
        self.assertEqual({r["kind"] for r in self.feed.q("SELECT kind FROM sources")}, {"feed"})
        self.assertEqual({r["kind"] for r in self.site.q("SELECT DISTINCT kind FROM batches")}, {"site"})


if __name__ == "__main__":
    unittest.main()
