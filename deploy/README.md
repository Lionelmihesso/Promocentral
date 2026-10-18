# Mise en ligne — un seul petit serveur (Debian ou Ubuntu)

Prérequis : Python 3.11 ou plus récent (bibliothèque standard uniquement), Caddy pour le HTTPS, un compte SMTP.

## 1. Code, données, configuration
```
sudo useradd --system --home /var/lib/deals --shell /usr/sbin/nologin deals
sudo mkdir -p /opt/deals /var/lib/deals /var/backups/deals /etc/deals
sudo cp -r . /opt/deals                                   # depuis le dossier de la plateforme
sudo chown -R deals:deals /var/lib/deals /var/backups/deals
sudo cp /opt/deals/deploy/deals.env.example /etc/deals/deals.env
sudo chmod 600 /etc/deals/deals.env && sudoedit /etc/deals/deals.env
```
Dans `collect/retailers.py`, remplacez `USER_AGENT` par le nom du robot, une page qui le décrit et une adresse de contact.

## 2. Constituer la base (une fois, en tant que deals)
```
cd /var/lib/deals
sudo -u deals python3 /opt/deals/collect.py --db deals.sqlite discover all --per 40
sudo -u deals python3 /opt/deals/collect.py --db deals.sqlite diagnose all --n 20     # lire reports/diagnostic.md
sudo -u deals python3 /opt/deals/collect.py --db deals.sqlite sample all --n 5        # pages brutes (samples/) pour une mise au point
sudo -u deals python3 /opt/deals/collect.py --db deals.sqlite build all
sudo -u deals python3 /opt/deals/collect.py --db deals.sqlite estimate               # durée de la passe de nuit
sudo -u deals python3 /opt/deals/cli.py --db deals.sqlite daily                     # premiers signaux et similarités
```

## 3. Services
```
sudo cp /opt/deals/deploy/*.service /opt/deals/deploy/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now deals-web.service deals-daily.timer deals-backup.timer
sudo cp /opt/deals/deploy/Caddyfile /etc/caddy/Caddyfile && sudoedit /etc/caddy/Caddyfile   # votre domaine
sudo systemctl reload caddy
```
Ne planifiez pas `collect.py nightly` : `deals-daily` lance déjà la passe de nuit.

## 4. Vérifier
```
curl -s https://deals.example.fr/api/r/categories                       # 200 et des catégories
curl -s -o /dev/null -w "%{http_code}\n" https://deals.example.fr/admin  # 404 : la console n'est pas publique
sudo -u deals python3 /opt/deals/cli.py --db /var/lib/deals/deals.sqlite metrics
journalctl -u deals-daily --since today                                  # rapport de la nuit
```

## Console interne (jamais publique)
Sur le serveur : `sudo -u deals python3 /opt/deals/app.py serve --admin --port 8001 --db /var/lib/deals/deals.sqlite`,
puis depuis votre machine : `ssh -L 8001:127.0.0.1:8001 serveur` et http://127.0.0.1:8001/admin.

## Restaurer une sauvegarde
```
sudo systemctl stop deals-web
sudo -u deals cp /var/backups/deals/deals-AAAA-MM-JJ_HHMMSS.sqlite /var/lib/deals/deals.sqlite
sudo systemctl start deals-web
```
