# L'ontologie de DEALS — comprendre un besoin, choisir et dire pourquoi (v57, aspirateurs pilotes)

« Aspirateur pour mon chat avec du parquet, 300 € max » : jusqu'à la v56, la Recherche comprenait le rayon et le budget,
et disait le reste ignoré (« « chat parquet, » : aucun produit »). Sur les 27 besoins du banc, 42 mots tombaient ainsi.
La v57 comprend le besoin, choisit les produits qui y répondent et dit pourquoi, carte par carte. Sans IA : ce que l'app
sait d'un domaine est écrit à la main, en **données versionnées** (`deals/ontology/aspirateurs.json`), relues et testées,
et un moteur l'applique au catalogue publié (`deals/journey.py`). Les aspirateurs sont le domaine pilote ; les autres
rayons gardent la Recherche de la v56.

## Quatre niveaux, séparés

| Niveau | Ce qu'il dit | Aspirateurs |
|---|---|---|
| Taxonomie | le chemin du domaine, ses catégories, ses sous-familles et la règle qui y range un produit — la première qui convient, dans l'ordre (un « balai laveur » est un laveur) | Maison › Entretien › Aspirateurs ; robot, laveur, à main, balai, traîneau |
| Ontologie du domaine | les **caractéristiques** : type (oui/non, nombre, liste), unité, plage, comment les lire sur la fiche de l'enseigne (129 noms déclarés, formats et unités variés) ou dans le titre ; ce qu'un type entraîne (« un robot est sans fil ») ; ce qui se déduit (« une autonomie : sur batterie ») | 23 caractéristiques, 3 déductions |
| Modèle de décision | les **critères**, calculés par sous-famille à partir des caractéristiques : oui (1), en partie (0,5), non (0) ou inconnu, avec la phrase qui le dit ; les **besoins**, qui demandent des critères — fort, faiblement, ou sans exception (éliminatoire) ; les **questions** à poser quand la demande est vague | 15 critères, 17 besoins, 2 questions |
| Offres et décision | le moteur de parcours applique ces règles aux produits publiés et à leurs prix ; rien de ce niveau n'est dans l'ontologie | `deals/journey.py`, `deals/catalog.py` |

**Une caractéristique n'est pas un critère.** Le poids est une caractéristique ; « léger, maniable » est un critère qui
le lit selon le type : 2,4 kg, c'est léger pour un balai (oui), 4,8 kg l'est pour un traîneau (en partie), et un robot ne
se porte pas (non). « Grande surface » lit l'autonomie d'un balai, le rayon d'action d'un traîneau filaire, l'autonomie
d'un robot (150 min au moins). Les seuils (70 dB pour silencieux, 2,5 kg, 60 min) sont des choix tirés des guides
d'achat, écrits dans le fichier, à réviser comme le reste.

## Le format

Un fichier JSON par domaine (`deals/ontology/<domaine>.json`), relu au démarrage. Extraits :

