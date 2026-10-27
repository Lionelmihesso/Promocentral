"""L'ontologie (deals/ontology) : une donnée versionnée, relue avant de servir ; ce qu'est un produit — sa catégorie, sa
sous-catégorie, deux attributs (sans fil, sans sac) — lu seulement dans ce qu'un flux affilié donne : le titre de l'offre
et sa catégorie déclarée ; rien de deviné ; ce qu'un type est par définition ; la phrase comprise. Et le chemin d'une
offre jusqu'au catalogue : la catégorie déclarée gardée, relue à chaque publication sous l'ontologie en vigueur."""
import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from deals import ontology as O
from deals.extract import attributes, product_attributes
from deals.extract.categories import CATEGORIES, FAMILY_OF
from deals.labels import CATEGORY_LABEL
from deals.market import Market
from deals.publish import publish
from deals.store import Store

D = O.DOMAINS["aspirateurs"]
RAW = json.loads((O.HERE / "aspirateurs.json").read_text(encoding="utf-8"))


class TheFile(unittest.TestCase):
    def test_it_loads_and_names_only_what_exists(self):
        self.assertEqual((D.version, D.categories), ("2.0.0", ("aspirateur", "robot_aspirateur")))
        self.assertTrue(set(D.categories) <= {c for c, _ in CATEGORIES} & set(FAMILY_OF) & set(CATEGORY_LABEL))   # des rayons suivis
        self.assertEqual([s["key"] for s in D.subs], ["robot", "laveur", "main", "balai", "traineau"])   # le plus précis d'abord
        self.assertEqual(sorted(D.attrs), ["bagless", "cordless"])                                    # deux attributs, pas plus

    def test_a_wrong_file_is_refused_with_where(self):
        def broken(edit):
            d = copy.deepcopy(RAW)
            edit(d)
            with self.assertRaises(O.OntologyError) as e:
                O.Domain(d, "essai.json")
            return str(e.exception)
        self.assertIn("schéma", broken(lambda d: d.update(schema=1)))
        self.assertIn("version", broken(lambda d: d.update(version="2.0")))
        self.assertIn("inconnu « poids »", broken(lambda d: d["subcategories"][3]["attributes"].append("poids")))
        self.assertIn("illisible", broken(lambda d: d["attributes"][0]["text"].append({"re": "(sans", "value": True})))
        self.assertIn("déjà pris", broken(lambda d: d["subcategories"][0]["words"].append("balai")))   # un mot, un sens
        self.assertIn("hors du domaine", broken(lambda d: d["subcategories"][0]["match"].update(category=["lave_linge"])))
        self.assertIn("oui (true) ou non", broken(lambda d: d["attributes"][1]["text"][0].update(value="oui")))
        self.assertIn("dit un texte", broken(lambda d: d["subcategories"][3]["match"]["any"].append({})))
        self.assertIn("sont requis", broken(lambda d: d["attributes"][0].pop("yes")))
        self.assertIn("inconnu « poids »", broken(lambda d: d["subcategories"][0]["implies"].update(poids=True)))


