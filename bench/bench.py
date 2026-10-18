"""Mesures : python -m bench.bench"""
import json
import random
import statistics
import threading
import time
import urllib.request

from listener import extract as X
from listener.core import Listener
from listener.fetch import Fetcher
from listener.server import serve
from tests.fakeweb import FIXTURES, RULE_FIXTURE, FakeWeb
from tests.test_listener import Clock


def extraction():
    ok, n, t = 0, 0, time.perf_counter()
    for _ in range(50):
        for name, (html, exp) in FIXTURES.items():
            r = X.extract(html)
            n += 1
            ok += (r is None) if exp is None else all(r.get(k) == v for k, v in exp.items())
    name, rules, exp = RULE_FIXTURE
    r = X.extract(FIXTURES[name][0], rules)
    per = (time.perf_counter() - t) / n * 1000
    print(f"1. Extraction : {ok // 50}/{len(FIXTURES)} formats corrects + règle de site {'OK' if all(r.get(k) == v for k, v in exp.items()) else 'KO'}, {per:.2f} ms/page")


def throughput(hosts=10, offers_per_host=30):
    webs = [FakeWeb().__enter__() for _ in range(hosts)]
    L = Listener(fetcher=Fetcher(min_interval=0, timeout=5), clock=Clock(), workers=16)
    for w in webs:
        for k in range(offers_per_host):
            w.live[str(k)] = (random.randint(200, 900) + .0, "InStock", None)
            L.track(f"{w.url}/live/{k}", 1)
    t = time.perf_counter()
    res = L.run_due(limit=10000)
    dt = time.perf_counter() - t
    for w in webs:
        w.__exit__()
    ok = sum(r["status"] == "ok" for r in res)
    print(f"2. Débit (réseau local, sans délai de politesse) : {len(res)} pages en {dt:.1f} s = {len(res) / dt:.0f} pages/s, {ok} OK")
    per_host_h = 3600 / 5
    print(f"   Avec politesse 5 s/site : {per_host_h:.0f} requêtes/h/site → ~{per_host_h * 6:.0f} offres/site en priorité normale (6 h), "
          f"~{per_host_h * 0.25:.0f} en prioritaire (15 min)")


def storage(offers=40, days=30):
    c = Clock()
    L = Listener(fetcher=Fetcher(min_interval=0, timeout=5), clock=c, workers=8)
    rng = random.Random(1)
    with FakeWeb() as w:
        for k in range(offers):
            w.live[str(k)] = (500.0, "InStock", None)
            L.track(f"{w.url}/live/{k}", 1)
        checks = 0
        for h in range(days * 24):
            for k in range(offers):
                if rng.random() < 0.01:  # ~ un changement tous les 4 jours par offre
                    p, a, g = w.live[str(k)]
                    w.live[str(k)] = (round(p * rng.uniform(0.9, 1.08)), a, g)
            checks += len(L.run_due(limit=10000))
            c.advance(3600)
        rows = L.q("SELECT COUNT(*) n FROM observations", one=True)["n"]
        stat = {}
        for r in L.q("SELECT status FROM checks"):
            stat[r["status"]] = stat.get(r["status"], 0) + 1
    print(f"3. Stockage sur {days} j, {offers} offres : {checks} vérifications → {rows} lignes d'historique "
          f"(÷{checks / rows:.0f}). Requêtes : {stat}")


def latency(n=20):
    c = Clock()
    L = Listener(fetcher=Fetcher(min_interval=0, timeout=5), clock=c)
    api = serve(L, 0)
    threading.Thread(target=api.serve_forever, daemon=True).start()
    got = []

    def listen():
        with urllib.request.urlopen(f"http://127.0.0.1:{api.server_address[1]}/api/stream", timeout=30) as r:
            for line in r:
                if line.startswith(b"data: ") and json.loads(line[6:])["type"] == "PRICE_DROP":
                    got.append(time.perf_counter())
                    if len(got) >= n:
                        return
    th = threading.Thread(target=listen, daemon=True)
    th.start()
    time.sleep(0.3)
    lat = []
    with FakeWeb() as w:
        w.live["x"] = (500.0, "InStock", None)
        oid = L.track(w.url + "/live/x", 1)
        L.check(oid)
        for k in range(n):
            w.live["x"] = (500.0 - 5 * (k + 1), "InStock", None)
            t = time.perf_counter()
            L.check(oid)
            while len(got) < k + 1:
                time.sleep(0.0005)
            lat.append((got[k] - t) * 1000)
    api.shutdown()
    api.server_close()
    print(f"4. Détection → événement reçu en SSE : médiane {statistics.median(lat):.1f} ms, max {max(lat):.1f} ms "
          f"(requête + extraction + enregistrement + diffusion, hors intervalle de passage)")


if __name__ == "__main__":
    extraction()
    throughput()
    storage()
    latency()
