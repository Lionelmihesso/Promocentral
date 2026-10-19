# DEALS — les bons deals du jour, au même endroit

On ouvre l'app pour savoir quelles bonnes affaires existent aujourd'hui. Un deal est un deal : le même pour tout le monde,
sans onboarding. L'entrée est le produit ; la marque et la catégorie sont des entrées secondaires ; l'enseigne n'est qu'un
attribut de l'offre. On lit sans compte ; un e-mail suffit pour garder des favoris et suivre des marques.

Trois familles chères, où une remise compte : **électroménager, ameublement, literie**. Une collecte par nuit, sans
affiliation, aucune IA, un seul petit serveur (Python, bibliothèque standard, SQLite) : environ 6 € HT par mois.

**Architecture** : une chaîne de nuit qui calcule (collecte → marché → publication du catalogue), une app de jour qui
lit le catalogue publié. Modules, règles et données : [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Audit et refonte
d'octobre 2026, mesures avant / après : [`docs/AUDIT.md`](docs/AUDIT.md).

## Commandes
```
python deals.py demo                         app sur http://127.0.0.1:8000/ : 84 nuits de marché simulé, 48 produits
python deals.py serve                        l'app et /api/r/ (en production derrière Caddy, voir deploy/)
python deals.py nightly                      la nuit : collecte → rapport du matin → publication du catalogue
python deals.py publish                      republier le catalogue sans relire le web
python deals.py discover|diagnose|sample|build <enseigne|all>     constituer et régler la base
python deals.py explain <adresse>            ce que l'extraction voit sur une page, et pourquoi
python deals.py rules <site> '<json>'        règle de lecture d'un site (sélecteurs)
python deals.py review|estimate|metrics      rapprochements à vérifier, durée de la nuit, mesures du produit
python deals.py backup <dossier>             sauvegarde à chaud vérifiée (14 conservées)
python -m unittest discover -s tests -t .    tests (36, ~8 s)
python -m bench.extraction | bench.deals_truth | bench.scale      mesures (extraction, vraies remises, charge)
ESBUILD=<esbuild> REACT_DIR=<node_modules> ./web/build.sh          reconstruire web/app.html
```
`--db` (avant la commande) choisit la base ; réglages par variables `DEALS_*` (`deals/config.py`,
`deploy/deals.env.example`). Les commandes qui lisent les sites exigent `DEALS_USER_AGENT` (nom du robot, contact).

## API `/api/r/` (contrat de l'app)
Lecture ouverte : `today?category=&q=`, `categories`, `brands`, `brand/<nom>`, `item/<id>`, `out/<offer_id>?from=`.
Ajoutés depuis la v41, sans rien retirer : `since` et `ends` (montrés dans la fiche), `saved_price` (favoris), `family`
(catégories).
Session requise (sinon 401) : `save`, `saves`, `brand/follow`, `follows`.
Comptes : `auth/request` {email}, `auth/verify?token=` (pose le cookie, ou renvoie vers `/?auth=expired`), `auth/me`, `auth/logout`.

## Règles du produit
- **Seulement des remises réelles.** Une remise affichée par l'enseigne est crue, sauf preuve du contraire : notre
  historique hors promotion (au moins 14 jours observés), la mention légale « prix le plus bas des 30 derniers jours »,
  ou un « prix barré » inchangé depuis 60 jours (c'est alors le prix). Fausse remise : 10 points de plus que la remise
  réelle, sauf si celle-ci dépasse 30 %. Une fiche reste consultable, sans remise affichée (`deals/judge.py`).
- **Minimaliste** : dans les listes, la marque, le produit, le prix et la remise, rien d'autre. La qualité est
  implicite ; les durées (depuis quand, jusqu'à quand) ne sont que dans la fiche.
- **Classement** : remise en %, × 1,5 si la marque est suivie par la personne connectée. Rien d'autre.
- **Produits similaires** : même catégorie, caractéristiques proches (taille, capacité, classe énergie) ; à défaut, prix le plus proche.
- **Recherche** : insensible aux accents, à la casse et aux tirets, synonymes courants (frigo, sofa, congélo…).
- **Connexion au moment de l'action** (favori, suivre), jamais à l'entrée. Lien à usage unique valable 15 min ; 5 liens
  par adresse et par heure, 20 par adresse IP, plafond quotidien global ; même réponse qu'un compte existe ou non ;
  seuls les hachages des jetons sont stockés.
- **Favoris** : le prix du jour où le favori a été posé est gardé ; une baisse se voit dans Favoris et sur l'onglet.
- **Clics sortants** : `out/<offer_id>` trace le clic (avec ou sans compte) et ne redirige que vers l'adresse d'une
  offre connue. C'est la mesure du produit (`python deals.py metrics`).
- **Fraîcheur** : toutes les offres sont relues chaque nuit tant que la passe tient dans le budget (4 h) ; sinon, par
  ordre de valeur (deal en cours, favori, clic récent, puis le plus ancien relu). Un prix non relu depuis 3 jours n'est
  plus montré.

## Interface

Une page (`web/src/App.jsx` → `web/app.html`, police Manrope incluse, aucune requête vers un tiers) : téléphone d'abord,
deux colonnes sur ordinateur, minimaliste (une ligne = marque, produit, prix, remise). Pictogrammes de catégorie dans
Explorer (pas de photo en V1), contrastes et zones à toucher aux normes WCAG AA. Principe, écrans et mesures v41 / v43 /
v44 : [`docs/UX.md`](docs/UX.md).

## Extraction : ne jamais enregistrer une donnée fausse

Une donnée manquée coûte une bonne affaire ; une donnée fausse (prix membre pris pour le prix public, prix d'un produit
voisin, fiche devenue page liste) coûte la confiance. L'extraction lit dans l'ordre : JSON-LD, règles de site,
microdonnées, balises meta, état applicatif embarqué (seulement si l'identité du produit concorde). Le prix barré peut
aussi venir du bloc de prix HTML, mais seulement à côté du prix trouvé par une source structurée, dans le même bloc.

Repris de l'existant (BSD-3, voir `THIRD_PARTY_NOTICES.md`) : **Protego** (Scrapy) pour robots.txt, la chaîne de
réparation JSON-LD d'**extruct** (Zyte), les corpus de test d'extruct, de price-parser et de Protego.

| `python -m bench.extraction` | Extracteur d'origine | Actuel |
|---|---|---|
| Chaînes de prix réelles (corpus price-parser) | 1 035 / 1 040 | 1 036 / 1 040 |
| JSON-LD mal formés tirés de bugs réels (corpus extruct) | 5 / 36 | 36 / 36 |
| Spécification robots.txt (Python 3.11 / 3.12 du serveur) | 37 / 66 | 66 / 66 |
| Pages-pièges construites sur des motifs réels | 9 / 26 | 26 / 26 |
| Pages-pièges écrites après réglage (généralisation) | 3 / 8 | 8 / 8 |
| Temps CPU, grande page produit (~450 Ko) | 80 ms | ~100 ms |

Garde-fous : prix membre jamais pris pour le prix public ; produit principal choisi parmi plusieurs (carrousels) ; fiche
devenue page liste, introuvable ou montrant un autre produit → offre retirée, rien d'enregistré ; offre reconditionnée
écartée si une offre neuve existe ; devise autre que l'euro refusée ; « -40 % » jamais lu comme un prix ; prix barré
validé (au-dessus du prix, remise ≤ 85 %, cohérent avec le pourcentage affiché ; bandeaux « jusqu'à -50 % » ignorés) ;
financement, éco-participation, ODR, « autres offres dès … » jamais pris pour un prix. Blocage reconnu par signature
(DataDome, Cloudflare, Akamai, Imperva, PerimeterX, Kasada, Queue-it) sans faux positif sur une page lisible.

## Collecte (sans affiliation)

Familles : **électroménager** (lave-linge, sèche-linge, lave-vaisselle, réfrigérateurs, congélateurs, fours, plaques,
hottes, cuisinières), **ameublement** (canapés, fauteuils, lits, armoires, tables, buffets, meubles TV, commodes),
**literie** (matelas, sommiers). Un titre qui commence par un accessoire ou un prix sous 100 € n'entre pas au catalogue.

Enseignes actives : Boulanger, Electro Dépôt, Ubaldi, Cdiscount, But, IKEA, Maisons du Monde, La Redoute, Vente-unique.
Désactivées, avec la raison dans `deals/collect/retailers.py` : Conforama (défi Cloudflare, prix chargés par le
navigateur), Darty (anti-robot signalé contre les centres de données, à vérifier avec `diagnose darty`), Amazon
(conditions d'utilisation). Un site qui bloque est signalé, jamais forcé.

Constituer la base : `discover` (plans de site) → `diagnose` (verdict par enseigne : garder si ≥ 80 % des pages ont un
prix, règle de site à écrire, ou abandonner) → `explain` et `rules` pour une page qui résiste → `sample` (pages brutes
pour un réglage hors ligne) → `build` (première lecture, rapprochement par EAN) → `review` → `estimate`. Sur le
serveur : `sudo deals <commande>` (voir `deploy/README.md`).

La passe de nuit : une requête par page, robots.txt et Crawl-delay respectés, au moins 5 s entre deux requêtes vers un
même site, les sites en parallèle ; requêtes conditionnelles (ETag / Last-Modified) ; seuls les changements de prix
sont enregistrés ; les fortes variations sont relues avant d'être crues ; rapport du matin avec alertes.

## Coût de fonctionnement
- ~4 200 fiches ; le site le plus chargé (~760 fiches × 5 s) fixe la passe : ~63 min par nuit. Publication : ~3 s.
- Base : quelques dizaines de Mo par an (seuls les changements sont écrits).
- Serveur : Hetzner CX23, 5,49 € HT + 0,50 € d'IPv4 = **5,99 € HT par mois** (tarifs d'août 2026).
- E-mails de connexion : Brevo gratuit jusqu'à 300 par jour. Nom de domaine : quelques euros par an. Aucun proxy, aucune
  API payante, aucune IA.

## Limites connues
- Les taux de lecture réels par enseigne restent à mesurer depuis le serveur (`diagnose`) : l'environnement de
  développement n'a pas accès au web ; tout est vérifié sur faux sites locaux, corpus publics et pages-pièges.
- Pas de navigateur : un site dont les prix n'existent qu'après exécution du JavaScript reste illisible (Conforama).
- Une baisse sans prix barré n'est pas montrée (choix produit et juridique, voir `docs/AUDIT.md`).
- Date de fin d'offre relevée (`priceValidUntil`), pas encore affichée ; les favoris choisis avant connexion ne sont pas
  repris (la connexion est demandée avant l'action).
