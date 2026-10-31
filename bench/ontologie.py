"""Ce que la plateforme lit des offres, catégorie par catégorie, telles que les flux affiliés et les API des enseignes les
donnent : un titre et la catégorie de l'enseigne (« Électroménager > Lave-linge > Lave-linge hublot »).

Pour chaque offre, ce qu'elle DIT est écrit à la main : sa catégorie, son type quand le titre ou la catégorie le nomme,
et les attributs de sa catégorie qu'elle donne (capacité, taille d'écran, sans fil…) ; une offre qui n'est pas un
produit du catalogue (accessoire, produit reconditionné ou d'occasion, autre rayon) est un piège : elle doit rester
dehors. Marques fictives ; titres et catégories écrits comme ceux des enseignes françaises (majuscules, tirets, unités
collées, « 139 cm » pour une télévision, « 8 Go RAM » à côté du stockage…). Le code mesuré lit chaque offre comme la
collecte (market.match_product).

Mesures, par famille et en tout :
  rangées      l'offre est dans la bonne catégorie, et la catégorie est suivie (elle entre au catalogue)
  types        dit par l'offre : lu juste, faux, pas lu ; non dit : deviné (un type lu que l'offre ne dit pas)
  attributs    dits : lus justes, faux, pas lus ; devinés : un attribut de la catégorie lu sans que l'offre le dise
  pièges       tenus hors du catalogue

C'est un jeu écrit par le même auteur que les règles : il dit ce que les règles savent lire, pas ce que donneront de
vrais flux (à mesurer sur un échantillon réel, `deals.py sample`). OFFERS a servi à écrire les règles (non-régression) ;
INEDITES (v59, 64 offres) a été écrit d'un trait, les règles finies, et mesuré une première fois sans rien retoucher :
sa première lecture est gardée dans docs/ONTOLOGIE.md, à côté de ce qu'elle donne après les corrections qu'elle a
montrées.

  python -m bench.ontologie [--code <dossier du code>] [--json sortie.json] [-v] [--inedites]
"""
import argparse
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--code", help="dossier d'un autre code à mesurer (le code d'avant)")
ap.add_argument("--json")
ap.add_argument("-v", action="store_true", help="chaque écart")
ap.add_argument("--inedites", action="store_true", help="les offres inédites seulement (v59)")
ARGS = ap.parse_args() if __name__ == "__main__" else ap.parse_args([])
if ARGS.code:
    sys.path.insert(0, ARGS.code)

from deals.extract.categories import FAMILY_OF  # noqa: E402
from deals.market import Market  # noqa: E402
from deals.sim import gtin  # noqa: E402
from deals.store import Store  # noqa: E402

# Les attributs de chaque catégorie (le modèle visé : un type, puis un ou deux attributs) : un attribut lu sans que
# l'offre le dise est compté « deviné ».
DECLARED = {
    "lave_linge": ("capacity_kg", "energy_class"), "lave_linge_sechant": ("capacity_kg", "energy_class"),
    "seche_linge": ("capacity_kg", "energy_class"), "lave_vaisselle": ("place_settings", "width_cm"),
    "refrigerateur": ("volume_l", "no_frost"), "congelateur": ("volume_l", "no_frost"), "four": ("pyrolyse", "volume_l"),
    "plaque_cuisson": ("zones", "width_cm"), "hotte": ("width_cm",), "cuisiniere": ("width_cm", "pyrolyse"),
    "aspirateur": ("cordless", "bagless"), "robot_aspirateur": ("cordless", "bagless"),
    "canape": ("seats", "convertible"), "fauteuil": ("electrique",), "lit": ("bed_size",), "armoire": ("width_cm", "sliding"),
    "table": ("seats", "extensible"), "buffet": ("width_cm",), "meuble_tv": ("width_cm",), "commode": ("drawers", "width_cm"),
    "matelas": ("bed_size",), "sommier": ("bed_size",),
    "televiseur": ("screen_in", "uhd"), "smartphone": ("storage_gb", "network_5g"), "ordinateur_portable": ("screen_in", "ram_gb"),
    "tablette": ("screen_in", "storage_gb"), "casque_audio": ("anc", "cordless"), "enceinte": ("waterproof", "dolby_atmos"),
    "montre_connectee": ("gps", "cellular"), "console": ("digital", "storage_gb"), "ecran_pc": ("screen_in", "refresh_hz"),
}
FAMILY = {**{c: "Électroménager" for c in ("lave_linge", "lave_linge_sechant", "seche_linge", "lave_vaisselle", "refrigerateur",
                                          "congelateur", "four", "plaque_cuisson", "hotte", "cuisiniere", "aspirateur", "robot_aspirateur")},
          **{c: "Ameublement" for c in ("canape", "fauteuil", "lit", "armoire", "table", "buffet", "meuble_tv", "commode")},
          **{c: "Literie" for c in ("matelas", "sommier")},
          **{c: "Électronique" for c in ("televiseur", "smartphone", "ordinateur_portable", "tablette", "casque_audio", "enceinte",
                                         "montre_connectee", "console", "ecran_pc")}}

