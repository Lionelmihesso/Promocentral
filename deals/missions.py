"""Missions : « je veux un aspirateur balai sous 300 €, préviens-moi ».

Une mission dit ce qu'on veut — une catégorie et, si on l'a précisé, des fonctions (balai, sans fil…), une taille, une
capacité, une classe énergie, une marque ; ou bien un produit précis — et un prix maximum. Elle s'écrit en une phrase
(`interpret`, pur), se vérifie sur le catalogue publié (`matches`, pur) et, la nuit, après la publication, `notify`
envoie à chacun au plus un e-mail : les produits qui viennent d'arriver à son prix, ou qui sont descendus plus bas que
lors du dernier e-mail. Jamais deux fois le même produit au même prix ; ce que la personne voit déjà dans l'app quand
elle lance la mission ne lui est pas renvoyé par e-mail.

Depuis une fiche, « tout produit comparable » (`like`, pur) : même catégorie, mêmes fonctions, même taille ou capacité.
Une seule mission par cible : relancer la même cible change son prix, sans doublon.
"""
import json
import re
import time
from collections import defaultdict
from email.message import EmailMessage

from .alternatives import energy_rank
from .catalog import CATEGORY_LABEL, CATEGORY_ONE, FEATURE_LABEL
from .errors import BadRequest, NotFound, Unavailable
from .extract import attributes, categorize
from .extract.categories import FAMILY_OF, plain

MAX_MISSIONS = 20
MAX_PRICE = 100_000
MAIL_PER_MISSION = 5                                       # les moins chers ; les autres sont dans l'app
AT_LEAST = {"capacity_kg", "place_settings", "zones", "volume_l", "autonomy_min", "seats"}   # au moins ce qui est demandé
EXACT = {"bed_size"}
NEAR = {"width_cm": 0.06}                                  # un appareil s'encastre au centimètre près
AT_MOST = {"noise_db"}
WANTED = AT_LEAST | EXACT | set(NEAR) | AT_MOST | {"energy_class"}
LIKE = ("bed_size", "width_cm", "capacity_kg", "place_settings", "zones", "seats")     # « comparable » : taille, capacité
FORM = ("balai", "traineau", "angle", "americain", "encastrable")          # dans un libellé, la forme vient d'abord
PRICE_RE = [re.compile(r"(?:sous|moins de|max(?:imum)?|jusqu'?a|en dessous de|pas plus de|budget|<|≤)\s*:?\s*(\d[\d\s.]*\d|\d)"),
            re.compile(r"(\d[\d\s.]*\d|\d)\s*(?:€|euros?\b|eur\b|balles\b)")]
SIZE_RE = re.compile(r"\b(\d{2,3})\s*(?:sur|par)\s*(\d{3})\b")        # « 160 sur 200 » → 160x200
# Mots du langage courant → catégorie (« lit », « canapés », « aspi », « meuble télé »…), en plus des mots-clés de
# l'extraction (« frigo », « lit coffre »…), y compris pour les catégories non suivies : on dit alors qu'elles ne le sont
# pas encore. Les plus longs d'abord.
SLANG = {"aspi": "aspirateur", "aspis": "aspirateur", "meuble tele": "meuble_tv", "tele": "televiseur", "tv": "televiseur",
         "sofa": "canape", "clic clac": "canape", "frigo": "refrigerateur", "congelo": "congelateur", "lampe": "luminaire",
         "lampadaire": "luminaire", "ordi": "ordinateur_portable", "pc portable": "ordinateur_portable", "ecouteurs": "casque_audio"}
WORDS = sorted({**{w: k for k in CATEGORY_LABEL for w in {plain(CATEGORY_LABEL[k]).replace("-", " "),
                                                          plain(CATEGORY_ONE.get(k, k)).replace("-", " "), k.replace("_", " ")}},
                **SLANG}.items(), key=lambda kv: -len(kv[0]))
# Une caractéristique qui n'a de sens que pour certaines catégories (« lit 2 places » n'est pas un nombre de places
# assises) : ailleurs, elle n'est pas retenue — sinon la mission ne serait jamais remplie.
ONLY = {"seats": {"canape", "fauteuil", "table"}, "bed_size": {"lit", "matelas", "sommier"},
        "capacity_kg": {"lave_linge", "seche_linge", "lave_linge_sechant"}, "place_settings": {"lave_vaisselle"},
        "zones": {"plaque_cuisson", "cuisiniere"}, "autonomy_min": {"aspirateur", "robot_aspirateur"}}


def euros(v):
    return f"{v:,.0f}".replace(",", " ") + " €"


