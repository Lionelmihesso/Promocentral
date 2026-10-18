"""DEALS — point d'entrée : python deals.py <commande> (voir deals/cli.py)."""
import sys

from deals.cli import main

if __name__ == "__main__":
    sys.exit(main())
