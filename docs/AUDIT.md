# Audit et nettoyage du dépôt avant la mise en production (1er novembre 2026)

Cadre suivi : « Promo Central — README : nettoyage du projet, préparation et déploiement OVH en production ».
Un seul projet, nettoyé et cohérent ; le guide de déploiement vérifié contre le code final. État audité : la v26
livrée (commit `2ca25aa`) ; état final : ce commit. L'audit précédent (refonte d'octobre 2026) reste dans git :
`git show 2ca25aa:docs/AUDIT.md`.

**Verdict.** Le code était sain : aucun module mort, aucune définition inutilisée, aucune dépendance hors de la
bibliothèque standard, aucun secret ni donnée personnelle, ni dans l'arbre ni dans l'historique. Le désordre était dans
la documentation (19 captures d'anciennes versions, des pages qui décrivaient des écrans ou des règles disparus) et
dans le chemin de déploiement : le rejouer sur un serveur simulé a fait tomber cinq défauts qui auraient bloqué ou
faussé la mise en ligne, tous corrigés et couverts par un test. Aucun code applicatif n'a été retiré ; aucun écran,
aucune règle métier, aucun réglage de sécurité n'a changé.

## 1. Audit préalable

| Point | Constat (mesuré) |
|---|---|
| Inventaire | 155 fichiers suivis : `deals/` 58, `docs/` 28 (dont 19 images), `tests/` 25, `deploy/` 15, `web/` 13, `bench/` 12, racine 4 ; `.git` 18 Mo en objets non compactés |
| Points d'entrée | `deals.py` (la ligne de commande) ; services `deals-web` (`serve`), `deals-daily` (`nightly`), `deals-backup` (`backup`) ; commande d'exploitation `deploy/deals` (`systemd-run`, compte `deals`) ; servis : `web/app.html` (polices incluses au build) et `web/robot.html`, l'API `/api/r/` |
| Imports | graphe complet, imports dans les fonctions compris : les 53 modules du paquet sont atteints depuis `deals.py` ; le marché simulé (`sim.py`, `demo.py`) n'est chargé que par la commande `demo` (vérifié : absent après l'import de la ligne de commande) |
| Code mort | aucune définition de premier niveau citée nulle part ailleurs (code, tests, bancs, déploiement, documentation) |
| Dépendances | bibliothèque standard seulement (`typing_extensions` n'apparaît que sous `TYPE_CHECKING` dans Protego, embarqué) ; pour reconstruire `app.html` seulement : esbuild 0.28.2, react et react-dom 19.2.8 (`web/build.sh`), sans `node_modules` dans le dépôt ; polices sous OFL avec leurs licences ; code et corpus de tiers avec leurs mentions (`THIRD_PARTY_NOTICES.md`) |
| Secrets, données personnelles | arbre et historique entier : aucun mot de passe, jeton, clé, `.env` réel ni base ; seulement des adresses d'exemple ou de test (et le contact professionnel public d'une société dans le corpus de tests d'extruct, tiers, BSD) ; auteur des commits `Claude <noreply@anthropic.com>`, aucun dépôt distant configuré |
| Tests et contrôles, avant | compilation : ok ; 254 tests ok sous Python 3.11 (51 s), 3.12 (59 s), 3.13 (60 s) ; les 11 bancs tournent (code 0) ; `bench.cadre` 16/19, 0 écart P0 |

## 2. Retiré

Rien de ce qui est retiré n'était appelé par le code, le packaging (`release.sh package` archive ce que git suit) ou le
déploiement (vérifié par recherche dans tout le dépôt). Tout reste dans l'historique git.

| Fichiers | Raison |
|---|---|
| `docs/ux/*.png` (19 images, 6,0 Mo) | captures des versions v46 à v60, citées seulement par l'historique de `docs/UX.md` |
| `docs/UX.md` : les mesures version par version (v41 à v63), 647 → 85 lignes | décrivaient des écrans disparus (« Une envie précise ? » sur l'accueil, « Peu importe », les recherches sauvegardées dans la Recherche, la jauge de la fiche) ; la page décrit l'interface telle qu'elle est |
| `docs/AUDIT.md` (audit d'octobre) | contredit par le code (rapprochement au titre, 35 tests) ; remplacé par ce compte rendu |
| `docs/PRODUCTION.md` : la baseline v24, la cartographie, l'hypothèse des flux, les plans des lots faits, 338 → 94 lignes | constat d'un état dépassé ; la page dit les décisions, les risques ouverts, le chemin jusqu'à l'ouverture et le go/no-go |
| Objets git en vrac (`git gc`) | le dépôt passe de 18 à 9 Mo, historique intact (`git fsck` sans erreur) |
| Artefacts générés par les tests | chaque passe laissait ~130 dossiers et ~90 Mo dans le dossier temporaire du système (mesuré) ; les tests écrivent désormais dans un dossier propre à la passe, effacé à la fin (`tests/__init__.py`) : 0 fichier laissé |

## 3. Gardé, et pourquoi

| Fichiers | Raison |
|---|---|
| `deals/` (53 modules), `deals.py` | tous atteints depuis le point d'entrée, chaque définition utilisée |
| `deals/vendor/protego/` et sa licence, `deals/ontology/*.json` | lecture de robots.txt ; données de référence de l'ontologie, lues au démarrage |
| `deals/sim.py`, `deals/demo.py` | le marché simulé de `deals.py demo` et des tests (dont la preuve que les flux nourrissent l'app comme les fiches) ; jamais chargés en production |
| `tests/` (263 tests) et `tests/corpus/` | chaque test vérifie un comportement actuel ; corpus de tiers avec leurs mentions |
| `bench/` (11 bancs) | chacun tourne et porte une mesure citée par `README.md` ou `docs/ARCHITECTURE.md` ; `bench.cadre` est dans le go/no-go |
| `web/src/`, `web/build.sh`, `web/fonts/` et licences OFL, `web/app.html`, `web/robot.html` | les sources, le build, les polices embarquées (licences obligatoires), les deux pages servies |
| `deploy/` | tout est utilisé par le guide (vérifié par `tests/test_deploy.py`) |
| `docs/` : ARCHITECTURE, RUNBOOK, AUTONOMIE, ONTOLOGIE, RECHERCHE, PERSONNALISATION, PRODUCTION, UX | l'exploitation (le runbook : ses ancres sont citées par le code), les règles du produit, la mise en production ; contradictions corrigées |

## 4. Corrigé en rejouant le déploiement

Le guide (`deploy/README.md`, réécrit pour un VPS OVHcloud selon le cadre) a été rejoué sur ce conteneur comme sur le
serveur : compte `deals`, `/opt/deals/releases`, `/var/lib/deals`, `/var/backups/deals`, `/etc/deals`, `sudo deals`,
services lancés comme systemd les lance (compte, dossier, fichier d'environnement), un flux Google Shopping servi en
local, un relais SMTP local. Ce qu'il a trouvé :

| Défaut | Effet sur le serveur | Correction | Preuve |
|---|---|---|---|
| L'archive d'une version, restée à la racine du dépôt, compte comme une modification | la mise à jour suivante (`release.sh package`) refusait de partir | `promocentral-*.tar.gz` ignoré par git | `tests/test_release.py` |
| HEAD répondait 501 | `curl -I` (le guide et le cadre l'utilisent) et les sondes qui interrogent en HEAD voyaient le site en panne | HEAD sur la page, `/robot` et `/api/r/health` ; 405 ailleurs, pour qu'un aperçu de lien ne rejoue ni un clic ni un lien de connexion | `tests/test_accounts.py` (dont l'absence de corps, sur une connexion gardée ouverte) |
| L'app lit les partenaires à son démarrage | après l'ajout d'un partenaire, ses clics partaient sans lien de suivi jusqu'au redémarrage | le guide et le runbook redémarrent `deals-web` après toute modification de `deals.env` ou `affiliate.json` | rejoué : le clic part par le lien du réseau |
| Copier le modèle de partenaires (ce que le cadre demande) déclarait Boulanger et But avec de faux liens | une source activée trop tôt aurait été publiée avec des liens fictifs | les clés du modèle ne désignent aucune enseigne | `tests/test_deploy.py` ; rejoué : « clé absente des sources » |
| L'échantillon d'un flux se téléchargeait avec `curl` et son adresse | les identifiants du réseau restaient dans l'historique du shell | `deals probe --source <clé>` : lu à l'adresse de la source, même désactivée, jamais affichée, même dans une erreur | `tests/test_ingest.py` |

Et, en vérifiant le guide contre le code :
- Ubuntu 22.04 était proposée alors que son Python est le 3.10 : retirée ; Python 3.11 vérifié par `deals.py` et
  `release.sh`, qui s'arrêtent avec la cause.
- La nuit était activée avant tout partenaire : elle se serait arrêtée en erreur chaque nuit. Elle s'active au § 9.
- Six sources d'exemple n'avaient pas leur variable dans `deals.env.example` : ajoutées.
- Sauvegardes sur le même disque que la base : la copie chiffrée hors du serveur est outillée (`deals-offsite`,
  restic, chaque jour à 6 h 30, 30 jours puis un par mois sur un an, vérification du dépôt), avec la procédure et
  l'essai de restauration ; elle s'active avec un stockage objet (§ 10).
- Le bloc `www` du Caddyfile, prêt à décommenter ; les minuteurs et l'en-tête `Server` portaient encore « DEALS ».
- Documentation contredite par le code : le coût (OVHcloud, plus Hetzner), les mesures de la Recherche (62 phrases,
  0 impasse, 43/43), les recherches sauvegardées (au Profil depuis la v61), les enseignes « actives », les lignes
  « Interface v56 / v58 » de l'architecture, l'objet de l'e-mail du matin, la fiche du runbook citée par `release.sh`.
- `tests/test_deploy.py` garde les fichiers de déploiement alignés sur le code : chaque variable d'exemple est un
  réglage lu, chaque `${VAR}` des sources a sa ligne, aucune source d'exemple active, le modèle de partenaires n'en
  déclare aucun, chaque service lance une commande que le code connaît sous le compte `deals`, Caddy relaie vers
  `127.0.0.1:8000` où l'app écoute. Six dérives introduites exprès : toutes détectées. Les nouveaux tests ont été
  vérifiés de même (le secret affiché dans une erreur, la source désactivée non lue, un corps envoyé sur un HEAD, un
  clic rejoué sur un HEAD : chaque fois détectés).

## 5. Validation après nettoyage

| Contrôle du cadre | Résultat |
|---|---|
| 1. Syntaxe et compilation | `compileall` : ok |
| 2. Tests | 263 ok sous Python 3.11 (50 s), 3.12 (54 s), 3.13 (55 s) |
| 3. Imports et démarrage | 53 modules sur 53 ; l'app démarre en production (`DEALS_ENV=prod`, mentions légales renseignées) et refuse sans elles (vu au rejeu) |
| 4. Front, polices, `/robot`, routes publiques | `app.html` reconstruit à l'octet près (SHA-256 identique), 4 polices incluses, aucune ressource extérieure ; dans Chromium, sur la démo nourrie par flux : parcours complet 85 étapes sur 85, aucune erreur JavaScript ; audit d'accessibilité de 92 écrans (contrastes, zones à toucher, noms) : 0 défaut |
| 5. Tests de fumée | `deploy/smoke.py` : 7/7 après l'installation, après une restauration, après un retour arrière |
| 6. systemd, Caddyfile, `release.sh` | `systemd-analyze verify` des 7 unités : aucune remarque ; Caddyfile : relais vers `127.0.0.1:8000` vérifié par test (Caddy lui-même n'est pas installable ici) ; `release.sh` : installation, mise à jour avec migration, retour arrière (base restaurée), version cassée refusée et retirée d'elle-même |
| 7. Rapport | ce document |

Rejeu du guide, sections 5 à 11 : **53 vérifications sur 53** — installation (version immuable, code à root), réglages
(`deals.env` root 600 ; partenaires et sources root:deals 640), la base créée par le compte `deals`, services, la nuit
qui refuse de tourner sans partenaire en disant pourquoi, fumée, HSTS, `/admin` 404, l'app sur `127.0.0.1:8000`
seulement, `/api/r/health` 503 avant la première nuit puis 200, `probe --source` sans jamais afficher l'adresse,
lot à blanc qui n'écrit rien, premier lot (90 offres) et fichier brut gardé, publication, un clic qui part par le lien
du réseau avec son identifiant, la nuit et son rapport, un lien de connexion parti par le SMTP réglé vers l'adresse
publique, sauvegarde et restauration (même catalogue), copie hors du serveur inerte tant qu'elle n'est pas réglée,
mise à jour avec migration puis retour arrière, version cassée refusée ; à la fin, rien d'écrit par le compte
`deals` hors de ses dossiers, aucune base ni fichier de flux dans le code, rien laissé à root dans `/var/lib/deals`.

Bancs, avant → après : mêmes résultats, aux temps de calcul près (`extraction`, `deals_truth`, `alternatives`,
`missions`, `search`, `ontologie`, `aspirateurs`, `profiles`, `autonomy`, `scale`) ; `bench.cadre` 16/19 → 17/19
(0 écart P0 ; restent la remise sans référence le premier mois, réglée par la pré-collecte, et la CSP, après
l'ouverture).

## 6. Réserves : ce qui ne se vérifie que sur le serveur

- `apt`, DNS, pare-feu (UFW et celui d'OVHcloud), Caddy et son certificat, SSH par clé : commandes officielles, à
  dérouler sur le VPS (`deploy/README.md` § 2 à 4) ; le guide dit comment vérifier chacune.
- La copie hors du serveur n'a pas été exécutée contre un vrai stockage (restic absent ici) : l'unité et la procédure
  suivent la documentation de restic et d'OVHcloud Object Storage ; l'essai de restauration est un point go/no-go.
- Le cloisonnement systemd (`ProtectSystem`, `ReadWritePaths`) n'est pas imité par le rejeu : il a vérifié après coup
  que le compte `deals` n'avait rien écrit hors de ses dossiers.
- Le SMTP réel (SPF, DKIM, DMARC) et la sonde extérieure dépendent de vos comptes (D4).
- Aucun flux réel n'a encore été lu (D1) : la correspondance de chaque flux s'écrit sur son échantillon.
- Le parcours e2e et l'audit d'accessibilité (Chromium), le harnais de mutations et le rejeu du déploiement sont des
  outils de vérification de cette session, hors du dépôt (ils modifient le système ou dépendent d'un navigateur) ;
  leurs résultats sont consignés ici.
