"""Autonomie : la nuit se débrouille seule quand c'est sans risque, s'arrête et demande quand ça ne l'est pas, et laisse
une trace de tout. Pannes injectées dans le vrai marché simulé de la démo (une source par enseigne : son flux) : flux
injoignable, panne passagère, prix barré disparu du flux, erreur de prix, SMTP en panne, catalogue qui fond, envoi massif,
étape qui casse."""
import io
import json
import os
import re
import sqlite3
import tempfile
import unittest
from collections import Counter
from contextlib import closing, redirect_stdout
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from deals import cli, config, demo, health, night, quarantine, sim, sources
from deals.agent import POLICY, Agent, Tools, urgent
from deals.api import Api, Request
from deals.ingest.report import summarize
from deals.errors import Unavailable
from deals.ops import Ops, scrub
from deals.store import Store

START, WARM_END = date(2025, 10, 1), date(2025, 10, 21)
D = WARM_END + timedelta(days=1)                 # première nuit de chaque scénario
OPERATOR = "ops@exemple.test"
WARM = None

SHOWN = len(sim.SHOWCASE) + len(sim.SHOWCASE_MORE) + len(sim.SHOWCASE_TECH)   # la vitrine de la démo : 127 produits, trois enseignes chacun


def setUpModule():
    """Une base chauffée une fois (21 nuits : assez pour les prix habituels), copiée pour chaque scénario."""
    global WARM
    WARM = Path(tempfile.mkdtemp(), "warm.sqlite")
    s = Store(WARM)
    demo.build(s, end=WARM_END, nights=(WARM_END - START).days, partners=set(demo.RULES))
    s.close()


def clone(src):
    dst = Path(tempfile.mkdtemp(), "s.sqlite")
    with closing(sqlite3.connect(src)) as a, closing(sqlite3.connect(dst)) as b:
        a.backup(b)
    return dst


class Faults:
    """Les flux du marché simulé, avec des pannes prévues par source : down (flux injoignable : les `first` premières
    lectures du jour, ou toutes), barred (le prix barré disparaît d'un flux XML, les prix ne bougent pas : unbarred),
    price_error (un prix ÷ factor : celui du premier jour de la panne, donné tel quel ensuite, comme
    une erreur de saisie de l'enseigne)."""

    def __init__(self, world):
        self.w, self.base, self.plan, self.hits = world, world.collector.transport, [], Counter()
        world.collector.transport = self

    def add(self, kind, first_day, last_day, source=None, url=None, first=None, factor=10):
        self.plan.append({"kind": kind, "days": (first_day, last_day), "source": source, "first": first, "served": Counter()})
        if kind == "price_error":                            # dans le marché simulé : le flux du jour le donne
            m = self.w.sim
            o = next(x for x in m.offers if x["url"] == url)
            k0, k1 = (first_day - m.start).days, (last_day - m.start).days
            wrong = round(o["price"][k0] / factor, 2)
            for k in range(k0, min(k1 + 1, len(o["price"]))):
                o["price"][k] = wrong

    def __call__(self, spec):
        key, day = spec["key"], datetime.fromtimestamp(self.w.clock(), timezone.utc).date()
        self.hits[key, day] += 1
        for f in self.plan:
            if f["source"] != key or not f["days"][0] <= day <= f["days"][1]:
                continue
            if f["kind"] == "down" and (f["first"] is None or f["served"][day] < f["first"]):
                f["served"][day] += 1
                raise OSError("503 Service Unavailable")
            if f["kind"] == "barred":
                return unbarred(self.base(spec))
        return self.base(spec)


def unbarred(xml):
    """Un flux Google Shopping où le réseau ne donne plus que le prix réduit, comme seul prix : plus de prix barré, et le
    prix, lui, ne bouge pas (la correspondance du flux a changé, pas les prix de l'enseigne)."""
    def one(m):
        item, sale = m.group(0), re.search(rb"<g:sale_price>([^<]*)</g:sale_price>", m.group(0))
        if not sale:
            return item
        item = re.sub(rb"<g:price>[^<]*</g:price>", b"<g:price>" + sale.group(1) + b"</g:price>", item.replace(sale.group(0), b""))
        return re.sub(rb"<g:sale_price_effective_date>[^<]*</g:sale_price_effective_date>", b"", item)
    return re.sub(rb"<item>.*?</item>", one, xml, flags=re.S)


class Box:
    """Boîte d'envoi : garde les e-mails ; SMTP en panne les jours de `down`."""

    def __init__(self, clock):
        self.clock, self.mails, self.down = clock, [], set()

    def send(self, to, link, about=None):
        self.mails.append((to, link))

    def send_mail(self, to, message):
        if datetime.fromtimestamp(self.clock(), timezone.utc).date() in self.down:
            raise Unavailable("SMTP indisponible")
        self.mails.append((to, message))

    def to(self, who):
        return [m for t, m in self.mails if t == who]


