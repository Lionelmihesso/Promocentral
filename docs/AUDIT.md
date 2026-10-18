# Audit de la plateforme DEALS — octobre 2026

**Verdict.** Le cœur était bon : l'extraction des prix, le rapprochement des produits et le design de l'app tenaient
leurs promesses, mesures à l'appui. Autour, trois générations de moteur s'étaient empilées : du code que le produit
n'utilise pas, des frontières qui fuyaient, des lectures qui recalculaient tout le marché à chaque requête, et une règle
de remise qui cachait les vrais deals au lancement — exactement quand il faut convaincre. La plateforme a été refondue
autour d'une seule idée, « la nuit calcule, le jour lit », avec un module par responsabilité et une seule écriture par
sujet. Le contrat de l'app (`/api/r/`) et l'interface v41 sont inchangés.

## Méthode

Lecture intégrale du code (commit `3a724b9`), couverture d'exécution des tests, puis mesures reproductibles. Les
chiffres « avant » ont été mesurés sur `3a724b9` avec les mêmes données que les chiffres « après » :

| Mesure | Commande (après) | Données |
|---|---|---|
| Vraie / fausse remise contre une vérité connue | `python -m bench.deals_truth` | un an de marché simulé, 30 produits × 3 enseignes, 3 tirages, chaîne complète chaque nuit |
| Lectures de l'app et publication | `python -m bench.scale` | 3 000 produits, 4 200 offres, ~40 000 lignes de prix sur 90 jours |
| Extraction | `python -m bench.extraction` | corpus publics (price-parser, extruct, Protego) et pages-pièges |
| Écritures web pendant la nuit | `tests/test_ops.py` | deux processus sur la même base |

## Constats et décisions

### Critiques

**1. Les vrais deals étaient cachés au lancement.** Sans historique, le « prix habituel » d'un produit était son prix
du jour — donc le prix promo — et toute remise de plus de 10 % passait pour fausse. Le premier jour, une vraie remise de
40 % était masquée. Sur le marché simulé, seuls 46 % des vrais deals du premier mois étaient montrés.
→ Règle refaite (`judge.py`, fonction pure) : la remise de l'enseigne est crue *sauf preuve du contraire* (historique
hors promotion d'au moins 14 jours, mention légale « plus bas 30 jours », prix barré inchangé depuis 60 jours).
Premier mois : 89 % des vrais deals montrés, et la précision monte aussi (75 % → 81 %).

**2. Chaque lecture de l'app recalculait le marché entier.** `today`, `categories`, `brands`, `brand` reconstruisaient
l'analyse des 3 000 produits à chaque requête : 6,4 à 7,0 s par page, 0,8 s par fiche, cache du jour compris.
→ Le catalogue du jour est calculé une fois après la collecte (`publish.py`, ~2,7 s) et écrit dans des tables dédiées ;
une requête fait une ou deux lectures indexées : moins de 5 ms.

**3. Les liens de connexion ne seraient pas partis en production.** Le fichier de réglages d'exemple portait un
commentaire en fin de ligne (`DEALS_SMTP_TLS=starttls  # …`). systemd le garde dans la valeur : le code ne
reconnaissait plus « starttls », se connectait sans chiffrement, et le fournisseur refusait l'authentification (ou,
pire, la recevait en clair).
→ Réglages validés au démarrage (la variable fautive est nommée), chiffrement par défaut (en clair seulement si
`none` est écrit), fichier d'exemple corrigé.

### Élevés

**4. Un moteur hérité que le produit n'utilise pas.** Un objet de 1 008 lignes (`Listener`) portait événements,
signaux, surveillances, webhooks, flux temps réel, console interne, flux marchands et planification par offre toutes
les 15 minutes. 22 % des lignes de fonctions n'étaient jamais exécutées (mesure de couverture) ; 7 tables étaient écrites
sans jamais être lues.
→ Retiré. Ce que le produit ne montre pas n'est ni calculé, ni stocké, ni testé.

**5. Des frontières qui fuyaient.** La boutique lisait le cache privé du moteur (`_snapshot_cached`), la collecte
remplaçait des méthodes du moteur à chaud, 23 tables étaient déclarées dans 4 fichiers, sans numéro de schéma.
→ Un module par responsabilité, une seule écriture par sujet, les lectures croisées listées
(`docs/ARCHITECTURE.md`) ; schéma complet dans `store.py`, versionné : un code plus ancien que la base refuse de démarrer.

**6. La concurrence tenait par contournement.** Validations groupées tenant le verrou d'écriture jusqu'à 1 s, pauses
de 0,1 s, verrou global : un favori ou un clic attendait jusqu'à 1,03 s pendant la passe de nuit.
→ SQLite en WAL, une connexion par fil, une transaction courte par page relue : 3 à 9 ms d'attente au pire.

**7. Trois lignes de commande** (`app.py`, `cli.py`, `collect.py`) aux options qui se recouvraient.
→ Une seule : `python deals.py <commande>`, et `sudo deals <commande>` sur le serveur.

**8. Un prix barré perdu, trouvé par le nouveau test de bout en bout.** Sur une fiche dont le titre finit par un chiffre
(« … Integral 3 »), le prix barré « 879,99 € » qui suit était recollé au « 3 » et lu 3 879,99 € ; le garde-fou
(remise ≤ 85 %) l'écartait, et un vrai −40 % disparaissait. → Corrigé (seuls deux fragments purement numériques d'un
même élément sont recollés) et verrouillé par une page-piège.

### Moyens

