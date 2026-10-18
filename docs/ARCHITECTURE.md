# Architecture de DEALS

DEALS montre chaque jour les bonnes affaires qui existent. Le marché est relu une fois par nuit ; tout le reste en
découle. L'architecture suit cette réalité : **une chaîne de nuit qui calcule, une app de jour qui lit**.

```
                    NUIT (deals.py nightly, une fois par jour)                      JOUR (deals.py serve)

 sites des enseignes ─► fetch ─► extract ─► market ─────► publish ─► catalog ◄── catalog ◄── api ◄── web ◄── app (v41)
                        politesse  page HTML   produits,    deals,     tables       lectures    routes  HTTP
                        robots.txt → offre     offres,      fausses    publiées     indexées    /api/r/ statique
                        blocages   (pur)       prix         remises,   (une seule
                                               (écrit)      similaires transaction)             accounts, activity
                                                            (judge pur)                         (connexion, favoris,
                                                                                                 marques, clics)
```

## Principes (ce qui rend le système juste par construction)

1. **Calculer une fois, lire mille fois.** Les deals du jour sont une fonction des données de la nuit : `publish` les
   calcule après la collecte et les écrit dans des tables dédiées (`catalog`, `catalog_offers`, `similar`). Une requête
   de l'app ne calcule rien : une ou deux lectures indexées. Le coût d'une page ne dépend plus de l'historique.
2. **Le cœur est pur.** Lire une page (`extract`) et juger une remise (`judge`) sont des fonctions sans base ni réseau :
   même entrée, même sortie. On les vérifie sur des corpus et contre une vérité connue, pas sur des scénarios montés.
3. **Une seule écriture par sujet.** `market` est le seul module qui écrit produits, offres et prix ; `publish` le seul
   qui écrit le catalogue ; `accounts` et `activity` les seuls qui écrivent les données des personnes. Aucun module ne
   lit les tables d'un autre en dehors de ce qui est listé plus bas.
4. **Concurrence sans verrou applicatif.** SQLite en mode WAL : les lectures ne bloquent jamais ; chaque fil a sa
   connexion ; chaque écriture est une transaction courte (une page relue, une action d'une personne, une
   publication). Le serveur et la passe de nuit partagent le fichier sans se gêner.
5. **Ne jamais enregistrer une donnée fausse.** Une donnée manquée coûte un deal ; une donnée fausse coûte la confiance.
   Les garde-fous sont dans le code qui lit (`extract`) et dans la règle qui juge (`judge`), pas dans des correctifs.
6. **Échouer tôt, avec la cause.** Réglage invalide, robot sans nom ni contact, base d'un autre schéma : arrêt au
   démarrage avec un message qui nomme le problème, plutôt qu'un service qui tourne mal.
7. **Pas de fonction sans usage.** Ce que le produit ne montre pas n'est ni calculé, ni stocké, ni testé.

## Modules

