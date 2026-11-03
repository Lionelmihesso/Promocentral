"""De bout en bout, sur les flux de deux enseignes : lecture → catalogue → nuit → publication → API de l'app.

Ce que le produit promet, vérifié une fois : un vrai deal est visible dès le premier jour ; un accessoire n'entre pas au
catalogue ; un même EAN chez deux enseignes = un produit ; une promotion finie quitte les deals du jour ; une adresse qui
montre un autre produit est retirée sans rien enregistrer ; un flux injoignable n'écrit rien ; l'app lit le catalogue
publié (classement, filtres, recherche dans tout le catalogue, fiche avec depuis quand et jusqu'à quand, marque et
catégorie navigables, favoris et leur prix suivi, marques suivies, missions, clic sortant tracé).
"""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from urllib.parse import quote
from datetime import timedelta
from pathlib import Path

from deals import config
from deals.api import Api
from deals.extract.categories import FAMILIES
from deals.ingest import report
from deals.ingest.collector import Collector
from deals.ingest.feeds import Mapping
from deals.market import Market
from deals.publish import publish
from deals.store import Store
from deals.web import make_server


def ean(body12):
    total = sum(int(x) * (3 if i % 2 else 1) for i, x in enumerate(body12))
    return body12 + str((10 - total % 10) % 10)


EAN = {"lave_linge": ean("424200500002"), "canape": ean("366300000001"), "matelas": ean("366728702075"),
       "protege": ean("333333000004"), "lit": ean("366300000002"), "frigo": ean("880609500006"), "frigo2": ean("880609500013")}
NAMES = {"a": "Site A", "b": "Site B"}
# enseigne → référence → ligne du flux (modifiable pendant le test)
CATALOG = {
    "a": {"1001": {"slug": "lave-linge", "title": "Lave-linge hublot Bosch Série 6 9 kg", "brand": "Bosch", "gtin": EAN["lave_linge"],
                   "category": "Lave-linge", "price": 649, "strike": 799},
          "1002": {"slug": "canape", "title": "Canapé d'angle convertible Oslo", "brand": "Oslo", "gtin": EAN["canape"],
                   "category": "Canapés", "price": 1299},
          "1003": {"slug": "matelas", "title": "Matelas mousse 140x190 Bultex Integral 3", "brand": "Bultex", "gtin": EAN["matelas"],
                   "category": "Matelas", "price": 529.99, "strike": 879.99},
          "1004": {"slug": "matelas", "title": "Protège-matelas 140x190 imperméable", "brand": "Dodo", "gtin": EAN["protege"],
                   "category": "Matelas", "price": 29}},
    "b": {"2001": {"slug": "lave-linge", "title": "Lave-linge Bosch Série 6 9kg hublot", "brand": "Bosch", "gtin": EAN["lave_linge"],
                   "category": "Lave-linge", "price": 679},
          "2002": {"slug": "lit-coffre", "title": "Lit coffre 160x200 Nils", "brand": "Nils", "gtin": EAN["lit"], "category": "Lits",
                   "price": 459},
          "2003": {"slug": "refrigerateur", "title": "Réfrigérateur combiné Samsung RB38", "brand": "Samsung", "gtin": EAN["frigo"],
                   "category": "Réfrigérateurs", "price": 699}},
}
CSV = {"format": "csv", "fields": {"external_id": "ref", "title": "nom", "brand": "marque", "gtin": "ean", "category": "categorie",
                                   "url": "lien", "price": "prix", "list_price": "prix_barre", "valid_until": "fin_promo",
                                   "availability": "disponibilite"}}


def url(site, sku):
    return f"https://{site}.example/p/{CATALOG[site][sku]['slug']}-{sku}.html"


def feed(site):
    """Le flux du jour d'une enseigne, en CSV à la française (point-virgule, virgule décimale)."""
    dec = lambda v: f"{v:.2f}".replace(".", ",") if v else ""
    lines = ["ref;nom;marque;ean;categorie;lien;prix;prix_barre;fin_promo;disponibilite"]
    for sku, it in CATALOG[site].items():
        lines.append(";".join([sku, it["title"], it["brand"], it["gtin"], it["category"], it.get("url") or url(site, sku),
                               dec(it["price"]), dec(it.get("strike")), it.get("until") or "", "En stock"]))
    return ("\n".join(lines) + "\n").encode()


def transport(spec):
    if spec["key"] == "c":
        raise OSError("connexion refusée : flux injoignable")
    return feed(spec["key"])


