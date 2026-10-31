"""Missions (missions.py) : vos recherches sauvegardées, que Deals surveille ; « je veux un aspirateur balai sous 300 €,
préviens-moi ».

Ce que le produit promet : une phrase suffit ; rien n'est deviné (ce qui n'est pas dit n'est pas exigé, ce qui est dit
l'est) ; un produit ne remplit une mission que s'il est disponible, au prix voulu et conforme ; le prix est facultatif
(sans lui, la mission suit les nouveautés) ; l'app dit ce qui est nouveau depuis le dernier regard ; la nuit, un e-mail par
personne qui a donné son adresse et laissé l'alerte, jamais deux fois le même produit au même prix, rien pour ce qu'elle
voyait déjà. Depuis une fiche, « tout produit comparable » garde la catégorie, les fonctions et la taille ; une cible,
une mission.
"""
import json
import tempfile
import unittest
from pathlib import Path

from deals.catalog import Catalog
from deals.errors import BadRequest, NotFound
from deals.extract import attributes, categorize
from deals.missions import Missions, interpret, label, like, matches, normalize
from deals.accounts import Outbox
from deals.store import Store

BRANDS = ["Zephyr", "Kessler", "Dormea"]


def product(title, price, stock=True, brand=None, pid=1):
    cat = categorize(title)[0]
    return {"product_id": pid, "category": cat, "brand": brand, "price": price, "in_stock": stock, "attrs": attributes(title, None, cat)}


class Interpret(unittest.TestCase):
    def test_one_sentence(self):
        m = interpret("Je veux un aspirateur balai sans fil à moins de 300 euros", BRANDS)
        self.assertEqual((m["domain"], m["sub"], m["props"], m["max_price"]), ("aspirateurs", "balai", {"cordless": True}, 300))
        self.assertEqual(label(m), "Aspirateur balai sans fil · 300 € max")
        self.assertEqual(label(interpret("aspirateur traîneau avec sac", BRANDS)), "Aspirateur traîneau avec sac")
        m = interpret("lave-linge 9 kg moins de 500 €", BRANDS)
        self.assertEqual((m["domain"], m["attrs"], m["max_price"]), ("lave_linge", {"capacity_kg": 9}, 500))   # v59 : chaque rayon
        m = interpret("un lit 160x200 jusqu'à 1 200€", BRANDS)
        self.assertEqual((m["domain"], m["attrs"], m["max_price"]), ("lit", {"bed_size": "160x200"}, 1200))
        self.assertEqual(interpret("un lit sous 500", BRANDS)["domain"], "lit")                       # le mot courant suffit
        m = interpret("TV OLED 55 pouces sous 1 200 €", BRANDS)                                       # v59 : l'électronique
        self.assertEqual((m["domain"], m["sub"], m["attrs"], m["max_price"]), ("televiseur", "oled", {"screen_in": 55}, 1200))
        self.assertEqual(label(m), "Téléviseur OLED 55 pouces · 1 200 € max")
        self.assertEqual(label(interpret("smartphone 5G 256 Go", BRANDS)), "Smartphone 5G 256 Go")
        self.assertEqual(label(interpret("frigo no frost 300 L", BRANDS)), "Réfrigérateur No Frost 300 L")   # un nom garde ses majuscules
        self.assertEqual(label(interpret("écouteurs sans réduction de bruit", BRANDS)), "Écouteurs sans réduction de bruit")
        self.assertEqual(label(interpret("console de salon édition numérique 1 To", BRANDS)), "Console de salon édition numérique 1 To")
        m = interpret("matelas Dormea 160x200", BRANDS)
        self.assertEqual((m["brand"], m["max_price"]), ("Dormea", None))                               # le prix se demande après
        self.assertEqual(label(interpret("Zephyr sous 400 €", BRANDS)), "Zephyr · 400 € max")

    def test_everyday_wording(self):
        m = interpret("aspi sans fil 250 balles", BRANDS)
        self.assertEqual((m["domain"], m["props"], m["max_price"]), ("aspirateurs", {"cordless": True}, 250))
        self.assertEqual(interpret("matelas 160 sur 200", BRANDS)["attrs"], {"bed_size": "160x200"})
        self.assertEqual(interpret("lit 2 places sous 400", BRANDS)["attrs"], {})                      # pas des places assises
        self.assertEqual(interpret("canapé 3 places", BRANDS)["attrs"], {"seats": 3})
        self.assertEqual(interpret("meuble télé sous 200 €", BRANDS)["domain"], "meuble_tv")
        self.assertIsNone(interpret("réfrigérateur sous 0 €", BRANDS)["max_price"])                   # impossible : demandé
        self.assertIsNone(interpret("aspirateur sous 300 000 €", BRANDS)["max_price"])
        self.assertEqual(interpret("télé 139 cm sous 500", BRANDS)["attrs"], {"screen_in": 55})       # la diagonale en centimètres
        with self.assertRaisesRegex(BadRequest, "pas encore suivis"):
            interpret("micro-ondes sous 150 €", BRANDS)

    def test_refused(self):
        with self.assertRaises(BadRequest):
            interpret("machine à café sous 300 €", BRANDS)        # pas suivi : on le dit, plutôt qu'une mission vaine
        with self.assertRaises(BadRequest):
            interpret("quelque chose de joli", BRANDS)


