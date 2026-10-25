"""Profil de goûts : des rayons et des marques pesés par ce que la personne choisit et regarde, qui font passer ses deals
devant sans jamais faire oublier l'intérêt du deal ; rien n'est gardé côté serveur pour une personne sans compte ; une
personne sur dix est témoin, pour mesurer ce que la personnalisation rapporte."""
import hashlib
import shutil
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from deals import config, demo
from deals import profile as P
from deals.api import Api, Request
from deals.catalog import cheap
from deals.store import Store

DB = None


def setUpModule():
    global DB
    DB = Path(tempfile.mkdtemp(), "profile.sqlite")
    s = Store(DB)
    demo.build(s, nights=20, partners=set(demo.RULES))
    s.close()


def row(pid, cat, brand="B", pct=0):
    return {"product_id": pid, "category": cat, "brand": brand, "pct": pct}


def account(store, now, control=False):
    """Un compte connecté, témoin ou non (le hachage décide : on en cherche un qui convient) → (uid, jeton)."""
    n = store.q("SELECT COUNT(*) n FROM users", one=True)["n"]
    while True:
        n += 1
        uid = store.x("INSERT INTO users(email, created_at) VALUES (?, 0)", (f"u{n}-{now}@exemple.test",))
        if P.control(uid) == control:
            break
    token = f"t{uid}"
    store.x("INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES (?,?,?,?)",
            (hashlib.sha256(token.encode()).hexdigest(), uid, 0, now + 86400))
    return uid, token


