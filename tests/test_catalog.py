"""Où se situe le prix du jour (catalog.position, pur) : ce que la fiche affirme au consommateur doit être vrai.

« Au plus bas » seulement si aucun jour des trois derniers mois n'était moins cher et que le prix était plus haut au moins
un jour sur deux (un prix qui ne bouge pas n'est pas « au plus bas », il est habituel) ; « parmi les plus bas » si
moins cher qu'au moins 2 jours sur 3 ; « plus cher que d'habitude » si plus cher qu'au moins 2 jours sur 3 ; rien sans
au moins 14 jours relevés.
"""
import unittest

from deals.catalog import position


def curve(*runs, today):
    """runs : (prix, nombre de jours)… ; today : le prix du jour, dernier point de la courbe."""
    p = [v for price, n in runs for v in [price] * n]
    return {"from": "2026-09-16", "p": [None] * (89 - len(p)) + p + [today]}


class Position(unittest.TestCase):
    def test_lowest_only_after_higher_prices(self):
        pos = position(curve((749, 60), (699, 29), today=612), 612)
        self.assertEqual((pos["level"], pos["rank"], pos["low"], pos["high"], pos["days"]), ("lowest", 0, 612, 749, 90))
        self.assertEqual(position(curve((599, 80), (649, 9), today=599), 599)["level"], "usual")   # son prix de toujours
        flat = position(curve((599, 89), today=599), 599)
        self.assertEqual((flat["level"], flat["rank"]), ("usual", 0.5))                             # prix qui ne bouge pas : au milieu

    def test_low_usual_high(self):
        self.assertEqual(position(curve((549, 20), (649, 69), today=579), 579)["level"], "low")      # moins cher que 69 jours sur 89
        self.assertEqual(position(curve((549, 40), (649, 49), today=599), 599)["level"], "usual")
        self.assertEqual(position(curve((549, 50), (649, 39), today=599), 599)["level"], "usual")    # plus cher qu'1 jour sur 2 seulement
        pos = position(curve((549, 70), (649, 19), today=629), 629)
        self.assertEqual((pos["level"], pos["usual"], pos["rank"]), ("high", 549, 0.79))            # souvent à 549 € ; à droite
        self.assertEqual(position(curve((549, 20), (649, 69), today=579), 579)["rank"], 0.22)      # bas : à gauche
        self.assertEqual(position(curve((549, 89), today=599), 599)["high"], 599)                    # la jauge inclut aujourd'hui

    def test_rounding_and_gaps(self):
        tied = position(curve((612, 30), (700, 59), today=612), 612.4)                               # courbe arrondie à l'euro
        self.assertEqual((tied["level"], tied["rank"]), ("lowest", 0))                              # au plus bas : tout à gauche
        self.assertEqual(position(curve((700, 60), (650, 29), today=700), 699.6)["level"], "usual")   # 700 € arrondi : pas « plus bas »
        gaps = curve((700, 20), today=650)
        gaps["p"][40:44] = [690, None, 690, 680]                                                     # jours sans prix : ignorés
        pos = position(gaps, 650)
        self.assertEqual((pos["level"], pos["low"], pos["days"]), ("lowest", 650, 50))              # 50 jours depuis le 1er relevé

    def test_too_few_days(self):
        self.assertIsNone(position(curve((700, 13), today=650), 650))
        self.assertIsNone(position(None, 650))
        self.assertEqual(position(curve((700, 14), today=650), 650)["days"], 15)


if __name__ == "__main__":
    unittest.main()
