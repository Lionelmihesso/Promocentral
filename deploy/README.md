# Mise en ligne de Promo Central — un seul petit serveur (Debian ou Ubuntu)

Nom de code technique : `deals` (commande, services, dossiers). Le nom affiché est Promo Central.

Prérequis : Python 3.11 ou plus récent (bibliothèque standard uniquement) avec SQLite 3.35 ou plus récent (Debian 12,
Ubuntu 22.04 et suivantes ; vérifié au démarrage), Caddy pour le HTTPS, un compte SMTP (liens de connexion, e-mails des
missions).
Trois services : l'app (`deals-web`), la nuit (`deals-daily`, 3 h : collecte, agent, publication, e-mails des
missions, contrôles, rapport du matin, e-mail au responsable s'il y a lieu), la sauvegarde (`deals-backup`, 6 h).

## 1. Code, données, réglages
Le code s'installe par versions datées (`deploy/release.sh`) : `/opt/deals/releases/<version>/`, jamais modifiée, et
`/opt/deals/current` → la version en service ; les services lancent `/opt/deals/current/deals.py`.
```
sudo useradd --system --home /var/lib/deals --shell /usr/sbin/nologin deals
sudo mkdir -p /opt/deals/releases /var/lib/deals /var/backups/deals /etc/deals
sh deploy/release.sh package                              # depuis le dépôt : promocentral-<date>-<commit>.tar.gz
sudo SYSTEMCTL=true DEALS_SMOKE=true sh deploy/release.sh install promocentral-….tar.gz   # la première : services pas encore là
sudo chown -R deals:deals /var/lib/deals /var/backups/deals
sudo cp /opt/deals/current/deploy/deals.env.example /etc/deals/deals.env
sudo chmod 600 /etc/deals/deals.env && sudoedit /etc/deals/deals.env       # robot, adresse, mentions légales, SMTP, flux
sudo cp /opt/deals/current/deploy/affiliate.example.json /etc/deals/affiliate.json  # enseignes partenaires : liens des réseaux
sudo chgrp deals /etc/deals/affiliate.json && sudo chmod 640 /etc/deals/affiliate.json && sudoedit /etc/deals/affiliate.json
sudo cp /opt/deals/current/deploy/sources.example.json /etc/deals/sources.json      # sources : le flux de chaque enseigne
sudo mkdir -p /etc/deals/feeds && sudo cp /opt/deals/current/deploy/feeds/*.json /etc/deals/feeds/
sudo chgrp -R deals /etc/deals/sources.json /etc/deals/feeds && sudo chmod -R g+r /etc/deals/sources.json /etc/deals/feeds
sudo install -m 755 /opt/deals/current/deploy/deals /usr/local/bin/deals    # « sudo deals … » sur le serveur
```
`sudo deals <commande>` lance `deals.py` comme les services : utilisateur `deals`, dossier `/var/lib/deals`, réglages
de `/etc/deals/deals.env`. Un réglage invalide arrête la commande en nommant la variable. Seules les enseignes de
`/etc/deals/affiliate.json` (`DEALS_AFFILIATE`) sont lues la nuit et publiées.

## 2. Brancher les flux des enseignes (la voie normale)
Pour chaque enseigne dont le programme d'affiliation est accepté et fournit un flux produits :
```
# 1. l'adresse du flux (identifiants du réseau compris) dans /etc/deals/deals.env : DEALS_FEED_<ENSEIGNE>=https://…
# 2. un échantillon, pour écrire la correspondance de ses colonnes (rien n'est deviné : la proposition se relit)
curl -s "$URL_DU_FLUX" -o /tmp/echantillon && sudo deals probe /tmp/echantillon
#    → enregistrer la correspondance proposée, corrigée, dans /etc/deals/feeds/<enseigne>.json
#      (un flux au format Google Shopping : {"preset": "google_shopping"} suffit)
# 3. activer la source dans /etc/deals/sources.json ("enabled": true) et l'enseigne dans /etc/deals/affiliate.json
sudo deals ingest <enseigne> --dry-run      # tout est lu et contrôlé, rien n'est écrit : offres retenues, refus et raisons
sudo deals ingest <enseigne>                # premier lot : offres écrites, fichier brut gardé (deals batches)
sudo deals publish                          # catalogue publié tout de suite (sinon : la nuit)
```
Ensuite, la nuit lit chaque flux (un lot par source), comme les fiches. `sudo deals batches` montre les lots, leurs
comptes et leurs refus ; `sudo deals replay <enseigne>` relit le dernier fichier gardé après une correction.

