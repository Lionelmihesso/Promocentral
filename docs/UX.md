# L'interface de DEALS — un flux vivant de remises (v47)

## Principe

**Pinterest × Bloomberg.** Pinterest pour donner envie : des visuels, une mosaïque, l'inspiration par pièce. Bloomberg
pour la vie et la décision : un bandeau où défilent les remises du jour avec l'heure de mise à jour, et dans chaque fiche
la courbe du prix sur 90 jours avec un verdict (« Au plus bas depuis 90 jours », ou « 148 € au-dessus du plus bas »).

Les visuels sont des **illustrations originales** par catégorie (`web/src/art.jsx`), déclinées par produit (couleurs
tirées du produit, proportions de l'objet : une armoire est haute, un canapé est large, d'où la mosaïque). Aucune image
extérieure, aucune requête vers un tiers, aucun droit de tiers. Les photos des enseignes sont lues par l'extraction mais
pas montrées : c'est une décision à prendre (droits, vie privée, coût), voir plus bas.

La qualité reste implicite : seulement des remises réelles, aucune mention « vérifiée ». Les durées (depuis quand,
jusqu'à quand) restent dans la fiche. Deux entrées : **les belles remises du moment** (l'accueil) et **le produit qu'on
regarde** (la recherche couvre tout le catalogue suivi) ; la fiche répond alors à « existe-t-il moins cher, et aussi
bien ? » (« Moins cher, comparable », règles : `deals/alternatives.py`) et à « est-ce le bon moment ? » (la courbe).

