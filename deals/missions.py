"""Missions : vos recherches sauvegardées, que Deals surveille. « Aspirateur balai sous 300 € », « canapé velours », « tout
produit comparable à celui-ci » : ce que la Recherche a compris (query.read), gardé et relu sur le catalogue publié.

Une mission dit ce qu'on veut — un rayon et, si on l'a précisé, des fonctions (balai, sans fil…), une taille, une
capacité, une classe énergie, une marque, des mots (« velours »), une promo, un budget ; ou bien un produit précis. Le
prix maximum est facultatif : avec lui, la mission est « atteinte » quand un produit y arrive ; sans lui, elle suit les
nouveautés. Dans l'app, chaque mission dit ce qui est nouveau depuis qu'on l'a ouverte (seen). La nuit, après la
publication, `notify` envoie à chacun au plus un e-mail — seulement aux comptes qui ont donné leur adresse, pour les
missions dont l'alerte est active : les produits qui viennent d'arriver, ou qui sont descendus plus bas que lors du
dernier e-mail. Jamais deux fois le même produit au même prix ; ce que la personne voyait déjà en sauvegardant n'est pas
renvoyé. Une seule mission par cible : la même recherche sauvegardée deux fois change seulement son prix.

Depuis une fiche, « tout produit comparable » (`like`, pur) : même catégorie, mêmes fonctions, même taille ou capacité.
"""
import json
import re
import time
from collections import defaultdict
from email.message import EmailMessage

from . import journey, ontology, query
from .catalog import cheap, enrich, matches as named_by, tokens
from .errors import BadRequest, NotFound, Unavailable
from .extract.categories import FAMILY_OF, plain
from .labels import CATEGORY_LABEL, CATEGORY_ONE, FEATURE_LABEL, ROOMS
from .query import AT_LEAST, AT_MOST, EXACT, FORM, NEAR, ONLY, WANTED, euros  # noqa: F401  (relus par les tests et les bancs)

MAX_MISSIONS = 20
MAX_PRICE = query.MAX_PRICE
MAIL_PER_MISSION = 5                                       # les moins chers ; les autres sont dans l'app
LIKE = ("bed_size", "width_cm", "capacity_kg", "place_settings", "zones", "seats")     # « comparable » : taille, capacité
MAX_WORDS = 6


def interpret(text, brands=()):
    """Une phrase → une mission : {category, brand, features, attrs, max_price} (query.read). Rien de deviné : ce qui
    n'est pas dit n'est pas demandé. BadRequest si on ne sait pas ce qui est cherché, ou si ce n'est pas suivi."""
    raw = (text or "").strip()
    if not raw or len(raw) > 200:
        raise BadRequest("Dites ce que vous cherchez, par exemple : aspirateur balai sous 300 €")
    r = query.read(raw, brands)
    if r["unsupported"]:
        raise BadRequest(f"Les {CATEGORY_LABEL.get(r['unsupported'], r['unsupported']).lower()} ne sont pas encore suivis : "
                         "électroménager, ameublement et literie seulement")
    if not r["category"] and not r["brand"] and not r["domain"]:
        raise BadRequest("Je n'ai pas reconnu le produit : essayez « lave-linge 9 kg sous 500 € » ou « matelas 160x200 »")
    return {"category": r["category"], "brand": r["brand"], "features": r["features"], "attrs": r["attrs"], "max_price": r["max_price"],
            **({k: r[k] for k in ("domain", "sub", "needs", "props")} if r["domain"] else {})}


def normalize(spec):
    """Une recherche gardée avant l'ontologie de son domaine (v56 : « aspirateur » et des fonctions : balai, sans fil,
    laveur) : relue comme la même phrase l'est aujourd'hui — le domaine (robots compris), le type, les caractéristiques
    exigées, les besoins (un robot « laveur » : laver le sol). Les autres restent telles quelles."""
    cat = spec.get("category")
    d = ontology.domain_of(cat) if cat and not spec.get("product_id") else None
    if d is None:
        return spec
    feats, needs, props = list(spec.get("features") or []), list(spec.get("needs") or []), dict(spec.get("props") or {})
    sub = spec.get("sub") or next((x["key"] for x in d.subs if x["match"]["category"] == [cat] and not x["match"].get("any")), None)
    for f in ("laveur", "balai", "traineau"):              # « balai laveur » : un laveur
        if f in feats:
            if sub == "robot" and f == "laveur":
                needs.append("lavage")
            elif sub is None:
                sub = f
    if "sans_fil" in feats:
        props["cordless"] = True
    return {**spec, "category": None, "domain": d.key, "sub": sub, "needs": list(dict.fromkeys(needs)), "props": props,
            "features": [f for f in feats if f not in query.DOMAIN_FEATURES]}


