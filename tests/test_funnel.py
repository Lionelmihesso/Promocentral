"""Affiner en entonnoir (v60, deals/funnel.py et Catalog.search) : une question à la fois, de l'univers au budget, chaque
réponse avec le nombre exact de produits qu'elle donne ; une question qui ne resserre rien n'est pas posée ; la fin
arrive (trois produits ou moins, plus de question) ; chaque étape franchie se retire ; une sélection toute dans un rayon
(une marque qui ne fait que des téléviseurs, la pièce Entretien) y entre d'elle-même."""
import json
import tempfile
import unittest
from pathlib import Path

from deals import funnel, ontology
from deals.catalog import Catalog, haystack
from deals.extract import attributes, categorize
from deals.store import Store

ROWS = [  # id, titre, marque, prix, remise
    (1, "Téléviseur OLED 55 pouces 4K", "Kanzo", 1299, 10), (2, "Téléviseur OLED 65 pouces 4K", "Kanzo", 1899, 0),
    (3, "TV QLED 55 pouces 4K", "Vistrel", 799, 15), (4, "TV LED 55 pouces 4K", "Vistrel", 449, 0),
    (5, "Téléviseur LED 43 pouces Full HD", "Vistrel", 299, 20), (18, "Téléviseur QLED 65 pouces 4K", "Vistrel", 1099, 0),
    (6, "Aspirateur balai sans fil", "Brava", 349, 0), (7, "Aspirateur traîneau sans sac", "Brava", 199, 10),
    (8, "Robot aspirateur laveur", "Brava", 449, 0), (9, "Robot aspirateur", "Kessler", 249, 0),
    (10, "Lave-linge hublot 9 kg", "Kessler", 499, 0), (11, "Lave-linge hublot 8 kg", "Kessler", 399, 0),
    (12, "Smartphone 5G 128 Go", "Orbis", 599, 0), (13, "Casque audio sans fil réduction de bruit", "Orbis", 199, 0),
    (14, "Canapé d'angle convertible 5 places", "Nordvik", 1290, 0), (15, "Canapé 3 places", "Nordvik", 699, 0),
    (16, "Matelas 140x190 mousse", "Nordvik", 399, 0), (17, "Réfrigérateur combiné No Frost", "Kessler", 699, 0)]

PARAM = {"category": "category", "room": "room", "domain": "domain", "sub": "sub", "min": "lo", "max": "hi"}


def answer(kw, patch):
    """Une réponse (ou un retour) appliquée aux critères, comme l'app le fait (web/src/App.jsx : apply)."""
    out = dict(kw)
    for k, v in patch.items():
        if k in ("props", "attrs"):
            if v is None:
                out.pop(k, None)
            else:
                merged = {**out.get(k, {}), **v}
                out[k] = {x: y for x, y in merged.items() if y is not None}
                if not out[k]:
                    out.pop(k)
        elif v is None:
            out.pop(PARAM[k], None)
        else:
            out[PARAM[k]] = v
    return out


