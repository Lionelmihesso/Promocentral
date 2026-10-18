"""Enseignes suivies — Tech + Électroménager.

Sélection : top 5 de la catégorie « produits électroniques et électroménager » (Fevad/Médiamétrie 2025 : Amazon,
Boulanger, Cdiscount, Fnac, Darty), plus deux spécialistes de l'électroménager (Electro Dépôt, Ubaldi) et un spécialiste
tech (LDLC).

Amazon est désactivé : ses conditions d'utilisation interdisent la collecte automatisée ; il viendra plus tard par son
programme d'affiliation (API produits).

`product_url` et les plans de site sont des POINTS DE DÉPART : ils sont à confirmer avec `python collect.py discover`
puis `python collect.py diagnose`, qui mesurent ce qui marche vraiment. Les plans de site sont d'abord lus dans
robots.txt (lignes « Sitemap: ») ; `sitemaps` ne sert que de complément.
"""

RETAILERS = {
    "boulanger": {"name": "Boulanger", "home": "https://www.boulanger.com", "enabled": True,
                  "product_url": r"/ref/\d+", "sitemaps": []},
    "cdiscount": {"name": "Cdiscount", "home": "https://www.cdiscount.com", "enabled": True,
                  "product_url": r"/f-\d+-[a-z0-9]+\.html", "sitemaps": []},
    "fnac": {"name": "Fnac", "home": "https://www.fnac.com", "enabled": True,
             "product_url": r"/a\d+/", "sitemaps": []},
    "darty": {"name": "Darty", "home": "https://www.darty.com", "enabled": True,
              "product_url": r"/nav/achat/.+\.html", "sitemaps": []},
    "electrodepot": {"name": "Electro Dépôt", "home": "https://www.electrodepot.fr", "enabled": True,
                     "product_url": r"\.html$", "sitemaps": []},
    "ubaldi": {"name": "Ubaldi", "home": "https://www.ubaldi.com", "enabled": True,
               "product_url": r"\.php$|/[a-z0-9-]+-\d+\.php", "sitemaps": []},
    "ldlc": {"name": "LDLC", "home": "https://www.ldlc.com", "enabled": True,
             "product_url": r"/fiche/[A-Z0-9]+\.html", "sitemaps": []},
    "amazon": {"name": "Amazon", "home": "https://www.amazon.fr", "enabled": False,
               "disabled_reason": "Collecte automatisée interdite par les conditions d'utilisation : passer par l'affiliation",
               "product_url": r"/dp/[A-Z0-9]{10}", "sitemaps": []},
}

# Catégories de départ et mots repérables dans l'adresse des pages produit (le titre de la page sert ensuite à confirmer)
CATEGORY_URL_HINTS = {
    "televiseur": ["televiseur", "tv-oled", "tv-qled", "tv-led", "television", "-tv-"],
    "ordinateur_portable": ["ordinateur-portable", "pc-portable", "macbook", "laptop"],
    "smartphone": ["smartphone", "iphone", "galaxy-s", "telephone-portable"],
    "casque_audio": ["casque", "ecouteurs", "airpods"],
    "enceinte": ["enceinte", "barre-de-son"],
    "tablette": ["tablette", "ipad"],
    "lave_linge": ["lave-linge"],
    "lave_vaisselle": ["lave-vaisselle"],
    "refrigerateur": ["refrigerateur", "frigo", "congelateur"],
    "four": ["four-encastrable", "four-multifonction", "four-pyrolyse"],
    "micro_ondes": ["micro-ondes"],
    "aspirateur": ["aspirateur"],
    "robot_aspirateur": ["robot-aspirateur", "aspirateur-robot"],
    "machine_cafe": ["machine-a-cafe", "expresso", "cafetiere"],
}

USER_AGENT = "DealsBot/0.1 (+https://deals.example/robot ; contact : robot@deals.example)"   # à remplacer par votre page et votre adresse
MIN_INTERVAL_S = 5.0     # au moins 5 s entre deux requêtes vers un même site
KEEP_THRESHOLD = 0.80    # une enseigne est gardée si ≥ 80 % de ses pages donnent un prix
