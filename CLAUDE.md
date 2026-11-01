# CLAUDE.md — Promo Central (nom de code : deals)

Consignes pour toute évolution de ce dépôt. Le produit est décrit dans `README.md`, l'architecture détaillée dans
`docs/ARCHITECTURE.md`, la mise en production dans `deploy/README.md`, l'exploitation dans `docs/RUNBOOK.md`.

## 1. Architecture

Monolithe modulaire Python 3.11+, bibliothèque standard uniquement, une base SQLite (WAL), un front React compilé dans
un fichier HTML autonome (`web/app.html`).

- **Nuit** : sources → ingestion (`deals/ingest/`) → marché (`market.py`) → publication (`publish.py`) → catalogue.
- **Jour** : l'app (`api.py`, `web.py`, `catalog.py`, `missions.py`, `accounts.py`) ne lit que le catalogue publié.
- **Exploitation** : `night.py`, `agent.py`, `health.py`, `ops.py`, `backup.py`, `cli.py`.

Règles de conception :
- chaque table a un seul écrivain (`market.py` pour produits, offres et prix ; `publish.py` pour le catalogue ;
  `accounts`, `activity`, `missions`, `profile` pour les données des personnes) ;
- les moteurs (`extract/`, `ontology/`, `judge.py`, `alternatives.py`, `query.py`, `funnel.py`, `labels.py`) sont purs :
  ni base, ni réseau ;
- l'app ne lit jamais l'ingestion ; l'ingestion ne dépend jamais de l'app. `tests/test_architecture.py` vérifie ces règles.

## 2. Conventions de développement

- Français pour le code commenté, la documentation et les messages.
- Pas de dépendance externe au code de production. `deals/vendor/protego` est vendu, sous licence (`LICENSE`).
- Mesurer avant de changer : un changement de comportement s'accompagne d'un test qui échoue sans lui.
- Ne pas modifier le catalogue, les règles métier (`judge`, `alternatives`, `funnel`, `query`), les parcours utilisateur
  ni les paramètres de sécurité sans accord explicite.
- Ne pas remplacer une implémentation par une version simplifiée pour faire passer un test.
- Préserver les permissions d'exécution des scripts (`deploy/release.sh`, `deploy/smoke.py`, `deploy/deals`, `web/build.sh`).
- Le front n'est reconstruit qu'avec `web/build.sh` (esbuild 0.28.2, React 19.2.8) ; `app.html` est versionné.
- Chaque ajout de réglage est reporté dans `deploy/deals.env.example` ; chaque ajout de service dans `deploy/`.
  `tests/test_deploy.py` vérifie la cohérence.

## 3. Commandes

```
python -m unittest discover -s tests -t .      # 285 tests, environ 100 s — à lancer avant tout commit
python -m unittest tests.test_release -v        # release et rollback seuls
python -m bench.cadre                           # cadre de mise en production (17/19 ; aucun point P0 ouvert)
python deals.py demo                            # app sur un marché simulé, base temporaire (jamais la base de production)
python -m unittest tests.test_demo_mode tests.test_install -v   # mode démo et installation en une commande
sh web/build.sh                                 # reconstruit web/app.html (esbuild et react requis, voir web/build.sh)
```

Le test de timing `test_web_writes_never_wait_during_the_night` lance deux processus réels sur la même base (sans
multiprocessing) et tolère 0,5 s pour la pire écriture. Un échec de ce test doit être reproduit avant d'être corrigé.

## 4. Sécurité et secrets

- Aucun secret, identifiant, adresse de flux réelle ni base de données dans le dépôt. Les secrets vivent dans
  `/etc/deals/deals.env`, `/etc/deals/affiliate.json` et `/etc/deals/offsite.env` (droits 600, root).
- Les adresses des flux portent les identifiants des réseaux : elles se mettent dans `DEALS_FEED_<ENSEIGNE>`, jamais
  dans `sources.json` (qui les cite par `${NOM}`), ni dans les journaux, ni dans un message.
- `.gitignore` couvre `*.env`, `*.sqlite*`, `raw/`, `reports/`, `backups/`, `samples/`. Ne jamais forcer l'ajout de ces fichiers.
- Le serveur écoute sur `127.0.0.1:8000` ; Caddy assure le HTTPS. Le port 8000 n'est jamais exposé.
- Cookie de session `HttpOnly; SameSite=Lax`, `Secure` en HTTPS. En-têtes : `nosniff`, `X-Frame-Options: DENY`, HSTS.
- Les messages d'erreur passent par `Collector._scrub` ; le journal masque les champs sensibles (`ops.SENSITIVE`).
- Les exemples (`*.example*`) ne désignent aucune enseigne réelle et ne contiennent aucune valeur réelle.
- Le robot se présente avec son nom, sa page `/robot` et un contact ; il respecte `robots.txt` et un délai de 5 s par site.
  Un anti-robot n'est jamais contourné.

