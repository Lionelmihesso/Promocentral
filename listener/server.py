"""API JSON + flux temps réel (Server-Sent Events) + tableau de bord. Bibliothèque standard."""
import json
from urllib.parse import unquote_plus
import queue
import re
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
SESSION_COOKIE = "deals_session"   # même nom que radar/accounts.py


def routes(L):
    return [
        ("GET", r"/api/offers", lambda b, q: L.offers()),
        ("POST", r"/api/offers", lambda b, q: {"id": L.track(b.get("url"), int(b.get("priority", 2)), b.get("merchant"))}),
        ("POST", r"/api/offers/(\d+)/check", lambda b, q, i: L.check(int(i))),
        ("POST", r"/api/offers/(\d+)/pause", lambda b, q, i: (L.q("UPDATE offers SET status='paused' WHERE id=?", (int(i),)), {"ok": True})[1]),
        ("POST", r"/api/diagnose", lambda b, q: L.diagnose(b["url"])),
        ("GET", r"/api/products", lambda b, q: L.products(q.get("category"))),
        ("GET", r"/api/products/(\d+)/history", lambda b, q, i: L.history(int(i), int(q.get("days", 365)))),
        ("GET", r"/api/products/(\d+)/intelligence", lambda b, q, i: L.intelligence(int(i)) or _nf()),
        ("GET", r"/api/facts", lambda b, q: L.facts(_int(q.get("product_id")), _int(q.get("offer_id")), int(q.get("limit", 200)))),
        ("GET", r"/api/signals", lambda b, q: L.signals(active=q.get("all") != "1", type_=q.get("type"), product_id=_int(q.get("product_id")))),
        ("GET", r"/api/watches", lambda b, q: L.watches()),
        ("POST", r"/api/watches", lambda b, q: {"id": L.add_watch(b)}),
        ("GET", r"/api/patterns", lambda b, q: L.patterns(q.get("by", "category"))),
        ("GET", r"/api/metrics", lambda b, q: L.metrics()),
        ("GET", r"/api/events", lambda b, q: L.events(int(q.get("since", 0)), int(q.get("limit", 200)), q.get("type"))),
        ("GET", r"/api/health", lambda b, q: L.health(int(q.get("hours", 24)))),
        ("POST", r"/api/rules", lambda b, q: (L.set_rules(b["host"], b["rules"]), {"ok": True})[1]),
        ("POST", r"/api/feeds", lambda b, q: {"id": L.add_feed(b["source"], b["merchant"], float(b.get("interval_s", 21600)))}),
        ("POST", r"/api/webhooks", lambda b, q: {"id": L.add_webhook(b["url"], b.get("types", []))}),
        ("POST", r"/api/run", lambda b, q: L.run_due()),
    ]


class NotFound(Exception):
    pass


def _nf():
    raise NotFound()


def _int(v):
    return int(v) if v not in (None, "") else None


def make_handler(L, extra=(), admin=True):
    # admin=False : mode public. Seules les routes passées dans `extra` (API consommateur) sont exposées ;
    # l'API marché (écriture de règles, flux, simulation) et la console /admin restent internes.
    R = list(extra) + (routes(L) if admin else [])

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def send(self, code, payload, ctype="application/json; charset=utf-8"):
            data = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def stream(self):
            """SSE : chaque événement de marché est poussé dès qu'il est détecté."""
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            q = L.bus.subscribe()
            try:
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()
                while True:
                    try:
                        ev = q.get(timeout=15)
                        msg = f"id: {ev['id']}\nevent: {ev['type']}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"
                    except queue.Empty:
                        msg = ": ping\n\n"
                    self.wfile.write(msg.encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                L.bus.unsubscribe(q)

        def handle_any(self, method):
            path, _, qs = self.path.partition("?")
            q = {k: unquote_plus(v) for k, v in (p.split("=", 1) for p in qs.split("&") if "=" in p)}
            # session : lue uniquement depuis le cookie, écrasée côté serveur (un paramètre ?_session= ne compte pas)
            jar = SimpleCookie(self.headers.get("Cookie", ""))
            q["_session"] = jar[SESSION_COOKIE].value if SESSION_COOKIE in jar else ""
            if path == "/api/stream":
                if not admin:
                    return self.send(404, {"error": "Route inconnue"})
                return self.stream()
            if not path.startswith("/api/"):
                # /admin = console Market Intelligence (outil interne) ; tout le reste = l'app grand public
                if path.startswith("/admin") and not admin:
                    return self.send(404, {"error": "Introuvable"})
                page = "index.html" if path.startswith("/admin") else "app.html"
                if not (WEB / page).exists():
                    page = "index.html"
                return self.send(200, (WEB / page).read_bytes(), "text/html; charset=utf-8")
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n)) if n else {}
            except json.JSONDecodeError:
                return self.send(400, {"error": "JSON invalide"})
            for m, pat, fn in R:
                mt = re.fullmatch(pat, path)
                if m == method and mt:
                    try:
                        out = fn(body, q, *mt.groups())
                        cookie = out.pop("__set_cookie__", None) if isinstance(out, dict) else None
                        if isinstance(out, dict) and out.get("__redirect__"):   # lien marchand ou lien magique : on redirige
                            self.send_response(302)
                            self.send_header("Location", out["__redirect__"])
                            if cookie:
                                self.send_header("Set-Cookie", cookie)
                            self.send_header("Content-Length", "0")
                            self.end_headers()
                            return
                        if cookie:
                            self.send_response(200)
                            self.send_header("Set-Cookie", cookie)
                            data = json.dumps(out, ensure_ascii=False, default=str).encode()
                            self.send_header("Content-Type", "application/json; charset=utf-8")
                            self.send_header("Content-Length", str(len(data)))
                            self.end_headers()
                            self.wfile.write(data)
                            return
                        return self.send(200, out)
                    except NotFound:
                        return self.send(404, {"error": "Introuvable"})
                    except PermissionError as e:
                        return self.send(401, {"error": str(e)})
                    except (ValueError, KeyError) as e:
                        return self.send(getattr(e, "status", 400), {"error": str(e)})
                    except LookupError as e:
                        return self.send(404, {"error": str(e) or "Introuvable"})
                    except Exception as e:  # noqa: BLE001
                        traceback.print_exc()
                        return self.send(500, {"error": str(e)})
            self.send(404, {"error": "Route inconnue"})

        def do_GET(self):
            self.handle_any("GET")

        def do_POST(self):
            self.handle_any("POST")

    return H


def serve(L, port=8000, host="127.0.0.1", extra=(), admin=True):
    return ThreadingHTTPServer((host, port), make_handler(L, extra, admin))
