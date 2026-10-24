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
# phrase → (catégorie, marque, fonctions, attributs, prix max)
PHRASES = [
    ("aspirateur balai sous 300 €", ("aspirateur", None, ["balai"], {}, 300)),
    ("Je veux un aspirateur balai sans fil à moins de 300 euros", ("aspirateur", None, ["balai", "sans_fil"], {}, 300)),
    ("un aspirateur pas plus de 200 €", ("aspirateur", None, [], {}, 200)),
    ("robot aspirateur laveur jusqu'à 500 €", ("robot_aspirateur", None, ["laveur"], {}, 500)),
    ("lave-linge 9 kg moins de 500€", ("lave_linge", None, [], {"capacity_kg": 9}, 500)),
    ("lave linge 8kg max 450", ("lave_linge", None, [], {"capacity_kg": 8}, 450)),
    ("sèche-linge 8 kg sous 600 €", ("seche_linge", None, [], {"capacity_kg": 8}, 600)),
    ("lave-vaisselle 60 cm classe C sous 600 €", ("lave_vaisselle", None, [], {"width_cm": 60, "energy_class": "C"}, 600)),
    ("lave vaisselle 13 couverts < 500 €", ("lave_vaisselle", None, [], {"place_settings": 13}, 500)),
    ("frigo américain jusqu'à 1 200 €", ("refrigerateur", None, ["americain"], {}, 1200)),
    ("congélateur moins de 300 €", ("congelateur", None, [], {}, 300)),
    ("plaque induction 4 foyers sous 350 €", ("plaque_cuisson", None, ["induction"], {"zones": 4}, 350)),
    ("four encastrable budget 400 €", ("four", None, ["encastrable"], {}, 400)),
    ("hotte en dessous de 250 €", ("hotte", None, [], {}, 250)),
    ("matelas 160x200 sous 600 €", ("matelas", None, [], {"bed_size": "160x200"}, 600)),
    ("matelas 140 x 190 à 400 euros max", ("matelas", None, [], {"bed_size": "140x190"}, 400)),
    ("un lit 160x200 jusqu'à 700€", ("lit", None, [], {"bed_size": "160x200"}, 700)),
    ("canapé d'angle sous 900 €", ("canape", None, ["angle"], {}, 900)),
    ("canapé convertible 3 places moins de 800 €", ("canape", None, ["convertible"], {"seats": 3}, 800)),
    ("table 6 places sous 400 €", ("table", None, [], {"seats": 6}, 400)),
    ("armoire sous 500 euros", ("armoire", None, [], {}, 500)),
    ("Zephyr sous 400 €", (None, "Zephyr", [], {}, 400)),
    ("matelas Dormea 160x200", ("matelas", "Dormea", [], {"bed_size": "160x200"}, None)),
    ("smartphone sous 300 €", SUIVI),
    ("un truc sympa pour le salon", RECONNU),
    # tournures du quotidien
    ("aspi sans fil 250 balles", ("aspirateur", None, ["sans_fil"], {}, 250)),
    ("je cherche un frigo pas cher", ("refrigerateur", None, [], {}, None)),
    ("machine à laver 9kg 450€", ("lave_linge", None, [], {"capacity_kg": 9}, 450)),
    ("lave-linge 1400 tours 9 kg moins de 600", ("lave_linge", None, [], {"capacity_kg": 9}, 600)),
    ("matelas 160 sur 200 sous 500 €", ("matelas", None, [], {"bed_size": "160x200"}, 500)),
    ("lit 2 places sous 400", ("lit", None, [], {}, 400)),                  # un lit n'a pas de places assises
    ("canapé 3 places en dessous de 1 500 €", ("canape", None, [], {"seats": 3}, 1500)),
    ("meuble télé sous 200 €", ("meuble_tv", None, [], {}, 200)),
    ("aspirateur Dyson V15 sous 500 €", ("aspirateur", None, [], {}, 500)),  # marque inconnue : pas inventée
    ("réfrigérateur sous 0 €", ("refrigerateur", None, [], {}, None)),      # prix impossible : demandé ensuite
    ("TV 55 pouces sous 500", SUIVI),
    ("micro-ondes sous 150 €", SUIVI),
]


def run():
    ok, rows = 0, []
    for text, want in PHRASES:
        try:
            m = interpret(text, BRANDS)
            got = (m["category"], m["brand"], sorted(m["features"]), m["attrs"], m["max_price"])
            shown = label(m)
        except BadRequest as e:
            shown = str(e)
            got = ("refus", want[1]) if want[0] == "refus" and want[1] in shown else ("refus", shown)
        expected = want if want[0] == "refus" else (want[0], want[1], sorted(want[2]), want[3], want[4])
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
