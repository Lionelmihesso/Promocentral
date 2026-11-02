# Mettre Promo Central en production sur un VPS OVHcloud

Un seul projet, un seul serveur. Nom de code technique : `deals` (commande, services, dossiers, compte système) ; le
nom affiché est Promo Central. Ce guide a été rejoué de bout en bout sur un serveur simulé (compte `deals`, dossiers et
services de ce guide, sections 5 à 11) : voir `docs/AUDIT.md`. Ce qui dépend de vos comptes (DNS, Caddy et son
certificat, pare-feu, SMTP, stockage objet) se vérifie sur le serveur, aux étapes indiquées.

**Architecture** : Python 3.11 ou plus récent, bibliothèque standard uniquement (aucun `pip install`, aucun
environnement virtuel), SQLite 3.35 ou plus récent, Caddy pour le HTTPS. L'app écoute sur `127.0.0.1:8000` seulement ;
Caddy est la seule porte d'entrée.

```
Code, par versions (jamais modifiées)   /opt/deals/releases/<version>/      /opt/deals/current → la version en service
Données (base, flux bruts, rapports)    /var/lib/deals/                     propriétaire deals, droits 750
Sauvegardes locales                     /var/backups/deals/                 propriétaire deals, droits 750
Réglages                                /etc/deals/deals.env                root, 600 : secrets (SMTP, adresses des flux)
                                        /etc/deals/affiliate.json           root:deals, 640 : enseignes partenaires
                                        /etc/deals/sources.json, feeds/     root:deals, 640 : sources et correspondances
                                        /etc/deals/offsite.env              root, 600 : copie hors du serveur (§ 10)
Compte système                          deals (sans shell, sans mot de passe)
Commande d'exploitation                 /usr/local/bin/deals → « sudo deals <commande> »
Services                                deals-web (l'app), deals-daily.timer (la nuit, 3 h), deals-backup.timer (6 h),
                                        deals-offsite.timer (6 h 30, copie chiffrée hors du serveur)
```
La base, les fichiers bruts des flux et les réglages ne sont jamais dans le dossier du code : une version s'installe
et se retire sans y toucher.

## Démonstration : démarrer en une commande

Le mode démo (`DEALS_ENV=demo`) montre la plateforme avec un marché **simulé et fictif** : aucune mention légale, aucun
e-mail, aucun flux ni partenaire réel, aucune nuit qui lit des sites. Il ne relâche aucun contrôle de production : la
production (`DEALS_ENV=prod`) refuse toujours une configuration incomplète.

Prérequis sur le serveur (testé avec Python 3.13 et 3.14, SQLite 3.45 ; Ubuntu 26.04 à valider sur le VPS) : accès SSH avec
`sudo`, systemd, Python 3.11 ou plus récent, SQLite 3.35 ou plus récent, git.

```
sudo apt update && sudo apt install -y git python3 sqlite3 ufw
git clone https://github.com/Lionelmihesso/Promocentral.git ~/promocentral
cd ~/promocentral
sudo sh deploy/install.sh demo                      # installe, initialise la base, remplit le marché simulé, démarre l'app
sudo sh /opt/deals/current/deploy/verify.sh         # vérifie : configuration, service, écoute locale, tests de fumée
```

`install.sh` ne lance que `deals-web` : aucune nuit réelle, aucune sauvegarde externe, aucun e-mail. Il crée le compte
`deals`, les dossiers (`/opt/deals`, `/var/lib/deals`, `/var/backups/deals`), `/etc/deals/deals.env` (droits 600, modèle
`deploy/deals.demo.env.example`) et les unités systemd, puis passe par `release.sh` : une version qui échoue ses tests
de fumée ou dont la configuration est refusée n'est jamais basculée.

**Voir la démo** : le port 8000 n'est jamais ouvert sur Internet. Depuis votre ordinateur :
```
ssh -L 8000:127.0.0.1:8000 <utilisateur>@<IPv4 du VPS>
```
puis http://127.0.0.1:8000/ dans votre navigateur. Un bandeau indique que les données sont fictives.

