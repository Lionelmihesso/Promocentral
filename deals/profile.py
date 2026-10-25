"""Profil de goûts d'une personne : ses rayons (catégories) et ses marques, pesés, et ce qu'ils changent à l'ordre des deals.

Ce qui compte :
  choisi   affinité 1         rayons choisis (encart de l'accueil, Profil), marques suivies, rayon et marque d'une mission
  vu       affinité ≤ 0,8     favoris (2 points), clics vers l'enseigne (1,5), recherches qui nomment un rayon ou une
                              marque (1), fiches ouvertes (0,5) ; un signal compte moitié moins tous les 30 jours ; la
                              confiance monte avec les points (pleine à 2 : deux clics, ou quatre fiches)
Une marque vue pèse moitié moins qu'un rayon vu (on parcourt des rayons plus que des marques) et ne compte qu'à partir
d'un point (deux fiches, ou un clic) ; un rayon donne 30 % de son affinité à sa famille (électroménager, ameublement,
literie) : la découverte reste proche des goûts, sans les noyer.

Affinité d'un produit : max(rayon, marque, 0,3 × famille), entre 0 et 1. Son score : intérêt du deal × (1 + ½ affinité), donc
au plus × 1,5, comme une marque suivie avant : l'intérêt du deal prime (une remise de 40 % hors de vos rayons passe devant
une remise de 26 % dans vos rayons). Un emplacement sur quatre reste au meilleur deal, quels que soient les goûts
(découverte) ; jamais plus de deux produits du même rayon sur quatre de suite.

Sans compte : le navigateur garde les rayons choisis et, pendant la visite, les fiches ouvertes et les clics ; il les
envoie avec les lectures (paramètres p, i, recent) ; le serveur n'en garde rien. Avec un compte : rayons choisis
(interests), favoris, marques, missions et, sauf refus (prefs.learn), fiches ouvertes et clics depuis la dernière remise à
zéro. Témoins : une personne sur dix voit l'ordre sans personnalisation (seule la marque suivie compte), pour mesurer ce
que la personnalisation rapporte (activity.metrics, by_variant).
"""
import hashlib
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

from .errors import BadRequest
from .extract.categories import FAMILY_OF

WEIGHT = {"save": 2.0, "click": 1.5, "search": 1.0, "view": 0.5}
CODE = {"v": "view", "c": "click", "s": "save"}            # p=v12.0,c45.3 : fiche 12 vue aujourd'hui, clic vers 45 il y a 3 jours
HALF_LIFE = 30.0                                          # jours : un signal compte moitié moins tous les 30 jours
FULL = 2.0                                                # points pour une confiance pleine
SEEN_CAT, SEEN_BRAND, FAMILY = 0.8, 0.4, 0.3              # plafonds de l'affinité d'un rayon vu, d'une marque vue ; part de la famille
BRAND_MIN = 1.0                                           # une marque vue compte à partir d'un point : deux fiches, ou un clic
BOOST = 0.5                                               # score × (1 + ½ affinité) : au plus × 1,5
MINE = 0.3                                                # « pour vous » : affinité d'au moins 0,3
EXPLORE = 4                                               # un emplacement sur 4 : le meilleur deal, sans personnalisation
WINDOW, SAME = 4, 2                                       # au plus 2 produits du même rayon sur 4 de suite
CONTROL = 10                                              # une personne sur 10 : témoin, sans personnalisation
MAX_EVENTS, MAX_PICKS, HISTORY_DAYS = 60, 12, 90
EVENT = re.compile(r"([vcs])(\d{1,9})(?:\.(\d{1,3}))?")