```json
{"schema": 1, "domain": "aspirateurs", "version": "1.0.0", "path": ["Maison", "Entretien", "Aspirateurs"],
 "categories": ["aspirateur", "robot_aspirateur"],
 "subfamilies": [{"key": "robot", "match": {"category": ["robot_aspirateur"]}, "implies": {"cordless": true},
                  "decision": ["navigation", "mapping", "auto_empty", "mop", "autonomy_min", "…"]}, "…"],
 "properties": [{"key": "weight_kg", "label": "Poids", "type": "number", "unit": "kg", "range": [0.2, 15],
                 "fiche": [{"names": ["poids", "poids net", "…"], "value": "number", "units": {"kg": 1, "g": 0.001}}],
                 "titre": [{"re": "(\\d{1,2}(?:[.,]\\d{1,2})?)\\s*kg\\b"}]}, "…"],
 "infer": [{"if": {"autonomy_min": "known"}, "then": {"cordless": true}, "say": "une autonomie : sur batterie"}],
 "criteria": [{"key": "poils", "label": "Poils d'animaux",
               "rules": [{"if": {"pet_tool": true}, "score": 1, "say": "Brosse pour les poils"},
                         {"if": {"motor_brush": true}, "score": 0.5, "say": "Brosse motorisée"}],
               "no": "Pas de brosse pour les poils", "unknown": "Brosse pour les poils non précisée"}, "…"],
 "needs": [{"key": "escaliers", "label": "Escaliers", "words": ["escalier", "escaliers", "marches"],
            "criteria": {"escaliers": "eliminatoire", "maniabilite": "faible"}, "hint": ["main", "balai"],
            "say": "Des escaliers : un aspirateur à main, ou un balai qui en devient un"}, "…"],
 "questions": [{"key": "type", "text": "Comment voulez-vous faire le ménage ?", "when": "sub",
                "options": [{"label": "Il passe tout seul", "small": "Robot", "apply": {"sub": "robot"}}, "…"]}]}
```

Une règle de critère est une condition sur la sous-famille et les caractéristiques (`true`/`false`, une valeur, une
liste, `{min, max}`, `null` : inconnue, `"known"` : connue) ; la première vraie décide. Les mots du domaine (« aspi »),
des sous-familles (« robot laveur »), des besoins (« chat », « marches », « 120 m² ») et des caractéristiques
(« sans sac », « HEPA ») forment la langue du domaine ; les mots qui ne demandent rien (« ménage », « famille ») sont
dits comme tels et ne sont plus « ignorés ».

## Faits, déductions, inconnu

- **Chaque fait garde sa source** : la fiche déclarée par l'enseigne (la plus sûre), le titre, le nom du modèle
  (« Animal », « Allergy », « Parquet » : un indice plus faible, dit comme tel), puis ce que le type entraîne et ce qui
  se déduit. Une déduction n'est jamais rangée comme un fait : elle n'est calculée qu'au moment de juger, et la source
  d'un verdict est la moins sûre des caractéristiques qu'il lit.
- **Inconnu reste inconnu.** Une caractéristique que la page ne dit pas n'est ni oui ni non : la fiche affiche « non
  précisé », le critère est inconnu. Pour classer, un critère inconnu compte un quart de ce qu'il peut encore valoir :
  un produit dont la page ne dit rien passe après ceux dont on sait qu'ils conviennent, et avant ceux dont on sait
  qu'ils ne conviennent pas ; un besoin éliminatoire n'écarte que ce qu'on sait ne pas y répondre.
- **Daté et versionné** : chaque produit garde la version de l'ontologie qui l'a lu (`_v`) et quand sa fiche a été lue
  (`_at`). La fiche brute est gardée (`_props` : 40 caractéristiques au plus, 120 caractères chacune) : une ontologie
  révisée relit tous les produits à la publication suivante, **sans relire les pages**.
- **Une donnée fausse ne passe pas** : hors de sa plage ou sans l'unité exigée (« Puissance : 2 200 » sans W), une valeur
  n'est pas lue ; ce qui n'a pas de sens pour le domaine est écarté (« 2,6 kg » est un poids, pas la capacité d'un
  lave-linge : 9 faits faux de ce genre sur les pages du banc en v56, 0 en v57).

## Comprendre une phrase

`query.read` reconnaît le domaine (« aspirateur », « robot qui se vide tout seul »), puis `Domain.understand` lit sa
langue : les expressions les plus longues d'abord, chaque mot pris une seule fois (« auto-vidage » n'est pas la
voiture) ; une surface (« 120 m² » : grande surface, dès 100 m² ; « 45 m² » : petite, jusqu'à 60) ; deux types nommés,
le plus précis l'emporte et l'autre dit ce qu'il apporte (« robot laveur » : un robot, qui lave). Les besoins suivent
l'ordre de la phrase. Ce qui est compris devient des puces (« Pour Poils d'animaux ») et un encadré qui dit pourquoi
(« Poils d'animaux · Un chat ou un chien : une brosse faite pour les poils (d'après « chat ») ») ; une puce se retire
d'un geste, rien d'autre n'est supposé.

