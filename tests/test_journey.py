"""Le moteur de parcours (journey.py) : l'ordre des critères (éliminatoires, forts, faibles), le classement (d'abord les
critères forts tout à fait satisfaits, puis l'adéquation, puis l'ordre demandé), ce qu'un type ne peut pas satisfaire et
l'autre type proposé (celui que le besoin suggère, s'il le peut et a des produits), la question (seulement si au moins
deux réponses changent la sélection), les verdicts gardés le temps d'une publication."""
import unittest

from deals import journey as J
from deals.ontology import DOMAINS

D = DOMAINS["aspirateurs"]


def row(pid, sub, price, **attrs):
    return {"product_id": pid, "price": price, "attrs": {"sub": sub, **attrs}}


by_price = lambda r: (r["price"], r["product_id"])


class Plans(unittest.TestCase):
    def test_criteria_in_order_eliminatory_strong_weak(self):
        self.assertEqual(J.Plan(D, ["carrelage", "animaux", "lavage"]).order, ["lavage", "poils", "sols_durs"])
        self.assertEqual(J.Plan(D, ["escaliers"]).strict, {"escaliers"})
        self.assertEqual(J.Plan(D, ["escaliers"], drop={"escaliers"}).order, ["maniabilite"])
        self.assertFalse(J.Plan(D, ["petite_surface"]))                     # un besoin dit, sans critère : rien ne change

    def test_only_strong_criteria_fully_met_count_first(self):
        a = row(1, "balai", 100, motor_brush=False)                         # poils : inconnu ; sols durs (faible) : en partie
        b = row(2, "balai", 200, motor_brush=True)                          # poils : en partie
        kept, seen, _ = J.Plan(D, ["animaux", "carrelage"]).rank([a, b], by_price)
        self.assertEqual(([r["product_id"] for r in kept], seen[1]["met"], seen[2]["met"]), ([2, 1], 0, 0))   # un critère faible ne compte pas
        c = row(3, "balai", 300, pet_tool=True, noise_db=80)                 # poils : oui ; silence : non → un critère fort tout à fait
        d = row(4, "robot", 50, motor_brush=True, noise_db=73, mop=True)     # en partie, en partie ; sols durs : oui
        kept, seen, _ = J.Plan(D, ["animaux", "silence", "carrelage"]).rank([d, c], by_price)
        self.assertGreater(seen[4]["fit"], seen[3]["fit"])
        self.assertEqual([r["product_id"] for r in kept], [3, 4])            # le plus de critères forts satisfaits d'abord

    def test_eliminatory_excludes_only_what_is_known_not_to_fit(self):
        rows = [row(1, "robot", 300, mop=True), row(2, "robot", 200), row(3, "balai", 100)]
        kept, seen, dropped = J.Plan(D, ["lavage"]).rank(rows, by_price)
        self.assertEqual(([r["product_id"] for r in kept], dropped), ([1, 2], {"Ne lave pas le sol": 1}))


class OtherTypes(unittest.TestCase):
    def test_conflicts_are_type_rules_at_zero(self):
        self.assertEqual(J.conflict(D, "robot", ["escaliers"]), [("escaliers", "Un robot ne monte pas les marches", "escaliers")])
        self.assertEqual([c for c, _, _ in J.conflict(D, "robot", ["escaliers"], weak=True)], ["escaliers", "maniabilite"])
        self.assertEqual(J.conflict(D, "main", ["voiture"]), [])            # à 1 pour ce type : rien à corriger
        self.assertEqual(J.conflict(D, None, ["escaliers"]), [])

    def test_the_suggested_type_can_do_it_and_has_products(self):
        self.assertEqual(J.suggest(D, "main", ["grande_surface"], {"robot": 2, "traineau": 2, "balai": 2})["sub"], "traineau")   # le besoin le suggère
        self.assertIsNone(J.suggest(D, "robot", ["escaliers"], {"laveur": 5, "traineau": 3}))     # un laveur ne peut pas, un traîneau qu'en partie
        self.assertEqual(J.suggest(D, "robot", ["escaliers"], {"balai": 4}),
                         {"sub": "balai", "label": "Aspirateurs balais", "why": "Un robot ne monte pas les marches", "count": 4})
        self.assertIsNone(J.suggest(D, "main", ["voiture"], {"balai": 4}))


class Questions(unittest.TestCase):
    ROWS = [row(i, "balai", 100 + i) for i in range(1, 7)] + [row(7, "robot", 400), row(8, "robot", 410), row(9, "main", 500), row(10, "main", 510)]

    def test_asked_only_when_answers_change_the_selection(self):
        current = [r["product_id"] for r in sorted(self.ROWS, key=by_price)][:6]
        q = J.question(D, self.ROWS, current, by_price, "sub")
        self.assertEqual([o["apply"] for o in q["options"]], [{"domain": "aspirateurs", "sub": "robot"}, {"domain": "aspirateurs", "sub": "main"}])
        self.assertEqual([o["count"] for o in q["options"]], [2, 2])         # « balai » ne changerait rien : pas proposé
        one = [r for r in self.ROWS if r["attrs"]["sub"] != "main"]
        self.assertIsNone(J.question(D, one, current, by_price, "sub"))      # une seule réponse utile : pas de question

    def test_verdicts_are_kept_and_needs_counted_once(self):
        v = J.Verdicts(D)
        rows = [row(1, "balai", 100, pet_tool=True), row(2, "balai", 100), row(3, "robot", 100, pet_tool=True)]
        self.assertEqual(v.good("animaux", rows), {1, 3})
        self.assertEqual(v.of(1, rows[0]["attrs"], "poils")[0], 1)
        rows[0]["attrs"]["pet_tool"] = False                                 # la même publication : rien n'est relu
        self.assertEqual((v.good("animaux", rows), v.of(1, rows[0]["attrs"], "poils")[0]), ({1, 3}, 1))


if __name__ == "__main__":
    unittest.main()
