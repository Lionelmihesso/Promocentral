"""Marché simulé à VÉRITÉ CONNUE : démo de l'app (SHOWCASE) et mesure des règles (bench/deals_truth.py, CATALOG).

Chaque offre suit un prix « normal » (érosion, bruit hebdomadaire, écart propre à l'enseigne) et subit des épisodes :
  vraie promo de l'enseigne  ~1 fois / 70 j, 5-10 j, -10 à -20 % (prix barré honnête 70 % du temps)
  Black Friday               85 % des offres, -12 à -25 % ; soldes d'hiver / d'été : 50 % / 40 % des offres, -8 à -15 %
  FAUSSE promo               ~1 fois / 150 j : prix gonflé de 30 % pendant 14 j, puis « -23 % » affiché pendant 7 j au
                             prix normal
  hausse temporaire          ~1 fois / 200 j : +12 % pendant 10 j ;   rupture : ~1 fois / 100 j, 3 à 8 j
Vérité par produit et par jour : OPPORTUNITÉ = meilleur prix en stock ≤ 92 % du meilleur prix normal du marché.
Deux offres sur trois déclarent la fin de leur promotion (dans le flux), comme beaucoup d'enseignes. Marques et
enseignes sont fictives.
"""
import random
import re
from xml.sax.saxutils import escape
from datetime import date, datetime, timedelta, timezone

# (catégorie, titre avec attributs, prix de base)
CATALOG = [
    ("canape", "Canapé 2 places tissu", 750), ("canape", "Canapé 3 places velours", 1150), ("canape", "Canapé 3 places convertible", 1350),
    ("canape", "Canapé d'angle 5 places", 1850),
    ("lit", "Lit 140x190 cadre de lit bois", 320), ("lit", "Lit 160x200 cadre de lit", 460), ("lit", "Lit 160x200 coffre de rangement", 640),
    ("lit", "Lit 180x200 cadre de lit", 690),
    ("matelas", "Matelas 140x190 mousse", 420), ("matelas", "Matelas 160x200 mousse", 590), ("matelas", "Matelas 160x200 ressorts ensachés", 820),
    ("matelas", "Matelas 180x200 mousse", 790),
    ("refrigerateur", "Réfrigérateur combiné 55 cm classe E", 480), ("refrigerateur", "Réfrigérateur combiné 60 cm classe D", 640),
    ("refrigerateur", "Réfrigérateur combiné 60 cm classe B", 820), ("refrigerateur", "Réfrigérateur combiné 70 cm classe C", 960),
    ("four", "Four encastrable multifonction classe A", 360), ("four", "Four encastrable pyrolyse classe A", 560),
    ("lave_linge", "Lave-linge 7 kg classe C", 390), ("lave_linge", "Lave-linge 8 kg classe B", 490), ("lave_linge", "Lave-linge 9 kg classe A", 640),
    ("lave_vaisselle", "Lave-vaisselle 45 cm 10 couverts classe E", 410), ("lave_vaisselle", "Lave-vaisselle 60 cm 13 couverts classe D", 470),
    ("lave_vaisselle", "Lave-vaisselle 60 cm 14 couverts 42 dB classe B", 620),
    ("table", "Table à manger 4 places", 380), ("table", "Table à manger 6 places chêne", 690), ("table", "Table à manger extensible 8 places", 940),
    ("lave_linge", "Lave-linge 10 kg classe A", 760), ("table", "Table à manger 6 places extensible", 820), ("canape", "Canapé 3 places cuir", 1990),
]
BRANDS = ["Nordvik", "Aurel", "Kessler", "Solenne"]
MERCHANTS = ["electroplus", "maisonco", "rapido", "bigbox"]