# (titre, catégorie déclarée par l'enseigne, ce que l'offre dit) ; None : un piège, hors catalogue
OFFERS = [
    # ------------------------------------------------------------------ électroménager
    ("Lave-linge hublot Kessler WM8 8 kg 1400 tr/min Classe A", "Électroménager > Lave-linge > Lave-linge hublot",
     {"cat": "lave_linge", "sub": "hublot", "capacity_kg": 8, "energy_class": "A"}),
    ("LAVE-LINGE TOP BRAVA T65 6,5KG", "ELECTROMENAGER > LAVAGE - SECHAGE > LAVE-LINGE", {"cat": "lave_linge", "sub": "top", "capacity_kg": 6.5}),
    ("Helio HW90 - Lave-linge frontal 9 kg - 1200 trs/min - Classe énergétique B", "Gros électroménager > Lavage et séchage > Lave-linge",
     {"cat": "lave_linge", "sub": "hublot", "capacity_kg": 9, "energy_class": "B"}),
    ("Machine à laver Ostra Silence 10 kg A", "Lavage > Machines à laver", {"cat": "lave_linge", "capacity_kg": 10}),
    ("Lave-linge chargement par le dessus Kessler TL7 7 kg", None, {"cat": "lave_linge", "sub": "top", "capacity_kg": 7}),
    ("Lave linge hublot pose libre Brava Eco 9kg classe A 1400 tours", "Lave-linge",
     {"cat": "lave_linge", "sub": "hublot", "capacity_kg": 9, "energy_class": "A"}),
    ("Lave-linge séchant Kessler WD96 9/6 kg Classe D", "Électroménager > Lave-linge séchant",
     {"cat": "lave_linge_sechant", "capacity_kg": 9, "energy_class": "D"}),
    ("Lavante-séchante Helio 10 kg + 6 kg séchage", "Lavage > Lavantes séchantes", {"cat": "lave_linge_sechant", "capacity_kg": 10}),
    ("BRAVA Lave-linge séchant hublot 8kg/5kg classe E", None, {"cat": "lave_linge_sechant", "capacity_kg": 8, "energy_class": "E"}),
    ("Sèche-linge pompe à chaleur Kessler DH8 8 kg Classe A++", "Électroménager > Sèche-linge > Sèche-linge pompe à chaleur",
     {"cat": "seche_linge", "sub": "pompe_chaleur", "capacity_kg": 8, "energy_class": "A++"}),
    ("Seche linge condensation Brava 7kg classe B", "Sèche-linge", {"cat": "seche_linge", "sub": "condensation", "capacity_kg": 7, "energy_class": "B"}),
    ("Sèche-linge à évacuation Helio 7 kg", "Gros électroménager > Lavage et séchage > Sèche-linge",
     {"cat": "seche_linge", "sub": "evacuation", "capacity_kg": 7}),
    ("Ostra DryCare 9 kg - Sèche-linge PAC A+++", "ELECTROMENAGER > SECHE-LINGE", {"cat": "seche_linge", "sub": "pompe_chaleur", "capacity_kg": 9,
                                                                                   "energy_class": "A+++"}),   # v59 : « A+++ » seul le dit
    ("Lave-vaisselle pose libre Helio 60 cm 13 couverts 44 dB Classe C", "Électroménager > Lave-vaisselle > Lave-vaisselle pose libre",
     {"cat": "lave_vaisselle", "sub": "pose_libre", "place_settings": 13, "width_cm": 60}),
    ("Lave-vaisselle tout intégrable Kessler 60 cm 14 couverts classe B", "Lave-vaisselle encastrable",
     {"cat": "lave_vaisselle", "sub": "encastrable", "place_settings": 14, "width_cm": 60}),
    ("Lave vaisselle 45 cm Brava 10 couverts", "ELECTROMENAGER > LAVE-VAISSELLE", {"cat": "lave_vaisselle", "place_settings": 10, "width_cm": 45}),
    ("Mini lave-vaisselle compact Ostra 6 couverts", "Petit électroménager > Lave-vaisselle compact",
     {"cat": "lave_vaisselle", "sub": "compact", "place_settings": 6}),
    ("Lave-vaisselle encastrable Helio SMV4 60cm 13 couverts", None, {"cat": "lave_vaisselle", "sub": "encastrable", "place_settings": 13, "width_cm": 60}),
    ("Kessler Lave-vaisselle semi-intégrable 45 cm 9 couverts", "Lave-vaisselle",
     {"cat": "lave_vaisselle", "sub": "encastrable", "place_settings": 9, "width_cm": 45}),
    ("Réfrigérateur combiné Brava 60 cm No Frost 331 L Classe C", "Électroménager > Réfrigérateur > Réfrigérateur combiné",
     {"cat": "refrigerateur", "sub": "combine", "volume_l": 331, "no_frost": True}),
    ("Réfrigérateur américain Helio 91 cm 635 L", "Réfrigérateur américain", {"cat": "refrigerateur", "sub": "americain", "volume_l": 635}),
    ("Réfrigérateur multi-portes Ostra 70 cm 450 L Total No Frost", "Froid > Réfrigérateurs multi-portes",
     {"cat": "refrigerateur", "sub": "multi_portes", "volume_l": 450, "no_frost": True}),
    ("Frigo 2 portes Kessler 213L froid statique", "ELECTROMENAGER > FROID > REFRIGERATEUR 2 PORTES",
     {"cat": "refrigerateur", "sub": "deux_portes", "volume_l": 213, "no_frost": False}),
    ("Réfrigérateur table top Brava 88 L", "Réfrigérateur top", {"cat": "refrigerateur", "sub": "une_porte", "volume_l": 88}),
    ("Réfrigérateur 1 porte Helio 359 L froid ventilé", None, {"cat": "refrigerateur", "sub": "une_porte", "volume_l": 359, "no_frost": True}),
    ("Congélateur armoire Kessler No Frost 242 L Classe E", "Électroménager > Congélateur > Congélateur armoire",
     {"cat": "congelateur", "sub": "armoire", "volume_l": 242, "no_frost": True}),
    ("Congélateur coffre Brava 300 L", "Congélateur coffre", {"cat": "congelateur", "sub": "coffre", "volume_l": 300}),
    ("Congélateur top Helio 85 L froid statique", "Froid > Congélateurs", {"cat": "congelateur", "sub": "table_top", "volume_l": 85, "no_frost": False}),
    ("CONGELATEUR ARMOIRE OSTRA 7 TIROIRS 210L NOFROST", None, {"cat": "congelateur", "sub": "armoire", "volume_l": 210, "no_frost": True}),
    ("Four encastrable pyrolyse Brava 71 L Classe A+", "Électroménager > Four > Four encastrable",
     {"cat": "four", "sub": "encastrable", "pyrolyse": True, "volume_l": 71}),
    ("Four multifonction catalyse Helio 65 L", "Four encastrable", {"cat": "four", "sub": "encastrable", "pyrolyse": False, "volume_l": 65}),
    ("Four pyrolytique Kessler 72L chaleur tournante", "ELECTROMENAGER > CUISSON > FOUR", {"cat": "four", "pyrolyse": True, "volume_l": 72}),
    ("Four posable Ostra 45 L", "Petit électroménager > Fours posables", {"cat": "four", "sub": "pose_libre", "volume_l": 45}),
    ("Four vapeur combiné Helio 70 L classe A", "Four vapeur", {"cat": "four", "volume_l": 70}),
    ("Plaque induction Ostra 4 foyers 60 cm", "Électroménager > Plaque de cuisson > Plaque induction",
     {"cat": "plaque_cuisson", "sub": "induction", "zones": 4, "width_cm": 60}),
    ("Table de cuisson vitrocéramique Brava 3 foyers", "Tables de cuisson", {"cat": "plaque_cuisson", "sub": "vitroceramique", "zones": 3}),
    ("Plaque mixte gaz induction Kessler 4 feux 60cm", "Plaque mixte", {"cat": "plaque_cuisson", "sub": "mixte", "zones": 4, "width_cm": 60}),
    ("Plaque gaz Helio 5 brûleurs 75 cm", "Cuisson > Plaques gaz", {"cat": "plaque_cuisson", "sub": "gaz", "zones": 5, "width_cm": 75}),
    ("Domino induction Brava 2 foyers 30 cm", None, {"cat": "plaque_cuisson", "sub": "induction", "zones": 2, "width_cm": 30}),
    ("Hotte décorative murale Brava 90 cm 700 m³/h", "Électroménager > Hotte > Hotte murale", {"cat": "hotte", "sub": "murale", "width_cm": 90}),
    ("Hotte îlot Kessler 90 cm", "Hottes îlot", {"cat": "hotte", "sub": "ilot", "width_cm": 90}),
    ("Hotte casquette Helio 60 cm", None, {"cat": "hotte", "sub": "casquette", "width_cm": 60}),
    ("Hotte tiroir télescopique Ostra 60 cm", "Hotte télescopique", {"cat": "hotte", "sub": "tiroir", "width_cm": 60}),
    ("Hotte aspirante plan de travail Brava 80 cm", "Hottes plan de travail", {"cat": "hotte", "sub": "plan_travail", "width_cm": 80}),
    ("Cuisinière induction Kessler 60 cm four pyrolyse", "Électroménager > Cuisinière > Cuisinière induction",
     {"cat": "cuisiniere", "sub": "induction", "width_cm": 60, "pyrolyse": True}),
    ("Cuisinière mixte Brava 50 cm four catalyse", "Cuisinières mixtes", {"cat": "cuisiniere", "sub": "mixte", "width_cm": 50, "pyrolyse": False}),
    ("Cuisinière gaz Helio 4 feux 60cm", None, {"cat": "cuisiniere", "sub": "gaz", "width_cm": 60}),
    ("Cuisinière vitrocéramique Ostra 50 cm", "CUISSON > CUISINIERE", {"cat": "cuisiniere", "sub": "vitroceramique", "width_cm": 50}),
    ("Aspirateur balai sans fil Zephyr V12 60 min", "Électroménager > Aspirateur > Aspirateur balai", {"cat": "aspirateur", "sub": "balai", "cordless": True}),
    ("Aspirateur traîneau avec sac Kessler 750 W", None, {"cat": "aspirateur", "sub": "traineau", "bagless": False}),
    ("Aspirateur traîneau Ostra Compact 700 W", "Entretien > Aspirateurs avec ou sans sac", {"cat": "aspirateur", "sub": "traineau"}),
    ("Robot aspirateur laveur Ostra S8 navigation laser", "Robot aspirateur", {"cat": "robot_aspirateur", "sub": "robot"}),
    ("Aspirateur à main sans fil Brava Mini", "Aspirateurs à main", {"cat": "aspirateur", "sub": "main", "cordless": True}),
    ("Aspirateur laveur sans fil Helio Wave", "Nettoyeurs de sols", {"cat": "aspirateur", "sub": "laveur", "cordless": True}),
    # ------------------------------------------------------------------ ameublement
    ("Canapé d'angle convertible Nordvik Oslo 5 places tissu", "Meubles > Canapés > Canapés d'angle",
     {"cat": "canape", "sub": "angle", "seats": 5, "convertible": True}),
    ("Canapé 3 places Varenne Lina velours côtelé", "Canapé droit", {"cat": "canape", "sub": "droit", "seats": 3}),
    ("Canapé convertible Lumen Bergen couchage 140x190", "Canapés convertibles", {"cat": "canape", "convertible": True}),
    ("Canapé modulable 4 places Aurel velours", None, {"cat": "canape", "sub": "modulable", "seats": 4}),
    ("Canapé d'angle réversible Varenne Ravel 4 places fixe", "Canapés d'angle", {"cat": "canape", "sub": "angle", "seats": 4, "convertible": False}),
    ("Clic-clac Lumen Nova 3 places", "Mobilier > Canapé > Clic-clac", {"cat": "canape", "seats": 3, "convertible": True}),
    ("Fauteuil relax électrique Aurel Nils cuir", "Fauteuils relax", {"cat": "fauteuil", "sub": "relax", "electrique": True}),
    ("Fauteuil releveur manuel Lumen Senior", "Fauteuil releveur", {"cat": "fauteuil", "sub": "relax", "electrique": False}),
    ("Fauteuil club Varenne Oscar cuir vieilli", "Salon > Fauteuils", {"cat": "fauteuil", "sub": "club"}),
    ("Fauteuil à bascule Nordvik Rock bois", None, {"cat": "fauteuil", "sub": "bascule"}),
    ("Lit coffre Nordvik Aria 160x200 avec tête de lit", "Chambre > Lits > Lit coffre", {"cat": "lit", "sub": "coffre", "bed_size": "160x200"}),
    ("Lit adulte Lumen Kara 140x190 chêne massif", "Lits adulte", {"cat": "lit", "bed_size": "140x190"}),
    ("Lit mezzanine Nordvik Hop 90x200", "Lits enfant", {"cat": "lit", "sub": "mezzanine", "bed_size": "90x200"}),
    ("Lit superposé Lumen Duo 2x90x190", None, {"cat": "lit", "sub": "superpose", "bed_size": "2x90x190"}),
    ("Cadre de lit Varenne Tilda 180x200 tête capitonnée", "Lits", {"cat": "lit", "bed_size": "180x200"}),
    ("Armoire Nordvik Lund 3 portes battantes 150 cm", "Rangement > Armoires", {"cat": "armoire", "width_cm": 150, "sliding": False}),
    ("Dressing Lumen Modulo 200 cm portes coulissantes", "Dressings", {"cat": "armoire", "sub": "dressing", "width_cm": 200, "sliding": True}),
    ("Armoire 2 portes coulissantes Varenne Lisa L.180 cm", None, {"cat": "armoire", "width_cm": 180, "sliding": True}),
    ("Penderie Nordvik Kit 100 cm", "Penderies", {"cat": "armoire", "sub": "penderie", "width_cm": 100}),
    ("Table à manger extensible Varenne Viggo 6 à 10 places chêne", "Salle à manger > Tables", {"cat": "table", "seats": 10, "extensible": True}),
    ("Table à manger ronde Nordvik Nora 4 places", "Tables à manger", {"cat": "table", "sub": "ronde", "seats": 4}),
    ("Table de salle à manger rectangulaire Aurel Roma céramique 8 places", None, {"cat": "table", "sub": "rectangulaire", "seats": 8}),
    ("Table extensible carrée Lumen Quadro 4 à 8 personnes", "Tables", {"cat": "table", "sub": "carree", "seats": 8, "extensible": True}),
    ("Table à manger ovale Varenne Ova 6 places", "Mobilier > Tables à manger", {"cat": "table", "sub": "ovale", "seats": 6}),
    ("Buffet Varenne Siena 3 portes 180 cm noyer", "Salon > Buffets", {"cat": "buffet", "width_cm": 180}),
    ("Buffet haut Nordvik Fjord 2 portes vitrées 90 cm", "Buffets hauts", {"cat": "buffet", "sub": "haut", "width_cm": 90}),
    ("Enfilade Lumen Mila 4 portes 200 cm", None, {"cat": "buffet", "sub": "bas", "width_cm": 200}),
    ("Meuble TV Nordvik Halden 200 cm chêne clair", "Salon > Meubles TV", {"cat": "meuble_tv", "width_cm": 200}),
    ("Meuble TV suspendu Lumen Flot 160 cm", "Meubles TV", {"cat": "meuble_tv", "sub": "suspendu", "width_cm": 160}),
    ("Banc TV Varenne Low 140 cm", None, {"cat": "meuble_tv", "sub": "bas", "width_cm": 140}),
    ("Commode Lumen Ella 6 tiroirs", "Chambre > Commodes", {"cat": "commode", "drawers": 6}),
    ("Chiffonnier Nordvik Tall 5 tiroirs 50 cm", "Commodes", {"cat": "commode", "sub": "chiffonnier", "drawers": 5, "width_cm": 50}),
    ("Commode à langer Varenne Bébé 3 tiroirs", None, {"cat": "commode", "sub": "langer", "drawers": 3}),
    ("Semainier Aurel 7 tiroirs 45 cm", "Commodes et chiffonniers", {"cat": "commode", "sub": "semainier", "drawers": 7, "width_cm": 45}),
    ("Commode Varenne Lina 5 tiroirs 80 cm", "Chambre > Commodes et chiffonniers", {"cat": "commode", "drawers": 5, "width_cm": 80}),
    # ------------------------------------------------------------------ literie
    ("Matelas Dormea Hybrid 160x200 ressorts ensachés", "Literie > Matelas > Matelas ressorts", {"cat": "matelas", "sub": "ressorts", "bed_size": "160x200"}),
    ("Matelas Solenne Mémoire 140x190 mousse à mémoire de forme", "Matelas mémoire de forme", {"cat": "matelas", "sub": "memoire", "bed_size": "140x190"}),
    ("Matelas Solenne Latex 160x200 latex naturel", "Matelas latex", {"cat": "matelas", "sub": "latex", "bed_size": "160x200"}),
    ("Matelas Dormea Essentiel 90x190 mousse", None, {"cat": "matelas", "sub": "mousse", "bed_size": "90x190"}),
    ("Matelas hybride Solenne Duo 180x200 ressorts et mousse", "Matelas", {"cat": "matelas", "sub": "hybride", "bed_size": "180x200"}),
    ("MATELAS 140X190 DORMEA CONFORT FERME", "LITERIE > MATELAS", {"cat": "matelas", "bed_size": "140x190"}),
    ("Sommier tapissier Dormea 160x200 lattes", "Literie > Sommiers > Sommier tapissier", {"cat": "sommier", "sub": "tapissier", "bed_size": "160x200"}),
    ("Sommier électrique Solenne relaxation 2x80x200", "Sommiers relaxation", {"cat": "sommier", "sub": "electrique", "bed_size": "2x80x200"}),
    ("Sommier à lattes Dormea 140x190 pieds inclus", None, {"cat": "sommier", "sub": "lattes", "bed_size": "140x190"}),
    ("Sommier coffre Solenne Box 160x200", "Sommiers coffres", {"cat": "sommier", "sub": "coffre", "bed_size": "160x200"}),
    # ------------------------------------------------------------------ électronique
    ("TV QLED Vistrel Q60 55'' (139 cm) 4K UHD Smart TV", "Image & Son > Téléviseurs > TV QLED",
     {"cat": "televiseur", "sub": "qled", "screen_in": 55, "uhd": True}),
    ("Téléviseur OLED Vistrel 65OL9 164 cm 4K", "TV OLED", {"cat": "televiseur", "sub": "oled", "screen_in": 65, "uhd": True}),
    ("Vistrel 43UX7 TV LED 108 cm 4K Ultra HD", "TV, Vidéo > Téléviseurs", {"cat": "televiseur", "sub": "led", "screen_in": 43, "uhd": True}),
    ("TV LED Ombrix 32 pouces HD", "Téléviseurs", {"cat": "televiseur", "sub": "led", "screen_in": 32, "uhd": False}),
    ('Téléviseur Mini LED Vistrel 75" 4K 120 Hz', "Image et son > TV > TV Mini LED", {"cat": "televiseur", "sub": "mini_led", "screen_in": 75, "uhd": True}),
    ("Smart TV Ombrix 50 pouces 4K UHD", None, {"cat": "televiseur", "screen_in": 50, "uhd": True}),
    ("TV 4K 55 Ombrix", "TV", {"cat": "televiseur", "uhd": True}),
    ("Smartphone Ombrion X5 5G 128 Go Noir", "Téléphonie > Smartphones", {"cat": "smartphone", "storage_gb": 128, "network_5g": True}),
    ("Ombrion A15 4G 64 Go - Smartphone Android", "Téléphones mobiles", {"cat": "smartphone", "storage_gb": 64, "network_5g": False}),
    ("Smartphone pliable Ombrion Fold 6 5G 256 Go", "Smartphones pliables", {"cat": "smartphone", "sub": "pliable", "storage_gb": 256, "network_5g": True}),
    ("Téléphone portable senior Telvo S1 à clapet", "Téléphonie > Téléphones portables", {"cat": "smartphone", "sub": "simple"}),
    ('Smartphone Ombrion Neo 8 Go RAM 256 Go 6,7" 5G', None, {"cat": "smartphone", "storage_gb": 256, "network_5g": True}),
    ("Ombrion Flip 5 512 Go 5G", "Mobile > Smartphones pliables", {"cat": "smartphone", "sub": "pliable", "storage_gb": 512, "network_5g": True}),
    ('PC Portable Calixo Vivo 15 15,6" Intel Core i5 16 Go RAM 512 Go SSD', "Informatique > Ordinateurs portables",
     {"cat": "ordinateur_portable", "screen_in": 15.6, "ram_gb": 16}),
    ("PC portable gamer Calixo Strix 17,3 pouces RTX 4060 32 Go", "PC portable gamer", {"cat": "ordinateur_portable", "sub": "gamer", "screen_in": 17.3}),
    ("Ordinateur portable 2 en 1 Calixo Flip 14 pouces tactile 8 Go RAM", "PC portables convertibles",
     {"cat": "ordinateur_portable", "sub": "deux_en_un", "screen_in": 14, "ram_gb": 8}),
    ('Chromebook Calixo C14 14" 4 Go 64 Go eMMC', "Informatique > Chromebook", {"cat": "ordinateur_portable", "sub": "chromebook", "screen_in": 14,
                                                                                "ram_gb": 4}),        # v59 : la mémoire, puis le stockage nommé
    ("Ultraportable Calixo Air 13,3'' 16Go 1To SSD", None, {"cat": "ordinateur_portable", "sub": "ultraportable", "screen_in": 13.3, "ram_gb": 16}),
    ("Laptop Calixo Pro 16 pouces 32 Go de RAM", "Ordinateurs portables", {"cat": "ordinateur_portable", "screen_in": 16, "ram_gb": 32}),
    ("Tablette tactile Tavelo Tab 11 pouces 128 Go Wi-Fi", "Informatique > Tablettes", {"cat": "tablette", "screen_in": 11, "storage_gb": 128}),
    ('Tablette enfant Tavelo Kids 7" 32 Go', "Tablettes enfant", {"cat": "tablette", "sub": "enfant", "screen_in": 7, "storage_gb": 32}),
    ("Tavelo Pad 10,9'' 256 Go 5G", "Tablettes tactiles", {"cat": "tablette", "screen_in": 10.9, "storage_gb": 256}),
    ("Tablette Android Tavelo T8 8 pouces 64 Go", None, {"cat": "tablette", "screen_in": 8, "storage_gb": 64}),
    ("Casque sans fil à réduction de bruit Sonoryn H700 Bluetooth", "Image & Son > Casques audio",
     {"cat": "casque_audio", "sub": "casque", "anc": True, "cordless": True}),
    ("Écouteurs sans fil Sonoryn Buds 3 ANC", "Écouteurs true wireless", {"cat": "casque_audio", "sub": "ecouteurs", "anc": True, "cordless": True}),
    ("Écouteurs filaires Sonoryn E10 jack 3,5 mm", "Écouteurs", {"cat": "casque_audio", "sub": "ecouteurs", "cordless": False}),
    ("Casque audio Sonoryn Studio filaire", None, {"cat": "casque_audio", "sub": "casque", "cordless": False}),
    ("Casque Bluetooth Sonoryn Move", "Casques", {"cat": "casque_audio", "sub": "casque", "cordless": True}),
    ("Casque Bluetooth Sonoryn H300", "Image & Son > Casques et écouteurs", {"cat": "casque_audio", "sub": "casque", "cordless": True}),
    ("Casque gaming Sonoryn G5 filaire", "Gaming > Casques", {"cat": "casque_audio", "sub": "casque", "cordless": False}),
    ("Enceinte Bluetooth portable Brisko Go 3 étanche IP67", "Image & Son > Enceintes portables", {"cat": "enceinte", "sub": "portable", "waterproof": True}),
    ("Barre de son Brisko S5 Dolby Atmos 5.1.2", "Barres de son", {"cat": "enceinte", "sub": "barre_de_son", "dolby_atmos": True}),
    ("Enceinte connectée Brisko Home Wi-Fi assistant vocal", "Enceintes connectées", {"cat": "enceinte", "sub": "connectee"}),
    ("Soundbar Brisko Cine 3.1", None, {"cat": "enceinte", "sub": "barre_de_son"}),
    ("Enceinte sans fil Brisko Boom waterproof", "Enceintes Bluetooth", {"cat": "enceinte", "sub": "portable", "waterproof": True}),
    ("Montre connectée Chronia Fit 4 GPS", "Objets connectés > Montres connectées", {"cat": "montre_connectee", "gps": True}),
    ("Bracelet connecté Chronia Band 8", "Bracelets connectés", {"cat": "montre_connectee", "sub": "bracelet"}),
    ("Montre GPS running Chronia Run 265", "Montres sport", {"cat": "montre_connectee", "sub": "sport", "gps": True}),
    ("Montre connectée Chronia S9 GPS + Cellular 45 mm", None, {"cat": "montre_connectee", "gps": True, "cellular": True}),
    ("Console de jeux Ludika One 1 To édition numérique", "Jeux vidéo > Consoles", {"cat": "console", "storage_gb": 1000, "digital": True}),
    ("Console portable Ludika Go 512 Go", "Consoles portables", {"cat": "console", "sub": "portable", "storage_gb": 512}),
    ("Console de salon Ludika Box 825 Go avec lecteur Blu-ray", "Consoles de salon", {"cat": "console", "sub": "salon", "storage_gb": 825, "digital": False}),
    ("Ludika Mini - console de jeu portable 64 Go", None, {"cat": "console", "sub": "portable", "storage_gb": 64}),
    ('Écran PC gaming Pixelia G27 27" 165 Hz', "Informatique > Écrans PC", {"cat": "ecran_pc", "sub": "gaming", "screen_in": 27, "refresh_hz": 165}),
    ("Moniteur incurvé Pixelia C34 34 pouces 144 Hz", "Écrans incurvés", {"cat": "ecran_pc", "sub": "incurve", "screen_in": 34, "refresh_hz": 144}),
    ("Écran PC Pixelia B24 24'' Full HD 75 Hz", "Moniteurs", {"cat": "ecran_pc", "screen_in": 24, "refresh_hz": 75}),
    ("Ecran gamer Pixelia Arena 32 pouces 240Hz", None, {"cat": "ecran_pc", "sub": "gaming", "screen_in": 32, "refresh_hz": 240}),
    # ------------------------------------------------------------------ pièges : rien de tout cela n'entre au catalogue
    ("Coque de protection pour smartphone Ombrion X5", "Accessoires téléphonie > Coques", None),
    ("Verre trempé Ombrion A15 x2", "Protection écran", None),
    ("Câble HDMI 2.1 8K 2 m", "Câbles", None),
    ("Chargeur USB-C 65 W pour PC portable", "Accessoires informatique", None),
    ("Support mural TV orientable 32-75 pouces", "Accessoires TV > Supports", None),
    ("Télécommande universelle pour téléviseur Vistrel", None, None),
    ("Manette sans fil pour console Ludika One", "Accessoires consoles", None),
    ("Jeu Ludika One : Course Folle", "Jeux vidéo", None),
    ("Housse pour tablette Tavelo Tab 11", "Étuis tablettes", None),
    ("Bracelet de rechange pour montre connectée Chronia", "Accessoires montres", None),
    ("Smartphone Ombrion X3 128 Go reconditionné Grade A", "Smartphones reconditionnés", None),
    ("Ombrion X2 64 Go - Occasion - Très bon état", "Téléphonie > Occasion", None),
    ("PC portable Calixo Vivo 15 reconditionné", "Informatique reconditionnée", None),
    ("Station de charge pour manettes", None, None),
    ("Embouts en mousse pour écouteurs Sonoryn", None, None),
    ("Sacoche pour ordinateur portable 15,6 pouces", "Bagagerie > Sacoches", None),
    ("Souris sans fil Calixo M1", "Périphériques", None),
    ("Clavier gamer Calixo K7", "Périphériques", None),
    ("Carte mémoire microSD 128 Go", "Stockage", None),
    ("Batterie externe 20000 mAh", "Accessoires téléphonie", None),
    ("Moniteur bébé vidéo Babylo Cam", "Puériculture > Babyphones", None),
    ("Pied de TV universel", None, None),
    ("Filtre à charbon pour hotte Brava", "Accessoires hotte", None),
    ("Tuyau d'évacuation pour lave-linge 2 m", None, None),
    ("Housse de canapé 3 places extensible", "Linge de maison", None),
    ("Protège-matelas 160x200 imperméable", "Linge de lit", None),
    ("Pieds de lit Nordvik x4", None, None),
    ("Kit de superposition lave-linge sèche-linge", None, None),
    ("Sacs aspirateur x10 compatibles Ostra", "Accessoires aspirateur", None),
    ("Station de vidage pour robot aspirateur Helio", None, None),
    ("Balai vapeur Vela Steam 1500 W", "Entretien des sols > Balais vapeur", None),
    ("Lave-linge Kessler WM8 reconditionné", "Électroménager reconditionné", None),
    ("Table basse Nordvik Oslo", "Salon > Tables basses", None),
    ("Lampe de chevet Lumen", None, None),
    ("Micro-ondes Helio 25 L", "Petit électroménager > Micro-ondes", None),
    ("Moniteur de pression artérielle Medix", "Santé", None),
    ("Casque de moto intégral Vexa", None, None),
    ("Console d'entrée Nordvik chêne 120 cm", "Meubles > Consoles", None),
    ("Tablette murale Nordvik 80 cm", "Étagères", None),
    ("Montre analogique Chronia cuir", "Montres", None),
    ("Vidéoprojecteur Vistrel 4K", "Vidéoprojecteurs", None),
]