class Scenario(unittest.TestCase):
    def setUp(self):
        self.path = clone(WARM)
        self.s = Store(self.path)
        self.w = demo.world(self.s, START)
        self.faults = Faults(self.w)
        self.box = Box(self.w.clock)
        self.settings = config.load({}, public_url="https://deals.test", operator_email=OPERATOR)
        self.k = 0

    def tearDown(self):
        self.s.close()

    def nights(self, n, partners=None, report_dir=None):
        out = []
        for _ in range(n):
            self.w.clock.set(D + timedelta(days=self.k))
            self.k += 1
            out.append(night.run(self.s, self.settings, self.w.collector, self.box, self.w.retailers,
                                 partners or set(demo.RULES), clock=self.w.clock, report_dir=report_dir))
        return out

    def day(self, k):
        return D + timedelta(days=k)

    def actions(self, action=None):
        return self.s.q("SELECT * FROM actions" + (" WHERE action=?" if action else "") + " ORDER BY id", (action,) if action else ())

    def incident(self, kind):
        return self.s.q("SELECT * FROM incidents WHERE kind=? ORDER BY id DESC", (kind,), one=True)

    def mission(self, email, product_id, max_price):
        """Une recherche sauvegardée sous max_price que ce produit remplit : son rayon, sa marque, les mots de son nom (v65 :
        plus d'alerte sur un produit ; la nuit et ses e-mails ne changent pas). Jamais envoyée : tout y est nouveau."""
        r = self.s.q("SELECT category, brand, name FROM catalog WHERE product_id=?", (product_id,), one=True)
        want = {"features": [], "attrs": {}, "words": [w for w in r["name"].lower().split() if w.isalpha()][:3]}
        uid = self.s.x("INSERT INTO users(email, created_at) VALUES (?, 0)", (email,))
        self.s.x("INSERT INTO missions(user_id, category, brand, want, max_price, label, created_at, notified) VALUES (?,?,?,?,?,?,0,'{}')",
                 (uid, r["category"], r["brand"], json.dumps(want), max_price, "Ce produit"))


class Guests(Scenario):
    def test_a_guest_nobody_can_open_any_more_is_erased_at_night(self):
        self.w.clock.set(D)
        at = self.w.clock()                                                       # l'heure de la nuit qui vient
        for token, expires in (("old", at - 1), ("live", at + 30 * 86400)):        # un an sans geste qui garde · un invité actif
            uid = self.s.x("INSERT INTO users(email, created_at) VALUES (NULL, 0)")
            self.s.x("INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES (?,?,0,?)", (token, uid, expires))
        out = self.nights(1)[0]
        run = self.s.q("SELECT stats FROM runs WHERE cid=? AND status!='retry'", (out["cid"],), one=True)
        self.assertEqual(json.loads(run["stats"])["guests_expired"], 1)
        self.assertEqual([r["token_hash"] for r in self.s.q("SELECT token_hash FROM sessions s JOIN users u ON u.id=s.user_id "
                                                            "WHERE u.email IS NULL ORDER BY token_hash")], ["live"])


