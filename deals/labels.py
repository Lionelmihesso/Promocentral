"""Les mots de l'app pour les rayons et les fonctions : partagés par les lectures (catalog), la compréhension d'une
recherche (query) et les missions, sans qu'ils dépendent les uns des autres."""

CATEGORY_LABEL = {
    "lave_linge": "Lave-linge", "lave_linge_sechant": "Lave-linge séchants", "seche_linge": "Sèche-linge",
    "lave_vaisselle": "Lave-vaisselle", "refrigerateur": "Réfrigérateurs", "congelateur": "Congélateurs", "four": "Fours",
    "plaque_cuisson": "Plaques de cuisson", "hotte": "Hottes", "cuisiniere": "Cuisinières", "micro_ondes": "Micro-ondes",
    "machine_cafe": "Machines à café", "canape": "Canapés", "fauteuil": "Fauteuils", "lit": "Lits", "armoire": "Armoires",
    "table": "Tables", "buffet": "Buffets", "meuble_tv": "Meubles TV", "commode": "Commodes", "luminaire": "Luminaires",
    "matelas": "Matelas", "sommier": "Sommiers", "televiseur": "Téléviseurs", "smartphone": "Smartphones",
    "ordinateur_portable": "Ordinateurs portables", "casque_audio": "Casques", "enceinte": "Enceintes", "tablette": "Tablettes",
    "robot_aspirateur": "Robots aspirateurs", "aspirateur": "Aspirateurs", "montre_connectee": "Montres connectées"}
CATEGORY_ONE = {
    "lave_linge": "Lave-linge", "lave_linge_sechant": "Lave-linge séchant", "seche_linge": "Sèche-linge",
    "lave_vaisselle": "Lave-vaisselle", "refrigerateur": "Réfrigérateur", "congelateur": "Congélateur", "four": "Four",
    "plaque_cuisson": "Plaque de cuisson", "hotte": "Hotte", "cuisiniere": "Cuisinière", "micro_ondes": "Micro-ondes",
    "machine_cafe": "Machine à café", "canape": "Canapé", "fauteuil": "Fauteuil", "lit": "Lit", "armoire": "Armoire",
    "table": "Table", "buffet": "Buffet", "meuble_tv": "Meuble TV", "commode": "Commode", "luminaire": "Luminaire",
    "matelas": "Matelas", "sommier": "Sommier", "televiseur": "Téléviseur", "smartphone": "Smartphone",
    "ordinateur_portable": "Ordinateur portable", "casque_audio": "Casque", "enceinte": "Enceinte", "tablette": "Tablette",
    "robot_aspirateur": "Robot aspirateur", "aspirateur": "Aspirateur", "montre_connectee": "Montre connectée"}
FEATURE_LABEL = {"sans_fil": "Sans fil", "balai": "Balai", "traineau": "Traîneau", "laveur": "Laveur", "convertible": "Convertible",
                 "angle": "D'angle", "induction": "Induction", "encastrable": "Encastrable", "americain": "Américain",
                 "electrique": "Électrique"}
# Les pièces de la maison (accueil, « Inspirations du moment » ; une recherche « pour le salon ») → leurs rayons
ROOMS = {"chambre": ("Chambre", ("lit", "matelas", "sommier", "armoire", "commode")),
         "salon": ("Salon", ("canape", "fauteuil", "table", "buffet", "meuble_tv", "luminaire")),
         "cuisine": ("Cuisine", ("refrigerateur", "congelateur", "four", "plaque_cuisson", "hotte", "lave_vaisselle", "cuisiniere",
                                 "micro_ondes", "machine_cafe")),
         "buanderie": ("Buanderie", ("lave_linge", "seche_linge", "lave_linge_sechant")),
         "entretien": ("Entretien", ("aspirateur", "robot_aspirateur"))}
