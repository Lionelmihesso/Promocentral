"""Sauvegarde à chaud de la base SQLite (API de sauvegarde : cohérente même pendant la passe de nuit), avec rotation.

  python3 deploy/backup.py /var/lib/deals/deals.sqlite /var/backups/deals --keep 14
"""
import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def backup(db, dest_dir, keep=14, now=None):
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y-%m-%d_%H%M%S")
    target = dest_dir / f"deals-{stamp}.sqlite"
    src = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
        ok = dst.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        dst.close()
        src.close()
    if not ok:
        target.unlink()
        raise RuntimeError("sauvegarde invalide (integrity_check)")
    olds = sorted(dest_dir.glob("deals-*.sqlite"))
    for old in olds[:-keep]:
        old.unlink()
    return target


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sauvegarde de la base DEALS")
    ap.add_argument("db")
    ap.add_argument("dest")
    ap.add_argument("--keep", type=int, default=14, help="nombre de sauvegardes conservées")
    a = ap.parse_args(argv)
    print(backup(a.db, a.dest, a.keep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