def interpret(text, brands=()):
    """Une phrase → une mission : {category, brand, features, attrs, max_price}. Rien de deviné : ce qui n'est pas dit
    n'est pas demandé. BadRequest si on ne sait pas ce qui est cherché, ou si ce n'est pas suivi."""
    raw = (text or "").strip()
    if not raw or len(raw) > 200:
        raise BadRequest("Dites ce que vous cherchez, par exemple : aspirateur balai sous 300 €")
    t = SIZE_RE.sub(r"\1x\2", " ".join(plain(raw).replace("-", " ").split()))
    price = None
    for rx in PRICE_RE:
        m = rx.search(t)
        if m:
            price = float(re.sub(r"[\s.]", "", m.group(1)))
            t = (t[:m.start()] + " " + t[m.end():]).strip()        # le prix n'est pas une caractéristique
            break
    if price is not None and not 1 <= price <= MAX_PRICE:
        price = None                                           # impossible : il sera demandé
    category, _ = categorize(t)
    if not category:
        category = next((k for w, k in WORDS if re.search(rf"(?<!\w){re.escape(w)}s?(?!\w)", t)), None)
    if category and category not in FAMILY_OF:
        raise BadRequest(f"Les {CATEGORY_LABEL.get(category, category).lower()} ne sont pas encore suivis : électroménager, "
                         "ameublement et literie seulement")
    brand = next((b for b in sorted(brands, key=len, reverse=True) if b and re.search(rf"(?<!\w){re.escape(plain(b))}(?!\w)", t)), None)
    if not category and not brand:
        raise BadRequest("Je n'ai pas reconnu le produit : essayez « lave-linge 9 kg sous 500 € » ou « matelas 160x200 »")
    a = attributes(t)
    return {"category": category, "brand": brand, "features": [f for f in a.get("features", []) if f in FEATURE_LABEL],
            "attrs": {k: v for k, v in a.items() if k in WANTED and (not category or category in ONLY.get(k, {category}))},
            "max_price": price}


def like(p):
    """Ce qui rend un produit comparable à p (category, attrs) : sa catégorie, ses fonctions, sa taille ou sa capacité ;
    ni sa marque, ni sa classe énergie, ni son bruit."""
    a, cat = p["attrs"] or {}, p["category"]
    return {"category": cat, "features": [f for f in a.get("features", []) if f in FEATURE_LABEL],
            "attrs": {k: a[k] for k in LIKE if k in a and cat in ONLY.get(k, {cat})}}


def matches(m, p):
    """p (produit publié : category, brand, price, in_stock, attrs) remplit-il la mission m ?"""
    if not p["in_stock"] or (m.get("max_price") is not None and p["price"] > m["max_price"]):
        return False
    if m.get("product_id"):
        return p["product_id"] == m["product_id"]
    if m.get("category") and p["category"] != m["category"]:
        return False
    if m.get("brand") and (p["brand"] or "").lower() != m["brand"].lower():
        return False
    A = p["attrs"] or {}
    if not set(m.get("features") or ()) <= set(A.get("features", ())):
        return False
    for k, v in (m.get("attrs") or {}).items():
        a = A.get(k)
        if a is None:                                      # demandé mais inconnu : pas de promesse
            return False
        if k in AT_LEAST and a < v or k in EXACT and a != v or k in AT_MOST and a > v:
            return False
        if k in NEAR and abs(a - v) > NEAR[k] * v:
            return False
        if k == "energy_class" and (energy_rank(a) is None or energy_rank(v) is None or energy_rank(a) > energy_rank(v)):
            return False
    return True


