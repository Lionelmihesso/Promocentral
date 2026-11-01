#!/bin/sh
# Déployer une version de Promo Central, et revenir en arrière d'une commande.
#
#   sudo deploy/release.sh package                 fabrique l'archive du commit courant (depuis le dépôt) :
#                                                  promocentral-<AAAAMMJJ-HHMMSS>-<commit>.tar.gz
#   sudo deploy/release.sh install <archive>       installe la version à côté des précédentes, sauvegarde la base,
#                                                  bascule, redémarre l'app, passe les tests de fumée ; un test raté :
#                                                  retour arrière automatique (code, et base si elle a été migrée)
#   sudo deploy/release.sh rollback                revient à la version précédente (code, et base si besoin)
#   sudo deploy/release.sh list                    les versions installées, la version en service
#
# Disposition : $ROOT/releases/<version>/ (une version par dossier, jamais modifiée), $ROOT/current → la version en
# service (les services systemd lancent $ROOT/current/deals.py), $ROOT/releases/<version>.backup : la sauvegarde de la
# base prise juste avant de l'installer. Une base migrée par une version refuse le code d'avant (store.py) : revenir
# en arrière restaure alors la sauvegarde prise avant la bascule, après avoir mis la base courante de côté
# ($BACKUPS/abandonnee-<horodatage>.sqlite : rien n'y est perdu).
# Réglages (pour les essais : tests/test_release.py) : DEALS_ROOT, DEALS_DATA, DEALS_BACKUPS, SYSTEMCTL, PYTHON,
# DEALS_SMOKE_URL, DEALS_SMOKE (commande de fumée), DEALS_KEEP (versions gardées, 5), DEALS_ENVFILE, DEALS_RUN_AS.
set -eu
ROOT=${DEALS_ROOT:-/opt/deals}
DATA=${DEALS_DATA:-/var/lib/deals}
BACKUPS=${DEALS_BACKUPS:-/var/backups/deals}
SYSTEMCTL=${SYSTEMCTL:-systemctl}
PYTHON=${PYTHON:-/usr/bin/python3}
SMOKE_URL=${DEALS_SMOKE_URL:-http://127.0.0.1:8000}
KEEP=${DEALS_KEEP:-5}
DB="$DATA/deals.sqlite"
ENVFILE=${DEALS_ENVFILE:-/etc/deals/deals.env}
# Commande qui lance Python comme le font les services : utilisateur deals, réglages de deals.env (vide : directement)
RUN_AS=${DEALS_RUN_AS-"systemd-run --quiet --wait --pipe --collect --uid=deals --gid=deals -p WorkingDirectory=$DATA -p EnvironmentFile=$ENVFILE"}

say() { printf '%s\n' "$*"; }
die() { printf 'ÉCHEC : %s\n' "$*" >&2; exit 1; }
schema_of_db() { "$PYTHON" -c "import sqlite3,sys; print(sqlite3.connect(sys.argv[1]).execute('PRAGMA user_version').fetchone()[0])" "$1"; }
schema_of_code() { "$PYTHON" -c "import sys; sys.path.insert(0, sys.argv[1]); from deals.store import SCHEMA_VERSION; print(SCHEMA_VERSION)" "$1"; }

switch_to() {   # bascule atomique du lien current
    ln -sfn "$1" "$ROOT/current.next" && mv -T "$ROOT/current.next" "$ROOT/current"
}

restore_if_needed() {   # $1 : la version vers laquelle on revient ; $2 : la sauvegarde prise avant la version quittée
    [ -f "$DB" ] || return 0
    have=$(schema_of_db "$DB"); want=$(schema_of_code "$1")
    if [ "$have" -gt "$want" ]; then
        [ -n "$2" ] && [ -f "$2" ] || die "la base est au schéma v$have, la version $(basename "$1") attend v$want, et aucune sauvegarde n'est disponible"
        say "base au schéma v$have, plus récent que la version visée (v$want) : restauration de $(basename "$2")"
        $SYSTEMCTL stop deals-web deals-daily || true
        # Les écritures faites depuis la sauvegarde (comptes, clics, missions) ne sont pas perdues : la base courante
        # est mise de côté, intacte, avant d'être remplacée. Elle n'a pas le nom deals-*.sqlite : la rotation ne la touche pas.
        abandoned="$BACKUPS/abandonnee-$(date -u +%Y%m%d-%H%M%S).sqlite"
        mkdir -p "$BACKUPS"
        "$PYTHON" -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); \
assert d.execute('PRAGMA integrity_check').fetchone()[0]=='ok'" "$DB" "$abandoned" \
            || die "impossible de mettre la base courante de côté : restauration annulée"
        say "base courante mise de côté : $abandoned (écritures depuis la sauvegarde : à reprendre à la main si besoin)"
        rm -f "$DB-wal" "$DB-shm"
        cp "$2" "$DB"
    fi
}

