# Mise en production à J+30 : audit J1–3, risques et plan par lots

Version auditée : **v24** (commit `e87a002`, 31 octobre 2026), depuis le zip décompressé. Cadre : « Plan CTO —
préparer une mise en production en 30 jours » (Promo Central), pris comme un cadre de décision, sans obligation.
**Le front v62 est validé et reste tel quel** : rien de ce plan ne le modifie. Ce qui y toucherait est signalé et
attend une décision (§ 7).

## En bref

- **Le socle est sain et se vérifie.** 201 tests passent sur Python 3.11, 3.12 et 3.13. Le build est reproductible
  au bit près. Le parcours navigateur passe (85 étapes sur 85), l'audit d'accessibilité aussi (90 écrans sans
  défaut). Une sauvegarde se restaure et la base restaurée sert l'app. SQLite tient la charge visée : 3 000
  produits, publication en 3,3 s, lectures sous 43 ms au 95e centile, base de 12,5 Mo.
- **L'hypothèse critique du cadre est fausse aujourd'hui.** Aucun flux CSV, XML ou JSON n'est ingéré. La collecte
  lit les fiches des enseignes (plans de site, puis JSON-LD et microdonnées). L'affiliation se limite aux gabarits de
  lien. Boulanger annonce pourtant des « flux produits mis à jour en temps réel » à ses affiliés, via Kwanko
  ([page affiliation Boulanger](https://www.boulanger.com/info/corporate/afiliation.htm)) : le connecteur de flux est
  le lot technique n° 1.
- **Quatre blocages avant d'ouvrir (P0)** :
  1. la chaîne n'a jamais lu une vraie enseigne : toutes les mesures portent sur un marché simulé, dont chaque fiche
     a un EAN et une disponibilité ;
  2. aucun programme d'affiliation n'est confirmé, or en production seules les enseignes partenaires sont lues et
     publiées ;
  3. le rapprochement fusionne deux références différentes sur la seule ressemblance du titre (prouvé par
     exécution) ;
  4. les mentions légales manquent (identité de l'éditeur et de l'hébergeur).
- **Ce qui ne change pas :** monolithe modulaire, SQLite, jobs de nuit, ni microservice ni IA. Les mesures ne
  justifient pas autre chose (§ 1).

## 1. Baseline exécutée (31 octobre 2026)

| Contrôle | Commande | Résultat |
|---|---|---|
| Contrats | `python -m unittest discover -s tests -t .` | 201 tests OK sous 3.11 (47 s), 3.12 (58 s) et 3.13 (55 s) |
| Build | `ESBUILD=… ./web/build.sh` | `web/app.html` reconstruit identique (408 504 octets), arbre propre |
| Parcours navigateur | e2e Chromium (hors dépôt) | 85 étapes sur 85, aucune erreur JS |
| Accessibilité | audit WCAG (hors dépôt) | 90 écrans (téléphone et ordinateur), 0 défaut |
| Extraction | `python -m bench.extraction` | 1 036/1 040 prix réels, 36/36 JSON-LD cassés, 66/66 robots.txt, 26/26 + 8/8 pages-pièges |
| Vraie ou fausse remise | `python -m bench.deals_truth` | 30 premiers jours : rappel 89 %, précision 81 % (357 remises montrées à tort), **18 % confirmées par une preuve** ; ensuite : 98 %, 90 %, 99 % |
| Pannes injectées | `python -m bench.autonomy` | anti-robot mis de côté sans être forcé, erreur de prix jamais publiée, SMTP en panne signalé, catalogue qui fond retenu 2 nuits |
| Charge (3 000 produits, 90 jours) | `python -m bench.scale` | publication 3,3 s, 10 000 missions en 2,2 s, lectures : médiane 0,1 à 28 ms, 95e centile ≤ 43 ms, base 12,5 Mo |
| Sauvegarde et restauration | `deals.py backup`, puis la procédure de `deploy/README.md` | integrity_check ok, 25 tables identiques, l'app démarre sur la base restaurée, `/api/r/health` répond |
| Cadre de mise en production | `python -m bench.cadre` | **8/19 respectés** ; écarts : P0 3, P1 6, P2 2 (§ 4) |

**SQLite ou PostgreSQL ?** SQLite reste. Un seul serveur, WAL, une écriture longue par nuit (la publication, 3,3 s)
pendant que les lectures continuent, une attente de 10 s sur verrou. La migration n'apporterait rien de mesurable
au lancement. À revoir seulement si les écritures concurrentes du jour (comptes, clics) dépassent ce que montrent les
mesures, ou s'il faut un deuxième serveur.

## 2. Cartographie observée

**La chaîne.**
Nuit (`deals.py nightly`, 3 h) :

> registre des sources → plan (ordre de valeur) → `fetch` (robots.txt, 5 s par site, blocages reconnus) → `extract`
> (pur : page → offre) → `market` (seul écrivain des produits, offres et prix ; un prix écrit seulement s'il change)
> → agent (relance, mise de côté, quarantaine) → `publish` (une transaction ; garde : −20 % de produits ou d'offres,
> la publication attend) → `missions` (e-mails) → `health` → rapport du matin → e-mail au responsable s'il y a lieu.

Jour (`deals.py serve`) : `web` (serveur à un fil par connexion, derrière Caddy) → `api` (32 routes `/api/r/`) →
lectures indexées du catalogue publié ; `accounts`, `activity`, `missions` et `profile` écrivent les données des
personnes.

**Modules** (41 modules Python, 7 731 lignes, bibliothèque standard seulement). Le graphe d'imports est relevé par
l'AST. Il a deux cycles, chacun à l'intérieur d'une couche et résolu par import différé :
`extract.categories` ↔ `ontology` et `catalog` ↔ `profile`. La nuit lit trois modules du jour (`catalog`,
`missions`, `accounts`), par construction.

| Couche | Modules | Lignes |
|---|---|---|
| Collecte (nuit) | `fetch`, `collect/` (crawl, discover, diagnose, report, retailers), `extract/` (page, offer, categories), `ontology/` (+ 4 JSON, 376 lignes), `market`, `sources`, `quarantine` | 2 781 |
| Jugement et publication (nuit) | `judge`, `alternatives`, `publish`, `night`, `agent`, `health`, `ops` | 1 144 |
| App (jour) | `web`, `api`, `catalog`, `query`, `funnel`, `labels`, `profile`, `missions`, `accounts`, `activity`, `affiliate` | 2 640 |
| Socle et outils | `store` (schéma v12 et migrations), `config`, `errors`, `backup`, `cli`, `sim`, `demo` | 1 166 |
| Front | `web/src/App.jsx` (1 430), `art.jsx` (381), `mount.jsx` (3) → `web/app.html` autonome | 1 814 |

**Tables** (25, schéma v12 ; lignes après 75 nuits de démo) :

| Domaine | Tables (lignes) | Écrites par |
|---|---|---|
| Marché | `products` (127), `offers` (381), `prices` (8 344 : une ligne par changement), `site_rules` (0) | `market` |
| Catalogue publié | `catalog` (127), `catalog_offers` (381), `alternatives` (80), `similar` (114), `meta` (1) | `publish` |
| Personnes | `users`, `sessions`, `login_links`, `saves`, `follows`, `interests`, `prefs`, `missions`, `views`, `clicks` (0 en démo) | `accounts`, `activity`, `profile`, `missions` |
| Exploitation | `runs` (75 : une par passe), `sources` (4), `quarantine`, `events` (150), `incidents`, `actions` | `collect`, `sources`, `quarantine`, `ops`, `agent` |

**API** : 17 lectures (`today`, `search`, `top`, `foryou`, `profile`, `categories`, `brands`, `brand/<nom>`,
`category/<clé>`, `item/<id>`, `out/<offre>` (clic tracé → lien affilié), `saves`, `follows`, `missions`,
`auth/verify`, `auth/me`, `health`) et 15 écritures POST (goûts, favoris, marques, missions, compte, connexion). Rien
d'autre n'est servi : `/admin` → 404.

**Jobs** : `deals-daily.timer` (3 h, la nuit), `deals-backup.timer` (6 h, sauvegarde à chaud vérifiée, 14 gardées),
`deals-web.service` (relancé s'il tombe).

**Déploiement** :
- Debian ou Ubuntu, Python 3.11 ou plus, SQLite 3.35 ou plus (vérifié au démarrage).
- Caddy : HTTPS automatique, gzip, aucun journal d'accès.
- systemd durci : `NoNewPrivileges`, `ProtectSystem=strict`, seuls `/var/lib/deals` et les sauvegardes en écriture.
- Secrets dans `/etc/deals/deals.env` (600, root) ; partenaires dans `/etc/deals/affiliate.json`.
- Coût visé : un Hetzner CX23, 5,99 € HT par mois (tarif relevé en août 2026).

## 3. L'hypothèse critique : des flux structurés ingérés ?

**Non, pas aujourd'hui.**
- Aucun module ne lit de flux produits. Le seul analyseur XML (`collect/discover.py`) lit les plans de site, et le
  seul `csv` (`cli.py`) écrit le rapport de diagnostic.
- La collecte n'utilise que les deux derniers recours de l'ordre de préférence du cadre : les données structurées des
  pages, puis les règles de site (sélecteurs HTML).
- `affiliate.py` (40 lignes) construit un lien au moment du clic. Ce n'est pas un connecteur produit.
- Deux documents disaient l'inverse (« lus dans ce que l'enseigne donne par son flux affilié ou son API ») :
  `README.md` et `docs/ONTOLOGIE.md` sont corrigés.

**Jamais confrontée au réel.** L'environnement de développement n'a pas accès au web. Le marché simulé est plus
propre qu'une vraie enseigne : chaque fiche simulée porte un EAN (`sim.py`, `gtin13`) et une disponibilité. Le
rapprochement par titre et la disponibilité inconnue n'ont donc jamais servi en démo ni dans les bancs, et c'est là
que se trouvent les écarts du § 4.

**Ce qui existe déjà et se garde.** Le contrat de sortie d'une lecture (`extract` → offre normalisée : prix, prix
barré, disponibilité, EAN, marque, référence, catégorie déclarée, provenance de chaque champ), le seul écrivain
(`market`), les garde-fous du prix et toute la suite (quarantaine, garde de publication, agent). Un flux produit
s'ajoute comme une source de plus qui produit les mêmes offres pour `market`, sans toucher au reste (déjà prévu par
`docs/ARCHITECTURE.md`).

## 4. Les points non négociables, vérifiés : `python -m bench.cadre`

| Point | v24 | Preuve (exécution) |
|---|---|---|
| Deux références fabricant différentes ne sont pas fusionnées sur le titre | **ÉCART P0** | WGG244Z0FR et WGG244Z1FR, sans EAN, titres semblables à 86 % (seuil 80 %) → un seul produit |
| Deux produits sans marque ni référence ne sont pas fusionnés sur le titre | **ÉCART P0** | canapé gris et canapé beige → un seul produit |
| Un rapprochement par le seul titre est marqué « à vérifier » | **ÉCART P0** | `needs_review` = 0 sur le produit fusionné |
| Deux tailles d'une même gamme, deux EAN différents : jamais fusionnés | OK | 55 et 65 pouces, EAN …017 et …024 : produits distincts |
| Une disponibilité non dite reste « inconnue » | OK | `unknown` à la lecture |
| Une disponibilité inconnue n'est pas promise | **ÉCART P1** | une offre `unknown` publiée compte comme disponible : l'alerte « lave-linge sous 600 € » enverrait son e-mail |
| Prix membre, prix avec code, frais de livraison, ODR : jamais pris pour le prix | OK | 899 € lu (membre 799 €) ; 649 € lu (code 599 €, livraison 39 €) |
| Frais de livraison connus | **ÉCART P2** | aucune colonne : le prix montré est celui de l'article seul |
| Pas de remise sur le seul prix barré de l'enseigne sans référence qualifiée | **ÉCART P1** | sans historique ni mention « plus bas 30 jours » : remise de 38 % montrée, non confirmée |
| Adresse de la fiche, lien affilié et identifiant du clic séparés ; la commission n'entre dans aucun classement | OK | `offers.url` intact, lien construit au clic ; aucune commission stockée |
| Sauvegarde restaurable, base identique | OK | produits, offres et prix identiques après restauration |
| Copie des sauvegardes hors du serveur | **ÉCART P1** | sauvegardes sur le même disque que la base |
| Une version se déploie et se retire d'une commande | **ÉCART P1** | `cp -r` puis redémarrage ; après une migration, revenir demande de restaurer la base à la main |
| HTTPS imposé au navigateur (HSTS) | **ÉCART P1** | aucun en-tête Strict-Transport-Security dans le `Caddyfile` |
| La page du robot annoncée aux enseignes existe | **ÉCART P1** | le robot se présente avec « …/robot » ; `GET /robot` → 404 |
| Politique de contenu (CSP) | **ÉCART P2** | servis : nosniff, X-Frame-Options DENY, Referrer-Policy |
| Aucun secret ni aucune base dans le dépôt | OK | aucun fichier sensible suivi |

Vérifié aussi, sans écart : un cookie de session `HttpOnly`, `SameSite=Lax` et `Secure` en https, ce qui suffit
contre les écritures inter-sites. Les corps de requête sont limités à 16 Ko, les connexions muettes coupées à 30 s.
L'adresse IP n'est lue dans `X-Forwarded-For` que derrière le proxy local. Il y a 100 comptes invités au plus par
adresse IP et par heure, et des plafonds d'e-mails de connexion. Les jetons sont stockés hachés. Un code plus ancien
que la base refuse de démarrer.

## 5. Registre des risques

### P0 : bloque l'ouverture

| # | Risque | Preuve | Réponse retenue | Écarté, et pourquoi |
|---|---|---|---|---|
| P0-1 | Données réelles jamais lues : taux de lecture, EAN, prix barrés, disponibilités inconnus par enseigne | README « Limites connues » ; marché simulé ; pas d'accès web en développement | Lot 3 : depuis le serveur, `discover` → `diagnose` → `sample` → `build` sur les sources confirmées ; audit à la main de 20 offres par source et par famille ; seuils fixés sur cet échantillon | Ouvrir sur la foi des bancs : ils ont été écrits par le même auteur que les règles |
| P0-2 | Aucun partenaire confirmé : en production, seules les enseignes de `affiliate.json` sont lues et publiées | `publish.py`, `affiliate.py` ; `deploy/affiliate.example.json` = gabarits fictifs | Décision D1 : programmes acceptés et leurs flux ; sans partenaire, rien n'ouvre | Publier des enseignes non partenaires : contraire au modèle et aux conditions des programmes |
| P0-3 | Fusion de produits sur la ressemblance du titre : un prix, une remise, des alternatives et une alerte d'un autre produit | `bench.cadre` (3 écarts P0) ; `market._find` | Lot 1 : plus de fusion au titre ; le titre propose un candidat à revoir (`review`), jamais une fusion | Monter le seuil à 90 % : ferait passer WGG244Z0FR/Z1FR (86 %), mais un titre plus long à un caractère près fusionnerait encore |
| P0-4 | Mentions légales absentes (éditeur, directeur de publication, hébergeur). L'information RGPD de « Comment ça marche » dit ce qui est gardé, une partie des durées et l'effacement, mais ne nomme ni le responsable du traitement, ni les bases légales, ni le contact pour exercer ses droits, ni la réclamation auprès de la CNIL | `App.jsx` : « Vos données », pas de page légale | Lot 5 : une page « Mentions légales et données personnelles » ajoutée en pied de page, sans toucher aux écrans validés. Elle demande l'identité légale (D2) et votre accord (front) | Ouvrir sans : obligation légale ([LCEN, art. 6-III](https://cms.law/fr/fra/a-la-une/editeurs-de-site-internet-soignez-vos-mentions-legales) ; RGPD, art. 13) |
| P0-5 | Droit de lire les sites : la lecture automatisée respecte robots.txt et se présente, mais les conditions d'utilisation de chaque enseigne et celles de son programme ne sont pas vérifiées | `collect/retailers.py` : constats publics du 18/10, « à confirmer » | Lot 3 : pour chaque source, flux du programme d'abord ; sinon lecture des fiches seulement si les conditions le permettent, avec la trace de la vérification | Lire une enseigne sans vérifier : le cadre l'interdit (« aucun contournement », « respect des contrats ») |

### P1 : avant l'ouverture

| # | Risque | Preuve | Réponse retenue |
|---|---|---|---|
| P1-1 | Pas de connecteur de flux CSV/XML/JSON : aucun lot, aucune trace brute, aucun rejeu | § 3 | Lot 2 : un connecteur générique (mise en correspondance des colonnes par source), une table des lots, le fichier brut gardé, le rejeu idempotent |
| P1-2 | Remises non qualifiées le premier mois : 81 % de précision, 18 % confirmées par une preuve. Le pied de page dit pourtant « remises vérifiées » sous chaque écran | `bench.deals_truth` ; `App.jsx` l. 1420 ; `judge.py` | **Pré-collecte silencieuse** de 3 semaines au moins avant d'ouvrir (D3). À l'ouverture, l'historique existe et les remises sont confirmées (99 % en régime établi), sans rien changer au front ni aux règles. Règle des annonces de réduction (prix de référence = plus bas des 30 derniers jours, [Code de la consommation, art. L112-1-1](https://www.dalloz-actualite.fr/document/ord-n-2021-1734-du-22-dec-2021-jo-23-dec)) à faire valider par un juriste pour la reprise des remises par une plateforme |
| P1-3 | Disponibilité inconnue promise (alerte, meilleure offre) | `bench.cadre` | Lot 1 : une alerte ne part que sur une offre dite en stock ; à prix égal, la meilleure offre préfère une disponibilité connue ; part des « inconnues » mesurée par source (lot 3) |
| P1-4 | Déploiement sans version ni retour arrière ; une migration rend l'ancien code inutilisable | `deploy/README.md` | Lot 4 : versions datées (`/opt/deals/releases/<version>` + lien `current`), sauvegarde avant migration, tests de fumée, `deploy/rollback.sh` (code et, si migrée, base) |
| P1-5 | Sauvegardes sur le même disque que la base | `deploy/deals-backup.service` | Lot 4 : copie quotidienne hors du serveur (D4) et restauration testée chaque mois |
| P1-6 | Sonde extérieure non branchée : si la machine tombe, personne n'est prévenu | `docs/RUNBOOK.md#sonde` | Lot 4 : sonde HTTP sur `/api/r/health` (D4) |
| P1-7 | Pas de préproduction pour répéter déploiement, migration et retour arrière | `deploy/` | Lot 4 : une instance `staging` sur le même serveur (base, port, sous-domaine à part) |
| P1-8 | HSTS absent ; la page `/robot` annoncée par le robot n'existe pas | `bench.cadre` | Lot 4 : en-tête HSTS dans Caddy ; page `/robot` statique servie par Caddy (qui lit, pourquoi, contact, comment refuser), sans toucher à l'app |
| P1-9 | E-mails de connexion en indésirables sans SPF, DKIM, DMARC : la connexion par lien casse | `accounts.py` (SMTP) | Lot 4 : DNS du domaine (D2, D4), essai d'envoi vers 3 messageries |
| P1-10 | Nom : l'app s'appelle « Deals », le cadre « Promo Central » ; il touche domaine, e-mails, robot, mentions | `App.jsx`, `deals.env.example` | Décision D2 : renommer l'app est un changement de front, il attend votre accord |

### P2 : après l'ouverture

| # | Risque | Réponse |
|---|---|---|
| P2-1 | Frais de livraison non lus : le prix montré est celui de l'article | Lus depuis les flux qui les donnent (lot 2) ; les montrer est un choix de front, reporté |
| P2-2 | Pas de CSP | CSP par empreinte du script de `app.html`, calculée au build : sans effet visible, à faire après l'ouverture avec le parcours e2e |
| P2-3 | Aucune limite de débit en lecture (un fil par connexion) | Surveiller (latence, erreurs) ; limite dans Caddy si le trafic le demande |
| P2-4 | `App.jsx` d'un seul tenant (1 430 lignes) | Découpage reporté : le front est gelé, le parcours e2e le protège |
| P2-5 | Métriques : celles des sources, de la quarantaine, du catalogue et des clics existent (`status`, `metrics`, rapport du matin, journal JSON) ; manquent la latence et les erreurs de l'API, les erreurs JS, le disque | Latence et erreurs de l'API dans le journal, puis un tableau de bord, après l'ouverture ; la sonde du lot 4 couvre la disponibilité et le certificat |
| P2-6 | Deux cycles d'imports (`extract.categories` ↔ `ontology`, `catalog` ↔ `profile`) | Sans effet aujourd'hui ; à défaire si l'un des modules grossit |

## 6. Périmètre de lancement proposé

| Inclus | Reporté |
|---|---|
| 2 à 4 sources confirmées (D1), dont au moins une par flux | Les autres enseignes ; Conforama, Darty et Amazon restent désactivées |
| Les rayons qui passent l'audit de l'échantillon réel (lot 3), dans les 4 familles suivies | Les rayons sous le seuil, jusqu'à correction |
| Catalogue canonique, offres et prix tracés, rapprochement prudent | Rapprochement « intelligent » au-delà de l'EAN et de la référence fabricant |
| Le front v62 tel quel : recherche, entonnoir, fiche, missions, Profil | Toute refonte |
| Exploitation : versions, retour arrière, sauvegarde hors serveur, sonde, runbook | PostgreSQL, conteneurs, files de messages |

Le périmètre se règle par les données, pas par le code. Les rayons non retenus ne sont simplement pas publiés.
L'entonnoir s'y adapte déjà : avec six rayons ou moins, la question « Quel univers ? » n'est pas posée (règle v60,
`funnel.py`).

