"""Quarantaine des prix suspects : une offre relue à moins de 30 % du prix habituel de son produit (la médiane des jours
relevés, au moins 14 jours : catalog.usual, de la publication précédente) n'est plus publiée ; le flux de son enseigne
la relit les nuits suivantes (ingest/). Revenue à son prix habituel, elle est libérée et le prix suspect est écarté des
courbes et des verdicts (prices.rejected) : c'était une erreur. Relue au même prix les CONFIRM nuits suivantes, le prix
est cru, l'offre libérée, et ce prix-là n'est plus suspecté. Une erreur de prix d'un soir n'atteint ainsi ni l'app ni les e-mails
des missions. Règle versionnée (RULE), citée par chaque décision ; les décisions sont des actions de l'agent (agent.py),
journalisées ; un responsable peut libérer une offre à la main (deals.py quarantine release <offre>).
"""
DROP = 0.70             # à moins de 30 % du prix habituel : suspect
CONFIRM = 2             # nuits suivantes au même prix pour le croire
SAME = 0.01             # même prix : à 1 % près
RULE = f"q1 : moins de {round((1 - DROP) * 100)} % du prix habituel ; cru s'il est relu au même prix les {CONFIRM} nuits suivantes"
BACK = "revenu à son prix habituel"
BELIEVED = f"cru : relu au même prix les {CONFIRM} nuits suivantes"


def suspicious(price, usual):
    return bool(usual) and price is not None and price < (1 - DROP) * usual


def same(a, b):
    return abs(a - b) <= SAME * max(a, b)


def review(store, night_start, day):
    """Les décisions de la nuit → (mettre en quarantaine, confirmer une nuit de plus, libérer), d'après les offres relues
    depuis night_start. Lit la base, n'écrit rien."""
    rows = store.q("SELECT o.id AS offer_id, o.product_id, o.retailer, o.merchant, pr.title, p.id AS price_id, p.price, c.usual "
                   "FROM offers o JOIN products pr ON pr.id=o.product_id "
                   "JOIN prices p ON p.id=(SELECT id FROM prices WHERE offer_id=o.id AND rejected=0 ORDER BY first_seen DESC, id DESC LIMIT 1) "
                   "JOIN catalog c ON c.product_id=o.product_id WHERE p.last_seen>=? AND c.usual IS NOT NULL ORDER BY o.id",
                   (night_start,))
    known = {r["offer_id"]: r for r in store.q("SELECT * FROM quarantine")}
    hold, confirm, release = [], [], []
    for r in rows:
        q = known.get(r["offer_id"])
        if q is None or q["status"] != "held":
            accepted = q is not None and (q["reason"] == BELIEVED or (q["reason"] or "").startswith("libéré")) \
                and same(r["price"], q["price"])
            if suspicious(r["price"], r["usual"]) and not accepted:
                hold.append(r)
        elif q["checked_day"] == day:
            continue                                         # déjà compté cette nuit
        elif not suspicious(r["price"], q["usual"]):
            release.append({**r, "why": BACK})
        elif not same(r["price"], q["price"]):
            hold.append(r)                                   # un autre prix, toujours suspect : on recommence
        elif q["confirmed"] + 1 >= CONFIRM:
            release.append({**r, "why": BELIEVED})
        else:
            confirm.append(r)
    return hold, confirm, release


def hold(store, r, now, day):
    """Met l'offre en quarantaine (ou y recommence, avec un autre prix suspect : on garde le début et le premier prix)."""
    store.x("INSERT INTO quarantine(offer_id, since, price, usual, rule, confirmed, checked_day, status, released_at, reason, price_id) "
            "VALUES (?,?,?,?,?,0,?,'held',NULL,NULL,?) ON CONFLICT(offer_id) DO UPDATE SET "
            "since=CASE WHEN quarantine.status='held' THEN quarantine.since ELSE excluded.since END, "
            "price_id=CASE WHEN quarantine.status='held' THEN quarantine.price_id ELSE excluded.price_id END, "
            "price=excluded.price, usual=excluded.usual, rule=excluded.rule, confirmed=0, checked_day=excluded.checked_day, "
            "status='held', released_at=NULL, reason=NULL", (r["offer_id"], now, r["price"], r["usual"], RULE, day, r["price_id"]))


def confirm(store, offer_id, day):
    store.x("UPDATE quarantine SET confirmed=confirmed+1, checked_day=? WHERE offer_id=? AND status='held'", (day, offer_id))


def release(store, offer_id, why, now, day=None):
    """Libère l'offre. Revenue à son prix habituel : les prix suspects relus depuis la mise en quarantaine sont écartés
    (des erreurs). → nombre de prix écartés."""
    q = store.q("SELECT * FROM quarantine WHERE offer_id=? AND status='held'", (offer_id,), one=True)
    if q is None:
        return 0
    with store.tx() as c:
        c.execute("UPDATE quarantine SET status='released', released_at=?, reason=?, checked_day=COALESCE(?, checked_day) "
                  "WHERE offer_id=?", (now, why, day, offer_id))
        if why != BACK or q["price_id"] is None:
            return 0
        return c.execute("UPDATE prices SET rejected=1 WHERE offer_id=? AND id>=? AND price<?",
                         (offer_id, q["price_id"], (1 - DROP) * q["usual"])).rowcount


def held(store):
    return store.q("SELECT q.*, o.retailer, o.merchant, o.product_id, o.url, p.title FROM quarantine q JOIN offers o ON o.id=q.offer_id "
                   "LEFT JOIN products p ON p.id=o.product_id WHERE q.status='held' ORDER BY q.since")
