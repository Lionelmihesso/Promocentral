"""Tests de fumée d'une version qui vient d'être déployée : l'app répond-elle comme il faut ? Bibliothèque standard.

  python3 deploy/smoke.py [https://promocentral.example.fr | http://127.0.0.1:8000]
→ une ligne par contrôle, code de sortie 0 si tout passe, 1 sinon (deploy/release.sh revient alors en arrière).
"""
import json
import sys
import time
import urllib.error
import urllib.request

CHECKS = [
    ("la page de l'app", "/", lambda code, body: code == 200 and b"Promo Central" in body),
    ("les catégories", "/api/r/categories", lambda code, body: code == 200 and isinstance(json.loads(body), list)),
    ("une recherche", "/api/r/search?q=lave-linge", lambda code, body: code == 200 and "products" in json.loads(body)),
    ("l'état pour la sonde", "/api/r/health", lambda code, body: code in (200, 503) and "status" in json.loads(body)),
    ("les mentions légales", "/api/r/legal", lambda code, body: code == 200 and json.loads(body)["name"] == "Promo Central"),
    ("rien d'autre n'est servi", "/admin", lambda code, body: code == 404),
]


def get(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main(base="http://127.0.0.1:8000", wait_s=30):
    base = base.rstrip("/")
    deadline = time.monotonic() + wait_s
    while True:                                   # le service vient de redémarrer : on lui laisse le temps d'écouter
        try:
            get(base + "/api/r/health", timeout=2)
            break
        except (urllib.error.URLError, OSError):
            if time.monotonic() > deadline:
                print(f"ÉCHEC  l'app ne répond pas sur {base} après {wait_s} s")
                return 1
            time.sleep(1)
    failed = 0
    for name, path, ok in CHECKS:
        try:
            code, body = get(base + path)
            good = bool(ok(code, body))
        except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError) as e:
            code, good = type(e).__name__, False
        failed += not good
        print(f"{'ok    ' if good else 'ÉCHEC '} {name} ({path} → {code})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
