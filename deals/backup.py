"""Sauvegarde à chaud de la base (API de sauvegarde SQLite : cohérente même pendant la passe de nuit), vérifiée, avec
rotation des plus anciennes."""
import sqlite3
from datetime import datetime
from pathlib import Path


def backup(db, dest_dir, keep=14, now=None):
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / f"deals-{(now or datetime.now()).strftime('%Y-%m-%d_%H%M%S')}.sqlite"
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
    for old in sorted(dest_dir.glob("deals-*.sqlite"))[:-keep]:
        old.unlink()
    return target