def label(m, name=None):
    """« Aspirateur balai sans fil · 300 € max », « Lit 160 × 200 Nordvik · 700 € max »."""
    if m.get("product_id"):
        head = name or "Ce produit"
    else:
        f, a = m.get("features") or [], m.get("attrs") or {}
        bits = [CATEGORY_ONE.get(m["category"], m["category"])] if m.get("category") else []
        bits += [FEATURE_LABEL[x].lower() for x in FORM if x in f] + [FEATURE_LABEL[x].lower() for x in FEATURE_LABEL if x in f and x not in FORM]
        fmt = {"bed_size": lambda v: v.replace("x", " × "), "width_cm": "{:g} cm".format, "capacity_kg": lambda v: f"{v:g} kg".replace(".", ","),
               "place_settings": "{:g} couverts".format, "zones": "{:g} foyers".format, "volume_l": "{:g} L".format,
               "autonomy_min": "{:g} min".format, "seats": "{:g} places".format, "energy_class": "classe {}".format, "noise_db": "{:g} dB".format}
        bits += [fmt[k](a[k]) for k in fmt if k in a]
        if m.get("brand"):
            bits.append(m["brand"])
        head = " ".join(bits)
        head = head[:1].upper() + head[1:]
    return f"{head} · {euros(m['max_price'])} max" if m.get("max_price") is not None else head


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
        ne lit en détail que ceux sous son prix."""
        where, args = (" WHERE c.product_id=?", (spec["product_id"],)) if spec.get("product_id") else \
            (" WHERE c.category=?", (spec["category"],)) if spec.get("category") else (" WHERE lower(c.brand)=lower(?)", (spec["brand"],))
        rows = self.s.q("SELECT c.product_id, c.category, c.brand, c.name, c.price, c.pct, c.attrs, c.offer_id, o.availability FROM catalog c "
                        "LEFT JOIN catalog_offers o ON o.product_id=c.product_id AND o.rank=0" + where + " ORDER BY c.price, c.product_id", args)
        return rows

    @staticmethod
    def _product(r):
        return {"product_id": r["product_id"], "category": r["category"], "brand": r["brand"], "price": r["price"],
                "in_stock": r["availability"] != "out_of_stock", "attrs": json.loads(r["attrs"] or "{}")}

    def _match(self, spec, rows=None, nearest=True, memo=None):
        """(produits au prix, du moins cher au plus cher ; s'il n'y en a pas, le moins cher qui y répond, prix mis à
        part). memo : produits déjà lus, partagés entre les missions d'une même nuit."""
        rows = self._rows(spec) if rows is None else rows
        memo = self._day_memo() if memo is None else memo
        prod = lambda r: memo.get(r["product_id"]) or memo.setdefault(r["product_id"], self._product(r))
        top, hits, stop = spec.get("max_price"), [], len(rows)
        for i, r in enumerate(rows):
            if top is not None and r["price"] > top:
                stop = i
                break
            if matches(spec, prod(r)):
                hits.append(r)
        if hits or not nearest:
            return hits, None
        free = {**spec, "max_price": None}                 # ceux sous le prix ont échoué pour une autre raison
        return hits, next((r for r in rows[stop:] if matches(free, prod(r))), None)

    def _name(self, pid):
        r = self.s.q("SELECT brand, name, title FROM catalog WHERE product_id=?", (pid,), one=True)
        return " ".join(x for x in (r["brand"], r["name"] or r["title"]) if x) if r else None

    def _brands(self):
        return [r["brand"] for r in self.s.q("SELECT DISTINCT brand FROM catalog WHERE brand IS NOT NULL")]

    # ------------------------------------------------------------------ ce qu'on demande
    def _spec(self, body, need_price):
        try:
            price = None if body.get("max_price") in (None, "") else float(body["max_price"])
            pid = int(body["product_id"]) if body.get("product_id") else None
            ref = int(body["like"]) if body.get("like") else None
        except (TypeError, ValueError):
            raise BadRequest("Prix ou produit invalide")
        if ref:                                            # « tout produit comparable » à celui de la fiche
            r = self.s.q("SELECT category, attrs FROM catalog WHERE product_id=?", (ref,), one=True)
            if not r:
                raise NotFound("produit inconnu")
            body, pid = {**like({"category": r["category"], "attrs": json.loads(r["attrs"] or "{}")}), "max_price": price}, None
        if price is None and need_price:
            raise BadRequest("Indiquez votre prix maximum")
        if price is not None and not 1 <= price <= MAX_PRICE:
            raise BadRequest("Prix maximum invalide")
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
        if not cat and not brand:
            raise BadRequest("Dites ce que vous cherchez : une catégorie, une marque ou un produit")
        feats = [f for f in body.get("features") or [] if f in FEATURE_LABEL]
        attrs = {k: v for k, v in (body.get("attrs") or {}).items() if k in WANTED and isinstance(v, (int, float, str))}
        return {"product_id": None, "category": cat, "brand": brand, "features": feats, "attrs": attrs, "max_price": price}

    def _cards(self, uid, rows):
        """Cartes de l'app pour quelques produits (lignes complètes du catalogue), dans l'ordre donné."""
        ids = [r["product_id"] for r in rows]
        full = {r["product_id"]: r for r in self.s.q(f"SELECT * FROM catalog WHERE product_id IN ({','.join('?' * len(ids))})", ids)} if ids else {}
        return self.c.cards(uid, [full[i] for i in ids])

    def _view(self, uid, spec, mid=None, created_at=None):
        hits, nearest = self._match(spec)
        out = {"id": mid, "product_id": spec.get("product_id"), "category": spec.get("category"), "brand": spec.get("brand"),
               "features": spec.get("features") or [], "attrs": spec.get("attrs") or {}, "max_price": spec.get("max_price"),
               "label": label(spec, spec.get("name")), "kind": CATEGORY_ONE.get(spec.get("category")) if spec.get("category") else None,
               # ce qui est guetté, sans le prix : « Aspirateur balai sans fil », « Zephyr V8 »
               "title": (self._name(spec["product_id"]) or "Produit retiré du suivi") if spec.get("product_id")
               else label({**spec, "max_price": None}),
               "matches": self._cards(uid, hits[:8]), "total": len(hits),
               "nearest": self._cards(uid, [nearest])[0] if nearest is not None else None}
        if created_at is not None:
            out["created_at"] = created_at
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
        keep = {k: spec[k] for k in ("product_id", "category", "brand", "features", "attrs", "max_price") if spec.get(k) not in (None, [], {})}
        return json.dumps(keep, ensure_ascii=False), label(spec, spec.get("name"))

    # ------------------------------------------------------------------ les missions d'une personne
    def create(self, uid, body):
        """Lance une mission ; la même cible déjà suivie (même produit, ou mêmes catégorie, marque et souhaits) change
        seulement de prix : pas de doublon, même si deux onglets la lancent après la connexion."""
        spec = self._spec(body or {}, need_price=True)
        want = json.dumps({"features": sorted(spec["features"]), "attrs": spec["attrs"]}, sort_keys=True)
        hits, _ = self._match(spec, nearest=False)
        seen = json.dumps({str(r["product_id"]): r["price"] for r in hits})   # déjà sous les yeux : pas d'e-mail pour eux
        lab, now = label(spec, spec.get("name")), self.clock()
        with self.s.tx() as c:
            same = c.execute("SELECT id, created_at FROM missions WHERE user_id=? AND product_id IS ? AND category IS ? "
                             "AND brand IS ? AND want=?", (uid, spec["product_id"], spec["category"], spec["brand"], want)).fetchone()
            if same:
                c.execute("UPDATE missions SET max_price=?, label=?, notified=? WHERE id=?", (spec["max_price"], lab, seen, same[0]))
                return self._view(uid, spec, same[0], same[1])
            if c.execute("SELECT COUNT(*) FROM missions WHERE user_id=?", (uid,)).fetchone()[0] >= MAX_MISSIONS:
                raise BadRequest(f"{MAX_MISSIONS} missions au plus : arrêtez-en une d'abord")
            mid = c.execute("INSERT INTO missions(user_id, product_id, category, brand, want, max_price, label, created_at, notified) "
                            "VALUES (?,?,?,?,?,?,?,?,?)", (uid, spec["product_id"], spec["category"], spec["brand"], want,
                                                           spec["max_price"], lab, now, seen)).lastrowid
        return self._view(uid, spec, mid, now)

    def _spec_of(self, row):
        want = json.loads(row["want"] or "{}")
        return {"product_id": row["product_id"], "category": row["category"], "brand": row["brand"],
                "features": want.get("features", []), "attrs": want.get("attrs", {}), "max_price": row["max_price"]}

    def list(self, uid):
        rows = self.s.q("SELECT * FROM missions WHERE user_id=? ORDER BY created_at DESC, id DESC", (uid,))
        views = []
        for r in rows:
            v = self._view(uid, self._spec_of(r), r["id"], r["created_at"])
            v["label"] = r["label"]
            views.append(v)
        return {"missions": views, "reached": sum(v["total"] > 0 for v in views)}

    def remove(self, uid, mid):
        try:
            mid = int(mid)
        except (TypeError, ValueError):
            raise BadRequest("Mission invalide")
        if not self.s.conn().execute("DELETE FROM missions WHERE id=? AND user_id=?", (mid, uid)).rowcount:
            raise NotFound("mission inconnue")
        return {"ok": True}

    # ------------------------------------------------------------------ la nuit
    def notify(self, outbox, base, sender="deals@localhost", limit=None, hold_above=None):
        """Après la publication : un e-mail par personne, pour les produits nouveaux à son prix ou moins chers qu'au
        dernier e-mail. Un envoi qui échoue (compté dans `failed`), ou qui dépasserait `limit` e-mails cette nuit (quota du
        fournisseur), ne marque rien comme envoyé : il repartira la nuit suivante. hold_above : garde contre un envoi
        massif anormal (night.py) : au-delà de ce nombre de personnes à prévenir, rien ne part ni n'est marqué (« held »),
        un responsable décide (deals.py approve)."""
        base = base.rstrip("/")
        rows = self.s.q("SELECT m.*, u.email FROM missions m JOIN users u ON u.id=m.user_id ORDER BY m.user_id, m.id")
        cache, by_user = {}, defaultdict(list)
        for r in rows:
            spec = self._spec_of(r)
            key = (spec["product_id"], spec["category"], (spec["brand"] or "").lower())
            if key not in cache:
                cache[key] = (self._rows(spec), {})
            hits, _ = self._match(spec, *cache[key][:1], nearest=False, memo=cache[key][1])
            if not hits:
                continue                                         # rien à son prix : rien à envoyer ni à écrire
            sent = json.loads(r["notified"] or "{}")
            fresh = [h for h in hits if str(h["product_id"]) not in sent or h["price"] < sent[str(h["product_id"])] - 0.5]
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
