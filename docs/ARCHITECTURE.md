# Architecture de DEALS

DEALS montre chaque jour les bonnes affaires qui existent. Le marché est relu une fois par nuit ; tout le reste en
découle. L'architecture suit cette réalité : **une chaîne de nuit qui calcule, une app de jour qui lit**.

```
                    NUIT (deals.py nightly, une fois par jour)                      JOUR (deals.py serve)

 sites des enseignes ─► fetch ─► extract ─► market ─────► publish ─► catalog ◄── catalog ◄── api ◄── web ◄── app (v48)
                        politesse  page HTML   produits,    deals,     tables       lectures    routes  HTTP
                        robots.txt → offre     offres,      fausses    publiées     indexées    /api/r/ statique
                        blocages   (pur)       prix         remises,   (une seule
                                               (écrit)      moins cher transaction)             accounts, activity,
                                                            comparable    │                     missions (connexion,
                                                            (purs)        ▼                     favoris, marques,
                                                                       missions ─► e-mails      clics, missions)
                                                                       prix atteints : un par personne
```

## Principes (ce qui rend le système juste par construction)

1. **Calculer une fois, lire mille fois.** Les deals du jour sont une fonction des données de la nuit : `publish` les
   calcule après la collecte et les écrit dans des tables dédiées (`catalog`, `catalog_offers`, `alternatives`,
   `similar`). Une requête de l'app ne calcule rien : une ou deux lectures indexées. Le coût d'une page ne dépend plus
   de l'historique.
2. **Le cœur est pur.** Lire une page (`extract`), juger une remise (`judge`) et dire si un produit en remplace un autre
   (`alternatives`) sont des fonctions sans base ni réseau : même entrée, même sortie. On les vérifie sur des corpus et
   contre une vérité connue ou une grille indépendante, pas sur des scénarios montés.
