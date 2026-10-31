"""Comptes et surface publique, par HTTP : sans e-mail, le premier geste qui garde quelque chose crée un compte invité
(cookie) ; l'adresse, facultative, s'y rattache par un lien magique à usage unique, ou y verse l'invité si le compte
existe ; « effacer mes données » ; session par cookie seulement, limites d'envoi (adresse, IP, plafond quotidien) et de
création d'invités, isolement des comptes, rien d'autre d'exposé que l'app et /api/r/."""
import email
import email.policy
import json
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from deals import config
from deals.accounts import GUESTS_PER_IP_HOUR, SmtpOutbox, expire_guests
from deals.api import Api
from deals.errors import Unavailable
from deals.store import Store
from deals.web import make_server


class Accounts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = Store(Path(tempfile.mkdtemp(), "t.sqlite"))
        cls.api = Api(cls.store, config.load({}, mails_per_day=30))
        cls.srv = make_server(cls.api, cls.store, config.load({}), port=0)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.store.close()

    def raw(self, method, path, body=None, cookie=None, headers=None):
        h = {"Content-Type": "application/json", **(headers or {})}
        if cookie:
            h["Cookie"] = f"deals_session={cookie}"
        data = body if isinstance(body, bytes) else json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, method=method, data=data, headers=h)
        opener = urllib.request.build_opener(type("NoRedirect", (urllib.request.HTTPRedirectHandler,), {"redirect_request": lambda *a: None}))
        try:
            with opener.open(req) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.headers, e.read()

    def link(self):
        return self.api.accounts.outbox.sent[-1][1]

    def test_a_mission_launched_before_login_waits_on_the_server(self):
        outbox = self.api.accounts.outbox
        before = len(outbox.sent)
        st = self.raw("POST", "/api/r/auth/request", {"email": "noa@test.local", "mission": {"category": "aspirateur"}})[0]
        self.assertEqual((st, len(outbox.sent)), (400, before))              # sans prix : refusée, et aucun e-mail
        mission = {"category": "aspirateur", "features": ["balai"], "max_price": 300}
        self.assertEqual(self.raw("POST", "/api/r/auth/request", {"email": "noa@test.local", "mission": mission})[0], 200)
        self.assertEqual(outbox.mails[-1][1]["Subject"], "Confirmez votre mission : Aspirateur balai · 300 € max")
        token = self.link().split("token=")[1]
        st, h, _ = self.raw("GET", f"/api/r/auth/verify?token={token}")       # ouvert sur un autre appareil : rien dans le navigateur
        self.assertTrue(h["Location"].startswith("/?mission="), h["Location"])
        cookie = h["Set-Cookie"].split(";")[0].split("=", 1)[1]
        mine = json.loads(self.raw("GET", "/api/r/missions", cookie=cookie)[2])["missions"]
        self.assertEqual([(m["id"], m["label"]) for m in mine], [(int(h["Location"].split("=")[1]), "Aspirateur balai · 300 € max")])
        self.raw("POST", "/api/r/auth/request", {"email": "noa@test.local"})  # une simple connexion ensuite : rien ne s'ajoute
        st, h, _ = self.raw("GET", f"/api/r/auth/verify?token={self.link().split('token=')[1]}")
        self.assertEqual((h["Location"], outbox.mails[-1][1]["Subject"]), ("/", "Votre lien de connexion Promo Central"))
        self.assertEqual(len(json.loads(self.raw("GET", "/api/r/missions", cookie=cookie)[2])["missions"]), 1)

    def test_magic_link(self):
        st, _, body = self.raw("POST", "/api/r/auth/request", {"email": "Inconnu@Test.local"})
        self.assertEqual((st, json.loads(body)["ok"]), (200, True))           # même réponse qu'un compte existe ou non
        token = self.link().split("token=")[1]
        st, h, _ = self.raw("GET", f"/api/r/auth/verify?token={token}")
        self.assertEqual((st, h["Location"]), (302, "/"))
        self.assertIn("HttpOnly", h["Set-Cookie"])
        self.assertIn("SameSite=Lax", h["Set-Cookie"])
        cookie = h["Set-Cookie"].split(";")[0].split("=", 1)[1]
        st, h2, _ = self.raw("GET", f"/api/r/auth/verify?token={token}")       # usage unique
        self.assertEqual((st, h2["Location"], h2.get("Set-Cookie")), (302, "/?auth=expired", None))
        self.assertEqual(json.loads(self.raw("GET", "/api/r/auth/me", cookie=cookie)[2])["email"], "inconnu@test.local")
        st, _, body = self.raw("GET", f"/api/r/saves?_session={cookie}")             # la session vient du cookie, pas de l'adresse
        self.assertEqual((st, json.loads(body)["products"]), (200, []))
        self.assertEqual(self.raw("POST", "/api/r/auth/logout", {}, cookie=cookie)[0], 200)
        self.assertEqual(self.raw("GET", "/api/r/auth/me", cookie=cookie)[0], 401)
        self.assertEqual(self.raw("GET", "/api/r/auth/verify?token=nimporte")[1]["Location"], "/?auth=expired")
        self.assertEqual(self.raw("POST", "/api/r/auth/request", {"email": "pas-un-mail"})[0], 400)

    def test_send_limits(self):
        self.store.x("DELETE FROM login_links")                               # les liens des autres tests ne comptent pas ici
        codes = [self.raw("POST", "/api/r/auth/request", {"email": "spam@test.local"})[0] for _ in range(6)]
        self.assertEqual(codes, [200] * 5 + [429])                             # 5 par adresse et par heure
        ip = {"X-Forwarded-For": "203.0.113.7"}                                # derrière Caddy : l'IP du client
        codes = [self.raw("POST", "/api/r/auth/request", {"email": f"u{i}@test.local"}, headers=ip)[0] for i in range(21)]
        self.assertEqual(codes[-2:], [200, 429])                               # 20 par adresse IP et par heure
        codes = [self.raw("POST", "/api/r/auth/request", {"email": f"v{i}@test.local"}, headers={"X-Forwarded-For": f"198.51.100.{i}"})[0]
                 for i in range(10)]
        self.assertIn(429, codes)                                              # plafond quotidien global (30 ici)

    def test_accounts_are_isolated(self):
        sessions = []
        for addr in ("zoe@test.local", "max@test.local"):
            self.api.accounts.request_link(addr)
            sessions.append(self.api.accounts.verify(self.link().split("token=")[1])[1].split(";")[0].split("=", 1)[1])
        self.assertEqual(self.raw("POST", "/api/r/brand/follow", {"brand": "Bosch"}, cookie=sessions[0])[0], 200)
        self.assertEqual(json.loads(self.raw("GET", "/api/r/follows", cookie=sessions[1])[2])["brands"], [])
        st, h, _ = self.raw("POST", "/api/r/brand/follow", {"brand": "Bosch"})       # sans compte : un compte invité, à part
        guest = h["Set-Cookie"].split(";")[0].split("=", 1)[1]
        self.assertEqual(json.loads(self.raw("GET", "/api/r/follows", cookie=guest)[2])["brands"], ["Bosch"])
        self.assertEqual(json.loads(self.raw("GET", "/api/r/follows", cookie=sessions[1])[2])["brands"], [])

    def guest(self, path="/api/r/brand/follow", body=None, headers=None):
        st, h, _ = self.raw("POST", path, body or {"brand": "Ostra"}, headers=headers)
        return st, (h.get("Set-Cookie") or "").split(";")[0].split("=", 1)[-1], h.get("Set-Cookie") or ""

    def test_keeping_things_needs_no_email(self):
        self.assertEqual(self.raw("GET", "/api/r/auth/me")[0], 401)                    # simple visite : aucun compte
        self.assertEqual(json.loads(self.raw("GET", "/api/r/missions")[2]), {"missions": [], "reached": 0, "fresh": 0})
        st, cookie, raw = self.guest("/api/r/brand/follow", {"brand": "Nordvik"})
        self.assertEqual(st, 200)
        self.assertIn("HttpOnly", raw)
        self.assertIn(f"Max-Age={365 * 24 * 3600}", raw)                               # la seule clé d'un invité : un an
        me = json.loads(self.raw("GET", "/api/r/auth/me", cookie=cookie)[2])
        self.assertEqual((me["email"], me["guest"], me["variant"] in ("p", "t")), (None, True, True))
        before = self.store.q("SELECT expires_at FROM sessions WHERE user_id=?", (self.api.accounts.user(cookie),), one=True)["expires_at"]
        again = self.raw("POST", "/api/r/brand/follow", {"brand": "Aurel"}, cookie=cookie)[1]["Set-Cookie"]
        self.assertEqual(again.split(";")[0].split("=", 1)[1], cookie)                  # le même compte, sa clé repart pour un an
        self.assertIn(f"Max-Age={365 * 24 * 3600}", again)
        self.assertGreater(self.store.q("SELECT expires_at FROM sessions WHERE user_id=?", (self.api.accounts.user(cookie),),
                                        one=True)["expires_at"], before)
        self.assertEqual(json.loads(self.raw("GET", "/api/r/follows", cookie=cookie)[2])["brands"], ["Aurel", "Nordvik"])
        made = json.loads(self.raw("POST", "/api/r/missions", {"category": "lave_linge", "max_price": 900}, cookie=cookie)[2])
        self.assertEqual(json.loads(self.raw("GET", "/api/r/missions", cookie=cookie)[2])["missions"][0]["id"], made["id"])
        prof = json.loads(self.raw("GET", "/api/r/profile", cookie=cookie)[2])
        self.assertEqual((prof["guest"], prof["email"], prof["learn"]), (True, None, False))   # n'apprend des fiches que sur demande

    def test_guest_creation_is_limited_per_address(self):
        ip = {"X-Forwarded-For": "192.0.2.44"}
        codes = [self.guest(headers=ip)[0] for _ in range(GUESTS_PER_IP_HOUR + 1)]
        self.assertEqual((GUESTS_PER_IP_HOUR, codes[-2:]), (100, [200, 429]))          # 100 comptes invités par IP et par heure
        before = self.store.q("SELECT COUNT(*) n FROM users", one=True)["n"]
        st, cookie, _ = self.guest("/api/r/save", {"product_id": 999999})            # le geste échoue : aucun compte ne reste
        self.assertEqual((st, cookie, self.store.q("SELECT COUNT(*) n FROM users", one=True)["n"]), (404, "", before))

    def test_an_email_attaches_to_the_guest_or_receives_it(self):
        _, cookie, _ = self.guest("/api/r/brand/follow", {"brand": "Lumen"})
        uid = self.api.accounts.user(cookie)
        self.raw("POST", "/api/r/auth/request", {"email": "ines@test.local"}, cookie=cookie)
        st, h, _ = self.raw("GET", f"/api/r/auth/verify?token={self.link().split('token=')[1]}")
        fresh = h["Set-Cookie"].split(";")[0].split("=", 1)[1]
        self.assertEqual((self.api.accounts.user(fresh), self.api.accounts.user(cookie)), (uid, uid))   # le même compte, partout
        self.assertEqual(json.loads(self.raw("GET", "/api/r/auth/me", cookie=cookie)[2])["email"], "ines@test.local")
        self.assertEqual(json.loads(self.raw("GET", "/api/r/follows", cookie=fresh)[2])["brands"], ["Lumen"])
        self.raw("POST", "/api/r/missions", {"category": "matelas"}, cookie=cookie)
        _, other, _ = self.guest("/api/r/brand/follow", {"brand": "Varenne"})          # un autre invité, même adresse : il s'y verse
        self.raw("POST", "/api/r/missions", {"category": "matelas"}, cookie=other)      # la même recherche des deux côtés : une seule
        self.raw("POST", "/api/r/brand/follow", {"brand": "Lumen"}, cookie=other)       # déjà suivie par le compte : sans doublon
        self.store.x("INSERT INTO views(at, day, user_id, product_id, source) VALUES (0, '2026-01-01', ?, 1, 'item')",
                     (self.api.accounts.user(other),))
        self.raw("POST", "/api/r/auth/request", {"email": "ines@test.local"}, cookie=other)
        self.raw("GET", f"/api/r/auth/verify?token={self.link().split('token=')[1]}")
        self.assertEqual(self.api.accounts.user(other), uid)                          # l'appareil de l'invité reste connecté
        self.assertEqual(json.loads(self.raw("GET", "/api/r/follows", cookie=cookie)[2])["brands"], ["Lumen", "Varenne"])
        self.assertEqual([m["label"] for m in json.loads(self.raw("GET", "/api/r/missions", cookie=cookie)[2])["missions"]], ["Matelas"])
        self.assertEqual(self.store.q("SELECT COUNT(*) n FROM users WHERE email IS NULL AND id NOT IN (SELECT user_id FROM sessions)",
                                      one=True)["n"], 0)                              # l'invité versé n'existe plus
        self.assertEqual(self.store.q("SELECT user_id FROM views ORDER BY id DESC LIMIT 1", one=True)["user_id"], uid)   # ses fiches vues aussi

    def test_an_address_is_given_once(self):
        """Un invité qui demande deux liens, pour deux adresses : le premier ouvert lui donne la sienne ; le second ne la
        change pas et ne verse pas ce compte ailleurs (c'est un compte, plus un invité)."""
        _, cookie, _ = self.guest("/api/r/brand/follow", {"brand": "Brava"})
        uid = self.api.accounts.user(cookie)
        links = []
        for addr in ("lea@test.local", "lea.pro@test.local"):
            self.raw("POST", "/api/r/auth/request", {"email": addr}, cookie=cookie)
            links.append(self.link().split("token=")[1])
        for token in links:
            self.raw("GET", f"/api/r/auth/verify?token={token}")
        self.assertEqual(self.store.q("SELECT email FROM users WHERE id=?", (uid,), one=True)["email"], "lea@test.local")
        pro = self.store.q("SELECT id FROM users WHERE email='lea.pro@test.local'", one=True)["id"]
        self.assertNotEqual(pro, uid)
        self.assertEqual(json.loads(self.raw("GET", "/api/r/follows", cookie=cookie)[2])["brands"], ["Brava"])

    def test_only_a_guest_key_is_renewed(self):
        self.api.accounts.request_link("vera@test.local")
        cookie = self.api.accounts.verify(self.link().split("token=")[1])[1].split(";")[0].split("=", 1)[1]
        uid = self.api.accounts.user(cookie)
        before = self.store.q("SELECT expires_at FROM sessions WHERE user_id=?", (uid,), one=True)["expires_at"]
        st, h, _ = self.raw("POST", "/api/r/brand/follow", {"brand": "Lumen"}, cookie=cookie)
        self.assertEqual((st, h.get("Set-Cookie")), (200, None))                      # un compte avec adresse garde sa session
        self.assertEqual(self.store.q("SELECT expires_at FROM sessions WHERE user_id=?", (uid,), one=True)["expires_at"], before)

    def test_a_guest_nobody_can_open_is_erased_at_night(self):
        _, cookie, _ = self.guest("/api/r/brand/follow", {"brand": "Aurel"})
        uid = self.api.accounts.user(cookie)
        self.store.x("INSERT INTO views(at, day, user_id, product_id, source) VALUES (0, '2026-01-01', ?, 1, 'item')", (uid,))
        self.api.accounts.request_link("ugo@test.local")
        self.api.accounts.verify(self.link().split("token=")[1])
        ugo = self.store.q("SELECT id FROM users WHERE email='ugo@test.local'", one=True)["id"]
        self.store.x("DELETE FROM sessions WHERE user_id=?", (ugo,))                    # un compte avec adresse, sans session : il reste
        now = time.time()
        self.assertEqual(expire_guests(self.store, now), 0)
        self.store.x("UPDATE sessions SET expires_at=? WHERE user_id=?", (now - 1, uid))  # un an sans geste qui garde
        self.assertEqual(expire_guests(self.store, now), 1)
        self.assertIsNone(self.store.q("SELECT id FROM users WHERE id=?", (uid,), one=True))
        self.assertIsNotNone(self.store.q("SELECT id FROM users WHERE id=?", (ugo,), one=True))
        self.assertEqual(self.store.q("SELECT COUNT(*) n FROM views WHERE user_id=?", (uid,), one=True)["n"], 0)   # mesure anonyme
        self.assertEqual(self.store.q("SELECT COUNT(*) n FROM follows WHERE user_id=?", (uid,), one=True)["n"], 0)

    def test_forgetting_erases_the_account(self):
        _, cookie, _ = self.guest("/api/r/brand/follow", {"brand": "Helio"})
        uid = self.api.accounts.user(cookie)
        self.store.x("INSERT INTO views(at, day, user_id, product_id, source) VALUES (0, '2026-01-01', ?, 1, 'item')", (uid,))
        st, h, body = self.raw("POST", "/api/r/account/delete", {}, cookie=cookie)
        self.assertEqual((st, json.loads(body), "Max-Age=0" in h["Set-Cookie"]), (200, {"ok": True}, True))
        self.assertEqual(self.raw("GET", "/api/r/auth/me", cookie=cookie)[0], 401)
        self.assertEqual(self.store.q("SELECT COUNT(*) n FROM follows WHERE user_id=?", (uid,), one=True)["n"], 0)
        self.assertEqual(self.store.q("SELECT user_id FROM views ORDER BY id DESC LIMIT 1", one=True)["user_id"], None)   # mesure anonyme
        self.assertEqual(self.raw("POST", "/api/r/account/delete", {})[0], 401)

    def test_public_surface(self):
        self.assertIn(b"/api/r/", self.raw("GET", "/")[2])                    # l'app
        for path in ("/admin", "/api/offers", "/api/run", "/api/stream", "/api/admin/metrics", "/robots"):
            self.assertEqual(self.raw("GET", path)[0], 404, path)
        self.assertEqual(self.raw("POST", "/api/r/auth/request", b"x" * 20000)[0], 413)   # corps limité
        self.assertEqual(self.raw("POST", "/api/r/auth/request", b"[1,2]")[0], 400)
        with socket.create_connection(("127.0.0.1", self.srv.server_port), timeout=5) as c:   # longueur négative : refus immédiat
            c.sendall(b"POST /api/r/auth/request HTTP/1.1\r\nHost: x\r\nContent-Length: -1\r\n\r\n")
            self.assertTrue(c.recv(64).startswith(b"HTTP/1.1 400"))
        st, h, _ = self.raw("GET", "/api/r/categories")
        self.assertEqual((st, h["X-Content-Type-Options"], h["Cache-Control"]), (200, "nosniff", "no-store"))



