"""Enseignes et catégories suivies — Électroménager, Électronique, Ameublement, Literie : des achats chers, où une remise
compte.

Choix des enseignes : spécialistes en ligne de ces familles en France ; But et Cdiscount vendent les trois, ce qui limite
le nombre de sites à lire (et donc le coût). `product_url` et les plans de site sont des POINTS DE DÉPART :
`python deals.py discover <enseigne>` puis `python deals.py diagnose <enseigne>` mesurent depuis le serveur ce qui
marche (lecture, prix, prix barré, EAN, blocage) et tranchent : garder / règle à écrire / abandonner.

Constats publics relevés le 18/10/2026 (à confirmer par le diagnostic) :
- Conforama : défi Cloudflare sur tout le domaine et prix chargés après coup par le navigateur (description d'un outil de
  collecte du commerce, Apify). Désactivé : sans navigateur la page n'a pas de prix, et on ne force pas un défi anti-robot.
- Darty : anti-robot qui bloque les adresses de centres de données (même source). Désactivé par défaut ;
  `python deals.py diagnose darty` pour vérifier depuis votre serveur.
- But : l'EAN figure dans l'adresse des fiches (/produits/<EAN>/…) ; prix barré, pourcentage et fin de promotion visibles.
- Boulanger : vendeurs tiers sur certaines fiches (« vendu & expédié par … ») : le vendeur est enregistré.
- La Redoute : prix membres affichés à côté du prix public (jamais pris pour le prix public).
- Electro Dépôt : prix au format « 279€98 » ; une adresse de fiche relevée menait à une page liste (reconnue : rien
  n'est enregistré, l'offre est retirée).
Amazon : collecte automatisée interdite par ses conditions d'utilisation.
"""
from ..extract.categories import FAMILIES, FAMILY_OF  # noqa: F401  familles suivies (taxonomie partagée avec l'app)


RETAILERS = {
    "boulanger": {"name": "Boulanger", "home": "https://www.boulanger.com", "enabled": True, "families": ["electromenager", "electronique"],
                  "product_url": r"/ref/\d+", "sitemaps": []},
    "electrodepot": {"name": "Electro Dépôt", "home": "https://www.electrodepot.fr", "enabled": True,
                     "families": ["electromenager", "electronique"],
                     "product_url": r"^https?://[^/]+/[a-z0-9-]*\d[a-z0-9-]*\.html$", "sitemaps": []},
    "ubaldi": {"name": "Ubaldi", "home": "https://www.ubaldi.com", "enabled": True, "families": ["electromenager", "electronique"],
               "product_url": r"/[a-z0-9-]+-\d+\.php$", "sitemaps": []},
    "cdiscount": {"name": "Cdiscount", "home": "https://www.cdiscount.com", "enabled": True,
                  "families": ["electromenager", "electronique", "ameublement", "literie"], "product_url": r"/f-\d+-[a-z0-9]+\.html",
                  "sitemaps": []},
    "but": {"name": "But", "home": "https://www.but.fr", "enabled": True, "families": ["electromenager", "ameublement", "literie"],
            "product_url": r"/produits/\d{8,14}/[^/]+\.html", "sitemaps": []},
    "ikea": {"name": "IKEA", "home": "https://www.ikea.com", "enabled": True, "families": ["ameublement", "literie"],
             "product_url": r"/fr/fr/p/[a-z0-9-]+-s?\d{8}/?$", "sitemaps": []},
    "maisonsdumonde": {"name": "Maisons du Monde", "home": "https://www.maisonsdumonde.com", "enabled": True,
                       "families": ["ameublement", "literie"], "product_url": r"/FR/fr/p/[^/]+\.htm", "sitemaps": []},
    "laredoute": {"name": "La Redoute", "home": "https://www.laredoute.fr", "enabled": True, "families": ["ameublement", "literie"],
                  "product_url": r"/ppdp/prod-\d+\.aspx", "sitemaps": []},
    "venteunique": {"name": "Vente-unique", "home": "https://www.vente-unique.com", "enabled": True,
                    "families": ["ameublement", "literie"], "product_url": r"/p/[a-z0-9-]+", "sitemaps": []},
    "darty": {"name": "Darty", "home": "https://www.darty.com", "enabled": False, "families": ["electromenager", "electronique"],
              "disabled_reason": "anti-robot signalé bloquant les adresses de centres de données : vérifier avec diagnose",
              "product_url": r"/nav/achat/.+\.html", "sitemaps": []},
    "conforama": {"name": "Conforama", "home": "https://www.conforama.fr", "enabled": False,
                  "families": ["electromenager", "ameublement", "literie"],
                  "disabled_reason": "défi Cloudflare sur tout le site et prix chargés par le navigateur : illisible sans forcer",
                  "product_url": r"/p/\d+", "sitemaps": []},
    "amazon": {"name": "Amazon", "home": "https://www.amazon.fr", "enabled": False, "families": [],
               "disabled_reason": "collecte automatisée interdite par les conditions d'utilisation",
               "product_url": r"/dp/[A-Z0-9]{10}", "sitemaps": []},
}

