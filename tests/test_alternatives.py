"""Alternatives moins chères (alternatives.py) — fonction pure, sur des titres réels de forme.

Ce que le produit promet : sur la fiche d'un produit, des produits qui le remplacent vraiment (même usage, pas moins
bien) et qui coûtent au moins 10 % de moins ; jamais un appareil d'une autre largeur, une literie d'une autre taille, un
aspirateur à fil à la place d'un sans fil.
"""
import unittest

from deals.alternatives import comparable, pick
from deals.extract import attributes, categorize
from deals.extract.categories import FAMILY_OF


def item(i, title, price, declared=None, in_stock=True):
    cat, _ = categorize(title, declared)
    return {"id": i, "category": cat, "family": FAMILY_OF.get(cat), "brand": title.split()[-1], "price": price,
            "in_stock": in_stock, "attrs": attributes(title)}


class Categories(unittest.TestCase):
    def test_declared_category_with_hyphens_or_plural(self):
        self.assertEqual(categorize("Robot aspirateur laveur S8", "robot-aspirateur")[0], "robot_aspirateur")
        self.assertEqual(categorize("Robot aspirateur S8", "Robots aspirateurs")[0], "robot_aspirateur")
        self.assertEqual(categorize("Lave-linge séchant 9 kg", "lave-linge-sechant")[0], "lave_linge_sechant")
        self.assertEqual(categorize("Aspirateur balai sans fil V15", "aspirateur")[0], "aspirateur")
        self.assertEqual(categorize("Batterie pour aspirateur balai")[0], None)              # accessoire

    def test_usage_read_in_the_title(self):
        a = attributes("Aspirateur balai sans fil Zephyr V15 Detect 60 min")
        self.assertEqual((a["features"], a["autonomy_min"]), (["balai", "sans_fil"], 60))
        self.assertEqual(attributes("Matelas Dormea 2 x 80 x 200 mousse")["bed_size"], "2x80x200")
        a = attributes("Lave-vaisselle encastrable 45 cm 10 couverts 44 dB classe D")
        self.assertEqual((a["width_cm"], a["place_settings"], a["noise_db"], a["energy_class"], a["features"]),
                         (45, 10, 44, "D", ["encastrable"]))


class Comparable(unittest.TestCase):
    def test_same_usage(self):
        v15 = item(1, "Aspirateur balai sans fil V15 60 min Zephyr", 699)
        self.assertTrue(comparable(v15, item(2, "Aspirateur balai sans fil Flex 45 min Kessler", 259)))
        self.assertFalse(comparable(v15, item(3, "Aspirateur traîneau sans sac Silence 750 W Ostra", 229)))    # autre forme
        self.assertFalse(comparable(v15, item(9, "Aspirateur balai Easy 600 W Ostra", 129)))                     # à fil
        self.assertFalse(comparable(v15, item(4, "Aspirateur balai sans fil Agile 30 min Helio", 179)))        # moitié moins d'autonomie
        self.assertFalse(comparable(v15, item(5, "Robot aspirateur laveur S8 Ostra", 549, "robot-aspirateur")))
        m = item(6, "Matelas Confort 160x200 ressorts Dormea", 900)
        self.assertTrue(comparable(m, item(7, "Matelas Air 160x200 mousse Solenne", 600)))
        self.assertFalse(comparable(m, item(8, "Matelas Air 140x190 mousse Solenne", 400)))                   # autre taille
        ll = item(10, "Lave-linge hublot 9 kg classe A Helio", 479)
        self.assertFalse(comparable(ll, item(11, "Sèche-linge pompe à chaleur 9 kg classe A Brava", 399)))      # autre catégorie

    def test_not_worse(self):
        lv = item(1, "Lave-vaisselle 60 cm 14 couverts 42 dB classe B Kessler", 579)
        self.assertTrue(comparable(lv, item(2, "Lave-vaisselle 60 cm 13 couverts 44 dB classe C Helio", 449)))
        self.assertFalse(comparable(lv, item(3, "Lave-vaisselle 60 cm 14 couverts 42 dB classe D Brava", 399)))  # deux lettres
        self.assertFalse(comparable(lv, item(4, "Lave-vaisselle 60 cm 14 couverts 47 dB classe B Ostra", 349)))  # 5 dB de plus
        enc = item(5, "Lave-vaisselle encastrable 60 cm 14 couverts classe B Ostra", 499)
        self.assertFalse(comparable(lv, enc) or comparable(enc, lv))      # la forme compte dans les deux sens : posable ≠ encastrable
        ll = item(7, "Lave-linge hublot 9 kg classe A Helio", 479)
        self.assertFalse(comparable(ll, item(8, "Lave-linge hublot 7 kg classe A Brava", 349)))                 # 2 kg de moins

    def test_unknown_size_is_not_a_replacement(self):
        frigo = item(1, "Réfrigérateur combiné 60 cm 360 L classe D Helio", 799)
        self.assertFalse(comparable(frigo, item(2, "Réfrigérateur combiné 360 L classe D Brava", 599)))        # largeur inconnue
        self.assertFalse(comparable(frigo, item(3, "Réfrigérateur combiné 70 cm 360 L classe D Brava", 599)))  # ne rentre pas
        self.assertTrue(comparable(frigo, item(4, "Réfrigérateur combiné 60 cm 331 L classe C Brava", 599)))   # 8 % de moins
        self.assertFalse(comparable(frigo, item(5, "Réfrigérateur combiné 60 cm 290 L classe C Brava", 549)))  # 19 % de moins


class Pick(unittest.TestCase):
    V15 = item(1, "Aspirateur balai sans fil V15 60 min Zephyr", 699)
    OTHERS = [item(2, "Aspirateur balai sans fil V8 40 min Zephyr", 399), item(3, "Aspirateur balai sans fil X5 50 min Brava", 349),
              item(4, "Aspirateur balai sans fil Flex 45 min Kessler", 259), item(5, "Aspirateur balai sans fil Flex+ 45 min Kessler", 249),
              item(6, "Aspirateur balai sans fil Pro 60 min Helio", 669), item(7, "Aspirateur balai sans fil Max 60 min Ostra", 199, in_stock=False)]

    def test_cheapest_first_one_brand_per_line(self):
        cheap, near = pick(self.V15, self.OTHERS)
        self.assertEqual([x["id"] for x in cheap], [5, 3, 2])          # Kessler une fois, épuisé écarté, 669 € pas 10 % moins cher
        self.assertEqual([x["id"] for x in near], [6, 4, 7])           # les autres comparables, au prix le plus proche

    def test_nothing_cheaper(self):
        agile = item(9, "Aspirateur balai sans fil Agile 30 min Helio", 179)
        cheap, _ = pick(agile, self.OTHERS + [self.V15, item(10, "Aspirateur balai sans fil Lite 30 min Brava", 169)])
        self.assertEqual(cheap, [])                                     # 10 € de moins : pas une alternative « moins chère »


if __name__ == "__main__":
    unittest.main()
