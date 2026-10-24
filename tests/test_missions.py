"""Missions (missions.py) : « je veux un aspirateur balai sous 300 €, préviens-moi ».

Ce que le produit promet : une phrase suffit ; rien n'est deviné (ce qui n'est pas dit n'est pas exigé, ce qui est dit
l'est) ; un produit ne remplit une mission que s'il est disponible, au prix voulu et conforme ; la nuit, un e-mail par
personne, jamais deux fois le même produit au même prix, rien pour ce qu'elle voyait déjà en lançant la mission.
Depuis une fiche, « tout produit comparable » garde la catégorie, les fonctions et la taille ; une cible, une mission.
"""
import json
import tempfile
import unittest
from pathlib import Path

from deals.catalog import Catalog
from deals.errors import BadRequest
from deals.extract import attributes, categorize
from deals.missions import Missions, interpret, label, like, matches
from deals.accounts import Outbox
from deals.store import Store

BRANDS = ["Zephyr", "Kessler", "Dormea"]


def product(title, price, stock=True, brand=None, pid=1):
    return {"product_id": pid, "category": categorize(title)[0], "brand": brand, "price": price, "in_stock": stock, "attrs": attributes(title)}


class Interpret(unittest.TestCase):
    def test_one_sentence(self):
        m = interpret("Je veux un aspirateur balai sans fil à moins de 300 euros", BRANDS)
        self.assertEqual((m["category"], m["features"], m["max_price"]), ("aspirateur", ["balai", "sans_fil"], 300))
        self.assertEqual(label(m), "Aspirateur balai sans fil · 300 € max")
        m = interpret("lave-linge 9 kg moins de 500 €", BRANDS)
        self.assertEqual((m["category"], m["attrs"], m["max_price"]), ("lave_linge", {"capacity_kg": 9}, 500))
        m = interpret("un lit 160x200 jusqu'à 1 200€", BRANDS)
        self.assertEqual((m["category"], m["attrs"], m["max_price"]), ("lit", {"bed_size": "160x200"}, 1200))
        self.assertEqual(interpret("un lit sous 500", BRANDS)["category"], "lit")                     # le mot courant suffit
        m = interpret("matelas Dormea 160x200", BRANDS)
        self.assertEqual((m["brand"], m["max_price"]), ("Dormea", None))                               # le prix se demande après
        self.assertEqual(label(interpret("Zephyr sous 400 €", BRANDS)), "Zephyr · 400 € max")

    def test_everyday_wording(self):
        m = interpret("aspi sans fil 250 balles", BRANDS)
        self.assertEqual((m["category"], m["features"], m["max_price"]), ("aspirateur", ["sans_fil"], 250))
        self.assertEqual(interpret("matelas 160 sur 200", BRANDS)["attrs"], {"bed_size": "160x200"})
        self.assertEqual(interpret("lit 2 places sous 400", BRANDS)["attrs"], {})                      # pas des places assises
        self.assertEqual(interpret("canapé 3 places", BRANDS)["attrs"], {"seats": 3})
        self.assertEqual(interpret("meuble télé sous 200 €", BRANDS)["category"], "meuble_tv")
        self.assertIsNone(interpret("réfrigérateur sous 0 €", BRANDS)["max_price"])                   # impossible : demandé
        self.assertIsNone(interpret("aspirateur sous 300 000 €", BRANDS)["max_price"])
        with self.assertRaisesRegex(BadRequest, "pas encore suivis"):
            interpret("TV 55 pouces sous 500", BRANDS)

    def test_refused(self):
        with self.assertRaises(BadRequest):
            interpret("smartphone sous 300 €", BRANDS)            # pas suivi : on le dit, plutôt qu'une mission vaine
        with self.assertRaises(BadRequest):
            interpret("quelque chose de joli", BRANDS)


