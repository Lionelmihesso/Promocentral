#!/bin/sh
# Installer ou mettre à jour Promo Central sur le serveur, en une seule commande (idempotente).
#
#   sudo sh deploy/install.sh demo    démonstration : données simulées et fictives, sans mentions légales, sans e-mail,
#                                     sans flux ni partenaire réel. Seul deals-web tourne (aucune nuit réelle).
#   sudo sh deploy/install.sh prod    production : exige la configuration complète (deploy/README.md § 6), refusée sinon.
#
# À lancer depuis un clone propre du dépôt : le commit courant est installé. Relancer la commande met à jour (une
# nouvelle version à côté des autres, sauvegarde de la base, bascule, tests de fumée, retour arrière si ça échoue).
# Chaque étape dit ce qu'elle fait ; la vérification finale est deploy/verify.sh.
#
# Réglages d'essai (tests/test_install.py) : DEALS_ROOT, DEALS_DATA, DEALS_BACKUPS, DEALS_ETC, DEALS_UNITS, SYSTEMCTL,
# PYTHON, DEALS_RUN_AS (vide : sans changer d'utilisateur), DEALS_NO_USER (pas de compte ni de propriétaire), DEALS_BIN.
set -eu
MODE=${1:-}
case "$MODE" in demo | prod) ;; *) echo "usage : sudo sh deploy/install.sh demo|prod" >&2; exit 2 ;; esac
HERE=$(cd "$(dirname "$0")/.." && pwd)
ROOT=${DEALS_ROOT:-/opt/deals}
DATA=${DEALS_DATA:-/var/lib/deals}
BACKUPS=${DEALS_BACKUPS:-/var/backups/deals}
ETC=${DEALS_ETC:-/etc/deals}
BIN=${DEALS_BIN:-/usr/local/bin}
UNITS=${DEALS_UNITS:-/etc/systemd/system}
SYSTEMCTL=${SYSTEMCTL:-systemctl}
PYTHON=${PYTHON:-/usr/bin/python3}
RUN_AS=${DEALS_RUN_AS-"systemd-run --quiet --wait --pipe --collect --uid=deals --gid=deals -p WorkingDirectory=$DATA -p EnvironmentFile=$ETC/deals.env"}
export DEALS_ROOT="$ROOT" DEALS_DATA="$DATA" DEALS_BACKUPS="$BACKUPS" DEALS_ENVFILE="$ETC/deals.env" SYSTEMCTL PYTHON DEALS_RUN_AS="$RUN_AS"

say() { printf '%s\n' "$*"; }
die() { printf 'ÉCHEC : %s\n' "$*" >&2; exit 1; }
step() { printf '\n== %s\n' "$*"; }
own() { [ -n "${DEALS_NO_USER:-}" ] || chown "$@"; }

[ "$(id -u)" = 0 ] || [ -n "${DEALS_ROOT:-}" ] || die "à lancer avec sudo : sudo sh deploy/install.sh $MODE"
command -v git >/dev/null || die "git est requis (apt install git)"
[ -z "$(git -C "$HERE" status --porcelain)" ] || die "des modifications ne sont pas commitées : une version vient d'un commit"

step "1. Python et SQLite"
"$PYTHON" -c 'import sys, sqlite3; assert sys.version_info >= (3, 11); assert sqlite3.sqlite_version_info >= (3, 35)' \
    || die "Python 3.11+ et SQLite 3.35+ sont requis ($PYTHON : $("$PYTHON" -V 2>&1))"
say "Python $("$PYTHON" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))'), SQLite $("$PYTHON" -c 'import sqlite3; print(sqlite3.sqlite_version)') ($PYTHON)"

step "2. Utilisateur et répertoires"
if [ -z "${DEALS_NO_USER:-}" ] && ! id deals >/dev/null 2>&1; then
    useradd --system --home-dir "$DATA" --shell /usr/sbin/nologin deals
    say "utilisateur système deals créé"
