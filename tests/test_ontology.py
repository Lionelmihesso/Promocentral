"""L'ontologie (deals/ontology) : une donnée versionnée, relue avant de servir ; ce qu'elle lit sur une page (la fiche
prime sur le titre, le nom du modèle est un indice plus faible, une valeur hors plage n'est pas lue) ; la sous-famille
d'un produit ; ce qu'un type entraîne et ce qui se déduit, jamais à la place d'un fait ; les critères (oui, en partie,
non, inconnu — et ce qu'un inconnu peut encore valoir) ; la phrase comprise. Et le chemin d'une page jusqu'au catalogue :
la fiche gardée, relue sous une ontologie révisée, la provenance publiée."""
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
        self.assertEqual((D.version, D.path, D.categories), ("1.0.0", ["Maison", "Entretien", "Aspirateurs"], ("aspirateur", "robot_aspirateur")))
        self.assertTrue(set(D.categories) <= {c for c, _ in CATEGORIES} & set(FAMILY_OF) & set(CATEGORY_LABEL))   # des rayons suivis
        self.assertEqual([s["key"] for s in D.subs], ["robot", "laveur", "main", "balai", "traineau"])   # l'ordre : le plus spécifique d'abord
        for n in D.needs.values():
            self.assertTrue(n.get("phrase") and n.get("say") and n["label"], n["key"])
        for c in D.criteria.values():                                          # chaque critère sert au moins un besoin
            self.assertTrue(any(c["key"] in n["criteria"] for n in D.needs.values()), c["key"])

    def test_a_wrong_file_is_refused_with_where(self):
        def broken(edit):
            d = copy.deepcopy(RAW)
            edit(d)
            with self.assertRaises(O.OntologyError) as e:
                O.Domain(d, "essai.json")
            return str(e.exception)
        self.assertIn("schéma", broken(lambda d: d.update(schema=2)))
        self.assertIn("version", broken(lambda d: d.update(version="1.0")))
        self.assertIn("inconnue « poids »", broken(lambda d: d["subfamilies"][0]["decision"].append("poids")))
        self.assertIn("score 0.7", broken(lambda d: d["criteria"][0]["rules"][0].update(score=0.7)))
        self.assertIn("illisible", broken(lambda d: d["properties"][1]["titre"].append({"re": "(kg"})))
        self.assertIn("déjà pris", broken(lambda d: d["needs"][0]["words"].append("silencieux")))   # un mot, un sens
        self.assertIn("critère « vol »", broken(lambda d: d["needs"][0]["criteria"].update(vol="fort")))
        self.assertIn("ne lit pas", broken(lambda d: d["criteria"][0]["rules"][0].update(say="{weight_kg} kg")))
        self.assertIn("réponse", broken(lambda d: d["questions"][0]["options"].append({"label": "x", "apply": {"sub": "fusee"}})))