3. **Une seule écriture par sujet.** `market` est le seul module qui écrit produits, offres et prix ; `publish` le seul
   qui écrit le catalogue ; `accounts`, `activity` et `missions` les seuls qui écrivent les données des personnes. Aucun module ne
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
| `deals/judge.py` | **pur** : vraie remise ou fausse remise, à partir des preuves disponibles | — | — |
| `deals/alternatives.py` | **pur** : ce qui remplace un produit (même usage, pas moins bien) et coûte au moins 10 % de moins | — | — |
| `deals/publish.py` | calcule le catalogue du jour (meilleure offre, deal, depuis quand et jusqu'à quand, courbe de 90 jours, alternatives moins chères, similaires) et l'écrit d'un bloc | store, judge, alternatives, extract, catalog (recherche) | catalog, catalog_offers, alternatives, similar, meta |
| `deals/catalog.py` | lectures de l'app (deals du jour, recherche dans tout le catalogue, catégories, marques, pages d'une marque et d'une catégorie avec tous leurs produits, fiche et ses alternatives, favoris) ; libellés et caractéristiques lisibles | store, extract (familles) | — |
| `deals/missions.py` | **pur** : une phrase → une mission (`interpret`), ce qui rend un produit comparable (`like`), un produit remplit-il une mission (`matches`) ; les missions d'une personne (lancer, une par cible, lister avec leur état, arrêter) ; la nuit, un e-mail par personne (`notify`) | store, catalog, extract, alternatives (classes énergie), accounts (envoi) | missions |
| `deals/accounts.py` | connexion par lien magique, sessions, limites d'envoi, SMTP (liens de connexion, e-mails de missions) | store, config | users, login_links, sessions |
| `deals/activity.py` | favoris, marques suivies, clics sortants, mesures | store | saves, follows, clicks |
| `deals/api.py` | contrat `/api/r/` (inchangé pour l'app, routes ajoutées) | catalog, accounts, activity, missions | — |
| `deals/web.py` | serveur HTTP : app statique, routes, cookie, taille des requêtes, en-têtes | api | — |
| `deals/sim.py`, `deals/demo.py` | marché simulé à vérité connue ; démo par la vraie chaîne | collect, market, publish | — |
| `deals/cli.py` (`deals.py`) | une seule ligne de commande | tout | — |

Lectures croisées autorisées, et seulement celles-ci : `publish` lit `products/offers/prices` (pour calculer) ;
`collect` lit `catalog/saves/clicks` (pour ordonner la relecture de nuit : deal en cours, favori, clic récent) ;
`activity` lit `offers` (pour rediriger un clic vers l'adresse connue) et `catalog` (prix au moment d'un favori) ;
`catalog` lit `follows/saves` (pour personnaliser l'ordre, les signets et la baisse d'un favori) ; `missions` lit
`catalog/catalog_offers` (produits publiés, disponibilité de la meilleure offre) et `users` (l'adresse où écrire, la
nuit).

## Données

```
products   (id, gtin unique, brand, mpn, title, norm_title, category, attributes, image, needs_review)
offers     (id, url unique, host, retailer, merchant, product_id, category_hint, status, note, protection, etag,
            last_modified, pending_price, fails, checked_at)                status : new | active | gone | blocked
                                                                             | disallowed | out_of_scope
prices     (offer_id, first_seen, last_seen, price, was, availability, seller, valid_until, lowest_30d, source,
            was_source)                                    une ligne par CHANGEMENT ; last_seen avance sinon
catalog    (product_id, name, title, brand, category, price, was, pct, merchant, offer_id, verified, search, published_on,
            since, ends, specs, history, attrs) depuis quand la remise court, fin déclarée par l'enseigne, caractéristiques
                                         lisibles, meilleur prix de chaque jour sur 90 jours (fiche), attributs lus (missions)
meta       (key, value)                  heure de la dernière publication (« MAJ » du bandeau), écrite avec le catalogue
catalog_offers (product_id, offer_id, merchant, price, was, pct, availability, rank)
alternatives (product_id, other_id, rank)       comparables, disponibles, au moins 10 % moins chers (fiche)
similar    (product_id, other_id, rank)         les autres comparables, au prix le plus proche (fiche, à défaut)
users, login_links, sessions          (jetons stockés en SHA-256)
follows (user_id, brand) · saves (user_id, product_id, price) · clicks (at, day, user_id, product_id, offer_id, merchant, source)
missions   (id, user_id, product_id, category, brand, want, max_price, label, created_at, notified)
            ce qui est guetté (un produit, ou catégorie, marque et souhaits : fonctions, tailles), le prix maximum ;
            notified : produit → prix du dernier e-mail (rien n'est renvoyé au même prix)
site_rules (host, rules) · runs (day, started, ended, stats)
```
Le schéma vit dans `store.py` et nulle part ailleurs : `SCHEMA` (version 1) puis `MIGRATIONS`, dans l'ordre, en une
transaction. Une base neuve suit exactement le même chemin qu'une base existante : chaque migration est exécutée par
chaque test. `PRAGMA user_version` date la base ; un code plus ancien que la base refuse de démarrer. Une évolution du
schéma = `SCHEMA_VERSION + 1` et une entrée dans `MIGRATIONS` (version 2 : durées de la fiche, prix des favoris ;
version 3 : alternatives ; version 4 : description de la fiche ; version 5 : courbe de prix, heure de publication ;
version 6 : missions).

## La nuit (`python deals.py nightly`)

1. **Plan** : toutes les offres suivies des enseignes activées (les fiches disparues sont revérifiées une nuit sur
   sept). Par site, ordre de valeur : produit en deal, en favori, cliqué depuis 3 jours, puis le plus ancien relu.
2. **Collecte** : un fil par site, à son rythme poli (5 s ou le Crawl-delay du site) ; coupe-circuit après 5 refus de
   suite ; arrêt au budget de nuit (ce qui n'est pas relu garde son prix, qui vieillit : au-delà de 3 jours il n'est
   plus montré). Chaque page : `fetch` → `extract` → décision → `market` dans une transaction courte.
3. **Confirmation** : une variation de prix énorme (÷2, ×2) est relue une fois avant d'être enregistrée.
4. **Rapport** : réussite par enseigne, passe interrompue, chute du taux de prix barré lu, plus fortes baisses.
5. **Publication** : `publish` lit le marché, juge chaque produit avec `judge`, choisit avec `alternatives` ce qui le
   remplace pour moins cher, réécrit le catalogue en une transaction (l'app passe d'un catalogue complet au suivant,
   jamais un état intermédiaire).
6. **Missions** : `missions.notify` relit les missions sur le catalogue publié (chaque catégorie lue une fois, du moins
   cher au plus cher : une mission ne détaille que les produits sous son prix) ; un e-mail par personne avec ce qui est
   nouveau à son prix ; un envoi qui échoue, ou qui dépasserait le plafond de la nuit, ne marque rien : il repart la
   nuit suivante. Le jour, l'état des missions se lit sur le même catalogue (produits lus gardés jusqu'à la
   publication suivante).

## Les règles du produit (où elles vivent)

| Règle | Où |
|---|---|
| Lire un prix sans se tromper (prix membre, financement, produit voisin, page liste…) | `extract/offer.py` |
| Catalogue : familles suivies, accessoires écartés, seuil de 100 € | `collect/retailers.py`, `extract/categories.py` |
| Alternative : même catégorie ; même usage (taille de literie, largeur, places, forme : balai, traîneau, encastrable, d'angle, américain) ; au moins les mêmes fonctions (sans fil, laveur, convertible, induction, électrique) ; pas moins bien (énergie, capacité, couverts, foyers, volume, autonomie, bruit) ; moins chère = au moins 10 % de moins et disponible ; la plus forte économie d'abord, une marque par ligne | `alternatives.py` |
| Recherche : tout le catalogue suivi, les remises d'abord, puis du moins cher au plus cher | `catalog.py` |
| Marque, catégorie : tous leurs produits, les remises d'abord (depuis une fiche, jamais de cul-de-sac) | `catalog.py` |
| Mission : ce qui est dit est exigé (catégorie, marque, fonctions ; capacité, couverts, foyers, places, volume, autonomie au moins ; taille de literie exacte ; largeur à 6 % près ; bruit au plus ; classe énergie au moins), ce qui ne l'est pas ne l'est pas ; disponible et au prix voulu ; caractéristique inconnue du produit = pas de promesse ; comparable = même catégorie, mêmes fonctions, même taille ou capacité ; une mission par cible, 20 par personne | `missions.py` |
| E-mail de mission : un par personne et par nuit, seulement le nouveau (jamais deux fois le même produit au même prix, rien de ce qui était visible au lancement), les cinq moins chers par mission, plafond par nuit (`DEALS_MISSION_MAILS`) | `missions.py` |
| Une remise est réelle sauf preuve du contraire ; preuve = historique hors promotion (≥ 14 jours) ou mention légale « plus bas 30 jours » ; prix barré permanent (≥ 60 jours) = pas un deal | `judge.py` |
| Interface : flux de cartes (visuel, remise, marque, nom, prix) ; caractéristiques, durées et courbe seulement dans la fiche ; la qualité est implicite | `web/src/App.jsx`, illustrations `web/src/art.jsx` (caractéristiques lisibles : `catalog.specs`) |
| Prix sur 90 jours : meilleur prix disponible de chaque jour, toutes enseignes, calculé à la publication ; plus bas, habituel = médiane | `publish.py` (`chart`), `web/src/App.jsx` |
| Classement : remise, × 1,5 pour une marque suivie | `catalog.py` |
| Clic sortant : seulement vers l'adresse d'une offre connue, tracé | `activity.py` |
| Connexion : lien à usage unique 15 min ; 5 liens par adresse et par heure, 20 par adresse IP, plafond quotidien global | `accounts.py` |
| Interface des missions : une phrase, ce qui est compris et ce qui y répond déjà avant de lancer ; connexion au lancement, la mission attend le retour du lien | `web/src/App.jsx` |

## Vérifier

| Quoi | Commande | Mesure actuelle |
|---|---|---|
| Contrats (54 tests, ~9 s) | `python -m unittest discover -s tests -t .` | tout passe, Python 3.11 à 3.13 |
| Extraction | `python -m bench.extraction` | 1 036/1 040 prix réels · 36/36 JSON-LD · 66/66 robots.txt · 26/26 + 8/8 pages-pièges |
| Vraie / fausse remise, de bout en bout | `python -m bench.deals_truth` | 1er mois : rappel 89 %, précision 81 % · ensuite : 98 %, 90 % |
| Alternatives, contre une grille indépendante | `python -m bench.alternatives` | 0 % de suggestions incompatibles · alternative moins chère montrée pour 95 % (démo) et 100 % (3 000 produits) des fiches qui en ont une |
| Missions en une phrase | `python -m bench.missions` | 37/37 phrases comprises (dont 12 tournures du quotidien, voir `docs/UX.md`) |
| Tenue en charge (3 000 produits) | `python -m bench.scale` | publication ~2,8 s par nuit (courbes de 90 jours comprises) · missions de la nuit : 10 000 en ~5,5 s · lectures de l'app ~2 ms (recherche ~7 ms, missions d'une personne ~10 ms) |

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
- **Une règle d'alternative** (un critère d'usage, une famille) : l'attribut dans `extract/categories.py`, la règle dans
  `alternatives.py` (pur), un cas dans `tests/test_alternatives.py`, la mesure `python -m bench.alternatives`.
- **Un mot ou une tournure pour les missions** : `SLANG` ou `PRICE_RE` dans `missions.py`, la phrase dans
  `bench/missions.py` avec ce qu'elle doit donner, un cas dans `tests/test_missions.py`.
- **Un écran de l'app** : une lecture dans `catalog.py`, une route dans `api.py`. Si elle demande un calcul, il va dans
  `publish.py`, jamais dans la requête. Interface : `web/src/App.jsx`, reconstruite par `web/build.sh` (principe et
  mesures : `docs/UX.md`). Une donnée n'est ajoutée que si un écran la montre.
