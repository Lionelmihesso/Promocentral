"""De bout en bout, sur de faux sites locaux : découverte → diagnostic → catalogue → nuit → publication → API de l'app.

Ce que le produit promet, vérifié une fois : un vrai deal est visible dès le premier jour ; un accessoire n'entre pas au
catalogue ; un même EAN chez deux enseignes = un produit ; une page inchangée n'est pas retéléchargée ; une fiche devenue
page liste ou montrant un autre produit est retirée sans rien enregistrer ; un site qui refuse est laissé tranquille ;
l'app lit le catalogue publié (classement, filtres, recherche dans tout le catalogue, fiche avec depuis quand et jusqu'à
quand, marque, favoris et leur prix suivi, marques suivies, clic sortant tracé).
"""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import timedelta
from pathlib import Path

from deals import config
from deals.api import Api
from deals.collect import report
from deals.collect.crawl import Crawler
from deals.collect.diagnose import diagnose
from deals.collect.discover import discover
from deals.fetch import Fetcher
from deals.market import Market
from deals.publish import publish
from deals.store import Store
from deals.web import make_server
from tests.sites import CATALOG, EAN, STATE, Sites


class Flow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sites = Sites().__enter__()
        cls.tmp = tempfile.mkdtemp()
        cls.store = Store(Path(cls.tmp, "t.sqlite"))
        cls.market = Market(cls.store)
        cls.crawler = Crawler(cls.market, Fetcher(user_agent="DealsTest/1.0", min_interval=0, timeout=5), cls.sites.retailers)
        cls.settings = config.load({}, public_url="http://127.0.0.1")
        cls.api = Api(cls.store, cls.settings)
        cls.srv = make_server(cls.api, cls.store, cls.settings, port=0)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.sites.__exit__()
        cls.store.close()

    def get(self, path, session=None):
        req = urllib.request.Request(self.base + "/api/r/" + path, headers={"Cookie": f"deals_session={session}"} if session else {})
        opener = urllib.request.build_opener(type("NoRedirect", (urllib.request.HTTPRedirectHandler,), {"redirect_request": lambda *a: None}))
        try:
            with opener.open(req) as r:
                return r.status, json.loads(r.read() or b"null"), r.headers
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read() or b"null"), e.headers

    def post(self, path, body, session):
        req = urllib.request.Request(self.base + "/api/r/" + path, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "Cookie": f"deals_session={session}"})
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    def session(self, email):
        self.api.accounts.request_link(email)
        token = self.api.accounts.outbox.sent[-1][1].split("token=")[1]
        return self.api.accounts.verify(token)[1].split(";")[0].split("=", 1)[1]

    def test_1_discover_diagnose_build(self):
        found = discover(self.crawler.f, self.sites.retailers["a"], per_category=10)
        self.assertEqual(found["total"], 4)                                  # 4 fiches ; page catégorie et panier écartés
        self.assertEqual(set(found["by_category"]), {"lave_linge", "canape", "matelas"})
        verdicts = {}
        for s in ("a", "b", "c"):
            urls = [u for v in discover(self.crawler.f, self.sites.retailers[s], 10)["by_category"].values() for u in v]
            verdicts[s] = diagnose(self.crawler, s, urls)["summary"]
        self.assertEqual((verdicts["a"]["verdict"], verdicts["a"]["with_price"], verdicts["a"]["with_gtin"]), ("garder", 1.0, 1.0))
        self.assertEqual(verdicts["b"]["verdict"], "garder")                 # sans JSON-LD : balises meta et microdonnées
        self.assertEqual((verdicts["c"]["verdict"], verdicts["c"]["protections"]), ("abandonner (bloqué)", {"datadome": 1}))
        for s in ("a", "b"):
            self.crawler.build(s, discover(self.crawler.f, self.sites.retailers[s], 10)["by_category"])
        q = self.store.q
        self.assertEqual(q("SELECT COUNT(*) n FROM offers WHERE product_id IN (SELECT id FROM products WHERE gtin=?)", (EAN["lave_linge"],), one=True)["n"], 2)
        self.assertEqual(q("SELECT COUNT(*) n FROM products", one=True)["n"], 5)       # 7 fiches, 1 accessoire, 1 EAN partagé
        self.assertEqual(q("SELECT status FROM offers WHERE url LIKE '%1004.html'", one=True)["status"], "out_of_scope")
        self.assertEqual({r["gtin"]: r["category"] for r in q("SELECT gtin, category FROM products")}[EAN["lit"]], "lit")

    def test_2_day_one_deals_are_visible(self):
        stats = publish(self.store, self.market.today(), self.market.clock())
        self.assertEqual((stats["products"], stats["deals"]), (5, 2))
        st, today, _ = self.get("today")
        self.assertEqual(st, 200)
        self.assertEqual([(p["name"], p["pct"]) for p in today["products"]],
                         [("Matelas mousse 140x190 Integral 3", 40), ("Lave-linge hublot Série 6 9 kg", 19)])   # prix barré lu dans le bloc HTML / en JSON-LD
        self.assertEqual(sum(c["count"] for c in self.get("categories")[1]), today["total"])
        self.assertEqual([p["kind"] for p in today["products"]], ["Matelas", "Lave-linge"])     # la liste : marque et catégorie
        item = self.get(f"item/{today['products'][1]['id']}")[1]
        self.assertEqual((item["name"], item["specs"]), ("Lave-linge hublot Série 6 9 kg", ["9 kg"]))  # la fiche : la description
        self.assertEqual([(o["merchant"], o["price"], o["best"]) for o in item["offers"]], [("Site A", 649.0, True), ("Site B", 679.0, False)])
        self.assertNotIn("url", item["offers"][0])                          # l'app passe par le clic tracé
        st, _, headers = self.get(f"out/{item['offers'][0]['offer_id']}?from=item")
        self.assertEqual((st, headers["Location"]), (302, self.sites.url("a", "1001")))
        self.get(f"out/{item['offers'][1]['offer_id']}?from=alternative")                 # fiche ouverte depuis « moins cher »
        self.assertEqual([r["source"] for r in self.store.q("SELECT source FROM clicks ORDER BY rowid")], ["item", "alternative"])
        self.assertEqual(self.get("out/999999")[0], 404)
        self.assertEqual(self.get("brand/Bosch")[1]["brand"], "Bosch")
        self.assertEqual(self.get("brand/Inconnue")[0], 404)
        self.assertEqual([p["brand"] for p in self.get("today?q=lave%20linge")[1]["products"]], ["Bosch"])
        self.assertEqual([p["category"] for p in self.get("today?category=matelas")[1]["products"]], ["matelas"])
        found = self.get("search?q=site")[1]["products"]                                # tout le catalogue : remises d'abord
        self.assertEqual([(p["brand"], p["pct"]) for p in found],
                         [("Bultex", 40), ("Bosch", 19), ("Nils", 0), ("Samsung", 0), ("Oslo", 0)])
        self.assertEqual(self.get("search?q=")[1]["products"], [])
        self.assertEqual(item["alternatives"], [])                                       # rien de comparable ici
        self.assertTrue(all(p["since"] == p["published_on"] for p in today["products"]))  # première publication : tout commence

    def test_3_second_night(self):
        tomorrow = self.market.today() + timedelta(days=1)
        CATALOG["a"]["1002"].update(price=999, strike=1299, omnibus="1 199,00 €",        # promo sur le canapé, finit dans 2 jours
                                    until=(tomorrow + timedelta(days=2)).isoformat())
        STATE["listing"].add("1003")                                                   # la fiche matelas renvoie vers une liste
        STATE["other"]["2003"] = {**CATALOG["b"]["2003"], "title": "Réfrigérateur américain Samsung RS68", "gtin": EAN["frigo2"]}
        stats = self.crawler.nightly(["a", "b"])
        a, b = stats["retailers"]["a"], stats["retailers"]["b"]
        self.assertEqual((a["changed"], a["gone"], a["unchanged_304"]), (1, 1, 1))     # canapé changé, matelas retiré, lave-linge 304
        self.assertEqual((b["gone"], b["unchanged_304"]), (1, 2))                       # autre produit à la même adresse
        self.assertEqual(self.store.q("SELECT note FROM offers WHERE url LIKE '%2003.html'", one=True)["note"], "l'adresse montre un autre produit")
        self.assertEqual(self.store.q("SELECT COUNT(*) n FROM prices p JOIN offers o ON o.id=p.offer_id WHERE o.url LIKE '%2003.html'", one=True)["n"], 1)
        name = report.write(stats, Path(self.tmp, "reports"))
        self.assertIn("1 299,00 € → 999,00 €", Path(self.tmp, "reports", f"{name}.md").read_text(encoding="utf-8"))
        publish(self.store, tomorrow, self.market.clock() + 86400)                     # publication du lendemain matin
        names = [p["name"] for p in self.get("today")[1]["products"]]
        self.assertIn("Canapé d'angle convertible", names)                              # la promo du jour apparaît
        self.assertNotIn("Matelas mousse 140x190 Integral 3", names)                    # la fiche retirée disparaît
        canape = next(p for p in self.get("today")[1]["products"] if p["brand"] == "Oslo")
        self.assertEqual((canape["pct"], canape["was"]), (23, 1299.0))                  # « plus bas 30 jours » cohérent : remise confirmée
        self.assertEqual((canape["since"], canape["ends"]), (tomorrow.isoformat(), (tomorrow + timedelta(days=2)).isoformat()))
        lave = next(p for p in self.get("today")[1]["products"] if p["brand"] == "Bosch")
        self.assertEqual(lave["since"], self.market.today().isoformat())                 # en remise depuis la veille

    def test_4_people(self):
        mia, lea = self.session("mia@test.local"), self.session("lea@test.local")
        today = self.get("today", mia)[1]
        self.assertTrue(today["signed_in"])
        last = today["products"][-1]
        self.post("brand/follow", {"brand": last["brand"]}, mia)
        after = self.get("today", mia)[1]["products"]
        self.assertEqual(after[0]["brand"], last["brand"])                              # marque suivie : remise × 1,5
        self.assertTrue(all(p["score"] == p["pct"] * (1.5 if p["brand"] == last["brand"] else 1) for p in after))
        self.assertEqual(self.get("follows", lea)[1]["brands"], [])                     # chacun ses marques
        self.post("save", {"product_id": last["id"]}, mia)
        saves = self.get("saves", mia)[1]["products"]
        self.assertEqual([(p["id"], p["saved_price"]) for p in saves], [(last["id"], last["price"])])   # prix suivi depuis le favori
        self.assertEqual(self.get("saves", lea)[1]["products"], [])
        self.assertEqual(self.get("saves")[0], 401)

    def test_5_a_refusing_site_is_left_alone(self):
        for i in range(8):
            self.market.track(f"{self.sites.retailers['c']['home']}/p/canape-30{i:02d}.html", "c", "Site C")
        stats = self.crawler.nightly(["c"])["retailers"]["c"]
        self.assertEqual((stats["blocked"], stats["interrupted"]), (5, 3))              # 5 refus de suite, puis on arrête


if __name__ == "__main__":
    unittest.main()