fi
install -d -m 755 "$ROOT" "$ROOT/releases" "$ETC"
install -d -m 750 "$DATA" "$DATA/raw" "$DATA/reports" "$BACKUPS"
own -R deals:deals "$DATA" "$BACKUPS"
say "$ROOT, $DATA, $BACKUPS, $ETC en place"

step "3. Configuration"
if [ ! -f "$ETC/deals.env" ]; then
    if [ "$MODE" = demo ]; then cp "$HERE/deploy/deals.demo.env.example" "$ETC/deals.env"; else cp "$HERE/deploy/deals.env.example" "$ETC/deals.env"; fi
    say "$ETC/deals.env créé à partir du modèle $MODE"
fi
grep -q "^DEALS_ENV=$MODE\$" "$ETC/deals.env" \
    || die "$ETC/deals.env ne déclare pas DEALS_ENV=$MODE : démo et production ne partagent jamais une configuration"
chmod 600 "$ETC/deals.env"
if [ "$MODE" = prod ]; then
    [ -f "$ETC/affiliate.json" ] || cp "$HERE/deploy/affiliate.example.json" "$ETC/affiliate.json"
    [ -f "$ETC/sources.json" ] || cp "$HERE/deploy/sources.example.json" "$ETC/sources.json"
    [ -d "$ETC/feeds" ] || cp -r "$HERE/deploy/feeds" "$ETC/feeds"
    own root:deals "$ETC/affiliate.json" "$ETC/sources.json"
    chmod 640 "$ETC/affiliate.json" "$ETC/sources.json"
fi

step "4. Services systemd"
if [ "$MODE" = demo ]; then
    UNIT_LIST="deals-web.service"
    for t in deals-daily.timer deals-backup.timer deals-offsite.timer; do
        $SYSTEMCTL disable --now "$t" >/dev/null 2>&1 || true
    done
else
    UNIT_LIST="deals-web.service deals-daily.service deals-daily.timer deals-backup.service deals-backup.timer deals-offsite.service deals-offsite.timer"
fi
install -d -m 755 "$UNITS"
for u in $UNIT_LIST; do install -m 644 "$HERE/deploy/$u" "$UNITS/$u"; done
$SYSTEMCTL daemon-reload
$SYSTEMCTL enable deals-web.service >/dev/null
say "services : $UNIT_LIST"
install -d -m 755 "$BIN"
install -m 755 "$HERE/deploy/deals" "$BIN/deals"
say "commande d'exploitation : $BIN/deals (sudo deals <commande>)"

step "5. Version : contrôle de la configuration, installation, tests de fumée"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
(cd "$WORK" && sh "$HERE/deploy/release.sh" package >"$WORK/out") || die "archive refusée (voir ci-dessus)"
ARCHIVE=$(tail -n 1 "$WORK/out")
say "archive : $(basename "$ARCHIVE")"
sh "$HERE/deploy/release.sh" install "$ARCHIVE" || die "installation refusée (la version précédente, s'il y en avait une, est en service)"

step "6. Base et marché"
$RUN_AS "$PYTHON" "$ROOT/current/deals.py" --db "$DATA/deals.sqlite" status >/dev/null
say "base prête : $DATA/deals.sqlite"
if [ "$MODE" = demo ]; then
    $RUN_AS "$PYTHON" "$ROOT/current/deals.py" --db "$DATA/deals.sqlite" seed-demo
else
    $SYSTEMCTL enable deals-daily.timer deals-backup.timer >/dev/null
    [ -f "$ETC/offsite.env" ] && $SYSTEMCTL enable deals-offsite.timer >/dev/null || say "copie hors serveur : pas encore configurée (deploy/README.md § 10)"
    say "nuit de 3 h et sauvegardes activées ; le premier flux reste à brancher (deploy/README.md § 9)"
fi
$SYSTEMCTL restart deals-web.service

step "Terminé"
say "Vérifier :  sudo sh $ROOT/current/deploy/verify.sh"
if [ "$MODE" = demo ]; then
    say "Voir la démo : ssh -L 8000:127.0.0.1:8000 <serveur>, puis http://127.0.0.1:8000/ sur votre ordinateur."
fi
