"""Comprendre une recherche (query.py) : une phrase comme on la tape → des critères (rayon, marque, fonctions, tailles,
budget, promo, petit prix) et les mots qui restent ; rien de deviné. Et la base qui passe de la v11 à la v12 sans rien
perdre (comptes sans e-mail, missions sans prix)."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from bench.missions import PHRASES
from deals import query, store
from deals.missions import interpret
from deals.store import Store

BRANDS = ["Zephyr", "Kessler", "Dormea", "Nordvik", "Helio", "Lumen", "Brava", "Ostra"]


def read(text):
    r = query.read(text, BRANDS)
    return {k: v for k, v in r.items() if v not in (None, [], {}, False)}


class Read(unittest.TestCase):
    def test_the_missions_sentences_are_read_the_same(self):
        for text, want in PHRASES:
            if want[0] == "refus":
                continue
            m = interpret(text, BRANDS)                       # bench.missions : 37 phrases, la même lecture
            r = query.read(text, BRANDS)
            self.assertEqual((r["category"], r["brand"], r["features"], r["attrs"], r["max_price"]),
                             (m["category"], m["brand"], m["features"], m["attrs"], m["max_price"]), text)

    def test_what_remains_is_searched_and_filler_is_dropped(self):
        self.assertEqual(read("Je cherche un canapé velours pas cher"), {"category": "canape", "sort": "price", "rest": ["velours"]})
        self.assertEqual(read("canapé convertible Lina"), {"category": "canape", "features": ["convertible"], "rest": ["lina"]})
        self.assertEqual(read("aspirateur Dyson V15 sous 500 €"), {"category": "aspirateur", "max_price": 500, "rest": ["dyson"]})
        self.assertEqual(read("lave-linge 1400 tours 9 kg moins de 600"), {"category": "lave_linge", "attrs": {"capacity_kg": 9},
                                                                          "max_price": 600})
        self.assertEqual(read("lave-vaisselle 60 cm classe C"), {"category": "lave_vaisselle", "attrs": {"width_cm": 60, "energy_class": "C"}})
        self.assertEqual(read("canapé d’angle gris"), {"category": "canape", "features": ["angle"], "rest": ["gris"]})   # ’ du téléphone
        self.assertEqual(read("canape d angle"), {"category": "canape", "features": ["angle"]})
        self.assertEqual(read("oslo"), {"rest": ["oslo"]})                          # rien de compris : mot à mot
        self.assertEqual(read("je cherche"), {})

    def test_budget_promo_and_low_prices(self):
        self.assertEqual(read("matelas entre 300 et 500 €"), {"category": "matelas", "min_price": 300, "max_price": 500})
        self.assertEqual(read("canapé à partir de 800 €"), {"category": "canape", "min_price": 800})
        self.assertEqual(read("aspirateur pas plus de 200 €"), {"category": "aspirateur", "max_price": 200})   # pas un minimum
        self.assertEqual(read("lave-linge -30 %"), {"category": "lave_linge", "off": 30})
        self.assertEqual(read("lave-linge -95 %"), {"category": "lave_linge"})       # au-delà de 90 % : pas une remise crédible
        self.assertEqual(read("frigo en promo"), {"category": "refrigerateur", "off": 1})
        self.assertEqual(read("lit au plus bas"), {"category": "lit", "low": True})
        self.assertEqual(read("table 6 places petit prix"), {"category": "table", "attrs": {"seats": 6}, "sort": "price"})
        self.assertEqual(read("coton 100%"), {"rest": ["coton"]})                   # 100 % n'est pas une remise
        self.assertEqual(read("smartphone sous 300 €"), {"max_price": 300, "unsupported": "smartphone"})
        self.assertEqual(read("matelas de 300 à 500 €"), {"category": "matelas", "min_price": 300, "max_price": 500})
        self.assertEqual(read("canapé 1 299 à 1 599 €"), {"category": "canape", "min_price": 1299, "max_price": 1599})
        self.assertEqual(read("matelas dès 300 €"), {"category": "matelas", "min_price": 300})
        self.assertEqual(read("lave-linge de 7 à 9 kg"), {"category": "lave_linge", "attrs": {"capacity_kg": 9}})   # pas un prix
        self.assertEqual(read("aspirateur autonomie 40 min"), {"category": "aspirateur", "attrs": {"autonomy_min": 40}})
        self.assertEqual(read("matelas 140 × 190"), {"category": "matelas", "attrs": {"bed_size": "140x190"}})
        self.assertEqual(read("matelas entre 500 et 300 €"), {"category": "matelas"})          # à l'envers : pas de budget inventé
        self.assertEqual(read("commodes 300 €"), {"category": "commode", "max_price": 300})     # « des » dans « commodes » : pas « dès »
        self.assertEqual(read("canapé pour le salon"), {"category": "canape"})                 # le rayon nommé suffit
        self.assertEqual(read("pour le salon"), {"room": "salon"})

    def test_chips_say_the_criteria_in_words(self):
        c = {**query.read("aspirateur balai sans fil Zephyr entre 200 et 400 € en promo pas cher", BRANDS), "words": ["v8"]}
        self.assertEqual([x["label"] for x in query.chips(c)],
                         ["Aspirateurs", "Balai", "Sans fil", "Zephyr", "200 à 400 €", "En promo", "Prix croissant", "« v8 »"])
        self.assertEqual([x["id"] for x in query.chips(c)],
                         ["category", "feature:balai", "feature:sans_fil", "brand", "price", "off", "sort", "word:v8"])
        self.assertEqual([x["label"] for x in query.chips({"attrs": {"capacity_kg": 9, "bed_size": "160x200"}, "max_price": 500, "off": 30,
                                                           "low": True})],
                         ["9 kg et plus", "160 × 200", "Moins de 500 €", "−30 % et plus", "Prix bas"])

    def test_chips_read_back_as_the_same_search(self):
        """Une recherche faite de puces se garde en mots (vos recherches récentes) : relue, elle redonne les mêmes critères."""
        keys = ("category", "room", "brand", "features", "attrs", "min_price", "max_price", "off", "low", "sort")
        more = ["aspirateur balai sans fil Zephyr entre 200 et 400 € en promo pas cher", "lave-linge 9 kg classe C moins de 600",
                "matelas 160x200 dès 300 €", "canapé convertible -30 %", "lit au plus bas", "salon pas cher", "chambre sous 500 €",
                "lave-vaisselle 60 cm 45 dB", "aspirateur autonomie 40 min", "table 6 places", "frigo 300 L en promo",
                "canapé 1 299 à 1 599 €", "salon à partir de 2 000 €"]
        for text in [t for t, want in PHRASES if want[0] != "refus"] + more:
            r = query.read(text, BRANDS)
            said = " · ".join(c["label"].strip("« »") for c in query.chips(r))
            back = query.read(said, BRANDS)
            self.assertEqual({k: back[k] for k in keys}, {k: r[k] for k in keys}, f"{text} → {said}")
            self.assertEqual(back["rest"], [], said)

    def test_fits_requires_what_is_said(self):
        balai = {"category": "aspirateur", "brand": "Zephyr", "attrs": {"features": ["balai", "sans_fil"], "autonomy_min": 40}}
        self.assertTrue(query.fits({"category": "aspirateur", "features": ["balai"]}, balai))
        self.assertTrue(query.fits({"brand": "zephyr", "attrs": {"autonomy_min": 30}}, balai))
        self.assertFalse(query.fits({"attrs": {"autonomy_min": 45}}, balai))
        self.assertFalse(query.fits({"features": ["traineau"]}, balai))
        self.assertFalse(query.fits({"attrs": {"width_cm": 60}}, balai))          # demandé mais inconnu : pas de promesse
        self.assertEqual([query.satisfies("energy_class", a, "C") for a in ("A", "C", "D", None)], [True, True, False, False])   # C ou mieux
        self.assertEqual([query.satisfies("width_cm", a, 60) for a in (59.5, 64, 56.5)], [True, False, True])   # à 6 % près
        self.assertTrue(query.fits({"room": "entretien"}, balai))                   # une pièce : un de ses rayons
        self.assertFalse(query.fits({"room": "salon"}, balai))
        self.assertTrue(query.fits({"room": "salon", "category": "aspirateur"}, balai))   # le rayon nommé l'emporte sur la pièce


class Migration(unittest.TestCase):
    def test_a_v11_base_keeps_everything(self):
        path = Path(tempfile.mkdtemp(), "v11.sqlite")
        c = sqlite3.connect(path, isolation_level=None)
        c.execute("PRAGMA foreign_keys=ON")
        for st in store.statements(store.SCHEMA):
            c.execute(st)
        for v in range(2, 12):
            for st in store.MIGRATIONS[v]:
                c.execute(st)
        c.execute("PRAGMA user_version=11")
        c.execute("INSERT INTO users(id, email, created_at) VALUES (7, 'mia@test.local', 0)")
        c.execute("INSERT INTO sessions VALUES ('h', 7, 0, 9e9)")
        c.execute("INSERT INTO follows VALUES (7, 'Nordvik', 0)")
        c.execute("INSERT INTO saves(user_id, product_id, created_at) VALUES (7, 1, 0)")
        c.execute("INSERT INTO missions(id, user_id, category, want, max_price, label, created_at) VALUES (3, 7, 'lit', '{}', 700, 'Lit · 700 € max', 0)")
        c.close()
        s = Store(path)
        self.assertEqual(s.q("PRAGMA user_version", one=True)["user_version"], 12)
        self.assertEqual([s.q(f"SELECT COUNT(*) n FROM {t}", one=True)["n"] for t in ("users", "sessions", "follows", "saves", "missions")],
                         [1, 1, 1, 1, 1])
        self.assertEqual(s.q("SELECT max_price, alert, seen FROM missions", one=True), {"max_price": 700, "alert": 1, "seen": None})
        s.x("INSERT INTO users(email, created_at) VALUES (NULL, 0)")              # un compte sans e-mail, désormais
        s.x("DELETE FROM users WHERE id=7")                                          # et les cascades suivent toujours
        self.assertEqual(s.q("SELECT COUNT(*) n FROM missions", one=True)["n"], 0)
        s.close()

    def test_broken_references_stop_the_migration(self):
        path = Path(tempfile.mkdtemp(), "v11.sqlite")
        c = sqlite3.connect(path, isolation_level=None)
        for st in store.statements(store.SCHEMA):
            c.execute(st)
        for v in range(2, 12):
            for st in store.MIGRATIONS[v]:
                c.execute(st)
        c.execute("PRAGMA user_version=11")
        c.execute("INSERT INTO follows VALUES (42, 'Nordvik', 0)")                   # un compte disparu, sans cascade d'alors
        c.close()
        with self.assertRaisesRegex(RuntimeError, "références cassées"):
            Store(path)
        c = sqlite3.connect(path)
        self.assertEqual(c.execute("PRAGMA user_version").fetchone()[0], 11)        # rien n'est à moitié migré
        c.close()


if __name__ == "__main__":
    unittest.main()