class Model(unittest.TestCase):
    def test_chosen_counts_fully_what_is_seen_counts_less_and_fades(self):
        p = P.build(chosen=["canape"], follows=["Nordvik"])
        self.assertEqual((p.cats["canape"], p.brands["Nordvik"]), (1.0, 1.0))
        seen = P.build(events=[("click", "matelas", "Dormea", 0), ("click", "matelas", "Dormea", 0)])
        self.assertAlmostEqual(seen.cats["matelas"], P.SEEN_CAT)                 # plafond d'un rayon vu : 0,8
        self.assertAlmostEqual(seen.brands["Dormea"], P.SEEN_BRAND)              # d'une marque vue : 0,4
        one = P.build(events=[("view", "matelas", "Dormea", 0)])
        self.assertAlmostEqual(one.cats["matelas"], P.SEEN_CAT * 0.5 / P.FULL)   # une fiche : confiance d'un quart
        self.assertNotIn("Dormea", one.brands)                                   # une marque vue une fois ne compte pas
        old = P.build(events=[("click", "matelas", None, 30), ("click", "matelas", None, 30)])
        self.assertAlmostEqual(old.cats["matelas"], P.SEEN_CAT * min(1, 1.5 / P.FULL))   # 30 jours : moitié moins
        self.assertFalse(P.build().personal)

    def test_each_signal_has_its_weight(self):
        fav = P.build(events=[("save", "matelas", "Dormea", 0)])            # un favori : 2 points, confiance pleine
        self.assertAlmostEqual(fav.cats["matelas"], 0.8)
        self.assertAlmostEqual(fav.brands["Dormea"], 0.4)
        for kind, points in (("click", 1.5), ("search", 1.0), ("view", 0.5)):
            self.assertAlmostEqual(P.build(events=[(kind, "matelas", None, 0)]).cats["matelas"], 0.8 * points / 2, msg=kind)
        two = P.build(events=[("view", "matelas", "Dormea", 0)] * 2)         # une marque compte dès un point : deux fiches
        self.assertAlmostEqual(two.brands["Dormea"], 0.4 * 1 / 2)
        ahead = P.build(events=[("view", "matelas", None, -30)])             # une horloge en avance : compté comme aujourd'hui
        self.assertAlmostEqual(ahead.cats["matelas"], 0.8 * 0.5 / 2)
        self.assertEqual(P.build(events=[("click", "matelas", None, 0)] * 2).brands, {})   # sans marque : aucune marque

    def test_the_most_seen_rayon_sets_the_scale_and_its_family_follows_the_best(self):
        p = P.build(events=[("click", "canape", None, 0), ("click", "canape", None, 0), ("view", "fauteuil", None, 0)])
        self.assertAlmostEqual(p.cats["canape"], 0.8)                        # 3,5 points : confiance pleine
        self.assertAlmostEqual(p.cats["fauteuil"], 0.8 * 0.5 / 3)            # à l'échelle du rayon le plus regardé
        self.assertAlmostEqual(p.boost("lit", "X"), 1 + 0.5 * 0.3 * 0.8)     # la famille suit son meilleur rayon
        b = P.build(events=[("click", None, "Dormea", 0)] * 2 + [("view", None, "Nordvik", 0)] * 2)
        self.assertAlmostEqual(b.brands["Dormea"], 0.4)                      # les marques aussi, à l'échelle de la plus vue
        self.assertAlmostEqual(b.brands["Nordvik"], 0.4 * 1 / 3)
        self.assertEqual(P.build(events=[("search", None, "Dormea", 0)] * 2).cats, {})   # une marque cherchée : pas de rayon

    def test_pour_vous_needs_the_rayon_itself_and_a_personal_order(self):
        self.assertEqual(P.mine([row(1, "canape")], P.Profile(cats={"canape": 0.3}, personal=True)), [row(1, "canape")])
        self.assertEqual(P.mine([row(1, "canape")], P.Profile(cats={"canape": 0.29}, personal=True)), [])
        self.assertEqual(P.mine([row(1, "canape")], P.build(chosen=["canape"], personal=False)), [])   # témoin : rien

    def test_a_boost_is_bounded_and_a_family_only_gets_a_little(self):
        p = P.build(chosen=["canape"])
        self.assertEqual(p.boost("canape", "X"), 1.5)
        self.assertAlmostEqual(p.boost("fauteuil", "X"), 1 + P.BOOST * P.FAMILY)  # même famille (ameublement)
        self.assertEqual(p.boost("lave_linge", "X"), 1.0)
        self.assertEqual(P.mine([row(1, "canape"), row(2, "fauteuil")], p), [row(1, "canape")])   # « pour vous » : pas la famille
        before = P.Profile(follows=frozenset({"Nordvik"}))                        # témoin : l'ordre d'avant
        self.assertEqual((before.boost("canape", "Nordvik"), before.boost("canape", "X")), (1.5, 1))
        tie = [row(1, "lit", "Nordvik", pct=20), row(2, "four", "X", pct=30)]      # 20 × 1,5 = 30 : à égalité, l'identifiant, comme avant
        self.assertEqual([r["product_id"] for r in P.arrange(tie, lambda r: r["pct"], before)], [1, 2])

    def test_the_interest_of_the_deal_comes_first(self):
        p = P.build(chosen=["canape"])
        rows = [row(1, "canape", pct=26), row(2, "lave_linge", pct=40), row(3, "canape", pct=25), row(4, "four", pct=30)]
        order = [r["product_id"] for r in P.arrange(rows, lambda r: r["pct"], p)]
        self.assertEqual(order[0], 2)                         # 40 % hors des goûts passe devant 26 % × 1,5 = 39
        self.assertLess(order.index(3), order.index(4))       # 25 % × 1,5 = 37,5 passe devant 30 %
        tie = [row(1, "canape", pct=26), row(2, "four", pct=39)]                  # 26 % × 1,5 = 39 : à égalité, la plus forte remise
        self.assertEqual([r["product_id"] for r in P.arrange(tie, lambda r: r["pct"], p)], [2, 1])
        self.assertEqual([r["product_id"] for r in P.arrange(rows, lambda r: r["pct"], P.build())], [2, 4, 1, 3])
        same = [row(1, "canape", pct=40), row(2, "canape", pct=39), row(3, "canape", pct=38), row(4, "four", pct=10)]
        self.assertEqual([r["product_id"] for r in P.arrange(same, lambda r: r["pct"], P.build())], [1, 2, 3, 4])   # sans goûts : l'ordre d'avant

    def test_one_slot_in_four_goes_to_the_best_deal_and_a_rayon_never_floods(self):
        liked = P.build(follows=["Nordvik"])                  # une marque suivie, dans des rayons tous différents
        rows = [row(i, c, "Nordvik", pct=20) for i, c in enumerate(["canape", "lit", "four", "hotte", "table"], 1)] + \
            [row(20, "matelas", pct=28), row(21, "commode", pct=27)]
        self.assertEqual([r["product_id"] for r in P.arrange(rows, lambda r: r["pct"], liked)], [1, 2, 3, 20, 4, 5, 21])
        # 20 % × 1,5 = 30 passe devant 28 %, sauf la 4e place : le meilleur deal restant, sans les goûts
        p = P.build(chosen=["canape"])
        others = ["four", "lit", "table", "hotte", "buffet", "commode"]
        rows = [row(i, "canape", pct=40 - i) for i in range(1, 7)] + [row(20 + k, c, pct=33 - k) for k, c in enumerate(others)]
        order = P.arrange(rows, lambda r: r["pct"], p)
        for i in range(len(order) - 3):                       # jamais plus de deux du même rayon sur quatre de suite
            window = [r["category"] for r in order[i:i + 4]]
            self.assertLessEqual(window.count("canape"), P.SAME, [r["category"] for r in order])
        self.assertEqual(sorted(r["product_id"] for r in order), sorted(r["product_id"] for r in rows))   # rien de perdu
        self.assertEqual(P.diversify([row(1, "canape"), row(2, "canape"), row(3, "canape")]), [row(1, "canape"), row(2, "canape"),
                                                                                              row(3, "canape")])   # faute d'autre : l'ordre
        ids = lambda rows: [r["product_id"] for r in P.diversify(rows)]
        self.assertEqual(ids([row(1, "c"), row(2, "c"), row(3, "c"), row(4, "a")]), [1, 2, 4, 3])
        self.assertEqual(ids([row(1, "c"), row(2, "c"), row(3, "a"), row(4, "b"), row(5, "c"), row(6, "d")]), [1, 2, 3, 4, 5, 6])
        # les trois derniers seulement : le 5e (c) suit a et b, il garde sa place

    def test_blend_keeps_one_in_four_for_discovery(self):
        self.assertEqual(P.blend([1, 2, 3, 4, 5], ["a", "b"]), [1, 2, 3, "a", 4, 5, "b"])
        self.assertEqual(P.blend([], ["a", "b"]), ["a", "b"])

    def test_what_the_browser_sends_is_checked(self):
        self.assertEqual(P.parse_events("v12.0,c45.3,s7,x9.1,v1.9999,v,c-3.1"), [("view", 12, 0), ("click", 45, 3), ("save", 7, 0)])
        self.assertEqual(len(P.parse_events(",".join(f"v{i}.1" for i in range(100)))), 60)
        self.assertEqual(P.parse_events("v1.900"), [("view", 1, 365)])
        self.assertEqual(P.parse_picks("canape,inconnu,canape,matelas", {"canape", "matelas"}), ["canape", "matelas"])
        known = [f"k{i:02}" for i in range(20)]
        self.assertEqual(P.parse_picks(",".join(known), set(known)), known[:12])

    def test_one_person_in_ten_is_a_control_always_the_same(self):
        share = sum(P.control(u) for u in range(1, 2001)) / 2000
        self.assertTrue(0.07 < share < 0.13, share)
        self.assertEqual([P.control(u) for u in range(50)], [P.control(u) for u in range(50)])


