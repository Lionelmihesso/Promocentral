#!/bin/sh
# Vérifier que Promo Central démarre et répond : configuration, service, écoute locale, tests de fumée.
#   sudo sh /opt/deals/current/deploy/verify.sh [http://127.0.0.1:8000]
# Code de sortie 0 si tout passe ; sinon la ligne en échec dit quoi faire (deploy/README.md § 8 et § 11).
set -u
ROOT=${DEALS_ROOT:-/opt/deals}
DATA=${DEALS_DATA:-/var/lib/deals}
ETC=${DEALS_ETC:-/etc/deals}
SYSTEMCTL=${SYSTEMCTL:-systemctl}
PYTHON=${PYTHON:-/usr/bin/python3}
RUN_AS=${DEALS_RUN_AS-"systemd-run --quiet --wait --pipe --collect --uid=deals --gid=deals -p WorkingDirectory=$DATA -p EnvironmentFile=$ETC/deals.env"}
URL=${1:-http://127.0.0.1:8000}
fail=0
ok() { printf 'ok     %s\n' "$*"; }
ko() { printf 'ÉCHEC  %s\n' "$*"; fail=1; }

if $RUN_AS "$PYTHON" "$ROOT/current/deals.py" --db "$DATA/deals.sqlite" check; then ok "configuration"; else ko "configuration (détail ci-dessus)"; fi
if $SYSTEMCTL is-active --quiet deals-web.service; then ok "service deals-web actif"; else ko "service deals-web arrêté : journalctl -u deals-web -n 50"; fi
if ! command -v ss >/dev/null 2>&1; then ko "ss absent (paquet iproute2) : écoute non vérifiée"
else
    listen=$(ss -ltn | awk 'NR>1 {print $4}' | grep -E ':8000$' || true)
    if [ "$listen" = "127.0.0.1:8000" ]; then ok "écoute sur 127.0.0.1:8000 uniquement"
    elif [ -n "$listen" ]; then ko "le port 8000 écoute ailleurs que sur 127.0.0.1 : $listen (ne jamais l'ouvrir)"
    else ko "rien n'écoute sur le port 8000"; fi
fi
if $PYTHON "$ROOT/current/deploy/smoke.py" "$URL"; then ok "tests de fumée sur $URL"; else ko "tests de fumée sur $URL"; fi
exit $fail
