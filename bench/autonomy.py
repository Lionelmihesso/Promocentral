"""Pannes injectées, nuit après nuit : ce que la plateforme voit, dit, fait seule, et ce qu'elle laisse passer.

Le marché simulé de la démo (59 produits, quatre enseignes, une source chacune), chauffé 50 nuits par la vraie nuit
(night.run), puis, pour chaque scénario, six nuits avec une panne : anti-robot durable, panne passagère, page changée,
erreur de prix d'un soir (÷ 10, et quelqu'un guette ce produit), SMTP en panne deux nuits (et une mission atteinte),
fichier des partenaires mal rempli (une enseigne déclarée sur quatre). On relève : incidents, actions de l'agent par
politique, e-mails au responsable (nuit par nuit), requêtes vers le site qui bloque, part des fiches relues, prix faux
publiés, e-mails trompeurs, offres publiées.

  python -m bench.autonomy
"""
import shutil
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from deals import config, demo, night
from deals.errors import Unavailable
from deals.store import Store

START, WARM, NIGHTS = date(2025, 10, 1), 50, 6
D = START + timedelta(days=WARM)
OPERATOR = "ops@exemple.test"


class Faulty:
    """Le marché simulé, avec la panne du scénario (par hôte ou par adresse, sur des jours donnés)."""

    def __init__(self, base, clock):
        self.base, self.clock, self.plan, self.hits = base, clock, [], Counter()

    def get(self, url, etag=None, last_modified=None):
        host, day = url.split("/")[2], datetime.fromtimestamp(self.clock(), timezone.utc).date()
        self.hits[host, day] += 1
        for f in self.plan:
            if not f["start"] <= day <= f["end"] or f.get("host") not in (None, host) or f.get("url") not in (None, url):
                continue
            if f["kind"] == "blocked":
                return {"status": "blocked", "code": 403, "protection": "datadome", "html": "", "final_url": url}
            if f["kind"] == "error" and f.setdefault("served", Counter())[day] < f["first"]:
                f["served"][day] += 1
                return {"status": "error", "code": 503, "html": "", "final_url": url}
            r = self.base.get(url)
            if f["kind"] == "layout":
                return {**r, "html": "<html><head><title>Nouvelle page</title></head><body><div class='prix'></div></body></html>"}
            if f["kind"] == "price_error":
                html = r["html"]
                a = html.index('"price": "') + len('"price": "')
                b = html.index('"', a)
                return {**r, "html": html[:a] + f"{float(html[a:b]) / 10:.2f}" + html[b:]}
            return r
        return self.base.get(url)

    def delay_for(self, host):
        return 0.0


class Box:
    def __init__(self, clock):
        self.clock, self.mails, self.down = clock, [], set()

    def send(self, to, link, about=None):
        pass

    def send_mail(self, to, message):
        day = datetime.fromtimestamp(self.clock(), timezone.utc).date()
        if day in self.down:
            raise Unavailable("SMTP indisponible")
        self.mails.append((day, to, message["Subject"]))


def mission(store, email, product_id, max_price):
    uid = store.x("INSERT INTO users(email, created_at) VALUES (?, 0)", (email,))
    store.x("INSERT INTO missions(user_id, product_id, want, max_price, label, created_at, notified) VALUES (?,?,'{}',?,?,0,'{}')",
            (uid, product_id, max_price, "Ce produit"))


def blocked(s, f, box, ctx):
    f.plan.append({"kind": "blocked", "host": "rapido.sim", "start": D, "end": D + timedelta(days=NIGHTS)})
    ctx["host"] = "rapido.sim"


def transient(s, f, box, ctx):
    f.plan.append({"kind": "error", "host": "electroplus.sim", "start": D, "end": D, "first": 5})
    ctx["host"], ctx["read"] = "electroplus.sim", "electroplus"


def layout(s, f, box, ctx):
    f.plan.append({"kind": "layout", "host": "maisonco.sim", "start": D, "end": D + timedelta(days=NIGHTS)})
    ctx["host"] = "maisonco.sim"


def price_error(s, f, box, ctx):
    o = s.q("SELECT o.url, o.product_id, c.price FROM offers o JOIN catalog c ON c.product_id=o.product_id "
            "WHERE o.retailer='grandbazar' ORDER BY c.price DESC LIMIT 1", one=True)
    f.plan.append({"kind": "price_error", "url": o["url"], "start": D, "end": D})
    mission(s, "lea@exemple.test", o["product_id"], round(o["price"] * 0.7))
    ctx["product"], ctx["normal"] = o["product_id"], o["price"]