class Reading(unittest.TestCase):
    def test_the_sheet_first_then_the_title_then_the_name(self):
        vals, src = D.read("Aspirateur balai sans fil Zephyr V12 Animal 60 min 2,3 kg",
                           {"Poids net (kg)": "2.6", "Filtration": "HEPA H13", "Niveau sonore (dB)": "79 dB(A)", "Sac": "Sans sac",
                            "Puissance d'aspiration": "185 AW", "Couleur": "gris"})
        self.assertEqual(vals, {"weight_kg": 2.6, "hepa": True, "noise_db": 79, "bagless": True, "suction_aw": 185, "cordless": True,
                                "autonomy_min": 60, "pet_tool": True})
        self.assertEqual((src["weight_kg"], src["autonomy_min"], src["pet_tool"]), ("fiche", "titre", "nom"))   # la fiche prime sur « 2,3 kg »
        self.assertEqual(D.read("Aspirateur balai Kessler 2,3 kg"), ({"weight_kg": 2.3}, {"weight_kg": "titre"}))   # sans fiche : le titre

    def test_formats_units_and_ranges(self):
        read = lambda props, title="Robot aspirateur": D.read(title, props)[0]
        self.assertEqual(read({"Puissance d'aspiration": "4000 Pa"}), {"suction_pa": 4000})          # Pa : un robot ;
        self.assertEqual(read({"Puissance d'aspiration": "185 AW"}), {"suction_aw": 185})            # AW : un balai
        self.assertEqual(read({"Puissance": "4000"}), {})                                            # sans unité : pas des watts
        self.assertEqual(read({"Puissance d'aspiration": "185"}), {})                                # ni Pa ni AW : pas lu
        self.assertEqual(read({"Franchissement d'obstacles": "2 cm"}), {"climb_mm": 20})
        self.assertEqual(read({"Autonomie": "Jusqu'à 1 h"}), {"autonomy_min": 60})
        self.assertEqual(read({"Poids": "45 kg"}), {})                                               # hors plage : pas lu
        self.assertEqual(read({"Type de filtre": "Mousse lavable"}), {"hepa": False})                # un autre filtre : pas HEPA
        self.assertEqual(read({"Sac": "Non"}), {"bagless": True})
        self.assertEqual(read({"Navigation": "Laser (LiDAR)"}), {"navigation": "laser"})
        self.assertEqual(read({"Brosse anti-enchevêtrement": "Oui"}), {"pet_tool": True})            # tirets, accents
        self.assertEqual(read({"Station de vidage": "peut-être"}), {})                               # ni oui ni non : inconnu
        self.assertEqual(read({}, "Aspirateur traîneau filaire 750 W"), {"cordless": False, "power_w": 750})

    def test_functions_follow_the_sheet(self):
        self.assertIn("sans_fil", attributes("Aspirateur balai Kessler X", {"Alimentation": "Batterie"}, "aspirateur")["features"])
        a = attributes("Aspirateur balai sans fil Kessler X", {"Alimentation": "Secteur"}, "aspirateur")     # la fiche prime sur le titre
        self.assertEqual((a["cordless"], "sans_fil" in a["features"]), (False, False))
        self.assertEqual(attributes("Robot aspirateur Brava R5", {"Fonction lavage": "Oui"}, "robot_aspirateur")["features"], ["laveur"])

    def test_subfamily_rules_in_order(self):
        sub = lambda cat, title, feats=(): D.sub_of(cat, title, {"features": list(feats)})
        self.assertEqual(sub("robot_aspirateur", "Robot aspirateur laveur S8"), "robot")             # un robot qui lave reste un robot
        self.assertEqual(sub("aspirateur", "Aspirateur balai laveur Vela W2", ["balai", "laveur"]), "laveur")
        self.assertEqual(sub("aspirateur", "Nettoyeur de sols Vela W2"), "laveur")
        self.assertEqual(sub("aspirateur", "Aspirateur à main sans fil H3"), "main")
        self.assertEqual(sub("aspirateur", "Aspirateur balai 2 en 1 avec aspirateur à main amovible", ["balai"]), "balai")
        self.assertEqual(sub("aspirateur", "Aspirateur traîneau sans sac", ["traineau"]), "traineau")
        self.assertIsNone(sub("aspirateur", "Aspirateur Kessler X"))                                 # aucun indice : sans type
        self.assertIsNone(sub("lave_linge", "Lave-linge 9 kg"))


