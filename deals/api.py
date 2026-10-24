"""Contrat de l'app : /api/r/ (inchangé pour l'interface v41).

Lecture ouverte (sans compte) : today?category=&q= (remises du jour), search?q=&category=&min=&max=&off=&sort= (tout le
catalogue suivi ; filtres : catégorie, budget, remise minimale ; tri : relevance, price, discount ; categories : la
facette des catégories trouvées), categories et brands (celles qui ont des remises ; ?all=1 : toutes), brand/<nom> et category/<clé> (tous les
produits, remises d'abord), item/<id>,
out/<offer_id>?from=, missions/parse {text} et missions/preview {mission} (ce qui est compris, ce qui y répond déjà).
Champs ajoutés depuis la v41 : since et ends (fiche), alternatives avec saving (fiche : comparables moins chers), kind
(cartes : catégorie au singulier ; specs, les caractéristiques, retiré en v49 : plus montré), history (fiche : prix des 90
derniers jours), position (fiche : le prix du jour sur ces 90 jours), published_at (today : heure de la dernière
publication), saved_price (favoris), family, best et products (catégories), best, products, top et categories (marques).
today?category= accepte plusieurs catégories séparées par des virgules.
Session requise (sinon 401) : save, saves, brand/follow, follows, missions (GET : les miennes ; POST : lancer),
missions/delete {id}.
Connexion : auth/request {email}, auth/verify?token= (pose le cookie, ou renvoie vers /?auth=expired), auth/me, auth/logout.
"""
import re
import time
import traceback
from dataclasses import dataclass, field
from urllib.parse import unquote

from .accounts import Accounts
from .activity import Activity
from .catalog import SORTS, Catalog
from .errors import BadRequest
from .missions import Missions


@dataclass
class Request:
    method: str
    path: str
    query: dict = field(default_factory=dict)
    body: dict = field(default_factory=dict)
    session: str = ""
    ip: str = ""


@dataclass
class Response:
    status: int = 200
    body: object = None
    location: str = None
    cookie: str = None


class Api:
    def __init__(self, store, settings, outbox=None, clock=time.time):
        self.catalog = Catalog(store)
        self.accounts = Accounts(store, settings, outbox, clock)
        self.activity = Activity(store, clock)
        self.missions = Missions(store, self.catalog, clock)
        C, A, T, M = self.catalog, self.accounts, self.activity, self.missions
        uid = lambda r: A.user(r.session)
        need = lambda r: A.require(r.session)
        self.routes = [(m, re.compile(p), f) for m, p, f in [
            ("GET", r"/api/r/today", lambda r: C.today(uid(r), r.query.get("category") or None, r.query.get("q") or None)),
            ("GET", r"/api/r/search", lambda r: C.search(uid(r), r.query.get("q") or None, r.query.get("category") or None,
                                                         *self._filters(r.query))),
            ("GET", r"/api/r/categories", lambda r: C.categories(r.query.get("all") == "1")),
            ("GET", r"/api/r/brands", lambda r: C.brands(uid(r), r.query.get("all") == "1")),
            ("GET", r"/api/r/brand/([^/]+)", lambda r, name: C.brand(uid(r), unquote(name))),
            ("GET", r"/api/r/category/([a-z_]+)", lambda r, key: C.category(uid(r), key)),
            ("GET", r"/api/r/item/(\d+)", lambda r, pid: C.item(uid(r), int(pid))),
            ("GET", r"/api/r/out/(\d+)", lambda r, oid: Response(302, location=T.click(uid(r), int(oid), r.query.get("from")))),
            ("POST", r"/api/r/save", lambda r: T.save(need(r), r.body)),
            ("GET", r"/api/r/saves", lambda r: C.saves(need(r))),
            ("POST", r"/api/r/brand/follow", lambda r: T.follow(need(r), r.body)),
            ("GET", r"/api/r/follows", lambda r: T.follows(need(r))),
            ("POST", r"/api/r/missions/parse", lambda r: M.interpret_text(uid(r), (r.body or {}).get("text"))),
            ("POST", r"/api/r/missions/preview", lambda r: M.preview(uid(r), r.body or {})),
            ("GET", r"/api/r/missions", lambda r: M.list(need(r))),
            ("POST", r"/api/r/missions", lambda r: M.create(need(r), r.body or {})),
            ("POST", r"/api/r/missions/delete", lambda r: M.remove(need(r), (r.body or {}).get("id"))),
            ("POST", r"/api/r/auth/request", lambda r: A.request_link(r.body.get("email"), r.ip)),
            ("GET", r"/api/r/auth/verify", self._verify),
            ("GET", r"/api/r/auth/me", lambda r: A.me(r.session)),
            ("POST", r"/api/r/auth/logout", lambda r: Response(200, {"ok": True}, cookie=A.logout(r.session))),
        ]]

    @staticmethod
    def _filters(query):
        """Recherche : budget (min, max en euros), remise minimale (off, en %), tri ; une valeur invalide est refusée."""
        try:
            lo, hi, off = (float(query[k]) if query.get(k) else None for k in ("min", "max", "off"))
        except ValueError:
            raise BadRequest("Filtre invalide")
        sort = query.get("sort") or "relevance"
        if sort not in SORTS:
            raise BadRequest("Tri inconnu")
        return lo, hi, off, sort

    def _verify(self, r):
        location, cookie = self.accounts.verify(r.query.get("token", ""))
        return Response(302, location=location, cookie=cookie)

    def handle(self, req):
        for method, pattern, fn in self.routes:
            m = pattern.fullmatch(req.path)
            if m and method == req.method:
                try:
                    out = fn(req, *m.groups())
                except Exception as e:      # erreurs métier → statut ; le reste → 500 sans détail interne
                    status = getattr(e, "status", None)
                    if status is None:
                        traceback.print_exc()
                        return Response(500, {"error": "Erreur interne"})
                    return Response(status, {"error": str(e)})
                return out if isinstance(out, Response) else Response(200, out)
        return Response(404, {"error": "Route inconnue"})
