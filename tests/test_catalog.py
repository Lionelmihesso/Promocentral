"""Où se situe le prix du jour (catalog.position, pur) : ce que la fiche affirme au consommateur doit être vrai.

« Au plus bas » seulement si aucun jour des trois derniers mois n'était moins cher et que le prix était plus haut au moins
un jour sur deux (un prix qui ne bouge pas n'est pas « au plus bas », il est habituel) ; « parmi les plus bas » si
moins cher qu'au moins 2 jours sur 3 ; « plus cher que d'habitude » si plus cher qu'au moins 2 jours sur 3 ; rien sans
au moins 14 jours relevés. La Recherche (Catalog.search) filtre par catégorie, budget et remise, même sans mot, et met
d'abord les produits dont la requête nomme la catégorie ou la marque ; sans mot ni filtre, elle montre un feed :
les produits des recherches récentes en tête, puis tout le catalogue, une catégorie à tour de rôle.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from deals import catalog
from deals import config
from deals.api import Api, Request
from deals.catalog import Catalog, haystack, position
from deals.extract import attributes, categorize
from deals.store import Store


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


class Search(unittest.TestCase):
    def setUp(self):
        self.s = Store(Path(tempfile.mkdtemp(), "c.sqlite"))
        rows = [(1, "Robot aspirateur laveur S8", "Brava", 299, 30), (2, "Lave-linge hublot 9 kg classe A", "Kessler", 449, 0),
                (3, "Lave-vaisselle 60 cm 13 couverts", "Helio", 389, 10), (4, "Lave-linge hublot 8 kg", "Ostra", 549, 15),
                (5, "Sèche-linge Zenit 8 kg à superposer avec Ostra", "Zenit", 399, 40)]
        with self.s.tx() as c:
            for pid, title, brand, price, pct in rows:
                cat = categorize(title)[0]
                c.execute("INSERT INTO catalog(product_id, name, title, brand, category, price, pct, search, published_on, attrs) "
                          "VALUES (?,?,?,?,?,?,?,?,?,?)", (pid, title, title, brand, cat, price, pct, haystack(title, brand, "Site", cat),
                                                         "2026-10-24", json.dumps(attributes(title))))
        self.c = Catalog(self.s)

    def tearDown(self):
        self.s.close()

    def ids(self, **kw):
        return [p["id"] for p in self.c.search(**kw)["products"]]

    def test_relevance_names_first(self):
        self.assertEqual(self.ids(q="lave"), [4, 3, 2, 1])               # « laveur » trouvé, mais après les lave-linge et lave-vaisselle
        self.assertEqual(self.ids(q="lave", sort="discount"), [1, 4, 3, 2])
        self.assertEqual(self.ids(q="lave", sort="price"), [1, 3, 2, 4])
        self.assertEqual(self.ids(q="ostra"), [4])                        # la marque nommée : ses produits (le Zenit « avec Ostra » n'en est pas)
        self.assertEqual(self.ids(q="superposer"), [5])                   # rien de compris : mot à mot

    def test_a_phrase_is_understood_as_criteria(self):
        out = self.c.search(q="Je veux un lave-linge 9 kg à moins de 500 €")
        self.assertEqual([p["id"] for p in out["products"]], [2])        # le 8 kg à 549 € n'y répond pas
        self.assertEqual([c["label"] for c in out["chips"]], ["Lave-linge", "9 kg et plus", "Moins de 500 €"])
        self.assertEqual((out["criteria"]["domain"], out["criteria"]["attrs"], out["criteria"]["max_price"], out["words"]),
                         ("lave_linge", {"capacity_kg": 9}, 500, []))       # v59 : le rayon a son ontologie
        self.assertEqual(self.ids(q="lave-linge 9 kg", attrs={"capacity_kg": 8}), [4, 2])   # le critère choisi l'emporte sur la phrase
        self.assertEqual(self.ids(q="sèche-linge pas cher"), [5])
        self.assertEqual(self.ids(q="lave linge en promo"), [4])          # « en promo » : une remise
        cheap = self.c.search(q="lave-linge sous 400 €")                  # rien sous le budget : les plus proches au-dessus
        self.assertEqual(([p["id"] for p in cheap["products"]], cheap["relaxed"]), ([2, 4], {"max_price": 400, "from": 449}))
        dyson = self.c.search(q="lave-linge dyson")                       # un mot qui ne trouve rien : signalé, le reste tient
        self.assertEqual(([p["id"] for p in dyson["products"]], dyson["ignored"]), ([4, 2], ["dyson"]))
        hublot = self.c.search(q="lave-linge hublot 8 kg")                # v59 : un type du rayon, plus un mot cherché
        self.assertEqual(([p["id"] for p in hublot["products"]], hublot["words"], hublot["criteria"]["sub"]), ([4, 2], [], "hublot"))
        phone = self.c.search(q="smartphone sous 300 €")                  # v59 : suivi, rien ici
        self.assertEqual((phone["products"], phone["unsupported"]), ([], None))
        oven = self.c.search(q="micro-ondes sous 150 €")                  # pas suivi : on le dit, rien d'autre
        self.assertEqual((oven["products"], oven["unsupported"]), ([], "Micro-ondes"))

    def test_the_api_takes_criteria_chosen_in_the_app(self):
        api = Api(self.s, config.load({}))
        get = lambda **q: api.handle(Request("GET", "/api/r/search", q))
        out = get(q="lave-linge", attr="capacity_kg:9").body                  # la puce choisie : 9 kg et plus
        self.assertEqual(([p["id"] for p in out["products"]], out["criteria"]["attrs"]), ([2], {"capacity_kg": 9}))
        self.assertEqual([p["id"] for p in get(brand="Brava").body["products"]], [1])
        self.assertEqual([p["id"] for p in get(feat="laveur").body["products"]], [1])
        self.assertEqual([p["id"] for p in get(q="robot aspirateur", sort="price").body["products"]], [1])
        both = get(q="aspirateur").body                                        # les aspirateurs : le domaine entier, robots compris
        self.assertEqual(([p["id"] for p in both["products"]], both["chips"]), ([1], [{"id": "domain", "label": "Aspirateurs"}]))
        self.assertEqual([p["id"] for p in get(domain="aspirateurs", sub="robot", prop="cordless:1").body["products"]], [1])
        self.assertEqual(get(domain="aspirateurs", prop="bagless:0").body["criteria"]["props"], {"bagless": False})
        for bad in ({"sub": "robot"}, {"domain": "jardin"}, {"domain": "aspirateurs", "sub": "fusee"},
                    {"domain": "aspirateurs", "prop": "weight_kg:1"}, {"domain": "televiseur", "prop": "screen_in:1"}):   # une mesure : pas un oui/non
            self.assertEqual(get(**bad).status, 400, bad)
        self.assertEqual(get(off="20").body["chips"], [{"id": "off", "label": "−20 % et plus"}])   # un palier de promo, dit en entier
        self.assertEqual(get(q="lave-linge", attr="energy_class:a").body["criteria"]["attrs"], {"energy_class": "A"})
        for bad in ({"feat": "volant"}, {"attr": "couleur:rouge"}, {"sort": "hasard"}, {"max": "beaucoup"}):
            self.assertEqual(get(**bad).status, 400, bad)

    def test_filters_even_without_words(self):
        self.assertEqual(self.ids(hi=450), [5, 1, 3, 2])                  # budget seul : les remises d'abord, puis le prix
        self.assertEqual(self.ids(off=15), [5, 1, 4])                     # remise minimale
        self.assertEqual(self.ids(q="lave", category="lave_linge", lo=500), [4])
        facet = {c["key"]: c["count"] for c in self.c.search(q="lave")["categories"]}
        self.assertEqual(facet, {"lave_linge": 2, "lave_vaisselle": 1, "robot_aspirateur": 1})   # chaque catégorie, ce qu'elle donnerait
        facet = {c["key"]: c["count"] for c in self.c.search(q="lave", category="lave_linge")["categories"]}
        self.assertEqual(facet, {"lave_linge": 2})                        # v59 : un rayon choisi est un domaine, ses seules catégories

    def test_feed_shows_the_breadth_of_the_catalog(self):
        out = self.c.search()                                             # ni mot ni filtre : le feed, jamais vide
        self.assertEqual(([p["id"] for p in out["products"]], out["total"], out["recent"]), ([4, 5, 1, 3, 2], 5, []))
        # une catégorie à tour de rôle : d'abord celle qui offre le plus de choix (lave-linge, sa remise d'abord), puis
        # les autres selon leur meilleur produit ; le second lave-linge au tour suivant
        self.assertEqual(self.ids(sort="price"), [1, 3, 5, 2, 4])          # un tri choisi s'applique au feed
        self.assertEqual(self.ids(hi=600), [5, 1, 4, 3, 2])               # un filtre, même s'il garde tout : la pertinence
        for kw in ({"category": "lave_linge"}, {"lo": 1}, {"hi": 1000}, {"off": 1}):
            self.assertEqual(self.c.search(recent=["lave"], **kw)["recent"], [], kw)   # les recherches passées : feed seulement

    def test_feed_follows_recent_searches(self):
        out = self.c.search(recent=["lave", "ostra"])                     # la plus récente d'abord, à tour de rôle, sans doublon
        self.assertEqual(([p["id"] for p in out["products"]], out["recent"]), ([4, 3, 5, 2, 1], ["lave", "ostra"]))
        out = self.c.search(recent=["xyzzy", "de la", "zenit"])            # seules comptent celles qui trouvent quelque chose
        self.assertEqual(([p["id"] for p in out["products"]], out["recent"]), ([5, 4, 1, 3, 2], ["zenit"]))
        self.assertEqual(self.c.search(recent=["a1", "a2", "a3", "a4", "zenit"])["recent"], [])     # les 4 dernières seulement
        self.assertEqual(self.ids(q="lave", recent=["ostra"]), [4, 3, 2, 1])   # une requête : les recherches passées n'y font rien
        with mock.patch.object(catalog, "RECENT_EACH", 2):                # au plus RECENT_EACH par recherche, puis le catalogue
            self.assertEqual(self.ids(recent=["lave"]), [4, 3, 5, 1, 2])


class Refine(unittest.TestCase):
    """Affiner : chaque choix dit ce que la recherche donnerait avec lui, ses autres critères gardés ; un choix qui ne donne
    rien ou ne change rien n'est pas proposé, sauf s'il est pris."""
    ROWS = [(1, "Canapé d'angle convertible 5 places", "Nordvik", 899, 20), (2, "Canapé d'angle 4 places", "Nordvik", 1290, 0),
            (3, "Canapé d'angle convertible 3 places", "Varenne", 749, 10), (4, "Canapé 3 places velours", "Lumen", 599, 0),
            (5, "Canapé convertible 2 places", "Varenne", 499, 0), (6, "Lit coffre 160x200", "Nordvik", 699, 0)]

    def setUp(self):
        self.s = Store(Path(tempfile.mkdtemp(), "r.sqlite"))
        with self.s.tx() as c:
            for pid, title, brand, price, pct in self.ROWS:
                cat = categorize(title)[0]
                c.execute("INSERT INTO catalog(product_id, name, title, brand, category, price, pct, search, published_on, attrs) "
                          "VALUES (?,?,?,?,?,?,?,?,?,?)", (pid, title, title, brand, cat, price, pct,
                                                         haystack(title, brand, "Site", cat), "2026-10-24", json.dumps(attributes(title, None, cat))))
        self.c = Catalog(self.s)

    def tearDown(self):
        self.s.close()

    def options(self, **kw):
        """→ (types, attributs oui/non, mesures, marques) : v59, chaque rayon suivi a son ontologie (un canapé : d'angle,
        modulable, droit ; convertible ; ses places)."""
        o = self.c.search(**kw)["options"]
        return ([(f["label"], f["count"]) for f in o.get("subs", [])] + [(f["label"], f["count"]) for f in o["features"]],
                [(f["label"], f["count"]) for f in o.get("props", [])],
                {k: [(v["label"], v["count"]) for v in a["values"]] for k, a in o["attrs"].items()},
                [(b["name"], b["count"]) for b in o["brands"]])

    def test_each_choice_counts_what_it_would_give(self):
        self.assertEqual(self.options(q="canapé d'angle"),
                         ([("D'angle", 3)], [("Convertible", 2)],           # pris ; « Convertible » en donnerait 2
                          {"seats": [("4 places et plus", 2), ("5 places et plus", 1)]},   # « 3 places et plus » : les trois, rien ne change
                          [("Nordvik", 2), ("Varenne", 1)]))
        self.assertEqual(self.options(q="canapé d'angle", attrs={"seats": 4})[1:],
                         ([("Convertible", 1)], {"seats": [("4 places et plus", 2), ("5 places et plus", 1)]}, [("Nordvik", 2)]))
        self.assertEqual(self.options(q="canapé", brand="Varenne")[:2], ([("D'angle", 1)], []))   # chez Varenne, tout est convertible : seul le type change
        self.assertEqual(self.options(q="canapé sous 800 €")[:2], ([("D'angle", 1)], [("Convertible", 2)]))
        self.assertEqual(self.options(q="canapé d'angle sous 100 €"), self.options(q="canapé d'angle"))   # au-dessus du budget : ce qui est montré
        self.assertEqual(self.options(q="pour la chambre"), ([], [], {}, [("Nordvik", 1)]))   # une pièce : ses marques
        self.assertEqual(self.options(q="pour le salon"), self.options(q="canapé"))   # v60 : une pièce qui n'a qu'un rayon y entre
        self.assertEqual(self.options(q="canapé en promo")[:2], ([("D'angle", 2)], []))  # la promo demandée compte : deux d'angle convertibles
        self.assertEqual(self.options(q="canapé velours"), ([], [], {}, [("Lumen", 1)]))   # les mots aussi
        self.assertEqual(self.options(q="canapé d'angle", attrs={"seats": 3})[2],         # pris, même s'il ne change rien
                         {"seats": [("3 places et plus", 3), ("4 places et plus", 2), ("5 places et plus", 1)]})
        self.assertEqual(self.options(q="canapé d'angle", attrs={"seats": 8})[2],         # pris, même s'il ne donne rien
                         {"seats": [("4 places et plus", 2), ("5 places et plus", 1), ("8 places et plus", 0)]})
        self.assertIn(("Ostra", 0), self.options(q="canapé", brand="Ostra")[3])
        self.assertEqual(self.options(q="canapé d'angle", attrs={"seats": 4.5})[2],       # pris, la valeur d'aucun produit : ce qu'il donne
                         {"seats": [("4 places et plus", 2), ("4,5 places et plus", 1), ("5 places et plus", 1)]})
        with self.s.tx() as c:                                                   # la nuit suivante : une taille relue
            c.execute("UPDATE catalog SET attrs=? WHERE product_id=3", (json.dumps({"sub": "angle", "convertible": True, "seats": 4}),))
            c.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('published_at', '2')")
        self.assertEqual(self.options(q="canapé d'angle")[2], {"seats": [("5 places et plus", 1)]})

    def test_the_phrase_alone_is_given_back(self):
        """said : ce que la phrase seule demande, pour que l'app en fasse ses critères quand on touche une puce."""
        out = self.c.search(q="aspirateur balai sans fil sous 200 € en promo", brand="Helio")
        self.assertEqual(out["said"], {"category": None, "room": None, "brand": None, "features": [], "attrs": {},
                                       "min_price": None, "max_price": 200, "off": 1, "low": False, "sort": None,
                                       "domain": "aspirateurs", "sub": "balai", "props": {"cordless": True}})
        self.assertEqual(out["criteria"]["brand"], "Helio")


