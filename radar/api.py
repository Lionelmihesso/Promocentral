"""Routes grand public /api/r/ (le contrat entre l'app et les moteurs)."""
from .consumer import Consumer
from . import accounts
from .shop import Shop


def routes(radar):
    A = accounts.of(radar)
    C = Consumer(radar)
    U = C.uid
    S = Shop(radar, C)
    return [
        ("GET", r"/api/r/today", lambda b, q: S.today(q)),
        ("GET", r"/api/r/categories", lambda b, q: S.categories(q)),
        ("GET", r"/api/r/brands", lambda b, q: S.brands(q)),
        ("GET", r"/api/r/brand/([^/]+)", lambda b, q, n: S.brand(q, n)),
        ("GET", r"/api/r/item/(\d+)", lambda b, q, i: S.item(q, int(i))),
        ("POST", r"/api/r/save", lambda b, q: S.save(U(q, b), b)),
        ("GET", r"/api/r/saves", lambda b, q: S.saves(U(q))),
        ("POST", r"/api/r/brand/follow", lambda b, q: S.follow(U(q, b), b)),
        ("GET", r"/api/r/follows", lambda b, q: S.follows(U(q))),
        ("GET", r"/api/r/out/(\d+)", lambda b, q, i: S.out(q, int(i))),
        ("POST", r"/api/r/auth/request", lambda b, q: A.request_link(b.get("email"))),
        ("GET", r"/api/r/auth/verify", lambda b, q: A.verify(q)),
        ("GET", r"/api/r/auth/me", lambda b, q: A.me(q.get("_session"))),
        ("POST", r"/api/r/auth/logout", lambda b, q: A.logout(q.get("_session"))),
        ("GET", r"/api/r/feed", lambda b, q: radar.feed(U(q))),
        ("GET", r"/api/r/search", lambda b, q: C.search(U(q), q.get("q", ""), q.get("category") or None, q.get("brand") or None)),
        ("GET", r"/api/r/product/(\d+)", lambda b, q, i: C.product(U(q), int(i))),
        ("POST", r"/api/r/watch", lambda b, q: C.create_watch(U(q, b), b)),
        ("GET", r"/api/r/watches", lambda b, q: radar.feed(U(q))["watches"]),
        ("POST", r"/api/r/watch/(\d+)/stop", lambda b, q, i: C.stop_watch(U(q, b), int(i))),
        ("POST", r"/api/r/target", lambda b, q: C.set_target(U(q, b), b)),
        ("POST", r"/api/r/interactions", lambda b, q: (radar.interact(U(q, b), b["kind"], b.get("product_id"), b.get("query")), {"ok": True})[1]),
        ("POST", r"/api/r/dismiss", lambda b, q: C.dismiss(U(q, b), b["product_id"])),
        ("POST", r"/api/r/alternative", lambda b, q: C.alternative(U(q, b), b)),
        ("GET", r"/api/r/go/(\d+)", lambda b, q, i: C.go(U(q), int(i), q)),
        ("GET", r"/api/r/alerts", lambda b, q: C.alerts(U(q))),
    ]


def admin_routes(radar):
    """Routes internes : exposées seulement avec la console (python app.py serve --admin, ou demo)."""
    from .shop import Shop
    S = Shop(radar, Consumer(radar))
    return [("GET", r"/api/admin/metrics", lambda b, q: S.metrics())]
