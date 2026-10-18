# DEALS — les bons deals du jour, au même endroit

On ouvre l'app pour savoir quelles bonnes affaires existent aujourd'hui. Un deal est un deal : le même pour tout le monde,
sans onboarding. L'entrée est le produit ; la marque et la catégorie sont des entrées secondaires ; l'enseigne n'est qu'un
attribut de l'offre. Simple, sans friction : on lit sans compte ; un e-mail suffit pour garder des favoris et suivre des marques.

Une collecte par jour, sans affiliation, aucune IA dans le classement, un seul petit serveur (Python, bibliothèque standard, SQLite).

| Couche | Fichiers | Rôle |
|---|---|---|
| Marché | `listener/`, `collect/` | collecte quotidienne polie, extraction, rapprochement produit / offre (EAN d'abord), historique des prix |
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
python collect.py discover|diagnose|build|rules|review|estimate   constituer et régler la base
python -m unittest discover -s tests -t .                         tests
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

## Collecte des prix (sans affiliation)

Base produits construite soi-même, prix rafraîchis **une fois par jour**, sans IA, sur un seul petit serveur.
Catégories : **Tech + Électroménager**. Enseignes : Boulanger, Cdiscount, Fnac, Darty (top 5 de la catégorie selon
Fevad/Médiamétrie 2025, avec Amazon), plus Electro Dépôt, Ubaldi et LDLC. Amazon est désactivé : ses conditions
d'utilisation interdisent la collecte automatisée ; il viendra par l'affiliation.

### Constituer la base (sur votre machine, avec accès au web)
1. Dans `collect/retailers.py`, remplacez `USER_AGENT` par le nom de votre robot, une page qui le décrit et une adresse de contact.
2. `python collect.py discover all --per 20` → pages produit trouvées dans les plans de site (`urls/<enseigne>.json`).
3. `python collect.py diagnose all --n 20` → `reports/diagnostic.md` : par enseigne, pages lues / avec prix / avec EAN /
   bloquées, et un verdict **garder** (≥ 80 % de pages avec prix), **règle de site à écrire** ou **abandonner**.
   Le détail page par page est dans `reports/diagnostic-<enseigne>.csv`.
4. Pour une enseigne « règle à écrire » : `python collect.py rules <site> '{"price": "sélecteur CSS du prix"}'`, puis relancer le diagnostic.
5. `python collect.py build all` → première lecture : produits rapprochés par EAN puis par titre ; `python collect.py review` pour les cas douteux.
6. `python collect.py estimate` → durée de la passe de nuit. En production, la passe est lancée par `cli.py daily`
   (voir « Exploitation ») ; ne pas planifier aussi `collect.py nightly`, qui relirait tout une seconde fois.
   Chaque passe écrit `reports/AAAA-MM-JJ.md` : réussite par enseigne (⚠ sous 80 %), plus fortes baisses, « plus bas 30 jours » relevés.

### Ce que fait la passe de nuit
- Une requête par page et par jour, en respectant robots.txt et au moins 5 s entre deux requêtes vers un même site ; les sites tournent en parallèle.
- Requêtes conditionnelles (ETag / Last-Modified) : une page inchangée n'est pas retéléchargée.
- Seuls les **changements** de prix sont enregistrés ; les fortes variations sont relues une fois pour confirmation.
- La mention légale « prix le plus bas des 30 derniers jours » est relevée quand elle figure sur la page : elle amorce l'historique.
- Une enseigne bloquée ou dont la page a changé apparaît en ⚠ dans le rapport : on la corrige ou on la retire (pas de proxies payants).
- Ordre de grandeur : 7 enseignes × 14 catégories × 20 pages ≈ 2 000 offres ; ~280 par site × 5 s ≈ **25 minutes** par nuit.

### Testé (sur de faux sites locaux, l'environnement de développement n'a pas accès au web)
`tests/test_collect.py` : découverte (robots.txt → index → plan compressé, page panier interdite écartée), diagnostic
(site JSON-LD gardé, site en microdonnées gardé, site anti-robot « abandonner (bloqué) »), rapprochement (même EAN chez
deux enseignes → un seul produit), deux nuits (304 sans changement ; baisse 1 299 € → 999 € enregistrée en une seule
ligne ; « plus bas 30 jours » relevé ; rapport). **Les taux réels par enseigne restent à mesurer avec l'étape 3.**


## Limites connues
- Pas de date de fin d'offre dans les données collectées : l'app n'affiche pas « fin dans X jours ».
- Les favoris et marques choisis avant connexion ne sont pas repris : la connexion est demandée avant l'action.
- Les taux de lecture réels par enseigne restent à mesurer sur le web (étape « diagnose »).
