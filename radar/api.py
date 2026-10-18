"""Routes grand public /api/r/ (le contrat entre l'app et le moteur) et routes internes de la console."""
from . import accounts
from .shop import Shop


def routes(radar):
    A = accounts.of(radar)
    S = Shop(radar)
    U = S.uid
    return [
        ("GET", r"/api/r/today", lambda b, q: S.today(q)),
        ("GET", r"/api/r/categories", lambda b, q: S.categories(q)),
        ("GET", r"/api/r/brands", lambda b, q: S.brands(q)),
        ("GET", r"/api/r/brand/([^/]+)", lambda b, q, n: S.brand(q, n)),
        ("GET", r"/api/r/item/(\d+)", lambda b, q, i: S.item(q, int(i))),
        ("GET", r"/api/r/out/(\d+)", lambda b, q, i: S.out(q, int(i))),
        ("POST", r"/api/r/save", lambda b, q: S.save(U(q), b)),
        ("GET", r"/api/r/saves", lambda b, q: S.saves(U(q))),
        ("POST", r"/api/r/brand/follow", lambda b, q: S.follow(U(q), b)),
        ("GET", r"/api/r/follows", lambda b, q: S.follows(U(q))),
        ("POST", r"/api/r/auth/request", lambda b, q: A.request_link(b.get("email"))),
        ("GET", r"/api/r/auth/verify", lambda b, q: A.verify(q)),
        ("GET", r"/api/r/auth/me", lambda b, q: A.me(q.get("_session"))),
        ("POST", r"/api/r/auth/logout", lambda b, q: A.logout(q.get("_session"))),
    ]


def admin_routes(radar):
    """Routes internes : exposées seulement avec la console (python app.py serve --admin, ou demo)."""
    S = Shop(radar)
    return [("GET", r"/api/admin/metrics", lambda b, q: S.metrics())]