## 7. Décisions à confirmer (J3)

| # | Décision | Proposition par défaut | Ce qui attend sans elle |
|---|---|---|---|
| D1 | Programmes d'affiliation : lesquels sont acceptés ou demandés, sur quels réseaux, avec quels flux | Demander les programmes des enseignes suivies, Boulanger (Kwanko, flux annoncés) en premier ; partir avec 2 à 4 acceptés | Lot 2 (le premier vrai flux), lot 3 et l'ouverture |
| D2 | Identité : nom affiché (Deals ou Promo Central), société éditrice, directeur de publication, domaine | Garder « Deals » dans l'app (front validé) ; vous fournissez l'identité légale et le domaine | Mentions légales, robot, DNS des e-mails |
| D3 | Pré-collecte silencieuse avant d'ouvrir | La collecte tourne sur le serveur dès J12, sans public ; ouverture au plus tôt 3 semaines après | Remises confirmées à l'ouverture (P1-2) |
| D4 | Comptes de service : hébergement, copie des sauvegardes, SMTP, sonde | Hetzner CX23, Storage Box, Brevo, une sonde gratuite (Healthchecks ou UptimeRobot) | Lot 4 |
| D5 | Page légale en pied de page, et seulement elle | Oui : une page de plus, aucun écran validé ne change | P0-4 |