Gardé des versions précédentes : le produit comme entrée (l'enseigne n'est qu'un attribut), un deal identique pour tous,
le suivi des marques, la connexion demandée au moment de l'action, contrastes et zones à toucher aux normes. Retiré de
la v46 : la liste à pictogrammes et le regroupement par marque × catégorie (les cartes portent un visuel et un nom
court, qui suffisent à départager), le signet (remplacé par le cœur).

## Ce que montre chaque écran

| Écran | Contenu |
|---|---|
| Accueil | bandeau défilant (« MAJ 14 déc. 11:00 », marque, catégorie, remise, prix ; immobile si l'appareil demande moins d'animations), « De bonnes affaires, pour vos envies. », « 13 remises en ce moment », recherche, univers (Pour vous, Électroménager, Ameublement, Literie), **inspirations du moment** par pièce (Chambre, Salon, Cuisine, Buanderie, Entretien : « Jusqu'à −20 % » et les catégories), **nos sélections** en mosaïque |
| Carte | visuel, remise sur le visuel, cœur, marque, nom (une ligne), prix en orange et prix barré ; « Baisse de 64 € » sur un favori ; « 481 € de moins » sur une alternative |
| Pièce | ses remises en mosaïque |
| Fiche | grand visuel, partager (lien vers la fiche), cœur ; marque · catégorie, nom ; remise, prix, prix barré ; « En remise depuis 3 jours, jusqu'au ven. 19 déc. » ; « Voir l'offre chez … » ; **prix sur 90 jours** (courbe en marches, un prix par jour, verdict, aujourd'hui · plus bas · habituel) ; **à propos** (caractéristiques avec pictogramme) ; **moins cher, comparable** ; autres enseignes ; à défaut, produits similaires |
| Explorer | toutes les remises en mosaïque, catégories, tri (meilleures remises, prix croissant, décroissant), marques ; recherche dans tout le catalogue |
| Favoris | produits gardés en mosaïque ; la cloche de l'en-tête compte les baisses de prix |
| Profil | connexion, marques suivies, déconnexion |

## À décider : les photos des produits

L'extraction lit déjà l'adresse de la photo de chaque produit (`products.image`, JSON-LD ou `og:image`). La montrer
demande un choix : la charger depuis le site de l'enseigne (requêtes vers un tiers à chaque ouverture, adresse IP des
visiteurs transmise, images parfois bloquées), la copier sur notre serveur (stockage et bande passante, et une
reproduction de photos dont les droits appartiennent aux marques ou aux enseignes), ou passer par des flux produits
fournis sous licence (programmes d'affiliation : contraire au principe « sans affiliation »). Tant que ce n'est pas
tranché, les illustrations tiennent la place ; elles restent de toute façon le repli d'un produit sans photo.

## Historique

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

## Mesures v45 → v46 : « trop de texte, on ne voit pas ce qui se passe »

Mêmes données (démo du 14 décembre), téléphone 390 × 844.

| | v45 | v46 |
|---|---|---|
| Mots sur le premier écran de l'accueil | 78 | **60** |
| Caractères par ligne de produit (accueil) | 62 | **26** |
| Lignes avec un pictogramme de catégorie | 0 sur 4 | **5 sur 5** |
| Caractéristiques (taille, capacité…) sur l'accueil | oui (« 160x200 », « 331 L »…) | **aucune** |
| Lignes pour 13 remises | 13 (deux « Nordvik, lit » à la suite) | **11**, une par marque × catégorie |
| Produits ou groupes entièrement visibles sans défiler | 4 | 5 |
| Recherche « aspirateur » : mots sur le premier écran · caractères par ligne | 78 · 52 | **51 · 25** |
| Fiche avec alternatives : mots sur le premier écran · caractères par alternative | 70 · 67 | **53 · 26** |
| Fiche d'un deal : mots sur le premier écran | 49 | 53 (la description y est maintenant) |
| Textes sous le contraste minimal · zones à toucher sous 44 px (tous les écrans) | 0 · 0 | 0 · 0 |
| Poids de la page | 267 Ko | 271 Ko |

Sur le catalogue synthétique de 3 000 produits, les 759 remises du jour tiennent en 538 lignes (177 groupes de plusieurs
produits). Le parcours navigateur v46 (19 étapes, deux passages) vérifie en plus : aucun titre ni caractéristique sur
l'accueil, un pictogramme par ligne, une ligne par marque × catégorie, un groupe qui s'ouvre sur ses produits
départagés, la description de la fiche, « Retour » qui ramène au groupe puis à l'accueil ; les mêmes contrôles échouent
sur la v45. Planche : `docs/ux/6-v46.png`.

## Mesures v46 → v47 : Pinterest × Bloomberg

Mêmes données (démo du 14 décembre), téléphone 390 × 844.

| | v46 | v47 |
|---|---|---|
| Part du premier écran de l'accueil occupée par des visuels | 5 % | **32 %** |
| Part de toute la page d'accueil occupée par des visuels | 5 % | **52 %** |
| Part du premier écran de la fiche occupée par des visuels | 1 % | **49 %** |
| Fraîcheur visible sur l'accueil | rien | bandeau défilant, heure de mise à jour |
| Prix sur 90 jours dans la fiche | non | courbe, plus bas, habituel, verdict |
| Mots sur le premier écran : accueil · fiche | 55 · 56 | 76 · 42 |
| Entrées entièrement visibles sans défiler (accueil) | 5 lignes | 2 pièces, la mosaïque commence dessous |
| Textes sous le contraste minimal · zones à toucher sous 44 px (7 écrans) | 0 · 0 | 0 · 0 ; texte blanc des pièces mesuré au pixel : 5,5:1 au pire |
| Requêtes vers un tiers à l'ouverture | 0 | 0 |
| Poids de la page | 271 Ko | 354 Ko (deux polices de plus, les illustrations) |

L'accueil porte plus de mots qu'en v46 : ceux du titre, du bandeau et des pièces de la maquette. La mosaïque porte, par
carte, la marque, un nom sur une ligne et le prix. Parcours vérifié dans un vrai navigateur (Chromium), 21 étapes, deux
passages : bandeau et compteur justes, une carte par remise (visuel, remise, prix, prix barré), un univers et une pièce
qui filtrent, recherche dans tout le catalogue, courbe et verdict, alternatives et leur économie, lien partagé qui
rouvre la fiche, durées et clic tracé, connexion, favori, tri d'Explorer, marque suivie dans Profil, mosaïque de 4
colonnes et plus sur ordinateur, bandeau immobile quand l'appareil demande moins d'animations. Planche :
`docs/ux/7-v47.png`.