## Choisir, sans rien imposer (`deals/journey.py`)

- **Contraintes et préférences.** Ce qui est dit comme une contrainte filtre : le budget, le type, une caractéristique
  (« sans fil », « sans sac »), un besoin sans exception (laver le sol, se vider seul, cartographier, les escaliers) —
  et un besoin sans exception n'écarte que ce dont on sait qu'il n'y répond pas, l'écran le dit (« 22 produits
  écartés : ne lave pas le sol. »). Le reste classe : un besoin fort pèse 1, un faible 0,35 (« des sols durs »), un
  besoin de contexte ne change rien (« un appartement » : dit, sans critère).
- **Classement.** D'abord les produits qui satisfont tout à fait le plus de critères forts, puis l'adéquation (la
  moyenne pondérée des verdicts), puis l'ordre demandé (les meilleures affaires, ou le prix). Chaque carte dit ses deux
  premières raisons, et la source quand elle est faible (« ✓ Brosse pour les poils (d'après le nom) », « ≈ Brosse
  motorisée », « ? Brosse pour parquet non précisée »).
- **Rien d'imposé.** Aucune préférence que la personne n'a pas dite : une demande précise ne reçoit pas de question,
  un type nommé n'est jamais remplacé. Quand le type demandé ne peut pas répondre à un besoin (une règle de type à 0 :
  « un robot ne monte pas les marches »), le critère est mis à part et un autre type est **proposé**, avec sa raison
  et son nombre de produits — celui que le besoin suggère d'abord, s'il peut y répondre et a des produits
  (« Voir les aspirateurs à main (3) ») ; la sélection reste celle du type demandé. Sans autre type possible
  (« aspirateur à main pour une grande maison sous 60 € »), la raison reste dite (« Un aspirateur à main est fait pour
  les petits travaux. »).
- **La question utile.** Seulement si la demande est vague (ni type, ni besoin, ni caractéristique, ni marque, ni mot
  cherché) et que l'app n'a pas de critère ; le type d'abord, puis l'usage ; posée seulement si au moins deux réponses
  ont des produits et changent vraiment la sélection (au plus 3 des 6 premiers en commun). Elle ne bloque rien : la
  sélection est dessous, « Passer » la retire pour la suite.
- **Une référence** (« Kessler Aero 12 ») : le produit en premier, sans question.
- Verdicts et faits sont gardés le temps d'une publication (ils ne changent qu'à la nuit) : sur 3 000 produits et 640
  aspirateurs (`python -m bench.scale --aspirateurs 640`), un besoin se cherche en ~12 ms, la question d'une demande
  vague en ~15 ms, Explorer en ~4 ms ; la publication relit les fiches sans coût visible (~1 ms par produit, comme
  les autres : 3,6 s pour 3 640 produits, 3,0 s pour 3 000).

## Explorer, Affiner, la fiche