**Mettre à jour depuis GitHub** (sur le VPS, dans le clone) :
```
cd ~/promocentral
git status --short                          # doit être vide : sinon l'installation est refusée
git pull --ff-only origin main
sudo sh deploy/install.sh demo              # même commande qu'à l'installation : la base est conservée
sudo sh /opt/deals/current/deploy/verify.sh
```
Une sauvegarde de la base est prise avant chaque bascule, la nouvelle version passe ses tests de fumée avant d'être
gardée, et une version refusée ou en échec ramène la précédente. **Revenir en arrière** à la main :
`sudo sh /opt/deals/current/deploy/release.sh rollback`.

**Compatibilité** : testé ici avec Python 3.13 et 3.14 (la suite de 288 tests passe sur les deux). Ubuntu 26.04 n'était
pas accessible depuis l'environnement de développement : `install.sh` vérifie la version de Python et de SQLite avant
toute installation et s'arrête avec la cause ; à confirmer sur le serveur avec `python3 -V`.

**Arrêter** : `sudo systemctl disable --now deals-web`.

Ce que la démo ne fait pas, par construction : la page « Mentions légales » ne publie aucune identité ; les liens de
connexion s'écrivent dans `/var/lib/deals/outbox.log` (lisible par `deals` seul) au lieu de partir par e-mail ; les
commandes qui lisent des sites ou envoient des e-mails répondent « indisponible en mode démo ».

## 1. Commander le VPS