class Flow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.store = Store(Path(cls.tmp, "t.sqlite"))
        cls.market = Market(cls.store)
        specs = {k: {"key": k, "name": n, "kind": "feed", "enabled": True, "families": list(FAMILIES),
                     "url": f"https://flux.example/{k}.csv", "mapping": Mapping.load(CSV)}
                 for k, n in {**NAMES, "c": "Site C"}.items()}
        cls.collector = Collector(cls.store, cls.market, specs, raw_dir=str(Path(cls.tmp, "raw")), transport=transport)
        cls.settings = config.load({}, public_url="http://127.0.0.1")
        cls.api = Api(cls.store, cls.settings)
        cls.srv = make_server(cls.api, cls.store, cls.settings, port=0)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
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

    def test_1_the_feeds_build_the_catalog(self):
        stats = self.collector.nightly(["a", "b"])
        a, b = stats["retailers"]["a"], stats["retailers"]["b"]
        self.assertEqual((a["received"], a["accepted"], a["ignored"], a["reasons"]), (4, 3, 1, {"accessoire": 1}))
        self.assertEqual((b["received"], b["accepted"], b["rejected"]), (3, 3, 0))
        q = self.store.q
        self.assertEqual(q("SELECT COUNT(*) n FROM offers WHERE product_id IN (SELECT id FROM products WHERE gtin=?)", (EAN["lave_linge"],), one=True)["n"], 2)
        self.assertEqual(q("SELECT COUNT(*) n FROM products", one=True)["n"], 5)       # 7 lignes, 1 accessoire, 1 EAN partagé
        self.assertFalse(q("SELECT 1 FROM offers WHERE url LIKE '%1004.html'"))         # l'accessoire n'entre pas
        self.assertEqual({r["gtin"]: r["category"] for r in q("SELECT gtin, category FROM products")}[EAN["lit"]], "lit")
        self.assertEqual({r["source"] for r in q("SELECT DISTINCT source FROM prices")}, {"feed:csv"})

    def test_2_day_one_deals_are_visible(self):
        stats = publish(self.store, self.market.today(), self.market.clock())
        self.assertEqual((stats["products"], stats["deals"]), (5, 2))
        st, today, _ = self.get("today")
        self.assertEqual(st, 200)
        self.assertEqual([(p["name"], p["pct"]) for p in today["products"]],
                         [("Matelas mousse 140x190 Integral 3", 40), ("Lave-linge hublot Série 6 9 kg", 19)])   # prix barré du flux
        self.assertEqual(sum(c["count"] for c in self.get("categories")[1]), today["total"])
        self.assertEqual([p["kind"] for p in today["products"]], ["Matelas", "Lave-linge"])     # la liste : marque et catégorie
        self.assertTrue(all(p["offer_id"] for p in today["products"]))                       # un « Voir l'offre » direct possible
        item = self.get(f"item/{today['products'][1]['id']}")[1]
        self.assertEqual(item["name"], "Lave-linge hublot Série 6 9 kg")
        self.assertNotIn("specs", item)                                                     # la description reste chez l'enseigne
        self.assertFalse({"history", "position"} & set(item))                               # v60 : la fiche ne montre plus la courbe
        curve = json.loads(self.store.q("SELECT history FROM catalog WHERE product_id=?", (item["id"],), one=True)["history"])
        self.assertEqual((len(curve["p"]), curve["p"][-1]), (90, 649))                        # gardée : le prix bas (catalog.cheap)
        self.assertIsInstance(today["published_at"], float)                                     # « mis à jour à … »
        self.assertEqual({c["key"]: c["best"] for c in self.get("categories")[1]}, {"matelas": 40, "lave_linge": 19})
        self.assertEqual(sorted((c["key"], c["count"]) for c in self.get("categories?all=1")[1])[:3],      # aussi sans remise
                         [("canape", 0), ("lave_linge", 1), ("lit", 0)])
        self.assertEqual([(b["name"], b["best"], b["top"]["category"], b["categories"]) for b in self.get("brands")[1]],
                         [("Bosch", 19, "lave_linge", ["Lave-linge"]), ("Bultex", 40, "matelas", ["Matelas"])])
        self.assertEqual([(b["name"], b["count"], b["products"]) for b in self.get("brands?all=1")[1]],     # on entre par la marque
                         [("Bosch", 1, 1), ("Bultex", 1, 1), ("Nils", 0, 1), ("Oslo", 0, 1), ("Samsung", 0, 1)])
        self.assertEqual(self.get("today?category=matelas,lave_linge")[1]["total"], 2)           # un univers = plusieurs catégories
        self.assertEqual([(o["merchant"], o["price"], o["best"]) for o in item["offers"]], [("Site A", 649.0, True), ("Site B", 679.0, False)])
        self.assertNotIn("url", item["offers"][0])                          # l'app passe par le clic tracé
        st, _, headers = self.get(f"out/{item['offers'][0]['offer_id']}?from=item")
        self.assertEqual((st, headers["Location"]), (302, url("a", "1001")))
        self.get(f"out/{item['offers'][1]['offer_id']}?from=alternative")                 # fiche ouverte depuis « moins cher »
        self.assertEqual([r["source"] for r in self.store.q("SELECT source FROM clicks ORDER BY rowid")], ["item", "alternative"])
        self.assertEqual(self.get("out/999999")[0], 404)
        top = self.get("top?family=ameublement,literie")[1]["products"]                 # v66 : Top deals d'un univers
        self.assertTrue(top and {p["category"] for p in top} <= {"canape", "fauteuil", "lit", "armoire", "table", "buffet",
                                                               "meuble_tv", "commode", "matelas", "sommier"}, top)
        self.assertEqual(self.get("top?family=jardin")[0], 400)
        self.assertEqual([p["brand"] for p in self.get("search?brand=Bosch")[1]["products"]], ["Bosch"])   # la marque, par la recherche
        self.assertEqual(self.get("search?brand=Inconnue")[1]["products"], [])
        self.assertEqual([p["brand"] for p in self.get("today?q=lave%20linge")[1]["products"]], ["Bosch"])
        self.assertEqual([p["category"] for p in self.get("today?category=matelas")[1]["products"]], ["matelas"])
        found = self.get("search?q=site")[1]["products"]                                # tout le catalogue : remises d'abord
        self.assertEqual([(p["brand"], p["pct"]) for p in found],
                         [("Bultex", 40), ("Bosch", 19), ("Nils", 0), ("Samsung", 0), ("Oslo", 0)])
        feed = self.get("search?q=")[1]                                                # ni mot ni filtre : le feed
        self.assertEqual(([p["brand"] for p in feed["products"]], feed["recent"]),
                         (["Bultex", "Bosch", "Nils", "Samsung", "Oslo"], []))              # une catégorie chacun : remises d'abord
        mine = self.get("search?recent=" + quote("canapé|lave linge"))[1]                     # orienté par les recherches récentes
        self.assertEqual(([p["brand"] for p in mine["products"]][:2], mine["recent"]), (["Oslo", "Bosch"], ["canapé", "lave linge"]))
        many = self.get("search?recent=" + quote("xyzzy1|xyzzy2|xyzzy3|xyzzy4|canapé"))[1]  # les 4 dernières seulement
        self.assertEqual((many["products"][0]["brand"], many["recent"]), ("Bultex", []))
        self.assertEqual(Api._recent({"recent": " |" + "a" * 120 + "| canapé "}), ["a" * 80, "canapé"])
        self.assertEqual(feed["offs"], {"1": 2, "10": 2, "20": 1, "30": 1, "40": 1, "50": 0, "low": 0})   # filtre Promo : chaque choix
        self.assertEqual(self.get("search?low=1")[1]["total"], 0)                          # premier jour : aucun historique
        top = self.get("top")[1]["products"]                                               # top deals : les remises, sans prix bas
        self.assertEqual([(p["brand"], p["why"]["pct"], p["why"]["low"]) for p in top], [("Bultex", 40, None), ("Bosch", 19, None)])
        self.assertEqual(self.store.q("SELECT COUNT(*) n FROM catalog WHERE level IS NOT NULL", one=True)["n"], 0)
        withq = self.get("search?recent=" + quote("canapé") + "&q=lave%20linge")[1]          # une requête : elles n'y font rien
        self.assertEqual(([p["brand"] for p in withq["products"]], withq["recent"]), (["Bosch"], []))
        cheap = self.get("search?q=site&max=700")[1]["products"]                        # budget
        self.assertTrue(cheap and all(p["price"] <= 700 for p in cheap) and len(cheap) < len(found))
        self.assertEqual([p["brand"] for p in self.get("search?off=1")[1]["products"]], ["Bultex", "Bosch"])   # sans mot : remises
        by_price = [p["price"] for p in self.get("search?q=site&sort=price")[1]["products"]]
        self.assertEqual(by_price, sorted(by_price))
        st, only, _ = self.get("search?q=site&category=matelas")
        self.assertEqual(([p["category"] for p in only["products"]], len(only["categories"])), (["matelas"], 1))   # v59 : un rayon choisi, ses catégories
        self.assertEqual(len(self.get("search?q=site")[1]["categories"]), 5)                                      # sans rayon : la facette entière
        self.assertEqual(self.get("search?q=site&sort=hasard")[0], 400)
        self.assertEqual(self.get("search?q=site&max=beaucoup")[0], 400)
        self.assertEqual(item["alternatives"], [])                                       # rien de comparable ici
        self.assertTrue(all(p["since"] == p["published_on"] for p in today["products"]))  # première publication : tout commence

    def test_3_second_night(self):
        tomorrow = self.market.today() + timedelta(days=1)
        CATALOG["a"]["1002"].update(price=999, strike=1299,                            # promo sur le canapé, finit dans 2 jours
                                    until=(tomorrow + timedelta(days=2)).strftime("%d/%m/%Y"))
        CATALOG["a"]["1003"].update(price=879.99, strike=None)                         # la promo du matelas est finie
        CATALOG["b"]["2003"] = {**CATALOG["b"]["2003"], "title": "Réfrigérateur américain Samsung RS68", "gtin": EAN["frigo2"],
                                "url": url("b", "2003")}                               # une autre fiche à la même adresse
        stats = self.collector.nightly(["a", "b"])
        a, b = stats["retailers"]["a"], stats["retailers"]["b"]
        self.assertEqual((a["accepted"], a["changed"], a["gone"]), (3, 2, 0))          # canapé et matelas changés, lave-linge reconfirmé
        self.assertEqual((b["accepted"], b["gone"]), (2, 1))                            # autre produit à la même adresse
        self.assertEqual(self.store.q("SELECT note FROM offers WHERE url LIKE '%2003.html'", one=True)["note"], "l'adresse montre un autre produit")
        self.assertEqual(self.store.q("SELECT COUNT(*) n FROM prices p JOIN offers o ON o.id=p.offer_id WHERE o.url LIKE '%2003.html'", one=True)["n"], 1)
        name = report.write(stats, Path(self.tmp, "reports"))
        self.assertIn("1 299,00 € → 999,00 €", Path(self.tmp, "reports", f"{name}.md").read_text(encoding="utf-8"))
        publish(self.store, tomorrow, self.market.clock() + 86400)                     # publication du lendemain matin
        names = [p["name"] for p in self.get("today")[1]["products"]]
        self.assertIn("Canapé d'angle convertible", names)                              # la promo du jour apparaît
        self.assertNotIn("Matelas mousse 140x190 Integral 3", names)                    # la promo finie disparaît
        self.assertNotIn("Réfrigérateur combiné RB38", [p["name"] for p in self.get("search?q=samsung")[1]["products"]])
        canape = next(p for p in self.get("today")[1]["products"] if p["brand"] == "Oslo")
        self.assertEqual((canape["pct"], canape["was"]), (23, 1299.0))                  # prix barré au prix de la veille : remise confirmée
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
        self.assertEqual(self.get("saves")[:2], (200, {"products": []}))                          # sans compte : rien de gardé
        found = self.get("search?q=" + urllib.parse.quote("lave-linge 9 kg sous 700 €"))[1]        # la Recherche comprend la phrase
        self.assertEqual(([p["brand"] for p in found["products"]], [c["label"] for c in found["chips"]]),
                         (["Bosch"], ["Lave-linge", "9 kg et plus", "Moins de 700 €"]))
        made = self.post("missions", {"category": "lave_linge", "attrs": {"capacity_kg": 9}, "max_price": 700}, mia)
        self.assertEqual((made["total"], self.get("missions", mia)[1]["reached"]), (1, 1))
        self.assertEqual(self.get("missions", lea)[1]["missions"], [])                             # chacun ses missions
        self.post("missions/delete", {"id": made["id"]}, mia)
        self.assertEqual(self.get("missions", mia)[1]["missions"], [])
        self.assertEqual([p["brand"] for p in self.get("search?category=lave_linge")[1]["products"]], ["Bosch"])   # depuis la fiche
        self.assertEqual(self.get("search?category=inconnue")[1]["products"], [])
        self.assertEqual(self.get("search?brand=Nils")[1]["products"][0]["pct"], 0)              # marque sans remise : visitable

    def test_6_only_partner_offers_are_published(self):
        q, today, now = self.store.q, self.market.today(), self.market.clock()
        theirs = {r["product_id"] for r in q("SELECT product_id FROM offers WHERE retailer='b' AND product_id IS NOT NULL "
                                            "AND status NOT IN ('gone', 'out_of_scope')")}
        stats = publish(self.store, today, now, partners={"b"})
        self.assertEqual({r["merchant"] for r in q("SELECT merchant FROM catalog_offers")}, {"Site B"})   # une seule enseigne
        self.assertEqual({r["product_id"] for r in q("SELECT product_id FROM catalog")}, theirs)
        self.assertEqual(stats["products"], len(theirs))
        publish(self.store, today, now)                                                    # de nouveau tout, pour la suite

    def test_5_an_unreachable_feed_writes_nothing_and_says_why(self):
        prices = self.store.q("SELECT COUNT(*) n FROM prices", one=True)["n"]
        c = self.collector.nightly(["c"])["retailers"]["c"]
        self.assertEqual((c["broken"], c["accepted"]), (True, 0))
        self.assertIn("flux injoignable", c["error"])
        self.assertEqual(self.store.q("SELECT COUNT(*) n FROM prices", one=True)["n"], prices)


if __name__ == "__main__":
    unittest.main()