class Matches(unittest.TestCase):
    def test_what_is_said_is_required(self):
        m = interpret("aspirateur balai sans fil sous 300 €")
        self.assertTrue(matches(m, product("Aspirateur balai sans fil Flex 45 min", 242)))
        self.assertFalse(matches(m, product("Aspirateur balai sans fil Flex 45 min", 301)))            # trop cher
        self.assertFalse(matches(m, product("Aspirateur balai sans fil Flex 45 min", 242, stock=False)))
        self.assertFalse(matches(m, product("Aspirateur traîneau sans sac 750 W", 199)))               # pas balai
        self.assertFalse(matches(m, product("Robot aspirateur laveur S8", 199)))                       # un robot n'est pas un balai
        self.assertTrue(matches(interpret("aspirateur sans fil"), product("Robot aspirateur laveur S8", 199)))   # sans fil : déduit du type
        m = interpret("aspirateur traîneau sans sac")
        self.assertTrue(matches(m, product("Aspirateur traîneau sans sac 750 W", 199)))
        self.assertFalse(matches(m, product("Aspirateur traîneau avec sac 750 W", 199)))
        self.assertFalse(matches(m, product("Aspirateur traîneau 750 W", 199)))                       # rien ne le dit : pas promis
        self.assertTrue(matches(interpret("aspirateur sans sac"), product("Aspirateur balai Flex", 199)))   # un balai : sans sac par définition
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
        flex = {**product("Aspirateur balai sans fil Flex 45 min", 242), "search": " aspirateur balai sans fil flex kessler "}
        self.assertEqual([matches({"category": "aspirateur", "words": w}, flex) for w in (["flex"], ["fle"], ["v8"])], [True, True, False])

    def test_comparable_keeps_kind_functions_and_size(self):
        self.assertEqual(like(product("Aspirateur balai sans fil Flex 45 min", 279)),
                         {"category": "aspirateur", "features": [], "attrs": {}, "domain": "aspirateurs", "sub": "balai",
                          "props": {"cordless": True}})                                               # l'autonomie n'en est pas
        self.assertEqual(like(product("Lave-linge hublot 9 kg classe A 1400 tr/min", 499)),
                         {"category": "lave_linge", "features": [], "attrs": {"capacity_kg": 9}, "domain": "lave_linge", "sub": "hublot",
                          "props": {}})                                                               # ni la classe énergie
        tv = {**like(product("TV OLED 55\" 4K 120 Hz", 1290)), "max_price": 1100}                     # v59 : même type, même écran
        self.assertTrue(matches(tv, product("TV OLED 139 cm 4K Ultra HD", 1090)))
        self.assertFalse(matches(tv, product("TV QLED 55 pouces 4K", 549)))
        self.assertFalse(matches(tv, product("TV OLED 65 pouces 4K", 1090)))
        hand = normalize(like(product("Aspirateur Brava X5", 199)))                                   # type non dit : son rayon, pas les robots
        self.assertEqual((hand["category"], hand["domain"], hand["sub"]), ("aspirateur", "aspirateurs", None))
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
            c.execute("INSERT OR REPLACE INTO catalog(product_id, name, title, brand, category, price, search, published_on, attrs, offer_id) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?)", (pid, title, title, brand, categorize(title)[0], price, " x ", "2026-10-24",
                                                     json.dumps(attributes(title, None, categorize(title)[0])), 100 + pid))   # comme publiés
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
        self.assertIn(f"https://deals.test/?p=2&from=mail&m={mission['id']}", body)                  # la fiche…
        self.assertIn(f"Voir l'offre : https://deals.test/api/r/out/102?from=mail&m={mission['id']}", body)   # …ou l'offre, en un clic
        self.assertIn("Deals touche une commission, sans surcoût pour vous", body)                     # liens partenaires : dit
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
        self.assertEqual(self.m.notify(box, "https://deals.test", limit=1), {"missions": 2, "emails": 1, "products": 1, "deferred": 1, "failed": 0})
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

    def test_a_search_kept_before_the_ontology_is_read_as_today(self):
        """v56 gardait « aspirateur balai sans fil » en rayon et fonctions : relue comme la même phrase aujourd'hui, une
        fois réécrite, et la même recherche gardée avant et après n'en fait qu'une."""
        self.assertEqual(normalize({"category": "aspirateur", "features": ["balai", "sans_fil"], "attrs": {}}),
                         {"category": None, "features": [], "attrs": {}, "domain": "aspirateurs", "sub": "balai", "props": {"cordless": True}})
        self.assertEqual(normalize({"category": "robot_aspirateur", "features": ["laveur"]}),                      # un robot qui lave : un robot
                         {"category": None, "features": [], "attrs": {}, "domain": "aspirateurs", "sub": "robot", "props": {}})
        self.assertEqual(normalize({"domain": "aspirateurs", "sub": "robot", "needs": ["lavage"], "props": {"auto_empty": True, "cordless": True}}),
                         {"category": None, "features": [], "attrs": {}, "domain": "aspirateurs", "sub": "robot", "props": {"cordless": True}})   # la v57 : oubliés
        self.assertEqual(normalize({"category": "aspirateur", "features": ["balai", "laveur"]})["sub"], "laveur")    # un balai laveur
        self.assertEqual(normalize({"category": "lave_linge", "attrs": {"capacity_kg": 9}}),                     # v59 : chaque rayon
                         {"category": None, "features": [], "attrs": {"capacity_kg": 9}, "domain": "lave_linge", "sub": None, "props": {}})
        self.assertEqual(normalize({"category": "canape", "features": ["angle", "convertible"], "attrs": {"seats": 3}}),
                         {"category": None, "features": [], "attrs": {"seats": 3}, "domain": "canape", "sub": "angle",
                          "props": {"convertible": True}})                                          # v56 : « canapé d'angle convertible »
        self.assertEqual(normalize({"category": "refrigerateur", "features": ["americain"]})["sub"], "americain")
        self.assertEqual(normalize({"product_id": 3, "category": "aspirateur"}), {"product_id": 3, "category": "aspirateur"})   # un produit précis
        with self.s.tx() as c:
            c.execute("INSERT INTO missions(user_id, category, want, max_price, label, created_at) VALUES (?,?,?,?,?,?)",
                      (self.uid, "aspirateur", json.dumps({"attrs": {}, "features": ["balai", "sans_fil"]}), 300, "Aspirateur balai sans fil · 300 € max", 1))
        made = self.m.create(self.uid, {"domain": "aspirateurs", "sub": "balai", "props": {"cordless": True}, "max_price": 300})   # la même, d'aujourd'hui
        self.assertEqual(made["id"], 1)                                                               # reconnue : pas une seconde
        views = self.m.list(self.uid)["missions"]
        self.assertEqual([(v["domain"], v["sub"], v["props"], v["total"]) for v in views], [("aspirateurs", "balai", {"cordless": True}, 1)])
        self.assertEqual(self.s.q("SELECT category, want FROM missions", one=True)["category"], None)                 # réécrite une fois

    def test_a_domain_mission_reads_only_its_domain_and_checks_its_type(self):
        self.put(9, "Lave-linge hublot 9 kg", "Kessler", 279)
        self.assertEqual({r["category"] for r in self.m._rows({"domain": "aspirateurs"})}, {"aspirateur"})
        with self.assertRaises(BadRequest):
            self.m.create(self.uid, {"domain": "aspirateurs", "sub": "fusee"})

    def test_a_person_manages_her_missions(self):
        self.assertEqual(self.m.list(self.uid), {"missions": [], "reached": 0, "fresh": 0})
        self.assertEqual(self.m.list(None), {"missions": [], "reached": 0, "fresh": 0})              # sans compte : rien
        a = self.m.create(self.uid, {"product_id": 2, "max_price": 350})                              # ce produit, sous 350 €
        self.assertEqual((a["label"], a["total"], a["nearest"]["price"]), ("Zephyr Aspirateur balai sans fil V8 40 min · 350 € max", 0, 399))
        b = self.m.create(self.uid, {"category": "aspirateur"})                                       # sans prix : une recherche gardée
        self.assertEqual((b["label"], b["total"], b["reached"], b["fresh"], b["nearest"]), ("Aspirateur", 3, False, 0, None))
        for bad in ({}, {"category": "micro_ondes", "max_price": 300}, {"category": "aspirateur", "off": 95}, {"words": "x"},
                    {"domain": "televiseur", "props": {"screen_in": True}}):                          # une mesure n'est pas un oui/non
            with self.assertRaises(BadRequest):
                self.m.create(self.uid, bad)
        listed = self.m.list(self.uid)
        self.assertEqual(([v["id"] for v in listed["missions"]], listed["reached"]), ([b["id"], a["id"]], 0))
        self.m.remove(self.uid, a["id"])
        self.assertEqual([v["id"] for v in self.m.list(self.uid)["missions"]], [b["id"]])
        bob = self.s.x("INSERT INTO users(email, created_at) VALUES ('bob@test.local', 0)")
        for act in (lambda: self.m.remove(bob, b["id"]), lambda: self.m.seen(bob, b["id"]), lambda: self.m.alert(None, b["id"], False)):
            with self.assertRaises(NotFound):                                                         # chacun les siennes
                act()

    def test_a_saved_search_says_what_is_new_since_the_last_look(self):
        s = self.m.create(self.uid, {"category": "aspirateur", "features": ["balai"]})
        self.assertEqual((s["total"], s["fresh"]), (2, 0))                                            # ce qu'elle voyait déjà
        self.put(4, "Aspirateur balai sans fil Agile 30 min", "Helio", 179)                          # un nouveau balai
        self.put(1, "Aspirateur balai sans fil Flex 45 min", "Kessler", 259)                          # et une baisse
        self.put(3, "Aspirateur traîneau sans sac 750 W", "Ostra", 149)                               # pas un balai : rien
        mine = self.m.list(self.uid)
        self.assertEqual((mine["missions"][0]["fresh"], mine["fresh"]), (2, 1))
        self.m.seen(self.uid, s["id"])                                                                # ouverte : plus nouveau
        self.assertEqual(self.m.list(self.uid)["missions"][0]["fresh"], 0)

    def test_words_promo_low_price_and_floor(self):
        with self.s.tx() as c:
            c.execute("UPDATE catalog SET search=' aspirateur balai sans fil flex kessler ', pct=20 WHERE product_id=1")
            c.execute("UPDATE catalog SET search=' aspirateur balai sans fil v8 zephyr ', level='lowest', span=90, usual=480 WHERE product_id=2")
        flex = self.m.create(self.uid, {"category": "aspirateur", "words": ["Flex"]})
        self.assertEqual(([c["id"] for c in flex["matches"]], flex["label"]), ([1], "Aspirateur « flex »"))
        promo = self.m.create(self.uid, {"category": "aspirateur", "off": 10})
        self.assertEqual(([c["id"] for c in promo["matches"]], promo["label"]), ([1], "Aspirateur · −10 % et plus"))
        low = self.m.create(self.uid, {"category": "aspirateur", "low": True, "min_price": 250})
        self.assertEqual(([c["id"] for c in low["matches"]], low["label"]), ([2], "Aspirateur · prix bas · dès 250 €"))
        self.assertEqual(self.m.create(self.uid, {"category": "aspirateur", "words": ["flex"]})["id"], flex["id"])   # la même recherche

    def test_what_is_asked_is_kept(self):
        with self.s.tx() as c:
            c.execute("UPDATE catalog SET search=' aspirateur balai sans fil flex kessler ' WHERE product_id=1")
        floor = self.m.create(self.uid, {"category": "aspirateur", "min_price": 250})                # dès 250 € : pas le traîneau à 199 €
        self.assertEqual(sorted(c["id"] for c in floor["matches"]), [1, 2])
        upside = self.m.create(self.uid, {"category": "aspirateur", "min_price": 500, "max_price": 300})   # à l'envers : le plancher tombe
        self.assertEqual((upside["label"], upside["total"]), ("Aspirateur · 300 € max", 2))
        both = self.m.create(self.uid, {"category": "aspirateur", "room": "salon"})                 # le rayon nommé l'emporte sur la pièce
        self.assertEqual((both["room"], both["total"]), (None, 3))
        self.assertEqual(self.m.create(self.uid, {"words": ["flex"]})["total"], 1)                     # des mots seulement
        self.assertEqual(self.m.create(self.uid, {"words": ["fle"]})["total"], 1)                      # le début d'un mot suffit
        salon, care = self.m.create(self.uid, {"room": "salon"}), self.m.create(self.uid, {"room": "entretien"})
        kept = {v["id"]: (v["room"], v["total"]) for v in self.m.list(self.uid)["missions"]}
        self.assertEqual((kept[salon["id"]], kept[care["id"]]), (("salon", 0), ("entretien", 3)))     # la pièce reste la pièce
        self.assertEqual(self.m.preview(self.uid, {"category": "aspirateur"})["fresh"], 0)             # un aperçu n'a rien de nouveau

    def test_saving_again_resets_what_is_new(self):
        s = self.m.create(self.uid, {"category": "aspirateur", "max_price": 300})
        again = self.m.create(self.uid, {"category": "aspirateur", "max_price": 450})                 # même recherche, autre prix
        self.assertEqual((again["id"], again["total"], again["fresh"]), (s["id"], 3, 0))               # ce qu'on voit en sauvegardant
        self.assertEqual(self.m.list(self.uid)["missions"][0]["fresh"], 0)
        self.assertEqual(self.m.notify(Outbox(), "https://deals.test")["emails"], 0)                   # ni par e-mail
        self.m.seen(self.uid, s["id"])
        self.put(2, "Aspirateur balai sans fil V8 40 min", "Zephyr", 397)                             # 2 € de moins : c'est nouveau
        self.assertEqual(self.m.list(self.uid)["missions"][0]["fresh"], 1)

    def test_an_address_given_later_does_not_mail_what_was_seen(self):
        guest = self.s.x("INSERT INTO users(email, created_at) VALUES (NULL, 0)")
        self.m.create(guest, {"category": "aspirateur", "max_price": 300})
        self.s.x("UPDATE missions SET notified='{}' WHERE user_id=?", (guest,))                      # vu dans l'app, jamais envoyé
        self.s.x("UPDATE users SET email='noe@test.local' WHERE id=?", (guest,))                     # l'adresse arrive (accounts.verify)
        self.m.caught_up(guest)
        self.assertEqual(self.m.notify(Outbox(), "https://deals.test")["emails"], 0)

    def test_the_night_mail_needs_an_address_and_the_alert(self):
        guest = self.s.x("INSERT INTO users(email, created_at) VALUES (NULL, 0)")                     # compte invité : l'app seulement
        bob = self.s.x("INSERT INTO users(email, created_at) VALUES ('bob@test.local', 0)")
        for who in (self.uid, guest, bob):
            self.m.create(who, {"category": "aspirateur", "max_price": 300})
        off = self.m.list(bob)["missions"][0]
        self.assertEqual(self.m.alert(bob, off["id"], False), {"alert": False})
        self.put(3, "Aspirateur traîneau sans sac 750 W", "Ostra", 189)
        box = Outbox()
        self.assertEqual((self.m.notify(box, "https://deals.test")["emails"], [to for to, _ in box.mails]), (1, ["mia@test.local"]))
        self.assertEqual(self.m.list(guest)["missions"][0]["fresh"], 1)                               # l'invité le voit dans l'app

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