Un VPS d'entrée de gamme suffit (VPS-1 : 2 vCore, 4 Go, 40 Go ; la plateforme publie 3 000 produits en ~3 s par nuit).
Système : **Debian 12** (Python 3.11, SQLite 3.40) ou **Ubuntu 24.04 LTS** (Python 3.12, SQLite 3.45). Pas Ubuntu
22.04 : son Python est le 3.10, le code demande 3.11 (`deals.py` et `release.sh` s'arrêtent avec la cause).
Ajoutez votre clé SSH publique à la commande. La sauvegarde quotidienne de la machine (7 jours) proposée par OVHcloud
s'ajoute aux sauvegardes de la base (§ 10), elle ne les remplace pas. Notez l'IPv4 publique du VPS.

## 2. DNS du domaine

Dans la zone DNS du domaine (par exemple `promocentral.fr`) : un enregistrement **A** vers l'IPv4 du VPS ; un **A**
pour `www` seulement si vous voulez servir `www` (le Caddyfile a un bloc prêt à décommenter, qui redirige vers
l'adresse principale) ; un **AAAA** seulement si l'IPv6 est configurée et joignable sur le VPS. Attendez la
propagation avant le § 7 (le certificat HTTPS en dépend) :
```
getent ahostsv4 promocentral.fr            # doit donner l'IPv4 du VPS
```

## 3. Mettre à jour le système, installer les paquets

Connecté en SSH avec l'utilisateur et la clé donnés à la commande (il a `sudo`) :
```
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3 sqlite3 curl ca-certificates gnupg ufw restic
python3 --version                                                    # 3.11 ou plus récent
python3 -c "import sqlite3; print(sqlite3.sqlite_version)"           # 3.35 ou plus récent (c'est celle qu'utilise l'app)
```
Rien d'autre : ni `pip`, ni environnement virtuel. `restic` sert à la copie
chiffrée des sauvegardes hors du serveur (§ 10), seule dépendance externe, prise dans les dépôts du système.

## 4. Sécuriser le serveur, installer Caddy

SSH par clé seulement. Gardez votre session ouverte et vérifiez qu'une nouvelle connexion passe avant de fermer :
```
echo 'PasswordAuthentication no' | sudo tee /etc/ssh/sshd_config.d/10-promocentral.conf
sudo systemctl reload ssh
```
Pare-feu : SSH, HTTP et HTTPS seulement (pour réserver SSH à votre adresse d'administration, remplacez la première
ligne par `sudo ufw allow from <votre IP> to any port 22 proto tcp`). Le pare-feu réseau d'OVHcloud (espace client)
peut s'ajouter devant, avec les mêmes ouvertures.
```
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```
Le port 8000 n'est jamais ouvert : l'app n'écoute que sur `127.0.0.1` et Caddy lui relaie les requêtes.

Caddy, depuis son dépôt officiel (commandes de caddyserver.com/docs/install, Debian et Ubuntu) ; il s'installe comme
service `caddy`, démarré :
```
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg
sudo chmod o+r /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

## 5. Installer et mettre à jour la production

Depuis un clone propre du dépôt sur le serveur (`install.sh` n'installe que le commit courant ; il refuse un dépôt
modifié) :
```
git clone https://github.com/Lionelmihesso/Promocentral.git ~/promocentral
cd ~/promocentral
sudo sh deploy/install.sh prod
```
`install.sh prod` crée le compte et les dossiers, copie `/etc/deals/deals.env` depuis son modèle (droits 600) et les
enseignes et sources d'exemple (inactives), installe les services et les timers, vérifie la configuration (`deals.py
check` liste ce qui manque et refuse de basculer tant que ce n'est pas réglé), installe la version et lance les tests de
fumée. Il ne démarre aucune enseigne : le § 9 le fait, une enseigne à la fois.

Pour mettre à jour : `git pull` puis la même commande. Pour revenir en arrière : `release.sh rollback` (§ 11).

## 6. Configurer

```
sudoedit /etc/deals/deals.env
sudo deals check                            # ce qui manque, en clair ; « prêt » quand tout est réglé
```
À renseigner (une valeur par ligne, sans commentaire en fin de ligne : systemd le garderait dans la valeur) :
- `DEALS_USER_AGENT` : nom du robot, adresse publique de `/robot`, adresse de contact réelle ;
- `DEALS_PUBLIC_URL` : l'adresse HTTPS définitive (`https://promocentral.fr`) ;
- `DEALS_LEGAL_EDITOR`, `DEALS_LEGAL_REGISTRATION`, `DEALS_LEGAL_ADDRESS`, `DEALS_LEGAL_DIRECTOR`,
  `DEALS_LEGAL_CONTACT`, `DEALS_LEGAL_HOST` : les mentions légales exactes (la production ne démarre pas sans elles) ;
- SMTP : `DEALS_SMTP_HOST`, `DEALS_SMTP_PORT`, `DEALS_SMTP_TLS` (`starttls` sur 587, `ssl` sur 465),
  `DEALS_SMTP_USER`, `DEALS_SMTP_PASSWORD`, `DEALS_MAIL_FROM` ;
- `DEALS_OPERATOR_EMAIL` : une adresse réellement lue (l'agent de nuit y écrit s'il y a lieu) ;
- `DEALS_FEED_<ENSEIGNE>` : l'adresse du flux de chaque enseigne partenaire, identifiants du réseau compris (§ 9) ;
  ces adresses ne vivent qu'ici.

`/etc/deals/affiliate.json` (enseignes partenaires) et `/etc/deals/sources.json` (sources) sont créés depuis leurs
modèles, qui n'activent rien : les clés du modèle de partenaires ne désignent aucune enseigne, et toutes les sources
d'exemple sont désactivées. Une enseigne ne devient active qu'au § 9.

`sudo deals <commande>` lance `deals.py` comme les services : compte `deals`, dossier `/var/lib/deals`, réglages de
`/etc/deals/deals.env` ; vos gestes sont journalisés à votre nom. Gardez le nom du robot (`PromoCentralBot`) dans
`DEALS_USER_AGENT` : les tests de fumée le cherchent sur `/robot`.

**Après toute modification** de `/etc/deals/deals.env` ou de `/etc/deals/affiliate.json` : `sudo systemctl restart
deals-web` (l'app les lit à son démarrage ; la nuit et `sudo deals` les relisent à chaque lancement).

## 7. Activer le HTTPS

`install.sh` a déjà installé et activé les services. Reste Caddy, qui reçoit le HTTPS et relaie vers l'app :
```
sudo cp /opt/deals/current/deploy/Caddyfile /etc/caddy/Caddyfile
sudoedit /etc/caddy/Caddyfile               # promocentral.example.fr → votre domaine (et le bloc www, si besoin)
sudo systemctl reload caddy
systemctl status deals-web caddy --no-pager
systemctl list-timers 'deals-*' --no-pager
```
La nuit (`deals-daily.timer`) n'a rien à lire tant qu'aucun partenaire n'est branché : elle s'active au § 9, avec le
premier partenaire. La copie hors du serveur (`deals-offsite.timer`) s'active au § 10.

**Vérifier** : `sudo sh /opt/deals/current/deploy/verify.sh https://VOTRE-DOMAINE` (configuration, service, écoute sur
127.0.0.1 seulement, tests de fumée).

## 8. Contrôles de mise en production

```
python3 /opt/deals/current/deploy/smoke.py https://VOTRE-DOMAINE        # 7 contrôles, à travers Caddy : tous « ok »
curl -sI https://VOTRE-DOMAINE/ | grep -i strict-transport-security    # HSTS, envoyé par l'app
curl -s https://VOTRE-DOMAINE/api/r/health                             # 503 « critical » tant qu'aucune nuit n'a tourné
curl -s -o /dev/null -w '%{http_code}\n' https://VOTRE-DOMAINE/admin   # 404 : rien d'autre que /, /api/r/ et /robot
sudo ss -ltnp | grep ':8000'                                           # 127.0.0.1:8000 seulement
sudo deals status
sudo deals metrics
journalctl -u deals-web -n 50 --no-pager
```
Vérifiez aussi : la page « Mentions légales » de l'app, complète ; un e-mail réel reçu (connexion depuis l'app :
« Ajouter mon e-mail ») ; depuis une autre machine, le port 8000 fermé (`curl -m 5 http://<IPv4>:8000/` échoue).

## 9. Flux des enseignes et première publication

La plateforme ne montre que des offres de partenaires confirmés. Pour chaque enseigne : l'accord du programme
d'affiliation, l'adresse de son flux et ses conditions d'usage, et le gabarit exact de son lien de suivi (dans
l'espace affilié du réseau). Puis :
```
sudoedit /etc/deals/deals.env               # DEALS_FEED_BOULANGER=https://… (identifiants du réseau compris)
sudo deals probe --source boulanger         # l'échantillon, lu à l'adresse de la source (même désactivée) :
                                            # format, colonnes, correspondance proposée ; l'adresse n'est jamais affichée
sudoedit /etc/deals/feeds/boulanger.json    # la correspondance relue (un flux Google Shopping : {"preset": "google_shopping"})
sudoedit /etc/deals/sources.json            # boulanger : "enabled": true
sudoedit /etc/deals/affiliate.json          # "boulanger": "<gabarit du réseau, avec {url} et {subid}>" ; retirer les clés d'exemple
sudo systemctl restart deals-web            # l'app lit les partenaires au démarrage : sans cela, les clics partiraient sans suivi
sudo deals partners                         # boulanger · feed suivie
sudo deals ingest boulanger --dry-run       # tout lu et contrôlé, rien écrit : offres retenues, refus et raisons
sudo deals ingest boulanger                 # premier lot (sudo deals batches --source boulanger pour le voir)
sudo deals publish
sudo systemctl enable --now deals-daily.timer
```
Avant d'ouvrir au public, relisez 20 offres de chaque enseigne dans l'app, face à son site : titre, prix, prix barré,
disponibilité, adresse, lien de suivi (« Voir l'offre » passe par le réseau, et le clic apparaît dans son espace
affilié), date de fin et cohérence de la promotion. La grille « Du flux à l'écran » (`docs/ARCHITECTURE.md`) dit ce
que chaque champ du flux nourrit, et ce qui se passe quand il manque.

Une enseigne sans flux ne se lit par ses fiches qu'en dernier recours, si ses conditions d'utilisation le permettent
(`docs/PRODUCTION.md`) : `sudo deals discover <enseigne> --per 40`, `diagnose`, `build` (produits rapprochés par EAN,
sinon marque et référence ; un titre semblable n'est qu'un candidat, à revoir avec `sudo deals review`).

## 10. Sauvegardes, supervision, exploitation

**Sauvegarde locale** : `deals-backup.timer`, chaque jour à 6 h (après la nuit de 3 h), à chaud et vérifiée,
14 conservées dans `/var/backups/deals`. Restaurer une sauvegarde — d'abord mettre de côté la base courante, qui contient
les écritures faites depuis (comptes, clics, missions) : elle ne doit jamais être écrasée sans copie :
```
sudo systemctl stop deals-web deals-daily
sudo -u deals python3 -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); assert d.execute('PRAGMA integrity_check').fetchone()[0]=='ok'" /var/lib/deals/deals.sqlite /var/backups/deals/abandonnee-$(date -u +%Y%m%d-%H%M%S).sqlite
sudo rm -f /var/lib/deals/deals.sqlite-wal /var/lib/deals/deals.sqlite-shm   # un journal resté là s'appliquerait à la copie
sudo -u deals cp /var/backups/deals/deals-AAAA-MM-JJ_HHMMSS.sqlite /var/lib/deals/deals.sqlite
sudo systemctl start deals-web
python3 /opt/deals/current/deploy/smoke.py http://127.0.0.1:8000
```

**Copie chiffrée hors du serveur** (obligatoire avant l'ouverture) : `deals-offsite.timer`, chaque jour à 6 h 30,
copie `/var/backups/deals` chiffrée (restic) vers un stockage objet S3, garde 30 jours puis un par mois sur un an, et
vérifie le dépôt. Dans l'espace client OVHcloud, Object Storage : un conteneur S3 (par exemple région GRA) et un
utilisateur S3 qui n'a accès qu'à lui ; notez sa clé d'accès et sa clé secrète. Puis, sur le serveur :
```
sudo cp /opt/deals/current/deploy/offsite.env.example /etc/deals/offsite.env
sudo chmod 600 /etc/deals/offsite.env
openssl rand -hex 32                        # le mot de passe du dépôt : à garder AUSSI hors du serveur (sans lui, rien ne se relit)
sudoedit /etc/deals/offsite.env             # RESTIC_REPOSITORY (s3:https://s3.gra.io.cloud.ovh.net/<conteneur>), RESTIC_PASSWORD, clés S3, région
sudo -i                                     # la suite dans un shell root
set -a; . /etc/deals/offsite.env; set +a; export RESTIC_CACHE_DIR=/var/cache/deals-offsite
restic init                                 # une fois : crée le dépôt chiffré
exit
sudo systemctl enable --now deals-offsite.timer
sudo systemctl start deals-offsite.service && journalctl -u deals-offsite -n 20 --no-pager
```
Essai de restauration (avant l'ouverture, puis chaque mois) :
```
sudo -i
set -a; . /etc/deals/offsite.env; set +a; export RESTIC_CACHE_DIR=/var/cache/deals-offsite
restic snapshots --tag deals
restic restore latest --tag deals --target /root/essai-restauration
ls /root/essai-restauration/var/backups/deals/
python3 -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute('PRAGMA integrity_check').fetchone()[0], c.execute('SELECT COUNT(*) FROM products').fetchone()[0], 'produits')" /root/essai-restauration/var/backups/deals/deals-<la plus récente>.sqlite
rm -rf /root/essai-restauration; exit
```

**Supervision** : une sonde HTTP extérieure (UptimeRobot, Healthchecks ou autre) sur
`https://VOTRE-DOMAINE/api/r/health`, toutes les 5 minutes ; 503 = critique (aucune nuit depuis 36 h, une étape en
erreur, un incident critique ouvert). Elle prévient par un autre chemin que le SMTP de la plateforme. Après chaque
première nuit complète, lisez le rapport (`journalctl -u deals-daily --since today`, et `/var/lib/deals/reports/`).

**Au quotidien** (`docs/RUNBOOK.md` : une fiche par incident ; `docs/AUTONOMIE.md` : ce que l'agent fait seul) :
```
sudo deals status                           # l'état, en quelques lignes
sudo deals approve <n°>                     # exécuter une proposition de l'agent (ou : sudo deals reject <n°>)
sudo deals sources enable <clé>             # reprendre une source mise de côté, la cause réglée
sudo deals quarantine                       # prix suspects retenus ; release <offre> pour un prix vérifié chez l'enseigne
sudo deals events --cid <corrélation>       # tout ce qui s'est passé une nuit donnée
```

## 11. Mettre à jour, revenir en arrière

```
sh deploy/release.sh package                                       # sur votre machine, depuis le dépôt, sur un commit
scp promocentral-<…>.tar.gz <utilisateur>@<IPv4 du VPS>:
sudo sh /opt/deals/current/deploy/release.sh install promocentral-<…>.tar.gz
sudo sh /opt/deals/current/deploy/release.sh list                  # les versions gardées (5), celle en service
sudo sh /opt/deals/current/deploy/release.sh rollback              # la version précédente, en une commande
```
`install` vérifie Python, sauvegarde la base, bascule `current`, redémarre l'app et passe les tests de fumée
(`deploy/smoke.py` : la page, les catégories, une recherche, l'état, les mentions légales, `/robot`, rien d'autre) ;
un test raté ramène aussitôt la version d'avant. La base porte un numéro de schéma, et un code plus ancien que sa base
refuse de démarrer : si la version retirée l'avait migrée, la sauvegarde prise juste avant la bascule est restaurée.
Une version qui change les services (`deploy/*.service`, `*.timer`) demande de les recopier (§ 7) puis
`sudo systemctl daemon-reload`. Essayez une mise à jour et un retour arrière avant l'ouverture.

## 12. Points bloquants avant l'ouverture au public

| Point | Comment le vérifier |
|---|---|
| Domaine et DNS ; HTTPS valide | `getent ahostsv4` (§ 2) ; `smoke.py https://VOTRE-DOMAINE` tout « ok » (§ 8) |
| VPS durci : SSH par clé, seuls SSH, 80 et 443 ouverts | `sudo ufw status verbose` ; port 8000 fermé depuis l'extérieur (§ 8) |
| Mentions légales complètes et exactes ; données personnelles relues | la page « Mentions légales » de l'app ; relecture par un juriste (`docs/PRODUCTION.md`) |
| SMTP opérationnel ; adresse d'exploitation lue | un lien de connexion reçu ; `DEALS_OPERATOR_EMAIL` réelle |
| Au moins un flux réel autorisé, correspondance vérifiée, affiliation confirmée | `sudo deals partners`, `sudo deals batches`, les 20 offres relues et un clic compté chez le réseau (§ 9) |
| Tests de fumée ; recherche, catégories, fiches et redirections vérifiées | `smoke.py` ; un parcours dans l'app jusqu'à « Voir l'offre » |
| Sauvegarde locale et copie externe ; restauration essayée | `ls /var/backups/deals` ; `restic snapshots` ; l'essai de restauration (§ 10) |
| Mise à jour et retour arrière essayés | `release.sh install`, puis `rollback`, puis `install` à nouveau (§ 11) |
| Aucun secret ni réglage réel dans le dépôt ou le zip | `python -m bench.cadre` (« aucun secret ni aucune base dans le dépôt ») |
| Remises vérifiées dès l'ouverture | la pré-collecte de 3 semaines au moins, nuit après nuit, avant d'ouvrir (`docs/PRODUCTION.md`) |