@dataclass
class Profile:
    cats: dict = field(default_factory=dict)              # rayon → affinité
    brands: dict = field(default_factory=dict)            # marque → affinité
    fams: dict = field(default_factory=dict)              # famille → affinité de son meilleur rayon
    picks: tuple = ()                                     # rayons choisis
    follows: frozenset = frozenset()                      # marques suivies
    personal: bool = False                                # False : témoin, ou rien de connu → l'ordre d'avant
    _boosts: dict = field(default_factory=dict, repr=False, compare=False)   # (rayon, marque) → bonus, le temps d'une lecture

    def direct(self, category, brand):
        """Le rayon ou la marque eux-mêmes (sans la famille) : ce qui fait « pour vous »."""
        return max(self.cats.get(category, 0), self.brands.get(brand, 0))

    def affinity(self, category, brand):
        return max(self.direct(category, brand), FAMILY * self.fams.get(FAMILY_OF.get(category), 0))

    def boost(self, category, brand):
        b = self._boosts.get((category, brand))
        if b is None:
            if not self.personal:                         # l'ordre d'avant : seule la marque suivie compte, 1,5 fois
                b = 1 + BOOST if brand in self.follows else 1
            else:
                b = 1 + BOOST * self.affinity(category, brand)
            self._boosts[(category, brand)] = b
        return b


def build(chosen=(), follows=(), events=(), personal=True):
    """chosen : rayons choisis (et ceux des missions) ; follows : marques suivies (et celles des missions) ; events :
    (genre, rayon, marque, âge en jours) des signaux vus (fiches, clics, favoris, recherches). → Profile."""
    raw_c, raw_b, mass = defaultdict(float), defaultdict(float), 0.0
    for kind, cat, brand, age in events:
        w = WEIGHT[kind] * 0.5 ** (max(age, 0) / HALF_LIFE)
        mass += w
        if cat:
            raw_c[cat] += w
        if brand:
            raw_b[brand] += w
    conf = min(1.0, mass / FULL)
    cats = {c: SEEN_CAT * conf * v / max(raw_c.values()) for c, v in raw_c.items()}
    brands = {b: SEEN_BRAND * conf * v / max(raw_b.values()) for b, v in raw_b.items() if v >= BRAND_MIN}
    cats.update({c: 1.0 for c in chosen if c})
    brands.update({b: 1.0 for b in follows if b})
    fams = {}
    for c, a in cats.items():
        f = FAMILY_OF.get(c)
        if f:
            fams[f] = max(fams.get(f, 0), a)
    return Profile(cats, brands, fams, tuple(dict.fromkeys(c for c in chosen if c)), frozenset(b for b in follows if b),
                   personal and bool(cats or brands))


def parse_events(text):
    """Les signaux envoyés par le navigateur (p=v12.0,c45.3,s7.10) → [(genre, produit, âge en jours)] ; le reste est ignoré."""
    out = []
    for part in (text or "").split(",")[:MAX_EVENTS]:
        m = EVENT.fullmatch(part.strip())
        if m:
            out.append((CODE[m[1]], int(m[2]), min(int(m[3] or 0), 365)))
    return out


def parse_picks(text, known):
    return list(dict.fromkeys(c for c in (text or "").split(",") if c in known))[:MAX_PICKS]


def arrange(rows, value, profile, key=lambda r: r["product_id"], head=120):
    """L'ordre personnalisé : score = value × bonus du profil ; un emplacement sur EXPLORE au meilleur value restant, sans
    personnalisation (découverte) ; au plus SAME produits du même rayon sur WINDOW de suite, dans les `head` premiers.
    Sans personnalisation : l'ordre d'avant (le score seul)."""
    score = lambda r: value(r) * profile.boost(r["category"], r["brand"])
    if not profile.personal:                              # l'ordre d'avant, à l'identique
        return sorted(rows, key=lambda r: (-score(r), key(r)))
    ordered = sorted(rows, key=lambda r: (-score(r), -value(r), key(r)))
    plain = sorted(rows, key=lambda r: (-value(r), key(r)))
    picked, used, at = [], set(), {"o": 0, "p": 0}
    while len(picked) < min(head, len(rows)):
        src, k = (plain, "p") if (len(picked) + 1) % EXPLORE == 0 else (ordered, "o")
        while key(src[at[k]]) in used:
            at[k] += 1
        r = src[at[k]]
        used.add(key(r))
        picked.append(r)
    return diversify(picked) + [r for r in ordered if key(r) not in used]