class Sources(Scenario):
    def test_a_feed_down_three_nights_is_set_aside_then_probed_every_three_days(self):
        self.faults.add("down", self.day(0), self.day(9), source="rapido")
        self.nights(3)
        inc = self.incident("source_failing")
        self.assertEqual((inc["entity"], inc["severity"], inc["status"], inc["nights"]), ("rapido", "critical", "open", 3))
        self.assertEqual(sources.status(self.s, "rapido"), "disabled")
        self.assertEqual([a["status"] for a in self.actions("retry_source")], ["unverified"] * 3)   # relu une fois chaque nuit
        mails = self.box.to(OPERATOR)                                        # nuit 2 (ça dure), nuit 3 (mise de côté)
        self.assertEqual(len(mails), 2)
        self.assertIn("mise de côté", mails[1].get_content())
        self.assertIn("docs/RUNBOOK.md#source-en-echec", mails[1].get_content())
        self.assertIn("deals.py sources enable rapido", mails[1].get_content())
        self.nights(3)                                                       # nuits 4 à 6 : plus lu, son flux relu à J+3
        self.assertEqual([self.faults.hits["rapido", self.day(k)] for k in range(6)], [2, 2, 2, 0, 0, 1])
        self.assertEqual(len(self.box.to(OPERATOR)), 2)                      # rien de neuf : pas d'e-mail
        self.assertEqual(self.incident("source_failing")["status"], "open")  # mise de côté : reste ouvert
        self.assertEqual(self.s.q("SELECT COUNT(*) n FROM catalog", one=True)["n"], SHOWN)   # rien de perdu, pas de garde

    def test_a_probe_that_reads_again_proposes_to_resume_and_approval_resumes(self):
        self.faults.add("down", self.day(0), self.day(3), source="rapido")
        self.nights(6)                                                       # mise de côté nuit 3, flux relu nuit 6 : lisible
        proposal = self.actions("enable_source")
        self.assertEqual([(a["entity"], a["status"]) for a in proposal], [("rapido", "proposed")])
        self.assertIn("reprendre la source", self.box.to(OPERATOR)[-1].get_content())
        ops = Ops(self.s, clock=self.w.clock)
        agent = Agent(self.s, ops, Tools(self.s, self.w.clock), self.w.clock, "geste-test", actor="lea")
        done = agent.approve(proposal[0]["id"], "lea")
        self.assertEqual((done["status"], done["decided_by"]), ("executed", "lea"))
        self.assertEqual(sources.status(self.s, "rapido"), "active")
        self.nights(1)
        self.assertEqual(self.faults.hits["rapido", self.day(6)], 1)         # relu la nuit suivante, en entier
        last = self.s.q("SELECT status, accepted FROM batches WHERE source='rapido' ORDER BY id DESC LIMIT 1", one=True)
        self.assertEqual(last, {"status": "succeeded", "accepted": len([o for o in self.w.sim.offers if o["merchant"] == "Rapido"])})
        self.assertEqual(self.incident("source_failing")["status"], "resolved")
        self.assertIn("RENTRÉ DANS L'ORDRE", self.box.to(OPERATOR)[-1].get_content())
        with self.assertRaises(ValueError):
            agent.approve(proposal[0]["id"], "lea")                          # déjà décidé

    def test_resuming_is_proposed_once_and_a_manual_resume_settles_it(self):
        self.faults.add("down", self.day(0), self.day(3), source="rapido")
        self.nights(9)                                                       # flux relu nuits 6 et 9 : lisible
        self.assertEqual(len(self.actions("probe_source")), 2)
        self.assertEqual([a["status"] for a in self.actions("enable_source")], ["proposed"])      # une seule proposition
        agent = Agent(self.s, Ops(self.s, clock=self.w.clock), Tools(self.s, self.w.clock), self.w.clock, actor="lea")
        agent.manual("enable_source", "rapido", "lea", "reprise à la main", lambda: agent.tools.enable_source("rapido"))
        self.assertEqual([a["status"] for a in self.actions("enable_source")], ["expired", "executed"])

    def test_failed_nights_count_in_a_row_and_a_good_night_starts_again(self):
        state = lambda: self.s.q("SELECT failures, status FROM sources WHERE key='rapido'", one=True)
        self.faults.add("down", self.day(0), self.day(1), source="rapido")
        self.nights(2)
        self.assertEqual(state(), {"failures": 2, "status": "degraded"})
        self.nights(1)
        self.assertEqual(state(), {"failures": 0, "status": "active"})
        self.assertEqual(self.incident("source_failing")["status"], "resolved")
        self.faults.add("down", self.day(3), self.day(4), source="rapido")
        self.nights(2)
        self.assertEqual(state(), {"failures": 2, "status": "degraded"})    # deux de suite, pas quatre : pas mise de côté

    def test_a_transient_failure_is_retried_once_and_nobody_is_bothered(self):
        self.faults.add("down", self.day(0), self.day(0), source="electroplus", first=1)
        out = self.nights(1)[0]
        retry = self.actions("retry_source")
        self.assertEqual([(a["entity"], a["status"], a["policy"]) for a in retry], [("electroplus", "verified", "auto")])
        self.assertEqual(json.loads(retry[0]["inputs"])["before"], {"pages": 0, "ok": None, "success": None, "errors": 1,
                                                                    "interrupted": 1})
        self.assertIn("flux en échec (OSError : 503 Service Unavailable)", retry[0]["justification"])
        self.assertEqual(out["collect"]["retailers"]["electroplus"]["success"], 1.0)    # le bilan de la nuit est celui de la relance
        self.assertEqual(out["status"], "succeeded")
        self.assertFalse(self.s.q("SELECT * FROM incidents"))
        self.assertEqual(self.box.to(OPERATOR), [])
        self.assertEqual(self.s.q("SELECT failures FROM sources WHERE key='electroplus'", one=True)["failures"], 0)
        run = self.s.q("SELECT * FROM runs WHERE cid=? AND status!='retry'", (out["cid"],), one=True)
        self.assertEqual(json.loads(run["stats"])["retailers"]["electroplus"]["success"], 1.0)   # la nuit suivante compare à ça
        self.assertEqual(self.s.q("SELECT COUNT(*) n FROM runs WHERE cid=? AND status='retry'", (out["cid"],), one=True)["n"], 1)

    def test_a_retry_that_does_not_help_waits_a_night_before_writing(self):
        self.faults.add("down", self.day(0), self.day(1), source="electroplus")
        self.nights(1)
        self.assertEqual([a["status"] for a in self.actions("retry_source")], ["unverified"])
        self.assertEqual(self.box.to(OPERATOR), [])                         # peut-être passager : on attend une nuit
        self.nights(1)
        self.assertEqual(self.incident("source_failing")["nights"], 2)
        self.assertIn("en échec (erreurs) · 2 nuits", self.box.to(OPERATOR)[0].get_content())

    def test_a_feed_that_stops_giving_barred_prices_asks_to_review_its_mapping_the_first_night(self):
        self.faults.add("barred", self.day(0), self.day(2), source="rapido")
        self.nights(1)
        inc = self.incident("source_layout")
        self.assertEqual((inc["entity"], inc["severity"]), ("rapido", "warning"))
        advice = self.actions("review_rules")[0]
        self.assertEqual(advice["status"], "recommended")
        self.assertEqual(json.loads(advice["inputs"])["commands"][0], "deals.py probe --source rapido")
        mail = self.box.to(OPERATOR)[0].get_content()
        self.assertIn("plus de prix barré : le flux a changé", mail)
        self.assertIn("revoir la correspondance du flux", mail)
        self.assertFalse(self.actions("retry_source"))                       # le flux se lit : rien à relancer
        self.nights(2)                                                       # le flux reste changé : l'incident aussi
        inc = self.incident("source_layout")
        self.assertEqual((inc["status"], inc["nights"]), ("open", 3))
        self.assertNotIn("RENTRÉ DANS L'ORDRE", "".join(m.get_content() for m in self.box.to(OPERATOR)))
        self.nights(1)                                                       # le prix barré revient : résolu
        self.assertEqual(self.incident("source_layout")["status"], "resolved")


