"""Contrat de l'app : /api/r/.

Lecture ouverte : today?category=&q= (remises du jour), top (l'onglet Top deals : remises et prix bas, why dit
pourquoi), search (tout le catalogue suivi ; voir plus bas), categories et brands (celles qui ont des remises ; ?all=1 :
toutes), brand/<nom> et category/<clé> (tous les produits, remises d'abord), item/<id>, view {product_id, from, m, v}
(fiche vue : le taux de clic), out/<offer_id>?from=&m=&v= (clic tracé → lien affilié de l'enseigne partenaire, avec
l'identifiant du clic ; m : la mission d'où il part), missions/parse {text} et missions/preview {mission} (ce qui est
compris, ce qui y répond déjà).
Recherche (v56) : search?q=&category=&brand=&feat=&attr=&min=&max=&off=&low=&sort=&recent= ; q est une phrase comprise
(query.read : « aspirateur balai sans fil sous 300 € ») ; les autres paramètres, choisis dans l'app, l'emportent sur ce
que dit la phrase (feat : fonctions séparées par des virgules ; attr : clé:valeur séparés par des virgules). La réponse
dit criteria (ce qui est appliqué), chips (les mêmes, en mots), words et ignored (les mots cherchés, ceux qui ne
trouvaient rien), unsupported (un rayon pas encore suivi) et relaxed (rien sous le budget : les plus proches au-dessus) ;
sans mot ni filtre, le feed, orienté par recent (les dernières recherches du navigateur, séparées par « | ») et par les
goûts. v60 : funnel (Affiner en entonnoir, deals/funnel.py : les étapes franchies, les questions qui restent) ; sort :
relevance, price, price_desc, discount ; item/<id> n'envoie plus history ni position (la fiche n'a plus la jauge).
Ce qu'on garde (v56 : sans e-mail) : save, brand/follow, interests {categories}, missions (POST : sauvegarder une
recherche, prix facultatif), profile {learn} créent au besoin un compte invité (cookie) ; saves, follows, missions (GET)
sont vides sans compte ; missions/delete, missions/seen (ce qui y répond n'est plus nouveau), missions/alert {id, on}
(e-mail de la nuit), profile/reset, account/delete (effacer le compte et ce qu'il gardait).
Adresse e-mail (facultative) : auth/request {email, mission?} (depuis un compte invité : l'adresse lui sera rattachée),
auth/verify?token= (pose le cookie ; un compte invité y est rattaché ou versé ; la mission qui attendait est lancée et
l'app l'ouvre : /?mission=<id> ; lien expiré : /?auth=expired), auth/me (email, guest, variant ; 401 sans compte),
auth/logout.
Goûts (profile.py) : today, top, search (le feed) et foryou (« pour vous ») suivent le profil ; le navigateur envoie p
(fiches vues v<id>.<âge en jours>, clics c…, au plus 60 ; sans compte, ou quand le compte n'apprend pas), i (rayons
choisis, sans compte) et v=t (témoin) ; rien n'en est gardé. profile : ce que l'app retient et a compris.
Surveillance : health (pour une sonde extérieure : status ok | degraded | critical, heure de la dernière nuit, taille du
catalogue ; 503 si aucune nuit depuis 36 h, si la dernière a eu une étape en erreur ou si un incident critique est
ouvert ; aucun détail de plus).
"""
import json
import re
import time
import traceback
from dataclasses import dataclass, field
from urllib.parse import unquote

from . import affiliate, config, ontology
from .accounts import Accounts
from .activity import Activity
from .catalog import SORTS, Catalog
from .errors import BadRequest, NotFound
from .labels import FEATURE_LABEL, ROOMS
from .query import WANTED
from .missions import Missions
from .ops import utc
from .profile import Profiles, control

STALE_S = 36 * 3600            # plus de 36 h sans nuit terminée : la plateforme ne se met plus à jour


@dataclass
class Request:
    method: str
    path: str
    query: dict = field(default_factory=dict)
    body: dict = field(default_factory=dict)
    session: str = ""
    ip: str = ""
    cookie: str = None                 # posé par la route : le compte invité créé pendant la requête
    guest: int = None                  # ce compte invité (effacé si la requête échoue)


