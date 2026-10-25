# Architecture de DEALS

DEALS montre chaque jour les bonnes affaires qui existent. Le marché est relu une fois par nuit ; tout le reste en
découle. L'architecture suit cette réalité : **une chaîne de nuit qui calcule, une app de jour qui lit**.

```
                    NUIT (deals.py nightly → night.py, une fois par jour)                   JOUR (deals.py serve)

 sites des enseignes ─► fetch ─► extract ─► market ─────► publish ─► catalog ◄── catalog ◄── api ◄── web ◄── app (v56)
                        politesse  page HTML   produits,    deals,     tables       lectures    routes  HTTP
                        robots.txt → offre     offres,      fausses    publiées     indexées    /api/r/ statique
                        blocages   (pur)       prix         remises,   (une seule
                                               (écrit)      moins cher transaction,             accounts, activity,
                                                            comparable  garde)                  missions, profile,
                                                            (purs)        │                     query (phrase comprise)
                                       agent : relance, mise de côté,     ▼                     (comptes invités, e-mail,
                                       page témoin, quarantaine ─►  missions ─► e-mails         favoris, marques, clics,
                                                                                                recherches, goûts)
                                       (sources, quarantine)        prix atteints : un par personne
                                                │
                       health : contrôles ─► agent : incidents, conseils, propositions ─► rapport, e-mail au responsable
                       ops : journal (events), corrélation de la nuit                      deals.py status | approve | …
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
   qui écrit le catalogue ; `accounts`, `activity`, `missions` et `profile` les seuls qui écrivent les données des
   personnes. Une exception, écrite : quand une adresse rejoint un compte qui existe déjà, `accounts` y rattache, en une
   transaction, les lignes du compte invité (favoris, marques, rayons, missions, sessions, fiches vues, clics) ; quand
   un compte est effacé, il anonymise ses fiches vues et ses clics. Aucun module ne lit les tables d'un autre en dehors
   de ce qui est listé plus bas.
4. **Concurrence sans verrou applicatif.** SQLite en mode WAL : les lectures ne bloquent jamais ; chaque fil a sa
   connexion ; chaque écriture est une transaction courte (une page relue, une action d'une personne, une
   publication). Le serveur et la passe de nuit partagent le fichier sans se gêner.
5. **Ne jamais enregistrer une donnée fausse.** Une donnée manquée coûte un deal ; une donnée fausse coûte la confiance.
   Les garde-fous sont dans le code qui lit (`extract`) et dans la règle qui juge (`judge`), pas dans des correctifs.
6. **Échouer tôt, avec la cause.** Réglage invalide, robot sans nom ni contact, base d'un autre schéma : arrêt au
   démarrage avec un message qui nomme le problème, plutôt qu'un service qui tourne mal.
7. **Pas de fonction sans usage.** Ce que le produit ne montre pas n'est ni calculé, ni stocké, ni testé. Le journal
   d'exploitation (événements, incidents, actions) est lu : par l'agent la nuit, par le responsable (`status`, e-mail du
   matin, `approve`), par la sonde extérieure.
8. **Agir seul seulement quand c'est sans risque.** L'agent relance, met de côté, retient, garde le catalogue de la
   veille ; ce qui engage attend une décision humaine ; contourner une protection est interdit. Chaque action est
   journalisée avec sa justification, sa vérification et son retour arrière (`docs/AUTONOMIE.md`).

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
| `deals/affiliate.py` | **pur** : enseignes partenaires (fichier `DEALS_AFFILIATE`) et lien affilié d'un clic (gabarit du réseau avec `{url}` et `{subid}`, ou paramètres ajoutés à la fiche) | — | — |
| `deals/publish.py` | calcule le catalogue du jour (meilleure offre, deal, depuis quand et jusqu'à quand, courbe de 90 jours, alternatives moins chères, similaires, verdict de prix de chaque produit) et l'écrit d'un bloc ; seules les offres des enseignes partenaires | store, judge, alternatives, extract, catalog (recherche) | catalog, catalog_offers, alternatives, similar, meta |
| `deals/query.py` | **pur** : une phrase → des critères (`read` : rayon, pièce, marque, fonctions, tailles, budget, promo, prix bas, tri, mots qui restent, rayon non suivi), les critères en puces (`chips`), un produit a-t-il ce qui est demandé (`fits`, `fitter`, `satisfies`) — la Recherche et les missions comprennent ainsi les mêmes phrases | extract, labels, alternatives (classes énergie) | — |
| `deals/labels.py` | libellés : catégories (pluriel, singulier), fonctions, pièces et leurs rayons | — | — |
| `deals/catalog.py` | lectures de l'app (deals du jour, recherche dans tout le catalogue — une phrase comprise, des critères choisis, les mots qui restent, les plus proches au-dessus du budget, Affiner et ce que donnerait chaque choix (`_options`) — et son feed, catégories et marques — toutes, ou celles qui ont des remises —, pages d'une marque et d'une catégorie avec tous leurs produits, fiche et ses alternatives, favoris) ; **pur** : où se situe le prix du jour sur les derniers mois (`position`), l'ordre du feed (`lead`, `breadth`), le prix bas (`cheap`) ; top deals de l'accueil, « pour vous » (`foryou`) et ce que l'app a compris (`taste`), dans l'ordre du profil de la lecture ; libellés | store, extract (familles), profile | — |
| `deals/profile.py` | goûts d'une personne : rayons et marques pesés par ce qu'elle choisit et regarde (`build`), l'ordre qui en découle sans faire oublier l'intérêt du deal (`arrange`, `diversify`, `blend`, `mine`) et les témoins (`control`), **purs** ; le profil d'une lecture (compte : ses tables ; sans compte : ce que le navigateur envoie, rien n'est gardé) ; les gestes (rayons choisis, apprentissage, remise à zéro) | store, extract (familles), catalog (noms des rayons) | interests, prefs |
| `deals/missions.py` | les recherches sauvegardées et les alertes de prix ; **pur** : une phrase → une mission (`interpret`, par `query.read`), ce qui rend un produit comparable (`like`), un produit remplit-il une mission (`matches`, `matcher` : préparé une fois par mission) ; les missions d'une personne (sauvegarder — prix facultatif —, une par cible, lister avec ce qui y répond et ce qui est nouveau depuis qu'elle l'a ouverte, `seen`, la cloche de l'e-mail, arrêter ; vérifier celle qui attend une connexion) ; la nuit, un e-mail par personne qui a une adresse et la cloche allumée (`notify`), chaque produit à un clic de l'offre | store, catalog, query, extract, accounts (envoi) | missions |
| `deals/accounts.py` | comptes invités (au premier geste qui garde : cookie d'un an, renouvelé ; limite par adresse IP ; effacés la nuit quand plus personne ne peut les ouvrir), connexion par lien magique (rattache l'adresse au compte invité, ou y verse ce qu'il garde ; la mission lancée avant la connexion attend avec le lien), sessions, effacer un compte, limites d'envoi, SMTP (liens de connexion, e-mails de missions) | store, config | users, login_links, sessions (et, à la fusion et à l'effacement, voir le principe 3) |
| `deals/activity.py` | favoris, marques suivies, fiches vues, clics sortants par le lien affilié, mesures de conversion (taux de clic par écran, par personne, par variante — personnalisé ou témoin —, part partenaire, missions) | store, affiliate | saves, follows, views, clicks |
| `deals/api.py` | contrat `/api/r/` (routes ajoutées) ; garder sans compte crée le compte invité (`_keep`), un geste qui échoue l'oublie | catalog, accounts, activity, missions, profile | — |
| `deals/web.py` | serveur HTTP : app statique, routes, cookie, taille des requêtes, en-têtes | api | — |
| `deals/ops.py` | journal opérationnel : événements datés (UTC), gravité, composant, entité, corrélation de la nuit ; JSON sur la sortie d'erreur ; jamais d'adresse ni de secret (`scrub`) | store | events |
| `deals/sources.py` | registre des sources (enseignes lues, partenaires ou non) et leur état : active, en difficulté (nuits ratées), mise de côté | store | sources |
| `deals/quarantine.py` | prix suspects : à moins de 30 % du prix habituel, retenus jusqu'au retour à la normale (le prix faux écarté) ou relus au même prix deux nuits de plus (cru) | store | quarantine, prices.rejected |
| `deals/health.py` | contrôles de santé de la nuit : `snapshot` lit l'état, `findings` (**pur**) en tire les constats d'après des seuils versionnés ; `cause` dit pourquoi une source va mal | store, sources | — |
| `deals/agent.py` | l'agent opérateur : politiques (auto, alert, approval, recommend, forbidden), actions auditées et idempotentes, incidents, conseils, propositions, e-mail au responsable ; gestes humains (`approve`, `reject`, gestes manuels) | health, sources, quarantine, ops | incidents, actions |
| `deals/night.py` | la nuit de bout en bout : sources, collecte, agent, publication (garde), missions (garde contre l'envoi massif), comptes invités expirés, contrôles, incidents, rapport, e-mail ; une étape qui casse n'arrête pas les suivantes | tout ce qui précède | runs (bilan complet) |
| `deals/sim.py`, `deals/demo.py` | marché simulé à vérité connue (une source par enseigne simulée) ; démo par la vraie nuit | collect, market, night | — |
| `deals/cli.py` (`deals.py`) | une seule ligne de commande ; centre de commande (`status`, `incidents`, `actions`, `events`, `approve`, `reject`, `sources`, `quarantine`, `partners`) | tout | — |

Lectures croisées autorisées, et seulement celles-ci : `publish` lit `products/offers/prices` (pour calculer) ;
`collect` lit `catalog/saves/clicks` (pour ordonner la relecture de nuit : deal en cours, favori, clic récent) ;
`activity` lit `offers` (pour rediriger un clic vers l'adresse connue) et `catalog` (prix au moment d'un favori) ;
`catalog` lit `follows/saves` (pour personnaliser l'ordre, les signets et la baisse d'un favori) ; `profile` lit
`catalog` (rayons et marques publiés : reconnaître une recherche, valider un rayon choisi), `products` (rayon et marque
d'une fiche vue) et, pour un compte, `saves/follows/views/clicks/missions` (ses signaux) ; `missions` lit
`catalog/catalog_offers` (produits publiés, disponibilité de la meilleure offre) et `users` (l'adresse où écrire, la
nuit). Exploitation : `health` lit `runs`, `sources`, `quarantine`, `catalog`, `catalog_offers`, `offers`, `prices`
et `clicks` (l'état de la nuit) ; `quarantine` lit `offers`, `prices` et `catalog` (prix habituel) ; `publish` et
`collect` lisent `quarantine` (pas de publication, relecture en priorité) et `publish` lit `sources` (la garde ignore
les sources mises de côté) ; l'agent écrit `sources` et `quarantine` par leurs modules, `incidents` et `actions` lui-même.

## Données

```
products   (id, gtin unique, brand, mpn, title, norm_title, category, attributes, image, needs_review)
offers     (id, url unique, host, retailer, merchant, product_id, category_hint, status, note, protection, etag,
            last_modified, pending_price, fails, checked_at)                status : new | active | gone | blocked
                                                                             | disallowed | out_of_scope
