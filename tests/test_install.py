"""L'installation en une commande (deploy/install.sh) : en démo, la plateforme s'installe sans mentions légales, sans
e-mail, sans flux ni partenaire réel, et se remplit de données simulées ; en production, une configuration incomplète
est refusée avant toute bascule. Les services sont simulés (SYSTEMCTL=true), les fichiers, la base et les archives sont
réels, dans un dépôt jetable qui reprend le code courant."""
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
SKIP = {".git", "__pycache__", "raw", "reports", "urls", "samples"}


def clone_repo(dest):
    """Une copie du code courant, commitée : install.sh n'accepte qu'un dépôt propre."""
    shutil.copytree(CODE, dest, ignore=lambda d, names: [n for n in names if n in SKIP or n.endswith((".sqlite", ".sqlite-wal", ".sqlite-shm"))])
    git = lambda *a: subprocess.run(["git", "-c", "user.name=essai", "-c", "user.email=essai@example.invalid",
                                     "-c", "commit.gpgsign=false", *a], cwd=dest, capture_output=True, text=True, check=True)
    git("init", "-q")
    git("add", "-A")
    git("commit", "-qm", "essai")
    return dest


class Install(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp())
        cls.repo = clone_repo(cls.base / "depot")

    def sandbox(self, name):
        """Les dossiers d'une installation d'essai : racine, données, sauvegardes, configuration, unités systemd."""
        d = Path(tempfile.mkdtemp(prefix=name + "-"))
        paths = {k: d / k for k in ("opt", "data", "bk", "etc", "units")}
        for p in paths.values():
            p.mkdir()
        return paths

    def env(self, paths, **extra):
        return {**os.environ, "DEALS_ROOT": str(paths["opt"]), "DEALS_DATA": str(paths["data"]),
                "DEALS_BACKUPS": str(paths["bk"]), "DEALS_ETC": str(paths["etc"]), "DEALS_UNITS": str(paths["units"]),
                "SYSTEMCTL": "true", "PYTHON": "python3", "DEALS_NO_USER": "1", "DEALS_RUN_AS": "env",
                "DEALS_SMOKE": "true", "DEALS_KEEP": "5", "DEALS_BIN": str(paths["opt"] / "bin"), **{k: v for k, v in extra.items() if v is not None}}

    def install(self, mode, env):
        return subprocess.run(["sh", str(self.repo / "deploy" / "install.sh"), mode], cwd=self.repo, env=env,
                              capture_output=True, text=True, timeout=300)

    def test_demo_installs_without_any_real_configuration_and_fills_simulated_market(self):
        p = self.sandbox("demo")
        r = self.install("demo", self.env(p, DEALS_ENV="demo"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((p["units"] / "deals-web.service").exists())
        self.assertTrue((p["opt"] / "bin" / "deals").exists(), "la commande d'exploitation est installée")
        self.assertFalse((p["units"] / "deals-daily.service").exists(), "la démo ne lance aucune nuit réelle")
        env = (p["etc"] / "deals.env").read_text(encoding="utf-8")
        self.assertIn("DEALS_ENV=demo", env)
        self.assertEqual(oct((p["etc"] / "deals.env").stat().st_mode & 0o777), "0o600")
        self.assertFalse(any(line.startswith("DEALS_SMTP_HOST=") and line.split("=", 1)[1].strip() for line in env.splitlines()))
        self.assertFalse((p["etc"] / "affiliate.json").exists() or (p["etc"] / "sources.json").exists(),
                         "pas de partenaire ni de flux en démo")
        self.assertTrue(Path(os.readlink(p["opt"] / "current")).name.startswith("promocentral-"))
        with closing(sqlite3.connect(p["data"] / "deals.sqlite")) as c:
            self.assertGreater(c.execute("SELECT COUNT(*) FROM products").fetchone()[0], 0, "le marché simulé est en place")
            self.assertGreater(c.execute("SELECT COUNT(*) FROM catalog").fetchone()[0], 0, "le catalogue est publié")
        self.assertIn("offres publiées (données simulées)", r.stdout + r.stderr)

    def test_demo_reinstall_updates_without_losing_the_database(self):
        p = self.sandbox("maj")
        env = self.env(p, DEALS_ENV="demo")
        self.assertEqual(self.install("demo", env).returncode, 0)
        with closing(sqlite3.connect(p["data"] / "deals.sqlite")) as c:
            before = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        time.sleep(1.1)                                  # une autre archive (le nom porte la seconde)
        r = self.install("demo", env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("rien à faire", r.stdout + r.stderr)
        with closing(sqlite3.connect(p["data"] / "deals.sqlite")) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM products").fetchone()[0], before)
        self.assertEqual(len([d for d in (p["opt"] / "releases").iterdir() if d.is_dir()]), 2, "deux versions gardées")

    def test_production_refuses_an_incomplete_configuration_before_switching(self):
        p = self.sandbox("prod")
        r = self.install("prod", self.env(p, DEALS_ENV="prod"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("configuration à régler", r.stdout + r.stderr)
        self.assertFalse((p["opt"] / "current").exists(), "rien n'est basculé")

    def test_a_demo_configuration_is_never_used_for_production(self):
        p = self.sandbox("melange")
        (p["etc"] / "deals.env").write_text("DEALS_ENV=demo\n", encoding="utf-8")
        r = self.install("prod", self.env(p))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("ne partagent jamais une configuration", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