| Constat | Décision |
|---|---|
| Quota d'e-mails épuisable : seule limite, 5 liens par adresse ; en changeant d'adresse, on épuisait le quota du fournisseur (300 par jour) et plus personne ne pouvait se connecter | 20 liens par adresse IP et par heure, plafond quotidien global avec message clair |
| Corps de requête non borné ; une longueur négative bloquait un fil du serveur ; aucune limite d'inactivité | 16 Ko, longueur invalide → 400, connexion inactive fermée après 30 s |
| Routes d'administration capables de faire lire n'importe quelle adresse au serveur | Retirées : seules l'app et `/api/r/` existent |
| Jour UTC et jour local mélangés (`time.mktime` dans le moteur quotidien, jour UTC ailleurs) | UTC partout |
| Les commandes lancées à la main lisaient les sites sous l'identité d'exemple du robot | Refus de lire un site sans `DEALS_USER_AGENT` ; commande `deals` qui reprend les réglages des services |
| Sauvegarde : service en lecture seule incapable d'ouvrir une base WAL fermée ; restauration exposée à un journal resté sur place | Service et procédure corrigés |
| Tests : 79 tests, 75 s, dont une trentaine sur des fonctions retirées ; scénarios montés plutôt que contrats | 35 tests de contrat, ~8 s ; la qualité se mesure dans `bench/` contre des corpus et une vérité connue |

### Ce qui était bon, et a été gardé tel quel

Extraction (JSON-LD réparé, prix barré validé, garde-fous, robots.txt conforme, blocages reconnus) ; rapprochement
produit par EAN, puis marque + référence, puis titre ; historique au changement seulement ; confirmation des variations
énormes ; connexion par lien magique (jetons hachés, usage unique) ; clic sortant tracé sans redirection ouverte ;
services systemd cloisonnés ; sauvegarde à chaud vérifiée ; contrat de l'app.

## Avant / après

| | Avant (`3a724b9`) | Après |
|---|---|---|
| Vrais deals montrés, 1er mois / ensuite | 46 % / 98 % | **89 %** / 98 % |
| Précision, 1er mois / ensuite | 75 % / 91 % | 81 % / 90 % |
| `today` à 3 000 produits (médiane) | 6 991 ms | **~3,5 ms** |
| `categories` · `brands` · `brand/<nom>` | 6 983 · 6 504 · 6 397 ms | 0,13 · 0,9 · 0,06 ms |
| `item/<id>` | 810 ms | 0,05 ms |
| Calcul du catalogue | à chaque requête | une fois par nuit, ~2,7 s |
| Attente d'une écriture web pendant la nuit | jusqu'à 1,03 s | 3 à 9 ms |
| Code applicatif hors extraction (lignes non vides) | 2 622 | 1 745, simulateur compris (−33 %) |
| Plus gros module hors extraction | 1 008 lignes | 196 lignes |
| Tables · fichiers qui les déclarent · version | 23 · 4 · aucune | 14 · 1 · `user_version` |
| Lignes de commande | 3 | 1 |
| Tests | 79 en 75 s | 35 en ~8 s |
| Extraction (`bench/extraction`) | 1 036/1 040 · 36/36 · 66/66 · 25/26 · 8/8 | 1 036/1 040 · 36/36 · 66/66 · 26/26 · 8/8 |

Les remises montrées sans opportunité réelle en régime établi (10 %) sont à 96 % de vraies promotions d'enseigne,
simplement modestes face au marché (entre 0 et 8 % sous son prix normal) ; 4 % sont de fausses promotions passées
(32 jours-produits sur trois ans simulés).

## Décisions d'architecte, et ce qu'elles coûtent

- **Un serveur, Python standard, SQLite.** ~6 € HT par mois, rien à installer, rien à maintenir. Coût : un seul
  serveur ; largement suffisant pour des centaines de milliers d'offres relues une fois par jour.
- **Une passe par nuit plutôt que du temps réel.** Une promotion de quelques heures peut être manquée ; c'est cohérent
  avec le produit (« les deals du jour ») et c'est ce qui permet de tout calculer d'avance.
- **Croire l'enseigne sans preuve contraire.** +43 points de vrais deals montrés au lancement ; en régime établi, 99 %
  des remises montrées sont confrontées à une preuve.
- **Pas de navigateur.** Les sites dont le prix n'existe qu'après JavaScript restent illisibles (Conforama) ; en
  échange, ni proxy, ni ferme de navigateurs, ni contournement de protection.
- **Des contrats et des mesures plutôt qu'une multitude de tests.** Les tests vérifient ce que le produit promet ; la
  qualité (extraction, justesse des remises, charge) se mesure dans `bench/` avant de changer une règle.

## Ce qui reste, par priorité

1. **Mesurer les vraies enseignes depuis le serveur** (`sudo deals diagnose all`) : l'environnement de développement n'a
   pas accès au web ; c'est la seule inconnue qui compte encore.
2. **Les baisses sans prix barré** ne sont pas montrées. Sur le marché simulé, cela représente un jour-opportunité sur
   cinq. Les montrer (« −X % par rapport à son prix habituel ») est une décision produit et juridique : les règles
   françaises sur les annonces de réduction de prix (directive Omnibus, prix de référence = plus bas des 30 derniers
   jours) sont à valider avant tout affichage.
3. **Lancement en période de soldes** : la variation hebdomadaire des prix coupe parfois un long épisode de
   promotion en deux, ce qui explique la plupart des vrais deals encore cachés le premier mois. Tout réglage se mesure
   avec `bench/deals_truth.py`.