# Démo : titres et prix proches de ceux des enseignes, marques fictives — (catégorie, titre, prix de base, marque)
SHOWCASE = [
    ("lave_linge", "Lave-linge hublot {brand} WM8 8 kg 1400 tr/min classe A", 549, "Kessler"),
    ("lave_linge", "Lave-linge hublot {brand} Série 6 9 kg classe A", 689, "Brava"),
    ("lave_linge", "Lave-linge top {brand} T65 6,5 kg classe C", 449, "Helio"),
    ("lave_linge", "Lave-linge hublot {brand} Silence 10 kg classe A", 799, "Ostra"),
    ("seche_linge", "Sèche-linge pompe à chaleur {brand} DH8 8 kg classe A++", 699, "Kessler"),
    ("seche_linge", "Sèche-linge pompe à chaleur {brand} DH9 9 kg classe A+++", 849, "Brava"),
    ("lave_vaisselle", "Lave-vaisselle {brand} 60 cm 13 couverts 44 dB classe C", 529, "Helio"),
    ("lave_vaisselle", "Lave-vaisselle encastrable {brand} 60 cm 14 couverts classe B", 749, "Ostra"),
    ("lave_vaisselle", "Lave-vaisselle {brand} 45 cm 10 couverts classe D", 449, "Kessler"),
    ("refrigerateur", "Réfrigérateur combiné {brand} 60 cm No Frost 331 L classe C", 699, "Brava"),
    ("refrigerateur", "Réfrigérateur américain {brand} 91 cm 635 L classe E", 1499, "Helio"),
    ("refrigerateur", "Réfrigérateur multi-portes {brand} 70 cm 450 L classe D", 1199, "Ostra"),
    ("congelateur", "Congélateur armoire {brand} No Frost 242 L classe E", 649, "Kessler"),
    ("four", "Four encastrable pyrolyse {brand} 71 L classe A+", 599, "Brava"),
    ("four", "Four vapeur combiné {brand} 70 L classe A", 899, "Helio"),
    ("plaque_cuisson", "Plaque induction {brand} 4 foyers 60 cm", 449, "Ostra"),
    ("plaque_cuisson", "Plaque induction {brand} 3 foyers flex 60 cm", 549, "Kessler"),
    ("hotte", "Hotte décorative murale {brand} 90 cm 700 m³/h", 499, "Brava"),
    ("canape", "Canapé d'angle convertible {brand} Oslo 5 places tissu", 1290, "Nordvik"),
    ("canape", "Canapé 3 places {brand} Lina velours côtelé", 899, "Varenne"),
    ("canape", "Canapé 2 places {brand} Milo cuir pleine fleur", 1490, "Aurel"),
    ("canape", "Canapé convertible {brand} Bergen couchage 140x190", 749, "Lumen"),
    ("canape", "Canapé d'angle {brand} Ravel méridienne réversible", 1690, "Varenne"),
    ("fauteuil", "Fauteuil relax {brand} Nils électrique cuir", 899, "Aurel"),
    ("fauteuil", "Fauteuil {brand} Louise bouclette", 399, "Varenne"),
    ("fauteuil", "Fauteuil {brand} Oscar velours pieds laiton", 349, "Lumen"),
    ("lit", "Lit coffre {brand} Aria 160x200 avec tête de lit", 699, "Nordvik"),
    ("lit", "Lit adulte {brand} Kara 140x190 chêne massif", 549, "Lumen"),
    ("lit", "Lit adulte {brand} Tilda 180x200 tête capitonnée", 899, "Nordvik"),
    ("armoire", "Armoire {brand} Lund 3 portes 150 cm", 649, "Nordvik"),
    ("armoire", "Dressing {brand} Modulo 200 cm portes coulissantes", 899, "Lumen"),
    ("table", "Table à manger extensible {brand} Viggo 6 à 10 places chêne", 899, "Varenne"),
    ("table", "Table à manger {brand} Roma céramique 8 places", 1190, "Aurel"),
    ("table", "Table à manger {brand} Nora ronde 4 places", 499, "Nordvik"),
    ("buffet", "Buffet {brand} Siena 3 portes 180 cm noyer", 749, "Varenne"),
    ("meuble_tv", "Meuble TV {brand} Halden 200 cm chêne clair", 449, "Nordvik"),
    ("commode", "Commode {brand} Ella 6 tiroirs", 399, "Lumen"),
    ("matelas", "Matelas {brand} Hybrid 160x200 ressorts ensachés", 899, "Dormea"),
    ("matelas", "Matelas {brand} Mémoire 140x190 mousse à mémoire de forme", 599, "Solenne"),
    ("matelas", "Matelas {brand} Confort+ 180x200 ressorts ensachés", 1190, "Dormea"),
    ("matelas", "Matelas {brand} Latex 160x200 latex naturel", 1290, "Solenne"),
    ("matelas", "Matelas {brand} Essentiel 90x190 mousse", 299, "Dormea"),
    ("matelas", "Matelas {brand} Ressorts 140x190 ferme", 449, "Solenne"),
    ("matelas", "Matelas {brand} Air 160x200 mousse respirante", 749, "Dormea"),
    ("matelas", "Matelas {brand} Enfant 90x190 mousse", 199, "Solenne"),
    ("sommier", "Sommier tapissier {brand} 160x200 lattes", 399, "Dormea"),
    ("sommier", "Sommier électrique {brand} relaxation 2x80x200", 1190, "Solenne"),
    ("sommier", "Sommier {brand} à lattes 140x190 pieds inclus", 249, "Dormea"),
    # de quoi comparer : l'aspirateur haut de gamme et ses alternatives, et des équivalents moins chers ailleurs
    ("aspirateur", "Aspirateur balai sans fil {brand} V15 Detect 60 min", 699, "Zephyr"),
    ("aspirateur", "Aspirateur balai sans fil {brand} V8 Origin 40 min", 399, "Zephyr"),
    ("aspirateur", "Aspirateur balai sans fil {brand} X5 Animal 50 min", 349, "Brava"),
    ("aspirateur", "Aspirateur balai sans fil {brand} Flex 45 min", 259, "Kessler"),
    ("aspirateur", "Aspirateur balai sans fil {brand} Agile 30 min", 179, "Helio"),
    ("aspirateur", "Aspirateur traîneau sans sac {brand} Silence 750 W", 229, "Ostra"),
    ("robot_aspirateur", "Robot aspirateur laveur {brand} S8 navigation laser", 549, "Ostra"),
    ("robot_aspirateur", "Robot aspirateur laveur {brand} R5 navigation laser", 329, "Brava"),
    ("lave_linge", "Lave-linge hublot {brand} Eco 9 kg 1200 tr/min classe A", 479, "Helio"),
    ("lave_vaisselle", "Lave-vaisselle {brand} 60 cm 14 couverts 42 dB classe B", 579, "Kessler"),
    ("canape", "Canapé d'angle convertible {brand} Nordic 5 places", 899, "Lumen"),
]
SHOWCASE_MERCHANTS = ["Électro Plus", "Maison & Co", "Rapido", "Grand Bazar"]
# v59 : l'électronique — téléviseurs, smartphones, ordinateurs portables, tablettes, casques, enceintes, montres, consoles,
# écrans ; des titres comme ceux des enseignes (pouces ou centimètres, « 16 Go RAM » à côté du stockage), de quoi comparer
# (un même type, une même taille d'écran ailleurs moins cher) et ce qui ne se compare pas (une édition numérique, un
# téléviseur Full HD). Simulés à part (leur propre tirage) : les produits d'avant gardent exactement leurs prix.
SHOWCASE_TECH = [
    ("televiseur", "TV OLED {brand} 55OL8 55\" 4K UHD 120 Hz Smart TV", 1290, "Vistrel"),
    ("televiseur", "TV OLED {brand} A55 139 cm 4K Ultra HD", 1090, "Kanzo"),
    ("televiseur", "TV OLED {brand} 65\" 4K 120 Hz Dolby Vision", 1790, "Kanzo"),
    ("televiseur", "TV QLED {brand} Q60 55\" (139 cm) 4K UHD Smart TV", 649, "Vistrel"),
    ("televiseur", "TV QLED {brand} Q55 55 pouces 4K", 549, "Orvia"),
    ("televiseur", "TV QLED {brand} 65 pouces 4K UHD", 799, "Orvia"),
    ("televiseur", "Téléviseur Mini LED {brand} 65\" 4K 144 Hz", 1190, "Vistrel", {"Taille de l'écran": "65 pouces"}),
    ("televiseur", "TV LED {brand} 55U6 55 pouces 4K", 379, "Kanzo"),
    ("televiseur", "TV LED {brand} 55\" 4K UHD Smart TV", 429, "Vistrel"),
    ("televiseur", "TV LED {brand} 43UX7 108 cm 4K Ultra HD", 329, "Kanzo"),
    ("televiseur", "TV LED {brand} 43\" Full HD", 249, "Orvia"),
    ("smartphone", "Smartphone {brand} X3 Pro 5G 256 Go Noir", 1099, "Ombrion"),
    ("smartphone", "Smartphone {brand} V12 5G 256 Go", 899, "Velto"),
    ("smartphone", "Smartphone {brand} X3 5G 128 Go", 699, "Ombrion"),
    ("smartphone", "Smartphone {brand} A5 5G 128 Go 6,6\"", 349, "Aphel"),
    ("smartphone", "Smartphone {brand} A2 4G 64 Go", 149, "Aphel"),
    ("smartphone", "Smartphone pliable {brand} Fold 2 5G 512 Go", 1599, "Ombrion"),
    ("ordinateur_portable", "PC portable {brand} Vivo 15 15,6\" Intel Core i5 16 Go RAM 512 Go SSD", 749, "Calixo"),
    ("ordinateur_portable", "Ordinateur portable {brand} Nova 15 15,6 pouces 16 Go RAM 512 Go SSD", 629, "Ternis"),
    ("ordinateur_portable", "PC portable gamer {brand} Strix 16\" 32 Go RAM 1 To SSD", 1799, "Calixo"),
    ("ordinateur_portable", "Ordinateur portable ultraportable {brand} Air 14\" 16 Go RAM 1 To", 1199, "Ternis"),
    ("ordinateur_portable", "Chromebook {brand} C14 14\" 8 Go RAM 128 Go", 349, "Calixo"),
    ("tablette", "Tablette tactile {brand} Tab 11 11\" 128 Go Wi-Fi", 449, "Tavelo"),
    ("tablette", "Tablette tactile {brand} Pad 11 11 pouces 128 Go", 329, "Ombrion"),
    ("tablette", "Tablette enfant {brand} Kids 8\" 32 Go", 119, "Tavelo"),
    ("casque_audio", "Casque sans fil à réduction de bruit {brand} H700 Bluetooth", 379, "Sonoryn"),
    ("casque_audio", "Casque Bluetooth à réduction de bruit {brand} Q35", 279, "Aurio"),
    ("casque_audio", "Casque audio filaire {brand} Studio", 99, "Aurio"),
    ("casque_audio", "Écouteurs sans fil {brand} Buds 3 réduction de bruit", 199, "Sonoryn"),
    ("casque_audio", "Écouteurs true wireless {brand} Air ANC", 129, "Aurio"),
    ("enceinte", "Barre de son {brand} 5.1.2 Dolby Atmos", 699, "Brisko"),
    ("enceinte", "Barre de son Dolby Atmos {brand} Cine 3.1.2", 549, "Aurio"),
    ("enceinte", "Enceinte Bluetooth portable {brand} Go 3 étanche IP67", 149, "Brisko"),
    ("enceinte", "Enceinte portable étanche {brand} Wave", 99, "Aurio"),
    ("montre_connectee", "Montre connectée {brand} Pace 3 GPS AMOLED", 349, "Chronia"),
    ("montre_connectee", "Montre connectée GPS {brand} Run 5", 249, "Tempra"),
    ("montre_connectee", "Bracelet connecté {brand} Fit 3", 59, "Chronia"),
    ("console", "Console de salon {brand} One 1 To", 549, "Ludika"),
    ("console", "Console de salon {brand} One Édition Numérique 1 To", 449, "Ludika"),
    ("console", "Console portable {brand} Go OLED", 329, "Ludika"),
    ("ecran_pc", "Écran PC gaming {brand} 27\" QHD 165 Hz", 299, "Calixo"),
    ("ecran_pc", "Écran gaming {brand} G27 27 pouces 170 Hz", 249, "Ternis"),
    ("ecran_pc", "Écran PC incurvé {brand} 34\" UWQHD 144 Hz", 449, "Calixo"),
]
# v57 : de quoi parcourir les aspirateurs par type et par besoin — chaque sous-famille, des fiches plus ou moins
# complètes (caractéristiques déclarées comme le font les enseignes, avec leurs noms et leurs formats), marques fictives.
# Simulés à part (leur propre tirage) : les produits d'avant gardent exactement leurs prix.
SHOWCASE_MORE = [
    ("aspirateur", "Aspirateur balai sans fil {brand} Aero 12 Animal", 329, "Kessler",
     {"Autonomie": "60 min", "Poids": "2,4 kg", "Brosse anti-enchevêtrement": "Oui", "Filtre HEPA": "Oui", "Utilisable en aspirateur à main": "Oui",
      "Niveau sonore": "78 dB"}),
    ("aspirateur", "Aspirateur balai sans fil {brand} Slim 5 Lite", 189, "Helio",
     {"Autonomie maximale": "35 minutes", "Poids net": "1,9 kg", "Brosse motorisée": "Oui", "Filtre HEPA": "Non", "Utilisable en aspirateur à main": "Oui"}),
    ("aspirateur", "Aspirateur balai 2 en 1 sans fil {brand} Duo 25 min", 129, "Brava", {"Poids": "2,1 kg", "Brosse motorisée": "Non"}),
    ("aspirateur", "Aspirateur balai sans fil {brand} U9 Ultra 90 min", 549, "Zephyr",
     {"Autonomie": "90 min", "Poids": "3,1 kg", "Batterie amovible": "Oui", "Filtre HEPA": "Oui", "Brosse parquet": "Oui", "Brosse motorisée": "Oui",
      "Puissance d'aspiration": "230 AW"}),
    ("aspirateur", "Aspirateur balai filaire {brand} Classic", 99, "Ostra", {"Poids": "3,4 kg", "Niveau sonore": "80 dB", "Rayon d'action": "8 m"}),
    ("aspirateur", "Aspirateur balai sans fil {brand} Flex Pet 50 min", 279, "Brava", {"Poids": "2,7 kg", "Spécial animaux": "Oui", "Filtre HEPA": "Oui"}),
    ("aspirateur", "Aspirateur balai sans fil {brand} Parquet 45 min", 239, "Kessler", {"Brosse parquet": "Oui", "Poids": "2,5 kg", "Niveau sonore": "74 dB"}),
    ("aspirateur", "Aspirateur balai sans fil {brand} Calme 40 min", 219, "Helio", {"Niveau sonore (dB)": "69 dB(A)", "Poids": "2,2 kg"}),
    ("aspirateur", "Aspirateur traîneau avec sac {brand} Silence Pro 650 W", 249, "Kessler",
     {"Niveau sonore": "62 dB", "Filtre HEPA": "Oui", "Rayon d'action": "10 m", "Sac": "Avec sac", "Poids": "5,8 kg"}),
    ("aspirateur", "Aspirateur traîneau sans sac {brand} Cyclo Animal 800 W", 199, "Brava",
     {"Brosse motorisée": "Oui", "Brosse poils d'animaux": "Oui", "Niveau sonore": "78 dB", "Rayon d'action": "9 m"}),
    ("aspirateur", "Aspirateur traîneau sans sac {brand} Compact 700 W", 119, "Helio", {"Poids": "4,6 kg", "Rayon d'action": "7 m", "Niveau sonore": "80 dB"}),
    ("aspirateur", "Aspirateur traîneau sans sac {brand} Allergy 750 W", 279, "Zephyr",
     {"Filtration": "HEPA H13", "Niveau sonore": "70 dB", "Brosse parquet": "Oui", "Rayon d'action": "11 m"}),
    ("aspirateur", "Aspirateur traîneau avec sac {brand} Eco 550 W", 89, "Ostra", {"Sac": "Avec sac", "Niveau sonore": "76 dB"}),
    ("robot_aspirateur", "Robot aspirateur laveur {brand} Q7 navigation laser avec station de vidage", 649, "Kessler",
     {"Navigation": "Laser (LiDAR)", "Station de vidage": "Oui", "Fonction serpillière": "Oui", "Autonomie": "180 min", "Puissance d'aspiration": "5000 Pa",
      "Brosse anti-enchevêtrement": "Oui", "Niveau sonore": "65 dB"}),
    ("robot_aspirateur", "Robot aspirateur {brand} Navi 3 caméra", 299, "Helio",
     {"Navigation": "Caméra", "Autonomie": "120 min", "Puissance d'aspiration": "2700 Pa", "Niveau sonore": "62 dB"}),
    ("robot_aspirateur", "Robot aspirateur {brand} Mini R2", 149, "Brava", {"Navigation": "Aléatoire", "Autonomie": "90 min", "Cartographie": "Non", "Niveau sonore": "64 dB"}),
    ("robot_aspirateur", "Robot aspirateur {brand} Pet S5 navigation laser", 399, "Ostra",
     {"Navigation": "Laser", "Brosse anti-enchevêtrement": "Oui", "Filtre HEPA": "Oui", "Autonomie": "150 min", "Station de vidage": "Non"}),
    ("robot_aspirateur", "Robot aspirateur laveur {brand} Aqua 2 gyroscope", 229, "Zephyr", {"Navigation": "Gyroscope", "Fonction lavage": "Oui", "Autonomie": "100 min"}),
    ("robot_aspirateur", "Robot aspirateur {brand} X9 avec station de vidage", 499, "Brava",
     {"Navigation": "Laser", "Station de vidage": "Oui", "Autonomie": "200 min", "Puissance d'aspiration": "4000 Pa"}),
    ("aspirateur", "Aspirateur laveur sans fil {brand} Wave 1", 349, "Kessler", {"Autonomie": "35 min", "Auto-nettoyage": "Oui", "Poids": "4,4 kg", "Niveau sonore": "78 dB"}),
    ("aspirateur", "Aspirateur laveur sans fil {brand} Aqua Pro", 449, "Ostra", {"Autonomie": "45 min", "Auto-nettoyage": "Oui", "Poids": "4,9 kg"}),
    ("aspirateur", "Nettoyeur de sols sans fil {brand} Clean 3", 279, "Helio", {"Autonomie": "30 min", "Poids": "3,9 kg"}),
    ("aspirateur", "Aspirateur à main sans fil {brand} Mini Animal", 79, "Brava", {"Autonomie": "20 min", "Poids": "1,1 kg", "Brosse poils d'animaux": "Oui"}),
    ("aspirateur", "Aspirateur à main sans fil {brand} Auto 15 min", 49, "Helio", {"Poids": "0,9 kg"}),
    ("aspirateur", "Aspirateur à main sans fil {brand} Pocket", 39, "Ostra", {}),
]