def smtp(s, f, box, ctx):
    box.down = {D, D + timedelta(days=1)}
    p = s.q("SELECT product_id, price FROM catalog ORDER BY title LIMIT 1", one=True)
    mission(s, "noa@exemple.test", p["product_id"], round(p["price"] * 1.3))


def partners(s, f, box, ctx):
    ctx["partners"] = {"rapido"}


SCENARIOS = [("anti-robot durable", blocked), ("panne passagère", transient), ("page changée", layout),
             ("erreur de prix", price_error), ("SMTP en panne", smtp), ("partenaires mal configurés", partners)]


def warm(path):
    s = Store(path)
    demo.build(s, end=D - timedelta(days=1), nights=WARM - 1, partners=set(demo.RULES))
    s.close()


def scenario(base, name, setup):
    path = Path(tempfile.mkdtemp(), "s.sqlite")
    shutil.copy(base, path)
    s = Store(path)
    w = demo.world(s, START)
    f = w.crawler.f = Faulty(w.crawler.f, w.clock)
    box, ctx = Box(w.clock), {"partners": set(demo.RULES)}
    settings = config.load({}, public_url="https://deals.test", operator_email=OPERATOR)
    setup(s, f, box, ctx)
    out = []
    for k in range(NIGHTS):
        day = D + timedelta(days=k)
        w.clock.set(day)
        r = night.run(s, settings, w.crawler, box, w.retailers, ctx["partners"], clock=w.clock)
        start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp()
        row = {"day": day, "offers": s.q("SELECT COUNT(*) n FROM catalog_offers", one=True)["n"], "held": bool((r["publish"] or {}).get("held"))}
        if ctx.get("host"):
            row["hits"] = f.hits[ctx["host"], day]
        if ctx.get("read"):
            n = s.q("SELECT COUNT(*) n, SUM((SELECT MAX(last_seen) FROM prices p WHERE p.offer_id=o.id) >= ?) f FROM offers o "
                    "WHERE retailer=? AND status='active'", (start, ctx["read"]), one=True)
            row["read"] = round((n["f"] or 0) / n["n"], 2)
        if ctx.get("product"):
            c = s.q("SELECT price FROM catalog_offers WHERE product_id=? ORDER BY rank LIMIT 1", (ctx["product"],), one=True)
            row["wrong_price"] = bool(c and c["price"] < 0.3 * ctx["normal"])
        out.append(row)
    res = {"name": name, "nights": out,
           "incidents": s.q("SELECT kind, entity, severity, status, nights FROM incidents ORDER BY id"),
           "actions": Counter(a["policy"] for a in s.q("SELECT policy FROM actions")),
           "operator": [d.isoformat() for d, to, _ in box.mails if to == OPERATOR],
           "users": [(d.isoformat(), to) for d, to, _ in box.mails if to != OPERATOR]}
    s.close()
    return res


def show(r):
    n = r["nights"]
    acts = " · ".join(f"{k} {v}" for k, v in sorted(r["actions"].items())) or "aucune"
    incidents = ", ".join(f"{i['kind']} ({i['severity']}, {i['status']}, {i['nights']} nuit(s))" for i in r["incidents"])
    print(f"\n{r['name']}")
    print(f"  incidents : {incidents or 'aucun'}")
    print(f"  actions de l'agent : {acts}")
    print(f"  e-mails au responsable : {len(r['operator'])} ({', '.join(r['operator']) or '—'})")
    print(f"  e-mails aux personnes : {len(r['users'])} ({', '.join(d for d, _ in r['users']) or '—'})")
    print(f"  offres publiées par nuit : {[x['offers'] for x in n]} · publication retenue : {sum(x['held'] for x in n)} nuit(s)")
    if "hits" in n[0]:
        print(f"  requêtes vers le site en panne, par nuit : {[x['hits'] for x in n]}")
    if "read" in n[0]:
        print(f"  part des fiches relues, par nuit : {[x['read'] for x in n]}")
    if "wrong_price" in n[0]:
        print(f"  nuits avec le prix faux publié : {sum(x['wrong_price'] for x in n)}")


def main():
    base = Path(tempfile.mkdtemp(), "warm.sqlite")
    warm(base)
    for name, setup in SCENARIOS:
        show(scenario(base, name, setup))


if __name__ == "__main__":
    main()
