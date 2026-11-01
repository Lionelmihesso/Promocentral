"""Promo Central (nom de code technique : deals) — point d'entrée : python deals.py <commande> (voir deals/cli.py)."""
import sys

if sys.version_info < (3, 11):                     # échouer tôt, avec la cause : le code est vérifié sous 3.11 à 3.13
    sys.exit(f"Promo Central demande Python 3.11 ou plus récent (trouvé : {sys.version.split()[0]}).")

from deals.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