# v59 : 64 offres écrites d'un trait après les règles, sans les essayer (marques fictives) — ce qu'elles disent, à la main.
INEDITES = [
    ("VISTREL 65QX9 - TV QLED 4K 164 cm - Smart TV - HDR10+", "TV - Vidéo > Téléviseurs > TV QLED",
     {"cat": "televiseur", "sub": "qled", "screen_in": 65, "uhd": True}),
    ("Téléviseur LED Kanzo 32HD5 80 cm HD", "Image et son > Télévision", {"cat": "televiseur", "sub": "led", "screen_in": 32, "uhd": False}),
    ("Orvia 50UQ7000 50\" LED 4K Ultra HD Smart TV", "Télévision > TV 4K", {"cat": "televiseur", "sub": "led", "screen_in": 50, "uhd": True}),
    ("TV OLED evo Vistrel 77 pouces 4K 144Hz", None, {"cat": "televiseur", "sub": "oled", "screen_in": 77, "uhd": True}),
    ("Smart TV Kanzo 43 pouces Full HD", "TV", {"cat": "televiseur", "screen_in": 43, "uhd": False}),
    ("Smartphone OMBRION X5 Lite 5G 128Go Noir", "Téléphonie > Smartphones", {"cat": "smartphone", "storage_gb": 128, "network_5g": True}),
    ("Velto V20 Dual SIM 4G 64 Go Bleu", "Téléphones portables", {"cat": "smartphone", "storage_gb": 64, "network_5g": False}),
    ("Aphel Flip 6 5G 256 Go", "Smartphones > Pliables", {"cat": "smartphone", "sub": "pliable", "storage_gb": 256, "network_5g": True}),
    ("Téléphone portable senior Velto S2 à clapet", None, {"cat": "smartphone", "sub": "simple"}),
    ("PC Portable Gamer CALIXO Nitro 17,3\" FHD 144 Hz - RTX 4060 - 16 Go RAM - 1 To SSD", "Informatique > Ordinateurs portables > PC portables gamer",
     {"cat": "ordinateur_portable", "sub": "gamer", "screen_in": 17.3, "ram_gb": 16}),
    ("Ternis Book 14 - Ordinateur portable 14 pouces - 8Go - 256Go SSD - Windows 11", None,
     {"cat": "ordinateur_portable", "screen_in": 14, "ram_gb": 8}),
    ("Chromebook Calixo C11 11,6\" 4 Go 64 Go eMMC", "Informatique > Chromebook", {"cat": "ordinateur_portable", "sub": "chromebook",
                                                                                     "screen_in": 11.6, "ram_gb": 4}),
    ("Tablette Android Tavelo T10 10,1'' 64Go Wi-Fi", "Tablettes tactiles", {"cat": "tablette", "screen_in": 10.1, "storage_gb": 64}),
    ("Tavelo Pad Kids 7 pouces 32 Go avec coque", "Jeux et jouets > Tablettes enfant", {"cat": "tablette", "sub": "enfant", "screen_in": 7,
                                                                                         "storage_gb": 32}),
    ("Écouteurs intra-auriculaires Bluetooth Aurio Pods 2", "Audio > Écouteurs", {"cat": "casque_audio", "sub": "ecouteurs", "cordless": True}),
    ("SONORYN WH-900 Casque circum-auriculaire sans fil à réduction de bruit active", "Image et son > Casques",
     {"cat": "casque_audio", "sub": "casque", "cordless": True, "anc": True}),
    ("Casque filaire Aurio Studio Pro jack 3,5 mm", None, {"cat": "casque_audio", "sub": "casque", "cordless": False}),
    ("Enceinte connectée Brisko Home avec assistant vocal", "Audio > Enceintes connectées", {"cat": "enceinte", "sub": "connectee"}),
    ("Barre de son Aurio SB500 2.1 avec caisson de basses", "Home cinéma > Barres de son", {"cat": "enceinte", "sub": "barre_de_son"}),
    ("Brisko Boom 2 - Enceinte Bluetooth étanche IPX7", None, {"cat": "enceinte", "sub": "portable", "waterproof": True}),
    ("Montre connectée Chronia Venu 2 GPS AMOLED", "Montres connectées", {"cat": "montre_connectee", "gps": True}),
    ("Tempra Run 300 montre de sport GPS multisport", None, {"cat": "montre_connectee", "sub": "sport", "gps": True}),
    ("Chronia Watch 4 LTE 44 mm", "Montres connectées", {"cat": "montre_connectee", "cellular": True}),
    ("Console Ludika Swap OLED - Édition standard", "Jeux vidéo > Consoles", {"cat": "console", "digital": False}),
    ("Ludika One Digital Edition 825 Go", "Consoles de salon", {"cat": "console", "sub": "salon", "digital": True, "storage_gb": 825}),
    ("Écran PC Calixo 24\" Full HD 75 Hz IPS", "Informatique > Écrans", {"cat": "ecran_pc", "screen_in": 24, "refresh_hz": 75}),
    ("Moniteur gaming incurvé Ternis 32 pouces 165Hz QHD", None, {"cat": "ecran_pc", "sub": "gaming", "screen_in": 32, "refresh_hz": 165}),
    ("Lave-linge séchant Kessler WD10 10/6 kg", "Lavage > Lavantes séchantes", {"cat": "lave_linge_sechant", "capacity_kg": 10}),
    ("Brava LF8 Lave linge frontal 8kg 1400 tours A", None, {"cat": "lave_linge", "sub": "hublot", "capacity_kg": 8, "energy_class": "A"}),
    ("Sèche-linge Helio pompe à chaleur 9kg A++", "Séchage", {"cat": "seche_linge", "sub": "pompe_chaleur", "capacity_kg": 9,
                                                               "energy_class": "A++"}),
    ("Lave vaisselle encastrable 45 cm Ostra 10 couverts", None, {"cat": "lave_vaisselle", "sub": "encastrable", "place_settings": 10,
                                                                  "width_cm": 45}),
    ("Réfrigérateur 2 portes Kessler 70 cm No Frost 430 L", "Froid > Réfrigérateurs double porte",
     {"cat": "refrigerateur", "sub": "deux_portes", "volume_l": 430, "no_frost": True}),
    ("Congélateur coffre Helio 200 L", "Congélation", {"cat": "congelateur", "sub": "coffre", "volume_l": 200}),
    ("Four multifonction pyrolyse Brava 71L", "Cuisson > Fours encastrables", {"cat": "four", "sub": "encastrable", "pyrolyse": True,
                                                                               "volume_l": 71}),
    ("Table de cuisson induction Kessler 3 foyers 60 cm", None, {"cat": "plaque_cuisson", "sub": "induction", "zones": 3, "width_cm": 60}),
    ("Hotte îlot Ostra 90 cm", "Hottes", {"cat": "hotte", "sub": "ilot", "width_cm": 90}),
    ("Cuisinière mixte Helio 60 cm four pyrolyse", None, {"cat": "cuisiniere", "sub": "mixte", "width_cm": 60, "pyrolyse": True}),
    ("Aspirateur sans fil Zephyr V10 Absolute", "Aspirateurs > Aspirateurs balais", {"cat": "aspirateur", "sub": "balai", "cordless": True}),
    ("Robot laveur Helio Mop 5", None, {"cat": "robot_aspirateur", "sub": "robot"}),
    ("Aspirateur traîneau sans sac 800W Ostra Cyclo", None, {"cat": "aspirateur", "sub": "traineau", "bagless": True}),
    ("Canapé d'angle réversible convertible 5 places gris Nordvik", "Salon > Canapés d'angle", {"cat": "canape", "sub": "angle",
                                                                                                "convertible": True, "seats": 5}),
    ("Canapé droit 3 places tissu Lumen", None, {"cat": "canape", "sub": "droit", "seats": 3}),
    ("Fauteuil relax électrique cuir Aurel", "Fauteuils", {"cat": "fauteuil", "sub": "relax", "electrique": True}),
    ("Lit mezzanine 90x190 Varenne bois", "Chambre enfant > Lits", {"cat": "lit", "sub": "mezzanine", "bed_size": "90x190"}),
    ("Armoire 2 portes battantes 100 cm Nordvik", None, {"cat": "armoire", "sliding": False, "width_cm": 100}),
    ("Table ronde extensible Lumen 4 à 6 personnes", "Salle à manger > Tables", {"cat": "table", "sub": "ronde", "extensible": True, "seats": 6}),
    ("Buffet haut 2 portes Varenne 90 cm", None, {"cat": "buffet", "sub": "haut", "width_cm": 90}),
    ("Meuble TV suspendu Nordvik 160 cm", "Salon > Meubles TV", {"cat": "meuble_tv", "sub": "suspendu", "width_cm": 160}),
    ("Commode 4 tiroirs Lumen 80 cm chêne", None, {"cat": "commode", "drawers": 4, "width_cm": 80}),
    ("Matelas mémoire de forme Solenne 140x190 cm", "Literie > Matelas", {"cat": "matelas", "sub": "memoire", "bed_size": "140x190"}),
    ("Sommier à lattes Dormea 2x80x200", None, {"cat": "sommier", "sub": "lattes", "bed_size": "2x80x200"}),
    ("Matelas Dormea Latex Naturel 160 x 200", None, {"cat": "matelas", "sub": "latex", "bed_size": "160x200"}),
    ("Câble HDMI 2.1 8K 2 m", "TV - Accessoires", None),
    ("Support TV mural orientable 32-75 pouces", None, None),
    ("Coque silicone pour Ombrion X5", "Téléphonie > Accessoires", None),
    ("Chargeur rapide USB-C 65 W", None, None),
    ("Smartwatch Chronia Fit reconditionnée", "Montres connectées reconditionnées", None),
    ("Housse de protection pour PC portable 15 pouces", None, None),
    ("Station de recharge pour manettes Ludika", "Accessoires", None),
    ("Filtre HEPA pour aspirateur Zephyr V10", None, None),
    ("Table basse ronde Lumen", "Salon > Tables basses", None),
    ("Lampe de bureau LED Lumen", None, None),
    ("Pack 3 jeux Ludika One", "Jeux vidéo", None),
    ("Télécommande de remplacement pour TV Kanzo", None, None),
]