class Prices(Scenario):
    """Un prix ÷ 10 dans un flux : une variation énorme attend d'être relue la nuit suivante avant d'être enregistrée
    (market.py) ; relue, elle est mise en quarantaine (quarantine.py) tant qu'elle n'est pas crue."""

    def target(self):
        return self.s.q("SELECT o.id, o.url, o.product_id, c.price FROM offers o JOIN catalog c ON c.product_id=o.product_id "
                        "WHERE o.retailer='grandbazar' ORDER BY c.price DESC LIMIT 1", one=True)

    def wrong(self, o):
        return round(next(x for x in self.w.sim.offers if x["url"] == o["url"])["price"][(self.day(0) - self.w.sim.start).days], 2)

    def test_a_one_night_price_error_is_never_recorded(self):
        o = self.target()
        self.faults.add("price_error", self.day(0), self.day(0), url=o["url"])
        self.mission("lea@exemple.test", o["product_id"], round(o["price"] * 0.7))
        self.nights(1)
        pending = self.s.q("SELECT pending_price FROM offers WHERE id=?", (o["id"],), one=True)["pending_price"]
        self.assertEqual(pending, self.wrong(o))                                                    # en attente d'être relu
        self.assertFalse(self.s.q("SELECT 1 FROM prices WHERE offer_id=? AND price=?", (o["id"], pending)))
        self.assertTrue(self.s.q("SELECT 1 FROM catalog_offers WHERE offer_id=?", (o["id"],)))      # publiée à son vrai prix
        self.assertEqual(self.w.collector.nightly([], retry=True)["offers"], 0)                     # aucune source : rien lu
        self.nights(1)                                                                               # revenue à la normale
        self.assertIsNone(self.s.q("SELECT pending_price FROM offers WHERE id=?", (o["id"],), one=True)["pending_price"])
        self.assertEqual(quarantine.held(self.s), [])
        self.assertEqual(self.box.to("lea@exemple.test"), [])                                        # pas d'e-mail trompeur
        self.assertEqual((self.box.to(OPERATOR), self.actions()), ([], []))                         # rien à faire, sans bruit

    def test_a_price_error_read_twice_reaches_neither_the_app_nor_the_missions(self):
        o = self.target()
        self.faults.add("price_error", self.day(0), self.day(1), url=o["url"])
        self.mission("lea@exemple.test", o["product_id"], round(o["price"] * 0.7))
        reports = Path(tempfile.mkdtemp())
        name = self.nights(2, report_dir=reports)[1]["report"]
        morning = (reports / f"{name}.md").read_text(encoding="utf-8")
        self.assertIn("retenu : prix suspect, en quarantaine", morning)                              # rapport du matin
        self.assertIn("## Agent", morning)
        self.assertIn("prix mis en quarantaine", morning)
        self.assertEqual([q["offer_id"] for q in quarantine.held(self.s)], [o["id"]])
        self.assertFalse(self.s.q("SELECT 1 FROM catalog_offers WHERE offer_id=?", (o["id"],)))      # pas publiée
        self.assertEqual(self.box.to("lea@exemple.test"), [])                                        # pas d'e-mail trompeur
        self.assertEqual(self.box.to(OPERATOR), [])                                                  # réglé seul, sans bruit
        self.nights(2)                                                                               # revenue, et relue
        self.assertEqual(quarantine.held(self.s), [])
        self.assertTrue(self.s.q("SELECT 1 FROM catalog_offers WHERE offer_id=?", (o["id"],)))
        bad = self.s.q("SELECT price FROM prices WHERE offer_id=? AND rejected=1", (o["id"],))
        self.assertEqual(len(bad), 1)
        self.assertLess(bad[0]["price"], 0.3 * o["price"])
        chart = json.loads(self.s.q("SELECT history FROM catalog WHERE product_id=?", (o["product_id"],), one=True)["history"])
        self.assertGreater(min(v for v in chart["p"] if v is not None), 0.3 * o["price"])         # l'erreur n'est pas dans la courbe
        self.assertEqual([a["action"] for a in self.actions()], ["quarantine_offer", "release_offer"])

    def test_a_price_read_again_two_more_nights_is_believed(self):
        o = self.target()
        self.faults.add("price_error", self.day(0), self.day(9), url=o["url"])
        self.nights(3)                                                       # en attente, en quarantaine, relu une fois
        self.assertEqual(len(quarantine.held(self.s)), 1)
        self.nights(1)
        self.assertEqual(quarantine.held(self.s), [])
        self.assertTrue(self.s.q("SELECT 1 FROM catalog_offers WHERE offer_id=?", (o["id"],)))       # cru : publié
        self.assertFalse(self.s.q("SELECT 1 FROM prices WHERE rejected=1"))
        self.nights(1)
        self.assertEqual(quarantine.held(self.s), [])                                                # pas resuspecté
        self.assertEqual([a["action"] for a in self.actions()], ["quarantine_offer", "confirm_offer", "release_offer"])

    def test_another_suspicious_price_starts_the_count_again(self):
        o = self.target()
        self.faults.add("price_error", self.day(0), self.day(1), url=o["url"])
        self.faults.add("price_error", self.day(2), self.day(9), url=o["url"], factor=5)
        self.nights(4)                                                       # ÷ 10 relu, puis ÷ 5 deux nuits : pas encore cru
        self.assertEqual(len(quarantine.held(self.s)), 1)
        self.assertEqual([a["action"] for a in self.actions()], ["quarantine_offer", "quarantine_offer", "confirm_offer"])

    def test_an_operator_can_release_a_price_checked_at_the_retailer(self):
        o = self.target()
        self.faults.add("price_error", self.day(0), self.day(9), url=o["url"])
        self.nights(2)
        agent = Agent(self.s, Ops(self.s, clock=self.w.clock), Tools(self.s, self.w.clock), self.w.clock, actor="noa")
        agent.manual("release_offer", f"offre {o['id']}", "noa", "vérifié chez l'enseigne",
                     lambda: {"rejected": quarantine.release(self.s, o["id"], "libéré par noa", self.w.clock())})
        self.nights(1)
        self.assertEqual(quarantine.held(self.s), [])                                                # pas remis en quarantaine
        self.assertTrue(self.s.q("SELECT 1 FROM catalog_offers WHERE offer_id=?", (o["id"],)))
        self.assertEqual(self.actions("release_offer")[0]["actor"], "noa")


