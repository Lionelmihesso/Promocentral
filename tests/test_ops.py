"""Exploitation : la passe de nuit et le serveur partagent la base sans se gêner ; la sauvegarde à chaud est cohérente ;
une base ancienne est migrée sur place ; la démo se construit avec la vraie chaîne, alternatives moins chères comprises."""
import json
import multiprocessing as mp
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path

from deals import config, demo, sim, store
from deals.api import Api, Request
from deals.backup import backup
from deals.catalog import position
from deals.store import Store


def _night(path, ready, seconds):
    s = Store(path)
    ready.set()
    t0, i = time.time(), 0
    while time.time() - t0 < seconds:                     # comme la collecte : une transaction courte par page relue,
        with s.tx():                                      # ici 50 par seconde (la vraie passe en fait moins de 2)
            s.x("INSERT INTO runs(day, started) VALUES (?,?)", (str(i), time.time()))
            time.sleep(0.005)
        time.sleep(0.015)
        i += 1
    s.close()


def _web(path, out):
    s = Store(path)
    s.x("INSERT OR IGNORE INTO users(id, email, created_at) VALUES (1, 'a@b.c', 0)")
    waits = []
    for k in range(20):
        t = time.time()
        s.x("INSERT OR IGNORE INTO saves(user_id, product_id, created_at) VALUES (1, ?, 0)", (k,))
        waits.append(time.time() - t)
        time.sleep(0.05)
    s.close()
    out.put(max(waits))


class Ops(unittest.TestCase):
    def test_web_writes_never_wait_during_the_night(self):
        path = str(Path(tempfile.mkdtemp(), "t.sqlite"))
        Store(path).close()
        ctx = mp.get_context("spawn")
        ready, out = ctx.Event(), ctx.Queue()
        night = ctx.Process(target=_night, args=(path, ready, 2.0))
        night.start()
        self.assertTrue(ready.wait(20))
        web = ctx.Process(target=_web, args=(path, out))
        web.start()
        worst = out.get(timeout=30)
        web.join(10)
        night.join(10)
        self.assertLess(worst, 0.25)                      # avant : jusqu'à 1 s d'attente, ou « database is locked »

    def test_older_database_is_migrated_in_place(self):
        path = Path(tempfile.mkdtemp(), "v1.sqlite")
        with closing(sqlite3.connect(path)) as c:                                       # une base de la version 1, déjà remplie
            c.executescript(store.SCHEMA + "PRAGMA user_version=1;")
            c.execute("INSERT INTO catalog(product_id, name, title, price, search, published_on) VALUES (1, 'x', 'x', 10, ' x ', '2026-01-01')")
            c.commit()
        s = Store(path)
        self.assertEqual(s.q("PRAGMA user_version", one=True)["user_version"], store.SCHEMA_VERSION)
        row = s.q("SELECT * FROM catalog", one=True)
        self.assertEqual((row["name"], row["since"], row["ends"]), ("x", None, None))
        self.assertEqual(s.q("SELECT COUNT(*) n FROM alternatives", one=True)["n"], 0)          # version 3
        self.assertNotIn("specs", row)                                                           # versions 4 puis 7
        self.assertEqual((row["history"], s.q("SELECT COUNT(*) n FROM meta", one=True)["n"]), (None, 0))   # version 5
        self.assertEqual((row["attrs"], s.q("SELECT COUNT(*) n FROM missions", one=True)["n"]), (None, 0))  # version 6
        s.close()

    def test_hot_backup(self):
        d = Path(tempfile.mkdtemp())
        s = Store(d / "deals.sqlite")
        s.x("INSERT INTO users(email, created_at) VALUES ('a@b.c', 0)")
        for i in range(16):
            target = backup(d / "deals.sqlite", d / "bk", keep=14, now=datetime(2026, 1, 1 + i))
        self.assertEqual(len(list((d / "bk").glob("deals-*.sqlite"))), 14)
        with closing(sqlite3.connect(target)) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
        s.close()

    def test_demo_runs_the_real_chain(self):
        s = Store(Path(tempfile.mkdtemp(), "d.sqlite"))
        market, clock = demo.build(s, nights=20)
        api = Api(s, config.load({}), clock=clock)
        self.assertEqual(api.handle(Request("GET", "/api/r/categories")).status, 200)
        self.assertEqual(s.q("SELECT COUNT(*) n FROM catalog", one=True)["n"], len(sim.SHOWCASE) + len(sim.SHOWCASE_MORE) + len(sim.SHOWCASE_TECH))   # toute la vitrine
        self.assertEqual(s.q("SELECT COUNT(*) n FROM runs", one=True)["n"], 21)                     # une nuit par jour
        v15 = s.q("SELECT product_id, price FROM catalog WHERE title LIKE '%V15%'", one=True)      # l'aspirateur haut de gamme
        item = api.handle(Request("GET", f"/api/r/item/{v15['product_id']}")).body
        alts = item["alternatives"]
        self.assertEqual(len(alts), 3)
        self.assertTrue(all(a["category"] == "aspirateur" and "sans fil" in a["title"] and a["price"] <= 0.9 * v15["price"]
                            and a["saving"] == round(v15["price"] - a["price"]) for a in alts))
        self.assertEqual(len({a["brand"] for a in alts}), 3)
        self.assertNotIn("Agile", " ".join(a["title"] for a in alts))                               # 30 min : pas un remplaçant
        for r in s.q("SELECT c.price, c.history, c.level, c.span, c.usual, o.availability FROM catalog c "
                     "JOIN catalog_offers o ON o.product_id=c.product_id AND o.rank=0"):        # le verdict de prix, publié
            pos = position(json.loads(r["history"]), r["price"]) if r["availability"] != "out_of_stock" else None
            self.assertEqual((r["level"], r["span"], r["usual"]), (pos["level"], pos["days"], pos["usual"]) if pos else (None, None, None))
        self.assertTrue(s.q("SELECT COUNT(*) n FROM catalog WHERE level IS NOT NULL", one=True)["n"])
        s.close()


if __name__ == "__main__":
    unittest.main()