class Matches(unittest.TestCase):
    def test_what_is_said_is_required(self):
        m = interpret("aspirateur balai sans fil sous 300 €")
        self.assertTrue(matches(m, product("Aspirateur balai sans fil Flex 45 min", 242)))
        self.assertFalse(matches(m, product("Aspirateur balai sans fil Flex 45 min", 301)))            # trop cher
        self.assertFalse(matches(m, product("Aspirateur balai sans fil Flex 45 min", 242, stock=False)))
        self.assertFalse(matches(m, product("Aspirateur traîneau sans sac 750 W", 199)))               # pas balai
        self.assertFalse(matches(m, product("Robot aspirateur laveur S8", 199)))                       # autre catégorie
        m = interpret("lave-linge 9 kg sous 600 €")
        self.assertTrue(matches(m, product("Lave-linge hublot 10 kg classe A", 549)))                  # au moins 9 kg
        self.assertFalse(matches(m, product("Lave-linge hublot 8 kg classe A", 449)))
        self.assertFalse(matches(m, product("Lave-linge hublot classe A", 449)))                       # capacité inconnue
        m = interpret("lave-vaisselle 60 cm classe C sous 600 €")
        self.assertTrue(matches(m, product("Lave-vaisselle 60 cm 13 couverts classe B", 449)))         # mieux que C
        self.assertFalse(matches(m, product("Lave-vaisselle 60 cm 13 couverts classe D", 349)))
        self.assertFalse(matches(m, product("Lave-vaisselle 45 cm 10 couverts classe C", 349)))
        m = interpret("Zephyr sous 400 €", BRANDS)
        self.assertTrue(matches(m, product("Aspirateur balai sans fil V8 40 min", 399, brand="Zephyr")))
        self.assertFalse(matches(m, product("Aspirateur balai sans fil V8 40 min", 399, brand="Kessler")))   # une autre marque
        self.assertTrue(matches({"product_id": 7, "max_price": 600}, product("Lave-linge 8 kg", 599, pid=7)))
        self.assertFalse(matches({"product_id": 7, "max_price": 600}, product("Lave-linge 8 kg", 599, pid=8)))

    def test_comparable_keeps_kind_functions_and_size(self):
        self.assertEqual(like(product("Aspirateur balai sans fil Flex 45 min", 279)),
                         {"category": "aspirateur", "features": ["balai", "sans_fil"], "attrs": {}})    # l'autonomie n'en est pas
        self.assertEqual(like(product("Lave-linge hublot 9 kg classe A 1400 tr/min", 499)),
                         {"category": "lave_linge", "features": [], "attrs": {"capacity_kg": 9}})      # ni la classe énergie
        self.assertEqual(like(product("Lit coffre 2 places 140x190 chêne", 499))["attrs"], {"bed_size": "140x190"})
        m = {**like(product("Lit coffre 160x200 chêne", 699)), "max_price": 600}
        self.assertTrue(matches(m, product("Lit coffre 160x200 noyer", 549)))
        self.assertFalse(matches(m, product("Lit coffre 140x190 noyer", 449)))