class Mail(Scenario):
    def test_an_smtp_outage_is_retried_and_the_operator_hears_once_it_is_back(self):
        p = self.s.q("SELECT product_id, price FROM catalog ORDER BY title LIMIT 1", one=True)
        self.mission("noa@exemple.test", p["product_id"], round(p["price"] * 1.3))
        self.box.down = {self.day(0), self.day(1)}
        out = self.nights(2)
        self.assertEqual([o["missions"]["failed"] for o in out], [1, 1])
        self.assertEqual(self.incident("mission_mail")["nights"], 2)
        self.assertEqual(self.s.q("SELECT COUNT(*) n FROM events WHERE kind='escalation_failed'", one=True)["n"], 2)
        self.assertEqual(self.box.to(OPERATOR), [])
        self.nights(1)
        self.assertEqual(len(self.box.to("noa@exemple.test")), 1)
        self.assertEqual(self.incident("mission_mail")["status"], "resolved")
        mail = self.box.to(OPERATOR)
        self.assertEqual(len(mail), 1)
        self.assertIn("tout est rentré dans l'ordre", mail[0]["Subject"])
        self.assertIn("e-mails des missions en échec (2 nuits)", mail[0].get_content())
        self.assertNotIn("noa@", mail[0].get_content())                     # jamais l'adresse d'un utilisateur

    def test_a_mail_to_the_operator_that_could_not_leave_goes_the_next_night(self):
        self.box.down = {self.day(0)}
        self.nights(1, partners={"rapido"})                                  # publication retenue : à dire d'emblée
        self.assertEqual(self.box.to(OPERATOR), [])
        self.nights(1, partners={"rapido"})                                  # rien de neuf, mais rien n'était parti
        self.assertEqual(len(self.box.to(OPERATOR)), 1)
        self.assertIn("publication retenue : le nouveau catalogue fondait", self.box.to(OPERATOR)[0].get_content())

    def test_a_mass_mailing_waits_for_a_decision(self):
        p = self.s.q("SELECT product_id, price FROM catalog ORDER BY title LIMIT 1", one=True)
        for k in range(31):                                                  # seuil : max(30, 3 × la médiane des nuits d'avant)
            self.mission(f"u{k}@exemple.test", p["product_id"], round(p["price"] * 1.3))
        out = self.nights(1)[0]
        self.assertEqual(out["missions"]["held"], 31)
        self.assertEqual(len(self.box.mails), 1)                             # le seul e-mail : celui au responsable
        proposal = self.actions("mass_notification")[0]
        self.assertEqual(proposal["status"], "proposed")
        self.assertIn(f"deals.py approve {proposal['id']}", self.box.to(OPERATOR)[0].get_content())
        notify = lambda: night.Missions(self.s, night.Catalog(self.s)).notify(self.box, "https://deals.test", limit=50)
        agent = Agent(self.s, Ops(self.s, clock=self.w.clock), Tools(self.s, self.w.clock, notify=notify), self.w.clock, actor="lea")
        self.assertEqual(json.loads(agent.approve(proposal["id"], "lea")["result"])["emails"], 31)
        self.nights(1)
        self.assertEqual(len([t for t, _ in self.box.mails if t.startswith("u")]), 31)               # pas deux fois
        self.assertEqual(self.incident("mass_mail")["status"], "resolved")