- **Trois portes** sur l'accueil : *Rechercher* (« Dites ce qu'il vous faut, même un besoin »), *Les bonnes affaires*
  (la Recherche en promo, la plus forte remise d'abord), *Explorer* (« Par type, par usage »). Aucun tunnel : chaque
  porte mène à un écran complet, et de chacun on passe aux autres.
- **Explorer**, sans rien régler : le chemin du domaine, ses produits, dès quel prix, ses remises ; chaque type (combien,
  dès quel prix, ce qu'il fait de mieux, illustré par sa meilleure remise) ; les usages qui ont des produits qui leur
  conviennent tout à fait, et combien ; puis tous les rayons. Un geste ouvre la Recherche avec ce critère, en puce.
- **Affiner** dans un domaine : le type (chacun avec son nombre de produits), l'usage, les caractéristiques qui décident
  pour ce type (oui ou non, avec leur nombre), poids, bruit et autonomie par paliers, les marques ; ce qui ne
  changerait rien n'est pas proposé.
- **La fiche : « L'essentiel »** — les caractéristiques qui décident pour son type, dans l'ordre où elles décident, avec
  leur valeur et leur source (« Poids 2,5 kg · fiche de l'enseigne », « Alimentation Sans fil · titre ») ou « Non
  précisé » ; « Caractéristiques lues sur la page de l'enseigne le 1 oct. ; ce qui n'y est pas reste « non précisé »,
  jamais deviné. »
- Une recherche sauvegardée garde son type, ses besoins et ses caractéristiques ; son nom les dit (« Aspirateur balai
  pour les poils d'animaux et le parquet »). Elle ne promet que les produits dont on sait qu'ils répondent tout à fait
  à ses besoins (un besoin dont la fiche ne dit rien n'est pas promis : 7 aspirateurs pour « mon chat » quand la
  Recherche en classe 33) ; ce que le type demandé ne peut pas est mis à part, comme dans la Recherche.

## Réviser, ajouter un domaine, tester

- **Relue avant de servir** (`ontology.check`) : schéma, version (trois nombres), références (sous-familles,
  caractéristiques, critères, besoins), expressions lisibles, scores permis (0, 0,5, 1), une règle ne dit pas une valeur
  qu'elle ne lit pas, chaque mot n'appartient qu'à un seul sens. Une faute arrête le démarrage, avec l'endroit.
- **Réviser** : modifier le fichier, monter sa version, lancer les tests et `python -m bench.needs` ; à la publication
  suivante, chaque produit est relu de sa fiche gardée sous la nouvelle version.
- **Ajouter un domaine** : un fichier JSON et ses catégories. Le moteur, la Recherche, Affiner, Explorer et la fiche le
  suivent ; le code ne change que là où l'ancienne extraction lisait déjà des fonctions de ce domaine (les aspirateurs :
  « balai », « traîneau », « laveur », « sans fil », `DOMAIN_FEATURES` dans `deals/query.py`).
- **Tests** : `tests/test_ontology.py` (le fichier relu et ses fautes, chaque format de fiche et de titre, faits et
  déductions, chaque verdict, la langue du domaine), `tests/test_journey.py` (ordre des critères, classement, conflits
  et autre type, question, verdicts gardés), `tests/test_catalog.py` (le parcours de bout en bout dans la Recherche,
  Affiner, Explorer, la fiche), `tests/test_missions.py` (ce qu'une recherche gardée promet). 125 mutations des règles
  v57 (code et données de l'ontologie, moteur, phrase, Recherche, missions, API, profil) : toutes détectées.

## Mesures (`python -m bench.needs`)

Un catalogue de **160 aspirateurs à vérité connue** (marques fictives : 60 balais, 35 traîneaux, 40 robots, 12 laveurs,
13 à main) : chaque produit a ses vraies caractéristiques ; sa page n'en dit qu'une partie, comme en vrai (le titre, une
fiche plus ou moins complète aux noms et formats variés ; une page sur sept n'a que le titre). Le code mesuré ne voit que
la page : il la lit comme la collecte, publie, puis on lui pose chaque phrase (la première réponse de l'API).

| | v56 | v57 |
|---|---|---|
| 27 besoins (« aspirateur pour poils de chien », « silencieux pour allergiques »…) : bons parmi les 6 premières cartes | 35 % | **96 %** |
| Cartes exclues (hors budget, autre type, usage impossible) parmi les 6 premières | 28 | **0** |
| Rappel des bons dans la réponse · nDCG@6 | 53 % · 0,59 | **90 % · 0,98** |
| Besoins dits à la personne · mots ignorés | 0 · 42 | **24 phrases · 0** |
| « Oui » dits sur les cartes et vrais | — | **162 / 164** |
| 4 demandes vagues (« quel aspirateur choisir ? ») : une question utile, sans bloquer | 0 | **4** |
| 5 demandes précises : question posée · la référence en premier · cartes admissibles | 0 · non · 100 % | **0 · oui · 100 %** |
| 3 besoins impossibles pour le type demandé : un autre type proposé, avec sa raison | 0 | **3** |
| Caractéristiques dites par les pages : lues justes · lues fausses · faits d'autres rayons | 116 / 1 217 · 0 · 9 | **1 217 / 1 217 · 0 · 0** |

**Lecture honnête.** La vérité est écrite à la main, avant le moteur, d'après ce que disent les guides d'achat — mais
par le même auteur que l'ontologie : elles peuvent partager un biais, et le banc mesure surtout que le moteur suit ses
règles, pas que les règles sont les bonnes. Les fiches du banc sont générées avec des noms et des formats que
l'ontologie sait lire : la lecture à 100 % est acquise par construction ; sur de vraies pages, elle sera plus basse, et
elle n'est pas encore mesurée (l'environnement de développement n'a pas accès au web) : à mesurer sur un échantillon de
fiches réelles (`deals.py sample` en garde les pages brutes). Les cartes « bonnes » manquées viennent surtout de pages qui
ne disent pas la caractéristique (inconnue, donc classée après) : ce que la page ne dit pas, le moteur ne l'invente pas.
Les 2 « oui » contredits par la vérité sont un même produit, un traîneau sans fil de 60 min : l'ontologie le dit
capable d'une grande surface (comme un balai de 60 min), la vérité, écrite avant, ne l'admet que pour un traîneau à fil ;
un désaccord de règles, pas une erreur de lecture, laissé tel quel (la vérité n'est pas retouchée après coup). Un fait
tiré du nom du modèle (« Animal ») est un indice plus faible : la carte le dit (« d'après le nom »). Le vrai juge sera
la production : clics, retours, et les fiches réelles des enseignes.

## Limites

- Un seul domaine (les aspirateurs) ; ailleurs, la Recherche de la v56.
- Une langue écrite : un mot hors de la liste n'est pas compris (pas d'IA, pas de correction des fautes de frappe) ;
  il reste un mot cherché, et l'écran le dit.
- Les seuils et les poids sont des choix, écrits et versionnés, pas appris ; une seule question à la fois, de deux sortes
  (le type, l'usage).
- Une fiche d'enseigne peut se tromper : l'app dit d'où vient chaque fait, sans le garantir.

## Où sont les règles

| Règle | Où |
|---|---|
| Ce que l'app sait des aspirateurs : types, caractéristiques, critères, besoins, questions, mots | `deals/ontology/aspirateurs.json` |
| Relire une ontologie, lire une page, faits et déductions, juger un critère, comprendre une phrase | `deals/ontology/__init__.py` (`check`, `read`, `facts`, `judge`, `understand`) |
| Lire et garder la fiche d'un produit, la relire sous l'ontologie du jour | `deals/extract/categories.py` (`attributes`, `product_attributes`), `deals/market.py`, `deals/publish.py` |
| La phrase : domaine, type, besoins, caractéristiques ; une caractéristique exigée répond-elle | `deals/query.py` (`read`, `fitter`, `chips`) |
| Classer, écarter, expliquer, proposer un autre type, la question utile | `deals/journey.py` (`Plan`, `conflict`, `suggest`, `question`, `Verdicts`) |
| La Recherche, Affiner, Explorer, « L'essentiel » | `deals/catalog.py` (`search`, `_journey`, `_domain_options`, `explore`, `_essentials`) |
| Recherches sauvegardées d'un domaine | `deals/missions.py` |
| L'écran | `web/src/App.jsx` : les trois portes de l'accueil, la vue Explorer ; dans la Recherche, l'encadré de ce qui est compris, la question, l'autre type, la référence ; `RefineSheet` ; « L'essentiel » de la fiche |
