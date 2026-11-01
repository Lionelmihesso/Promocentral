# L'ontologie de Promo Central — chaque rayon, et l'électronique

Ce que la plateforme sait d'un produit vient de ce que les enseignes déclarent de leurs offres : un titre, une marque,
un prix, un EAN et leur propre catégorie (« TV - Vidéo > Téléviseurs > TV QLED »), dans leur **flux produits** (v63,
`deals/ingest/feeds.py` : la démo en est nourrie) ou dans les données structurées de leurs fiches, le dernier recours. L'ontologie est construite là-dessus, et sur rien d'autre : rien n'est rédigé, rien
n'est déduit d'une fiche technique que les enseignes ne donnent pas. La v58 l'avait essayée sur les aspirateurs ; la v59 la donne à **chaque rayon suivi** (31
rayons, 30 domaines, 4 familles) et ouvre la famille **Électronique** (9 rayons : téléviseurs, smartphones, ordinateurs
portables, tablettes, casques et écouteurs, enceintes, montres connectées, consoles de jeux, écrans PC).

## Trois niveaux, pas plus

| Niveau | Ce qu'il dit | Exemples |
|---|---|---|
| Catégorie | le rayon ; un domaine en réunit parfois deux (les aspirateurs : aspirateur et robot) | Téléviseurs ; Lave-linge |
| Sous-catégorie | le type, et la règle qui y range une offre — dans l'ordre, le plus précis d'abord ; ce qu'un type est par définition | OLED, Mini LED, QLED, LED ; Hublot, Top |
| Attributs | un ou deux : oui ou non, avec les mots qui le disent ; ou une mesure, lue par l'extracteur | 4K, taille d'écran ; capacité, classe énergie |

Les rayons, leurs types et leurs attributs :

| Famille | Rayon | Types | Attributs |
|---|---|---|---|
| Électroménager | Lave-linge | Hublot, Top | capacité, classe énergie |
| Électroménager | Lave-linge séchants | — | capacité, classe énergie |
| Électroménager | Sèche-linge | Pompe à chaleur, Condensation, Évacuation | capacité, classe énergie |
| Électroménager | Lave-vaisselle | Encastrable, Compact, Pose libre | couverts, largeur |
| Électroménager | Réfrigérateurs | Américain, Multi-portes, Combiné, 2 portes, 1 porte | volume, No Frost |
| Électroménager | Congélateurs | Armoire, Coffre, Table top | volume, No Frost |
| Électroménager | Fours | Encastrable, Posable | Pyrolyse, volume |
| Électroménager | Plaques de cuisson | Mixte, Induction, Vitrocéramique, Gaz | foyers, largeur |
| Électroménager | Hottes | Îlot, Plan de travail, Plafond, Tiroir, Casquette, Murale | largeur |
| Électroménager | Cuisinières | Mixte, Induction, Vitrocéramique, Gaz | largeur, Pyrolyse |
| Électroménager | Aspirateurs | Robot, Laveur, À main, Balai, Traîneau | Sans fil, Sans sac |
| Électronique | Téléviseurs | OLED, Mini LED, QLED, LED | taille d'écran, 4K |
| Électronique | Smartphones | Pliable, Téléphone simple | stockage, 5G |
| Électronique | Ordinateurs portables | Gamer, 2 en 1, Chromebook, Ultraportable | taille d'écran, mémoire vive |
| Électronique | Tablettes | Enfant | taille d'écran, stockage |
| Électronique | Casques et écouteurs | Écouteurs, Casque | Réduction de bruit, Sans fil |
| Électronique | Enceintes | Barre de son, Connectée, Portable | Étanche, Dolby Atmos |
| Électronique | Montres connectées | Bracelet, Sport | GPS, 4G / eSIM |
| Électronique | Consoles de jeux | Portable, De salon | Édition numérique, stockage |
| Électronique | Écrans PC | Gaming, Incurvé | taille d'écran, fréquence |
| Ameublement | Canapés | D'angle, Modulable, Droit | places, Convertible |
| Ameublement | Fauteuils | Relax, Club, À bascule, De bureau | Électrique |
| Ameublement | Lits | Coffre, Mezzanine, Superposé, Gigogne, Enfant | taille |
| Ameublement | Armoires | Dressing, Penderie | largeur, Portes coulissantes |
| Ameublement | Tables | Ronde, Carrée, Rectangulaire, Ovale | places, Extensible |
| Ameublement | Buffets | Haut, Bas | largeur |
| Ameublement | Meubles TV | Suspendu, Bas | largeur |
| Ameublement | Commodes | Chiffonnier, Semainier, À langer | tiroirs, largeur |
| Literie | Matelas | Hybride, Ressorts, Mémoire de forme, Latex, Mousse | taille |
| Literie | Sommiers | Électrique, Coffre, Tapissier, À lattes | taille |

