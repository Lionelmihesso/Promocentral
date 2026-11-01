"""Les fichiers de déploiement disent exactement ce que le code lit (deploy/README.md) : chaque variable de
deals.env.example est un réglage du code ; chaque source d'exemple est désactivée et sa variable existe ; copier
l'exemple des partenaires ne déclare aucune enseigne ; chaque service lance une commande que le code connaît ; Caddy
relaie vers l'adresse où l'app écoute, et elle seule."""
import io
import json
import re
import unittest
from contextlib import redirect_stdout
from dataclasses import fields
from pathlib import Path

from deals import affiliate, cli, config
from deals.ingest import registry
from deals.ingest.retailers import RETAILERS

DEPLOY = Path(__file__).resolve().parent.parent / "deploy"


def env_file(path):
    """Les lignes NOM=valeur d'un fichier d'environnement, lues comme systemd les lit (pas de commentaire en fin de ligne)."""
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith(("#", ";")):
            name, _, value = line.partition("=")
            out[name.strip()] = value.strip()
    return out


def unit(name):
    sections, cur = {}, None
    for line in (DEPLOY / name).read_text(encoding="utf-8").splitlines():
        if line.startswith("["):
            cur = sections.setdefault(line.strip("[]"), [])
        elif "=" in line and not line.startswith("#"):
            cur.append(tuple(x.strip() for x in line.split("=", 1)))
    return sections


class Examples(unittest.TestCase):
    def test_every_variable_of_the_env_example_is_read_by_the_code(self):
        env = env_file(DEPLOY / "deals.env.example")
        settings = {"DEALS_" + f.name.upper() for f in fields(config.Settings)}
        sources = json.loads((DEPLOY / "sources.example.json").read_text(encoding="utf-8"))
        feeds = {m for s in sources.values() for m in registry.VAR.findall(s.get("url", ""))}
        self.assertEqual(set(env) - settings - feeds, set(), "variables que le code ne lit pas")
        self.assertEqual(feeds - set(env), set(), "variables de flux citées par sources.example.json mais absentes")
        self.assertFalse([k for k, v in env.items() if " #" in v], "commentaire en fin de ligne : systemd le garde")
        s = config.load(env)                                       # l'exemple se charge tel quel
        self.assertEqual((s.env, s.affiliate, s.sources), ("prod", "/etc/deals/affiliate.json", "/etc/deals/sources.json"))
        self.assertTrue(s.raw_dir.startswith("/var/lib/deals"))    # jamais dans le dossier du code

    def test_the_source_example_reads_nothing_until_a_source_is_enabled(self):
        specs = registry.load(str(DEPLOY / "sources.example.json"), env={})
        examples = json.loads((DEPLOY / "sources.example.json").read_text(encoding="utf-8"))
        self.assertTrue(examples)
        self.assertFalse([k for k in examples if specs[k]["enabled"]], "une source d'exemple activée")
        self.assertTrue(all(specs[k]["kind"] == "feed" for k in examples))

    def test_copying_the_partner_example_declares_no_retailer(self):
        rules = affiliate.load(str(DEPLOY / "affiliate.example.json"))
        known = set(RETAILERS) | set(json.loads((DEPLOY / "sources.example.json").read_text(encoding="utf-8")))
        self.assertEqual(set(rules) & known, set(), "l'exemple ferait d'une vraie enseigne un partenaire")
        self.assertTrue(all("{subid}" in r for r in rules.values()))   # les deux formes de règle, avec l'identifiant du clic

    def test_the_offsite_example_names_a_repository_and_no_secret(self):
        env = env_file(DEPLOY / "offsite.env.example")
        self.assertTrue(env["RESTIC_REPOSITORY"].startswith("s3:https://"))
        self.assertEqual([env[k] for k in ("RESTIC_PASSWORD", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")], ["", "", ""])


class Services(unittest.TestCase):
    def command(self, line):
        """Les arguments donnés à deals.py ; le code doit les accepter (--help : l'analyse, sans rien lancer)."""
        args = line.split("/opt/deals/current/deals.py", 1)[1].split()
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) as e:
            cli.main([a for a in args if a != '"$@"'] + ["--help"])
        self.assertEqual(e.exception.code, 0, f"commande refusée : {args}")
        return args

    def test_each_service_runs_a_command_the_code_knows_as_the_deals_user(self):
        for name, cmd in (("deals-web.service", "serve"), ("deals-daily.service", "nightly"), ("deals-backup.service", "backup")):
            svc = dict(unit(name)["Service"])
            self.assertEqual((svc["User"], svc["Group"]), ("deals", "deals"), name)
            self.assertIn(cmd, self.command(svc["ExecStart"]), name)
            self.assertIn("/var/lib/deals", svc["ReadWritePaths"], name)
            self.assertEqual(svc.get("ProtectSystem"), "strict", name)
            if cmd != "backup":
                self.assertEqual(svc["EnvironmentFile"], "/etc/deals/deals.env", name)
        wrapper = (DEPLOY / "deals").read_text(encoding="utf-8")
        self.assertIn("EnvironmentFile=/etc/deals/deals.env", wrapper)
        self.command(wrapper.split("\n  /usr/bin/python3 ", 1)[1].replace("\\\n", " ") + " status")
        for name in ("deals-daily.timer", "deals-backup.timer", "deals-offsite.timer"):
            self.assertIn("OnCalendar", dict(unit(name)["Timer"]), name)

    def test_caddy_relays_to_the_address_the_app_listens_on_and_nothing_else(self):
        caddy = [line for line in (DEPLOY / "Caddyfile").read_text(encoding="utf-8").splitlines() if not line.startswith("#")]
        self.assertEqual(re.findall(r"reverse_proxy\s+(\S+)", "\n".join(caddy)), ["127.0.0.1:8000"])
        web = dict(unit("deals-web.service")["Service"])["ExecStart"]
        self.assertIn("--port 8000", web)
        from deals.web import make_server
        self.assertEqual(make_server.__defaults__[0], "127.0.0.1")     # l'app n'écoute que sur la machine


if __name__ == "__main__":
    unittest.main()
