"""Alternatives moins chères (alternatives.py) — fonction pure, sur des titres réels de forme.

Ce que le produit promet : sur la fiche d'un produit, des produits qui le remplacent vraiment (même usage, pas moins
bien) et qui coûtent au moins 10 % de moins ; jamais un appareil d'une autre largeur, une literie d'une autre taille, un
aspirateur à fil à la place d'un sans fil ; v59 : jamais un autre type (un matelas à ressorts pour un matelas en mousse,
un téléviseur QLED pour un OLED), ni une autre taille d'écran, ni moins de stockage, ni une console sans lecteur pour
une console qui en a un.
"""
import unittest

from deals.alternatives import comparable, pick
from deals.extract import attributes, categorize
from deals.extract.categories import FAMILY_OF


def item(i, title, price, declared=None, in_stock=True):
    cat, _ = categorize(title, declared)
    return {"id": i, "category": cat, "family": FAMILY_OF.get(cat), "brand": title.split()[-1], "price": price,
            "in_stock": in_stock, "attrs": attributes(title, None, cat, declared)}     # comme le marché : lus avec leur rayon


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
        self.assertEqual(attributes("Four encastrable pyrolyse 71 L classe A+")["energy_class"], "A+")      # un A+ n'est pas un A
        self.assertEqual(attributes(None, {"Classe énergétique": "A+++ (de A+++ à D)"})["energy_class"], "A+++")