| Module | Rôle | Dépend de | Écrit |
|---|---|---|---|
| `deals/config.py` | réglages (environnement `DEALS_*`), validés au chargement | — | — |
| `deals/store.py` | connexion SQLite (WAL, une par fil), **schéma complet**, version | — | — |
| `deals/fetch.py` | HTTP poli : robots.txt RFC 9309 (Protego), délais, blocages reconnus | vendor | — |
| `deals/extract/` | **pur** : page HTML → offre (prix, prix barré, disponibilité, identité, provenance) ; taxonomie (catégories, familles suivies) | — | — |
| `deals/market.py` | rapprochement produit (EAN → marque + référence → titre), prix au changement seulement | store, extract | products, offers, prices, site_rules |
| `deals/collect/` | découverte (plans de site), passe de nuit (un fil par site, coupe-circuit, budget), diagnostic, rapport | fetch, extract, market | runs |
| `deals/judge.py` | **pur** : vraie remise ou fausse remise, et la preuve retenue (prix de référence, nature) | — | — |
| `deals/publish.py` | calcule le catalogue du jour (meilleure offre, deal et sa preuve, nouveauté, fin d'offre, plus bas prix relevé, similaires) et l'écrit d'un bloc | store, judge, catalog (recherche) | catalog, catalog_offers, similar |
| `deals/catalog.py` | lectures de l'app (deals du jour, « depuis hier », catégories, marques, fiche, favoris), recherche | store, extract (familles) | — |
| `deals/accounts.py` | connexion par lien magique, sessions, limites d'envoi, SMTP | store, config | users, login_links, sessions |
| `deals/activity.py` | favoris, marques suivies, clics sortants, mesures | store | saves, follows, clicks |
| `deals/api.py` | contrat `/api/r/` (inchangé pour l'app) | catalog, accounts, activity | — |
| `deals/web.py` | serveur HTTP : app statique, routes, cookie, taille des requêtes, en-têtes | api | — |
| `deals/sim.py`, `deals/demo.py` | marché simulé à vérité connue ; démo par la vraie chaîne | collect, market, publish | — |
| `deals/cli.py` (`deals.py`) | une seule ligne de commande | tout | — |

Lectures croisées autorisées, et seulement celles-ci : `publish` lit `products/offers/prices` (pour calculer) ;
`collect` lit `catalog/saves/clicks` (pour ordonner la relecture de nuit : deal en cours, favori, clic récent) ;
`activity` lit `offers` (pour rediriger un clic vers l'adresse connue) et `catalog` (prix au moment d'un favori) ;
`catalog` lit `follows/saves` (pour personnaliser l'ordre, les signets et la baisse d'un favori).

## Données

```
products   (id, gtin unique, brand, mpn, title, norm_title, category, attributes, image, needs_review)
offers     (id, url unique, host, retailer, merchant, product_id, category_hint, status, note, protection, etag,
            last_modified, pending_price, fails, checked_at)                status : new | active | gone | blocked
                                                                             | disallowed | out_of_scope
prices     (offer_id, first_seen, last_seen, price, was, availability, seller, valid_until, lowest_30d, source,
            was_source)                                    une ligne par CHANGEMENT ; last_seen avance sinon
catalog    (product_id, name, title, brand, category, price, was, pct, merchant, offer_id, verified, search, published_on,
            since, ends, low_days, usual, proof, fake, n_offers, tracked)      depuis quand la remise court, fin déclarée,
                                                         plus bas prix relevé depuis n jours, preuve, remise jugée fausse
catalog_offers (product_id, offer_id, merchant, price, was, pct, availability, rank)
similar    (product_id, other_id, rank)
users, login_links, sessions          (jetons stockés en SHA-256)
follows (user_id, brand) · saves (user_id, product_id, price) · clicks (at, day, user_id, product_id, offer_id, merchant, source)
site_rules (host, rules) · runs (day, started, ended, stats)
```
Le schéma vit dans `store.py` et nulle part ailleurs : `SCHEMA` (version 1) puis `MIGRATIONS`, dans l'ordre, en une
transaction. Une base neuve suit exactement le même chemin qu'une base existante : chaque migration est exécutée par
chaque test. `PRAGMA user_version` date la base ; un code plus ancien que la base refuse de démarrer. Une évolution du
schéma = `SCHEMA_VERSION + 1` et une entrée dans `MIGRATIONS` (version 2 : catalogue enrichi, prix des favoris).

## La nuit (`python deals.py nightly`)

1. **Plan** : toutes les offres suivies des enseignes activées (les fiches disparues sont revérifiées une nuit sur
   sept). Par site, ordre de valeur : produit en deal, en favori, cliqué depuis 3 jours, puis le plus ancien relu.
2. **Collecte** : un fil par site, à son rythme poli (5 s ou le Crawl-delay du site) ; coupe-circuit après 5 refus de
   suite ; arrêt au budget de nuit (ce qui n'est pas relu garde son prix, qui vieillit : au-delà de 3 jours il n'est
   plus montré). Chaque page : `fetch` → `extract` → décision → `market` dans une transaction courte.
3. **Confirmation** : une variation de prix énorme (÷2, ×2) est relue une fois avant d'être enregistrée.
4. **Rapport** : réussite par enseigne, passe interrompue, chute du taux de prix barré lu, plus fortes baisses.
5. **Publication** : `publish` lit le marché, juge chaque produit avec `judge`, calcule les similaires, réécrit le
   catalogue en une transaction (l'app passe d'un catalogue complet au suivant, jamais un état intermédiaire).

## Les règles du produit (où elles vivent)

| Règle | Où |
|---|---|
| Lire un prix sans se tromper (prix membre, financement, produit voisin, page liste…) | `extract/offer.py` |
| Catalogue : familles suivies, accessoires écartés, seuil de 100 € | `collect/retailers.py`, `extract/categories.py` |
| Une remise est réelle sauf preuve du contraire ; preuve = historique hors promotion (≥ 14 jours) ou mention légale « plus bas 30 jours » ; prix barré permanent (≥ 60 jours) = pas un deal | `judge.py` |
| Montrer la preuve : prix habituel relevé, ou plus bas 30 jours affiché, ou « annoncée par l'enseigne » ; plus bas prix relevé depuis n jours | `judge.py`, `publish.py` |
| Depuis hier : « nouvelle » = remise absente de la publication précédente ; « finit bientôt » = fin déclarée par l'enseigne dans 3 jours ou moins | `publish.py`, `catalog.py` |
| Classement : remise, × 1,5 pour une marque suivie | `catalog.py` |
| Clic sortant : seulement vers l'adresse d'une offre connue, tracé | `activity.py` |
| Connexion : lien à usage unique 15 min ; 5 liens par adresse et par heure, 20 par adresse IP, plafond quotidien global | `accounts.py` |

## Vérifier

| Quoi | Commande | Mesure actuelle |
|---|---|---|
| Contrats (38 tests, ~8 s) | `python -m unittest discover -s tests -t .` | tout passe, Python 3.11 à 3.13 |
| Extraction | `python -m bench.extraction` | 1 036/1 040 prix réels · 36/36 JSON-LD · 66/66 robots.txt · 26/26 + 8/8 pages-pièges |
| Vraie / fausse remise, de bout en bout | `python -m bench.deals_truth` | 1er mois : rappel 89 %, précision 81 % · ensuite : 98 %, 90 % |
| Tenue en charge (3 000 produits) | `python -m bench.scale` | publication ~2,7 s par nuit · lectures de l'app < 5 ms |

## Ce qui a été retiré, et pourquoi

Le moteur de « veille de marché » des générations précédentes : événements, signaux, surveillances, webhooks, flux
temps réel, console interne, planification par offre toutes les 15 minutes, flux marchands, motifs saisonniers. Le
produit n'en lit rien ; tout était calculé, stocké et testé quand même (voir `docs/AUDIT.md`). Si un jour un flux
marchand devient une source, il s'ajoute comme une source de `collect/` qui produit des offres pour `market`, sans
toucher au reste.

## Ajouter quelque chose sans rien casser

- **Une enseigne** : une entrée dans `collect/retailers.py`, puis `deals.py diagnose <enseigne>`.
- **Un format de page** : un cas dans `tests/pages.py`, puis la règle dans `extract/offer.py` ; `python -m bench.extraction`.
- **Une règle de deal** : `judge.py` (pur), un cas dans `tests/test_judge.py`, la mesure `python -m bench.deals_truth`.
- **Un écran de l'app** : une lecture dans `catalog.py`, une route dans `api.py`. Si elle demande un calcul, il va dans
  `publish.py`, jamais dans la requête. Interface : `web/src/App.jsx`, reconstruite par `web/build.sh` (revue
  utilisateur et mesures : `docs/UX.md`).