def diversify(rows, window=WINDOW, same=SAME):
    """Au plus `same` produits du même rayon sur `window` de suite (le suivant qui le permet passe devant ; à défaut, l'ordre).
    Une file par rayon : le suivant permis est la tête de file la plus ancienne parmi les rayons permis."""
    queues = {}
    for i, r in enumerate(rows):
        queues.setdefault(r["category"], deque()).append((i, r))
    out = []
    while queues:
        recent = [r["category"] for r in out[-(window - 1):]]
        heads = [q[0] for c, q in queues.items() if recent.count(c) < same] or [q[0] for q in queues.values()]
        _, r = min(heads, key=lambda h: h[0])
        out.append(r)
        queue = queues[r["category"]]
        queue.popleft()
        if not queue:
            del queues[r["category"]]
    return out


def blend(yours, others, every=EXPLORE):
    """Vos produits, et un sur `every` pris ailleurs (découverte) ; quand une liste est vide, l'autre continue."""
    out, yours, others = [], list(yours), list(others)
    while yours or others:
        turn = others if (len(out) + 1) % every == 0 and others else yours if yours else others
        out.append(turn.pop(0))
    return out


def mine(rows, profile):
    """Les produits de vos goûts : leur rayon ou leur marque (pas seulement la famille) a une affinité d'au moins MINE."""
    return [r for r in rows if profile.personal and profile.direct(r["category"], r["brand"]) >= MINE]


def control(uid):
    """Une personne sur CONTROL est témoin (sans personnalisation), toujours la même : un hachage de son compte."""
    return int(hashlib.sha256(f"deals-{uid}".encode()).hexdigest(), 16) % CONTROL == 0


