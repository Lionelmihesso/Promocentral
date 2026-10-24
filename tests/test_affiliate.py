"""Affiliation (affiliate.py, activity.py) : seules les enseignes partenaires sont montrées, chaque clic part par leur lien
affilié avec son identifiant (la vente que le réseau rapporte se rattache au clic), et la conversion se lit par écran et
selon la personne : fiches vues, clics vers l'enseigne, taux de clic, part des clics rémunérables, clics des missions.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from deals import affiliate, cli
from deals.activity import Activity
from deals.errors import BadRequest, NotFound
from deals.store import Store

AWIN = "https://www.awin1.com/cread.php?awinmid=1234&awinaffid=5678&clickref={subid}&ued={url}"


class Link(unittest.TestCase):
    def test_network_template(self):
        self.assertEqual(affiliate.link("https://www.shop.fr/p/12?coloris=gris", AWIN, 42),
                         "https://www.awin1.com/cread.php?awinmid=1234&awinaffid=5678&clickref=42"
                         "&ued=https%3A%2F%2Fwww.shop.fr%2Fp%2F12%3Fcoloris%3Dgris")

    def test_parameters_added_to_the_page(self):
        self.assertEqual(affiliate.link("https://www.shop.fr/p/12", "tag=deals-21&sub={subid}", 7), "https://www.shop.fr/p/12?tag=deals-21&sub=7")
        self.assertEqual(affiliate.link("https://www.shop.fr/p/12?c=1", "?tag=deals-21", 7), "https://www.shop.fr/p/12?c=1&tag=deals-21")
        self.assertEqual(affiliate.link("https://www.shop.fr/p/12#avis", "sub={subid}", 7), "https://www.shop.fr/p/12?sub=7#avis")

    def test_no_rule_no_link(self):
        self.assertIsNone(affiliate.link("https://www.shop.fr/p/12", None, 7))
        self.assertIsNone(affiliate.link("https://www.shop.fr/p/12", "", 7))

    def test_rules_file(self):
        d = Path(tempfile.mkdtemp())
        (d / "ok.json").write_text(json.dumps({"boulanger": AWIN, "but": "tag=x"}))
        self.assertEqual(affiliate.load(str(d / "ok.json")), {"boulanger": AWIN, "but": "tag=x"})
        self.assertIsNone(affiliate.load(""))                                     # développement : aucun filtre
        for bad in ("[1, 2]", "{}", '{"but": ""}', '{"but": 3}', "pas du json"):
            (d / "bad.json").write_text(bad)
            with self.assertRaises(ValueError, msg=bad):
                affiliate.load(str(d / "bad.json"))
        with self.assertRaises(ValueError):
            affiliate.load(str(d / "absent.json"))


class Clicks(unittest.TestCase):
    def setUp(self):
        self.s = Store(Path(tempfile.mkdtemp(), "a.sqlite"))
        with self.s.tx() as c:
            for oid, retailer, url in [(1, "boulanger", "https://www.boulanger.com/ref/1"), (2, "ikea", "https://www.ikea.com/fr/fr/p/2")]:
                c.execute("INSERT INTO products(id, title, created_at) VALUES (?, 'P', 0)", (oid,))
                c.execute("INSERT INTO offers(id, url, host, retailer, merchant, product_id, created_at) VALUES (?,?,?,?,?,?,0)",
                          (oid, url, url.split("/")[2], retailer, retailer.title(), oid))
                c.execute("INSERT INTO catalog(product_id, name, title, brand, category, price, pct, search, published_on, attrs) "
                          "VALUES (?,?,?,?,?,?,?,?,?,?)", (oid, "P", "P", "B", "lave_linge", 400, 0, " p ", "2026-10-24", "{}"))
            self.uid = c.execute("INSERT INTO users(email, created_at) VALUES ('mia@test.local', 0)").lastrowid
            self.bob = c.execute("INSERT INTO users(email, created_at) VALUES ('bob@test.local', 0)").lastrowid
            c.execute("INSERT INTO missions(user_id, category, want, max_price, label, created_at) VALUES (?, 'lave_linge', '{}', 500, 'L', 0)",
                      (self.uid,))

    def tearDown(self):
        self.s.close()

    def last(self):
        return self.s.q("SELECT * FROM clicks ORDER BY id DESC LIMIT 1", one=True)

    def test_a_partner_click_leaves_with_its_id(self):
        a = Activity(self.s, clock=lambda: 1_790_000_000, rules={"boulanger": AWIN})
        self.assertEqual(a.click(None, 2, "pirate", "x"), "https://www.ikea.com/fr/fr/p/2")       # pas partenaire : lien direct
        self.assertEqual((self.last()["partner"], self.last()["source"], self.last()["mission_id"]), (0, None, None))
        url = a.click(self.uid, 1, "mail", "9")
        c = self.last()
        self.assertEqual((c["id"], url), (2, affiliate.link("https://www.boulanger.com/ref/1", AWIN, 2)))   # l'identifiant du clic part
        self.assertEqual((c["partner"], c["source"], c["mission_id"], c["user_id"]), (1, "mail", 9, self.uid))
        dev = Activity(self.s)                                                                     # sans règles : développement
        self.assertEqual(dev.click(None, 1, "item"), "https://www.boulanger.com/ref/1")
        self.assertIsNone(self.last()["partner"])
        with self.assertRaises(NotFound):
            a.click(None, 99, "item")

    def test_conversion_by_screen_and_by_person(self):
        a = Activity(self.s, rules={"boulanger": AWIN})
        for uid, source in [(self.uid, "mail"), (self.uid, "mail"), (self.bob, "search"), (None, "search"), (None, "feed")]:
            a.view(uid, {"product_id": 1, "from": source, "m": "4" if source == "mail" else None})
        a.click(self.uid, 1, "mail", "4")
        a.click(None, 1, "search")
        a.click(None, 2, "search")
        Activity(self.s).click(None, 1, "item")                                     # sans règles (développement), sans fiche vue
        m = a.metrics()
        self.assertEqual(m["by_source"]["item"], {"views": 0, "clicks": 1, "ctr": None})
        self.assertEqual(m["by_source"]["mail"], {"views": 2, "clicks": 1, "ctr": 0.5})
        self.assertEqual(m["by_source"]["search"], {"views": 2, "clicks": 2, "ctr": 1.0})
        self.assertEqual(m["by_source"]["feed"], {"views": 1, "clicks": 0, "ctr": 0.0})
        self.assertEqual(m["by_person"]["avec mission"], {"views": 2, "clicks": 1, "ctr": 0.5})
        self.assertEqual(m["by_person"]["connecté, sans mission"], {"views": 1, "clicks": 0, "ctr": 0.0})
        self.assertEqual(m["by_person"]["sans compte"], {"views": 2, "clicks": 3, "ctr": 1.5})
        self.assertEqual((m["partner_share"], m["from_missions"]), (0.667, {"clicks": 1, "missions": 1}))
        self.assertEqual(self.s.q("SELECT mission_id FROM views WHERE source='mail' LIMIT 1", one=True)["mission_id"], 4)

    def test_a_view_needs_a_published_product(self):
        a = Activity(self.s)
        with self.assertRaises(BadRequest):
            a.view(None, {"product_id": "x"})
        with self.assertRaises(NotFound):
            a.view(None, {"product_id": 99})


class Startup(unittest.TestCase):
    def run_cli(self, rules, *argv):
        d = Path(tempfile.mkdtemp())
        (d / "aff.json").write_text(rules)
        env = {"DEALS_AFFILIATE": str(d / "aff.json"), "DEALS_USER_AGENT": "DealsTest/1.0 (+https://t.example ; contact : t@t.example)"}
        with mock.patch.dict(os.environ, env), self.assertRaises(SystemExit) as stop:
            cli.main(["--db", str(d / "c.sqlite"), *argv])
        return str(stop.exception)

    def test_a_bad_rules_file_stops_the_start(self):
        self.assertIn("Réglage invalide : DEALS_AFFILIATE", self.run_cli('{"but": ""}', "publish"))

    def test_the_night_reads_partners_only(self):
        self.assertIn("aucune des enseignes déclarées n'est suivie", self.run_cli('{"inconnue": "tag=x"}', "nightly"))


if __name__ == "__main__":
    unittest.main()
