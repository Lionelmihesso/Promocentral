"""Couche de décision grand public (P0) : le parcours complet par l'API HTTP, sur le vrai moteur et un marché simulé.
recherche → produit → « je l'achète à X » → prix atteint → récapitulatif → clic marchand → étoile polaire."""
import json
import threading
import unittest
import urllib.error
import urllib.request
from datetime import timedelta

from app import build_demo
from radar import accounts
from listener.server import serve
from radar.api import admin_routes, routes


class ConsumerAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.L, cls.R, demo = build_demo(warmup_days=60)
        cls.srv = serve(cls.L, 0, extra=routes(cls.R) + admin_routes(cls.R) + demo)
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close(); cls.L.close()

    _sessions = {}

    def raw(self, method, path, body=None, cookie=None):
        """Requête brute, sans suivre les redirections ; renvoie (statut, en-têtes, corps)."""
        h = {"Content-Type": "application/json"}
        if cookie:
            h["Cookie"] = f"deals_session={cookie}"
        req = urllib.request.Request(f"{self.base}/api/r/{path}", method=method,
                                     data=json.dumps(body).encode() if body is not None else None, headers=h)
        opener = urllib.request.build_opener(type("NoRedirect", (urllib.request.HTTPRedirectHandler,), {"redirect_request": lambda *a: None}))
        try:
            with opener.open(req) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def login(self, user):
        """Parcours réel : e-mail → lien reçu → vérification → cookie de session."""
        if user not in self._sessions:
            st, _, _ = self.raw("POST", "auth/request", {"email": f"{user}@test.local"})
            self.assertEqual(st, 200)
            link = accounts.of(self.R).outbox.sent[-1][1]
            st, hdrs, _ = self.raw("GET", "auth/verify?" + link.split("?", 1)[1])
            self.assertEqual(st, 302)
            cookie = hdrs["Set-Cookie"].split(";", 1)[0].split("=", 1)[1]
            self._sessions[user] = cookie
        return self._sessions[user]

    def call(self, method, path, body=None, user="lea"):
        sep = "&" if "?" in path else "?"
        req = urllib.request.Request(f"{self.base}/api/r/{path}", method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json", "Cookie": f"deals_session={self.login(user)}"})
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    def test_00_public_mode_exposes_only_consumer_api(self):
        from listener.server import serve as serve_public
        srv = serve_public(self.L, 0, extra=routes(self.R), admin=False)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_port}"
        try:
            for path in ["/api/offers", "/api/rules", "/api/run", "/api/stream", "/admin", "/api/admin/metrics", "/api/demo/next"]:
                with self.assertRaises(urllib.error.HTTPError) as cm:
                    urllib.request.urlopen(urllib.request.Request(f"{base}{path}", method="POST" if path.startswith(("/api/run", "/api/rules", "/api/demo")) else "GET", data=b"{}" if path.startswith(("/api/run", "/api/rules", "/api/demo")) else None))
                self.assertEqual(cm.exception.code, 404, path)
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(urllib.request.Request(f"{base}/api/r/feed"))
            self.assertEqual(cm.exception.code, 401)                       # l'API consommateur reste là, protégée par session
        finally:
            srv.shutdown(); srv.server_close()

    def test_0_auth_magic_link_and_isolation(self):
        # pas de session : 401, même avec un paramètre ?user= (ignoré)
        st, _, _ = self.raw("GET", "feed?user=lea")
        self.assertEqual(st, 401)
        # réponse identique qu'une adresse existe ou non
        st, _, body = self.raw("POST", "auth/request", {"email": "inconnu@test.local"})
        self.assertEqual(st, 200)
        # lien à usage unique
        link = accounts.of(self.R).outbox.sent[-1][1]
        tok = link.split("token=", 1)[1]
        st, hdrs, _ = self.raw("GET", f"auth/verify?token={tok}")
        self.assertEqual(st, 302)
        self.assertIn("HttpOnly", hdrs["Set-Cookie"])
        st2, hdrs2, _ = self.raw("GET", f"auth/verify?token={tok}")
        self.assertEqual(st2, 302)                                  # déjà utilisé : retour à l'app, sans cookie
        self.assertIn("auth=expired", hdrs2["Location"])
        self.assertIsNone(hdrs2.get("Set-Cookie"))
        cookie = hdrs["Set-Cookie"].split(";", 1)[0].split("=", 1)[1]
        st, _, body = self.raw("GET", "auth/me", cookie=cookie)
        self.assertEqual(json.loads(body)["email"], "inconnu@test.local")
        # le cookie ouvre le compte ; un _session dans l'URL ne remplace pas le cookie
        self.assertEqual(self.raw("GET", "feed?_session=" + cookie)[0], 401)
        # déconnexion : la session n'est plus valable
        self.assertEqual(self.raw("POST", "auth/logout", {}, cookie=cookie)[0], 200)
        self.assertEqual(self.raw("GET", "auth/me", cookie=cookie)[0], 401)
        # mauvais jeton, adresse invalide
        self.assertIn("auth=expired", self.raw("GET", "auth/verify?token=nimporte")[1]["Location"])
        self.assertEqual(self.raw("POST", "auth/request", {"email": "pas-un-mail"})[0], 400)

    def test_0b_rate_limit_on_links(self):
        codes = [self.raw("POST", "auth/request", {"email": "spam@test.local"})[0] for _ in range(7)]
        self.assertEqual(codes[:5], [200] * 5)
        self.assertEqual(codes[5:], [429, 429])

    def test_0c_users_cannot_read_each_other(self):
        self.call("POST", "watch", {"search": {"category": "refrigerateur"}, "target_price": 12345}, user="zoe")
        self.assertNotIn("12345", json.dumps(self.call("GET", "watches", user="lea")))
        self.assertIn("12345", json.dumps(self.call("GET", "watches", user="zoe")))

    def next_day(self):
        urllib.request.urlopen(urllib.request.Request(f"{self.base}/api/demo/next", method="POST", data=b"{}"))

    def test_1_search_product_watch_hit_click_metrics(self):
        s = self.call("GET", "search?q=lave-linge")
        self.assertGreater(s["count"], 0)
        self.assertTrue(all(p["category"] == "lave_linge" for p in s["products"]))
        pid = s["products"][0]["id"]
        p = self.call("GET", f"product/{pid}")
        self.assertIsNone(p["watch"])
        self.assertLessEqual(p["range"]["low"], p["price"])
        self.assertGreaterEqual(p["range"]["high"], p["price"])
        r = self.call("POST", "watch", {"product_id": pid, "target_price": p["price"] + 1})       # prix déjà atteint
        self.assertEqual([e["type"] for e in r["immediate"]], ["TARGET_REACHED"])                # réponse immédiate, sans attendre la nuit
        f = self.call("GET", "feed")
        self.assertIn(pid, [h["product_id"] for h in f["watch_hits"]])                            # « watch hit », distinct de la découverte
        self.assertNotIn(pid, [o["product_id"] for o in f["foryou"] + f["discovery"]])
        self.assertEqual(self.call("GET", f"product/{pid}")["watch"]["state"], "TARGET_REACHED")
        # clic marchand tracé puis redirection
        st, hdrs, _ = self.raw("GET", f"go/{pid}?from=watch_hit", cookie=self.login("lea"))
        self.assertEqual(st, 302)
        self.assertTrue(hdrs["Location"].startswith("http"))

    def test_2_target_update_and_stop(self):
        pid = self.call("GET", "search?q=televiseur")["products"][0]["id"]
        w = self.call("POST", "watch", {"product_id": pid, "target_price": 1})
        self.assertEqual(w["immediate"], [])
        r = self.call("POST", "target", {"watch_id": w["watch_id"], "target_price": 99999})
        self.assertEqual(r["immediate"][0]["type"], "TARGET_REACHED")
        self.call("POST", f"watch/{w['watch_id']}/stop", {})
        self.assertNotIn(w["watch_id"], [x["id"] for x in self.call("GET", "watches")])
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.call("POST", "watch", {"product_id": pid, "target_price": -5})
        self.assertEqual(cm.exception.code, 400)

    def test_3_search_watch(self):
        r = self.call("POST", "watch", {"search": {"category": "refrigerateur"}, "target_price": 99999}, user="sam")
        self.assertEqual(r["immediate"][0]["type"], "TARGET_REACHED")                             # une recherche surveillée = même entité
        kinds = {w["kind"] for w in self.call("GET", "watches", user="sam")}
        self.assertEqual(kinds, {"search"})

    def test_4_dismiss_and_alternative_learning(self):
        R = self.R
        uid = R.user("nina")
        tvs = self.L.q("SELECT id, brand FROM products WHERE category='televiseur'")
        big = max(tvs, key=lambda t: R.market_signal(t["id"])["price"])
        wid = R.watch(uid, big["id"], R.market_signal(big["id"])["price"] * 0.999 - 1, alternatives=True)
        others = [t for t in tvs if t["id"] != big["id"]]
        # nina refuse deux fois une autre marque → le profil devient « fidèle à la marque »
        for t in others[:2]:
            self.L.q("INSERT INTO opportunities(user_id, product_id, type, score, day, alt_of_product_id, section, created_at) VALUES (?,?,?,?,?,?,?,0)",
                     (uid, t["id"], "ALTERNATIVE", 1, (self.R.today() - timedelta(days=30)).isoformat(), big["id"], "watch"))
            self.L.q("UPDATE products SET brand='Autre' WHERE id=?", (t["id"],)) if t["brand"] == big["brand"] else None
            R.reject_alternative(wid, t["id"])
        prof = R.alt_profile(uid)
        self.assertTrue(prof["brand_loyal"])
        base = {"brand": "X", "price": 1000, "attributes": {}}
        self.assertGreater(R.rank_alternative(0.7, base, {"brand": "X", "price": 900}, prof), R.rank_alternative(0.8, base, {"brand": "Y", "price": 900}, prof))
        f = self.call("GET", "feed", user="nina")
        pid = (f["foryou"] + f["discovery"] + [{"product_id": others[-1]["id"]}])[0]["product_id"]
        self.call("POST", "dismiss", {"product_id": pid}, user="nina")
        f2 = self.call("GET", "feed", user="nina")
        self.assertNotIn(pid, [o["product_id"] for o in f2["foryou"] + f2["discovery"]])

    def test_5_app_and_admin_pages(self):
        app = urllib.request.urlopen(self.base + "/").read().decode()
        admin = urllib.request.urlopen(self.base + "/admin").read().decode()
        self.assertIn("/api/r/", app)                      # l'app consomme l'API grand public
        self.assertNotIn("/api/r/", admin)                 # la console reste un outil interne

    def test_7_shop_contract_product_brand_category(self):
        # lecture ouverte, sans compte
        st, _, body = self.raw("GET", "today")
        today = json.loads(body)
        self.assertEqual(st, 200)
        self.assertFalse(today["signed_in"])
        self.assertTrue(today["products"])
        ranks = [p["score"] for p in today["products"]]
        self.assertEqual(ranks, sorted(ranks, reverse=True))                       # classé par remise
        cats = json.loads(self.raw("GET", "categories")[2])
        self.assertEqual(sum(c["count"] for c in cats), today["total"])           # rien de perdu entre catégories et produits
        brands = json.loads(self.raw("GET", "brands")[2])
        self.assertTrue(brands)
        # actions personnelles : refusées sans session
        self.assertEqual(self.raw("POST", "brand/follow", {"brand": brands[0]["name"]})[0], 401)
        self.assertEqual(self.raw("POST", "save", {"product_id": today["products"][0]["id"]})[0], 401)
        self.assertEqual(self.raw("GET", "saves")[0], 401)
        # marque suivie : ses produits remontent (remise × 1,5)
        last = today["products"][-1]
        brand = last["brand"]
        self.call("POST", "brand/follow", {"brand": brand}, user="mia")
        after = json.loads(self.raw("GET", "today", cookie=self.login("mia"))[2])
        self.assertTrue(after["signed_in"])
        self.assertIn(brand, [p["brand"] for p in after["products"] if p["followed"]])
        # le coefficient est appliqué exactement : score = remise × 1,5 pour la marque suivie, remise seule sinon
        for p in after["products"]:
            expected = p["pct"] * (1.5 if p["brand"] == brand else 1)
            self.assertAlmostEqual(p["score"], expected, places=6, msg=p["title"])
        self.assertTrue(all(p["followed"] == (p["brand"] == brand) for p in after["products"]))
        self.assertEqual(self.call("GET", "follows", user="mia")["brands"], [brand])
        self.call("POST", "brand/follow", {"brand": brand, "on": False}, user="mia")
        self.assertEqual(self.call("GET", "follows", user="mia")["brands"], [])
        # favoris : ajout, liste, retrait
        pid = today["products"][0]["id"]
        self.assertTrue(self.call("POST", "save", {"product_id": pid}, user="mia")["saved"])
        self.assertIn(pid, [p["id"] for p in self.call("GET", "saves", user="mia")["products"]])
        self.assertNotIn(pid, [p["id"] for p in self.call("GET", "saves", user="lea")["products"]])   # isolé par compte
        self.call("POST", "save", {"product_id": pid, "on": False}, user="mia")
        self.assertEqual(self.call("GET", "saves", user="mia")["products"], [])
        # fiche : offres par enseigne, meilleure en premier ; similaires de la même catégorie
        item = json.loads(self.raw("GET", f"item/{pid}")[2])
        prices = [o["price"] for o in item["offers"]]
        self.assertEqual(prices, sorted(prices))
        self.assertTrue(item["offers"][0]["best"])
        self.assertTrue(all(c["category"] == item["category"] and c["id"] != pid for c in item["similar"]))
        # marque : page et inconnus
        self.assertEqual(json.loads(self.raw("GET", "brand/" + brand.replace(" ", "%20"))[2])["brand"], brand)
        self.assertEqual(self.raw("GET", "brand/MarqueInconnue")[0], 404)
        self.assertEqual(self.raw("GET", "item/999999")[0], 404)
        # filtres : catégorie et texte (accents ignorés), tout reste dans la catégorie
        cat = cats[0]["key"]
        by_cat = json.loads(self.raw("GET", f"today?category={cat}")[2])
        self.assertTrue(by_cat["products"] and all(p["category"] == cat for p in by_cat["products"]))
        word = today["products"][0]["brand"].upper()
        hits = json.loads(self.raw("GET", "today?q=" + word.replace(" ", "%20"))[2])["products"]
        self.assertTrue(hits and all(word.lower() in p["brand"].lower() for p in hits))

    def test_8_outbound_clicks_tracked_without_account(self):
        pid = json.loads(self.raw("GET", "today")[2])["products"][0]["id"]
        item = json.loads(self.raw("GET", f"item/{pid}")[2])
        off = item["offers"][0]
        before = json.loads(urllib.request.urlopen(f"{self.base}/api/admin/metrics").read())["total_clicks"]
        st, hdrs, _ = self.raw("GET", f"out/{off['offer_id']}?from=item")          # anonyme
        self.assertEqual(st, 302)
        self.assertEqual(hdrs["Location"], off["url"])                             # vers l'offre connue, rien d'autre
        st, _, _ = self.raw("GET", f"out/{off['offer_id']}?from=item", cookie=self.login("mia"))   # connecté
        self.assertEqual(st, 302)
        m = json.loads(urllib.request.urlopen(f"{self.base}/api/admin/metrics").read())
        self.assertEqual(m["total_clicks"], before + 2)
        self.assertGreaterEqual(m["by_source"]["item"], 2)
        self.assertGreaterEqual(m["by_day"][0]["signed"], 1)
        # pas de redirection ouverte, source inconnue ignorée
        self.assertEqual(self.raw("GET", "out/999999")[0], 404)
        self.assertEqual(self.raw("GET", f"out/{off['offer_id']}?from=http://evil.example")[0], 302)
        self.assertNotIn("http://evil.example", json.dumps(urllib.request.urlopen(f"{self.base}/api/admin/metrics").read().decode()))

    def test_6_batch_rollback(self):
        n = self.L.q("SELECT COUNT(*) n FROM users", one=True)["n"]
        with self.assertRaises(RuntimeError):
            with self.L.batch():
                self.R.user("fantome")
                raise RuntimeError("panne au milieu de la tâche")
        self.assertEqual(self.L.q("SELECT COUNT(*) n FROM users", one=True)["n"], n)   # rien d'écrit à moitié


if __name__ == "__main__":
    unittest.main()
