"""Serveur HTTP de l'app : la page (web/app.html) et l'API /api/r/. Bibliothèque standard.

Garde-fous : corps de requête limité à 16 Ko (longueur invalide refusée) ; connexion inactive fermée après 30 s ;
session lue seulement dans le cookie ; adresse IP du client prise dans X-Forwarded-For uniquement quand la connexion
vient du proxy local (Caddy) ; en-têtes de sécurité, HTTPS imposé au navigateur (HSTS) quand l'adresse publique est en
https ; aucune autre route que la page, /api/r/ et /robot (ce que fait le robot qui lit les enseignes, et qui joindre).
"""
import json
from html import escape
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl

from .accounts import COOKIE
from .api import Request

APP = Path(__file__).resolve().parent.parent / "web" / "app.html"
ROBOT = Path(__file__).resolve().parent.parent / "web" / "robot.html"
HSTS = "max-age=31536000"
MAX_BODY = 16 * 1024
IDLE_S = 30                    # un client lent ou muet ne garde pas un fil indéfiniment
HEADERS = {"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "same-origin"}


def make_server(api, store, settings, host="127.0.0.1", port=8000):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version, sys_version = "PromoCentral", ""
        timeout = IDLE_S
        head = False                   # requête HEAD : les en-têtes d'un GET, sans le corps

        def log_message(self, *a):
            pass

        def send(self, status, body=b"", ctype="application/json; charset=utf-8", location=None, cookie=None, cache="no-store"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, default=str).encode()
            self.send_response(status)
            for k, v in HEADERS.items():
                self.send_header(k, v)
            if settings.public_url.startswith("https://"):
                self.send_header("Strict-Transport-Security", HSTS)
            self.send_header("Cache-Control", cache)
            if location:
                self.send_header("Location", location)
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if not self.head:
                self.wfile.write(data)

        def client_ip(self):
            peer = self.client_address[0]
            fwd = self.headers.get("X-Forwarded-For")
            if fwd and settings.trust_proxy and peer in ("127.0.0.1", "::1"):
                return fwd.split(",")[-1].strip()
            return peer

        def session(self):
            try:
                jar = SimpleCookie(self.headers.get("Cookie", ""))
            except CookieError:
                return ""
            return jar[COOKIE].value if COOKIE in jar else ""

        def handle_any(self, method):
            path, _, qs = self.path.partition("?")
            if path == "/robot" and method == "GET":
                page = ROBOT.read_text(encoding="utf-8").replace("{agent}", escape(settings.user_agent)).replace(
                    "{contact}", escape(settings.legal_contact or "l'adresse indiquée dans son nom (User-Agent)"))
                return self.send(200, page.encode(), "text/html; charset=utf-8", cache="public, max-age=3600")
            if not path.startswith("/api/"):
                if path not in ("/", "/index.html"):
                    return self.send(404, {"error": "Introuvable"})
                if method != "GET":
                    return self.send(405, {"error": "Méthode non permise"})
                return self.send(200, APP.read_bytes(), "text/html; charset=utf-8", cache="no-cache")
            raw_len = self.headers.get("Content-Length") or "0"
            if not raw_len.isdigit():
                self.close_connection = True
                return self.send(400, {"error": "Longueur de requête invalide"})
            n = int(raw_len)
            if n > MAX_BODY:
                self.close_connection = True
                return self.send(413, {"error": "Requête trop volumineuse"})
            try:
                body = json.loads(self.rfile.read(n)) if n else {}
            except (json.JSONDecodeError, UnicodeDecodeError):
                return self.send(400, {"error": "JSON invalide"})
            if not isinstance(body, dict):
                return self.send(400, {"error": "JSON invalide"})
            res = api.handle(Request(method, path, dict(parse_qsl(qs, keep_blank_values=True)), body, self.session(), self.client_ip()))
            self.send(res.status, b"" if res.body is None else res.body, location=res.location, cookie=res.cookie)

        def do_GET(self):
            self.head = False
            self.handle_any("GET")

        def do_POST(self):
            self.head = False
            self.handle_any("POST")

        def do_HEAD(self):
            """HEAD (RFC 9110 : tout serveur le doit ; curl -I, sondes extérieures) : les en-têtes d'un GET, sans le corps,
            là où un GET ne change rien — la page, /robot, l'état pour la sonde. Ailleurs 405 : un clic sortant ou un lien
            de connexion ne se rejouent pas sur un HEAD (aperçus de liens, robots)."""
            self.head = True
            if self.path.partition("?")[0] in ("/", "/index.html", "/robot", "/api/r/health"):
                return self.handle_any("GET")
            return self.send(405, {"error": "Méthode non permise"})

        def finish(self):
            try:
                super().finish()
            finally:
                store.release()        # la connexion SQLite de ce fil se ferme avec lui

    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    return srv
