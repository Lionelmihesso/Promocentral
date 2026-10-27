# L'ontologie de DEALS — ce qu'est un produit, d'après ce que donnent les flux (v58, aspirateurs pilotes)

Ce que la plateforme sait d'un produit vient de ce que les enseignes donnent de leurs offres, par leurs **flux affiliés
et leurs API** : un titre, une marque, un prix, un EAN et leur propre catégorie (« Électroménager > Aspirateur >
Aspirateur balai »). La v58 construit l'ontologie là-dessus, et sur rien d'autre : rien n'est rédigé, rien n'est déduit
d'une fiche technique que les flux ne donnent pas. La v57 lisait 23 caractéristiques, 15 critères et 17 besoins (poils
d'animaux, décibels, poids…) : trop pour aider à décider, et une partie n'existe pas dans un flux. Elle est retirée.

## Trois niveaux, pas plus

| Niveau | Ce qu'il dit | Aspirateurs |
|---|---|---|
| Catégorie | le domaine et ses rayons | Aspirateurs : `aspirateur`, `robot_aspirateur` |
| Sous-catégorie | le type, et la règle qui y range une offre — dans l'ordre, le plus précis d'abord (un « balai laveur » est un laveur) ; ce qu'un type est par définition | robot, laveur, à main, balai, traîneau ; un robot est sans fil et sans sac, un balai ou un laveur sans sac |
| Attributs | deux, oui ou non, et les mots qui les disent | sans fil (« sans fil », « filaire », « avec fil », « sur secteur ») ; sans sac (« sans sac », « avec sac », « à sac ») |

Le fichier : `deals/ontology/aspirateurs.json` (schéma 2, version 2.0.0), relu au chargement par
`deals/ontology/__init__.py` (`check`) : un schéma inconnu, une version mal écrite, un type hors du domaine, un attribut
inconnu, une expression illisible ou un mot réclamé deux fois l'empêchent de servir, avec où est la faute.

```json
{"schema": 2, "domain": "aspirateurs", "version": "2.0.0", "categories": ["aspirateur", "robot_aspirateur"],
 "subcategories": [
   {"key": "robot", "match": {"category": ["robot_aspirateur"]}, "implies": {"cordless": true, "bagless": true}},
   {"key": "balai", "match": {"category": ["aspirateur"], "any": [{"text": "\\bbalais?\\b"}]},
    "implies": {"bagless": true}, "attributes": ["cordless"]}, "…"],
 "attributes": [
   {"key": "cordless", "yes": "Sans fil", "no": "Avec fil", "words": {"sans fil": true, "filaire": false, "avec fil": false},
    "text": [{"re": "\\bsans fil\\b", "value": true}, {"re": "\\bfilaire\\b|\\bavec fil\\b|\\bsur secteur\\b", "value": false}]}, "…"]}
```

## Lu dans l'offre, rien de deviné

- **Où** : le titre de l'offre, puis chaque niveau de la catégorie déclarée (« Électroménager », « Aspirateur »,
  « Aspirateur balai »), sans accents ni majuscules, les tirets lus comme des espaces (« Aspirateur-balai sans-fil »).
- **Le type** : le premier, du plus précis au plus général, dont la règle convient (son rayon, puis un mot du titre ou
  de la catégorie). Rien ne le dit (« Brava X5 » rangé sous « Électroménager > Aspirateur ») : le produit reste un
  aspirateur, sans type — il répond à « aspirateur », pas à « aspirateur balai ».
- **Un attribut** : le premier dit l'emporte (le titre avant la catégorie). L'offre ne le dit pas : inconnu, jamais
  supposé ; une recherche « sans fil » ne le promet pas. Ce qu'un type est par définition (un robot est sans fil) ne
  remplace jamais ce que l'offre dit.
- **Ce qui n'est pas un aspirateur reste hors du rayon** : un titre qui commence par un accessoire (sac, batterie,
  filtre, brosse, station de vidage…) n'a pas de catégorie ; un balai vapeur, un balai à franges non plus.
- **Gardé et relu** : la catégorie déclarée est gardée avec le produit (`_cat`, 120 caractères au plus) et relue à chaque
  publication sous l'ontologie en vigueur ; ce qu'une version d'avant avait lu et qui n'a plus de sens (les
  caractéristiques et besoins de la v57) est écarté au passage (`drops`). Les recherches sauvegardées en v57 avec des
  besoins sont relues sans eux (`missions.normalize`).

## Ce que l'app en fait