class Night(unittest.TestCase):
    def setUp(self):
        self.s = Store(Path(tempfile.mkdtemp(), "m.sqlite"))
        self.uid = self.s.x("INSERT INTO users(email, created_at) VALUES ('mia@test.local', 0)")
        self.m = Missions(self.s, Catalog(self.s), clock=lambda: 1000.0)
        self.night = 0
        for pid, title, brand, price in [(1, "Aspirateur balai sans fil Flex 45 min", "Kessler", 279), (2, "Aspirateur balai sans fil V8 40 min", "Zephyr", 399),
                                         (3, "Aspirateur traîneau sans sac 750 W", "Ostra", 199)]:
            self.put(pid, title, brand, price)

    def tearDown(self):
        self.s.close()

    def put(self, pid, title, brand, price, stock=True):
        with self.s.tx() as c:
            c.execute("INSERT OR REPLACE INTO catalog(product_id, name, title, brand, category, price, search, published_on, attrs) "
                      "VALUES (?,?,?,?,?,?,?,?,?)", (pid, title, title, brand, categorize(title)[0], price, " x ", "2026-10-24", json.dumps(attributes(title))))
            c.execute("INSERT OR REPLACE INTO catalog_offers(product_id, offer_id, price, availability, rank) VALUES (?,?,?,?,0)",
                      (pid, pid, price, "in_stock" if stock else "out_of_stock"))
            self.night += 1                                                                           # comme une publication
            c.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('published_at', ?)", (str(self.night),))

    def test_mail_only_for_what_is_new(self):
        mission = self.m.create(self.uid, {"category": "aspirateur", "features": ["balai"], "max_price": 300})
        self.assertEqual((mission["label"], mission["total"]), ("Aspirateur balai · 300 € max", 1))    # Kessler à 279 €, déjà visible
        box = Outbox()
        self.assertEqual(self.m.notify(box, "https://deals.test")["emails"], 0)                        # rien de neuf : pas d'e-mail
        self.put(2, "Aspirateur balai sans fil V8 40 min", "Zephyr", 289)                             # le V8 passe sous 300 €
        self.assertEqual(self.m.notify(box, "https://deals.test")["emails"], 1)
        to, msg = box.mails[-1]
        body = msg.get_body(("plain",)).get_content()
        self.assertEqual((to, msg["Subject"]), ("mia@test.local", "Mission accomplie : Aspirateur balai · 300 € max"))
        self.assertIn("Zephyr, Aspirateur balai sans fil V8 40 min : 289 €", body)
        self.assertIn("https://deals.test/?p=2", body)
        self.assertNotIn("Kessler", body)
        self.assertEqual(self.m.notify(box, "https://deals.test")["emails"], 0)                        # pas deux fois au même prix
        self.put(2, "Aspirateur balai sans fil V8 40 min", "Zephyr", 349)                             # remonte…
        self.m.notify(box, "https://deals.test")
        self.put(2, "Aspirateur balai sans fil V8 40 min", "Zephyr", 289)                             # …et revient au même prix
        self.assertEqual(self.m.notify(box, "https://deals.test")["emails"], 0)
        self.put(1, "Aspirateur balai sans fil Flex 45 min", "Kessler", 249)                          # plus bas qu'annoncé
        self.assertEqual(self.m.notify(box, "https://deals.test")["products"], 1)

    def test_the_quota_defers_to_the_next_night(self):
        bob = self.s.x("INSERT INTO users(email, created_at) VALUES ('bob@test.local', 0)")
        self.m.create(self.uid, {"category": "aspirateur", "max_price": 300})
        self.m.create(bob, {"category": "aspirateur", "max_price": 300})
        self.put(3, "Aspirateur traîneau sans sac 750 W", "Ostra", 189)                               # baisse : nouveau pour les deux
        box = Outbox()
        self.assertEqual(self.m.notify(box, "https://deals.test", limit=1), {"missions": 2, "emails": 1, "products": 1, "deferred": 1})
        night2 = self.m.notify(box, "https://deals.test", limit=1)                                    # le reste part ensuite
        self.assertEqual((night2["emails"], night2["deferred"], box.mails[-1][0]), (1, 0, "bob@test.local"))

    def test_a_long_mail_stays_short(self):
        self.m.create(self.uid, {"category": "aspirateur", "max_price": 150})
        for pid in range(10, 18):                                                                     # huit balais à 120 €
            self.put(pid, f"Aspirateur balai sans fil M{pid} 30 min", "Ostra", 100 + pid)
        box = Outbox()
        self.assertEqual(self.m.notify(box, "https://deals.test")["products"], 8)
        body = box.mails[-1][1].get_body(("plain",)).get_content()
        self.assertEqual(body.count("/?p="), 5)                                                       # les cinq moins chers
        self.assertIn("M10 30 min : 110 €", body)
        self.assertIn("et 3 autres à votre prix", body)

    def test_a_person_manages_her_missions(self):
        self.assertEqual(self.m.list(self.uid), {"missions": [], "reached": 0})
        a = self.m.create(self.uid, {"product_id": 2, "max_price": 350})                              # ce produit, sous 350 €
        self.assertEqual((a["label"], a["total"], a["nearest"]["price"]), ("Zephyr Aspirateur balai sans fil V8 40 min · 350 € max", 0, 399))
        with self.assertRaises(BadRequest):
            self.m.create(self.uid, {"category": "aspirateur"})                                       # sans prix
        with self.assertRaises(BadRequest):
            self.m.create(self.uid, {"category": "smartphone", "max_price": 300})
        listed = self.m.list(self.uid)
        self.assertEqual(([v["id"] for v in listed["missions"]], listed["reached"]), ([a["id"]], 0))
        self.m.remove(self.uid, a["id"])
        self.assertEqual(self.m.list(self.uid)["missions"], [])

    def test_one_mission_per_target(self):
        a = self.m.create(self.uid, {"like": 1, "max_price": 300})                                    # comparable au Flex
        self.assertEqual((a["label"], a["title"], a["total"]), ("Aspirateur balai sans fil · 300 € max", "Aspirateur balai sans fil", 1))
        b = self.m.create(self.uid, {"like": 1, "max_price": 260})                                    # même cible : nouveau prix
        c = self.m.create(self.uid, {"category": "aspirateur", "features": ["sans_fil", "balai"], "max_price": 250})
        self.assertEqual((b["id"], c["id"], b["total"]), (a["id"], a["id"], 0))
        d = self.m.create(self.uid, {"product_id": 2, "max_price": 350})
        self.assertEqual(d["title"], "Zephyr Aspirateur balai sans fil V8 40 min")
        self.assertEqual(self.m.create(self.uid, {"product_id": 2, "max_price": 330})["id"], d["id"])
        listed = self.m.list(self.uid)["missions"]
        self.assertEqual(sorted((v["id"], v["max_price"]) for v in listed), [(a["id"], 250), (d["id"], 330)])
        self.put(2, "Aspirateur balai sans fil V8 40 min", "Zephyr", 319)                             # publication suivante
        self.assertEqual([v["total"] for v in self.m.list(self.uid)["missions"] if v["id"] == d["id"]], [1])


if __name__ == "__main__":
    unittest.main()