class Facts(unittest.TestCase):
    def test_the_type_and_deductions_never_replace_a_fact(self):
        f = D.facts({"sub": "robot", "navigation": "laser", "_src": {"navigation": "fiche"}})
        self.assertEqual((f["cordless"], f["mapping"], f["navigation"]), ((True, "type"), (True, "deduit"), ("laser", "fiche")))
        f = D.facts({"sub": "balai", "autonomy_min": 45, "cordless": False})        # un fait contraire : il prime
        self.assertEqual(f["cordless"], (False, "titre"))
        self.assertNotIn("hepa", D.facts({"sub": "balai"}))                         # rien dit, rien déduit : inconnu
        self.assertEqual(D.facts({"sub": "balai", "bagless": False, "_src": {"bagless": "fiche"}})["bagless"], (False, "fiche"))   # le type ne l'efface pas

    def test_criteria_yes_partly_no_unknown(self):
        judge = lambda c, attrs: D.judge(c, attrs.get("sub"), D.facts(attrs))[:2]
        self.assertEqual(judge("poils", {"sub": "balai", "pet_tool": True}), (1, "Brosse pour les poils"))
        self.assertEqual(judge("poils", {"sub": "balai", "motor_brush": True}), (0.5, "Brosse motorisée"))
        self.assertEqual(judge("poils", {"sub": "balai", "pet_tool": False, "motor_brush": False}), (0, "Pas de brosse pour les poils"))
        self.assertEqual(judge("poils", {"sub": "balai"}), (None, "Brosse pour les poils non précisée"))
        self.assertEqual(D.judge("poils", "balai", D.facts({"sub": "balai", "pet_tool": False}))[4], 0.5)   # au mieux : en partie
        self.assertEqual(judge("silence", {"sub": "traineau", "noise_db": 64}), (1, "64 dB"))
        self.assertEqual(judge("silence", {"sub": "traineau", "noise_db": 79}), (0, "79 dB : bruyant"))
        self.assertEqual(judge("silence", {"sub": "robot", "noise_db": 70}), (1, "70 dB"))            # 70 dB au plus : 70 compris
        self.assertEqual(judge("silence", {"sub": "robot", "noise_db": 71}), (0.5, "71 dB"))
        self.assertEqual(judge("escaliers", {}), (None, "2 en 1 non précisé"))                        # sans type : rien de décidé
        both = D.facts({"sub": "balai", "handheld": True, "weight_kg": 2.4, "_src": {"handheld": "fiche", "weight_kg": "nom"}})
        self.assertEqual(D.judge("escaliers", "balai", both)[2], "nom")                               # la source la moins sûre des deux
        self.assertEqual(judge("maniabilite", {"sub": "balai", "weight_kg": 2.3}), (1, "2,3 kg"))
        self.assertEqual(judge("maniabilite", {"sub": "main"}), (1, "Un aspirateur à main pèse peu"))
        self.assertEqual(judge("couverture", {"sub": "balai", "cordless": False}), (1, "Avec fil : pas de limite d'autonomie"))
        self.assertEqual(judge("couverture", {"sub": "balai"}), (None, "Autonomie non précisée"))
        self.assertEqual(D.judge("escaliers", "robot", {})[:4], (0, "Un robot ne monte pas les marches", "type", True))
        self.assertEqual(judge("lavage", {"sub": "balai"}), (0, "Ne lave pas le sol"))               # un balai ne lave pas : le type le dit
        self.assertEqual(judge("cartographie", {"sub": "robot", "navigation": "camera"})[0], 1)
        self.assertEqual(judge("parquet", {"sub": "laveur"}), (0.5, "Parquet vitrifié seulement : il mouille le sol"))
        self.assertEqual(judge("poils", {}), (None, "Brosse pour les poils non précisée"))            # sans type ni fait


class Phrase(unittest.TestCase):
    def test_longest_first_in_the_order_said(self):
        u = D.understand(O.text("robot aspirateur qui se vide tout seul, l'auto-vidage, pour l'escalier"))
        self.assertEqual((u["sub"], [k for k, _ in u["needs"]]), ("robot", ["vidage", "escaliers"]))   # « auto » n'est pas la voiture
        u = D.understand(O.text("aspirateur silencieux pour allergiques"))
        self.assertEqual([k for k, _ in u["needs"]], ["silence", "allergies"])
        self.assertEqual(D.understand(O.text("aspirateur sans sac 2 en 1"))["props"], {"bagless": True, "handheld": True})
        self.assertEqual(O.detect(O.text("un balai pour les poils de chat")), D)
        self.assertIsNone(O.detect(O.text("canapé d'angle")))