class Funnel(unittest.TestCase):
    def setUp(self):
        self.s = Store(Path(tempfile.mkdtemp(), "f.sqlite"))
        with self.s.tx() as c:
            for pid, title, brand, price, pct in ROWS:
                cat = categorize(title)[0]
                c.execute("INSERT INTO catalog(product_id, name, title, brand, category, price, pct, search, published_on, attrs) "
                          "VALUES (?,?,?,?,?,?,?,?,?,?)", (pid, title, title, brand, cat, price, pct, haystack(title, brand, "Site", cat),
                                                         "2026-10-24", json.dumps(attributes(title, None, cat))))
        self.c = Catalog(self.s)

    def tearDown(self):
        self.s.close()

    def ask(self, **kw):
        out = self.c.search(**kw)
        return out, out["funnel"]

    def said(self, **kw):
        """→ (chemin, [(titre, [(réponse, nombre)])])"""
        _, f = self.ask(**kw)
        return ([s["label"] + (" (fixe)" if s["fixed"] else "") for s in f["path"]],
                [(q["title"], [(o["label"], o["count"]) for o in q["options"]]) for q in f["questions"]])

    def test_one_question_at_a_time_from_the_universe_to_the_budget(self):
        path, qs = self.said()                                                   # rien demandé : l'univers d'abord
        self.assertEqual((path, qs[0]), ([], ("Quel univers ?", [("High-tech", 8), ("Entretien", 4), ("Buanderie", 2), ("Salon", 2),
                                                                  ("Chambre", 1), ("Cuisine", 1)])))
        self.assertEqual([q[0] for q in qs], ["Quel univers ?", "Quel rayon ?", "Votre budget ?"])   # « Peu importe » : la suivante
        self.assertEqual(self.said(room="high_tech")[1][0],
                         ("Quel rayon ?", [("Téléviseurs", 6), ("Casques et écouteurs", 1), ("Smartphones", 1)]))
        path, qs = self.said(category="televiseur")
        self.assertEqual((path, [q[0] for q in qs]), (["Téléviseurs"], ["Quel type ?", "Taille d'écran ?", "Définition ?", "Votre budget ?"]))
        self.assertEqual(qs[0][1], [("OLED", 2), ("QLED", 2), ("LED", 2)])
        self.assertEqual(qs[2][1], [("4K", 5), ("HD ou Full HD", 1)])            # « télévision 4K »
        self.assertEqual(self.said(category="televiseur", domain="televiseur", props={"uhd": True})[0], ["Téléviseurs", "4K"])

    def test_each_answer_gives_exactly_its_count(self):
        """Le nombre montré à côté d'une réponse est celui que la recherche donne quand on la choisit — à chaque étape."""
        states, seen = [{}], 0
        while states:
            kw = states.pop()
            out, f = self.ask(**kw)
            for q in f["questions"]:
                for o in q["options"]:
                    nxt = answer(kw, o["set"])
                    got = self.c.search(**nxt)["total"]
                    self.assertEqual(got, o["count"], (kw, q["title"], o["label"]))
                    self.assertLess(o["count"], out["total"])                     # chaque réponse resserre
                    seen += 1
                    if len(nxt) < 4:
                        states.append(nxt)
        self.assertGreater(seen, 150)

    def test_the_end_and_the_way_back(self):
        out, f = self.ask(category="televiseur", domain="televiseur", sub="oled")
        self.assertEqual((out["total"], f["questions"]), (2, []))                  # deux produits : votre sélection
        kw = {"room": "high_tech", "category": "televiseur", "domain": "televiseur", "sub": "led", "attrs": {"screen_in": 55}, "hi": 1000}
        out, f = self.ask(**kw)
        self.assertEqual([s["label"] for s in f["path"]], ["High-tech", "Téléviseurs", "LED", "55 pouces", "Moins de 1 000 €"])
        back = {s["level"] + ":" + s["key"]: self.c.search(**answer(kw, s["back"]))["funnel"] for s in f["path"]}
        self.assertEqual([s["label"] for s in back["budget:budget"]["path"]], ["High-tech", "Téléviseurs", "LED", "55 pouces"])   # le budget seul
        self.assertEqual([s["label"] for s in back["attr:screen_in"]["path"]], ["High-tech", "Téléviseurs", "LED", "Moins de 1 000 €"])
        self.assertEqual([s["label"] for s in back["sub:led"]["path"]], ["High-tech", "Téléviseurs", "Moins de 1 000 €"])   # le type et ses attributs
        self.assertEqual([s["label"] for s in back["category:televiseur"]["path"]], ["High-tech", "Moins de 1 000 €"])
        self.assertEqual([s["label"] for s in back["room:high_tech"]["path"]], ["Moins de 1 000 €"])                     # tout le rayon
        self.assertEqual(back["category:televiseur"]["questions"][0]["title"], "Quel rayon ?")
        self.assertEqual(self.said(category="televiseur", lo=400, hi=1500)[0], ["Téléviseurs", "400 à 1 500 €"])

    def test_the_path_shows_what_the_chips_said(self):
        """Ce que l'entonnoir montre n'est pas répété en puce (l'app garde les autres : marque, promo, tri, mots)."""
        for kw in ({"q": "TV OLED 55 pouces sous 2000 €"}, {"q": "robot aspirateur"}, {"category": "robot_aspirateur"},
                   {"q": "pour le salon"}, {"q": "aspirateur sans fil", "brand": "Brava"}, {"category": "televiseur", "domain": "televiseur",
                                                                                            "sub": "oled", "props": {"uhd": True}}):
            out, f = self.ask(**kw)
            covered = {c for s in f["path"] for c in s["chips"]}
            self.assertEqual({c["id"] for c in out["chips"]} - covered - {"brand"}, set(), kw)
        self.assertEqual(self.said(category="robot_aspirateur")[0], ["Robots aspirateurs"])   # une catégorie qui est un type : une étape
        self.assertEqual(self.said(room="salon", category="televiseur")[0], ["Téléviseurs"])  # une pièce qui ne le contient pas : pas dite
        path, qs = self.said(q="high-tech")                                      # la pièce dite par la phrase
        self.assertEqual((path, qs[0][0]), (["High-tech"], "Quel rayon ?"))

    def test_nothing_under_the_budget_counts_what_is_shown(self):
        """Rien sous le budget : les plus proches au-dessus sont montrés, et l'entonnoir compte ceux-là."""
        out, f = self.ask(room="high_tech", hi=100)
        self.assertEqual((out["relaxed"]["max_price"], out["total"]), (100, 8))
        self.assertEqual(self.said(room="high_tech", hi=100), (["High-tech", "Moins de 100 €"], [
            ("Quel rayon ?", [("Téléviseurs", 6), ("Casques et écouteurs", 1), ("Smartphones", 1)])]))

    def test_a_selection_all_in_one_rayon_enters_it(self):
        self.assertEqual(self.said(brand="Vistrel"), (["Téléviseurs (fixe)"], [                  # une marque de téléviseurs seulement
            ("Quel type ?", [("QLED", 2), ("LED", 2)]), ("Taille d'écran ?", [("43 pouces", 1), ("55 pouces", 2), ("65 pouces", 1)]),
            ("Définition ?", [("4K", 3), ("HD ou Full HD", 1)]),
            ("Votre budget ?", [("Moins de 300 €", 1), ("Moins de 500 €", 2), ("Moins de 1 000 €", 3)])]))
        path, qs = self.said(room="entretien")                                   # deux catégories, un domaine : ses types, robots compris
        self.assertEqual((path, qs[0]), (["Entretien", "Aspirateurs (fixe)"], ("Quel type ?", [("Robot", 2), ("Balai", 1), ("Traîneau", 1)])))
        self.assertEqual(self.said(brand="Kessler")[1][0][0], "Quel rayon ?")      # plusieurs rayons : on demande
        path, qs = self.said(q="aspirateur")                                     # la phrase a dit le rayon : il se retire
        self.assertEqual((path, qs[0][0]), (["Aspirateurs"], "Quel type ?"))
        self.assertEqual(self.c.search(brand="Vistrel")["total"], 4)              # la même sélection
        self.assertEqual(self.said(brand="Kanzo"), ([], []))                     # deux produits : rien à demander
        self.assertEqual(self.said(brand="Brava"), ([], []))                     # trois : c'est déjà la fin

    def test_the_rayon_counts_what_choosing_it_gives(self):
        cats = dict(self.said()[1][1][1])
        self.assertEqual((cats["Aspirateurs"], cats["Robots aspirateurs"]), (4, 2))   # « Aspirateurs » : robots compris
        self.assertEqual(self.c.search(category="aspirateur")["total"], 4)

    def test_sorts(self):
        prices = [p["price"] for p in self.c.search(category="televiseur", sort="price_desc")["products"]]
        self.assertEqual(prices, sorted(prices, reverse=True))
        self.assertEqual(self.c.search(category="televiseur", sort="price_desc")["chips"][-1], {"id": "sort", "label": "Prix décroissant"})