def like(p):
    """Ce qui rend un produit comparable à p (category, attrs) : sa catégorie, ses fonctions, sa taille ou sa capacité ;
    ni sa marque, ni sa classe énergie, ni son bruit."""
    a, cat = p["attrs"] or {}, p["category"]
    return {"category": cat, "features": [f for f in a.get("features", []) if f in FEATURE_LABEL],
            "attrs": {k: a[k] for k in LIKE if k in a and cat in ONLY.get(k, {cat})}}


def matches(m, p):
    """Le produit p (product_id, category, brand, price, in_stock, attrs ; pct, search et le verdict de prix pour la
    promo et le prix bas) répond-il à la mission m ?"""
    return matcher(m)(p)


def matcher(m):
    """matches, préparé une fois pour une mission (la nuit : des milliers de produits par mission). Des besoins (un
    domaine à ontologie) : le produit doit les satisfaire tout à fait, d'après ce qu'on sait de lui (un besoin dont la
    fiche ne dit rien n'est pas promis) ; ce que le type demandé ne peut pas satisfaire est mis à part, comme dans la
    Recherche (« un robot ne monte pas les marches » : la recherche gardée répond comme la recherche)."""
    top, floor, pid, off, low = m.get("max_price"), m.get("min_price"), m.get("product_id"), m.get("off"), m.get("low")
    fit, toks = query.fitter(m), tokens(" ".join(m["words"])) if m.get("words") else None
    d = ontology.DOMAINS.get(m.get("domain")) if m.get("domain") else None
    needs = m.get("needs") or ()
    plan = journey.Plan(d, needs, drop={c for c, _, _ in journey.conflict(d, m.get("sub"), needs, weak=True)}) if d else None

    def ok(p):
        if not p["in_stock"] or top is not None and p["price"] > top or floor is not None and p["price"] < floor:
            return False
        if pid:
            return p["product_id"] == pid
        if not fit(p) or off and (p.get("pct") or 0) < off or low and not cheap(p):
            return False
        if plan:
            j = plan.judge(p["attrs"])
            if j["out"] or j["met"] < len(plan.strong):
                return False
        return not toks or named_by(p.get("search") or "", toks)
    return ok