class Reading(unittest.TestCase):
    def test_the_type_from_the_title_or_the_declared_category(self):
        sub = lambda cat, title, declared=None: D.sub_of(cat, title, declared)
        self.assertEqual(sub("robot_aspirateur", "Robot aspirateur laveur S8"), "robot")             # le rayon suffit
        self.assertEqual(sub("aspirateur", "Aspirateur balai laveur Vela W2"), "laveur")             # le plus précis d'abord
        self.assertEqual(sub("aspirateur", "Aspirateur-balai sans fil X5"), "balai")
        self.assertEqual(sub("aspirateur", "Aspirateur à main sans fil H3"), "main")
        self.assertEqual(sub("aspirateur", "Aspirateur traîneau sans sac"), "traineau")
        self.assertEqual(sub("aspirateur", "Dyson V8 Absolute", "Électroménager > Aspirateur > Aspirateur balai"), "balai")   # le flux le dit
        self.assertEqual(sub("aspirateur", "Kessler K2", "Aspirateur à main"), "main")
        self.assertIsNone(sub("aspirateur", "Kessler K2", "Électroménager > Aspirateur"))            # rien ne le dit : pas deviné
        self.assertEqual(sub("aspirateur", "Kessler K2", "Petit électroménager > Aspirateur à main"), "main")   # chaque niveau lu
        self.assertEqual(sub("aspirateur", "Kessler K2", "Électroménager > Aspirateurs balais"), "balai")      # au pluriel
        self.assertEqual(sub("aspirateur", "Kessler C3", "Électroménager > Aspirateurs traîneaux"), "traineau")
        self.assertEqual(sub("aspirateur", "Aspirateur balai sans fil 2 en 1 avec aspirateur à main amovible"), "balai")   # un 2 en 1
        self.assertIsNone(sub("lave_linge", "Lave-linge 9 kg"))

    def test_two_attributes_said_by_the_offer_nothing_guessed(self):
        self.assertEqual(D.read("Aspirateur balai sans fil Zephyr V12"), {"cordless": True})
        self.assertEqual(D.read("Aspirateur traîneau filaire avec sac 750 W"), {"cordless": False, "bagless": False})
        self.assertEqual(D.read("Zephyr V12", "Aspirateurs > Aspirateurs sans sac"), {"bagless": True})   # la catégorie de l'enseigne
        self.assertEqual(D.read("Aspirateur balai sans-fil 60 min"), {"cordless": True})              # tirets
        self.assertEqual(D.read("Zephyr V12 Animal 2,3 kg HEPA"), {})                                 # le reste n'est pas lu
        self.assertEqual(D.read("Aspirateur traîneau à sac Ostra S3"), {"bagless": False})            # « à sac » : avec sac
        self.assertEqual(D.read("ASPIRATEUR BALAI SANS FIL"), {"cordless": True})                     # majuscules

    def test_what_a_feed_sends_that_is_not_a_vacuum_stays_out(self):
        from deals.extract import categorize
        for title, declared in (("Station de vidage pour robot aspirateur Helio", None), ("Sacs aspirateur x10", "Accessoires aspirateur"),
                                ("Batterie pour aspirateur balai", None), ("Balai vapeur Vela 1500 W", "Entretien des sols > Balais vapeur"),
                                ("Nettoyeur vapeur Vela S10", "Entretien des sols > Nettoyeurs vapeur")):
            self.assertIsNone(categorize(title, declared)[0], title)
        self.assertEqual(categorize("Nettoyeur de sols sans fil Vela F8")[0], "aspirateur")              # un aspirateur laveur
        self.assertEqual(D.sub_of("aspirateur", "Vela F8", "Électroménager > Nettoyeurs de sols"), "laveur")

    def test_the_offer_fills_the_attributes_and_the_function(self):
        a = attributes("Dyson V8 Absolute", None, "aspirateur", "Électroménager > Aspirateur balai sans fil")
        self.assertEqual((a["sub"], a["cordless"], a["features"]), ("balai", True, ["sans_fil"]))
        a = attributes("Aspirateur balai sans fil Kessler X filaire", None, "aspirateur")             # le premier dit l'emporte
        self.assertTrue(a["cordless"])
        self.assertNotIn("capacity_kg", attributes("Aspirateur balai Kessler 2,6 kg", None, "aspirateur"))   # pas un lave-linge


class Facts(unittest.TestCase):
    def test_what_a_type_is_never_replaces_what_the_offer_says(self):
        self.assertEqual(D.facts({"sub": "robot"}), {"cordless": True, "bagless": True})             # un robot : sans fil, sans sac
        self.assertEqual(D.facts({"sub": "balai", "cordless": False}), {"cordless": False, "bagless": True})
        self.assertEqual(D.facts({"sub": "traineau"}), {})                                           # un traîneau : rien par définition
        self.assertEqual(D.facts({"sub": "traineau", "bagless": False}), {"bagless": False})
        self.assertEqual(D.facts({"sub": "balai", "bagless": False}), {"bagless": False})           # l'offre dit « avec sac » : elle l'emporte
        self.assertEqual(D.facts({}), {})


class Phrase(unittest.TestCase):
    def test_types_and_attributes_longest_first(self):
        u = D.understand(O.text("aspirateur balai sans fil"))
        self.assertEqual((u["sub"], u["props"]), ("balai", {"cordless": True}))
        self.assertTrue(D.understand(O.text("aspirateur sans sac"))["domain"])
        self.assertEqual(D.understand(O.text("robot aspirateur laveur"))["sub"], "robot")             # le plus précis des deux types
        self.assertEqual(D.understand(O.text("aspirateur balai laveur"))["sub"], "laveur")
        self.assertEqual(D.understand(O.text("aspirateur traineau avec sac"))["props"], {"bagless": False})
        self.assertEqual(D.understand(O.text("aspirateur avec fil, ou sans fil"))["props"], {"cordless": False})   # le premier dit
        self.assertEqual(O.detect(O.text("un balai sans fil")), D)
        self.assertIsNone(O.detect(O.text("canapé d'angle")))