class Catalog(Scenario):
    def test_a_melting_catalog_is_held_and_publishing_anyway_needs_approval(self):
        out = self.nights(1, partners={"rapido"})[0]                         # fichier des partenaires mal rempli
        self.assertEqual({r["key"]: r["partner"] for r in sources.listing(self.s)},
                         {"rapido": 1, "electroplus": 0, "maisonco": 0, "grandbazar": 0})
        held = out["publish"]["held"]
        self.assertEqual((held["before"], held["offers_before"]), (SHOWN, 3 * SHOWN))
        self.assertLess(held["offers_after"], 0.8 * 3 * SHOWN)
        self.assertEqual(self.s.q("SELECT COUNT(*) n FROM catalog_offers", one=True)["n"], 3 * SHOWN)    # celui de la veille reste
        self.assertEqual(self.incident("catalog_held")["severity"], "critical")
        proposal = self.actions("force_publication")[0]
        self.assertEqual(proposal["status"], "proposed")
        self.assertIn("1 décision à prendre", self.box.to(OPERATOR)[0]["Subject"])
        tools = Tools(self.s, self.w.clock, publish=lambda guard=False: night.publish(self.s, self.w.market.today(), self.w.clock(),
                                                                                       {"rapido"}, guard=guard))
        Agent(self.s, Ops(self.s, clock=self.w.clock), tools, self.w.clock, actor="lea").approve(proposal["id"], "lea")
        self.assertEqual(self.s.q("SELECT COUNT(*) n FROM catalog_offers", one=True)["n"], held["offers_after"])

    def test_the_guard_lets_go_after_two_nights_and_says_so(self):
        out = self.nights(3, partners={"rapido"})
        self.assertEqual([bool(o["publish"].get("held")) for o in out], [True, True, False])
        self.assertTrue(out[2]["publish"]["unguarded"])
        self.assertEqual(self.actions("release_publication")[0]["status"], "verified")
        self.assertEqual(self.actions("force_publication")[0]["status"], "expired")                # la décision n'a plus lieu d'être
        self.assertEqual(self.incident("catalog_held")["status"], "resolved")
        self.assertEqual((self.incident("catalog_small")["status"], self.incident("catalog_small")["severity"]), ("open", "critical"))
        self.assertIn("publication relâchée", self.box.to(OPERATOR)[-1].get_content())

    def test_without_a_publication_date_the_guard_cannot_hold_forever(self):
        self.s.x("DELETE FROM meta WHERE key='published_at'")               # base d'avant la date de publication
        out = self.nights(1, partners={"rapido"})[0]
        self.assertFalse(out["publish"].get("held"))
        self.assertTrue(out["publish"]["unguarded"])

    def test_a_broken_step_becomes_a_critical_incident_and_the_night_goes_on(self):
        p = self.s.q("SELECT product_id, price FROM catalog ORDER BY title LIMIT 1", one=True)
        self.mission("noa@exemple.test", p["product_id"], round(p["price"] * 1.3))
        with mock.patch("deals.night.publish", side_effect=OSError("disque plein")):
            out = self.nights(1)[0]
        self.assertEqual(out["status"], "failed")
        self.assertEqual(out["errors"][0][0], "publication")
        self.assertEqual(out["missions"]["emails"], 1)                       # la suite a tourné
        inc = self.incident("night_error")
        self.assertEqual((inc["entity"], inc["severity"]), ("publication", "critical"))
        self.assertIn("étape de la nuit en erreur", self.box.to(OPERATOR)[0].get_content())
        api = Api(self.s, self.settings, clock=self.w.clock)
        self.assertEqual(api.handle(Request("GET", "/api/r/health")).status, 503)
        with mock.patch("deals.night.health.snapshot", side_effect=RuntimeError("base verrouillée")):
            self.nights(1)                                                   # même sans contrôles, l'erreur est un incident
        self.assertEqual(self.s.q("SELECT entity FROM incidents WHERE kind='night_error' AND status='open'"), [{"entity": "contrôles"}])
        with mock.patch("deals.ingest.collector.summarize", side_effect=RuntimeError("bilan impossible")):
            out = self.nights(1)[0]                                          # la passe casse après avoir ouvert sa ligne
        run = self.s.q("SELECT status, ended FROM runs WHERE cid=?", (out["cid"],), one=True)
        self.assertEqual(run["status"], "failed")                            # jamais « en cours » pour toujours
        self.assertIsNotNone(run["ended"])


class Audit(Scenario):
    def test_every_action_is_audited_idempotent_and_correlated(self):
        self.faults.add("down", self.day(0), self.day(9), source="rapido")
        out = self.nights(3)
        for a in self.actions():
            self.assertTrue(a["justification"] and a["idempotency_key"] and a["cid"] and a["policy"] == POLICY[a["action"]])
        disable = self.actions("disable_source")[0]
        self.assertEqual(disable["cid"], out[2]["cid"])
        self.assertTrue(disable["rollback_plan"] and disable["expected_effect"] and disable["verification"])
        events = Ops(self.s).recent(out[2]["cid"], 500)
        self.assertEqual(events[0]["kind"], "started")
        self.assertEqual(events[-1]["kind"], "finished")
        self.assertIn("disable_source", [e["kind"] for e in events])
        agent = Agent(self.s, Ops(self.s, clock=self.w.clock), Tools(self.s, self.w.clock), self.w.clock, "geste-test")
        ran = []
        self.assertEqual(agent.act("disable_source", "rapido", "encore", run=lambda: ran.append(1))["id"], disable["id"])
        with mock.patch.dict(POLICY, {"essai_interdit": "forbidden"}):      # aucune action interdite aujourd'hui : le garde-fou reste
            refused = agent.act("essai_interdit", "rapido", "essai", run=lambda: ran.append(1), key="essai")
        self.assertEqual((refused["status"], ran), ("refused", []))          # interdit : jamais exécuté

    def test_logs_carry_no_address_nor_secret(self):
        self.assertEqual(scrub({"to": "lea@exemple.test", "smtp_password": "x", "token": "y", "n": [1, "a b@c.fr"]}),
                         {"to": "[adresse masquée]", "n": [1, "a [adresse masquée]"]})
        stream = io.StringIO()
        ops = Ops(self.s, "prod", stream, clock=lambda: 0)
        ops.event("warning", "agent", "essai", "rapido", "nuit-x", detail="écrire à lea@exemple.test", severity="faux")
        line = json.loads(stream.getvalue())
        self.assertEqual((line["severity"], line["env"], line["correlation_id"], line["ts"]), ("warning", "prod", "nuit-x",
                                                                                                "1970-01-01T00:00:00Z"))
        self.assertNotIn("lea@", stream.getvalue())
        self.nights(1)
        self.assertNotIn(OPERATOR, json.dumps(self.s.q("SELECT payload FROM events")))