class Reads(unittest.TestCase):
    def setUp(self):
        self.s = Store(DB)
        self.now = self.s.q("SELECT MAX(last_seen) t FROM prices", one=True)["t"] + 3600
        self.api = Api(self.s, config.load({}, public_url="https://deals.test"), clock=lambda: self.now, rules=demo.RULES)

    def tearDown(self):
        self.s.close()

    def get(self, path, session="", **query):
        r = self.api.handle(Request("GET", path, {k: v for k, v in query.items() if v}, {}, session))
        return r.body if r.status == 200 else r

    def post(self, path, body, session=""):
        return self.api.handle(Request("POST", path, {}, body, session))

    def account(self, control=False):
        return account(self.s, self.now, control)

    def deal_category(self):
        """Un rayon qui a au moins deux remises aujourd'hui, sans être celui de la meilleure remise."""
        best = self.s.q("SELECT category FROM catalog WHERE pct > 0 ORDER BY pct DESC LIMIT 1", one=True)["category"]
        return self.s.q("SELECT category FROM catalog WHERE pct > 0 AND category != ? GROUP BY category HAVING COUNT(*) >= 2 "
                        "ORDER BY COUNT(*) DESC, category LIMIT 1", (best,), one=True)["category"]

    def test_forgetting_without_an_account_keeps_nothing(self):
        before = self.s.q("SELECT COUNT(*) n FROM prefs", one=True)["n"]
        r = self.post("/api/r/profile/reset", {})                                 # sans compte : le navigateur oublie seul
        self.assertEqual((r.status, r.body, r.cookie), (200, {"reset_at": None}, None))
        self.assertEqual(self.s.q("SELECT COUNT(*) n FROM prefs", one=True)["n"], before)

    def test_a_new_visitor_sees_the_order_of_before(self):
        today = self.get("/api/r/today")
        self.assertFalse(today["personal"])
        pcts = [p["pct"] for p in today["products"]]
        self.assertEqual(pcts, sorted(pcts, reverse=True))
        self.assertEqual(self.get("/api/r/foryou")["products"], [])
        self.assertFalse(self.get("/api/r/search")["personal"])

    def test_chosen_rayons_lead_without_hiding_the_best_deal(self):
        cat = self.deal_category()
        best = self.get("/api/r/today")["products"][0]
        mine = self.get("/api/r/today", i=cat)
        self.assertTrue(mine["personal"])
        self.assertEqual(mine["products"][0]["category"] in (cat, best["category"]), True)
        self.assertIn(best["id"], [p["id"] for p in mine["products"][:4]])       # le meilleur deal reste dans les 4 premiers
        you = self.get("/api/r/foryou", i=cat)
        self.assertTrue(you["products"] and all(p["category"] == cat for p in you["products"]))
        self.assertEqual(you["taste"]["cats"][0], {"key": cat, "label": you["taste"]["cats"][0]["label"], "chosen": True})
        feed = self.get("/api/r/search", i=cat)
        self.assertTrue(feed["personal"])
        self.assertTrue(all(p["category"] == cat for p in feed["products"][:3]))  # vos rayons d'abord, puis la découverte
        self.assertNotEqual(feed["products"][3]["category"], cat)                 # un sur quatre pris ailleurs
        self.assertEqual(self.get("/api/r/search", q="lit", i=cat)["personal"], False)   # une recherche répond à ce qui est demandé
        self.assertEqual(self.get("/api/r/today", category="lit", i=cat)["personal"], False)
        self.assertEqual(self.get("/api/r/today", q="lit", i=cat)["personal"], False)
        self.assertEqual(self.get("/api/r/search", q="lit", i=cat)["products"], self.get("/api/r/search", q="lit")["products"])

    def test_top_deals_follow_the_rayons_three_places_at_most_and_keep_the_best(self):
        cat = self.deal_category()
        plain = self.get("/api/r/top")["products"]
        mine = self.get("/api/r/top", i=cat)["products"]
        self.assertEqual(len(mine), len(plain))
        self.assertIn(plain[0]["id"], [p["id"] for p in mine])                   # la plus forte remise reste
        first = lambda ps: next((i for i, p in enumerate(ps) if p["category"] == cat), len(ps))
        self.assertLess(first(mine), len(mine))
        self.assertLessEqual(first(mine), first(plain))                           # le rayon choisi monte
        self.assertLessEqual(max(Counter(p["category"] for p in mine).values()), 3)
        self.assertEqual(self.get("/api/r/top", i=cat, v="t")["products"], plain)   # témoin : l'ordre d'avant, à l'identique

    def test_pour_vous_holds_the_deals_and_low_prices_of_your_rayons(self):
        cat = self.deal_category()
        rows = self.s.q("SELECT product_id, pct, price, level, span, usual FROM catalog WHERE category=?", (cat,))
        want = {r["product_id"] for r in rows if r["pct"] > 0 or cheap(r)}
        got = [p["id"] for p in self.get("/api/r/foryou", i=cat)["products"]]
        self.assertEqual(len(got), min(10, len(want)))
        self.assertTrue(set(got) <= want)
        if len(want) <= 10:
            self.assertEqual(set(got), want)

    def test_searches_that_name_a_rayon_or_a_brand_count(self):
        named = lambda q: self.api.profiles._searched([q])
        for q, want in [("aspirateur balai", [("aspirateur", None)]), ("lave-linge 9 kg", [("lave_linge", None)]),
                        ("matelas 160x200", [("matelas", None)]), ("canapé d'angle", [("canape", None)]),   # « d » ne nomme pas Dormea
                        ("robot aspirateur", [("robot_aspirateur", None)]),                                 # le nom le plus précis
                        ("plaque induction", [("plaque_cuisson", None)]),             # à défaut, tous ses mots le nomment
                        ("lave", [("lave_linge", None), ("lave_vaisselle", None)]),
                        ("matelas dormea 140", [("matelas", None), (None, "Dormea")]), ("xyz 9", []), ("d", [])]:
            self.assertEqual(named(q), want, q)
        self.assertEqual(len(self.api.profiles._searched(["matelas"] * 6)), 4)      # les quatre dernières recherches
        taste = self.get("/api/r/profile", recent="lave-linge 9 kg")["taste"]
        self.assertEqual([(c["key"], c["chosen"]) for c in taste["cats"]], [("lave_linge", False)])
        you = self.get("/api/r/foryou", recent="lave-linge 9 kg")["products"]     # les lectures en tiennent compte
        self.assertTrue(you and all(p["category"] == "lave_linge" for p in you))

    def test_what_the_app_understood_is_said_in_a_few_words(self):
        cats = [r["category"] for r in self.s.q("SELECT DISTINCT category FROM catalog ORDER BY category LIMIT 5")]
        prof = self.get("/api/r/profile", i=",".join(cats), v="t")
        self.assertEqual((prof["picks"], prof["learn"], prof["variant"], prof["signed_in"]), (cats, None, "t", False))
        self.assertEqual(prof["taste"], {"cats": [], "brands": [], "personal": False})   # témoin : rien de compris
        taste = self.get("/api/r/profile", i=",".join(cats))["taste"]
        self.assertEqual([c["key"] for c in taste["cats"]], sorted(cats)[:4])   # quatre rayons au plus
        uid, token = self.account()
        for b in [r["brand"] for r in self.s.q("SELECT DISTINCT brand FROM catalog ORDER BY brand LIMIT 4")]:
            self.post("/api/r/brand/follow", {"brand": b, "on": True}, token)
        self.assertEqual(len(self.get("/api/r/profile", token)["taste"]["brands"]), 3)   # trois marques au plus

    def test_a_visit_learns_from_the_fiches_it_opens_and_nothing_is_kept(self):
        cat = self.deal_category()
        ids = [r["product_id"] for r in self.s.q("SELECT product_id FROM catalog WHERE category=? LIMIT 3", (cat,))]
        before = {t: self.s.q(f"SELECT COUNT(*) n FROM {t}", one=True)["n"] for t in ("interests", "prefs", "views", "clicks")}
        taste = self.get("/api/r/profile", p=",".join(f"v{i}.0" for i in ids))
        self.assertEqual([c["key"] for c in taste["taste"]["cats"]][:1], [cat])
        self.assertFalse(taste["taste"]["cats"][0]["chosen"])
        self.assertEqual(self.get("/api/r/foryou", p=",".join(f"v{i}.0" for i in ids))["taste"]["cats"][0]["key"], cat)
        other = self.s.q("SELECT product_id, category FROM catalog WHERE category != ? LIMIT 1", (cat,), one=True)
        glance = self.get("/api/r/profile", p=",".join(f"v{i}.0" for i in ids + [other["product_id"]]))["taste"]["cats"]
        self.assertEqual([c["key"] for c in glance], [cat])                      # une fiche d'un autre rayon : 0,27, sous 0,3
        pid = ids[0]
        firm = self.get("/api/r/profile", p=f"c{pid}.0,v{pid}.0,v{pid}.1")["taste"]   # 2,5 points : rayon vu à 0,8
        self.assertEqual([(c["key"], c["chosen"]) for c in firm["cats"]], [(cat, False)])   # vu, pas choisi
        self.assertEqual(firm["brands"], [{"name": self.s.q("SELECT brand FROM products WHERE id=?", (pid,), one=True)["brand"],
                                           "chosen": False}])                     # marque vue : 0,4
        light = self.get("/api/r/profile", p=f"v{pid}.0,v{pid}.0")["taste"]       # 1 point : marque vue à 0,2, sous 0,3
        self.assertEqual(light["brands"], [])
        self.assertEqual({t: self.s.q(f"SELECT COUNT(*) n FROM {t}", one=True)["n"] for t in before}, before)   # rien de gardé
        control = self.get("/api/r/today", p=",".join(f"v{i}.0" for i in ids), v="t")
        self.assertFalse(control["personal"])                                    # témoin : l'ordre d'avant

    def test_an_account_keeps_its_rayons_and_can_stop_and_reset_learning(self):
        uid, token = self.account()
        self.assertEqual(self.post("/api/r/interests", {"categories": ["inconnu"]}, token).status, 400)
        self.assertEqual(self.post("/api/r/interests", {"categories": ["canape"] * 13}, token).status, 400)
        visitor = self.post("/api/r/interests", {"categories": ["canape"]}, "")         # sans compte : un compte invité
        self.assertEqual((visitor.status, visitor.body, "deals_session=" in visitor.cookie), (200, {"categories": ["canape"]}, True))
        cat = self.deal_category()
        self.assertEqual(self.post("/api/r/interests", {"categories": [cat]}, token).body, {"categories": [cat]})
        prof = self.get("/api/r/profile", token)
        self.assertEqual((prof["picks"], prof["learn"], prof["variant"], prof["signed_in"]), ([cat], True, "p", True))
        self.assertTrue(self.get("/api/r/today", token)["personal"])
        other = self.s.q("SELECT product_id, category FROM catalog WHERE category NOT IN (?, ?) LIMIT 1", (cat, "x"), one=True)
        for _ in range(4):
            self.post("/api/r/view", {"product_id": other["product_id"], "from": "item"}, token)
        seen = lambda: [c["key"] for c in self.get("/api/r/profile", token)["taste"]["cats"]]
        self.assertIn(other["category"], seen())                                 # ses fiches ouvertes comptent
        self.post("/api/r/profile", {"learn": False}, token)
        self.assertNotIn(other["category"], seen())                              # plus si elle refuse
        self.assertIs(self.get("/api/r/profile", token)["learn"], False)
        self.post("/api/r/profile", {"learn": True}, token)
        self.post("/api/r/profile/reset", {}, token)
        self.assertNotIn(other["category"], seen())                              # remise à zéro : les fiches d'avant oubliées
        self.assertEqual(self.get("/api/r/auth/me", token)["variant"], "p")

    def test_chosen_rayons_replace_the_previous_list_in_their_order(self):
        uid, token = self.account()
        self.assertEqual(self.post("/api/r/interests", {"categories": "canape"}, token).body, {"error": "rayons invalides"})
        twelve = [r["category"] for r in self.s.q("SELECT DISTINCT category FROM catalog ORDER BY category LIMIT 12")]
        self.assertEqual(self.post("/api/r/interests", {"categories": twelve}, token).status, 200)   # douze au plus
        a, b = twelve[:2]
        self.post("/api/r/interests", {"categories": [b, a]}, token)
        self.assertEqual(self.get("/api/r/profile", token)["picks"], [b, a])
        self.post("/api/r/interests", {"categories": [a]}, token)
        self.assertEqual(self.get("/api/r/profile", token)["picks"], [a])

    def test_an_account_forgets_after_90_days_but_its_favorites_always_count(self):
        uid, token = self.account()
        cat = self.deal_category()
        old, fav = (self.s.q("SELECT product_id, category FROM catalog WHERE category NOT IN (?, ?) ORDER BY product_id LIMIT 1",
                             (cat, x), one=True) for x in ("x", self.s.q("SELECT category FROM catalog WHERE category != ? "
                                                                          "ORDER BY product_id LIMIT 1", (cat,), one=True)["category"]))
        seen = lambda: [c["key"] for c in self.get("/api/r/profile", token)["taste"]["cats"]]
        for _ in range(20):                                       # 20 fiches il y a 100 jours : 1 point, assez sans la limite
            self.s.x("INSERT INTO views(at, day, user_id, product_id, source) VALUES (?, '2025-01-01', ?, ?, 'item')",
                     (self.now - 100 * 86400, uid, old["product_id"]))
        self.assertNotIn(old["category"], seen())                                 # plus de 90 jours : oublié
        for _ in range(4):
            self.s.x("INSERT INTO views(at, day, user_id, product_id, source) VALUES (?, '2025-01-01', ?, ?, 'item')",
                     (self.now - 10 * 86400, uid, old["product_id"]))
        self.assertIn(old["category"], seen())
        self.post("/api/r/profile", {"learn": False}, token)
        self.post("/api/r/save", {"product_id": fav["product_id"], "on": True}, token)
        self.assertEqual(seen(), [fav["category"]])                               # un favori compte toujours

    def test_a_guest_learns_only_this_visit_unless_asked(self):
        while True:                                                               # un geste : un compte invité (pas témoin, ici)
            token = self.post("/api/r/brand/follow", {"brand": "Nordvik", "on": True}, "").cookie.split(";")[0].split("=", 1)[1]
            if not P.control(self.api.accounts.user(token)):
                break
        cat = self.deal_category()
        ids = [x["product_id"] for x in self.s.q("SELECT product_id FROM catalog WHERE category=? LIMIT 3", (cat,))]
        for i in ids:
            self.post("/api/r/view", {"product_id": i, "from": "item"}, token)
        cats = lambda **q: [c["key"] for c in self.get("/api/r/profile", token, **q)["taste"]["cats"]]
        self.assertEqual(self.get("/api/r/profile", token)["learn"], False)
        self.assertNotIn(cat, cats())                                             # ses fiches gardées ne comptent pas…
        self.assertIn(cat, cats(p=",".join(f"v{i}.0" for i in ids)))              # …celles de la visite, oui
        self.post("/api/r/profile", {"learn": True}, token)
        self.assertIn(cat, cats())                                                # sur demande : son historique

    def test_a_mission_counts_as_a_chosen_rayon(self):
        uid, token = self.account()
        cat = self.deal_category()
        self.assertEqual(self.post("/api/r/missions", {"category": cat, "max_price": 5000}, token).status, 200)
        cats = self.get("/api/r/profile", token)["taste"]["cats"]
        self.assertEqual((cats[0]["key"], cats[0]["chosen"]), (cat, True))
        uid, token = self.account()                                               # une mission sur un produit : son rayon, sa marque
        r = self.s.q("SELECT product_id, category, brand FROM catalog WHERE pct > 0 ORDER BY product_id LIMIT 1", one=True)
        self.assertEqual(self.post("/api/r/missions", {"product_id": r["product_id"], "max_price": 5000}, token).status, 200)
        taste = self.get("/api/r/profile", token)["taste"]
        self.assertIn({"key": r["category"], "label": taste["cats"][0]["label"], "chosen": True}, taste["cats"])
        self.assertEqual(taste["brands"], [{"name": r["brand"], "chosen": True}])
        uid, token = self.account()                                               # une mission sur une marque
        self.post("/api/r/missions", {"brand": r["brand"].lower(), "max_price": 5000}, token)
        self.assertEqual(self.get("/api/r/profile", token)["taste"]["brands"], [{"name": r["brand"], "chosen": True}])

    def test_a_control_account_sees_the_order_of_before_and_the_measures_tell_them_apart(self):
        uid, token = self.account(control=True)
        self.post("/api/r/interests", {"categories": [self.deal_category()]}, token)
        self.assertFalse(self.get("/api/r/today", token)["personal"])
        self.assertEqual(self.get("/api/r/foryou", token)["products"], [])       # ni « pour vous »
        self.assertEqual(self.get("/api/r/auth/me", token)["variant"], "t")
        pid = self.get("/api/r/today")["products"][0]["id"]
        offer = self.s.q("SELECT offer_id FROM catalog WHERE product_id=?", (pid,), one=True)["offer_id"]
        self.post("/api/r/view", {"product_id": pid, "from": "foryou", "v": "t"}, token)
        self.post("/api/r/view", {"product_id": pid, "from": "home", "v": "zz"})
        self.api.handle(Request("GET", f"/api/r/out/{offer}", {"from": "foryou", "v": "zz"}))
        self.assertIsNone(self.s.q("SELECT variant FROM clicks ORDER BY id DESC LIMIT 1", one=True)["variant"])
        self.api.handle(Request("GET", f"/api/r/out/{offer}", {"from": "foryou", "v": "p"}))
        views = self.s.q("SELECT source, variant FROM views ORDER BY id DESC LIMIT 2")
        self.assertEqual(views, [{"source": "home", "variant": None}, {"source": "foryou", "variant": "t"}])
        self.assertEqual(self.s.q("SELECT source, variant FROM clicks ORDER BY id DESC LIMIT 1", one=True), {"source": "foryou", "variant": "p"})
        by = self.api.activity.metrics()["by_variant"]
        self.assertIn("t · foryou", by)
        self.assertIn("p · foryou", by)
        self.post("/api/r/view", {"product_id": pid, "from": "room"})                 # une pièce de l'accueil
        self.assertEqual(self.s.q("SELECT source FROM views ORDER BY id DESC LIMIT 1", one=True)["source"], "room")