class Pure(unittest.TestCase):
    def test_a_question_narrows_or_is_not_asked(self):
        """Ni tout, ni rien : une réponse qui donnerait toute la sélection, ou aucun produit, n'est pas proposée ; une
        question sans réponse qui resserre n'est pas posée ; le type choisi ne se redemande pas."""
        d = ontology.DOMAINS["televiseur"]
        opts = {"subs": [{"key": "oled", "label": "OLED", "count": 5}, {"key": "led", "label": "LED", "count": 0}],
                "props": [{"key": "uhd", "value": True, "label": "4K", "count": 5}, {"key": "uhd", "value": False, "label": "HD", "count": 0}],
                "attrs": {"screen_in": {"values": [{"value": 55, "label": "55 pouces", "count": 3}, {"value": 65, "label": "65 pouces", "count": 5}]}}}
        said = lambda qs: [(q["title"], [o["label"] for o in q["options"]]) for q in qs]
        self.assertEqual(said(funnel.questions({}, d, {}, opts, [100] * 5, 5)), [("Taille d'écran ?", ["55 pouces"])])
        two = {**opts, "subs": [{"key": "oled", "label": "OLED", "count": 3}, {"key": "led", "label": "LED", "count": 2}]}
        self.assertEqual(said(funnel.questions({}, d, {}, two, [100] * 5, 5))[0], ("Quel type ?", ["OLED", "LED"]))
        self.assertEqual(said(funnel.questions({"sub": "oled"}, d, {}, two, [100] * 5, 5)), [("Taille d'écran ?", ["55 pouces"])])
        kitchen = {c: 1 for c in ("refrigerateur", "congelateur", "four", "plaque_cuisson", "hotte", "lave_vaisselle", "cuisiniere")}
        self.assertEqual(said(funnel.questions({}, None, kitchen, None, [100] * 7, 7))[0][0], "Quel rayon ?")   # une seule pièce : pas d'univers


    def test_budgets_split_the_prices(self):
        self.assertEqual(funnel.budgets([100, 150, 300, 700, 900, 1200], 6), [(100, 1), (300, 3), (700, 4), (1000, 5)])
        self.assertEqual(funnel.budgets([120, 130], 2), [])                      # aucun seuil ne sépare 120 et 130
        self.assertEqual(funnel.budgets([90, 170], 2), [(100, 1)])               # 100 et 150 donnent la même chose : le plus bas
        for prices in ([49, 51, 99, 101, 149, 151, 199, 4999], [1000] * 9 + [10]):
            for t, n in funnel.budgets(prices, len(prices)):
                self.assertTrue(0 < n < len(prices))

    def test_few_products_is_the_end(self):
        self.assertEqual(funnel.questions({}, None, {"televiseur": 3}, None, [100, 200, 300], 3), [])
        self.assertTrue(funnel.questions({}, None, {"televiseur": 2, "canape": 2}, None, [100, 200, 300, 400], 4))

    def test_implied(self):
        self.assertEqual(funnel.implied({"televiseur": 4}, 4), {"category": "televiseur"})
        self.assertEqual(funnel.implied({"aspirateur": 3, "robot_aspirateur": 2}, 5), {"domain": "aspirateurs"})
        self.assertIsNone(funnel.implied({"aspirateur": 3, "televiseur": 2}, 5))
        self.assertIsNone(funnel.implied({"televiseur": 4}, 6))                  # deux produits hors de tout rayon : on ne dit rien
        self.assertEqual(funnel.implied({"televiseur": 4, "canape": 2}, 2, room="salon"), {"category": "canape"})
        self.assertEqual((funnel.own_sub("robot_aspirateur"), funnel.own_sub("aspirateur")), ("robot", None))
        self.assertEqual((funnel.reach("aspirateur"), funnel.reach("robot_aspirateur")),
                         ({"aspirateur", "robot_aspirateur"}, {"robot_aspirateur"}))


if __name__ == "__main__":
    unittest.main()
