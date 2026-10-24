#!/usr/bin/env bash
# Reconstruit web/app.html : une page autonome (React et les polices incluses), servie à /.
# Aucune requête vers un tiers à l'ouverture de l'app (pas de Google Fonts : RGPD, rapidité, rendu garanti).
# Dépendances de BUILD uniquement (pas à l'exécution) : esbuild, react, react-dom.
#   ESBUILD=/chemin/vers/esbuild REACT_DIR=/chemin/vers/node_modules ./web/build.sh
set -euo pipefail
cd "$(dirname "$0")"
ESBUILD="${ESBUILD:-esbuild}"
REACT_DIR="${REACT_DIR:-$(npm root -g)}"
# Polices, sous-ensembles latins (SIL OFL 1.1, licences dans fonts/) : Manrope (texte), Instrument Serif (titres),
# JetBrains Mono (bandeau, chiffres de la courbe).
face() { printf '@font-face{font-family:%s;font-style:normal;font-weight:%s;font-display:swap;src:url(data:font/woff;base64,' "$1" "$2"
         base64 < "fonts/$3" | tr -d '\n'; printf ') format("woff")}'; }
OUT="$(mktemp -d)"
"$ESBUILD" src/mount.jsx --bundle --minify --format=iife --jsx=automatic --loader:.jsx=jsx \
  --define:process.env.NODE_ENV='"production"' \
  --alias:react="$REACT_DIR/react" --alias:react-dom="$REACT_DIR/react-dom" \
  --outfile="$OUT/app.js" --log-level=warning
{
  printf '<!doctype html>\n<html lang="fr"><head><meta charset="utf-8">\n'
  printf '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
  printf '<meta name="theme-color" content="#FFFFFF"><title>Deals — de bonnes affaires, pour vos envies</title>\n'
  printf '<meta name="description" content="Les vraies remises du jour sur l\x27électroménager, l\x27ameublement et la literie, avec le prix des 90 derniers jours et ce qui coûte moins cher.">\n'
  printf '<style>'
  face Manrope "200 800" manrope-latin.woff
  face '"Instrument Serif"' 400 instrumentserif-regular-latin.woff
  face '"JetBrains Mono"' 400 jetbrainsmono-regular-latin.woff
  face '"JetBrains Mono"' 700 jetbrainsmono-bold-latin.woff
  printf 'html,body{margin:0;background:#FFFFFF}</style></head>\n<body><div id="root"></div>\n<script>\n'
  cat "$OUT/app.js"
  printf '\n</script></body></html>\n'
} > app.html
rm -rf "$OUT"
echo "app.html : $(wc -c < app.html) octets"