Les fichiers : `deals/ontology/electromenager.json`, `electronique.json`, `ameublement.json`, `literie.json` (schéma 3,
version 3.0.0, un type ou un attribut par ligne), relus au chargement par `deals/ontology/__init__.py` (`check`) : un
schéma inconnu, une version mal écrite, un rayon qui n'est pas de la famille du fichier ou décrit deux fois, un type
hors du domaine, un attribut inconnu, une mesure que l'extracteur ne sait pas lire, une expression illisible ou un mot
réclamé deux fois dans un rayon l'empêchent de servir, avec où est la faute.

```json
{"domain": "televiseur", "label": "Téléviseurs", "one": "Téléviseur", "categories": ["televiseur"],
 "words": ["televiseur", "tv", "tele", "television", "smart tv", "…"],
 "subcategories": [
  {"key": "oled", "label": "OLED", "plural": "Téléviseurs OLED", "one": "Téléviseur OLED", "words": ["oled", "…"],
   "match": {"category": ["televiseur"], "any": [{"text": "\\boled\\b"}]}}, "…"],
 "attributes": [
  {"key": "screen_in", "label": "Taille d'écran", "kind": "measure"},
  {"key": "uhd", "label": "Définition", "kind": "bool", "yes": "4K", "no": "HD ou Full HD", "words": {"4k": true, "full hd": false, "…": true},
   "text": [{"re": "\\b[48]k\\b|\\buhd\\b|ultra hd|2160p", "value": true}, {"re": "full hd|hd ready|\\bhd\\b|1080p|720p", "value": false}]}]}
```