def same(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(a - b) < 0.05
    return a == b


def measure(offers=None):
    """Chaque offre lue comme la collecte → {famille: compteurs}, écarts."""
    offers = OFFERS if offers is None else offers
    store = Store(Path(tempfile.mkdtemp(), "ontologie.sqlite"))
    market = Market(store, clock=lambda: 1_760_000_000.0)
    blank = lambda: {"offres": 0, "rangées": 0, "types dits": 0, "types justes": 0, "types faux": 0, "types pas lus": 0,
                     "types devinés": 0, "attributs dits": 0, "attributs justes": 0, "attributs faux": 0, "attributs pas lus": 0,
                     "attributs devinés": 0, "pièges": 0, "pièges écartés": 0}
    out, gaps = defaultdict(blank), []
    for n, (title, declared, want) in enumerate(offers):
        pid = market.match_product({"title": title, "gtin": gtin(70000 + n), "category": declared})
        p = store.q("SELECT category, attributes FROM products WHERE id=?", (pid,), one=True)
        cat, a = p["category"], json.loads(p["attributes"] or "{}")
        tracked = cat in FAMILY_OF
        if want is None:
            r = out["Pièges"]
            r["pièges"] += 1
            r["pièges écartés"] += not tracked
            if tracked:
                gaps.append((title, "hors catalogue", cat))
            continue
        r = out[FAMILY[want["cat"]]]
        r["offres"] += 1
        if cat != want["cat"] or not tracked:
            gaps.append((title, want["cat"], f"{cat}{'' if tracked or not cat else ' (pas suivi)'}"))
            continue
        r["rangées"] += 1
        feats = set(a.get("features") or ())
        sub = a.get("sub") or (want.get("sub") if want.get("sub") in feats else None)   # avant l'ontologie : la fonction du même nom
        if "sub" in want:
            r["types dits"] += 1
            key = "types justes" if sub == want["sub"] else "types pas lus" if sub is None else "types faux"
            r[key] += 1
            if key != "types justes":
                gaps.append((title, f"type {want['sub']}", sub))
        elif sub is not None:
            r["types devinés"] += 1
            gaps.append((title, "type non dit", sub))
        for k in DECLARED[want["cat"]]:
            got = a.get(k, True if k in feats else None)     # avant l'ontologie : une fonction du même nom vaut « oui »
            if k in want:
                r["attributs dits"] += 1
                key = "attributs justes" if got is not None and same(got, want[k]) else "attributs pas lus" if got is None else "attributs faux"
                r[key] += 1
                if key != "attributs justes":
                    gaps.append((title, f"{k} {want[k]}", got))
            elif got is not None:
                r["attributs devinés"] += 1
                gaps.append((title, f"{k} non dit", got))
    store.close()
    return dict(out), gaps


def main():
    offers = INEDITES if ARGS.inedites else OFFERS
    out, gaps = measure(offers)
    total = {k: sum(r[k] for r in out.values()) for k in next(iter(out.values()))}
    print(f"{len(offers)} offres {'inédites' if ARGS.inedites else 'écrites comme dans les flux'} "
          f"({sum(1 for o in offers if o[2])} produits, {sum(1 for o in offers if not o[2])} pièges)")
    for fam in ("Électroménager", "Ameublement", "Literie", "Électronique", "Pièges", "Total"):
        r = total if fam == "Total" else out.get(fam)
        if not r:
            continue
        if fam == "Pièges":
            print(f"  {fam:15} {r['pièges écartés']}/{r['pièges']} tenus hors du catalogue")
            continue
        print(f"  {fam:15} rangées {r['rangées']:3d}/{r['offres']:<3d} · types {r['types justes']}/{r['types dits']} "
              f"(faux {r['types faux']}, pas lus {r['types pas lus']}, devinés {r['types devinés']}) · attributs "
              f"{r['attributs justes']}/{r['attributs dits']} (faux {r['attributs faux']}, pas lus {r['attributs pas lus']}, "
              f"devinés {r['attributs devinés']})" + (f" · pièges {r['pièges écartés']}/{r['pièges']}" if fam == "Total" else ""))
    if ARGS.v:
        for t, want, got in gaps:
            print(f"    « {t} » : attendu {want}, lu {got}")
    if ARGS.json:
        Path(ARGS.json).write_text(json.dumps({"familles": out, "total": total, "écarts": gaps}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