## 8. Plan de changement par lots

Chaque lot a des tests, un critère d'acceptation, un plan de migration et un retour arrière. Un lot se livre en un
commit et un zip vérifié depuis un dossier propre. 15 à 20 % du temps reste réservé aux imprévus.

**Lot 1. Socle des données (J4–J7, aucune décision requise)**
- *Rapprochement prudent* (`market.py`) :
  - l'EAN, puis la marque avec la référence fabricant exacte, rattachent comme aujourd'hui ;
  - deux références différentes ne se rattachent jamais ;
  - le titre seul ne fusionne plus : il crée un produit marqué `needs_review`, avec son candidat, que
    `deals.py review` liste.
- *Disponibilité* (`missions.py`, `publish.py`) : une alerte ne part que sur une offre dite en stock ; à prix
  égal, la meilleure offre préfère une disponibilité connue.
- *Fichiers* : `deals/market.py`, `deals/missions.py`, `deals/publish.py`, `deals/cli.py` (`review`) et leurs tests.
- *Migration* : aucune. La base de production est vide ; une base existante garde ses rapprochements et `review` les
  liste.
- *Critère d'acceptation* :
  - `bench.cadre` : 0 écart P0 côté données, P1-3 levé ;
  - tous les tests passent ;
  - `bench.deals_truth`, `bench.alternatives`, `bench.search` et le parcours e2e sont inchangés (le marché simulé a
    des EAN).