class Domain(unittest.TestCase):
    """Les aspirateurs, domaine à ontologie : le domaine entier (robots compris) tant qu'aucun type n'est nommé ; un type et
    deux attributs (sans fil, sans sac), lus dans l'offre ou ce que le type est par définition, rien de deviné ; Affiner
    par type et par attribut, chaque choix avec ce qu'il donnerait."""
    ROWS = [  # id, titre, marque, prix, remise, catégorie déclarée par l'enseigne
        (1, "Aspirateur balai sans fil Zephyr V15 60 min", "Zephyr", 449, 0, None),
        (2, "Aspirateur balai filaire Kessler Flex", "Kessler", 259, 20, None),
        (3, "Helio Agile", "Helio", 179, 0, "Électroménager > Aspirateur > Aspirateur balai"),   # le flux dit le type
        (4, "Aspirateur traîneau sans sac Ostra Silence", "Ostra", 229, 10, None),
        (5, "Robot aspirateur laveur Ostra S8", "Ostra", 549, 0, None),
        (6, "Robot aspirateur Brava R5", "Brava", 329, 15, None),
        (7, "Aspirateur à main Helio H3", "Helio", 59, 0, None),
        (8, "Lave-linge hublot 9 kg", "Kessler", 449, 0, None),
        (9, "Aspirateur traîneau avec sac Kessler Eco", "Kessler", 99, 0, None),
        (10, "Kessler K2", "Kessler", 129, 0, "Électroménager > Aspirateur")]                  # rien ne dit le type

    def setUp(self):
        self.s = Store(Path(tempfile.mkdtemp(), "j.sqlite"))
        with self.s.tx() as c:
            for pid, title, brand, price, pct, declared in self.ROWS:
                cat = categorize(title, declared)[0]
                c.execute("INSERT INTO catalog(product_id, name, title, brand, category, price, pct, search, published_on, attrs) "
                          "VALUES (?,?,?,?,?,?,?,?,?,?)", (pid, title, title, brand, cat, price, pct, haystack(title, brand, "Site", cat),
                                                         "2026-10-24", json.dumps(attributes(title, None, cat, declared))))
        self.c = Catalog(self.s)

    def tearDown(self):
        self.s.close()

    def ids(self, **kw):
        return [p["id"] for p in self.c.search(**kw)["products"]]

    def test_the_domain_its_types_and_two_attributes(self):
        self.assertEqual(sorted(self.ids(q="aspirateur")), [1, 2, 3, 4, 5, 6, 7, 9, 10])            # robots compris, pas le lave-linge
        self.assertEqual(sorted(self.ids(q="aspirateur balai")), [1, 2, 3])                         # le type dit par le flux compte
        self.assertEqual(self.ids(q="aspirateur balai sans fil"), [1])                               # Helio Agile : rien ne le dit, pas promis
        self.assertEqual(sorted(self.ids(q="aspirateur sans fil")), [1, 5, 6, 7])                    # robots et aspirateurs à main : par définition
        self.assertEqual(sorted(self.ids(q="aspirateur sans sac")), [1, 2, 3, 4, 5, 6, 7])           # balais : sans sac par définition
        self.assertEqual(self.ids(q="aspirateur traîneau avec sac"), [9])
        self.assertEqual(self.ids(q="aspirateur sans fil avec sac"), [])                             # les deux exigés, pas l'un ou l'autre
        out = self.c.search(q="robot aspirateur laveur")
        self.assertEqual((sorted(p["id"] for p in out["products"]), out["chips"]), ([5, 6], [{"id": "sub", "label": "Robots aspirateurs"}]))
        out = self.c.search(q="aspirateur pour mon chat")                                           # un besoin n'est pas un critère : dit ignoré
        self.assertEqual((out["ignored"], len(out["products"])), (["chat"], 9))

    def test_a_category_of_the_domain_is_the_domain_and_its_type(self):
        out = self.c.search(category="robot_aspirateur")
        self.assertEqual((out["criteria"]["category"], out["criteria"]["domain"], out["criteria"]["sub"], out["chips"]),
                         (None, "aspirateurs", "robot", [{"id": "sub", "label": "Robots aspirateurs"}]))
        self.assertEqual(self.c.search(q="aspirateur sans sac")["criteria"]["props"], {"bagless": True})
        self.assertEqual(self.c.search(q="aspirateur sans sac", props={"cordless": True})["criteria"]["props"], {"bagless": True, "cordless": True})
        self.assertEqual(self.c.search(q="aspirateur sans sac", props={"bagless": False})["criteria"]["props"], {"bagless": False})   # le choix fait dans l'app l'emporte
        self.assertEqual([c["label"] for c in self.c.search(q="aspirateur balai filaire")["chips"]], ["Aspirateurs balais", "Avec fil"])

    def test_refine_by_type_and_attribute_each_with_what_it_gives(self):
        o = self.c.search(q="aspirateur")["options"]
        self.assertEqual([(x["label"], x["count"]) for x in o["subs"]], [("Balai", 3), ("Robot", 2), ("Traîneau", 2), ("À main", 1)])
        self.assertEqual([(x["label"], x["count"]) for x in o["props"]], [("Sans fil", 4), ("Avec fil", 1)])   # commun à plusieurs types
        o = self.c.search(q="aspirateur balai")["options"]
        self.assertEqual([x["key"] for x in o["subs"]], ["balai", "robot", "traineau", "main"])    # les autres types restent proposés
        self.assertEqual([(x["label"], x["count"]) for x in o["props"]], [("Sans fil", 1), ("Avec fil", 1)])   # Helio Agile : inconnu
        self.assertEqual(sorted(b["name"] for b in o["brands"]), ["Helio", "Kessler", "Zephyr"])   # les marques de ce type seul
        o = self.c.search(q="aspirateur sans fil")["options"]                                       # chaque type compte ce qui est sans fil
        self.assertEqual([(x["key"], x["count"]) for x in o["subs"]], [("robot", 2), ("main", 1), ("balai", 1)])
        o = self.c.search(q="aspirateur traîneau sans fil")["options"]                              # aucun : le type choisi reste, pour le retirer
        self.assertIn(("traineau", 0), [(x["key"], x["count"]) for x in o["subs"]])
        o = self.c.search(q="aspirateur balai", props={"bagless": True})["options"]                 # exigé hors des attributs du type : proposé
        self.assertIn(("Sans sac", 3), [(x["label"], x["count"]) for x in o["props"]])
        self.assertEqual(self.c.search(q="aspirateur balai", brand="Zephyr")["options"]["props"], [])   # un choix qui ne change rien : pas proposé
        self.assertEqual(self.c.search(q="aspirateur balai", sub="traineau")["criteria"]["sub"], "traineau")   # le type choisi dans l'app l'emporte
        self.assertEqual((self.c.search(q="aspirateur")["domain"], self.c.search(q="lave-linge")["domain"]),
                         ({"key": "aspirateurs", "label": "Aspirateurs", "categories": ["aspirateur", "robot_aspirateur"]},
                          {"key": "lave_linge", "label": "Lave-linge", "categories": ["lave_linge"]}))   # v59 : chaque rayon
        self.assertEqual(self.c.search(q="robot aspirateur")["domain"]["categories"], ["robot_aspirateur"])   # son type : son rayon (Affiner)
        o = self.c.search(q="aspirateur traîneau", props={"bagless": True})["options"]
        self.assertEqual([(x["label"], x["count"]) for x in o["props"] if x["key"] == "bagless"], [("Sans sac", 1), ("Avec sac", 1)])
        o = self.c.search(q="aspirateur traîneau")["options"]                                       # un traîneau : sans sac, ou non
        self.assertEqual([(x["label"], x["count"]) for x in o["props"]], [("Sans sac", 1), ("Avec sac", 1)])
        o = self.c.search(q="robot aspirateur")["options"]
        self.assertEqual(o["props"], [])                                                            # un robot : rien à choisir
        self.assertEqual(self.c.search(q="robot aspirateur", props={"cordless": True})["options"]["props"],
                         [{"key": "cordless", "value": True, "label": "Sans fil", "count": 2}])     # exigé : reste proposé, pour le retirer

    def test_the_product_page_says_nothing_more(self):
        item = self.c.item(None, 1)
        self.assertEqual((item["attrs"]["sub"], item["attrs"]["cordless"]), ("balai", True))
        self.assertFalse({"facts", "digest", "essentials", "history", "position"} & set(item))   # v60 : ni courbe ni jauge


