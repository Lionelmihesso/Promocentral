# L'interface de DEALS — minimaliste, sans friction (v45)

## Principe

Une liste se lit en un regard : **marque, produit, prix, remise**. Rien d'autre sur l'accueil ni dans les listes.
La qualité est implicite : l'app ne montre que de vraies remises, elle n'a pas à l'écrire (aucune mention « vérifiée »,
aucun compteur de fausses promos). Les durées (depuis quand la remise court, jusqu'à quand l'enseigne la déclare) ne
sont que dans la fiche, en une ligne, à côté du bouton « Voir l'offre ».

Deux entrées, une seule app : **les belles remises du moment** (l'accueil), et **le produit qu'on regarde** (la
recherche couvre tout le catalogue suivi, pas seulement les remises). La fiche répond alors à la question qu'on se pose
devant un produit cher : existe-t-il moins cher, et aussi bien ? « Moins cher, comparable » : jusqu'à trois produits
qui le remplacent vraiment (même usage, pas moins bien), au moins 10 % moins chers, avec l'économie en euros. Une
suggestion est une promesse : un appareil d'une autre largeur, une literie d'une autre taille, un aspirateur à fil à la
place d'un sans fil n'y apparaissent jamais (règles : `deals/alternatives.py`). Sans produit comparable, la fiche ne
propose rien plutôt qu'un produit qui ne convient pas.

Gardé des maquettes v27 à v44 : le produit comme entrée (l'enseigne n'est qu'un attribut), un deal identique pour tous,
pas d'image en V1, le signet sur chaque ligne, le suivi des marques, la connexion demandée au moment de l'action,
l'identité visuelle (noir, blanc, orange, Manrope).

## Ce que montre chaque écran

| Écran | Contenu |
|---|---|
| Aujourd'hui | « 13 remises aujourd'hui », recherche, catégories (un geste pour filtrer), le plus intéressant, les autres |
| Recherche | tout le catalogue suivi, les remises d'abord ; un produit sans remise montre son prix seul |
| Ligne de liste | marque, produit, prix, remise, signet |
| Fiche | marque · catégorie, produit, remise, prix et prix barré, « En remise depuis 3 jours, jusqu'au ven. 19 déc. », « Voir l'offre chez … » ; **moins cher, comparable** (« 481 € de moins ») ; autres enseignes ; à défaut d'alternative moins chère, produits similaires (comparables, au prix le plus proche) |
| Explorer | recherche ; catégories par famille (pictogramme et nom) ; marques |
| Favoris | produits gardés (« Baisse de 64 € » seulement quand le prix a baissé, pastille sur l'onglet), marques suivies |

Retiré de la v43, à la demande (trop d'informations, lecture alourdie) : « Toutes vérifiées », « fausses promos
écartées », « Depuis hier » (nouvelles, finissent bientôt), le signal de chaque ligne (finit bientôt, nouveau, plus bas
depuis n jours, vérifiée), l'enseigne et le prix barré dans les listes, la date de relevé dans l'en-tête, le bloc
« Pourquoi c'est un vrai deal » de la fiche, les compteurs des catégories et des marques. Les données qui ne servaient
qu'à ces éléments ne sont plus calculées ni stockées (preuve, plus bas prix relevé, filtres « depuis hier »).

## Mesures v41 → v44 (mêmes données de démo, téléphone 390 × 844)

| | v41 | v43 | v44 |
|---|---|---|---|
| Mots sur le premier écran de l'accueil | 59 | 128 | 82 |
| Éléments par ligne de liste | 4 | 7 | **4** |
| Produits entièrement visibles sans défiler | 3 | 3 | **4** |
| Mots sur le premier écran de la fiche | 49 | 90 | 56 (dont la ligne des durées) |
| Remises d'une catégorie | 2 gestes | 1 geste | 1 geste |
| Aller chez l'enseigne depuis l'accueil | 2 gestes | 2 gestes | 2 gestes |
| Textes sous le contraste minimal WCAG AA (accueil · fiche) | 5 · 3 | 0 · 0 | 0 · 0 |
| Zones à toucher sous 44 px (accueil · fiche) | 5 · 6 | 0 · 0 | 0 · 0 |
| Requêtes vers un tiers à l'ouverture | 1 (Google Fonts) | 0 | 0 |
| Poids de la page | 218 Ko + police | 281 Ko | 267 Ko, police comprise |

Les mots en plus de la v41 sur l'accueil sont ceux des catégories et du quatrième produit visible ; une ligne porte
exactement autant d'informations qu'en v41.

## Mesures v44 → v45 : « je regarde ce produit, existe-t-il moins cher ? »

Mêmes données (démo du 14 décembre, 59 produits) et catalogue synthétique de 3 000 produits (`bench.scale`). Les
suggestions de la fiche sont jugées par une grille indépendante du code, écrite avant le moteur (`bench/alternatives.py`) ;
v44 = l'ancien calcul « Produits similaires » (caractéristiques proches, à défaut prix le plus proche).

| | v44 | v45 |
|---|---|---|
| Trouver un produit qui n'est pas en remise (recherche « v15 ») | 0 résultat | 1 résultat |
| Du produit regardé à une alternative moins chère | impossible | 2 gestes après la saisie (le résultat, l'alternative) |
| Suggestions incompatibles (démo · 3 000 produits) | 55 % · 1 % | **0 % · 0 %** |
| Fiches qui ont une alternative moins chère et la montrent (démo · 3 000) | 90 % · 63 % | **95 % · 100 %** |
| Économie moyenne montrée, pour une économie possible de 259 € (démo) · 398 € (3 000) | 223 € · 204 € | **243 € · 398 €** |
| Fiches sans suggestion (démo · 3 000) | 5 · 0 | 27 · 0 |
| Mots sur le premier écran : accueil · fiche d'un deal · fiche avec alternatives | 78 · 49 · — | 78 · 49 · 70 |
| Textes sous le contraste minimal · zones à toucher sous 44 px | 0 · 0 | 0 · 0 |
| Poids de la page | 267 Ko | 267 Ko |

Exemples de suggestions v44 écartées par la grille : un lave-vaisselle de 45 cm pour un 60 cm, un lave-linge de 8 kg
pour un 10 kg, un réfrigérateur américain de 91 cm pour un combiné de 60 cm, un matelas 140x190 pour un 160x200, un
canapé droit pour un canapé d'angle, un aspirateur balai pour un traîneau. La fiche manquée en v45 (démo) :
un four vapeur dont l'alternative est un four encastrable, écarté parce que la forme (encastrable) doit être la même.
Les 27 fiches sans suggestion de la démo n'ont aucun produit comparable dans un catalogue de 59 produits ; sur 3 000
produits, aucune fiche n'est vide.

Parcours vérifié dans un vrai navigateur (Chromium), 17 étapes, deux passages, dont : aucune durée ni mention de
vérification sur l'accueil, 4 éléments par ligne ; un produit sans remise trouvé par la recherche, sans badge ; sa fiche
montre « Moins cher, comparable » sur le premier écran, chaque ligne au moins 10 % moins chère et son économie égale à
la différence de prix ; une alternative s'ouvre, et son clic sortant est compté comme venu de « Moins cher,
comparable » (`deals.py metrics`, par source). Captures : `docs/ux/` (`5-alternatives.png` : v44 et v45 côte à côte).