class Shaped(unittest.TestCase):
    """Un catalogue façonné (la démo, remises réécrites) où les goûts doivent se voir : quatre rayons riches en remises
    de 27 à 30 %, la plus forte remise du jour (40 %) ailleurs, un prix bas sans remise, un rayon aux petites remises."""

    @classmethod
    def setUpClass(cls):
        path = Path(tempfile.mkdtemp(), "shaped.sqlite")
        shutil.copy(DB, path)
        cls.s = s = Store(path)
        s.x("UPDATE catalog SET pct=0, was=NULL, level='usual', span=10")
        ids = lambda cat: [r["product_id"] for r in s.q("SELECT product_id FROM catalog WHERE category=? ORDER BY product_id", (cat,))]
        for cat, pcts in (("matelas", [30, 29, 28, 27]), ("canape", [30, 29, 28]), ("lit", [30, 29, 28]), ("table", [30, 29, 28]),
                          ("four", [40]), ("sommier", [10, 9, 8])):
            for pid, pct in zip(ids(cat), pcts):
                s.x("UPDATE catalog SET pct=?, was=ROUND(price / (1 - ? / 100.0)) WHERE product_id=?", (pct, pct, pid))
        cls.best = ids("four")[0]
        cls.cheap = ids("matelas")[5]                        # prix bas sans remise : au plus bas depuis 90 jours, 23 % sous l'habitude
        s.x("UPDATE catalog SET level='lowest', span=90, usual=ROUND(price * 1.3) WHERE product_id=?", (cls.cheap,))
        deals = s.q("SELECT product_id, brand FROM catalog WHERE category='matelas' AND pct > 0 ORDER BY pct DESC")
        cls.other = next(r for r in deals if r["brand"] != deals[0]["brand"])   # la meilleure remise d'une autre marque
        cls.now = s.q("SELECT MAX(last_seen) t FROM prices", one=True)["t"] + 3600
        cls.api = Api(s, config.load({}, public_url="https://deals.test"), clock=lambda: cls.now, rules=demo.RULES)

    @classmethod
    def tearDownClass(cls):
        cls.s.close()

    def get(self, path, session="", **query):
        return self.api.handle(Request("GET", path, query, {}, session)).body["products"]

    def test_your_rayons_lead_the_top_deals_and_the_best_deal_of_the_day_stays(self):
        plain = self.get("/api/r/top")
        self.assertEqual(plain[0]["id"], self.best)
        one = self.get("/api/r/top", i="matelas")
        self.assertEqual([p["category"] for p in one[:2]], ["matelas", "matelas"])   # vos rayons en tête
        self.assertEqual(Counter(p["category"] for p in one)["matelas"], 3)            # quatre remises et un prix bas : trois places
        four = self.get("/api/r/top", i="matelas,canape,lit,table")                   # douze remises de vos rayons au-dessus de 40 %
        self.assertEqual([p["id"] for p in four if p["pct"] > 0][3], self.best)        # la 4e remise : le meilleur deal du jour
        self.assertLessEqual(max(Counter(p["category"] for p in four).values()), 3)

    def test_pour_vous_has_the_low_prices_of_your_rayons_and_ten_cards_at_most(self):
        mine = self.get("/api/r/foryou", i="matelas")
        self.assertIn(self.cheap, [p["id"] for p in mine])
        self.assertEqual({p["category"] for p in mine}, {"matelas"})
        self.assertEqual(len(self.get("/api/r/foryou", i="matelas,canape,lit,table")), 10)

    def test_the_feed_never_floods_with_one_rayon(self):
        feed = self.get("/api/r/search", i="matelas,sommier")[:12]
        for i in range(len(feed) - 3):
            self.assertLessEqual(max(Counter(p["category"] for p in feed[i:i + 4]).values()), 2, [p["category"] for p in feed])

    def test_a_filter_answers_what_is_asked_and_a_followed_brand_still_counts(self):
        self.assertEqual(self.get("/api/r/search", off="1", i="matelas"), self.get("/api/r/search", off="1"))
        uid, token = account(self.s, self.now)
        self.api.handle(Request("POST", "/api/r/brand/follow", {}, {"brand": self.other["brand"], "on": True}, token))
        self.assertEqual(self.get("/api/r/today", token, category="matelas")[0]["id"], self.other["product_id"])   # × 1,5 : devant 30 %


if __name__ == "__main__":
    unittest.main()