def label(m, name=None):
    """« Aspirateur balai sans fil · 300 € max », « Lit 160 × 200 Nordvik · 700 € max », « Canapé « velours » · en promo »."""
    if m.get("product_id"):
        head = name or "Ce produit"
    else:
        f, a = m.get("features") or [], m.get("attrs") or {}
        d = ontology.DOMAINS.get(m.get("domain")) if m.get("domain") else None
        bits = [CATEGORY_ONE.get(m["category"], m["category"])] if m.get("category") else \
            [d.sub[m["sub"]]["one"] if m.get("sub") in d.sub else d.one] if d else [ROOMS[m["room"]][0]] if m.get("room") in ROOMS else []
        bits += [FEATURE_LABEL[x].lower() for x in FORM if x in f] + [FEATURE_LABEL[x].lower() for x in FEATURE_LABEL if x in f and x not in FORM]
        if d:
            bits += [d.props[k]["yes" if v else "no"].lower() for k, v in (m.get("props") or {}).items() if k in d.props]
        fmt = {"bed_size": lambda v: v.replace("x", " × "), "width_cm": "{:g} cm".format, "capacity_kg": lambda v: f"{v:g} kg".replace(".", ","),
               "place_settings": "{:g} couverts".format, "zones": "{:g} foyers".format, "volume_l": "{:g} L".format,
               "autonomy_min": "{:g} min".format, "seats": "{:g} places".format, "energy_class": "classe {}".format, "noise_db": "{:g} dB".format}
        bits += [fmt[k](a[k]) for k in fmt if k in a]
        if m.get("brand"):
            bits.append(m["brand"])
        if m.get("words"):
            bits.append(f"« {' '.join(m['words'])} »")
        if d and m.get("needs"):                           # « silencieux », puis « pour les allergies et le parquet »
            said = [d.needs[n].get("phrase") or f"pour {d.needs[n]['label'].lower()}" for n in m["needs"] if n in d.needs]
            fors = [x[5:] for x in said if x.startswith("pour ")]
            both = ", ".join(fors[:-1]) + " et " + fors[-1] if len(fors) > 1 else "".join(fors)
            bits += [x for x in said if not x.startswith("pour ")] + ([f"pour {both}"] if fors else [])
        head = " ".join(bits)
        head = head[:1].upper() + head[1:]
    extra = (["en promo" if m["off"] <= 1 else f"−{m['off']:g} % et plus"] if m.get("off") else []) + (["prix bas"] if m.get("low") else []) \
        + ([f"dès {euros(m['min_price'])}"] if m.get("min_price") is not None else []) \
        + ([f"{euros(m['max_price'])} max"] if m.get("max_price") is not None else [])
    return " · ".join([head] + extra)


PARTNERS_NOTE = "Liens vers nos enseignes partenaires : si vous achetez, Deals touche une commission, sans surcoût pour vous."


def mission_message(to, items, base, sender):
    """Un e-mail par personne et par nuit : ses missions arrivées à son prix, et les produits concernés. Chaque produit
    mène en un clic à l'offre (« Voir l'offre », lien tracé : l'e-mail et la mission sont la source du clic) ou à sa fiche.
    items : (libellé, produits, identifiant de la mission)."""
    n = sum(len(hits) for _, hits, _ in items)
    subject = f"Mission accomplie : {items[0][0]}" if len(items) == 1 else f"{len(items)} missions accomplies, {n} produits à votre prix"
    text, html = ["Bonjour,", ""], ["<p>Bonjour,</p>"]
    for lab, hits, mid in items:
        text.append(f"Votre mission « {lab} » :")
        html.append(f"<p><b>Votre mission « {lab} »</b></p><ul>")
        for r in hits[:MAIL_PER_MISSION]:                  # les moins chers d'abord
            off = f" (−{r['pct']} %)" if r["pct"] else ""
            line = f"{r['brand']}, {r['name']} : {euros(r['price'])}{off}"
            page, offer = f"{base}/?p={r['product_id']}&from=mail&m={mid}", f"{base}/api/r/out/{r['offer_id']}?from=mail&m={mid}"
            text.append(f"- {line}\n  Voir l'offre : {offer}\n  La fiche : {page}")
            html.append(f'<li><a href="{page}">{line}</a> · <a href="{offer}" style="font-weight:700;color:#C2330B">Voir l\'offre</a></li>')
        if len(hits) > MAIL_PER_MISSION:
            more = len(hits) - MAIL_PER_MISSION
            text.append(f"- et {more} autre{'s' if more > 1 else ''} à votre prix : {base}/")
            html.append(f'<li><a href="{base}/">et {more} autre{"s" if more > 1 else ""} à votre prix</a></li>')
        text.append("")
        html.append("</ul>")
    text.append(f"Vos missions, pour les modifier ou les arrêter : {base}/")
    text.append(PARTNERS_NOTE)
    html.append(f'<p style="color:#5E6166">Vos missions, pour les modifier ou les arrêter : <a href="{base}/">Deals</a></p>')
    html.append(f'<p style="color:#5E6166;font-size:12px">{PARTNERS_NOTE}</p>')
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, sender, to
    msg.set_content("\n".join(text))
    msg.add_alternative("\n".join(html), subtype="html")
    return msg