## 3. Lire les fiches d'une enseigne sans flux (dernier recours, une fois)
Seulement si ses conditions d'utilisation le permettent (`docs/PRODUCTION.md`, P0-5) :
```
sudo deals discover all --per 40       # fiches trouvées dans les plans de site (urls/<enseigne>.json)
sudo deals diagnose all --n 20         # reports/diagnostic.md : garder / règle de site à écrire / abandonner
sudo deals sample all --n 5            # pages brutes (samples/) pour régler l'extraction hors ligne
sudo deals build all                   # première lecture : produits rapprochés par EAN, puis marque + référence, puis titre
sudo deals review                      # rapprochements à vérifier
sudo deals estimate                    # durée de la passe de nuit
sudo deals nightly                     # première nuit : catalogue publié
```

## 4. Services
```
sudo cp /opt/deals/current/deploy/*.service /opt/deals/current/deploy/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now deals-web.service deals-daily.timer deals-backup.timer
sudo cp /opt/deals/current/deploy/Caddyfile /etc/caddy/Caddyfile && sudoedit /etc/caddy/Caddyfile   # votre domaine
sudo systemctl reload caddy
```

## 5. Vérifier
```
curl -s https://promocentral.example.fr/api/r/categories                       # 200 et des catégories
curl -s https://promocentral.example.fr/api/r/health                           # {"status": "ok", …} après la première nuit
curl -s -o /dev/null -w "%{http_code}\n" https://promocentral.example.fr/admin  # 404 : rien d'autre que l'app, /api/r/ et /robot
curl -sI https://promocentral.example.fr/ | grep -i strict-transport                 # HSTS envoyé par l'app
sudo deals status                                                        # dernière nuit, catalogue, sources, incidents, décisions
sudo deals metrics                                                       # clics sortants, comptes, catalogue, dernière nuit
journalctl -u deals-daily --since today                                  # rapport de la nuit (aussi dans /var/lib/deals/reports/), journal JSON
```

## 6. Exploitation au quotidien
La nuit se débrouille seule (`docs/AUTONOMIE.md`) : `DEALS_OPERATOR_EMAIL` reçoit au plus un e-mail par nuit, seulement
s'il y a lieu (décision à prendre, source mise de côté, incident critique, retour à la normale), avec la fiche du
runbook (`docs/RUNBOOK.md`) et les commandes à lancer. Branchez aussi une sonde HTTP extérieure (UptimeRobot,
Healthchecks…) sur `https://promocentral.example.fr/api/r/health` : elle prévient par un autre chemin si la nuit ne tourne plus
ou si le SMTP tombe (503 = critique).
```
sudo deals status                      # l'état, en quelques lignes
sudo deals approve <n°>                # exécuter une proposition de l'agent (ou : sudo deals reject <n°>)
sudo deals sources enable <clé>        # reprendre une source mise de côté, une fois la cause réglée
sudo deals quarantine                  # prix suspects retenus ; release <offre> pour un prix vérifié chez l'enseigne
sudo deals events --cid <corrélation>  # tout ce qui s'est passé une nuit donnée
```
Vos gestes sont journalisés à votre nom (`sudo deals` le transmet).

## Mettre à jour le code, revenir en arrière
```
sh deploy/release.sh package                                       # depuis le dépôt, sur un commit (rien de non commité)
sudo sh /opt/deals/current/deploy/release.sh install promocentral-<date>-<commit>.tar.gz
sudo sh /opt/deals/current/deploy/release.sh list                  # les versions gardées (5), celle en service
sudo sh /opt/deals/current/deploy/release.sh rollback              # la version précédente, en une commande
```
`install` sauvegarde la base, bascule le lien `current`, redémarre l'app et passe les tests de fumée
(`deploy/smoke.py` : la page, les catégories, une recherche, l'état, les mentions légales, `/robot`, rien d'autre) ; un
test raté ramène aussitôt la version d'avant. La base porte un numéro de schéma, et un code plus ancien que sa base
refuse de démarrer : si la version retirée l'avait migrée, la sauvegarde prise juste avant la bascule est restaurée
(services arrêtés le temps de la copie). Une mise à jour se répète d'abord en préproduction (`docs/PRODUCTION.md`).

## Restaurer une sauvegarde
```
sudo systemctl stop deals-web deals-daily
sudo rm -f /var/lib/deals/deals.sqlite-wal /var/lib/deals/deals.sqlite-shm   # un journal resté là s'appliquerait à la copie
sudo -u deals cp /var/backups/deals/deals-AAAA-MM-JJ_HHMMSS.sqlite /var/lib/deals/deals.sqlite
sudo systemctl start deals-web
```
