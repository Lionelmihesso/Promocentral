"""Pannes injectées, nuit après nuit : ce que la plateforme voit, dit, fait seule, et ce qu'elle laisse passer.

Le marché simulé de la démo (127 produits, quatre enseignes, une source chacune : son flux), chauffé 50 nuits par la
vraie nuit (night.run), puis, pour chaque scénario, six nuits avec une panne : flux injoignable durable, panne passagère,
flux changé (plus de prix barré), erreur de prix d'un soir (÷ 10, et quelqu'un guette ce produit), SMTP en panne deux
nuits (et une mission atteinte), fichier des partenaires mal rempli (une enseigne déclarée sur quatre). On relève :
incidents, actions de l'agent par politique, e-mails au responsable (nuit par nuit), lectures du flux en panne, part des
offres relues, prix faux publiés, e-mails trompeurs, offres publiées.

  python -m bench.autonomy
"""
import json
import re
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
    """Les flux du marché simulé, avec la panne du scénario (par source, sur des jours donnés) : down (injoignable : les
    `first` premières lectures du jour, ou toutes), barred (plus de prix barré, prix inchangés), price_error (÷ 10, écrit
    dans le marché simulé : le flux du jour le donne)."""

    def __init__(self, world):
        self.w, self.base, self.plan, self.hits = world, world.collector.transport, [], Counter()
        world.collector.transport = self

    def add(self, f):
        self.plan.append(f)
        if f["kind"] == "price_error":
            m = self.w.sim
            o = next(x for x in m.offers if x["url"] == f["url"])
            for k in range((f["start"] - m.start).days, (f["end"] - m.start).days + 1):
                o["price"][k] = round(o["price"][k] / 10, 2)

    def __call__(self, spec):
        key, day = spec["key"], datetime.fromtimestamp(self.w.clock(), timezone.utc).date()
        self.hits[key, day] += 1
        for f in self.plan:
            if not f["start"] <= day <= f["end"] or f.get("source") != key:
                continue
            served = f.setdefault("served", Counter())
            if f["kind"] == "down" and (f.get("first") is None or served[day] < f["first"]):
                served[day] += 1
                raise OSError("503 Service Unavailable")
            if f["kind"] == "barred":
                return unbarred(self.base(spec))
        return self.base(spec)


def unbarred(xml):
    """Un flux Google Shopping qui ne donne plus que le prix réduit, comme seul prix : plus de prix barré, prix inchangés."""
    def one(m):
        item, sale = m.group(0), re.search(rb"<g:sale_price>([^<]*)</g:sale_price>", m.group(0))
        if not sale:
            return item
        item = re.sub(rb"<g:price>[^<]*</g:price>", b"<g:price>" + sale.group(1) + b"</g:price>", item.replace(sale.group(0), b""))
        return re.sub(rb"<g:sale_price_effective_date>[^<]*</g:sale_price_effective_date>", b"", item)
    return re.sub(rb"<item>.*?</item>", one, xml, flags=re.S)


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
    """Une recherche sauvegardée sous max_price que ce produit remplit : son rayon, sa marque, les mots de son nom (v65 :
    plus d'alerte sur un produit, une alerte d'avant reste inerte)."""
    r = store.q("SELECT category, brand, name FROM catalog WHERE product_id=?", (product_id,), one=True)
    want = {"features": [], "attrs": {}, "words": [w for w in r["name"].lower().split() if w.isalpha()][:3]}
    uid = store.x("INSERT INTO users(email, created_at) VALUES (?, 0)", (email,))
    store.x("INSERT INTO missions(user_id, category, brand, want, max_price, label, created_at, notified) VALUES (?,?,?,?,?,?,0,'{}')",
            (uid, r["category"], r["brand"], json.dumps(want), max_price, "Ce produit"))


def down(s, f, box, ctx):
    f.add({"kind": "down", "source": "rapido", "start": D, "end": D + timedelta(days=NIGHTS)})
    ctx["source"] = "rapido"


def transient(s, f, box, ctx):
    f.add({"kind": "down", "source": "electroplus", "start": D, "end": D, "first": 1})
    ctx["source"], ctx["read"] = "electroplus", "electroplus"


def barred(s, f, box, ctx):
    f.add({"kind": "barred", "source": "rapido", "start": D, "end": D + timedelta(days=NIGHTS)})
    ctx["source"] = "rapido"


def price_error(s, f, box, ctx):
    o = s.q("SELECT o.url, o.product_id, c.price FROM offers o JOIN catalog c ON c.product_id=o.product_id "
            "WHERE o.retailer='grandbazar' ORDER BY c.price DESC LIMIT 1", one=True)
    f.add({"kind": "price_error", "url": o["url"], "start": D, "end": D})
    mission(s, "lea@exemple.test", o["product_id"], round(o["price"] * 0.7))
    ctx["product"], ctx["normal"] = o["product_id"], o["price"]


def smtp(s, f, box, ctx):
    box.down = {D, D + timedelta(days=1)}
    p = s.q("SELECT product_id, price FROM catalog ORDER BY title LIMIT 1", one=True)
    mission(s, "noa@exemple.test", p["product_id"], round(p["price"] * 1.3))


def partners(s, f, box, ctx):
    ctx["partners"] = {"rapido"}


SCENARIOS = [("flux injoignable durable", down), ("panne passagère", transient), ("flux changé (plus de prix barré)", barred),
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
    f = Faulty(w)
    box, ctx = Box(w.clock), {"partners": set(demo.RULES)}
    settings = config.load({}, public_url="https://deals.test", operator_email=OPERATOR)
    setup(s, f, box, ctx)
    out = []
    for k in range(NIGHTS):
        day = D + timedelta(days=k)
        w.clock.set(day)
        r = night.run(s, settings, w.collector, box, w.retailers, ctx["partners"], clock=w.clock)
        start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp()
        row = {"day": day, "offers": s.q("SELECT COUNT(*) n FROM catalog_offers", one=True)["n"], "held": bool((r["publish"] or {}).get("held"))}
        if ctx.get("source"):
            row["hits"] = f.hits[ctx["source"], day]
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
        print(f"  lectures du flux en panne, par nuit : {[x['hits'] for x in n]}")
    if "read" in n[0]:
        print(f"  part des offres relues, par nuit : {[x['read'] for x in n]}")
    if "wrong_price" in n[0]:
        print(f"  nuits avec le prix faux publié : {sum(x['wrong_price'] for x in n)}")


def main():
    base = Path(tempfile.mkdtemp(), "warm.sqlite")
    warm(base)
    for name, setup in SCENARIOS:
        show(scenario(base, name, setup))


if __name__ == "__main__":
    main()