- **Recherche** : « aspirateur balai sans fil » → deux puces, « Aspirateurs balais » et « Sans fil » ; « aspirateur »
  seul : le domaine entier, robots compris. Un mot qui n'est ni un type ni un attribut est dit comme avant (« « chat
  parquet » : aucun produit ; voici le reste de votre recherche ») : aucun besoin n'est supposé.
- **Affiner** : Type (nom court, les plus fournis d'abord), puis Caractéristiques : sans fil et sans sac, oui ou non,
  chacun avec ce qu'il donnerait. Sans type choisi, seuls les attributs communs à plusieurs types (sans fil) ; un
  traîneau propose aussi sans sac (les autres le sont par définition).
- **Recherches sauvegardées** : « Aspirateur traîneau sans sac » ne promet que ce que l'offre dit, ou ce que le type est.
- **Fiche** : rien d'ajouté. Pas de section « L'essentiel » (v57), pas de résumé : la fiche dit le prix, son histoire
  et l'offre, comme les autres rayons.

## Mesures (`python -m bench.aspirateurs`, même banc sur le code v57 avec `--code`)

160 aspirateurs à vérité connue (marques fictives), leurs offres écrites comme un flux : un titre qui dit le type trois
fois sur quatre, parfois sans fil ou sans sac, sinon seulement la marque et le modèle ; une catégorie plus ou moins
précise. Lues comme la collecte (`market.match_product`), publiées, puis cherchées.

| | v57 | v58 |
|---|---|---|
| type, quand l'offre le dit (149) | 137 justes, 12 pas lus | **149 justes** |
| type, quand elle ne le dit pas (11) | 0 deviné | 0 deviné |
| sans fil dit (68) / sans sac dit (19) | 68 / 19 justes | 68 / 19 justes |
| non dits (92 / 141) | 0 deviné | 0 deviné |
| « aspirateur balai » : rappel de ce que l'offre dit | 84 % | **100 %** |
| « aspirateur à main » : rappel | 91 % | **100 %** |
| autres recherches (balai sans fil sous 300 €, traîneau sans sac, robot, laveur) | 100 % | 100 % |
| justes parmi les 6 premières cartes, chaque recherche | 100 % | 100 % |
| 31 offres écrites comme dans les flux : aspirateurs reconnus | 22 / 23 | **23 / 23** |
| … types justes / attributs justes | 16 / 20, 13 / 17 | **20 / 20, 17 / 17** |
| … pièges tenus hors du rayon (sacs, batterie, filtre, brosse, station, balai vapeur…) | 7 / 8 | **8 / 8** |

Les 31 offres « comme dans les flux » (majuscules, tirets, « à sac », « aspirateur robot », un type dit par la seule
catégorie, des accessoires) sont écrites à la main ; les trois écarts qu'elles ont montrés en v58 (« à sac », « Nettoyeur
de sols », « Station de vidage pour robot ») ont été corrigés ensuite : c'est un jeu de non-régression, pas une mesure
indépendante. Mutations : chaque règle du fichier et du code qui s'en sert, altérée une à une (91 en tout), fait
échouer un test (`docs/ARCHITECTURE.md`, « Vérifier »).

## Ajouter un domaine, réviser celui-ci

1. Un fichier `deals/ontology/<domaine>.json` : ses rayons (déjà suivis par la collecte), ses types et leur règle, un ou
   deux attributs que les flux disent vraiment (le relevé `sample` d'une enseigne le montre), leurs mots.
2. `python -m unittest tests.test_ontology` : le fichier est relu ; ajouter les offres réelles qui le mettent en défaut.
3. `python -m bench.aspirateurs` (ou son équivalent) : le type et les attributs lus, rien de deviné.
4. Changer la version (`2.0.0` → `2.1.0`) ; la publication suivante relit les produits gardés.

## Limites

- Un seul domaine a son ontologie ; ailleurs, la Recherche de la v56 (rayon, fonctions, tailles lues dans le titre).
- Seulement ce que le titre et la catégorie déclarée disent : un flux dont les titres ne disent ni le type ni les
  attributs donne des produits « aspirateur », sans plus. La lecture sur de vrais flux reste à mesurer (`sample`).
- Des règles écrites à la main, en français : un mot absent (« cordless ») n'est pas lu.
- Ce qu'un type est par définition (un balai est sans sac) est une règle du fichier : un balai à sac, s'il en existe,
  n'est dit « avec sac » que si son offre le dit.