class Top(unittest.TestCase):
    """Top deals : les plus fortes remises et les prix parmi les plus bas depuis longtemps, à tour de rôle ; le filtre
    Promo de la Recherche (paliers de remise, prix bas) et le nombre de produits de chaque choix."""
    ROWS = [  # id, remise, prix, verdict, jours relevés, prix habituel, marque, catégorie
        (1, 30, 299, "lowest", 75, 400, "Brava", "aspirateur"),   # remise et prix bas (25 % sous l'habituel)
        (2, 0, 440, "low", 75, 500, "Kessler", "lave_linge"),     # prix bas sans remise (12 %)
        (3, 12, 380, "usual", 75, 430, "Helio", "lave_linge"),    # remise seulement
        (4, 0, 300, "low", 30, 400, "Ostra", "lave_linge"),       # trop peu de jours relevés
        (5, 0, 380, "lowest", 90, 400, "Zenit", "four"),          # au plus bas, mais 5 % seulement sous l'habituel
        (6, 15, 600, None, None, None, "Dormea", "matelas"),      # remise, historique trop court pour un verdict
        (7, 0, 500, "high", 75, 450, "Nordvik", "lit"),
        (8, 0, 180, "lowest", 60, 200, "Lumen", "hotte")]          # deux mois tout juste, 10 % tout juste

    def setUp(self):
        self.s = Store(Path(tempfile.mkdtemp(), "t.sqlite"))
        with self.s.tx() as c:
            for pid, pct, price, level, span, usual, brand, cat in self.ROWS:
                c.execute("INSERT INTO catalog(product_id, name, title, brand, category, price, pct, search, published_on, attrs, "
                          "level, span, usual) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (pid, f"P{pid}", f"P{pid}", brand, cat, price, pct, f" p{pid} {cat.replace('_', ' ')} ", "2026-10-24", "{}",
                           level, span, usual))
        self.c = Catalog(self.s)

    def tearDown(self):
        self.s.close()

    def test_the_low_price_rule(self):
        self.assertEqual([r[0] for r in self.ROWS if catalog.cheap(dict(zip(("product_id", "pct", "price", "level", "span", "usual"), r)))],
                         [1, 2, 8])

    def test_top_deals_alternate_discounts_and_low_prices(self):
        top = self.c.top()["products"]
        self.assertEqual([p["id"] for p in top], [1, 6, 2, 3, 8])      # remise, remise, prix bas, remise, prix bas ; sans doublon
        self.assertEqual([p["why"] for p in top], [{"pct": 30, "low": "lowest", "days": 75}, {"pct": 15, "low": None, "days": None},
                                                    {"pct": 0, "low": "low", "days": 75}, {"pct": 12, "low": None, "days": None},
                                                    {"pct": 0, "low": "lowest", "days": 60}])
        with mock.patch.object(catalog, "TOP_LIMIT", 3):
            self.assertEqual([p["id"] for p in self.c.top()["products"]], [1, 6, 2])
        uid = self.s.x("INSERT INTO users(email, created_at) VALUES ('mia@test.local', 0)")
        self.s.x("INSERT INTO follows(user_id, brand, created_at) VALUES (?, 'Helio', 0)", (uid,))
        self.assertEqual([p["id"] for p in self.c.top(uid)["products"]][:3], [1, 3, 2])   # une marque suivie : 12 × 1,5 > 15

    def test_top_deals_of_one_universe(self):
        """v66 : Top deals par univers (les puces de l'onglet : Électroménager ; Maison = ameublement et literie ;
        High-tech) : la même règle, sur les seuls produits de l'univers ; sans univers, rien ne change."""
        self.assertEqual([p["id"] for p in self.c.top(families={"electromenager"})["products"]], [1, 3, 2, 8])
        self.assertEqual([p["id"] for p in self.c.top(families={"ameublement", "literie"})["products"]], [6])
        self.assertEqual(self.c.top(families={"electronique"})["products"], [])
        self.assertEqual([p["id"] for p in self.c.top(families=None)["products"]], [1, 6, 2, 3, 8])

    def test_promo_filter_says_what_each_choice_gives(self):
        out = self.c.search()
        self.assertEqual(out["offs"], {"1": 3, "10": 3, "20": 1, "30": 1, "40": 0, "50": 0, "low": 3})
        self.assertEqual(sorted(p["id"] for p in self.c.search(low=True)["products"]), [1, 2, 8])
        self.assertEqual(self.c.search(off=20, low=True)["offs"], out["offs"])           # avant le filtre de promo
        self.assertEqual(self.c.search(category="lave_linge")["offs"], {"1": 1, "10": 1, "20": 0, "30": 0, "40": 0, "50": 0, "low": 1})
        self.assertEqual({c["key"] for c in self.c.search(low=True)["categories"]}, {"aspirateur", "lave_linge", "hotte"})
        self.assertEqual(self.c.search(low=True, recent=["p2"])["recent"], [])           # un filtre : ce n'est plus le feed


if __name__ == "__main__":
    unittest.main()