- *Risque* : de vrais doublons sans EAN ni référence restent deux produits jusqu'à la revue. C'est assumé : un doublon
  coûte une comparaison, une fusion fausse coûte un prix faux.
- *Retour arrière* : `git revert`, redéployer (aucune donnée à reprendre).

**Lot 2. Connecteur de flux (J8–J12, D1 pour le premier vrai flux)**
- *Contrat d'une source* : `kind` (`page` ou `feed`), identifiant, transport (adresse, secrets dans `deals.env`),
  format (CSV, TSV, XML, JSON, JSONL ; compressé ou non) et mise en correspondance des colonnes par source
  (`/etc/deals/feeds/<source>.json` : titre, EAN, marque, référence, prix, prix barré, disponibilité, catégorie
  déclarée, adresse de la fiche, frais de livraison, « plus bas 30 jours »).
- *Un lot par lecture* : table `batches` (source, début, fin, statut, reçus, acceptés, rejetés, ignorés, empreinte
  SHA-256, version du connecteur) et fichier brut gardé 14 jours (compressé).
- *Rejeu* : `deals.py feed <source> [--replay <lot>]`. Le même fichier ne crée ni doublon ni ligne de prix
  (l'empreinte, puis l'écriture au changement déjà en place dans `market`).
- *Le flux produit les mêmes offres que l'extraction* : mêmes garde-fous (devise, prix barré validé, seuils,
  quarantaine). Une ligne invalide est rejetée avec sa raison, sans arrêter le lot.
