#!/usr/bin/env bash
# Reconstruit web/app.html : une page autonome (React inclus), servie à /.
# Dépendances de BUILD uniquement (pas à l'exécution) : esbuild, react, react-dom.
#   ESBUILD=/chemin/vers/esbuild REACT_DIR=/chemin/vers/node_modules ./web/build.sh
set -euo pipefail
cd "$(dirname "$0")"
ESBUILD="${ESBUILD:-esbuild}"
REACT_DIR="${REACT_DIR:-$(npm root -g)}"
OUT="$(mktemp -d)"
"$ESBUILD" src/mount.jsx --bundle --minify --format=iife --jsx=automatic --loader:.jsx=jsx \
  --define:process.env.NODE_ENV='"production"' \
  --alias:react="$REACT_DIR/react" --alias:react-dom="$REACT_DIR/react-dom" \
  --outfile="$OUT/app.js" --log-level=warning
{
  printf '<!doctype html>\n<html lang="fr"><head><meta charset="utf-8">\n'
  printf '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
  printf '<meta name="theme-color" content="#FFFFFF"><title>Deals</title>\n'
  printf '<style>html,body{margin:0;background:#DADAD6}</style></head>\n<body><div id="root"></div>\n<script>\n'
  cat "$OUT/app.js"
  printf '\n</script></body></html>\n'
} > app.html
rm -rf "$OUT"
echo "app.html : $(wc -c < app.html) octets"