## 5. Processus de release

Une version vient toujours d'un commit propre.

Première installation et mises à jour, en une commande depuis un clone propre sur le serveur :

```
sudo sh deploy/install.sh demo                      # démonstration : marché simulé, aucun e-mail, aucun flux réel
sudo sh deploy/install.sh prod                      # production : refusée tant que deals.py check signale un manque
sudo sh /opt/deals/current/deploy/verify.sh         # vérification : configuration, service, écoute, tests de fumée
```

Modes : `DEALS_ENV` vaut `dev`, `demo` ou `prod`. En `demo`, les commandes qui lisent des sites ou envoient des
e-mails (`config.DEMO_REFUSED`) refusent de tourner, la page affiche un bandeau « données fictives », la page
« Mentions légales » ne publie aucune identité, et la santé ne dépend pas de la date des nuits. En `prod`, les
mentions légales restent obligatoires : aucun mode démo ne relâche ce contrôle, et `demo` et `prod` ne partagent
jamais un `deals.env` (`install.sh` le vérifie).

Une version est aussi contrôlée avant d'être basculée : `release.sh install` lance `deals.py check` avec la
configuration réelle, et refuse la bascule si elle échoue.

```
sh deploy/release.sh package                        # archive du commit courant (refusée s'il reste des modifications)
sudo sh deploy/release.sh install <archive>         # installe à côté des autres, sauvegarde la base, bascule,
                                                    # redémarre deals-web, lance deploy/smoke.py ; échec → retour arrière
sudo sh deploy/release.sh rollback                  # version précédente (code, et base si elle a été migrée)
sudo sh deploy/release.sh list
```

Disposition sur le serveur : `/opt/deals/releases/<version>/` (une version par dossier, jamais modifiée),
`/opt/deals/current` (lien vers la version en service), `/var/lib/deals` (base et brut des flux),
`/var/backups/deals` (sauvegardes). Cinq versions sont gardées.

Avant d'ouvrir une version au serveur : tests verts, `bench.cadre` sans P0, archive fabriquée depuis un commit, et
mise à jour puis retour arrière essayés sur une copie.

Une version qui change `deploy/*.service` ou `*.timer` demande de les recopier dans `/etc/systemd/system/` puis
`systemctl daemon-reload`. `release.sh` ne le fait pas.

## 6. La base SQLite de production : ne jamais l'écraser

`/var/lib/deals/deals.sqlite` contient les comptes, les favoris, les missions, les clics, le catalogue et les
historiques de prix. Une perte est irréversible. Règles :

1. **Aucun test, aucune démo, aucune commande de développement ne pointe vers la base de production.** Les tests et
   `deals.py demo` travaillent dans des dossiers temporaires. Vérifier `--db` avant toute commande manuelle.
2. **Toute migration passe par `store.py`** : un numéro de schéma, une entrée dans `MIGRATIONS`, un test de migration
   sur une base de l'ancienne version. Une version qui ne connaît pas un schéma plus récent refuse de démarrer
   (c'est voulu).
3. **Une sauvegarde précède toute migration** : `release.sh install` la prend avant la bascule (`deals.py backup`,
   vérifiée par `integrity_check`).
4. **Ne jamais restaurer sans mettre la base courante de côté.** `release.sh` le fait désormais : la base courante
   devient `/var/backups/deals/abandonnee-<horodatage>.sqlite`, et les écritures faites depuis la sauvegarde y restent.
   Les écritures ne sont pas réinjectées automatiquement dans la base restaurée : elles se reprennent à la main.
5. **Arrêter les services avant toute copie à la main** (`systemctl stop deals-web deals-daily`), et copier une base
   vivante uniquement par l'API de sauvegarde SQLite (`deals.py backup` ou `sqlite3.Connection.backup`), jamais par `cp`.
6. **Supprimer `deals.sqlite-wal` et `-shm` seulement après un arrêt propre des services**, et seulement quand la base
   qu'ils accompagnent est déjà mise de côté.
7. **Ne jamais supprimer `/var/backups/deals`** ni ses copies `abandonnee-*` : elles sont la seule trace des écritures
   d'une restauration. La copie chiffrée hors serveur (`deals-offsite`) doit tourner avant l'ouverture au public.
8. Avant toute opération destructive sur la base, vérifier l'état : `sudo deals status`, `release.sh list`,
   `ls -l /var/backups/deals`.

## 7. Commits

- Message en français, première ligne courte, corps qui explique le pourquoi.
- Se terminer par les lignes :
  ```
  Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01NQ8adgh3NMNZuZxej7BKeK
  ```
- Ne pas pousser sans accord du responsable du projet.