- *Un flux incomplet ne supprime rien* : les offres absentes vieillissent comme une page non relue (au-delà de 3
  jours, plus montrées) et la garde de publication (−20 %) reste.
- *Fichiers* : `deals/collect/feed.py` (nouveau), `deals/sources.py`, `deals/store.py` (migration 13 : `batches`),
  `deals/night.py`, `deals/cli.py`, `tests/test_feed.py` (fixtures CSV et XML, rejeu, flux tronqué, ligne
  invalide), `bench/cadre.py`.
- *Migration* : v12 → v13, ajout d'une table, sans recopie ; testée sur une copie de base.
- *Critère d'acceptation* : un lot ingéré, contrôlé, rejoué sans doublon et audité (`events`, `batches`). Puis, D1
  confirmée, le flux réel d'une enseigne lu de bout en bout et comparé à 20 fiches à la main.
- *Retour arrière* : désactiver la source (`deals.py sources disable`) ; la table v13 reste, sans effet.

**Lot 3. Preuve sur les données réelles (J10–J16, D1, serveur prêt)**
- `discover`, `diagnose` (verdict par enseigne), `sample`, `build` sur chaque source confirmée.
- Audit à la main de 20 offres par source et par famille : prix, prix barré, disponibilité, EAN, catégorie, rayon,
  type. Les seuils de garde sont fixés sur cet échantillon, pas inventés.