class Pipeline(unittest.TestCase):
    """D'une page au catalogue : la fiche est gardée, relue à chaque publication sous l'ontologie en vigueur ; le
    catalogue publie la provenance (_src), la version (_v) et quand la fiche a été lue (_at)."""
    def setUp(self):
        self.s = Store(Path(tempfile.mkdtemp(), "o.sqlite"))

    def tearDown(self):
        self.s.close()

    def test_sheet_kept_reread_and_published_with_provenance(self):
        m = Market(self.s, clock=lambda: 1000.0)
        pid = m.match_product({"title": "Aspirateur balai sans fil Kessler Flex 2,6 kg", "brand": "Kessler", "gtin": "3000000000017",
                               "category": "aspirateur", "properties": {"poids": "2,4 kg", "filtre hepa": "Oui"}})
        a = json.loads(self.s.q("SELECT attributes FROM products WHERE id=?", (pid,), one=True)["attributes"])
        self.assertEqual((a["weight_kg"], a["hepa"], a["sub"], a["_src"]["weight_kg"], a["_v"], a["_at"]), (2.4, True, "balai", "fiche", "1.0.0", 1000.0))
        self.assertNotIn("capacity_kg", a)                                         # « 2,6 kg » : un poids, pas une capacité
        self.assertEqual(a["_props"], {"poids": "2,4 kg", "filtre hepa": "Oui"})
        m.clock = lambda: 2000.0                                                   # relue sans fiche : la fiche gardée sert encore
        m.match_product({"title": "Aspirateur balai sans fil Kessler Flex 2,6 kg", "brand": "Kessler", "gtin": "3000000000017", "category": "aspirateur"})
        a = json.loads(self.s.q("SELECT attributes FROM products WHERE id=?", (pid,), one=True)["attributes"])
        self.assertEqual((a["weight_kg"], a["hepa"], a["_at"]), (2.4, True, 1000.0))
        out = product_attributes("Aspirateur balai sans fil Kessler Flex 2,6 kg", "aspirateur", {**a, "capacity_kg": 2.6, "seats": 3})
        self.assertNotIn("capacity_kg", out)                                       # une lecture d'avant, sans sens ici : écartée
        legacy = product_attributes("Lave-linge 8 kg", "lave_linge", {"capacity_kg": 9, "energy_class": "B"})
        self.assertEqual((legacy["capacity_kg"], legacy["energy_class"]), (9, "B"))  # hors ontologie : ce qui est connu prime, comme avant

    def test_publish_rereads_the_kept_sheet(self):
        now = 1_760_000_000.0
        m = Market(self.s, clock=lambda: now)
        pid = m.match_product({"title": "Robot aspirateur Brava R5", "brand": "Brava", "gtin": "3000000000024", "category": "robot-aspirateur",
                               "properties": {"navigation": "LiDAR"}})
        oid = self.s.x("INSERT INTO offers(url, host, retailer, merchant, product_id, status, created_at) VALUES "
                       "('https://x.sim/p', 'x.sim', 'x', 'X', ?, 'active', 0)", (pid,))
        self.s.x("INSERT INTO prices(offer_id, first_seen, last_seen, price, availability) VALUES (?,?,?,?,?)", (oid, now - 86400, now, 329, "in_stock"))
        publish(self.s, date.fromtimestamp(now), now)
        a = json.loads(self.s.q("SELECT attrs FROM catalog", one=True)["attrs"])
        self.assertEqual((a["navigation"], a["sub"], a["_src"]["navigation"]), ("laser", "robot", "fiche"))
        self.assertNotIn("_props", a)                                              # la fiche brute reste côté produits


if __name__ == "__main__":
    unittest.main()