class Pipeline(unittest.TestCase):
    """D'une offre au catalogue : la catégorie déclarée est gardée, relue à chaque publication sous l'ontologie en vigueur ;
    ce qu'une version d'avant avait lu et qui n'a plus de sens est écarté."""
    def setUp(self):
        self.s = Store(Path(tempfile.mkdtemp(), "o.sqlite"))

    def tearDown(self):
        self.s.close()

    def test_declared_category_kept_reread_and_published(self):
        m = Market(self.s, clock=lambda: 1000.0)
        offer = {"title": "Kessler Flex 2,6 kg", "brand": "Kessler", "gtin": "3000000000017", "category": "Aspirateur > Aspirateur balai sans fil"}
        pid = m.match_product(offer)
        a = json.loads(self.s.q("SELECT attributes FROM products WHERE id=?", (pid,), one=True)["attributes"])
        self.assertEqual((a["sub"], a["cordless"], a["_cat"]), ("balai", True, "Aspirateur > Aspirateur balai sans fil"))
        self.assertNotIn("capacity_kg", a)                                         # « 2,6 kg » : pas une capacité
        m.match_product({**offer, "category": None})                               # relue sans catégorie : la gardée sert encore
        a = json.loads(self.s.q("SELECT attributes FROM products WHERE id=?", (pid,), one=True)["attributes"])
        self.assertEqual((a["sub"], a["cordless"]), ("balai", True))
        m.match_product({**offer, "category": "Aspirateur > Aspirateur balai filaire"})   # l'enseigne la change : la nouvelle sert
        a = json.loads(self.s.q("SELECT attributes FROM products WHERE id=?", (pid,), one=True)["attributes"])
        self.assertEqual((a["cordless"], a["_cat"]), (False, "Aspirateur > Aspirateur balai filaire"))
        old = {"sub": "balai", "pet_tool": True, "noise_db": 79, "_props": {"poids": "2 kg"}, "_src": {}, "_v": "1.0.0", "autonomy_min": 40,
               "features": ["balai", "sans_fil"]}                                  # « sans fil » déduit par la v57 : plus lu
        out = product_attributes("Aspirateur balai Kessler Flex", "aspirateur", old)
        self.assertEqual(out, {"sub": "balai", "features": ["balai"], "autonomy_min": 40})   # la v57 relue : ce qui n'a plus de sens, écarté
        now = product_attributes("Aspirateur traîneau sans sac Ostra", "aspirateur", {"sub": "balai", "bagless": False})
        self.assertEqual((now["sub"], now["bagless"]), ("traineau", True))          # une lecture gardée ne remplace pas l'offre du jour
        legacy = product_attributes("Lave-linge 8 kg", "lave_linge", {"capacity_kg": 9, "energy_class": "B"})
        self.assertEqual((legacy["capacity_kg"], legacy["energy_class"]), (9, "B"))  # hors ontologie : ce qui est connu prime, comme avant

    def test_publish_rereads_the_offer(self):
        now = 1_760_000_000.0
        m = Market(self.s, clock=lambda: now)
        pid = m.match_product({"title": "Brava R5", "brand": "Brava", "gtin": "3000000000024", "category": "Électroménager > Robot aspirateur"})
        oid = self.s.x("INSERT INTO offers(url, host, retailer, merchant, product_id, status, created_at) VALUES "
                       "('https://x.sim/p', 'x.sim', 'x', 'X', ?, 'active', 0)", (pid,))
        self.s.x("INSERT INTO prices(offer_id, first_seen, last_seen, price, availability) VALUES (?,?,?,?,?)", (oid, now - 86400, now, 329, "in_stock"))
        publish(self.s, date.fromtimestamp(now), now)
        a = json.loads(self.s.q("SELECT attrs FROM catalog", one=True)["attrs"])
        self.assertEqual(a, {"sub": "robot"})                                      # la catégorie gardée reste côté produits


if __name__ == "__main__":
    unittest.main()
