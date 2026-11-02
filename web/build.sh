#!/usr/bin/env bash
# Reconstruit web/app.html : une page autonome (React et les polices incluses), servie à /.
# Aucune requête vers un tiers à l'ouverture de l'app (pas de Google Fonts : RGPD, rapidité, rendu garanti).
# Dépendances de BUILD uniquement (pas à l'exécution) : esbuild, react, react-dom. app.html a été construit avec
# esbuild 0.28.2, react et react-dom 19.2.8 : ces versions le redonnent à l'octet près. Le serveur n'a besoin ni de
# Node ni de ces outils : app.html est versionné.
#   ESBUILD=/chemin/vers/esbuild REACT_DIR=/chemin/vers/node_modules ./web/build.sh
set -euo pipefail
cd "$(dirname "$0")"
ESBUILD="${ESBUILD:-esbuild}"
REACT_DIR="${REACT_DIR:-$(npm root -g)}"
# Police, sous-ensemble latin (SIL OFL 1.1, licence dans fonts/) : Manrope, la seule depuis la v66 (textes et titres).
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
  printf '<meta name="theme-color" content="#FFFFFF"><title>Promo Central — de bonnes affaires, pour vos envies</title>\n'
  # l'icône : le « P » de Promo, en blanc sur l'anthracite, la couleur action (v66)
  printf '%s\n' "<link rel=\"icon\" href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%233C3C3E'/%3E%3Cpath d='M11.5 25V7.5h5.5a5.25 5.25 0 0 1 0 10.5h-5.5' fill='none' stroke='%23FFFFFF' stroke-width='3.4' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E\">"
  printf '<meta name="description" content="Les vraies remises du jour sur l\x27électroménager, l\x27électronique, l\x27ameublement et la literie : le prix, la remise, l\x27économie, et ce qui coûte moins cher.">\n'
  printf '<style>'
  face Manrope "200 800" manrope-latin.woff
  printf 'html,body{margin:0;background:#FFFFFF}</style></head>\n<body><div id="root"></div>\n<script>\n'
  cat "$OUT/app.js"
  printf '\n</script></body></html>\n'
} > app.html
rm -rf "$OUT"
echo "app.html : $(wc -c < app.html) octets"