class FakeSMTP:
    def __init__(self):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.messages, self.auth = [], []
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        conn, _ = self.sock.accept()
        f = conn.makefile("rb")
        send = lambda line: conn.sendall((line + "\r\n").encode())
        send("220 fake")
        data, in_data = [], False
        for raw in f:
            line = raw.decode().rstrip("\r\n")
            if in_data:
                if line == ".":
                    self.messages.append("\r\n".join(data)); data, in_data = [], False; send("250 ok")
                else:
                    data.append(line[1:] if line.startswith("..") else line)
                continue
            cmd = line.split(" ", 1)[0].upper()
            if cmd == "EHLO":
                conn.sendall(b"250-fake\r\n250 AUTH PLAIN\r\n")
            elif cmd == "AUTH":
                self.auth.append(line); send("235 ok")
            elif cmd == "DATA":
                in_data = True; send("354 go")
            elif cmd == "QUIT":
                send("221 bye"); break
            else:
                send("250 ok")
        conn.close()
        self.sock.close()


class SmtpSend(unittest.TestCase):
    """Envoi réel du lien par SMTP, contre un faux serveur local (protocole minimal, sans TLS)."""

    def test_link_is_sent_by_smtp(self):
        srv = FakeSMTP()
        box = SmtpOutbox(config.load({"DEALS_SMTP_HOST": "127.0.0.1", "DEALS_SMTP_PORT": str(srv.port), "DEALS_SMTP_TLS": "none",
                                      "DEALS_SMTP_USER": "u", "DEALS_SMTP_PASSWORD": "p", "DEALS_MAIL_FROM": "Deals <bonjour@deals.test>"}))
        link = "https://deals.test/api/r/auth/verify?token=abc123"
        box.send("lea@exemple.fr", link)
        msg = email.message_from_string(srv.messages[0], policy=email.policy.default)
        self.assertEqual((msg["To"], msg["Subject"]), ("lea@exemple.fr", "Votre lien de connexion Promo Central"))
        self.assertIn(link, msg.get_body(("plain",)).get_content())
        self.assertIn(link, msg.get_body(("html",)).get_content())
        self.assertTrue(srv.auth)

    def test_misconfiguration_stops_at_startup(self):
        with self.assertRaisesRegex(ValueError, "DEALS_SMTP_TLS"):            # systemd garde un commentaire de fin de ligne
            config.load({"DEALS_SMTP_TLS": "starttls          # starttls (587) | ssl (465)"})

    def test_unreachable_server_gives_clear_error(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        box = SmtpOutbox(config.load({"DEALS_SMTP_HOST": "127.0.0.1", "DEALS_SMTP_PORT": str(port), "DEALS_SMTP_TLS": "none"}))
        with self.assertRaises(Unavailable) as cm:
            box.send("lea@exemple.fr", "https://x/verify?token=t")
        self.assertEqual(cm.exception.status, 503)


if __name__ == "__main__":
    unittest.main()