class Missions:
    def __init__(self, store, catalog, clock=time.time):
        self.s, self.c, self.clock = store, catalog, clock
        self._memo = (None, {})                            # produits lus, valables jusqu'à la publication suivante

    def _day_memo(self):
        """Les produits lus le jour, partagés entre les requêtes : le catalogue ne change qu'à la publication de nuit."""
        at = self.c.published_at()
        if self._memo[0] != at:
            self._memo = (at, {})
        return self._memo[1]

    # ------------------------------------------------------------------ lecture du catalogue publié
    def _rows(self, spec):
        """Les produits publiés que la mission peut viser (colonnes légères), du moins cher au plus cher : une mission
        ne lit en détail que ceux sous son prix ; des mots : seulement les produits qui les contiennent."""
        room = ROOMS.get(spec.get("room"), (None, ()))[1] or (ontology.DOMAINS[spec["domain"]].categories if spec.get("domain") in ontology.DOMAINS else ())
        where, args = (" WHERE c.product_id=?", (spec["product_id"],)) if spec.get("product_id") else \
            (" WHERE c.category=?", (spec["category"],)) if spec.get("category") else \
            (f" WHERE c.category IN ({','.join('?' * len(room))})", tuple(room)) if room else \
            (" WHERE lower(c.brand)=lower(?)", (spec["brand"],)) if spec.get("brand") else ("", ())
        for t in tokens(" ".join(spec.get("words") or [])):   # des mots : les seuls produits qui les ont (matches confirme)
            where, args = where + (" AND" if where else " WHERE") + " c.search LIKE ?", args + ((f"%{t}%" if " " in t else f"% {t}%"),)
        return self.s.q("SELECT c.product_id, c.category, c.brand, c.name, c.price, c.pct, c.attrs, c.offer_id, c.search, c.level, "
                        "c.span, c.usual, o.availability FROM catalog c LEFT JOIN catalog_offers o ON o.product_id=c.product_id "
                        "AND o.rank=0" + where + " ORDER BY c.price, c.product_id", args)

    @staticmethod
    def _product(r):
        return {"product_id": r["product_id"], "category": r["category"], "brand": r["brand"], "price": r["price"], "pct": r["pct"],
                "in_stock": r["availability"] != "out_of_stock", "attrs": enrich(json.loads(r["attrs"] or "{}"), r), "search": r["search"],
                "level": r["level"], "span": r["span"], "usual": r["usual"]}

    def _match(self, spec, rows=None, nearest=True, memo=None):
        """(produits au prix, du moins cher au plus cher ; s'il n'y en a pas, le moins cher qui y répond, prix mis à
        part). memo : produits déjà lus, partagés entre les missions d'une même nuit."""
        rows = self._rows(spec) if rows is None else rows
        memo = self._day_memo() if memo is None else memo
        prod = lambda r: memo.get(r["product_id"]) or memo.setdefault(r["product_id"], self._product(r))
        top, hits, stop, ok = spec.get("max_price"), [], len(rows), matcher(spec)
        for i, r in enumerate(rows):
            if top is not None and r["price"] > top:
                stop = i
                break
            if ok(prod(r)):
                hits.append(r)
        if hits or not nearest or top is None:
            return hits, None
        free = matcher({**spec, "max_price": None})        # ceux sous le prix ont échoué pour une autre raison
        return hits, next((r for r in rows[stop:] if free(prod(r))), None)

    def _name(self, pid):
        r = self.s.q("SELECT brand, name, title FROM catalog WHERE product_id=?", (pid,), one=True)
        return " ".join(x for x in (r["brand"], r["name"] or r["title"]) if x) if r else None

    def _brands(self):
        return [r["brand"] for r in self.s.q("SELECT DISTINCT brand FROM catalog WHERE brand IS NOT NULL")]

    # ------------------------------------------------------------------ ce qu'on demande
    def _spec(self, body, need_price):
        try:
            price = None if body.get("max_price") in (None, "") else float(body["max_price"])
            floor = None if body.get("min_price") in (None, "") else float(body["min_price"])
            off = None if body.get("off") in (None, "", 0) else int(body["off"])
            pid = int(body["product_id"]) if body.get("product_id") else None
            ref = int(body["like"]) if body.get("like") else None
        except (TypeError, ValueError):
            raise BadRequest("Prix ou produit invalide")
        if ref:                                            # « tout produit comparable » à celui de la fiche
            r = self.s.q("SELECT category, attrs FROM catalog WHERE product_id=?", (ref,), one=True)
            if not r:
                raise NotFound("produit inconnu")
            body, pid = {**like({"category": r["category"], "attrs": json.loads(r["attrs"] or "{}")}), "max_price": price}, None
            floor = off = None
        if price is None and need_price:
            raise BadRequest("Indiquez votre prix maximum")
        for v in (price, floor):
            if v is not None and not 1 <= v <= MAX_PRICE:
                raise BadRequest("Prix invalide")
        if price is not None and floor is not None and floor >= price:
            floor = None
        if off is not None and not 1 <= off <= 90:
            raise BadRequest("Remise invalide")
        if pid:
            name = self._name(pid)
            if name is None:
                raise NotFound("produit inconnu")
            return {"product_id": pid, "category": None, "brand": None, "features": [], "attrs": {}, "max_price": price,
                    "name": name}
        cat = body.get("category") or None
        if cat and cat not in FAMILY_OF:
            raise BadRequest("Catégorie non suivie")
        brand = body.get("brand") or None
        if brand:
            known = {b.lower(): b for b in self._brands()}
            if brand.lower() not in known:
                raise BadRequest("Marque inconnue")
            brand = known[brand.lower()]
        words = body.get("words") or []
        if not isinstance(words, list) or len(words) > MAX_WORDS:
            raise BadRequest("Mots invalides")
        words = list(dict.fromkeys(w for w in (" ".join(plain(str(x)).split())[:30] for x in words) if w))
        room = body.get("room") or None
        if room is not None and room not in ROOMS:
            raise BadRequest("Pièce inconnue")
        dom = body.get("domain") or None                   # un domaine à ontologie : type, besoins, caractéristiques exigées
        d = ontology.DOMAINS.get(dom) if dom else None
        if dom and d is None:
            raise BadRequest("Domaine inconnu")
        if cat or d:
            room = None
        if not cat and not room and not brand and not words and not d:
            raise BadRequest("Dites ce que vous cherchez : une catégorie, une pièce, une marque, des mots ou un produit")
        feats = [f for f in body.get("features") or [] if f in FEATURE_LABEL]
        attrs = {k: v for k, v in (body.get("attrs") or {}).items() if k in WANTED and isinstance(v, (int, float, str))}
        out = {"product_id": None, "category": cat, "room": room, "brand": brand, "features": feats, "attrs": attrs, "max_price": price,
               "min_price": floor, "off": off, "low": bool(body.get("low")), "words": words}
        if d:
            sub = body.get("sub") or None
            if sub is not None and sub not in d.sub:
                raise BadRequest("Type inconnu")
            needs = body.get("needs") or []
            props = body.get("props") or {}
            if not isinstance(needs, list) or not isinstance(props, dict) or any(n not in d.needs for n in needs) \
                    or any(k not in d.props or d.props[k]["type"] != "bool" for k in props):
                raise BadRequest("Critère inconnu")
            out.update(domain=dom, sub=sub, needs=list(dict.fromkeys(needs)), props={k: bool(v) for k, v in props.items()})
        return normalize(out)                              # « aspirateur balai » d'avant : comme aujourd'hui

    @staticmethod
    def _want(spec):
        """Ce qui est cherché, en plus du rayon et de la marque (colonne want) : seulement ce qui est dit, pour qu'une même
        recherche se reconnaisse (une mission d'avant la v56 n'a que features et attrs)."""
        w = {"features": sorted(spec.get("features") or []), "attrs": spec.get("attrs") or {}}
        w.update({k: spec[k] for k in ("words", "off", "low", "min_price", "room", "domain", "sub", "needs", "props") if spec.get(k)})
        return json.dumps(w, sort_keys=True)

    def _cards(self, uid, rows):
        """Cartes de l'app pour quelques produits (lignes complètes du catalogue), dans l'ordre donné."""
        ids = [r["product_id"] for r in rows]
        full = {r["product_id"]: r for r in self.s.q(f"SELECT * FROM catalog WHERE product_id IN ({','.join('?' * len(ids))})", ids)} if ids else {}
        return self.c.cards(uid, [full[i] for i in ids])

    @staticmethod
    def _fresh(hits, seen):
        """Les produits nouveaux, ou moins chers d'au moins 0,50 €, depuis le dernier regard (seen : produit → prix)."""
        return [h for h in hits if str(h["product_id"]) not in seen or h["price"] < seen[str(h["product_id"])] - 0.5]

    def _view(self, uid, spec, mid=None, created_at=None, seen=None, alert=None):
        hits, nearest = self._match(spec)
        fresh = self._fresh(hits, seen) if seen is not None else []
        out = {"id": mid, "product_id": spec.get("product_id"), "category": spec.get("category"), "brand": spec.get("brand"),
               "features": spec.get("features") or [], "attrs": spec.get("attrs") or {}, "max_price": spec.get("max_price"),
               "min_price": spec.get("min_price"), "off": spec.get("off"), "low": bool(spec.get("low")), "words": spec.get("words") or [],
               "room": spec.get("room"), "domain": spec.get("domain"), "sub": spec.get("sub"), "needs": spec.get("needs") or [],
               "props": spec.get("props") or {},
               "label": label(spec, spec.get("name")), "kind": CATEGORY_ONE.get(spec.get("category")) if spec.get("category") else None,
               # ce qui est guetté, sans le prix : « Aspirateur balai sans fil », « Zephyr V8 »
               "title": (self._name(spec["product_id"]) or "Produit retiré du suivi") if spec.get("product_id")
               else label({**spec, "max_price": None}),
               "matches": self._cards(uid, hits[:8]), "total": len(hits), "fresh": len(fresh),
               "reached": spec.get("max_price") is not None and bool(hits),
               "nearest": self._cards(uid, [nearest])[0] if nearest is not None else None}
        if created_at is not None:
            out["created_at"] = created_at
        if alert is not None:
            out["alert"] = bool(alert)
        return out

    def interpret_text(self, uid, text):
        """Aperçu d'une phrase, avant de lancer la mission (sans compte) : ce qui est compris, ce qui y répond déjà."""
        return self._view(uid, self._spec(interpret(text, self._brands()), need_price=False))

    def preview(self, uid, body):
        return self._view(uid, self._spec(body or {}, need_price=False))

    def pending(self, body):
        """Une mission lancée avant la connexion : vérifiée tout de suite, puis gardée avec le lien de connexion et lancée
        quand il est ouvert, sur n'importe quel appareil. → (la mission en JSON, son libellé), ou (None, None)."""
        if body is None:
            return None, None
        if not isinstance(body, dict):
            raise BadRequest("Mission invalide")
        spec = self._spec(body, need_price=True)
        keep = {k: spec[k] for k in ("product_id", "category", "room", "brand", "features", "attrs", "max_price", "min_price", "off", "low",
                                     "words", "domain", "sub", "needs", "props") if spec.get(k) not in (None, [], {}, False)}
        return json.dumps(keep, ensure_ascii=False), label(spec, spec.get("name"))

    # ------------------------------------------------------------------ les missions d'une personne
    def create(self, uid, body):
        """Sauvegarde une recherche (une mission) ; le prix maximum est facultatif. La même cible déjà suivie (même produit,
        ou mêmes rayon, marque et souhaits) change seulement de prix : pas de doublon, même depuis deux onglets."""
        spec = self._spec(body or {}, need_price=False)
        want = self._want(spec)
        self._renew(uid, self.s.q("SELECT * FROM missions WHERE user_id=?", (uid,)))    # une recherche d'avant : réécrite d'abord
        hits, _ = self._match(spec, nearest=False)
        seen = json.dumps({str(r["product_id"]): r["price"] for r in hits})   # déjà sous les yeux : ni nouveauté ni e-mail
        lab, now = label(spec, spec.get("name")), self.clock()
        with self.s.tx() as c:
            same = c.execute("SELECT id, created_at, alert FROM missions WHERE user_id=? AND product_id IS ? AND category IS ? "
                             "AND brand IS ? AND want=?", (uid, spec["product_id"], spec["category"], spec["brand"], want)).fetchone()
            if same:
                c.execute("UPDATE missions SET max_price=?, label=?, notified=?, seen=?, opened_at=? WHERE id=?",
                          (spec["max_price"], lab, seen, seen, now, same[0]))
                return self._view(uid, spec, same[0], same[1], json.loads(seen), same[2])
            if c.execute("SELECT COUNT(*) FROM missions WHERE user_id=?", (uid,)).fetchone()[0] >= MAX_MISSIONS:
                raise BadRequest(f"{MAX_MISSIONS} recherches sauvegardées au plus : retirez-en une d'abord")
            mid = c.execute("INSERT INTO missions(user_id, product_id, category, brand, want, max_price, label, created_at, notified, "
                            "seen, opened_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (uid, spec["product_id"], spec["category"], spec["brand"], want, spec["max_price"], lab, now, seen,
                             seen, now)).lastrowid
        return self._view(uid, spec, mid, now, json.loads(seen), 1)

    def _spec_of(self, row):
        return normalize(self._stored(row))

    @staticmethod
    def _stored(row):
        want = json.loads(row["want"] or "{}")
        return {"product_id": row["product_id"], "category": row["category"], "brand": row["brand"],
                "features": want.get("features", []), "attrs": want.get("attrs", {}), "max_price": row["max_price"],
                "min_price": want.get("min_price"), "off": want.get("off"), "low": bool(want.get("low")), "words": want.get("words", []),
                "room": want.get("room"), "domain": want.get("domain"), "sub": want.get("sub"), "needs": want.get("needs", []),
                "props": want.get("props", {})}

    def _mine(self, uid, mid):
        try:
            mid = int(mid)
        except (TypeError, ValueError):
            raise BadRequest("Mission invalide")
        row = self.s.q("SELECT * FROM missions WHERE id=? AND user_id=?", (mid, uid), one=True) if uid is not None else None
        if not row:
            raise NotFound("mission inconnue")
        return row

    def list(self, uid):
        """Les missions d'une personne, avec ce qui y répond, ce qui est nouveau depuis qu'elle les a ouvertes, et si
        elles sont atteintes ; rien pour une personne qui n'a encore rien gardé."""
        rows = self.s.q("SELECT * FROM missions WHERE user_id=? ORDER BY created_at DESC, id DESC", (uid,)) if uid is not None else []
        rows = self._renew(uid, rows)
        views = []
        for r in rows:
            v = self._view(uid, self._spec_of(r), r["id"], r["created_at"], json.loads(r["seen"] or r["notified"] or "{}"), r["alert"])
            v["label"] = r["label"]
            views.append(v)
        return {"missions": views, "reached": sum(v["reached"] for v in views), "fresh": sum(v["fresh"] > 0 for v in views)}

    def _renew(self, uid, rows):
        """Les recherches gardées avant l'ontologie de leur domaine sont réécrites comme aujourd'hui (normalize), une fois ;
        la même recherche gardée deux fois (avant, après) n'en fait plus qu'une, la plus ancienne."""
        old = [(r, normalize(self._stored(r))) for r in rows if not r["product_id"] and normalize(self._stored(r)) != self._stored(r)]
        if not old:
            return rows
        with self.s.tx() as c:
            for r, spec in old:
                c.execute("UPDATE missions SET category=?, want=? WHERE id=?", (spec["category"], self._want(spec), r["id"]))
            c.execute("DELETE FROM missions WHERE user_id=? AND id NOT IN (SELECT MIN(id) FROM missions WHERE user_id=? "
                      "GROUP BY product_id, category, brand, want)", (uid, uid))
        return self.s.q("SELECT * FROM missions WHERE user_id=? ORDER BY created_at DESC, id DESC", (uid,))

    def seen(self, uid, mid):
        """La personne a ouvert la mission : ce qui y répond aujourd'hui n'est plus nouveau."""
        row = self._mine(uid, mid)
        hits, _ = self._match(self._spec_of(row), nearest=False)
        self.s.x("UPDATE missions SET seen=?, opened_at=? WHERE id=?",
                 (json.dumps({str(r["product_id"]): r["price"] for r in hits}), self.clock(), row["id"]))
        return {"ok": True}

    def alert(self, uid, mid, on):
        """Recevoir ou non l'e-mail de la nuit pour cette mission (il faut une adresse : accounts.attach)."""
        row = self._mine(uid, mid)
        self.s.x("UPDATE missions SET alert=? WHERE id=?", (int(bool(on)), row["id"]))
        return {"alert": bool(on)}

    def remove(self, uid, mid):
        row = self._mine(uid, mid)
        self.s.x("DELETE FROM missions WHERE id=?", (row["id"],))
        return {"ok": True}

    def caught_up(self, uid):
        """Une adresse vient d'être donnée : ce que la personne voit déjà dans l'app ne lui sera pas envoyé par e-mail."""
        for r in self.s.q("SELECT * FROM missions WHERE user_id=?", (uid,)):
            hits, _ = self._match(self._spec_of(r), nearest=False)
            self.s.x("UPDATE missions SET notified=? WHERE id=?", (json.dumps({str(h["product_id"]): h["price"] for h in hits}), r["id"]))

    # ------------------------------------------------------------------ la nuit
    def notify(self, outbox, base, sender="deals@localhost", limit=None, hold_above=None):
        """Après la publication : un e-mail par personne, pour les produits nouveaux à son prix ou moins chers qu'au
        dernier e-mail. Un envoi qui échoue (compté dans `failed`), ou qui dépasserait `limit` e-mails cette nuit (quota du
        fournisseur), ne marque rien comme envoyé : il repartira la nuit suivante. hold_above : garde contre un envoi
        massif anormal (night.py) : au-delà de ce nombre de personnes à prévenir, rien ne part ni n'est marqué (« held »),
        un responsable décide (deals.py approve)."""
        base = base.rstrip("/")
        rows = self.s.q("SELECT m.*, u.email FROM missions m JOIN users u ON u.id=m.user_id WHERE u.email IS NOT NULL AND m.alert=1 "
                        "ORDER BY m.user_id, m.id")              # sans adresse (compte invité) ou alerte coupée : l'app seulement
        cache, by_user = {}, defaultdict(list)
        for r in rows:
            spec = self._spec_of(r)
            key = (spec["product_id"], spec["category"], spec.get("room"), (spec["brand"] or "").lower())
            if key not in cache:
                cache[key] = (self._rows(spec), {})
            hits, _ = self._match(spec, *cache[key][:1], nearest=False, memo=cache[key][1])
            if not hits:
                continue                                         # rien à son prix : rien à envoyer ni à écrire
            sent = json.loads(r["notified"] or "{}")
            fresh = self._fresh(hits, sent)
            for h in hits:
                k = str(h["product_id"])
                sent[k] = min(h["price"], sent.get(k, h["price"]))
            by_user[r["email"]].append((r, fresh, sent))
        emails = products = deferred = failed = 0
        due = sum(any(fresh for _, fresh, _ in items) for items in by_user.values())
        if hold_above is not None and due > hold_above:
            return {"missions": len(rows), "emails": 0, "products": 0, "deferred": 0, "failed": 0, "held": due}
        for email, items in by_user.items():
            todo = [(r["label"], fresh, r["id"]) for r, fresh, _ in items if fresh]
            if todo and limit is not None and emails >= limit:
                deferred += 1                                   # quota atteint : la nuit suivante
                continue
            if todo:
                try:
                    outbox.send_mail(email, mission_message(email, todo, base, sender))
                except Unavailable:
                    failed += 1
                    continue                                    # rien n'est marqué : réessayé la nuit suivante
                emails += 1
                products += sum(len(f) for _, f, _ in todo)
            with self.s.tx() as c:                               # seulement ce qui a changé
                c.executemany("UPDATE missions SET notified=? WHERE id=?",
                              [(j, r["id"]) for r, _, sent in items if (j := json.dumps(sent)) != r["notified"]])
        return {"missions": len(rows), "emails": emails, "products": products, "deferred": deferred, "failed": failed}