# En dessous, c'est presque toujours un accessoire (filtre, housse, pieds…) : la fiche n'entre pas au catalogue.
# Un produit déjà suivi qui passe sous ce seuil reste suivi (c'est peut-être une bonne affaire).
MIN_PRICE = {"electromenager": 100.0, "electronique": 50.0, "ameublement": 100.0, "literie": 100.0}
# Un rayon où un vrai produit coûte moins (v57 : un aspirateur à main dès 30 € ; v59 : des écouteurs, une enceinte, un
# bracelet connecté dès 20 €) ; ses accessoires sont écartés par leur titre (« Filtre pour… », « Coque… », « Embouts… » :
# extract.categories.ACCESSORY).
MIN_PRICE_CATEGORY = {"aspirateur": 30.0, "casque_audio": 20.0, "enceinte": 20.0, "montre_connectee": 20.0}

# Mots repérables dans l'adresse des fiches (tri de départ ; le titre de la fiche confirme ensuite)
CATEGORY_URL_HINTS = {
    "lave_linge": ["lave-linge", "machine-a-laver"],
    "seche_linge": ["seche-linge"],
    "lave_vaisselle": ["lave-vaisselle"],
    "refrigerateur": ["refrigerateur", "frigo"],
    "congelateur": ["congelateur"],
    "four": ["four-encastrable", "four-multifonction", "four-pyrolyse", "four-pyrolytique", "four-vapeur", "four-a-chaleur"],
    "plaque_cuisson": ["plaque-induction", "plaque-de-cuisson", "table-de-cuisson", "table-induction", "plaque-vitroceramique",
                       "plaque-gaz"],
    "hotte": ["hotte"],
    "cuisiniere": ["cuisiniere"],
    "robot_aspirateur": ["robot-aspirateur", "aspirateur-robot", "robot-laveur"],
    "aspirateur": ["aspirateur"],
    "canape": ["canape", "sofa", "clic-clac", "banquette-convertible"],
    "fauteuil": ["fauteuil"],
    "lit": ["cadre-de-lit", "lit-coffre", "lit-double", "lit-adulte", "lit-90", "lit-140", "lit-160", "lit-180", "lit-mezzanine",
            "lit-superpose"],
    "armoire": ["armoire", "dressing", "penderie"],
    "table": ["table-a-manger", "table-de-salle-a-manger", "table-extensible", "table-de-repas"],
    "buffet": ["buffet", "bahut", "vaisselier", "enfilade"],
    "meuble_tv": ["meuble-tv", "banc-tv", "meuble-television"],
    "commode": ["commode"],
    "matelas": ["matelas"],
    "sommier": ["sommier"],
    "televiseur": ["televiseur", "television", "tv-led", "tv-oled", "tv-qled", "tv-mini-led", "smart-tv", "/tv-"],
    "smartphone": ["smartphone", "telephone-portable", "telephone-mobile", "iphone"],
    "ordinateur_portable": ["ordinateur-portable", "pc-portable", "laptop", "macbook", "chromebook"],
    "tablette": ["tablette-tactile", "tablette-android", "tablette-enfant", "ipad"],
    "casque_audio": ["casque-audio", "casque-bluetooth", "casque-sans-fil", "casque-gaming", "ecouteurs"],
    "enceinte": ["enceinte", "barre-de-son"],
    "montre_connectee": ["montre-connectee", "bracelet-connecte", "smartwatch"],
    "console": ["console-de-jeux", "console-de-jeu", "console-portable", "playstation", "xbox", "nintendo-switch"],
    "ecran_pc": ["ecran-pc", "ecran-gaming", "ecran-gamer", "ecran-incurve", "moniteur"],
}

KEEP_THRESHOLD = 0.80    # une enseigne est gardée si ≥ 80 % de ses pages donnent un prix
BREAKER = 5              # passe de nuit : 5 refus de suite sur un site → on arrête ce site pour la nuit
