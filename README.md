# DEALS — les bons deals du jour, au même endroit

On ouvre l'app pour savoir quelles bonnes affaires existent aujourd'hui. Un deal est un deal : le même pour tout le monde,
sans onboarding. L'entrée est le produit ; la marque et la catégorie sont des entrées secondaires ; l'enseigne n'est qu'un
attribut de l'offre. Simple, sans friction : on lit sans compte ; un e-mail suffit pour garder des favoris et suivre des marques.

Trois familles chères, où une remise compte : **électroménager, ameublement, literie**. Une collecte par jour, sans
affiliation, aucune IA, un seul petit serveur (Python, bibliothèque standard, SQLite) : environ 6 € HT par mois.

| Couche | Fichiers | Rôle |
|---|---|---|
| Marché | `listener/`, `collect/` | collecte quotidienne polie, extraction, rapprochement produit / offre (EAN d'abord), historique des prix |
| Extraction | `listener/fetch.py`, `listener/structured.py`, `listener/extract.py`, `listener/vendor/protego/` | robots.txt RFC 9309, blocages reconnus, données structurées réparées, prix barré, garde-fous |
| Moteur quotidien | `radar/engine.py`, `radar/verify.py` | signaux de marché, **fausses remises détectées** (prix barré gonflé), similarité hebdomadaire, plan de collecte |
| Produit | `radar/shop.py`, `radar/search.py` | deals du jour, catégories, marques, fiche, favoris, marques suivies, clics sortants |
| Comptes | `radar/accounts.py` | lien magique par e-mail, session 90 jours, SMTP |
| App | `web/src/App.jsx` → `web/app.html` | une page, design de la maquette v41 |
| Serveur | `app.py`, `listener/server.py`, `radar/api.py` | API publique `/api/r/` ; console et API marché seulement en mode admin |

## Règles du produit (dans le code)
- **Seulement des remises réelles** : prix barré au-dessus du prix, et jamais une fausse remise (prix barré nettement au-dessus du
  prix habituel). Une fiche reste consultable, sans remise affichée.
- **Classement** : remise en %, × 1,5 si la marque est suivie par la personne connectée. Rien d'autre.
- **Produits similaires** : similarité calculée chaque semaine sur les caractéristiques (même catégorie) ; repli : même catégorie, prix le plus proche.
- **Recherche** : insensible aux accents et à la casse, avec synonymes du langage courant (frigo, télé, ordi…).
- **Connexion demandée au moment de l'action** (favori, suivre), jamais à l'entrée. Lien à usage unique valable 15 min ;
  5 demandes par adresse et par heure ; même réponse qu'un compte existe ou non ; seuls les hachages des jetons sont stockés.
- **Clics sortants** : `out/<offer_id>` trace le clic (avec ou sans compte, sans cookie pour l'anonyme) et ne redirige que vers
  une URL d'offre connue. C'est la mesure du produit (`/api/admin/metrics`, `python cli.py metrics`).
- **Fraîcheur** : toutes les offres sont relues chaque jour tant que la passe tient dans la nuit (`DEALS_NIGHT_BUDGET_S`, 4 h).
  Au-delà, mode adaptatif : deal en cours, bon prix récent, favori, clic récent, produit volatil → chaque jour ;
  marque suivie → tous les 3 jours ; le reste → chaque semaine.

## Commandes
```
python app.py demo                       app sur http://127.0.0.1:8000/ avec un marché simulé (console /admin incluse)
python app.py serve [--db deals.sqlite]  app publique : seules l'app et /api/r/ sont exposées
python app.py serve --admin              + console /admin et API marché (outil interne, à ne pas publier)
python cli.py daily                      tâche de nuit : plan de collecte → collecte → similarités (hebdo) → signaux
python cli.py metrics                    clics sortants, comptes, deals du jour, fausses remises écartées
python collect.py discover|diagnose|sample|explain|build|rules|review|estimate   constituer et régler la base
python -m unittest discover -s tests -t .                         tests
python -m bench.extraction                                        mesure de l'extraction (corpus publics, pages-pièges, temps CPU)
ESBUILD=<esbuild> REACT_DIR=<node_modules> ./web/build.sh          reconstruire web/app.html (build seulement)
```

## API publique `/api/r/`
Lecture ouverte : `today?category=&q=`, `categories`, `brands`, `brand/<nom>`, `item/<id>`, `out/<offer_id>?from=`.
Session requise (sinon 401) : `save`, `saves`, `brand/follow`, `follows`.
Comptes : `auth/request` {email}, `auth/verify?token=` (pose le cookie, ou renvoie vers `/?auth=expired`), `auth/me`, `auth/logout`.

## Exploitation
Voir `deploy/` : service systemd, tâche de nuit, sauvegarde quotidienne de la base, variables d'environnement (`deploy/deals.env.example`).

## Mesures
- Politique de collecte (`python -m bench.refresh_policy`, un an simulé, 2 tirages) : le mode adaptatif fait −58 % de requêtes
  mais rate 13 à 17 % des bonnes affaires hors centres d'intérêt (2,7 j de retard). D'où la relecture complète par défaut.
- Transactions (`python -m bench.transactions`, 30 nuits) : une transaction par nuit, −33 % de temps.

## Archives
Les générations précédentes (Decision OS, déménagement, vitrine, surveillance de prix) sont dans `deals-archive-legacy.zip`.

## Extraction : ne jamais enregistrer une donnée fausse

Une donnée manquée coûte une bonne affaire ; une donnée fausse (prix membre pris pour le prix public, prix d'un produit
voisin, fiche devenue page liste) coûte la confiance. L'extraction lit dans l'ordre : JSON-LD, règles de site,
microdonnées, balises meta, état applicatif embarqué (seulement si l'identité du produit concorde). Le prix barré peut
aussi venir du bloc de prix HTML, mais seulement à côté du prix trouvé par une source structurée, dans le même bloc.

Ce qui a été repris de l'existant (licences BSD-3, voir `THIRD_PARTY_NOTICES.md`) : **Protego** (Scrapy) pour robots.txt,
la chaîne de réparation JSON-LD d'**extruct** (Zyte), et les corpus de test d'extruct, de price-parser et de Protego.
Consultés sans rien reprendre : changedetection.io (sa détection de rupture s'appuie sur un navigateur), Scrapling
(relocalisation de sélecteurs, dépend de lxml), les services payants (Zyte API, Diffbot, Bright Data, Apify).

Mesures (`python -m bench.extraction`, le 18/10/2026) :

| | Avant | Après |
|---|---|---|
| Chaînes de prix réelles (corpus price-parser) | 1 035 / 1 040 | 1 036 / 1 040 |
| JSON-LD mal formés tirés de bugs réels (corpus extruct) | 5 / 36 | 36 / 36 |
| Spécification robots.txt, Python 3.11 / 3.12 du serveur | 37 / 66 | 66 / 66 |
| Pages-pièges construites sur des motifs réels | 9 / 25 | 25 / 25 |
| Pages-pièges écrites après réglage (généralisation) | 3 / 8 | 8 / 8 |
| Temps CPU, grande page produit (~450 Ko) | 80 ms | ~110 ms |

Garde-fous en place : prix membre / fidélité (`validForMemberTier`, « Prix membre ») jamais pris pour le prix public ;
produit principal choisi parmi plusieurs (produits associés, carrousels) ; fiche redirigée vers une page liste ou page
introuvable → offre retirée, rien d'enregistré ; autre produit à la même adresse (EAN différent) → idem ; offre
reconditionnée écartée si une offre neuve existe ; devise autre que l'euro refusée ; « -40 % » jamais lu comme un prix ;
prix barré validé (au-dessus du prix, remise ≤ 85 %, cohérent avec le pourcentage affiché dans le même bloc ; bandeaux
« jusqu'à -50 % » ignorés) ; « à partir de » (variantes) sans prix barré ; financement (« 108,42 €/mois en 4x »),
éco-participation, ODR, « autres offres dès … » jamais pris pour un prix. Blocage reconnu par signature (DataDome,
Cloudflare, Akamai, Imperva, PerimeterX, Kasada, Queue-it) sans faux positif sur une page lisible d'un site protégé.
Passe de nuit : 5 refus de suite sur un site → on arrête ce site pour la nuit ; chute du taux de prix barré lu → alerte
dans le rapport (changement de page probable). Provenance enregistrée : source du prix barré, vendeur, fin de promotion.

## Collecte des prix (sans affiliation)

Base produits construite soi-même, prix rafraîchis **une fois par jour**, sans IA, sur un seul petit serveur.
Familles : **électroménager** (lave-linge, sèche-linge, lave-vaisselle, réfrigérateurs, congélateurs, fours, plaques,
hottes, cuisinières), **ameublement** (canapés, fauteuils, lits, armoires, tables, buffets, meubles TV, commodes),
**literie** (matelas, sommiers). Un titre qui commence par un accessoire (housse, pieds, filtre…) ou un prix sous
100 € n'entre pas au catalogue (`collect/retailers.py` : `FAMILIES`, `MIN_PRICE`).

Enseignes actives : Boulanger, Electro Dépôt, Ubaldi, Cdiscount, But, IKEA, Maisons du Monde, La Redoute, Vente-unique.
Désactivées, avec la raison dans `collect/retailers.py` : Conforama (défi Cloudflare sur tout le site, prix chargés par le
navigateur), Darty (anti-robot signalé contre les adresses de centres de données ; à vérifier avec `diagnose darty`),
Amazon (conditions d'utilisation). Un site qui bloque est signalé, jamais forcé.

### Constituer la base (sur le serveur)
1. Dans `collect/retailers.py`, remplacez `USER_AGENT` par le nom de votre robot, une page qui le décrit et une adresse de contact.
2. `python collect.py discover all --per 40` → fiches trouvées dans les plans de site (`urls/<enseigne>.json`).
3. `python collect.py diagnose all --n 20` → `reports/diagnostic.md` : par enseigne, pages lues / avec prix / avec prix
   barré / avec EAN / bloquées (et par quelle protection), d'où vient chaque donnée, et un verdict **garder**
   (≥ 80 % de pages avec prix), **règle de site à écrire** ou **abandonner**. Détail page par page : `reports/diagnostic-<enseigne>.csv`.
4. Une page qui résiste : `python collect.py explain <adresse>` montre ce que chaque source a lu et pourquoi une donnée
   a été écartée ; puis `python collect.py rules <site> '{"price": "…", "list_price": "…"}'` et on relance le diagnostic.
5. `python collect.py sample all --n 5` enregistre des pages brutes dans `samples/` : compressé et joint, ce dossier permet
   de régler l'extraction hors ligne sur vos vraies pages.
6. `python collect.py build all` → première lecture : produits rapprochés par EAN puis par titre ; `python collect.py review`.
7. `python collect.py estimate` → durée de la passe de nuit. En production, la passe est lancée par `cli.py daily`
   (voir « Exploitation ») ; ne pas planifier aussi `collect.py nightly`.

### Ce que fait la passe de nuit
- Une requête par page et par jour, en respectant robots.txt (y compris Crawl-delay) et au moins 5 s entre deux requêtes
  vers un même site ; les sites tournent en parallèle.
- Requêtes conditionnelles (ETag / Last-Modified) ; seuls les **changements** de prix sont enregistrés ; les fortes
  variations sont relues une fois pour confirmation.
- La mention légale « prix le plus bas des 30 derniers jours » est relevée quand elle figure sur la page.
- Rapport du matin : réussite par enseigne (⚠ sous 80 %), passe interrompue, chute du prix barré lu, plus fortes baisses.

### Coût de fonctionnement
- Volume : 9 enseignes × leurs catégories × 40 fiches ≈ 4 200 fiches ; le site le plus chargé (But ou Cdiscount 
  760 fiches × 5 s) fixe la durée de la passe : ~63 min par nuit. CPU : ~0 1 s par page  soit ~8 min par nuit.
  Base : quelques dizaines de Mo par an (seuls les changements sont écrits).
- Serveur : le plus petit suffit. Hetzner CX23 : 5,49 € HT + 0,50 € d'IPv4 = **5,99 € HT par mois** (tarifs d'août 2026).
- E-mails de connexion : Brevo gratuit jusqu'à 300 e-mails par jour (SMTP autorisé, mention Brevo dans le message).
- Nom de domaine : quelques euros par an. Aucun proxy, aucune API payante, aucune IA à l'usage.

### Testé
Sans accès au web depuis l'environnement de développement : faux sites locaux (`tests/test_collect.py`,
`tests/test_extraction.py`), corpus publics et pages-pièges (`tests/corpus/`, `tests/pages.py`). **Les taux réels par
enseigne restent à mesurer avec `diagnose` depuis le serveur.**


## Limites connues
- Date de fin d'offre : relevée quand la page la déclare (`priceValidUntil`), pas encore affichée dans l'app.
- Les favoris et marques choisis avant connexion ne sont pas repris : la connexion est demandée avant l'action.
- Les taux de lecture réels par enseigne restent à mesurer sur le web (étape « diagnose ») ; les modèles d'adresse de
  fiche d'IKEA, Maisons du Monde, Vente-unique et Ubaldi sont des points de départ, confirmés par `discover`.
- Pas de navigateur : un site dont les prix n'existent qu'après exécution du JavaScript reste illisible (Conforama).
- Les flux marchands (affiliation) seraient la source la plus solide et la moins chère ; le moteur sait déjà les lire
  (format Google Merchant), mais l'affiliation est écartée au départ.
