"""Connexion et surface publique, par HTTP : lien magique à usage unique, session par cookie seulement, limites d'envoi
(adresse, IP, plafond quotidien), isolement des comptes, rien d'autre d'exposé que l'app et /api/r/."""
import email
import email.policy
import json
import socket
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from deals import config
from deals.accounts import SmtpOutbox
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
        self.assertEqual(self.raw("GET", f"/api/r/saves?_session={cookie}")[0], 401)   # la session vient du cookie, pas de l'adresse
        self.assertEqual(self.raw("POST", "/api/r/auth/logout", {}, cookie=cookie)[0], 200)
        self.assertEqual(self.raw("GET", "/api/r/auth/me", cookie=cookie)[0], 401)
        self.assertEqual(self.raw("GET", "/api/r/auth/verify?token=nimporte")[1]["Location"], "/?auth=expired")
        self.assertEqual(self.raw("POST", "/api/r/auth/request", {"email": "pas-un-mail"})[0], 400)

    def test_send_limits(self):
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
        for email in ("zoe@test.local", "max@test.local"):
            self.api.accounts.request_link(email)
            sessions.append(self.api.accounts.verify(self.link().split("token=")[1])[1].split(";")[0].split("=", 1)[1])
        self.assertEqual(self.raw("POST", "/api/r/brand/follow", {"brand": "Bosch"}, cookie=sessions[0])[0], 200)
        self.assertEqual(json.loads(self.raw("GET", "/api/r/follows", cookie=sessions[1])[2])["brands"], [])
        self.assertEqual(self.raw("POST", "/api/r/brand/follow", {"brand": "Bosch"})[0], 401)

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
        self.assertEqual((msg["To"], msg["Subject"]), ("lea@exemple.fr", "Votre lien de connexion Deals"))
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
