# Mise en ligne — un seul petit serveur (Debian ou Ubuntu)

Prérequis : Python 3.11 ou plus récent (bibliothèque standard uniquement) avec SQLite 3.35 ou plus récent (Debian 12,
Ubuntu 22.04 et suivantes ; vérifié au démarrage), Caddy pour le HTTPS, un compte SMTP (liens de connexion, e-mails des
missions).
Trois services : l'app (`deals-web`), la nuit (`deals-daily`, 3 h : collecte, agent, publication, e-mails des
missions, contrôles, rapport du matin, e-mail au responsable s'il y a lieu), la sauvegarde (`deals-backup`, 6 h).

## 1. Code, données, réglages
```
sudo useradd --system --home /var/lib/deals --shell /usr/sbin/nologin deals
sudo mkdir -p /opt/deals /var/lib/deals /var/backups/deals /etc/deals
sudo cp -r . /opt/deals                                   # depuis le dossier de la plateforme
sudo chown -R deals:deals /var/lib/deals /var/backups/deals
sudo cp /opt/deals/deploy/deals.env.example /etc/deals/deals.env
sudo chmod 600 /etc/deals/deals.env && sudoedit /etc/deals/deals.env       # robot, adresse publique, SMTP, responsable
sudo cp /opt/deals/deploy/affiliate.example.json /etc/deals/affiliate.json  # enseignes partenaires : liens des réseaux
sudo chgrp deals /etc/deals/affiliate.json && sudo chmod 640 /etc/deals/affiliate.json && sudoedit /etc/deals/affiliate.json
sudo install -m 755 /opt/deals/deploy/deals /usr/local/bin/deals            # « sudo deals … » sur le serveur
```
`sudo deals <commande>` lance `deals.py` comme les services : utilisateur `deals`, dossier `/var/lib/deals`, réglages
de `/etc/deals/deals.env`. Un réglage invalide arrête la commande en nommant la variable. Seules les enseignes de
`/etc/deals/affiliate.json` (`DEALS_AFFILIATE`) sont lues la nuit et publiées.

## 2. Constituer la base (une fois)
```
sudo deals discover all --per 40       # fiches trouvées dans les plans de site (urls/<enseigne>.json)
sudo deals diagnose all --n 20         # reports/diagnostic.md : garder / règle de site à écrire / abandonner
sudo deals sample all --n 5            # pages brutes (samples/) pour régler l'extraction hors ligne
sudo deals build all                   # première lecture : produits rapprochés par EAN, puis marque + référence, puis titre
sudo deals review                      # rapprochements à vérifier
sudo deals estimate                    # durée de la passe de nuit
sudo deals nightly                     # première nuit : catalogue publié
```

## 3. Services
```
sudo cp /opt/deals/deploy/*.service /opt/deals/deploy/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now deals-web.service deals-daily.timer deals-backup.timer
sudo cp /opt/deals/deploy/Caddyfile /etc/caddy/Caddyfile && sudoedit /etc/caddy/Caddyfile   # votre domaine
sudo systemctl reload caddy
```

## 4. Vérifier
```
curl -s https://deals.example.fr/api/r/categories                       # 200 et des catégories
curl -s https://deals.example.fr/api/r/health                           # {"status": "ok", …} après la première nuit
curl -s -o /dev/null -w "%{http_code}\n" https://deals.example.fr/admin  # 404 : rien d'autre que l'app et /api/r/
sudo deals status                                                        # dernière nuit, catalogue, sources, incidents, décisions
sudo deals metrics                                                       # clics sortants, comptes, catalogue, dernière nuit
journalctl -u deals-daily --since today                                  # rapport de la nuit (aussi dans /var/lib/deals/reports/), journal JSON
```

## 5. Exploitation au quotidien
La nuit se débrouille seule (`docs/AUTONOMIE.md`) : `DEALS_OPERATOR_EMAIL` reçoit au plus un e-mail par nuit, seulement
s'il y a lieu (décision à prendre, source mise de côté, incident critique, retour à la normale), avec la fiche du
runbook (`docs/RUNBOOK.md`) et les commandes à lancer. Branchez aussi une sonde HTTP extérieure (UptimeRobot,
Healthchecks…) sur `https://deals.example.fr/api/r/health` : elle prévient par un autre chemin si la nuit ne tourne plus
ou si le SMTP tombe (503 = critique).
```
sudo deals status                      # l'état, en quelques lignes
sudo deals approve <n°>                # exécuter une proposition de l'agent (ou : sudo deals reject <n°>)
sudo deals sources enable <clé>        # reprendre une source mise de côté, une fois la cause réglée
sudo deals quarantine                  # prix suspects retenus ; release <offre> pour un prix vérifié chez l'enseigne
sudo deals events --cid <corrélation>  # tout ce qui s'est passé une nuit donnée
```
Vos gestes sont journalisés à votre nom (`sudo deals` le transmet).

## Mettre à jour le code
```
sudo cp -r . /opt/deals && sudo systemctl restart deals-web
```
La base porte un numéro de schéma : un code plus ancien que la base refuse de démarrer, plutôt que de l'abîmer.

## Restaurer une sauvegarde
```
sudo systemctl stop deals-web deals-daily
sudo rm -f /var/lib/deals/deals.sqlite-wal /var/lib/deals/deals.sqlite-shm   # un journal resté là s'appliquerait à la copie
sudo -u deals cp /var/backups/deals/deals-AAAA-MM-JJ_HHMMSS.sqlite /var/lib/deals/deals.sqlite
sudo systemctl start deals-web
```
