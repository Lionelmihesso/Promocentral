"""Sauvegarde : copie cohérente, vérifiée, rotation."""
import importlib.util
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

spec = importlib.util.spec_from_file_location("backup", Path(__file__).resolve().parent.parent / "deploy" / "backup.py")
backup = importlib.util.module_from_spec(spec); spec.loader.exec_module(backup)


class Backup(unittest.TestCase):
    def test_copy_is_consistent_and_rotated(self):
        d = Path(tempfile.mkdtemp())
        db = d / "deals.sqlite"
        c = sqlite3.connect(db); c.execute("PRAGMA journal_mode=WAL"); c.execute("CREATE TABLE saves(x)")
        c.executemany("INSERT INTO saves VALUES (?)", [(i,) for i in range(100)]); c.commit()
        t0 = datetime(2026, 10, 1)
        for k in range(5):
            out = backup.backup(db, d / "b", keep=3, now=t0 + timedelta(days=k))
        files = sorted((d / "b").glob("deals-*.sqlite"))
        self.assertEqual(len(files), 3)                                   # rotation
        self.assertEqual(files[-1], out)
        self.assertEqual(sqlite3.connect(out).execute("SELECT COUNT(*) FROM saves").fetchone()[0], 100)
        c.close()


if __name__ == "__main__":
    unittest.main()
