"""Serveur web et passe de nuit : deux processus, un même fichier SQLite.
Pendant une longue passe groupée, un favori doit s'enregistrer, et vite (le verrou n'est jamais tenu plus d'une seconde)."""
import multiprocessing as mp
import os
import tempfile
import time
import unittest

from listener.core import Listener
from radar.engine import Radar

HOLD_S = 5


def _night(path, ready):
    with Listener(path, workers=1) as L:
        Radar(L)
        with L.batch():
            ready.set()
            t0, i = time.time(), 0
            while time.time() - t0 < HOLD_S:
                L.q("INSERT INTO jobs(name, key, started, status) VALUES ('sim', ?, ?, 'x')", (str(i), time.time()))
                i += 1
                time.sleep(0.01)


def _web(path, out):
    with Listener(path, workers=1) as L:
        Radar(L)
        waits = []
        for k in range(3):
            t = time.time()
            try:
                L.q("INSERT OR IGNORE INTO saves(user_id, product_id, created_at) VALUES (1, ?, 0)", (k,))
                waits.append(time.time() - t)
            except Exception as e:  # noqa: BLE001
                out.put(("error", str(e)))
            time.sleep(1)
        out.put(("waits", waits))


class WebWritesDuringNightlyPass(unittest.TestCase):
    def test_saves_succeed_quickly_during_the_nightly_transaction(self):
        path = os.path.join(tempfile.mkdtemp(), "t.sqlite")
        with Listener(path) as L:
            Radar(L)
        ctx = mp.get_context("spawn")
        ready, out = ctx.Event(), ctx.Queue()
        night = ctx.Process(target=_night, args=(path, ready)); night.start()
        self.assertTrue(ready.wait(20))
        web = ctx.Process(target=_web, args=(path, out)); web.start()
        web.join(30); night.join(30)
        results = []
        while not results or results[-1][0] != "waits":           # portable (Queue.qsize n'existe pas sur macOS)
            results.append(out.get(timeout=10))
        errors = [r for r in results if r[0] == "error"]
        waits = results[-1][1]
        self.assertEqual(errors, [])
        self.assertEqual(len(waits), 3)
        self.assertLess(max(waits), 2.5, waits)                # avant correctif : échecs « database is locked »
        with Listener(path) as L:
            self.assertEqual(L.q("SELECT COUNT(*) n FROM saves", one=True)["n"], 3)


if __name__ == "__main__":
    unittest.main()
