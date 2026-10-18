# DEALS — radar personnel des bonnes offres

« Vous n'avez pas besoin de surveiller le marché en permanence. DEALS le fait pour vous. »
Chaîne active : **MARCHÉ → OPPORTUNITÉ → UTILISATEUR → SUIVI → ALTERNATIVE → ACHAT** (audit v15).
Un passage par jour, aucun LLM, un seul petit serveur.

| Couche | Dossier | Rôle |
|---|---|---|
| Marché | `listener/`, `collect/` | collecte quotidienne polie, extraction, normalisation, produit / offre / observation (EAN prioritaire), historique des prix |
| Intelligence | `listener/intelligence.py`, `radar/verify.py` | prix habituel, percentile, état du prix ; fausses remises (prix barré gonflé) écartées |
| Utilisateur | `radar/engine.py` | utilisateurs, marques / catégories suivies, interactions, suivis avec `user_id` |
| Personnalisation | `radar/engine.py` | opportunités personnelles (score + raison), alternatives sous contraintes, récapitulatif quotidien plafonné |

```
python collect.py discover|diagnose|build all      constituer la base (voir plus bas)
python radar.py daily                              la tâche de chaque nuit (idempotente)
python radar.py feed alice                         ce que l'app affiche à alice
python -m unittest discover -s tests -v            tests
python -m bench.refresh_policy                     coût de collecte vs événements ratés
```

## Moteur
- **Signal de marché** (objectif) : `NORMAL / GOOD_PRICE / VERY_GOOD_PRICE`, baisse du jour, retour en stock, prix barré gonflé.
  Recalculé seulement pour les produits dont le prix a bougé, plus les produits suivis.
