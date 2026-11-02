"""Le mode démo (DEALS_ENV=demo) démarre sans SMTP, sans flux ni partenaire réel, sans mention légale, et le dit ;
la production refuse toujours une configuration incomplète. Les tests lancent de vrais processus (deals.py) sur une
base temporaire."""
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from deals import config, web

CODE = Path(__file__).resolve().parent.parent
BASE_ENV = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "/tmp")}


def cli(env, *args, timeout=300):
    return subprocess.run([sys.executable, str(CODE / "deals.py"), *args], cwd=CODE, env={**BASE_ENV, **env},
                          capture_output=True, text=True, timeout=timeout)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        with e:                                                  # fermée : pas de ResourceWarning (Python 3.14)
            return e.code, e.read().decode("utf-8", "replace")


class Config(unittest.TestCase):
    def test_env_must_be_dev_demo_or_prod(self):
        with self.assertRaisesRegex(ValueError, "DEALS_ENV"):
            config.load({"DEALS_ENV": "staging"})

    def test_demo_needs_nothing_and_production_always_needs_its_legal_identity(self):
        self.assertEqual(config.problems(config.load({"DEALS_ENV": "demo"})), [])
        todo = config.problems(config.load({"DEALS_ENV": "prod"}))
        self.assertTrue(any("mentions légales" in t for t in todo), todo)

    def test_production_refuses_example_values(self):
        s = config.load({"DEALS_ENV": "prod", "DEALS_PUBLIC_URL": "https://promocentral.example.fr"})
        self.assertTrue(any("valeurs d'exemple" in t for t in config.problems(s)))


class Cli(unittest.TestCase):
    def test_production_serve_refuses_missing_legal_mentions(self):
        db = Path(tempfile.mkdtemp()) / "p.sqlite"
        r = cli({"DEALS_ENV": "prod"}, "--db", str(db), "serve", "--port", str(free_port()))
        self.assertEqual(r.returncode, 1)
        self.assertIn("DEALS_LEGAL_EDITOR", r.stderr)
        self.assertFalse(db.exists() and db.stat().st_size > 0, "rien n'est écrit quand la configuration est refusée")

    def test_check_says_ready_for_demo_and_lists_what_production_lacks(self):
        db = str(Path(tempfile.mkdtemp()) / "c.sqlite")
        ok = cli({"DEALS_ENV": "demo"}, "--db", db, "check")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("données simulées et fictives", ok.stdout)
        ko = cli({"DEALS_ENV": "prod"}, "--db", db, "check")
        self.assertEqual(ko.returncode, 1)
        self.assertIn("point(s) à régler", ko.stdout)

    def test_demo_refuses_everything_that_reads_real_sites_or_sends_mail(self):
        db = str(Path(tempfile.mkdtemp()) / "r.sqlite")
        for cmd in ("nightly", "missions", "discover", "ingest", "publish"):
            r = cli({"DEALS_ENV": "demo"}, "--db", db, cmd, *(["all"] if cmd in ("discover", "ingest") else []))
            self.assertEqual(r.returncode, 1, cmd)
            self.assertIn("indisponible en mode démo", r.stderr, cmd)

    def test_seed_demo_only_in_demo(self):
        db = str(Path(tempfile.mkdtemp()) / "s.sqlite")
        r = cli({"DEALS_ENV": "prod"}, "--db", db, "seed-demo")
        self.assertEqual(r.returncode, 1)
        self.assertIn("réservé au mode démo", r.stderr)


class Banner(unittest.TestCase):
    def test_the_demo_page_says_its_data_is_fictive_and_the_real_page_does_not(self):
        self.assertIn(b"demo-banner", web.app_page(demo=True))
        self.assertNotIn(b"demo-banner", web.app_page(demo=False))
        self.assertIn("fictives".encode(), web.app_page(demo=True))

    def test_the_banner_sits_above_the_app_and_covers_nothing(self):
        """v65 : fixé en bas de l'écran, le bandeau cachait la barre d'onglets d'un téléphone et prenait ses gestes. Il est
        maintenant le premier élément de la page, dans le flux, avant l'app : il ne recouvre rien."""
        page = web.app_page(demo=True)
        banner = page[page.index(b"<div id=\"demo-banner\""):page.index(b"</div>", page.index(b"demo-banner")) + 6]
        self.assertLess(page.index(b"demo-banner"), page.index(b'id="root"'))
        self.assertNotIn(b"position:fixed", banner)
        self.assertNotIn(b"position:absolute", banner)


class Demo(unittest.TestCase):
    """Un vrai serveur en démo, sur une base remplie par le marché simulé, sans aucune configuration réelle."""

    @classmethod
    def setUpClass(cls):
        cls.db = str(Path(tempfile.mkdtemp()) / "demo.sqlite")
        cls.port = free_port()
        cls.env = {"DEALS_ENV": "demo", "DEALS_PUBLIC_URL": f"http://127.0.0.1:{cls.port}",
                   "DEALS_OUTBOX": str(Path(tempfile.mkdtemp()) / "outbox.log")}
        r = cli(cls.env, "--db", cls.db, "seed-demo")
        assert r.returncode == 0, r.stdout + r.stderr
        cls.server = subprocess.Popen([sys.executable, str(CODE / "deals.py"), "--db", cls.db, "serve", "--port", str(cls.port)],
                                      cwd=CODE, env={**BASE_ENV, **cls.env}, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        base = f"http://127.0.0.1:{cls.port}"
        for _ in range(100):
            try:
                get(base + "/api/r/health")
                break
            except OSError:
                time.sleep(0.2)
        cls.base = base

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        cls.server.wait(10)
        cls.server.stderr.close()

    def test_the_app_starts_without_smtp_affiliate_sources_or_legal_mentions(self):
        self.assertIsNone(self.server.poll(), "le serveur tourne")
        status, body = get(self.base + "/")
        self.assertEqual(status, 200)
        self.assertIn("demo-banner", body)
        self.assertIn("Promo Central", body)

    def test_the_demo_is_healthy_and_says_so(self):
        status, body = get(self.base + "/api/r/health")
        self.assertEqual(status, 200, body)
        self.assertIn('"demo": true', body)
        self.assertIn('"status": "ok"', body)

    def test_the_legal_page_publishes_no_invented_identity(self):
        status, body = get(self.base + "/api/r/legal")
        self.assertEqual(status, 200)
        self.assertIn('"demo": true', body)
        self.assertIn('"editor": null', body)
        self.assertIn('"registration": null', body)

    def test_search_and_robot_page_answer(self):
        status, body = get(self.base + "/api/r/search?q=lave-linge")
        self.assertEqual(status, 200)
        self.assertIn('"products"', body)
        status, body = get(self.base + "/robot")
        self.assertEqual(status, 200)
        self.assertIn("PromoCentralBot", body)

    def test_nothing_else_is_served(self):
        status, _ = get(self.base + "/admin")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