Un attribut oui/non dit aussi comment une alternative s'y compare (`compare`) : « oui » est un plus (par défaut : 4K,
5G, sans fil, No Frost — il le faut aussi), une forme (`same` : sans sac ou avec sac, portes coulissantes ou battantes —
la même), « oui » est un moins (`less` : une console en édition numérique, sans lecteur — seulement à la place d'une
autre qui l'est).

## Lu dans l'offre, rien de deviné

- **Où** : le titre de l'offre, puis chaque niveau de la catégorie déclarée, sans accents ni majuscules, les tirets lus
  comme des espaces. Un niveau qui nomme plusieurs choses (« Commodes et chiffonniers », « Casques et écouteurs »,
  « Aspirateurs avec ou sans sac ») ne dit pas lequel est l'offre : il n'est pas lu pour le type ni pour les attributs.
- **Le rayon** : la catégorie déclarée d'abord, puis le titre (`extract/categories.py`). Un titre qui commence par un
  accessoire (« Coque pour… », « Embouts… », « Manette… », « Support TV… », pluriels compris) n'a pas de rayon ; un
  produit reconditionné ou d'occasion non plus ; des produits qui ressemblent à ceux d'un rayon sont reconnus pour ne pas
  y entrer (babyphone, tensiomètre, casque de moto, montre analogique, console d'entrée sous « Meubles »). En dessous
  de 50 € (20 € pour un casque, une enceinte, une montre), une fiche lue sur un site n'entre pas au catalogue.
- **Le type** : le premier, du plus précis au plus général, dont la règle convient. Rien ne le dit : le produit reste
  dans son rayon, sans type.
- **Un attribut oui/non** : le premier dit l'emporte (le titre avant la catégorie). L'offre ne le dit pas : inconnu,
  jamais supposé. Ce qu'un type est par définition (un robot aspirateur est sans fil) ne remplace jamais ce que l'offre dit.
- **Une mesure** : lue dans le titre, seulement là où elle a un sens (`ONLY`) — la taille d'écran d'un téléviseur, d'un
  ordinateur, d'une tablette, d'un écran (en pouces, `55"`, ou en centimètres pour un téléviseur : « 139 cm » → 55) ;
  pas celle d'un smartphone, rarement dite. Le stockage n'est pas la mémoire vive (« 8 Go RAM 256 Go » : 256) ; un
  ordinateur dont le titre dit « 8Go - 256Go SSD » a 8 Go de mémoire (une seule autre capacité à côté d'un stockage
  nommé). Une classe énergie est dite par « classe A » ou par un « A++ » seul ; un « A » seul ne dit rien.
- **Gardé et relu** : la catégorie déclarée est gardée avec le produit (`_cat`) et relue à chaque publication sous
  l'ontologie en vigueur ; l'offre du jour l'emporte, ce qu'elle ne dit plus reste connu, sauf ce qui n'a plus de sens
  pour le rayon (une « largeur » de 139 cm lue avant la v59 sur un téléviseur est écartée).

## Ce que l'app en fait

- **Recherche** : « TV OLED 55 pouces » → « Téléviseurs OLED », « 55 pouces » ; « télé 139 cm » → 55 pouces ;
  « smartphone 5G 256 Go » → « Smartphones », « 5G », « 256 Go et plus » ; « console digitale » → « Édition
  numérique » ; « micro-ondes » : pas encore suivi, on le dit. Chaque nom que l'app montre (un type, un oui, un non) se
  relit dans une recherche : une puce gardée en mots redonne la même recherche (`tests/test_ontology.py`).
- **Affiner** : le rayon (celui que la phrase a dit est coché), le type, les caractéristiques (oui ou non), les mesures
  qui existent (taille d'écran, stockage, mémoire, fréquence, tiroirs…), chacune avec ce qu'elle donnerait.
- **Accueil** : la pièce **High-tech** ouvre les inspirations ; les exemples de la Recherche disent « TV OLED 55
  pouces », « smartphone 5G ». Chaque rayon d'électronique a son illustration originale (`web/src/art.jsx`).
- **Moins cher, comparable** (la fiche) : le même type, ni plus ni moins — un produit dont l'offre ne dit pas le type
  n'est comparé qu'à d'autres qui ne le disent pas (un canapé convertible n'est pas remplacé par un canapé d'angle) ;
  les attributs selon `compare` ; la même taille d'écran à 5 % près (un 55 pouces par un 55 pouces) ; au moins autant
  de stockage, de mémoire, de fréquence ; une console de la même marque (ses jeux sont les siens).
- **Recherches sauvegardées** : celles des versions d'avant (« canapé d'angle convertible », « frigo américain ») sont
  relues comme la même phrase aujourd'hui (le type, l'attribut) ; une alerte « tous les comparables » garde le type et
  les attributs du produit.

## Mesures

**Offres comme dans les flux** (`python -m bench.ontologie`, même banc sur le code v58 avec `--code`) : 146 produits à
vérité connue et 41 pièges (accessoires, reconditionnés, autres rayons), titres et catégories écrits comme ceux des
enseignes françaises, lus comme la collecte (`market.match_product`). Ce jeu a servi à écrire les règles : c'est un jeu
de non-régression.

| | v58 | v59 |
|---|---|---|
| offres rangées dans leur rayon suivi | 98 / 146 (électronique : 0 / 47) | **146 / 146** |
| type dit par l'offre, lu juste | 15 / 79 | **113 / 113** |
| attributs dits, lus justes | 104 / 134 (1 faux) | **207 / 207** |
| types ou attributs devinés | 1 | **0** |
| pièges tenus hors du catalogue | 40 / 41 | **41 / 41** |

**Offres inédites** (`--inedites`) : 52 produits et 12 pièges, écrits d'un trait une fois les règles finies, mesurés
une première fois sans rien retoucher.

| | v58 | v59, première lecture | v59, après corrections |
|---|---|---|---|
| rangées | 24 / 52 | 49 / 52 | **52 / 52** |
| types lus justes | 6 / 21 | 38 / 38 | **40 / 40** |
| attributs lus justes | 25 / 33 (1 faux) | 68 / 72 | **75 / 76** |
| faux ou devinés | 1 | 0 | **0** |
| pièges | 12 / 12 | 12 / 12 | **12 / 12** |

Ce que la première lecture a montré, et qui est corrigé : « montre de sport GPS » pas reconnue ; « Console … » rangée
seulement sous « Jeux vidéo > Consoles » ; « Table ronde extensible » ; la mémoire d'un ordinateur dite sans le mot RAM
(« 8Go - 256Go SSD », deux fois) ; un « A++ » seul. Reste non lu, par choix : un « A » seul en fin de titre.

**Alternatives** (`python -m bench.alternatives`, grille indépendante du code, lue dans le seul titre, étendue en v59 au
type, aux formes et à l'électronique) : sur la démo de la v58 (84 produits), 22 suggestions sur 110 que la grille v59
juge incompatibles (un matelas latex remplacé par un matelas à ressorts, un canapé convertible par un canapé d'angle) ;
sur la démo v59 (127 produits, électronique comprise), 0 sur 132, et une alternative moins chère montrée pour les 47
fiches qui en ont une ; sur 3 000 produits, 0 incompatible, 100 % montrées.

**Recherche et missions** : 50 phrases sur 50 comprises (`bench.missions`, dont 13 d'électronique) ; 43 recherches dont
la démo a la réponse : la première carte juste, pertinence et rappel 100 % (`bench.search`).

**Tenue en charge** (3 000 produits, `bench.scale`) : publication 2,7 s → 3,1 s (chaque produit n'est plus comparé
qu'aux produits de son rayon et de son type, et ce qu'il a est lu une fois) ; lectures de l'app inchangées.

**Mutations** : chaque règle ajoutée ou changée, altérée une à une (54 en tout, code et données), fait échouer un test.

## Ajouter un rayon, réviser une famille

1. Le rayon est d'abord reconnu et suivi (`extract/categories.py` : ses mots, sa famille ; `labels.py` : son nom).
2. Dans le fichier de sa famille, un domaine : ses types et leur règle (le plus précis d'abord), un ou deux attributs que
   les flux disent vraiment (le relevé `sample` d'une enseigne le montre), leurs mots, et pour chaque nom montré par l'app
   le mot qui le relit.
3. `python -m unittest tests.test_ontology` : les fichiers sont relus, chaque nom se relit ; ajouter les offres réelles
   qui les mettent en défaut à `bench/ontologie.py`, puis `python -m bench.ontologie` : rien de faux, rien de deviné.
4. Changer la version du fichier (`3.0.0` → `3.1.0`) ; la publication suivante relit les produits gardés.

## Limites

- Des règles écrites à la main, en français, et deux jeux d'offres écrits par le même auteur : ils disent ce que les
  règles savent lire, pas ce que donneront de vrais flux. La lecture sur un échantillon réel de chaque enseigne reste à
  faire (`deals.py sample`), avant la mise en production.
- Un mot absent n'est pas lu (« cordless ») ; une coque vendue « iPhone 15 coque silicone » (le produit d'abord) n'est
  écartée que par le seuil de prix.
- Le type « non dit » est fréquent dans de vrais flux : un produit dont le type n'est pas dit n'a d'alternatives que
  parmi ceux dont le type n'est pas dit non plus (précision d'abord, au prix de moins d'alternatives).
- Deux consoles de marques différentes ne se remplacent pas ; deux smartphones, si (système d'exploitation non lu).