- **Opportunité personnelle** (`NEW_OPPORTUNITY, EXCEPTIONAL_PRICE, PRICE_DROP, BACK_IN_STOCK, TARGET_REACHED, ALTERNATIVE`) :
  pertinence (marques et catégories suivies, interactions avec demi-vie de 3 semaines, produits écartés, budget) + qualité du prix
  + nouveauté + fraîcheur. Sans signal personnel, seules les très bonnes affaires (≥ 15 % sous l'habituel) vont dans « Vous ne cherchiez pas ça ».
- **Suivi** : prix cible, date limite, alternatives autorisées, contraintes dures (marque uniquement, minimums de caractéristiques),
  alternatives refusées. Une alternative que l'utilisateur suit lui-même devient un suivi à part entière.
- **Alternatives** : similarité déterministe sur les caractéristiques, même catégorie, précalculée une fois par semaine.
- **Notifications** : un récapitulatif par jour au plus, plafonné par utilisateur ; seulement prix atteint, alternative, ou forte
  opportunité d'une marque / catégorie suivie ; pas plus de 2 alertes « opportunité » par semaine ; un même produit n'est
  renotifié qu'après 7 jours (14 pour un suivi) ou si son prix baisse encore (≥ 5 % pour un suivi).
- **Fréquence de relecture** (plafond 1 fois par jour) : suivi, opportunité récente ou produit volatil → chaque jour ;
  centre d'intérêt → tous les 3 jours ; reste → chaque semaine.
- **Exploitation** : connexions fermées explicitement (`with Listener(...)`), tâches idempotentes (clé nom + jour), contraintes d'unicité.

## App grand public et API (couche de décision)
- `python app.py demo` → app sur http://127.0.0.1:8000/ (marché simulé, bouton « jour suivant ») ; console interne sur `/admin`.
- `python app.py serve --db deals.sqlite` → mêmes écrans sur la base réelle alimentée par `collect.py` et `radar.py daily`.
- Contrat `/api/r/` (`radar/api.py`, `radar/consumer.py`) : `feed`, `search`, `product/<id>`, `watch`, `watches`, `target`,
  `watch/<id>/stop`, `interactions`, `dismiss`, `alternative`, `go/<id>` (clic marchand tracé puis redirection), `alerts`, `metrics`.
  Utilisateur passé en `?user=` : **pas d'authentification, à ajouter avant toute ouverture publique.**
- Une seule entité de surveillance (`user_watches`) : un produit (« je l'achète à 999 € ») ou une recherche (« un lave-linge sous 500 € »).
  Elle alimente la priorité de collecte et est évaluée tout de suite à sa création (prix déjà atteint ? alternative déjà là ?).
- Fil : `watch_hits` (opportunité attendue) est séparé de `foryou` / `discovery` (opportunité inconnue).
- Alternatives apprises : deux refus d'une autre marque → l'utilisateur est traité comme fidèle à sa marque ; deux acceptations →
  l'économie compte davantage dans le classement.
- Étoile polaire (`/api/r/metrics`) : opportunités suivies d'un clic marchand dans les 3 jours, détaillées en watch hit / découverte ;
  taux de prix atteints, clic après opportunité, acceptation des alternatives, conversion des alertes, délai intention → clic.

## Mesures
`bench/refresh_policy.py`, un an de marché simulé, 2 tirages :

| | Tout relire chaque jour | Adaptatif |
|---|---|---|
| Requêtes par jour | 108 | 44–45 (**−58 %**) |
| Prix cible atteint (suivis) ratés | 0 % | **0 %** (délai 0 j) |
| Bonne affaire, centre d'intérêt, ratée | 0 % | 0–5,7 % (délai ~1 j) |
| Bonne affaire, découverte, ratée | 0 % | 13–17 % (délai ~2,7 j) |

Notifications sur 61 jours simulés (`tests/test_radar.py`) : 1,7 par semaine pour un utilisateur qui suit une marque, une catégorie et
un produit ; 0 pour un utilisateur sans intérêt déclaré.

Transactions (`bench/transactions.py`, base fichier, 30 nuits) : validation à chaque requête 1,4 s → une transaction par nuit 0,9 s (−37 %).

## Archives
Les générations précédentes (assistant de déménagement, Decision OS, vitrine) sont sorties du produit : voir `deals-archive-legacy.zip`.

## Authentification
Connexion par lien magique (e-mail, sans mot de passe) : `POST /api/r/auth/request`, lien → `GET /api/r/auth/verify` (cookie de session 90 jours). Toute route `/api/r/` sans session répond 401. Envoi des liens : `radar/accounts.py` (`Outbox.send`, à brancher sur un envoi SMTP en production).

---

# DEALS — collecte des prix (sans affiliation) · v0.1

Base produits construite soi-même, prix rafraîchis **une fois par jour**, sans IA, sur un seul petit serveur.
Catégories : **Tech + Électroménager**. Enseignes : Boulanger, Cdiscount, Fnac, Darty (top 5 de la catégorie selon
Fevad/Médiamétrie 2025, avec Amazon), plus Electro Dépôt, Ubaldi et LDLC. Amazon est désactivé : ses conditions
d'utilisation interdisent la collecte automatisée ; il viendra par l'affiliation.

## Mode d'emploi (sur votre machine, avec accès au web)
1. Dans `collect/retailers.py`, remplacez `USER_AGENT` par le nom de votre robot, une page qui le décrit et une adresse de contact.
2. `python collect.py discover all --per 20` → pages produit trouvées dans les plans de site (`urls/<enseigne>.json`).
3. `python collect.py diagnose all --n 20` → `reports/diagnostic.md` : par enseigne, pages lues / avec prix / avec EAN /
   bloquées, et un verdict **garder** (≥ 80 % de pages avec prix), **règle de site à écrire** ou **abandonner**.
   Le détail page par page est dans `reports/diagnostic-<enseigne>.csv`.
4. Pour une enseigne « règle à écrire » : `python run.py rules <site> '{"price": "sélecteur CSS du prix"}'`, puis relancer le diagnostic.
5. `python collect.py build all` → première lecture : produits rapprochés par EAN puis par titre ; `python collect.py review` pour les cas douteux.
6. `python collect.py estimate` → durée de la passe de nuit, puis planifier une passe par jour :
   `0 3 * * *  cd /chemin/deals && python3 collect.py nightly >> logs/nightly.log 2>&1`
   Chaque passe écrit `reports/AAAA-MM-JJ.md` : réussite par enseigne (⚠ sous 80 %), plus fortes baisses, « plus bas 30 jours » relevés.

## Ce que fait la passe de nuit
- Une requête par page et par jour, en respectant robots.txt et au moins 5 s entre deux requêtes vers un même site ; les sites tournent en parallèle.
- Requêtes conditionnelles (ETag / Last-Modified) : une page inchangée n'est pas retéléchargée.
- Seuls les **changements** de prix sont enregistrés ; les fortes variations sont relues une fois pour confirmation.
- La mention légale « prix le plus bas des 30 derniers jours » est relevée quand elle figure sur la page : elle amorce l'historique.
- Une enseigne bloquée ou dont la page a changé apparaît en ⚠ dans le rapport : on la corrige ou on la retire (pas de proxies payants).
- Ordre de grandeur : 7 enseignes × 14 catégories × 20 pages ≈ 2 000 offres ; ~280 par site × 5 s ≈ **25 minutes** par nuit.

## Testé (sur de faux sites locaux, l'environnement de développement n'a pas accès au web)
`tests/test_collect.py` : découverte (robots.txt → index → plan compressé, page panier interdite écartée), diagnostic
(site JSON-LD gardé, site en microdonnées gardé, site anti-robot « abandonner (bloqué) »), rapprochement (même EAN chez
deux enseignes → un seul produit), deux nuits (304 sans changement ; baisse 1 299 € → 999 € enregistrée en une seule
ligne ; « plus bas 30 jours » relevé ; rapport). **Les taux réels par enseigne restent à mesurer avec l'étape 3.**

## Application grand public (`web/`)
- Source : `web/src/App.jsx` (une seule page React, design de la maquette v41), point d'entrée `web/src/mount.jsx`.
- Build : `ESBUILD=<esbuild> REACT_DIR=<node_modules> ./web/build.sh` → `web/app.html`, page autonome servie à `/`.
  Dépendances de build uniquement ; rien n'est requis à l'exécution.
- Contrat `/api/r/` (`radar/shop.py`) : `today?category=&q=`, `categories`, `brands`, `brand/<nom>`, `item/<id>`
  (lecture ouverte) ; `save`, `saves`, `brand/follow`, `follows` (session requise, sinon 401).
- Lancement : `python app.py serve` (public : seule l'API `/api/r/` et l'app sont exposées) ;
  `python app.py serve --admin` ou `python app.py demo` ajoutent la console `/admin` et l'API marché (outil interne).

## Limites connues
- Les liens « Voir ↗ » vont directement à l'enseigne : le clic n'est pas tracé pour les visiteurs anonymes.
- Les fonctionnalités de surveillance (`watch`, `target`, alternatives) restent dans le moteur mais ne sont pas exposées par l'app.
- `radar.py` (CLI) porte le même nom que le package `radar/` : à renommer en `cli.py`.