- Les rayons qui passent sont publiés ; la pré-collecte démarre (D3).
- *Critère d'acceptation* : sur l'échantillon, 0 prix faux publié ; les écarts restants sont documentés par source.

**Lot 4. Exploitation (J13–J24, D4)**
- `deploy/release.sh` : archive datée du commit, installation dans `releases/`, sauvegarde, migration, bascule du
  lien, tests de fumée (accueil, recherche, fiche, `out`, `health`) ; `deploy/rollback.sh` : retour au lien
  précédent et, si la base a migré, à la sauvegarde d'avant.
- Copie des sauvegardes hors du serveur et restauration mensuelle vérifiée.
- Instance `staging` ; HSTS ; page `/robot` ; sonde extérieure ; SPF, DKIM et DMARC.
- *Critère d'acceptation* : en préproduction, déploiement, migration, retour arrière et restauration répétés de
  bout en bout, chronométrés dans le runbook.

**Lot 5. Conformité (J17–J24, D2, D5)**
- La page légale en pied de page.
- La note du juriste sur la reprise des remises et sur la lecture des sites, gardée avec chaque source.
- *Critère d'acceptation* : page relue, liens vérifiés sur téléphone et ordinateur, parcours e2e inchangé ailleurs.

**Lot 6. Préproduction et ouverture (J25–J30)**
- Gel à J20 : seules les corrections passent.
- À J27, rien de neuf ne part sans avoir été répété en préproduction.
- Répétition générale (déploiement, retour arrière, restauration, incident simulé avec le runbook), décision
  go/no-go, version taguée, ouverture, surveillance renforcée la première semaine.