class Profiles:
    """Le profil d'une requête : celui du compte (ses tables) ou celui que le navigateur envoie ; et les gestes qui le règlent
    (rayons choisis, apprentissage, remise à zéro). Seul module qui écrit interests et prefs."""

    def __init__(self, store, clock=time.time):
        self.s, self.clock = store, clock

    def known(self):
        return {r["category"] for r in self.s.q("SELECT DISTINCT category FROM catalog WHERE category IS NOT NULL")}

    def _things(self, ids):
        ids = list(dict.fromkeys(ids))
        return {r["id"]: r for r in self.s.q(f"SELECT id, category, brand FROM products WHERE id IN ({','.join('?' * len(ids))})",
                                             ids)} if ids else {}

    def _searched(self, recent):
        """Les recherches récentes qui nomment un rayon ou une marque → [(rayon, marque)]. Une marque : un mot d'au moins
        trois lettres qui commence l'un des siens. Un rayon : la recherche contient l'un de ses noms, et c'est le plus
        précis (« lave-linge 9 kg » : les lave-linge ; « lave-linge séchant » : les lave-linge séchants, pas les
        lave-linge) ; à défaut, tous ses mots restants le nomment (« plaque induction » : les plaques de cuisson ; « lave » :
        les lave-linge et les lave-vaisselle)."""
        recent = list(recent)[:4]
        if not recent:
            return []
        from .catalog import CATEGORY_LABEL, CATEGORY_ONE, names, norm, tokens   # ici : catalog importe ce module
        words = lambda text: set(" ".join(tokens(text)).split())   # un synonyme peut valoir deux mots (« lavelinge »)
        out = []
        brand_of = {r["brand"]: f" {norm(r['brand'])} "
                    for r in self.s.q("SELECT DISTINCT brand FROM catalog WHERE brand IS NOT NULL")}
        called = {c: [w for w in (words(CATEGORY_LABEL.get(c, "")), words(CATEGORY_ONE.get(c, "")), words(c.replace("_", " "))) if w]
                  for c in self.known()}
        for text in recent:
            toks = tokens(text)
            brands = {b for b, n in brand_of.items() if any(len(t) >= 3 and f" {t}" in n for t in toks)}
            rest = [t for t in toks if not any(len(t) >= 3 and f" {t}" in brand_of[b] for b in brands)]
            have = set(" ".join(rest).split())
            named = {c: max((w for w in ws if w <= have), key=len, default=None) for c, ws in called.items()}
            named = {c: w for c, w in named.items() if w}
            long = [t for t in rest if len(t) >= 3]                # « d'angle », « 9 kg » : trop courts pour nommer
            cats = {c for c, w in named.items() if not any(w < other for other in named.values())} or \
                {c for c in called if long and all(f" {t}" in names(c, None) for t in long)}
            out += [(c, None) for c in sorted(cats)] + [(None, b) for b in sorted(brands)]
        return out

    def of(self, uid, query=None, recent=()):
        """Le profil pour une lecture. Sans compte : p (signaux), i (rayons choisis), v=t (témoin), venus du navigateur ;
        avec un compte : ses tables (le navigateur ne compte pas en double) ; recent : ses recherches récentes."""
        query, now = query or {}, self.clock()
        searched = [("search", c, b, 0) for c, b in self._searched(recent)]
        if uid is None:
            events = parse_events(query.get("p"))
            things = self._things(i for _, i, _ in events)
            seen = [(k, things[i]["category"], things[i]["brand"], age) for k, i, age in events if i in things]
            picks = parse_picks(query.get("i"), self.known()) if query.get("i") else []
            return build(picks, (), seen + searched, personal=query.get("v") != "t")
        prefs = self.prefs(uid)
        since = max(now - HISTORY_DAYS * 86400, prefs["reset_at"] or 0)
        rows = [("save", r["product_id"], r["at"]) for r in self.s.q(
            "SELECT product_id, created_at at FROM saves WHERE user_id=?", (uid,))]
        if prefs["learn"]:
            for kind, table in (("view", "views"), ("click", "clicks")):
                rows += [(kind, r["product_id"], r["at"]) for r in self.s.q(
                    f"SELECT product_id, at FROM {table} WHERE user_id=? AND at>? ORDER BY at DESC LIMIT 300", (uid, since))]
        missions = self.s.q("SELECT product_id, category, brand FROM missions WHERE user_id=?", (uid,))
        things = self._things([i for _, i, _ in rows] + [m["product_id"] for m in missions if m["product_id"]])
        seen = [(k, things[i]["category"], things[i]["brand"], (now - at) / 86400) for k, i, at in rows if i in things]
        chosen = [r["category"] for r in self.s.q("SELECT category FROM interests WHERE user_id=? ORDER BY created_at", (uid,))]
        follows = [r["brand"] for r in self.s.q("SELECT brand FROM follows WHERE user_id=?", (uid,))]
        for m in missions:                                     # une mission en cours : on est en train d'acheter
            thing = things.get(m["product_id"]) or {}
            chosen.append(m["category"] or thing.get("category"))
            follows.append(m["brand"] or (thing.get("brand") if m["product_id"] else None))
        return build(chosen, follows, seen + searched, personal=not control(uid))

    # ------------------------------------------------------------ gestes
    def prefs(self, uid):
        return self.s.q("SELECT learn, reset_at FROM prefs WHERE user_id=?", (uid,), one=True) or {"learn": 1, "reset_at": None}

    def choose(self, uid, categories):
        """Les rayons choisis du compte, remplacés (la liste montrée par l'app) ; ceux qu'on ne connaît pas sont refusés."""
        if not isinstance(categories, list) or len(categories) > MAX_PICKS:
            raise BadRequest("rayons invalides")
        known = self.known()
        picked = list(dict.fromkeys(c for c in categories if isinstance(c, str)))
        if any(c not in known for c in picked):
            raise BadRequest("rayon inconnu")
        now = self.clock()
        with self.s.tx() as c:
            c.execute("DELETE FROM interests WHERE user_id=?", (uid,))
            c.executemany("INSERT INTO interests(user_id, category, created_at) VALUES (?,?,?)", [(uid, k, now + i * 1e-3)
                                                                                                    for i, k in enumerate(picked)])
        return {"categories": picked}

    def learn(self, uid, on):
        self.s.x("INSERT INTO prefs(user_id, learn) VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET learn=excluded.learn", (uid, int(bool(on))))
        return {"learn": bool(on)}

    def reset(self, uid):
        """Oublie, pour l'ordre des deals, les fiches ouvertes et les clics d'avant (ils restent dans les mesures de conversion)."""
        now = self.clock()
        self.s.x("INSERT INTO prefs(user_id, reset_at) VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET reset_at=excluded.reset_at", (uid, now))
        return {"reset_at": now}