@dataclass
class Response:
    status: int = 200
    body: object = None
    location: str = None
    cookie: str = None


class Api:
    def __init__(self, store, settings, outbox=None, clock=time.time, rules=None):
        """rules : enseigne → règle d'affiliation ; par défaut, le fichier DEALS_AFFILIATE (aucun : liens directs)."""
        self.catalog = Catalog(store)
        self.accounts = Accounts(store, settings, outbox, clock)
        self.activity = Activity(store, clock, rules if rules is not None else affiliate.load(settings.affiliate))
        self.missions = Missions(store, self.catalog, clock)
        self.profiles = Profiles(store, clock)
        self.store, self.clock, self.settings = store, clock, settings
        C, A, T, M, P = self.catalog, self.accounts, self.activity, self.missions, self.profiles
        uid = lambda r: A.user(r.session)
        need = self._keep                                   # garder quelque chose : un compte invité au besoin
        prof = lambda r: P.of(uid(r), r.query, self._recent(r.query))
        self.routes = [(m, re.compile(p), f) for m, p, f in [
            ("GET", r"/api/r/today", lambda r: C.today(uid(r), r.query.get("category") or None, r.query.get("q") or None, prof(r))),
            ("GET", r"/api/r/search", lambda r: C.search(uid(r), r.query.get("q") or None, r.query.get("category") or None,
                                                         *self._filters(r.query), recent=self._recent(r.query),
                                                         low=r.query.get("low") == "1", prof=prof(r), **self._criteria(r.query))),
            ("GET", r"/api/r/top", lambda r: C.top(uid(r), prof(r))),
            ("GET", r"/api/r/foryou", lambda r: C.foryou(uid(r), prof(r))),
            ("GET", r"/api/r/profile", self._profile),
            ("POST", r"/api/r/interests", lambda r: P.choose(need(r), (r.body or {}).get("categories"))),
            ("POST", r"/api/r/profile", lambda r: P.learn(need(r), (r.body or {}).get("learn"))),
            ("POST", r"/api/r/profile/reset", lambda r: P.reset(uid(r)) if uid(r) is not None else {"reset_at": None}),
            ("GET", r"/api/r/categories", lambda r: C.categories(r.query.get("all") == "1")),
            ("GET", r"/api/r/brands", lambda r: C.brands(uid(r), r.query.get("all") == "1")),
            ("GET", r"/api/r/brand/([^/]+)", lambda r, name: C.brand(uid(r), unquote(name))),
            ("GET", r"/api/r/category/([a-z_]+)", lambda r, key: C.category(uid(r), key)),
            ("GET", r"/api/r/item/(\d+)", lambda r, pid: C.item(uid(r), int(pid))),
            ("GET", r"/api/r/out/(\d+)", lambda r, oid: Response(302, location=T.click(uid(r), int(oid), r.query.get("from"),
                                                                                         r.query.get("m"), r.query.get("v")))),
            ("POST", r"/api/r/view", lambda r: T.view(uid(r), r.body)),
            ("POST", r"/api/r/save", lambda r: T.save(need(r), r.body)),
            ("GET", r"/api/r/saves", lambda r: C.saves(uid(r))),
            ("POST", r"/api/r/brand/follow", lambda r: T.follow(need(r), r.body)),
            ("GET", r"/api/r/follows", lambda r: T.follows(uid(r))),
            ("POST", r"/api/r/missions/parse", lambda r: M.interpret_text(uid(r), (r.body or {}).get("text"))),
            ("POST", r"/api/r/missions/preview", lambda r: M.preview(uid(r), r.body or {})),
            ("GET", r"/api/r/missions", lambda r: M.list(uid(r))),
            ("POST", r"/api/r/missions", lambda r: M.create(need(r), r.body or {})),
            ("POST", r"/api/r/missions/delete", lambda r: M.remove(uid(r), (r.body or {}).get("id"))),
            ("POST", r"/api/r/missions/seen", lambda r: M.seen(uid(r), (r.body or {}).get("id"))),
            ("POST", r"/api/r/missions/alert", lambda r: M.alert(uid(r), (r.body or {}).get("id"), (r.body or {}).get("on"))),
            ("POST", r"/api/r/account/delete", lambda r: Response(200, A.forget(A.require(r.session)), cookie=A.cookie(None))),
            ("POST", r"/api/r/auth/request", lambda r: A.request_link(r.body.get("email"), r.ip, *M.pending(r.body.get("mission")),
                                                                     guest=uid(r))),
            ("GET", r"/api/r/auth/verify", self._verify),
            ("GET", r"/api/r/auth/me", lambda r: {**A.me(r.session), "variant": "t" if control(uid(r)) else "p"}),   # 401 sans session
            ("POST", r"/api/r/auth/logout", lambda r: Response(200, {"ok": True}, cookie=A.logout(r.session))),
            ("GET", r"/api/r/health", lambda r: self._health()),
            ("GET", r"/api/r/legal", lambda r: self._legal()),
        ]]

    @staticmethod
    def _filters(query):
        """Recherche : budget (min, max en euros), remise minimale (off, en %), tri ; une valeur invalide est refusée."""
        try:
            lo, hi, off = (float(query[k]) if query.get(k) else None for k in ("min", "max", "off"))
        except ValueError:
            raise BadRequest("Filtre invalide")
        sort = query.get("sort") or None
        if sort is not None and sort not in SORTS:
            raise BadRequest("Tri inconnu")
        return lo, hi, off, sort

    @staticmethod
    def _criteria(query):
        """Recherche : les critères choisis dans l'app (marque, fonctions, tailles), qui l'emportent sur la phrase."""
        feats = [f for f in (query.get("feat") or "").split(",") if f]
        if any(f not in FEATURE_LABEL for f in feats):
            raise BadRequest("Fonction inconnue")
        attrs = {}
        for part in (query.get("attr") or "").split(","):
            if not part:
                continue
            k, _, v = part.partition(":")
            if k not in WANTED or not v:
                raise BadRequest("Caractéristique inconnue")
            attrs[k] = float(v) if re.fullmatch(r"\d+(?:\.\d+)?", v) else v.upper() if k == "energy_class" else v
            if isinstance(attrs[k], float) and attrs[k].is_integer():
                attrs[k] = int(attrs[k])
        room = query.get("room") or None
        if room is not None and room not in ROOMS:
            raise BadRequest("Pièce inconnue")
        out = {"brand": query.get("brand") or None, "features": feats, "attrs": attrs, "room": room}
        domain = query.get("domain") or None                # un domaine à ontologie : le type, les attributs exigés
        d = ontology.DOMAINS.get(domain) if domain else None
        if domain and d is None:
            raise BadRequest("Domaine inconnu")
        sub, props = query.get("sub") or None, {}
        for part in (query.get("prop") or "").split(","):
            if part:
                k, _, v = part.partition(":")
                props[k] = v != "0"
        if (sub or props) and d is None:
            raise BadRequest("Ces critères demandent un domaine")
        if d and (sub and sub not in d.sub or any(k not in d.bools for k in props)):
            raise BadRequest("Critère inconnu")
        if d:
            out.update(domain=domain, sub=sub, props=props)
        return out

    def _keep(self, r):
        """Le compte de la requête ; sans compte, un compte invité est créé et son cookie part avec la réponse ; un invité
        qui garde encore quelque chose voit sa clé renouvelée."""
        who = self.accounts.user(r.session)
        if who is None:
            who, r.cookie = self.accounts.guest(r.ip)
            r.guest = who                                       # à oublier si la requête échoue (handle)
        else:
            r.cookie = self.accounts.renew(r.session)           # un invité : sa clé repart pour un an
        return who

    @staticmethod
    def _recent(query):
        """Feed de la Recherche : les dernières recherches de la personne, la plus récente d'abord, séparées par « | »
        (80 caractères au plus chacune ; le catalogue lit les premières, catalog.RECENT_SEARCHES) ; jamais gardées par le
        serveur."""
        return [t.strip()[:80] for t in (query.get("recent") or "").split("|") if t.strip()]

    def _legal(self):
        """Les mentions légales (page « Mentions légales et données personnelles ») : l'identité de l'éditeur, lue dans la
        configuration (DEALS_LEGAL_…) ; en production l'app ne démarre pas sans elle (config.legal_missing)."""
        s = self.settings
        if config.is_demo(s):                                  # démo : aucune entité, aucune mention, quelle que soit la config
            return {"name": "Promo Central", "demo": True, "editor": None, "registration": None, "address": None,
                    "director": None, "contact": None, "host": None}
        return {"name": "Promo Central", "editor": s.legal_editor or None, "registration": s.legal_registration or None,
                "address": s.legal_address or None, "director": s.legal_director or None, "contact": s.legal_contact or None,
                "host": s.legal_host or None}

    def _health(self):
        """État pour une sonde extérieure : elle prévient le responsable par un autre chemin que nos e-mails, même quand
        la nuit ne tourne plus du tout (agent.py ne peut pas signaler une nuit qui n'a pas lieu)."""
        last = self.store.q("SELECT ended, status FROM runs WHERE ended IS NOT NULL AND COALESCE(status, '') NOT IN ('retry', 'running') "
                            "ORDER BY id DESC LIMIT 1", one=True)
        open_ = {r["severity"]: r["n"] for r in self.store.q("SELECT severity, COUNT(*) n FROM incidents WHERE status='open' "
                                                              "GROUP BY severity")}
        catalog = self.store.q("SELECT COUNT(*) n FROM catalog", one=True)["n"]
        demo = config.is_demo(self.settings)                 # démo : données simulées, datées ; la nuit ne tourne pas
        late = (not demo and (last is None or self.clock() - last["ended"] > STALE_S)) or (demo and catalog == 0)
        state = "critical" if late or open_.get("critical") or (last is not None and last["status"] == "failed") else \
            "degraded" if open_.get("warning") else "ok"
        body = {"status": state, "last_night": utc(last["ended"]) if last else None, "catalog": catalog}
        if demo:
            body["demo"] = True
        return Response(503 if state == "critical" else 200, body)

    def _profile(self, r):
        """Ce que l'app retient et a compris des goûts : rayons choisis (du compte ; sans compte, ceux que le navigateur
        envoie), rayons et marques compris (taste), apprentissage par les fiches et les clics, témoin ou non, compte
        invité ou adresse donnée."""
        who = self.accounts.user(r.session)
        prof = self.profiles.of(who, r.query, self._recent(r.query))
        email = self.store.q("SELECT email FROM users WHERE id=?", (who,), one=True)["email"] if who is not None else None
        return {"picks": list(prof.picks) if who is None else [x["category"] for x in self.store.q(
                    "SELECT category FROM interests WHERE user_id=? ORDER BY created_at", (who,))],
                "taste": self.catalog.taste(prof), "learn": bool(self.profiles.prefs(who)["learn"]) if who is not None else None,
                "variant": ("t" if control(who) else "p") if who is not None else ("t" if r.query.get("v") == "t" else "p"),
                "signed_in": who is not None, "guest": who is not None and email is None, "email": email}

    def _verify(self, r):
        """Le lien ouvert connecte la personne ; la mission qui attendait ce lien est lancée, et l'app l'ouvre."""
        location, cookie, opened = self.accounts.verify(r.query.get("token", ""))
        if opened:
            uid, mission, attached = opened
            if attached:
                self.missions.caught_up(uid)                    # ce que l'invité voyait déjà ne part pas par e-mail
            if mission:
                try:
                    location = f"/?mission={self.missions.create(uid, json.loads(mission))['id']}"
                except (BadRequest, NotFound):
                    pass                                        # produit retiré depuis, ou 20 missions déjà : connecté quand même
        return Response(302, location=location, cookie=cookie)

    def handle(self, req):
        for method, pattern, fn in self.routes:
            m = pattern.fullmatch(req.path)
            if m and method == req.method:
                try:
                    out = fn(req, *m.groups())
                except Exception as e:      # erreurs métier → statut ; le reste → 500 sans détail interne
                    if req.guest is not None:   # rien n'a été gardé : pas de compte invité orphelin
                        self.accounts.forget(req.guest)
                    status = getattr(e, "status", None)
                    if status is None:
                        traceback.print_exc()
                        return Response(500, {"error": "Erreur interne"})
                    return Response(status, {"error": str(e)})
                out = out if isinstance(out, Response) else Response(200, out)
                if req.cookie and not out.cookie:
                    out.cookie = req.cookie                     # le compte invité créé pendant la requête
                return out
        return Response(404, {"error": "Route inconnue"})