## 9. Checklist go/no-go

1. Tests, build reproductible, parcours e2e et audit d'accessibilité : verts sur la version taguée.
2. `bench.cadre` : 0 écart P0 ; les P1 restants acceptés par écrit.
3. Au moins 2 sources partenaires actives, leur lien affilié vérifié par un clic réel remonté dans le réseau.
4. Audit de l'échantillon réel signé : 0 prix faux publié ; rayons publiés listés.
5. Pré-collecte d'au moins 3 semaines : la part des remises confirmées par une preuve est mesurée et acceptée.
6. Page légale en ligne ; note juridique sur les remises et la lecture des sites.
7. Sauvegarde hors serveur de la nuit précédente, restauration testée dans le mois.
8. Retour arrière répété en préproduction (code et base), durée notée.
9. Sonde extérieure active ; e-mail du responsable reçu sur un incident simulé ; e-mail de connexion reçu hors
   indésirables chez 3 messageries.
10. Runbook relu : collecte manuelle limitée, diagnostic d'une enseigne en panne, quarantaine, rejeu d'un lot,
    republication de la dernière version saine, restauration, destinataire des alertes.

## 10. Compromis et travaux reportés

**Gardé de l'existant**, parce que ça fonctionne et que c'est vérifié : la lecture des fiches (extraction, robots,
blocages reconnus, quarantaine, agent de nuit) reste la source des enseignes sans flux. Le reste se garde aussi :
le seul écrivain du marché, la publication d'un bloc avec sa garde, SQLite, la bibliothèque standard.

**Ce que le cadre propose et qui n'est pas retenu, front gelé (v60 à v62 validés) :**
- historique de prix et autres vendeurs sur la fiche : l'historique est retiré (v60), et la fiche ne montre qu'une
  enseigne, par choix produit ;
- découpage d'`App.jsx` et jetons de design : reportés, le front est gelé ; panneau « Tous les critères » : remplacé
  par l'entonnoir validé ;
- « pas de feed infini » : le feed de la Recherche et la sélection de l'accueil restent tels qu'ils ont été validés.

**Reporté après l'ouverture** :
- frais de livraison affichés, CSP, limite de débit, tableau de bord ;
- rapprochement au-delà de l'EAN et de la référence, photos des enseignes (droits à trancher) ;
- personnalisation au-delà des préférences explicites et des signaux simples déjà en place.
