"""Déployer et revenir en arrière (deploy/release.sh, lot 4) : une version s'installe à côté des précédentes, la base est
sauvegardée avant la bascule, des tests de fumée ratés ramènent la version d'avant — et la base d'avant quand la
nouvelle version l'avait migrée (un code plus ancien que sa base refuse de démarrer). Les services sont simulés
(SYSTEMCTL=true) ; le script, les archives et la base sont réels."""
import os
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from deals.store import SCHEMA_VERSION, Store

CODE = Path(__file__).resolve().parent.parent
SKIP = {".git", "__pycache__", "raw", "reports", "urls", "samples"}


def archive(dest, name, patch=None):
    """Une archive de version faite du code de travail ; patch(dossier) la modifie avant l'emballage."""
    work = Path(tempfile.mkdtemp()) / "v"
    shutil.copytree(CODE, work, ignore=lambda d, names: [n for n in names if n in SKIP or n.endswith((".sqlite", ".sqlite-wal", ".sqlite-shm"))])
    if patch:
        patch(work)
    path = Path(dest) / f"{name}.tar.gz"
    with tarfile.open(path, "w:gz") as t:
        for f in sorted(work.rglob("*")):
            t.add(f, arcname=str(f.relative_to(work)), recursive=False)
    return path


def migrating(work):
    """La version suivante : elle ajoute une migration (le schéma passe à v+1)."""
    p = work / "deals" / "store.py"
    s = p.read_text(encoding="utf-8")
    s = s.replace(f"SCHEMA_VERSION = {SCHEMA_VERSION}", f"SCHEMA_VERSION = {SCHEMA_VERSION + 1}")
    s = s.replace("\n}\n\n\ndef statements", f'\n    {SCHEMA_VERSION + 1}: ["ALTER TABLE meta ADD COLUMN essai TEXT"],\n}}\n\n\ndef statements', 1)
    p.write_text(s, encoding="utf-8")


class Release(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = {**os.environ, "DEALS_ROOT": str(self.tmp / "opt"), "DEALS_DATA": str(self.tmp / "data"),
                    "DEALS_BACKUPS": str(self.tmp / "bk"), "SYSTEMCTL": "true", "PYTHON": "python3", "DEALS_SMOKE": "true"}
        (self.tmp / "data").mkdir()
        self.db = self.tmp / "data" / "deals.sqlite"

    def run_(self, *args, smoke="true"):
        r = subprocess.run(["sh", str(CODE / "deploy" / "release.sh"), *args], env={**self.env, "DEALS_SMOKE": smoke},
                           capture_output=True, text=True, timeout=120)
        return r.returncode, r.stdout + r.stderr

    def current(self):
        return Path(os.readlink(self.tmp / "opt" / "current")).name

    def schema(self):
        with closing(sqlite3.connect(self.db)) as c:            # fermée : la base est remplacée sous nos pieds
            return c.execute("PRAGMA user_version").fetchone()[0]

    def test_install_backup_failed_smoke_and_rollback(self):
        a = archive(self.tmp, "promocentral-20261031-110000-aaaaaaa")
        code, out = self.run_("install", str(a))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.current(), "promocentral-20261031-110000-aaaaaaa")
        Store(str(self.db)).close()                                     # la base de la version en service
        self.assertEqual(self.schema(), SCHEMA_VERSION)
        b = archive(self.tmp, "promocentral-20261031-120000-bbbbbbb", migrating)
        migrate_then_fail = f"python3 {self.tmp}/opt/current/deals.py --db {self.db} status >/dev/null; false"
        code, out = self.run_("install", str(b), smoke=migrate_then_fail)
        self.assertNotEqual(code, 0)
        self.assertIn("retour à", out)
        self.assertIn("restauration", out)                               # la nouvelle version avait migré la base
        self.assertEqual(self.current(), "promocentral-20261031-110000-aaaaaaa")
        self.assertEqual(self.schema(), SCHEMA_VERSION)                  # la base d'avant : l'ancien code redémarre
        Store(str(self.db)).close()
        self.assertTrue(list((self.tmp / "bk").glob("deals-*.sqlite")))

    def test_rollback_command_and_listing(self):
        self.run_("install", str(archive(self.tmp, "promocentral-20261031-110000-aaaaaaa")))
        Store(str(self.db)).close()
        code, out = self.run_("install", str(archive(self.tmp, "promocentral-20261031-120000-bbbbbbb", migrating)),
                              smoke=f"python3 {self.tmp}/opt/current/deals.py --db {self.db} status >/dev/null")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.schema(), SCHEMA_VERSION + 1)
        code, out = self.run_("list")
        self.assertIn("* promocentral-20261031-120000-bbbbbbb  (en service)", out)
        code, out = self.run_("rollback")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.current(), "promocentral-20261031-110000-aaaaaaa")
        self.assertEqual(self.schema(), SCHEMA_VERSION)
        code, out = self.run_("rollback")
        self.assertNotEqual(code, 0)
        self.assertIn("pas de version précédente", out)

    def test_an_installed_version_is_never_overwritten(self):
        a = archive(self.tmp, "promocentral-20261031-110000-aaaaaaa")
        self.run_("install", str(a))
        code, out = self.run_("install", str(a))
        self.assertNotEqual(code, 0)
        self.assertIn("déjà installée", out)


class Smoke(unittest.TestCase):
    def test_smoke_checks_pass_on_a_running_app_and_fail_elsewhere(self):
        import socket
        import threading

        from deals.api import Api
        from deals.config import Settings
        from deals.web import make_server
        store = Store(str(Path(tempfile.mkdtemp()) / "s.sqlite"))
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        settings = Settings()
        srv = make_server(Api(store, settings), store, settings, port=port)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            r = subprocess.run(["python3", str(CODE / "deploy" / "smoke.py"), f"http://127.0.0.1:{port}"], capture_output=True,
                               text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertEqual(r.stdout.count("ok "), 7)
        finally:
            srv.shutdown()
            srv.server_close()
            store.close()
        r = subprocess.run(["python3", "-c", f"import sys; sys.path.insert(0, '{CODE / 'deploy'}'); import smoke; "
                                             f"sys.exit(smoke.main('http://127.0.0.1:{port}', wait_s=1))"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ne répond pas", r.stdout)


if __name__ == "__main__":
    unittest.main()
