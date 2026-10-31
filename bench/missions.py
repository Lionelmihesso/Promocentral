"""Missions en une phrase : ce qui est compris, sur des phrases comme on les tape.

Pour chaque phrase, l'interprétation attendue (catégorie, marque, fonctions, taille ou capacité, prix maximum) est écrite
à la main ; un refus attendu porte le début de son explication (« pas encore suivis », « pas reconnu »). Une phrase est
comprise si tout ce qu'elle dit est retrouvé et rien d'autre : ce qui n'est pas dit n'est pas exigé, un prix impossible
n'est pas retenu (il est demandé ensuite), une marque inconnue n'est pas inventée.

  python -m bench.missions
"""
from deals.errors import BadRequest
from deals.missions import interpret, label

BRANDS = ["Zephyr", "Kessler", "Dormea", "Nordvik", "Helio", "Lumen", "Brava", "Ostra"]
SUIVI, RECONNU = ("refus", "pas encore suivis"), ("refus", "pas reconnu")
# phrase → (catégorie, marque, fonctions, attributs, prix max[, domaine à ontologie : type, attributs exigés])
# Les aspirateurs : le domaine entier tant qu'aucun type n'est nommé ; « balai » est un type, « sans fil » un attribut
# exigé ; « robot laveur » : un robot (le plus précis des deux types nommés). v59 : chaque rayon suivi a son ontologie
# (« frigo américain » : le type américain ; « canapé convertible » : l'attribut convertible), l'électronique aussi.
PHRASES = [
    ("aspirateur balai sous 300 €", (None, None, [], {}, 300, {"domain": "aspirateurs", "sub": "balai"})),
    ("Je veux un aspirateur balai sans fil à moins de 300 euros", (None, None, [], {}, 300, {"domain": "aspirateurs", "sub": "balai",
                                                                                            "props": {"cordless": True}})),
    ("un aspirateur pas plus de 200 €", (None, None, [], {}, 200, {"domain": "aspirateurs"})),
    ("robot aspirateur laveur jusqu'à 500 €", (None, None, [], {}, 500, {"domain": "aspirateurs", "sub": "robot"})),
    ("lave-linge 9 kg moins de 500€", (None, None, [], {"capacity_kg": 9}, 500, {"domain": "lave_linge"})),
    ("lave linge 8kg max 450", (None, None, [], {"capacity_kg": 8}, 450, {"domain": "lave_linge"})),
    ("sèche-linge 8 kg sous 600 €", (None, None, [], {"capacity_kg": 8}, 600, {"domain": "seche_linge"})),
    ("lave-vaisselle 60 cm classe C sous 600 €", (None, None, [], {"width_cm": 60, "energy_class": "C"}, 600, {"domain": "lave_vaisselle"})),
    ("lave vaisselle 13 couverts < 500 €", (None, None, [], {"place_settings": 13}, 500, {"domain": "lave_vaisselle"})),
    ("frigo américain jusqu'à 1 200 €", (None, None, [], {}, 1200, {"domain": "refrigerateur", "sub": "americain"})),
    ("congélateur moins de 300 €", (None, None, [], {}, 300, {"domain": "congelateur"})),
    ("plaque induction 4 foyers sous 350 €", (None, None, [], {"zones": 4}, 350, {"domain": "plaque_cuisson", "sub": "induction"})),
    ("four encastrable budget 400 €", (None, None, [], {}, 400, {"domain": "four", "sub": "encastrable"})),
    ("hotte en dessous de 250 €", (None, None, [], {}, 250, {"domain": "hotte"})),
    ("matelas 160x200 sous 600 €", (None, None, [], {"bed_size": "160x200"}, 600, {"domain": "matelas"})),
    ("matelas 140 x 190 à 400 euros max", (None, None, [], {"bed_size": "140x190"}, 400, {"domain": "matelas"})),
    ("un lit 160x200 jusqu'à 700€", (None, None, [], {"bed_size": "160x200"}, 700, {"domain": "lit"})),
    ("canapé d'angle sous 900 €", (None, None, [], {}, 900, {"domain": "canape", "sub": "angle"})),
    ("canapé convertible 3 places moins de 800 €", (None, None, [], {"seats": 3}, 800, {"domain": "canape", "props": {"convertible": True}})),
    ("table 6 places sous 400 €", (None, None, [], {"seats": 6}, 400, {"domain": "table"})),
    ("armoire sous 500 euros", (None, None, [], {}, 500, {"domain": "armoire"})),
    ("Zephyr sous 400 €", (None, "Zephyr", [], {}, 400)),
    ("matelas Dormea 160x200", (None, "Dormea", [], {"bed_size": "160x200"}, None, {"domain": "matelas"})),
    ("smartphone sous 300 €", (None, None, [], {}, 300, {"domain": "smartphone"})),          # v59 : l'électronique est suivie
    ("un truc sympa pour le salon", RECONNU),
    # tournures du quotidien
    ("aspi sans fil 250 balles", (None, None, [], {}, 250, {"domain": "aspirateurs", "props": {"cordless": True}})),
    ("je cherche un frigo pas cher", (None, None, [], {}, None, {"domain": "refrigerateur"})),
    ("machine à laver 9kg 450€", (None, None, [], {"capacity_kg": 9}, 450, {"domain": "lave_linge"})),
    ("lave-linge 1400 tours 9 kg moins de 600", (None, None, [], {"capacity_kg": 9}, 600, {"domain": "lave_linge"})),
    ("matelas 160 sur 200 sous 500 €", (None, None, [], {"bed_size": "160x200"}, 500, {"domain": "matelas"})),
    ("lit 2 places sous 400", (None, None, [], {}, 400, {"domain": "lit"})),                  # un lit n'a pas de places assises
    ("canapé 3 places en dessous de 1 500 €", (None, None, [], {"seats": 3}, 1500, {"domain": "canape"})),
    ("meuble télé sous 200 €", (None, None, [], {}, 200, {"domain": "meuble_tv"})),
    ("aspirateur Dyson V15 sous 500 €", (None, None, [], {}, 500, {"domain": "aspirateurs"})),  # marque inconnue : pas inventée
    ("réfrigérateur sous 0 €", (None, None, [], {}, None, {"domain": "refrigerateur"})),      # prix impossible : demandé ensuite
    ("TV 55 pouces sous 500", (None, None, [], {"screen_in": 55}, 500, {"domain": "televiseur"})),
    ("micro-ondes sous 150 €", SUIVI),
    # v59 : l'électronique, comme on la demande
    ("TV OLED 65 pouces moins de 1 500 €", (None, None, [], {"screen_in": 65}, 1500, {"domain": "televiseur", "sub": "oled"})),
    ("télé 139 cm 4K sous 600 €", (None, None, [], {"screen_in": 55}, 600, {"domain": "televiseur", "props": {"uhd": True}})),
    ("smartphone 5G 128 Go sous 400 €", (None, None, [], {"storage_gb": 128}, 400, {"domain": "smartphone", "props": {"network_5g": True}})),
    ("iphone 256 go jusqu'à 1000 €", (None, None, [], {"storage_gb": 256}, 1000, {"domain": "smartphone"})),
    ("PC portable 16 Go de RAM jusqu'à 900 €", (None, None, [], {"ram_gb": 16}, 900, {"domain": "ordinateur_portable"})),
    ("casque à réduction de bruit sous 300 €", (None, None, [], {}, 300, {"domain": "casque_audio", "sub": "casque", "props": {"anc": True}})),
    ("écouteurs sans fil 100 balles", (None, None, [], {}, 100, {"domain": "casque_audio", "sub": "ecouteurs", "props": {"cordless": True}})),
    ("console de salon 1 To max 550 €", (None, None, [], {"storage_gb": 1000}, 550, {"domain": "console", "sub": "salon"})),
    ("écran 27 pouces 144 Hz sous 300 €", (None, None, [], {"screen_in": 27, "refresh_hz": 144}, 300, {"domain": "ecran_pc"})),
    ("montre connectée GPS moins de 250 €", (None, None, [], {}, 250, {"domain": "montre_connectee", "props": {"gps": True}})),
    ("barre de son dolby atmos jusqu'à 500 €", (None, None, [], {}, 500, {"domain": "enceinte", "sub": "barre_de_son",
                                                                         "props": {"dolby_atmos": True}})),
    ("tablette 11 pouces 128 Go sous 400 €", (None, None, [], {"screen_in": 11, "storage_gb": 128}, 400, {"domain": "tablette"})),
    ("machine à café sous 300 €", SUIVI),
]


def run():
    ok, rows = 0, []
    for text, want in PHRASES:
        try:
            m = interpret(text, BRANDS)
            got = (m["category"], m["brand"], sorted(m["features"]), m["attrs"], m["max_price"],
                   {k: m[k] for k in ("domain", "sub", "props") if m.get(k)})
            shown = label(m)
        except BadRequest as e:
            shown = str(e)
            got = ("refus", want[1]) if want[0] == "refus" and want[1] in shown else ("refus", shown)
        expected = want if want[0] == "refus" else (want[0], want[1], sorted(want[2]), want[3], want[4], want[5] if len(want) > 5 else {})
        good = got == expected
        ok += good
        rows.append((good, text, shown, None if good else (got, expected)))
    return ok, rows


def main():
    ok, rows = run()
    for good, text, shown, diff in rows:
        print(f"{'ok ' if good else 'NON'} {text:52} → {shown}")
        if diff:
            print(f"      lu {diff[0]}\n      attendu {diff[1]}")
    print(f"compris : {ok}/{len(rows)}")


if __name__ == "__main__":
    main()