class Comparable(unittest.TestCase):
    def test_same_usage(self):
        v15 = item(1, "Aspirateur balai sans fil V15 60 min Zephyr", 699)
        self.assertTrue(comparable(v15, item(2, "Aspirateur balai sans fil Flex 45 min Kessler", 259)))
        self.assertFalse(comparable(v15, item(3, "Aspirateur traîneau sans sac Silence 750 W Ostra", 229)))    # autre forme
        self.assertFalse(comparable(v15, item(9, "Aspirateur balai Easy 600 W Ostra", 129)))                     # à fil
        self.assertFalse(comparable(v15, item(4, "Aspirateur balai sans fil Agile 30 min Helio", 179)))        # moitié moins d'autonomie
        self.assertFalse(comparable(v15, item(5, "Robot aspirateur laveur S8 Ostra", 549, "robot-aspirateur")))
        m = item(6, "Matelas Confort 160x200 ressorts Dormea", 900)
        self.assertTrue(comparable(m, item(7, "Matelas Ferme 160x200 ressorts ensachés Solenne", 600)))
        self.assertFalse(comparable(m, item(8, "Matelas Ferme 140x190 ressorts Solenne", 400)))                # autre taille
        self.assertFalse(comparable(m, item(12, "Matelas Air 160x200 mousse Solenne", 600)))                  # autre type
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
        four = item(9, "Four encastrable pyrolyse 71 L classe A+++ Brava", 699)
        self.assertTrue(comparable(four, item(10, "Four encastrable pyrolyse 72 L classe A++ Helio", 499)))
        self.assertFalse(comparable(four, item(11, "Four encastrable pyrolyse 72 L classe A+ Ostra", 449)))    # deux crans

    def test_the_same_type_neither_more_nor_less(self):
        """v59 : le type que l'offre dit (l'ontologie du rayon) ; un type non dit n'est remplacé que par un type non dit."""
        conv = item(1, "Canapé convertible Bergen couchage 140x190 Lumen", 749)
        self.assertFalse(comparable(conv, item(2, "Canapé d'angle convertible Nordic 5 places Lumen", 899 * 0.6)))
        self.assertTrue(comparable(conv, item(3, "Canapé convertible Oslo couchage 140x190 Nordvik", 549)))
        angle = item(4, "Canapé d'angle convertible Oslo 5 places Nordvik", 1290)
        self.assertTrue(comparable(angle, item(5, "Canapé d'angle convertible Nordic 5 places Lumen", 899)))
        self.assertFalse(comparable(angle, item(6, "Canapé d'angle Ravel 5 places Varenne", 899)))             # pas dit convertible
        tr = item(7, "Aspirateur traîneau sans sac Silence 750 W Ostra", 229)
        self.assertFalse(comparable(tr, item(8, "Aspirateur traîneau avec sac Eco 550 W Ostra", 89)))          # une forme : la même
        self.assertFalse(comparable(tr, item(9, "Aspirateur traîneau Compact 700 W Helio", 119)))               # forme non dite
        self.assertTrue(comparable(tr, item(10, "Aspirateur traîneau sans sac Compact 700 W Helio", 119)))
        self.assertFalse(comparable(item(13, "Aspirateur traîneau avec sac Pro 650 W Kessler", 249), tr))  # dans l'autre sens non plus
        dressing = item(11, "Armoire Modulo 200 cm portes coulissantes Lumen", 899)
        self.assertFalse(comparable(dressing, item(12, "Armoire Lund 200 cm portes battantes Nordvik", 649)))
        self.assertFalse(comparable(item(14, "Armoire Lund 200 cm portes battantes Nordvik", 649), dressing))   # une forme, dans les deux sens

    def test_electronics(self):
        """v59 : un téléviseur 55 pouces n'est remplacé que par un 55 pouces du même type, 4K s'il l'est ; un smartphone,
        pas par moins de stockage, ni en 4G s'il est 5G ; une console, par une console de sa marque, sans perdre son lecteur."""
        oled = item(1, "TV OLED 55OL8 55\" 4K UHD 120 Hz Vistrel", 1290)
        self.assertTrue(comparable(oled, item(2, "TV OLED A55 139 cm 4K Ultra HD Kanzo", 1090)))                # 139 cm : 55 pouces
        self.assertFalse(comparable(oled, item(3, "TV QLED Q55 55 pouces 4K Orvia", 549)))                       # autre type
        self.assertFalse(comparable(oled, item(4, "TV OLED 65\" 4K Kanzo", 1190)))                              # autre taille
        self.assertFalse(comparable(oled, item(5, "Téléviseur 55 pouces 4K Orvia", 449)))                        # type non dit
        self.assertFalse(comparable(oled, item(29, "TV OLED 4K Ultra HD Kanzo", 899)))                           # taille non dite
        led = item(6, "TV LED 43UX7 108 cm 4K Ultra HD Kanzo", 329)
        self.assertFalse(comparable(led, item(7, "TV LED 43\" Full HD Orvia", 249)))                            # pas 4K
        self.assertTrue(comparable(item(8, "TV LED 43\" Full HD Orvia", 249), led))                             # 4K à la place : oui
        phone = item(9, "Smartphone X3 Pro 5G 256 Go Ombrion", 1099)
        self.assertTrue(comparable(phone, item(10, "Smartphone V12 5G 256 Go Velto", 899)))
        self.assertFalse(comparable(phone, item(11, "Smartphone X3 5G 128 Go Ombrion", 699)))                    # moins de stockage
        self.assertFalse(comparable(phone, item(12, "Smartphone V9 4G 512 Go Velto", 499)))                     # 4G
        self.assertTrue(comparable(item(13, "Smartphone A2 4G 64 Go Aphel", 149), item(14, "Smartphone A5 5G 128 Go Aphel", 129)))
        pc = item(15, "PC portable Vivo 15 15,6\" 16 Go RAM 512 Go SSD Calixo", 749)
        self.assertTrue(comparable(pc, item(16, "Ordinateur portable Nova 15 15,6 pouces 16 Go RAM 512 Go SSD Ternis", 629)))
        self.assertFalse(comparable(pc, item(17, "PC portable Lite 15,6\" 8 Go RAM 512 Go SSD Ternis", 499)))     # moins de RAM
        self.assertFalse(comparable(pc, item(18, "PC portable Air 14\" 16 Go RAM 512 Go Ternis", 599)))          # autre écran
        screen = item(19, "Écran PC 27\" QHD 165 Hz Calixo", 299)
        self.assertFalse(comparable(screen, item(20, "Écran PC 27 pouces 75 Hz Ternis", 149)))                  # moins fluide
        anc = item(21, "Casque sans fil à réduction de bruit H700 Sonoryn", 379)
        self.assertTrue(comparable(anc, item(22, "Casque Bluetooth à réduction de bruit Q35 Aurio", 279)))
        self.assertFalse(comparable(anc, item(23, "Casque Bluetooth Move Aurio", 129)))                          # réduction non dite
        self.assertFalse(comparable(anc, item(24, "Écouteurs sans fil réduction de bruit Buds 3 Sonoryn", 199)))  # autre type
        console = item(25, "Console de salon One 1 To Ludika", 549)
        self.assertFalse(comparable(console, item(26, "Console de salon One Édition Numérique 1 To Ludika", 449)))  # sans lecteur
        self.assertTrue(comparable(item(27, "Console de salon One Édition Numérique 1 To Ludika", 449), console))
        self.assertFalse(comparable(console, item(28, "Console de salon Arena 1 To Vexa", 449)))               # autre marque, autres jeux

    def test_drawers_at_most_one_fewer(self):
        six = item(1, "Commode Ella 6 tiroirs 80 cm Lumen", 399)
        self.assertTrue(comparable(six, item(2, "Commode Lina 5 tiroirs 80 cm Varenne", 299)))
        self.assertFalse(comparable(six, item(3, "Commode Nils 4 tiroirs 80 cm Nordvik", 249)))              # deux de moins

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
