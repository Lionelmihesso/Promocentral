"""L'ontologie (deals/ontology) : une donnée versionnée, un fichier par famille (électroménager, électronique, ameublement,
literie), relue avant de servir ; ce qu'est un produit — sa catégorie, sa sous-catégorie (le type), un ou deux attributs
(oui ou non : sans fil, No Frost ; ou une mesure : capacité, taille d'écran) — lu seulement dans ce qu'un flux affilié
donne : le titre de l'offre et sa catégorie déclarée ; rien de deviné ; ce qu'un type est par définition ; la phrase
comprise. Et le chemin d'une offre jusqu'au catalogue : la catégorie déclarée gardée, relue à chaque publication sous
l'ontologie en vigueur."""
import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from deals import ontology as O
from deals import query
from deals.extract import attributes, categorize, product_attributes
from deals.extract.categories import CATEGORIES, FAMILIES, FAMILY_OF, MEASURES
from deals.labels import CATEGORY_LABEL
from deals.market import Market
from deals.publish import publish
from deals.store import Store

D = O.DOMAINS["aspirateurs"]
FILE = json.loads((O.HERE / "electromenager.json").read_text(encoding="utf-8"))
RAW = next(d for d in FILE["domains"] if d["domain"] == "aspirateurs")


class TheFiles(unittest.TestCase):
    def test_every_followed_category_has_one_domain_of_its_family(self):
        self.assertEqual(set(O.FAMILIES), set(FAMILIES))                                          # un fichier par famille suivie
        self.assertEqual(set(O.BY_CATEGORY), set(FAMILY_OF))                                      # chaque rayon suivi, une fois
        for c, d in O.BY_CATEGORY.items():
            self.assertEqual(d.family, FAMILY_OF[c], c)
            self.assertIn(c, {k for k, _ in CATEGORIES} & set(CATEGORY_LABEL), c)
        self.assertIsNone(O.domain_of("micro_ondes"))                                              # reconnu, pas suivi

    def test_the_pilot_domain_is_unchanged(self):
        self.assertEqual((D.version, D.family, D.categories), ("3.0.0", "electromenager", ("aspirateur", "robot_aspirateur")))
        self.assertEqual([s["key"] for s in D.subs], ["robot", "laveur", "main", "balai", "traineau"])   # le plus précis d'abord
        self.assertEqual(sorted(D.attrs), ["bagless", "cordless"])                                    # deux attributs, pas plus

    def test_a_few_attributes_per_domain_read_from_the_offer(self):
        for d in O.DOMAINS.values():
            self.assertLessEqual(len(d.attrs), 2, d.key)                                             # un ou deux, pas plus
            self.assertTrue(set(d.measures) <= set(MEASURES), d.key)                                 # une mesure que l'extracteur lit
        tv = O.DOMAINS["televiseur"]
        self.assertEqual(([s["key"] for s in tv.subs], tv.bools, tv.measures), (["oled", "mini_led", "qled", "led"], ["uhd"], ["screen_in"]))
        self.assertEqual(O.DOMAINS["console"].attrs["digital"]["compare"], "less")                   # une édition numérique : sans lecteur

    def test_every_name_shown_reads_back(self):
        """Ce que l'app montre (Affiner, les puces) se relit dans une recherche : le pluriel et le singulier de chaque type, le
        oui et le non de chaque attribut."""
        for key, d in O.DOMAINS.items():
            for s in d.subs:
                for label in (s["plural"], s["one"]):
                    r = query.read(label)
                    self.assertEqual((r["domain"], r["sub"], r["rest"]), (key, s["key"], []), label)
            for k in d.bools:
                for v in (True, False):
                    text = f"{d.one} {d.attrs[k]['yes' if v else 'no']}"
                    r = query.read(text)
                    self.assertEqual((r["domain"], r["props"].get(k), r["rest"]), (key, v, []), text)

    def test_a_wrong_file_is_refused_with_where(self):
        def broken(edit, family=False):
            f = copy.deepcopy(FILE)
            d = next(x for x in f["domains"] if x["domain"] == "aspirateurs")
            edit(f if family else d)
            with self.assertRaises(O.OntologyError) as e:
                O.check(f, "essai.json") if family else O.Domain(d, source="essai.json")
            return str(e.exception)
        self.assertIn("schéma", broken(lambda f: f.update(schema=2), family=True))
        self.assertIn("version", broken(lambda f: f.update(version="3.0"), family=True))
        self.assertIn("pas un rayon suivi de la famille", broken(lambda f: f.update(family="literie"), family=True))
        self.assertIn("inconnu « poids »", broken(lambda d: d["subcategories"][3]["attributes"].append("poids")))
        self.assertIn("illisible", broken(lambda d: d["attributes"][0]["text"].append({"re": "(sans", "value": True})))
        self.assertIn("déjà pris", broken(lambda d: d["subcategories"][0]["words"].append("balai")))   # un mot, un sens
        self.assertIn("hors du domaine", broken(lambda d: d["subcategories"][0]["match"].update(category=["lave_linge"])))
        self.assertIn("oui (true) ou non", broken(lambda d: d["attributes"][1]["text"][0].update(value="oui")))
        self.assertIn("dit un texte", broken(lambda d: d["subcategories"][3]["match"]["any"].append({})))
        self.assertIn("sont requis", broken(lambda d: d["attributes"][0].pop("yes")))
        self.assertIn("inconnu « poids »", broken(lambda d: d["subcategories"][0]["implies"].update(poids=True)))
        self.assertIn("ne sait pas lire", broken(lambda d: d["attributes"].append({"key": "poids_kg", "label": "Poids", "kind": "measure"})))
        self.assertIn("more, same ou less", broken(lambda d: d["attributes"][1].update(compare="mieux")))

    def test_a_category_described_twice_is_refused(self):
        folder = Path(tempfile.mkdtemp())
        for name in ("electromenager", "electronique", "ameublement", "literie"):
            (folder / f"{name}.json").write_text((O.HERE / f"{name}.json").read_text(encoding="utf-8"), encoding="utf-8")
        twice = copy.deepcopy(FILE)
        twice["domains"].append({**RAW, "domain": "aspirateurs_bis"})
        (folder / "electromenager.json").write_text(json.dumps(twice), encoding="utf-8")
        with self.assertRaisesRegex(O.OntologyError, "déjà décrit"):
            O.load(folder)


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
        self.assertIsNone(sub("lave_linge", "Lave-linge 9 kg"))                                      # pas un rayon de ce domaine

    def test_a_level_that_names_several_kinds_says_none(self):
        """« Commodes et chiffonniers », « Casques et écouteurs », « avec ou sans sac » : un rayon de l'enseigne qui en
        réunit plusieurs ne dit pas lequel est l'offre (v59)."""
        commode, casque = O.DOMAINS["commode"], O.DOMAINS["casque_audio"]
        self.assertIsNone(commode.sub_of("commode", "Commode Lina 5 tiroirs", "Chambre > Commodes et chiffonniers"))
        self.assertEqual(commode.sub_of("commode", "Semainier Aurel 7 tiroirs", "Commodes et chiffonniers"), "semainier")
        self.assertEqual(casque.sub_of("casque_audio", "Casque Bluetooth H300", "Image & Son > Casques et écouteurs"), "casque")
        self.assertIsNone(casque.sub_of("casque_audio", "Sonoryn H300", "Image & Son > Casques et écouteurs"))
        self.assertEqual(D.read("Aspirateur traîneau Ostra", "Entretien > Aspirateurs avec ou sans sac"), {})
        self.assertEqual(casque.sub_of("casque_audio", "Sonoryn Buds 3", "Image & Son > Écouteurs"), "ecouteurs")   # un seul : il le dit

    def test_two_attributes_said_by_the_offer_nothing_guessed(self):
        self.assertEqual(D.read("Aspirateur balai sans fil Zephyr V12"), {"cordless": True})
        self.assertEqual(D.read("Aspirateur traîneau filaire avec sac 750 W"), {"cordless": False, "bagless": False})
        self.assertEqual(D.read("Zephyr V12", "Aspirateurs > Aspirateurs sans sac"), {"bagless": True})   # la catégorie de l'enseigne
        self.assertEqual(D.read("Aspirateur balai sans-fil 60 min"), {"cordless": True})              # tirets
        self.assertEqual(D.read("Zephyr V12 Animal 2,3 kg HEPA"), {})                                 # le reste n'est pas lu
        self.assertEqual(D.read("Aspirateur traîneau à sac Ostra S3"), {"bagless": False})            # « à sac » : avec sac
        self.assertEqual(D.read("ASPIRATEUR BALAI SANS FIL"), {"cordless": True})                     # majuscules

    def test_electronics_as_feeds_write_it(self):
        a = attributes("TV QLED Vistrel Q60 55'' (139 cm) 4K UHD Smart TV", None, "televiseur")
        self.assertEqual((a["sub"], a["screen_in"], a["uhd"]), ("qled", 55, True))
        self.assertNotIn("width_cm", a)                                                               # 139 cm : sa diagonale
        a = attributes("Vistrel 43UX7 TV LED 108 cm 4K Ultra HD", None, "televiseur")
        self.assertEqual((a["sub"], a["screen_in"]), ("led", 43, ))
        self.assertEqual(attributes("TV LED 43\" Full HD", None, "televiseur")["uhd"], False)
        self.assertEqual(attributes("Téléviseur Mini LED 75\" 4K 120 Hz", None, "televiseur")["sub"], "mini_led")   # pas « LED »
        a = attributes("PC portable Calixo 15,6\" Intel Core i5 8 Go RAM 512 Go SSD", None, "ordinateur_portable")
        self.assertEqual((a["screen_in"], a["ram_gb"], a["storage_gb"]), (15.6, 8, 512))              # la mémoire vive à part
        a = attributes("Smartphone Ombrion X3 5G 256 Go 6,6\"", None, "smartphone")
        self.assertEqual((a["network_5g"], a["storage_gb"], "screen_in" in a), (True, 256, False))    # l'écran d'un téléphone : pas lu
        self.assertEqual(attributes("Console de salon Ludika One Édition Numérique 1 To", None, "console")["digital"], True)
        self.assertEqual(attributes("Casque Bluetooth Sonoryn Move", None, "casque_audio")["cordless"], True)
        self.assertEqual(attributes("Écouteurs sans réduction de bruit Sonoryn E2", None, "casque_audio")["anc"], False)
        self.assertEqual(attributes("Barre de son Brisko 5.1.2 Dolby Atmos", None, "enceinte")["sub"], "barre_de_son")

    def test_what_the_unseen_offers_showed(self):
        """v59, la première lecture des offres inédites (bench.ontologie --inedites) : ce qu'elle a montré, corrigé."""
        self.assertEqual(attributes("Ternis Book 14 - Ordinateur portable 14 pouces - 8Go - 256Go SSD", None, "ordinateur_portable")["ram_gb"], 8)
        self.assertEqual(attributes("Chromebook Calixo C11 11,6\" 4 Go 64 Go eMMC", None, "ordinateur_portable")["ram_gb"], 4)
        self.assertNotIn("ram_gb", attributes("PC portable Calixo 15,6\" 512 Go", None, "ordinateur_portable"))   # un stockage seul : pas de mémoire
        self.assertNotIn("ram_gb", attributes("PC portable Calixo 15,6\" 32 Go", None, "ordinateur_portable"))    # sans stockage nommé : on ne sait pas
        self.assertNotIn("ram_gb", attributes("PC portable Calixo 15,6\" 8 Go 16 Go 512 Go SSD", None, "ordinateur_portable"))   # deux : on ne choisit pas
        self.assertEqual(attributes("Sèche-linge Helio pompe à chaleur 9kg A++", None, "seche_linge")["energy_class"], "A++")
        self.assertNotIn("energy_class", attributes("Lave linge frontal 8kg 1400 tours A", None, "lave_linge"))   # un « A » seul ne dit rien
        self.assertEqual(categorize("Tempra Run 300 montre de sport GPS multisport")[0], "montre_connectee")
        self.assertEqual(categorize("Montre running Tempra 245")[0], "montre_connectee")
        self.assertNotIn(categorize("Casque moto modulable avec écouteurs Bluetooth intégrés")[0], FAMILY_OF)   # un casque de moto
        self.assertNotIn("screen_in", attributes("Téléviseur portable Kanzo 25 cm", None, "televiseur"))   # 25 cm : la taille d'aucun téléviseur
        self.assertTrue(attributes("Four pyrolytique Kessler 72L chaleur tournante", None, "four")["pyrolyse"])
        self.assertEqual(categorize("Console Ludika Swap OLED - Édition standard", "Jeux vidéo > Consoles")[0], "console")
        self.assertIsNone(categorize("Console d'entrée Nordvik chêne", "Meubles > Consoles")[0])
        self.assertEqual(categorize("Table ronde extensible Lumen 4 à 6 personnes")[0], "table")
        self.assertNotIn(categorize("Table basse ronde Lumen")[0], FAMILY_OF)                      # pas une table à manger

    def test_what_a_feed_sends_that_is_not_the_product_stays_out(self):
        for title, declared in (("Station de vidage pour robot aspirateur Helio", None), ("Sacs aspirateur x10", "Accessoires aspirateur"),
                                ("Batterie pour aspirateur balai", None), ("Balai vapeur Vela 1500 W", "Entretien des sols > Balais vapeur"),
                                ("Nettoyeur vapeur Vela S10", "Entretien des sols > Nettoyeurs vapeur"),
                                ("Coque pour smartphone Ombrion X3", "Accessoires téléphonie"), ("Embouts en mousse pour écouteurs", None),
                                ("Manette sans fil pour console Ludika One", "Accessoires consoles"),
                                ("Smartphone Ombrion X3 128 Go reconditionné Grade A", "Smartphones reconditionnés"),
                                ("Moniteur de pression artérielle Medix", "Santé"), ("Casque de moto intégral Vexa", None),
                                ("Moniteur bébé vidéo Babylo Cam", "Puériculture > Babyphones"), ("Montre analogique Chronia cuir", "Montres")):
            self.assertNotIn(categorize(title, declared)[0], FAMILY_OF, title)
        self.assertEqual(categorize("Nettoyeur de sols sans fil Vela F8")[0], "aspirateur")              # un aspirateur laveur
        self.assertEqual(D.sub_of("aspirateur", "Vela F8", "Électroménager > Nettoyeurs de sols"), "laveur")
        self.assertEqual(categorize("Bracelet connecté Chronia Fit 3")[0], "montre_connectee")         # pas un bracelet de montre
        self.assertEqual(categorize("Casque gaming Sonoryn G5", "Gaming > Casques")[0], "casque_audio")

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
        tv = O.DOMAINS["televiseur"].understand(O.text("tv oled 4k"))
        self.assertEqual((tv["sub"], tv["props"]), ("oled", {"uhd": True}))
        self.assertEqual(O.DOMAINS["casque_audio"].understand(O.text("casque sans reduction de bruit"))["props"], {"anc": False})

    def test_the_domain_a_phrase_names(self):
        self.assertEqual(O.detect(O.text("un balai sans fil")), D)
        self.assertEqual(O.detect(O.text("canapé d'angle")).key, "canape")                            # v59 : chaque rayon
        self.assertEqual(O.detect(O.text("plaques mixtes")).key, "plaque_cuisson")                    # l'expression la plus longue
        self.assertIsNone(O.detect(O.text("encastrable")))                                            # un four ou un lave-vaisselle
        self.assertIsNone(O.detect(O.text("pour le salon")))


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
        known = product_attributes("Lave-linge 8 kg", "lave_linge", {"capacity_kg": 9, "energy_class": "B"})
        self.assertEqual((known["capacity_kg"], known["energy_class"]), (8, "B"))    # v59 : l'offre du jour l'emporte ; ce qu'elle ne dit plus reste
        tv = product_attributes("TV Vistrel 139 cm", "televiseur", {"width_cm": 139, "sub": "oled"})
        self.assertEqual(tv, {"screen_in": 55, "sub": None})                        # une largeur lue avant la v59, un type plus dit : écartés

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