class Health(unittest.TestCase):
    def test_findings_follow_written_thresholds(self):
        snap = {"sources": {"a": {"kind": "feed", "pages": 0, "interrupted": 1, "errors": 1, "broken": True, "failures": 1,
                                  "status": "degraded"},                     # injoignable
                            "b": {"kind": "feed", "pages": 10, "accepted": 0, "broken": True, "failures": 3, "status": "degraded"},
                            "c": {"kind": "feed", "pages": 10, "accepted": 10, "was_drop": True, "failures": 0, "status": "active"},
                            "d": {"kind": "feed", "pages": 10, "accepted": 10, "failures": 0, "status": "active"},
                            "e": {"pages": 0, "status": "disabled", "failures": 3}},
                "quarantine": {"c": 5}, "publish": {}, "missions": {"failed": 2, "deferred": 1}, "errors": [],
                "catalog": {"products": 50, "offers": {"a": 10}, "reference": {"a": 40, "e": 100}},
                "freshness": {"products": 100, "fresh": 80}, "clicks": {"last_day": 5, "median_7d": 30}}
        got = {(f["kind"], f["entity"], f["severity"]) for f in health.findings(snap)}
        self.assertEqual(got, {("source_failing", "a", "warning"), ("source_failing", "b", "critical"),
                               ("source_layout", "c", "warning"), ("suspect_prices", "c", "warning"),
                               ("catalog_small", "", "critical"),            # 10 offres pour 40 ; la source mise de côté ne compte pas
                               ("freshness", "", "warning"), ("mission_mail", "", "warning"), ("mail_quota", "", "info"),
                               ("clicks_drop", "", "warning")})

    def test_a_source_set_aside_explains_a_smaller_catalog_and_a_lost_barred_price_is_a_feed_change(self):
        snap = {"sources": {"a": {"pages": 10, "success": 1.0, "status": "active", "was_drop": True}, "e": {"status": "disabled"}},
                "catalog": {"products": 50, "offers": {"a": 35}, "reference": {"a": 40, "e": 100}},
                "freshness": {"products": 0, "fresh": 0}, "clicks": {"last_day": 0, "median_7d": 0}}
        self.assertEqual([(f["kind"], f["severity"]) for f in health.findings(snap)], [("source_layout", "warning")])

    def test_staleness_already_explained_by_a_failing_source_is_only_noted(self):
        snap = lambda stale: {"sources": {"a": {"pages": 0, "status": "degraded", "failures": 1}, "b": {"pages": 0, "status": "active"}},
                              "freshness": {"products": 100, "fresh": 60, "stale_by_source": stale},
                              "clicks": {"last_day": 0, "median_7d": 0}}
        explained = health.findings(snap({"a": 40}))[0]
        self.assertEqual((explained["severity"], explained["evidence"]["explained_by"]), ("info", ["a"]))
        self.assertEqual(health.findings(snap({"a": 30, "b": 10}))[0]["severity"], "critical")    # b n'a rien signalé

    def test_every_incident_has_its_runbook_entry(self):
        doc = (Path(__file__).resolve().parent.parent / "docs" / "RUNBOOK.md").read_text(encoding="utf-8")
        for anchor in [*health.RUNBOOK.values(), "nuit-absente", "sonde"]:
            self.assertIn(f'<a id="{anchor}"></a>', doc)

    def test_who_gets_an_email(self):
        inc = lambda kind, severity, nights=1: {"kind": kind, "severity": severity, "nights": nights}
        self.assertTrue(urgent(inc("freshness", "critical")))
        self.assertTrue(urgent(inc("source_layout", "warning")))             # ne passera pas tout seul
        self.assertFalse(urgent(inc("source_failing", "warning")))           # peut-être passager : on attend une nuit
        self.assertTrue(urgent(inc("source_failing", "warning", 2)))
        self.assertFalse(urgent(inc("mail_quota", "info", 5)))

    def test_a_barred_price_lost_at_the_same_price_is_a_feed_change_not_a_promo_ending(self):
        def run(after):
            market = mock.Mock()
            market.s.q.return_value = {"n": 0}
            market.last_prices.return_value = [{"price": after, "was": None, "first_seen": 2}, {"price": 100, "was": 130, "first_seen": 1}]
            res = [{"offer_id": k, "retailer": "x", "status": "ok", "outcome": "changed", "was": None} for k in range(12)]
            return summarize(market, date(2025, 10, 2), res, {"x": "X"}, previous={"x": {"was_rate": 0.6}})["retailers"]["x"]["was_drop"]
        self.assertTrue(run(100))                                            # même prix, plus de prix barré : le flux a changé
        self.assertFalse(run(130))                                           # le prix remonte : la promotion est finie

    def test_a_barred_price_drop_lasts_until_the_barred_price_comes_back(self):
        market = mock.Mock()
        market.s.q.return_value = {"n": 0}
        night = lambda was: summarize(market, date(2025, 10, 3), [{"offer_id": k, "retailer": "x", "status": "ok", "outcome": "unchanged",
                                                                   "was": was} for k in range(12)],
                                      {"x": "X"}, previous={"x": {"was_rate": 0.0, "was_ref": 0.6}})["retailers"]["x"]
        self.assertEqual((night(None)["was_drop"], night(None)["was_ref"]), (True, 0.6))   # rien de perdu ce soir : la chute dure
        self.assertNotIn("was_ref", night(130))                              # le prix barré revient : fini


