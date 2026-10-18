#!/usr/bin/env bash
# Reconstruit web/app.html : une page autonome (React et la police Manrope inclus), servie à /.
# Aucune requête vers un tiers à l'ouverture de l'app (pas de Google Fonts : RGPD, rapidité, rendu garanti).
# Dépendances de BUILD uniquement (pas à l'exécution) : esbuild, react, react-dom.
#   ESBUILD=/chemin/vers/esbuild REACT_DIR=/chemin/vers/node_modules ./web/build.sh
set -euo pipefail
cd "$(dirname "$0")"
ESBUILD="${ESBUILD:-esbuild}"
REACT_DIR="${REACT_DIR:-$(npm root -g)}"
FONT="fonts/manrope-latin.woff"            # Manrope variable 200-800, sous-ensemble latin (SIL OFL 1.1, fonts/OFL-Manrope.txt)
OUT="$(mktemp -d)"
"$ESBUILD" src/mount.jsx --bundle --minify --format=iife --jsx=automatic --loader:.jsx=jsx \
  --define:process.env.NODE_ENV='"production"' \
  --alias:react="$REACT_DIR/react" --alias:react-dom="$REACT_DIR/react-dom" \
  --outfile="$OUT/app.js" --log-level=warning
{
  printf '<!doctype html>\n<html lang="fr"><head><meta charset="utf-8">\n'
  printf '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
  printf '<meta name="theme-color" content="#FFFFFF"><title>Deals — les vraies remises du jour</title>\n'
  printf '<meta name="description" content="Les vraies remises du jour sur l\x27électroménager, l\x27ameublement et la literie : prix relevés chaque nuit, fausses promos écartées.">\n'
  printf '<style>@font-face{font-family:Manrope;font-style:normal;font-weight:200 800;font-display:swap;src:url(data:font/woff;base64,'
  base64 < "$FONT" | tr -d '\n'
  printf ') format("woff")}html,body{margin:0;background:#FFFFFF}</style></head>\n<body><div id="root"></div>\n<script>\n'
  cat "$OUT/app.js"
  printf '\n</script></body></html>\n'
} > app.html
rm -rf "$OUT"
echo "app.html : $(wc -c < app.html) octets"
