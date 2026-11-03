"""Les frontières de la plateforme, vérifiées sur le code (docs/ARCHITECTURE.md) : un module qui en franchit une casse ce
test, pas la production. Monolithe modulaire : des couches qui se parlent par des contrats, pas des services.

  ingestion   ingest/ (sources, flux, fiches, lots)          → écrit par market.py, jamais l'app
  marché      market.py, quarantine.py                       → les seuls à écrire produits, offres, prix
  publication publish.py                                      → le seul à écrire le catalogue publié
  moteurs     extract/, ontology/, judge, alternatives, query, funnel, ingest/feeds, ingest/contract : purs (ni base, ni
              réseau)
  app         api, web, catalog, missions, accounts, activity, profile : lisent le catalogue publié, jamais l'ingestion
"""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "deals"
PURE = ["extract/__init__.py", "extract/offer.py", "extract/page.py", "extract/categories.py", "ontology/__init__.py",
        "judge.py", "alternatives.py", "query.py", "funnel.py", "labels.py", "ingest/feeds.py", "ingest/contract.py",
        "ingest/retailers.py"]
APP = ["api.py", "web.py", "catalog.py", "missions.py", "accounts.py", "activity.py", "profile.py", "funnel.py", "query.py"]
IMPURE = {"sqlite3", "socket", "urllib.request", "http.client", "http.server", "deals.store", "deals.market",
          "deals.ingest.batches", "deals.ingest.collector", "deals.api", "deals.web"}
WRITERS = {  # table → les seuls fichiers qui l'écrivent (store.py : le schéma et ses migrations)
    "products": {"market.py"}, "offers": {"market.py"}, "prices": {"market.py", "quarantine.py"},
    "catalog": {"publish.py"}, "catalog_offers": {"publish.py"}, "alternatives": {"publish.py"}, "similar": {"publish.py"},
    "batches": {"ingest/batches.py"}, "batch_rejects": {"ingest/batches.py"},
}


def modname(path):
    rel = path.relative_to(ROOT.parent).with_suffix("")
    return ".".join(rel.parts).removesuffix(".__init__")


def imports(path):
    """Les modules qu'importe un fichier : absolus, et relatifs résolus (deals.…)."""
    tree, out = ast.parse(path.read_text(encoding="utf-8")), set()
    pkg = modname(path) if path.name == "__init__.py" else modname(path).rpartition(".")[0]
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            if n.level:
                base = pkg.split(".")[: len(pkg.split(".")) - (n.level - 1)]
                mod = ".".join(base + ([n.module] if n.module else []))
                out |= {f"{mod}.{a.name}" for a in n.names} | {mod}
            else:
                out |= {n.module} | {f"{n.module}.{a.name}" for a in n.names}
    return out


def files():
    return [p for p in ROOT.rglob("*.py") if "vendor" not in p.parts and "__pycache__" not in p.parts]


class Boundaries(unittest.TestCase):
    def test_engines_are_pure(self):
        for f in PURE:
            bad = {m for m in imports(ROOT / f) if any(m == x or m.startswith(x + ".") for x in IMPURE)}
            self.assertEqual(bad, set(), f"{f} doit rester pur (ni base, ni réseau) : {bad}")

    def test_the_app_never_reads_ingestion(self):
        for f in APP:
            bad = {m for m in imports(ROOT / f) if m.startswith("deals.ingest")}
            self.assertEqual(bad, set(), f"{f} lit le catalogue publié, pas l'ingestion : {bad}")

    def test_ingestion_never_reaches_into_the_app(self):
        app = {"deals." + f[:-3] for f in APP if f not in ("query.py", "funnel.py")}
        for p in (ROOT / "ingest").rglob("*.py"):
            bad = {m for m in imports(p) if any(m == x or m.startswith(x + ".") for x in app)}
            self.assertEqual(bad, set(), f"{p.relative_to(ROOT)} : l'ingestion ne dépend pas de l'app : {bad}")

    def test_each_table_has_its_writers(self):
        pattern = re.compile(r"(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|REPLACE\s+INTO)\s+(\w+)", re.I)
        for p in files():
            rel = str(p.relative_to(ROOT))
            if rel == "store.py":
                continue
            for table in set(pattern.findall(p.read_text(encoding="utf-8"))):
                allowed = WRITERS.get(table)
                if allowed is not None:
                    self.assertIn(rel, allowed, f"{rel} écrit {table}, réservée à {sorted(allowed)}")

    def test_the_front_writes_nothing_of_the_catalog(self):
        """v67 : le front reçoit le catalogue de l'API (/api/r/catalog, les cartes, la recherche) ; aucune clé ni aucun nom
        de rayon, de famille, de pièce ou d'univers n'est écrit dans son code : un rayon, une famille ou une pièce de plus,
        ou de moins, après une nuit, ne demande aucun changement du front. Seul art.jsx connaît des rayons : un dessin par
        rayon, et un colis pour un rayon qu'il ne connaît pas."""
        from deals import ontology
        from deals.extract.categories import FAMILY_OF
        from deals.labels import ROOMS, UNIVERSES
        web = ROOT.parent / "web" / "src"
        code = re.sub(r"/\*.*?\*/|//[^\n]*", "", (web / "App.jsx").read_text(encoding="utf-8"), flags=re.S)
        keys = set(FAMILY_OF) | set(FAMILY_OF.values()) | set(ROOMS) | set(UNIVERSES)
        self.assertEqual({k for k in keys if re.search(rf"[\"'`]{k}[\"'`,]", code)}, set())
        names = {label for label, _ in [*ontology.FAMILIES.values(), *ROOMS.values(), *UNIVERSES.values()]}
        self.assertEqual({n for n in names if n in code}, set())
        self.assertIn('api("catalog")', code)
        self.assertIn("(DRAW[category] || parcel)", (web / "art.jsx").read_text(encoding="utf-8"))

    def test_quarantine_only_marks_prices_rejected(self):
        src = (ROOT / "quarantine.py").read_text(encoding="utf-8")
        writes = re.findall(r"(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+prices[^\"']*", src, re.I)
        self.assertEqual([w.split("WHERE")[0].strip() for w in writes], ["UPDATE prices SET rejected=1"])


if __name__ == "__main__":
    unittest.main()