class Units(unittest.TestCase):
    def setUp(self):
        self.s = Store(Path(tempfile.mkdtemp(), "u.sqlite"))
        self.now = [datetime(2025, 10, 1, 10, tzinfo=timezone.utc).timestamp()]
        self.clock = lambda: self.now[0]

    def tearDown(self):
        self.s.close()

    def nights(self, kind, severities):
        box, sent = Box(self.clock), []
        for severity in severities:
            agent = Agent(self.s, Ops(self.s, clock=self.clock), Tools(self.s, self.clock), self.clock, operator=OPERATOR)
            agent.after_night([health.finding(kind, "x", severity, pages=10)])
            sent.append(bool(agent.escalate(box, "deals@localhost")))
            self.now[0] += 86400
        return sent

    def test_an_incident_is_written_when_it_matters_again_when_it_worsens_never_twice(self):
        self.assertEqual(self.nights("source_failing", ["warning", "warning", "warning"]), [False, True, False])   # passager ?
        self.assertEqual(self.nights("source_layout", ["warning", "critical", "critical"]), [True, True, False])   # pire : réécrit

    def test_the_morning_mail_lists_what_was_done_without_drowning_it(self):
        from deals.agent import DIGEST_DONE, digest
        agent = Agent(self.s, Ops(self.s, clock=self.clock), Tools(self.s, self.clock), self.clock, "nuit-x")
        for k in range(DIGEST_DONE + 3):
            agent.act("confirm_offer" if k == 0 else "quarantine_offer", f"offre {k}", f"prix {k}", run=lambda: None)
        text = digest(self.s, "2025-10-01", "deals@localhost", OPERATOR).get_content()
        self.assertNotIn("offre 0 ·", text)                                  # « relu une nuit de plus » : pas la peine
        self.assertEqual(text.count("· prix mis en quarantaine —"), DIGEST_DONE)
        self.assertIn("… et 2 autres : deals.py actions", text)

    def test_the_next_night_compares_with_the_night_not_with_a_retry(self):
        from deals.ingest.report import previous_retailers
        self.s.x("INSERT INTO runs(day, started, stats, status) VALUES ('2025-10-01', 1, ?, 'partial_success')",
                 (json.dumps({"retailers": {"a": {"was_rate": 0.5}, "b": {"was_rate": 0.4}}}),))
        self.s.x("INSERT INTO runs(day, started, stats, status) VALUES ('2025-10-01', 2, ?, 'retry')",
                 (json.dumps({"retailers": {"b": {"was_rate": 0.4}}}),))
        self.assertEqual(set(previous_retailers(self.s, date(2025, 10, 2))), {"a", "b"})

    def test_a_failed_night_makes_the_probe_critical(self):
        self.assertIn("état en attente de la première nuit", cli.status_lines(self.s, self.now[0])[0])
        self.s.x("INSERT INTO runs(day, started, ended, status) VALUES ('2025-10-01', ?, ?, 'failed')", (self.now[0], self.now[0]))
        api = Api(self.s, config.load({}, public_url="https://deals.test"), clock=self.clock)
        self.assertEqual(api.handle(Request("GET", "/api/r/health")).body["status"], "critical")
        self.assertIn("état critique", cli.status_lines(self.s, self.now[0])[0])              # le centre de commande aussi


class Command(Scenario):
    def cli(self, *argv, **env):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"DEALS_OPERATOR_EMAIL": OPERATOR, **env}), redirect_stdout(out):
            cli.main(["--db", str(self.path), *argv])
        return out.getvalue()

    def test_status_sources_and_gestures_from_the_command_line(self):
        self.faults.add("down", self.day(0), self.day(9), source="rapido")
        self.nights(3)
        self.s.close()
        status = self.cli("status")
        self.assertIn("Promo Central · état critique", status)
        self.assertIn("Rapido mise de côté (agent : 3 nuits ratées (erreurs))", status)
        self.assertIn("CRITIQUE · Rapido · en échec (erreurs) · 3 nuits · mise de côté", status)
        listing = self.cli("sources", "enable", "rapido", "--reason", "flux rétabli par le réseau", SUDO_USER="lea")
        self.assertRegex(listing, r"rapido +Rapido +feed +active")
        self.s = Store(self.path)
        self.assertEqual(sources.status(self.s, "rapido"), "active")
        gesture = self.actions("enable_source")[-1]
        self.assertEqual((gesture["actor"], gesture["status"], gesture["decided_by"]), ("lea", "executed", "lea"))
        self.assertIn("reprise à la main : flux rétabli par le réseau", gesture["justification"])
        self.s.close()
        self.assertIn("enable_source", self.cli("events", "--n", "5"))
        self.assertIn("[", self.cli("actions", "--n", "3"))
        with self.assertRaises(SystemExit) as stop:
            self.cli("approve", "999")
        self.assertIn("aucune décision en attente", str(stop.exception))
        with self.assertRaises(SystemExit):
            self.cli("sources", "disable", "inconnue")
        self.s = Store(self.path)

    def test_health_route_for_an_outside_probe(self):
        api = lambda now: Api(self.s, self.settings, clock=lambda: now)
        fresh = Store(Path(tempfile.mkdtemp(), "vide.sqlite"))
        self.assertEqual(Api(fresh, self.settings).handle(Request("GET", "/api/r/health")).status, 503)   # aucune nuit
        fresh.close()
        self.nights(1)
        now = self.w.clock()
        r = api(now).handle(Request("GET", "/api/r/health"))
        self.assertEqual((r.status, r.body["status"], r.body["catalog"]), (200, "ok", SHOWN))
        self.assertEqual(set(r.body), {"status", "last_night", "catalog"})                       # rien de plus
        self.assertEqual(api(now + 37 * 3600).handle(Request("GET", "/api/r/health")).status, 503)   # la nuit n'a pas tourné


if __name__ == "__main__":
    unittest.main()