def gtin(n):
    body = f"{300000000000 + n:012d}"
    total = sum(int(x) * (3 if i % 2 else 1) for i, x in enumerate(body))
    return body + str((10 - total % 10) % 10)


def retail_events(year):
    """Calendrier commercial français : Black Friday, soldes d'hiver et d'été."""
    nov1 = date(year, 11, 1)
    bf = nov1 + timedelta(days=(4 - nov1.weekday()) % 7 + 21)
    jan1 = date(year, 1, 1)
    winter = jan1 + timedelta(days=(2 - jan1.weekday()) % 7 + 7)
    jun30 = date(year, 6, 30)
    summer = jun30 - timedelta(days=(jun30.weekday() - 2) % 7)
    return {"black_friday": (bf - timedelta(days=7), bf + timedelta(days=3)),
            "soldes_hiver": (winter, winter + timedelta(days=27)),
            "soldes_ete": (summer, summer + timedelta(days=27))}


def slug(name):
    return re.sub(r"[^a-z0-9]", "", name.lower().replace("é", "e").replace("&", ""))


class Market:
    def __init__(self, start=date(2026, 1, 5), days=200, seed=4, catalog=CATALOG, merchants=MERCHANTS, extra=()):
        """extra : des groupes de produits de plus [(catégorie, titre, prix, marque, fiche déclarée)…], chacun simulé avec
        son propre tirage : les produits d'avant gardent exactement leurs prix."""
        self.start, self.days = start, days
        rng = random.Random(seed)
        self.products, self.offers = [], []
        self._add(catalog, rng, merchants)
        self._simulate(rng)
        for n, group in enumerate(extra):
            more = random.Random(seed * 1000 + 57 + n)
            first = len(self.offers)
            self._add(group, more, merchants)
            self._simulate(more, self.offers[first:])

    def _add(self, catalog, rng, merchants):
        for slug_, label, base, *named in catalog:
            i = len(self.products)
            brand = named[0] if named else BRANDS[i % len(BRANDS)]
            cls = re.search(r"classe ([A-G])", label)
            title = label.format(brand=brand) if "{brand}" in label else \
                label.replace(" classe", f" {brand} classe") if cls else f"{label} {brand}"
            self.products.append({"id": i, "category": slug_, "brand": brand, "gtin": gtin(i), "base": base * rng.uniform(0.92, 1.08),
                                  "title": title, "energy": cls.group(1) if cls else None, "props": named[1] if len(named) > 1 else {}})
            for m in rng.sample(merchants, 3):
                self.offers.append({"pid": i, "merchant": m, "url": f"https://{slug(m)}.sim/p/{i}", "factor": rng.uniform(0.97, 1.06)})

    def _simulate(self, rng, offers=None):
        D = self.days
        for o in self.offers if offers is None else offers:
            p = self.products[o["pid"]]
            normal, noise = [], 1.0
            for k in range(D):
                if (self.start + timedelta(days=k)).weekday() == 0:
                    noise = rng.uniform(0.98, 1.025)
                normal.append(round(p["base"] * o["factor"] * (1 - 0.06 * k / 365) * noise))
            price, listp, stock, kind, until = normal[:], [None] * D, [True] * D, ["normal"] * D, [None] * D

            def paint(a, b, fn, label):
                for j in range(max(0, a), min(D, b)):
                    if kind[j] == "normal":
                        fn(j)
                        kind[j] = label
                        until[j] = b - 1 if label in ("true_promo", "fake_promo") else None
            for y in (self.start.year, self.start.year + 1):
                for name, (a, b) in retail_events(y).items():
                    prob, lo, hi = {"black_friday": (0.85, .12, .25), "soldes_hiver": (0.5, .08, .15), "soldes_ete": (0.4, .08, .15)}[name]
                    if rng.random() < prob:
                        dep = rng.uniform(lo, hi)

                        def f(j, dep=dep):
                            price[j] = round(normal[j] * (1 - dep))
                            listp[j] = normal[j]
                        paint((a - self.start).days, (b - self.start).days + 1, f, "true_promo")
            k = 0
            while k < D:
                r = rng.random()
                if r < 1 / 70:
                    n, dep, honest = rng.randint(5, 10), rng.uniform(.10, .20), rng.random() < 0.7

                    def f(j, dep=dep, honest=honest):
                        price[j] = round(normal[j] * (1 - dep))
                        listp[j] = normal[j] if honest else None
                    paint(k, k + n, f, "true_promo")
                    k += n
                elif r < 1 / 70 + 1 / 150:
                    def up(j):
                        price[j] = round(normal[j] * 1.30)

                    def fake(j):
                        price[j] = round(normal[j] * rng.uniform(0.98, 1.02))
                        listp[j] = round(normal[j] * 1.30)
                    paint(k, k + 14, up, "inflated")
                    paint(k + 14, k + 21, fake, "fake_promo")
                    k += 21
                elif r < 1 / 70 + 1 / 150 + 1 / 200:
                    def hike(j):
                        price[j] = round(normal[j] * 1.12)
                    paint(k, k + 10, hike, "hike")
                    k += 10
                elif r < 1 / 70 + 1 / 150 + 1 / 200 + 1 / 100:
                    n = rng.randint(3, 8)
                    for j in range(k, min(D, k + n)):
                        stock[j] = False
                    k += n
                else:
                    k += 1
            o.update(normal=normal, price=price, list=listp, stock=stock, kind=kind, until=until,
                     declares=int(o["factor"] * 1000) % 3 != 0)      # deux offres sur trois annoncent la fin (sans tirage)

    def truth(self, pid, k):
        """Vérité du jour k pour un produit : opportunité réelle ?"""
        offs = [o for o in self.offers if o["pid"] == pid]
        live = [o for o in offs if o["stock"][k]]
        if not live:
            return {"opp": False, "best": None}
        best = min(o["price"][k] for o in live)
        return {"opp": best <= min(o["normal"][k] for o in offs) * 0.92, "best": best}

    def feed(self, merchant, k, fmt="xml"):
        """Le flux produits d'une enseigne simulée le jour k : toutes ses offres du jour, au format Google
        Shopping (XML, espace de noms g:) ou en CSV à la française (point-virgule, virgule décimale, Windows-1252)."""
        day = self.start + timedelta(days=k)
        rows = []
        for o in (x for x in self.offers if x["merchant"] == merchant):
            p = self.products[o["pid"]]
            price, listed, stock, until = o["price"][k], o["list"][k], o["stock"][k], o["until"][k]
            end = self.start + timedelta(days=until) if listed and o["declares"] and until is not None else None
            props = ([("Classe énergétique", p["energy"])] if p["energy"] else []) + list(p["props"].items())
            rows.append({"id": f"{o['pid']}", "title": p["title"], "url": o["url"], "brand": p["brand"], "gtin": p["gtin"],
                         "category": p["category"].replace("_", "-"), "price": price, "list": listed, "stock": stock,
                         "end": end, "props": props})
        if fmt == "csv":
            dec = lambda v: f"{v:.2f}".replace(".", ",")
            lines = ["id;nom;marque;ean;categorie;lien;prix;prix_barre;disponibilite;fin_promo;caracteristiques"]
            for r in rows:
                lines.append(";".join([r["id"], r["title"], r["brand"], r["gtin"], r["category"], r["url"], dec(r["price"]),
                                       dec(r["list"]) if r["list"] else "", "En stock" if r["stock"] else "Rupture",
                                       r["end"].strftime("%d/%m/%Y") if r["end"] else "",
                                       " | ".join(f"{n}: {v}" for n, v in r["props"])]))
            return ("\r\n".join(lines) + "\r\n").encode("cp1252")
        x = lambda v: escape(str(v))
        items = []
        for r in rows:
            regular, sale = (r["list"], r["price"]) if r["list"] else (r["price"], None)
            parts = [f"<g:id>{x(r['id'])}</g:id>", f"<title>{x(r['title'])}</title>", f"<link>{x(r['url'])}</link>",
                     f"<g:price>{regular:.2f} EUR</g:price>", f"<g:availability>{'in_stock' if r['stock'] else 'out_of_stock'}</g:availability>",
                     f"<g:gtin>{r['gtin']}</g:gtin>", f"<g:brand>{x(r['brand'])}</g:brand>",
                     f"<g:product_type>{x(r['category'])}</g:product_type>", "<g:condition>new</g:condition>"]
            if sale is not None:
                parts.append(f"<g:sale_price>{sale:.2f} EUR</g:sale_price>")
            if r["end"]:
                parts.append(f"<g:sale_price_effective_date>{day.isoformat()}T00:00+0100/{r['end'].isoformat()}T23:59+0100"
                             "</g:sale_price_effective_date>")
            parts += [f"<g:product_detail><g:attribute_name>{x(n)}</g:attribute_name><g:attribute_value>{x(v)}</g:attribute_value>"
                      "</g:product_detail>" for n, v in r["props"]]
            items.append("<item>" + "".join(parts) + "</item>")
        return ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0"><channel>'
                f"<title>{x(merchant)}</title><link>https://{slug(merchant)}.sim/</link>" + "".join(items) + "</channel></rss>\n").encode()


class SimClock:
    """Horloge réglable (10 h UTC du jour courant)."""

    def __init__(self, d):
        self.set(d)

    def set(self, d):
        self.t = datetime(d.year, d.month, d.day, 10, tzinfo=timezone.utc).timestamp()

    def __call__(self):
        return self.t