preflight() {   # $1 : le dossier de la version à installer : sa configuration est contrôlée avant toute bascule
    $RUN_AS "$PYTHON" "$1/deals.py" --db "$DB" check
}

smoke() {
    if [ -n "${DEALS_SMOKE:-}" ]; then sh -c "$DEALS_SMOKE"; else "$PYTHON" "$ROOT/current/deploy/smoke.py" "$SMOKE_URL"; fi
}

case "${1:-}" in
package)
    here=$(cd "$(dirname "$0")/.." && pwd)
    sha=$(git -C "$here" rev-parse --short HEAD) || die "pas un dépôt git"
    [ -z "$(git -C "$here" status --porcelain)" ] || die "des modifications ne sont pas commitées : une version vient d'un commit"
    name="promocentral-$(date -u +%Y%m%d-%H%M%S)-$sha.tar.gz"
    git -C "$here" archive --format=tar.gz -o "$PWD/$name" HEAD
    say "$PWD/$name"
    ;;
install)
    archive=${2:-}
    [ -n "$archive" ] && [ -f "$archive" ] || die "usage : release.sh install <archive.tar.gz>"
    version=$(basename "$archive" .tar.gz)
    dest="$ROOT/releases/$version"
    [ ! -e "$dest" ] || die "la version $version est déjà installée"
    "$PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null \
        || die "Python 3.11 ou plus récent est nécessaire ($PYTHON : $("$PYTHON" -V 2>&1))"
    mkdir -p "$dest" "$BACKUPS"
    tar -xzf "$archive" -C "$dest"
    [ -f "$dest/deals.py" ] || die "archive sans deals.py"
    if ! preflight "$dest"; then                  # configuration incomplète : rien n'est basculé
        rm -rf "$dest"
        die "configuration à régler avant d'installer $version (voir ci-dessus, deals.py check)"
    fi
    "$PYTHON" -m compileall -q "$dest/deals" >/dev/null 2>&1 || true   # le code précompilé : le service n'écrit rien ici
    prev=$(readlink "$ROOT/current" 2>/dev/null || true)
    backup=""
    if [ -f "$DB" ]; then                         # avant que la nouvelle version ne migre la base
        backup=$("$PYTHON" "$dest/deals.py" --db "$DB" backup "$BACKUPS" --keep 30 | tail -1)
        cp "$backup" "$ROOT/releases/$version.backup"
        say "base sauvegardée : $backup"
    fi
    switch_to "$dest"
    $SYSTEMCTL restart deals-web
    say "version $version en service ; tests de fumée…"
    if ! smoke; then
        say "tests de fumée ratés : retour à ${prev:-rien}"
        if [ -n "$prev" ]; then
            restore_if_needed "$prev" "$ROOT/releases/$version.backup"
            switch_to "$prev"
            $SYSTEMCTL restart deals-web
        fi
        die "version $version retirée"
    fi
    ls -1d "$ROOT"/releases/*/ 2>/dev/null | sort | head -n "-$KEEP" | while read -r old; do
        [ "${old%/}" = "$dest" ] || rm -rf "${old%/}" "${old%/}.backup"
    done
    say "version $version installée"
    ;;
rollback)
    cur=$(readlink "$ROOT/current" 2>/dev/null) || die "aucune version en service"
    prev=$(ls -1d "$ROOT"/releases/*/ | sed 's:/$::' | sort | grep -B1 -x "$cur" | head -1)
    [ -n "$prev" ] && [ "$prev" != "$cur" ] || die "pas de version précédente"
    restore_if_needed "$prev" "$cur.backup"
    switch_to "$prev"
    $SYSTEMCTL restart deals-web
    smoke || die "la version précédente ne passe pas les tests de fumée non plus : voir docs/RUNBOOK.md#mise-a-jour"
    say "retour à $(basename "$prev")"
    ;;
list)
    cur=$(readlink "$ROOT/current" 2>/dev/null || true)
    for d in $(ls -1d "$ROOT"/releases/*/ 2>/dev/null | sed 's:/$::' | sort); do
        if [ "$d" = "$cur" ]; then say "* $(basename "$d")  (en service)"; else say "  $(basename "$d")"; fi
    done
    ;;
*)
    die "usage : release.sh package | install <archive> | rollback | list"
    ;;
esac