prices     (offer_id, first_seen, last_seen, price, was, availability, seller, valid_until, lowest_30d, source,
            was_source)                                    une ligne par CHANGEMENT ; last_seen avance sinon
catalog    (product_id, name, title, brand, category, price, was, pct, merchant, offer_id, verified, search, published_on,
            since, ends, history, attrs,  depuis quand la remise court, fin déclarée par l'enseigne, meilleur prix de
            level, span, usual)          chaque jour sur 90 jours (verdict de prix de la fiche), attributs lus (missions),
                                         verdict de prix publié : niveau, jours relevés, prix habituel (top deals, Promo)
meta       (key, value)                  heure de la dernière publication (« MAJ » du bandeau), écrite avec le catalogue
catalog_offers (product_id, offer_id, merchant, price, was, pct, availability, rank)
alternatives (product_id, other_id, rank)       comparables, disponibles, au moins 10 % moins chers (fiche)
similar    (product_id, other_id, rank)         les autres comparables, au prix le plus proche (fiche, à défaut)
users (email : NULL pour un compte invité), login_links (guest_id : l'invité qui a demandé le lien), sessions
                                      (jetons stockés en SHA-256 ; un compte invité : un an après le dernier geste qui garde)
follows (user_id, brand) · saves (user_id, product_id, price)
interests  (user_id, category, created_at)    rayons choisis par un compte (l'ordre du choix)
prefs      (user_id, learn, reset_at)         apprendre des fiches ouvertes et des clics (0 pour un compte invité
                                              tant qu'il ne le demande pas) ; ce qui précède reset_at est oublié pour
                                              l'ordre (gardé pour les mesures)
clicks     (id, at, day, user_id, product_id, offer_id, merchant, source, partner, mission_id, variant)
            id : l'identifiant transmis au réseau d'affiliation (sous-ID) ; partner : parti chez un partenaire ;
            mission_id : la mission d'où vient le clic (carte de mission, e-mail) ; variant : p (ordre personnalisé)
            ou t (témoin)
views      (at, day, user_id, product_id, source, mission_id, variant)    fiches ouvertes : le taux de clic de chaque
            écran, par variante
login_links.mission                    la mission lancée avant la connexion, lancée à l'ouverture du lien
missions   (id, user_id, product_id, category, brand, want, max_price, label, created_at, notified, alert, seen,
            opened_at)    une recherche sauvegardée ou une alerte : ce qui est guetté (un produit, ou catégorie, marque
            et, dans want, fonctions, tailles, mots, pièce, promo, prix bas, prix minimum), le prix maximum (facultatif) ;
            notified : produit → prix du dernier e-mail (rien n'est renvoyé au même prix) ; seen : produit → prix
            quand la personne l'a ouverte (ce qui est nouveau) ; alert : l'e-mail de la nuit (il faut une adresse)
site_rules (host, rules) · runs (day, started, ended, stats, cid, status)
            status : running | succeeded | partial_success | failed | retry (relance d'une enseigne par l'agent) ;
            stats : le bilan complet de la nuit (passe, publication, missions, offres publiées par source) : la
            référence des nuits suivantes
prices.rejected                        erreur de prix écartée (quarantaine) : hors courbes et verdicts
sources    (key, kind, name, partner, status, failures, last_success, last_run, reason, updated_at)
            status : active | degraded | disabled ; failures : nuits ratées de suite ; reason : qui l'a mise de côté
events     (at, severity, component, kind, entity, cid, payload)       journal opérationnel, sans adresse ni secret
incidents  (kind, entity, severity, status, opened_at, last_seen, resolved_at, nights, evidence, runbook, cid, escalated)
actions    (at, actor, action, entity, incident_id, policy, status, justification, inputs, preconditions,
            expected_effect, idempotency_key unique, result, verification, rollback_plan, decided_by, decided_at, cid,
            notified)        status : verified | failed | proposed | recommended | refused | executed | rejected | expired
quarantine (offer_id, since, price, usual, rule, confirmed, checked_day, status, released_at, reason, price_id)
```
Le schéma vit dans `store.py` et nulle part ailleurs : `SCHEMA` (version 1) puis `MIGRATIONS`, dans l'ordre, en une
transaction. Une base neuve suit exactement le même chemin qu'une base existante : chaque migration est exécutée par
chaque test. `PRAGMA user_version` date la base ; un code plus ancien que la base refuse de démarrer. Une évolution du
schéma = `SCHEMA_VERSION + 1` et une entrée dans `MIGRATIONS` (version 2 : durées de la fiche, prix des favoris ;
version 3 : alternatives ; version 4 : description de la fiche ; version 5 : courbe de prix, heure de publication ;
version 6 : missions ; version 7 : la description retirée, `ALTER TABLE … DROP COLUMN`, d'où SQLite 3.35 au moins,
vérifié au démarrage ; version 8 : affiliation, fiches vues ; version 9 : verdict de prix publié ; version 10 :
exploitation autonome — sources, journal, incidents, actions, quarantaine ; version 11 : goûts — rayons choisis,
apprentissage, variante des fiches vues et des clics ; version 12 : comptes sans e-mail, missions sans prix, cloche
et nouveautés — deux tables recopiées, d'où les clés étrangères suspendues le temps de la migration, puis vérifiées
(`PRAGMA foreign_key_check` : une référence cassée annule tout, la base reste dans sa version).

## La nuit (`python deals.py nightly`, `deals/night.py`)

0. **Sources** : le registre suit les enseignes partenaires ; une source mise de côté n'est pas lue (page témoin tous
   les 3 jours).
1. **Plan** : toutes les offres suivies des sources lisibles (les fiches disparues sont revérifiées une nuit sur
   sept). Par site, ordre de valeur : prix en quarantaine, produit en deal, en favori, cliqué depuis 3 jours, puis le
   plus ancien relu.
2. **Collecte** : un fil par site, à son rythme poli (5 s ou le Crawl-delay du site) ; coupe-circuit après 5 refus de
   suite ; arrêt au budget de nuit (ce qui n'est pas relu garde son prix, qui vieillit : au-delà de 3 jours il n'est
   plus montré). Chaque page : `fetch` → `extract` → décision → `market` dans une transaction courte.
3. **Confirmation** : une variation de prix énorme (÷2, ×2) est relue une fois avant d'être enregistrée.
4. **Agent** : une source en panne passagère est relancée une fois et vérifiée ; les nuits ratées sont comptées, une
   source qui en accumule 3 est mise de côté (jamais de contournement d'un anti-robot) ; les prix suspects sont mis en
   quarantaine, confirmés ou libérés.
5. **Publication** : `publish` lit le marché, juge chaque produit avec `judge`, choisit avec `alternatives` ce qui le
   remplace pour moins cher, réécrit le catalogue en une transaction (l'app passe d'un catalogue complet au suivant,
   jamais un état intermédiaire). Sans les offres en quarantaine ni les prix écartés ; garde : un catalogue qui perdrait
   plus de 20 % de ses produits ou de ses offres n'est pas écrit (au plus deux nuits).
6. **Missions** : `missions.notify` relit les missions sur le catalogue publié (chaque catégorie lue une fois, du moins
   cher au plus cher : une mission ne détaille que les produits sous son prix) ; un e-mail par personne avec ce qui est
   nouveau à son prix ; un envoi qui échoue, ou qui dépasserait le plafond de la nuit, ne marque rien : il repart la
   nuit suivante ; un envoi bien plus nombreux que d'habitude attend une décision. Le jour, l'état des missions se lit
   sur le même catalogue (produits lus gardés jusqu'à la publication suivante).
7. **Contrôles et incidents** : `health` relève les constats (sources, prix suspects, budget, garde, taille et
   fraîcheur du catalogue, e-mails, clics, étapes en erreur) ; l'agent ouvre, suit ou résout les incidents et joint ses
   conseils ou propositions.
8. **Rapport du matin** (réussite par enseigne, passe interrompue, prix barré perdu à prix inchangé, plus fortes
   baisses, section « Agent ») et **e-mail au responsable** s'il y a lieu.

## Les règles du produit (où elles vivent)

| Règle | Où |
|---|---|
| Lire un prix sans se tromper (prix membre, financement, produit voisin, page liste…) | `extract/offer.py` |
| Catalogue : familles suivies, accessoires écartés, seuil de 100 € | `collect/retailers.py`, `extract/categories.py` |
| Alternative : même catégorie ; même usage (taille de literie, largeur, places, forme : balai, traîneau, encastrable, d'angle, américain) ; au moins les mêmes fonctions (sans fil, laveur, convertible, induction, électrique) ; pas moins bien (énergie, capacité, couverts, foyers, volume, autonomie, bruit) ; moins chère = au moins 10 % de moins et disponible ; la plus forte économie d'abord, une marque par ligne | `alternatives.py` |
| Comprendre une phrase : rayon (ou pièce si aucun rayon), marque, fonctions, tailles (seulement dans les rayons où elles ont un sens), budget maximum, de… à…, minimum, remise (≤ 90 %), prix bas, « pas cher » ; les mots vides ignorés, les autres cherchés ; rien n'est deviné ; une recherche faite de puces se relit à l'identique | `query.py` (`read`, `chips`), `tests/test_query.py` |
| Recherche : tout le catalogue suivi ; la phrase comprise et les critères choisis dans l'app (qui l'emportent) ; les mots qui restent filtrent s'ils trouvent, sinon ils sont dits ; rien sous le budget : les plus proches au-dessus ; Affiner : chaque choix compte ce qu'il donnerait, ses autres critères gardés, et n'est proposé que s'il donne et change quelque chose (ou s'il est pris) ; pertinence = les mots nomment le produit, puis les remises, puis le prix ; ou prix croissant, ou remise ; sans mot ni filtre, le feed : les produits des 4 dernières recherches (gardées par le navigateur) d'abord, 6 au plus chacune, puis ceux de vos rayons et de vos marques (un sur quatre pris ailleurs), puis tout le catalogue, une catégorie à tour de rôle | `catalog.py` (`search`, `_options`, `lead`, `breadth`), `profile.py` (`blend`) ; `docs/RECHERCHE.md` |
| Marque, catégorie : tous leurs produits, les remises d'abord (depuis une fiche, jamais de cul-de-sac) | `catalog.py` |
| Top deals (accueil, en premier) : les plus fortes remises réelles et les prix bas, à tour de rôle, dix au plus, dans l'ordre du profil (trois au plus d'un même rayon) ; prix bas = au plus bas, ou moins cher que 2 jours sur 3, depuis au moins 60 jours relevés et au moins 10 % sous le prix habituel (médiane) ; « pour vous » et notre sélection ne les répètent pas | `catalog.py` (`top`, `cheap`), `web/src/App.jsx` |
| Goûts : choisi = affinité 1 (rayons choisis, marques suivies, rayon et marque d'une mission) ; vu = favori 2 points, clic 1,5, recherche qui nomme un rayon ou une marque 1, fiche ouverte 0,5, moitié moins tous les 30 jours, 90 jours au plus ; confiance pleine à 2 points ; rayon vu ≤ 0,8, marque vue ≤ 0,4 (à partir d'un point), famille 30 % ; « pour vous » = affinité directe ≥ 0,3 ; sans compte, rien n'est gardé par le serveur ; une personne sur dix est témoin | `profile.py` (`build`, `mine`, `control`, `Profiles`) ; `docs/PERSONNALISATION.md` |
| Filtre Promo : en promo, −10 % à −50 % et plus, ou prix bas ; le nombre de produits de chaque choix, avant ce filtre | `catalog.py` (`search`) |
| Mission (recherche sauvegardée, alerte) : ce qui est dit est exigé (catégorie ou pièce, marque, fonctions, mots, promo, prix bas, prix minimum ; capacité, couverts, foyers, places, volume, autonomie au moins ; taille de literie exacte ; largeur à 6 % près ; bruit au plus ; classe énergie au moins), ce qui ne l'est pas ne l'est pas ; disponible et au prix voulu (s'il y en a un) ; caractéristique inconnue du produit = pas de promesse ; comparable = même catégorie, mêmes fonctions, même taille ou capacité ; une mission par cible, 20 par personne ; nouveau = arrivé, ou moins cher d'au moins 0,50 €, depuis qu'on l'a ouverte | `missions.py`, `query.py` |
| E-mail de mission : un par personne et par nuit, seulement pour qui a une adresse et la cloche allumée, seulement le nouveau (jamais deux fois le même produit au même prix, rien de ce qui était visible en sauvegardant ni dans l'app avant l'adresse), les cinq moins chers par mission, plafond par nuit (`DEALS_MISSION_MAILS`) | `missions.py` |
| Une remise est réelle sauf preuve du contraire ; preuve = historique hors promotion (≥ 14 jours) ou mention légale « plus bas 30 jours » ; prix barré permanent (≥ 60 jours) = pas un deal | `judge.py` |
| Interface : un Accueil éditorial (pièces, marques en promo, sélection) et une Recherche (un champ, trois filtres, un tri, un feed que la saisie adapte) ; flux de cartes (visuel, remise, marque, nom, prix) ; durées et verdict de prix seulement dans la fiche ; la qualité est implicite | `web/src/App.jsx`, illustrations `web/src/art.jsx` |
| Prix sur 90 jours : meilleur prix disponible de chaque jour, toutes enseignes, calculé à la publication | `publish.py` (`chart`) |
| Verdict de prix : au plus bas (aucun jour moins cher, plus cher un jour sur deux au moins), parmi les plus bas (moins cher que 2 jours sur 3), plus cher que d'habitude (plus cher que 2 jours sur 3), habituel sinon ; 14 jours relevés au moins ; le point de la jauge = rang du jour | `catalog.py` (`position`) |
| Fiche : une seule enseigne, la moins chère disponible ; ni description technique ni autres enseignes | `publish.py` (meilleure offre), `web/src/App.jsx` |
| Classement : l'intérêt du deal × (1 + ½ affinité), au plus × 1,5 ; une place sur quatre au meilleur deal restant ; au plus deux d'un même rayon sur quatre de suite ; sans goûts connus ou pour un témoin : remise, × 1,5 pour une marque suivie (l'ordre d'avant) ; une recherche ou un filtre : sans les goûts | `profile.py` (`arrange`, `diversify`), `catalog.py` |
| Clic sortant : seulement vers l'adresse d'une offre connue, tracé ; part par le lien affilié de l'enseigne avec l'identifiant du clic | `activity.py`, `affiliate.py` |
| Affiliation : seules les offres des enseignes partenaires sont lues la nuit et publiées ; sans fichier de partenaires (développement), tout est publié et les liens partent tels quels | `affiliate.py`, `publish.py`, `cli.py` |
| Mesure de conversion : fiches vues → clics vers l'enseigne (taux de clic), par écran (source), par personne (avec mission, connectée sans mission, sans compte) et par variante (personnalisé ou témoin, par écran) ; part des clics partis chez un partenaire ; clics venus des missions (app, e-mail) | `activity.py` (`metrics`) |
| Transparence : « enseigne partenaire » près de l'offre, page « Comment ça marche » (référencement, classement, rémunération) depuis chaque écran ; mention dans les e-mails | `web/src/App.jsx`, `missions.py` |
| Sans e-mail : un compte invité au premier geste qui garde (cookie d'un an, renouvelé ; 100 par adresse IP et par heure ; un geste qui échoue ne laisse rien ; effacé la nuit quand plus personne ne peut l'ouvrir) ; l'adresse se rattache au compte invité ou y verse ce qu'il garde, sans doublon ; effacer un compte anonymise ses mesures. Connexion : lien à usage unique 15 min ; 5 liens par adresse et par heure, 20 par adresse IP, plafond quotidien global | `accounts.py`, `api.py` (`_keep`), `night.py` |
| Exploitation : qui décide quoi (auto, alert, approval, recommend, forbidden) ; source mise de côté après 3 nuits ratées, page témoin tous les 3 jours ; quarantaine q1 ; garde de publication ; envoi massif ; e-mail au responsable seulement s'il y a lieu | `agent.py`, `sources.py`, `quarantine.py`, `publish.py`, `health.py` ; `docs/AUTONOMIE.md` |
| Interface v56 : la phrase en puces, Affiner, Sauvegarder (« Sauvegardée »), vos recherches sauvegardées et récentes dans la Recherche, le Profil centre de commande (recherches, alertes, favoris, marques, rayons, ce que l'app a compris, e-mail facultatif, effacer) ; mission atteinte : « Voir l'offre » en un geste ; trois onglets | `web/src/App.jsx`, `docs/UX.md` |

## Vérifier

| Quoi | Commande | Mesure actuelle |
|---|---|---|
| Contrats (161 tests, ~31 s) | `python -m unittest discover -s tests -t .` | tout passe, Python 3.11 à 3.13 ; 104 mutations des règles v56 (lecture d'une phrase, Affiner, missions, comptes invités, API, profil, migration, nuit) : toutes détectées |
| Pannes injectées (6 scénarios × 6 nuits) | `python -m bench.autonomy` | anti-robot : mis de côté nuit 3, jamais forcé · panne passagère relancée, 100 % relu · erreur de prix ni publiée ni envoyée · catalogue qui fond retenu 2 nuits · 8 e-mails au responsable en 36 nuits (voir `docs/AUTONOMIE.md`) |
| Extraction | `python -m bench.extraction` | 1 036/1 040 prix réels · 36/36 JSON-LD · 66/66 robots.txt · 26/26 + 8/8 pages-pièges |
| Vraie / fausse remise, de bout en bout | `python -m bench.deals_truth` | 1er mois : rappel 89 %, précision 81 % · ensuite : 98 %, 90 % |
| Alternatives, contre une grille indépendante | `python -m bench.alternatives` | 0 % de suggestions incompatibles · alternative moins chère montrée pour 95 % (démo) et 100 % (3 000 produits) des fiches qui en ont une |
| Missions en une phrase | `python -m bench.missions` | 37/37 phrases comprises (dont 12 tournures du quotidien, voir `docs/UX.md`) |
| Recherche : trouve-t-on ce qu'on tape ? | `python -m bench.search [--scale]` | 41 phrases : 0 impasse (15 en v55), première carte juste 24/24 (démo) et 19/19 (3 000 produits) ; voir `docs/RECHERCHE.md` |
| Tenue en charge (3 000 produits) | `python -m bench.scale` | publication ~2,9 s par nuit (courbes de 90 jours comprises) · missions de la nuit : 10 000 en ~5,9 s, ~1,5 s sans changement (1,8 s en v55 : chaque mission prépare sa règle une fois) · lectures de l'app ~2,5 ms (deals du jour) ; une phrase comprise ~11 à 14 ms (Affiner compris ; ~10 ms en v55, sans Affiner), critères choisis ~13 ms, une pièce ~16 ms ; feed ~16 ms, ~21 à 26 ms orienté par des fiches ouvertes ou quatre recherches ; top deals et « pour vous » 9 à 11 ms ; missions d'un compte ~14 ms, d'un invité avec trois recherches ~8 ms |
| Personnalisation, sur des personnes simulées | `python -m bench.profiles [--scale]` | nouvelle visite : l'ordre d'avant · accueil, cartes des rayons de la personne : 19 à 22 % → 43 à 60 % (3 000 produits) ; clics attendus × 1,5 à × 2,1 ; remise moyenne montrée 29,6 % → 28,7 à 29,1 % (voir `docs/PERSONNALISATION.md`) |

## Ce qui a été retiré, et pourquoi

Le moteur de « veille de marché » des générations précédentes : événements, signaux, surveillances, webhooks, flux
temps réel, console interne, planification par offre toutes les 15 minutes, flux marchands, motifs saisonniers. Le
produit n'en lit rien ; tout était calculé, stocké et testé quand même (voir `docs/AUDIT.md`). Le journal
d'exploitation de la v54 (événements, incidents, actions) n'est pas ce moteur : il ne sert qu'à faire tourner la nuit
sans surveillance, et chaque ligne a un lecteur (l'agent, le responsable, la sonde extérieure). Si un jour un flux
marchand devient une source, il s'ajoute comme une source de `collect/` qui produit des offres pour `market`, sans
toucher au reste.

## Ajouter quelque chose sans rien casser

- **Une enseigne** : une entrée dans `collect/retailers.py`, puis `deals.py diagnose <enseigne>`.
- **Un format de page** : un cas dans `tests/pages.py`, puis la règle dans `extract/offer.py` ; `python -m bench.extraction`.
- **Une règle de deal** : `judge.py` (pur), un cas dans `tests/test_judge.py`, la mesure `python -m bench.deals_truth`.
- **Une règle d'alternative** (un critère d'usage, une famille) : l'attribut dans `extract/categories.py`, la règle dans
  `alternatives.py` (pur), un cas dans `tests/test_alternatives.py`, la mesure `python -m bench.alternatives`.
- **Un mot ou une tournure** (Recherche et missions) : `SLANG`, `STOP` ou les expressions de prix dans `query.py`, la
  phrase dans `bench/missions.py` (ou `bench/search.py`) avec ce qu'elle doit donner, un cas dans `tests/test_query.py`.
- **Un écran de l'app** : une lecture dans `catalog.py`, une route dans `api.py`. Si elle demande un calcul, il va dans
  `publish.py`, jamais dans la requête. Interface : `web/src/App.jsx`, reconstruite par `web/build.sh` (principe et
  mesures : `docs/UX.md`). Une donnée n'est ajoutée que si un écran la montre.
