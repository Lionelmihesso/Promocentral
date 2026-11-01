"""Affiner en entonnoir (v60) : une question à la fois, du plus large au plus précis — l'univers (High-tech, Salon…),
le rayon, le type, les attributs du rayon (son ontologie), le budget —, chaque réponse avec le nombre de produits
qu'elle donne. Une question dont aucune réponse ne resserre la sélection n'est pas posée ; quand il n'en reste plus, ou
que la sélection tient en trois produits, c'est la fin : votre sélection. La feuille Affiner de la v59 montrait tout à
la fois (53 choix d'emblée, jusqu'à 8 sections) ; ici, une question et ses quelques réponses.

Pur : la Recherche (catalog.search) lui donne ce qu'elle a compté.

  build(crit, d, counts, options, prices, total, room, category, implied) → {"path": [étape], "questions": [question]}

  étape     {level, key, label, fixed, back, chips}   back : de quoi revenir avant elle (fixed : elle ne se retire pas) ;
            chips : les puces de la recherche (query.chips) qu'elle montre déjà
  question  {level, key, title, options: [{label, count, set}]}   set : ce que la réponse ajoute aux critères

Les questions sont dans l'ordre de l'entonnoir : l'app pose la première, sauf celles qu'on a passées (« Passer » :
c'est l'app qui s'en souvient). Les critères (set, back) sont ceux de l'app (web/src/App.jsx) et de l'API de la
Recherche : category, room, domain, sub, min, max ; props et attrs sont des dictionnaires — None les vide, un
dictionnaire s'y ajoute (une valeur None retire la clé). Revenir avant une étape retire aussi les étapes du rayon qui la
suivent (le type, ses attributs), jamais le budget.
"""
from bisect import bisect_right

from . import ontology
from .labels import CATEGORY_LABEL, ROOMS
from .query import ATTR_CHIP, euros

MAX_RAYONS = 6                    # au-delà, l'univers d'abord (High-tech, Salon…)
FEW = 3                           # une sélection de trois produits ou moins : c'est la fin
BUDGETS = (50, 100, 150, 200, 300, 400, 500, 700, 1000, 1500, 2000, 3000, 5000)
ROOM_OF = {c: r for r, (_, cats) in ROOMS.items() for c in cats}
CLEAR_RAYON = {"category": None, "domain": None, "sub": None, "props": None, "attrs": None}


def own_sub(category):
    """Le type qu'une catégorie est à elle seule (robot_aspirateur : le type robot du domaine aspirateurs), ou None."""
    d = ontology.domain_of(category)
    return next((s["key"] for s in d.subs if s["match"]["category"] == [category] and not s["match"].get("any")), None) if d else None


def reach(category):
    """Les catégories que donne le choix d'une catégorie : son domaine entier (choisir « Aspirateurs », c'est aussi ses
    robots), sauf si elle est à elle seule un type du domaine."""
    d = ontology.domain_of(category)
    return set(d.categories) if d and not own_sub(category) else {category}


def implied(counts, total, room=None):
    """Le rayon que la sélection dit d'elle-même (une marque qui ne fait que des téléviseurs, la pièce Entretien) : toute
    dans une catégorie → {"category": c} ; dans plusieurs catégories d'un même domaine → {"domain": clé} ; sinon None.
    L'entonnoir y entre (le rayon y est une étape fixe) : ses questions sont celles du rayon."""
    scope = {c: n for c, n in counts.items() if n and c in ROOM_OF and (room is None or ROOM_OF[c] == room)}
    if not scope or sum(scope.values()) != total:
        return None
    if len(scope) == 1:
        c = next(iter(scope))
        return {"category": c} if ontology.domain_of(c) else None
    ds = {ontology.domain_of(c) for c in scope}
    return {"domain": next(iter(ds)).key} if len(ds) == 1 and None not in ds else None


def budget_label(lo, hi):
    return f"{euros(lo)[:-2]} à {euros(hi)}" if lo is not None and hi is not None else \
        f"Moins de {euros(hi)}" if hi is not None else f"Plus de {euros(lo)}"


def path(crit, d, room=None, category=None, implied=False):
    """Les étapes déjà franchies, dans l'ordre de l'entonnoir : l'univers (s'il a été choisi et contient le rayon), le
    rayon (la catégorie choisie, ou le domaine), le type (sauf celui que la catégorie est à elle seule), les attributs
    (l'ordre du rayon), le budget."""
    out = []
    if room in ROOMS and (d is None or any(ROOM_OF.get(c) == room for c in d.categories)):
        out.append({"level": "room", "key": room, "label": ROOMS[room][0], "fixed": False,
                    "back": {"room": None, **CLEAR_RAYON}, "chips": ["room"]})
    if d is not None:
        sub = crit.get("sub")
        mine = own_sub(category) if category else None
        step = {"level": "category", "key": category or d.key, "label": CATEGORY_LABEL.get(category) or d.label, "fixed": implied,
                "back": dict(CLEAR_RAYON), "chips": ["category", "domain"] + (["sub"] if mine and mine == sub else [])}
        out.append(step)
        if sub in d.sub and sub != mine:
            out.append({"level": "sub", "key": sub, "label": d.sub[sub]["label"], "fixed": False,
                        "back": {"sub": None, "props": None, "attrs": None}, "chips": ["sub"]})
        props, attrs = crit.get("props") or {}, crit.get("attrs") or {}
        order = d.attributes_of(sub)
        for k in sorted(set(props) | set(attrs), key=lambda k: (order.index(k) if k in order else len(order), k)):
            if k in props and k in d.bools:
                out.append({"level": "attr", "key": k, "label": d.attrs[k]["yes" if props[k] else "no"], "fixed": False,
                            "back": {"props": {k: None}}, "chips": [f"prop:{k}"]})
            elif k in attrs and k in ATTR_CHIP:
                out.append({"level": "attr", "key": k, "label": ATTR_CHIP[k](attrs[k]), "fixed": False,
                            "back": {"attrs": {k: None}}, "chips": [f"attr:{k}"]})
    lo, hi = crit.get("min_price"), crit.get("max_price")
    if lo is not None or hi is not None:
        out.append({"level": "budget", "key": "budget", "label": budget_label(lo, hi), "fixed": False,
                    "back": {"min": None, "max": None}, "chips": ["price"]})
    return out


def budgets(prices, total, most=4):
    """Des seuils de budget qui resserrent la sélection (ni tout, ni rien), quatre au plus, répartis sur ses prix."""
    ps = sorted(prices)
    fits = [(t, bisect_right(ps, t)) for t in BUDGETS]
    fits = [(t, n) for t, n in fits if 0 < n < total]
    fits = [(t, n) for i, (t, n) in enumerate(fits) if not i or fits[i - 1][1] != n]   # même sélection : le seuil le plus bas
    if len(fits) <= most:
        return fits
    picked = []
    for share in (0.25, 0.5, 0.75, 0.9):
        t, n = min(fits, key=lambda x: (round(abs(x[1] / total - share), 6), x[0]))
        if (t, n) not in picked:
            picked.append((t, n))
    return sorted(picked)


def questions(crit, d, counts, options, prices, total, room=None):
    """Les questions qui restent, dans l'ordre de l'entonnoir : chacune a au moins deux réponses, ou une, qui resserrent la
    sélection (ni tout, ni rien). Aucune quand la sélection tient en trois produits."""
    if total <= FEW:
        return []
    out = []
    if d is None:
        scope = {c: n for c, n in counts.items() if n and c in ROOM_OF and (room is None or ROOM_OF[c] == room)}
        if room is None and len(scope) > MAX_RAYONS:
            per = {r: sum(n for c, n in scope.items() if ROOM_OF[c] == r) for r in ROOMS}
            opts = [{"label": ROOMS[r][0], "count": per[r], "set": {"room": r, **CLEAR_RAYON}} for r in ROOMS if 0 < per[r] < total]
            if opts:
                out.append({"level": "room", "key": "room", "title": "Quel univers ?",
                            "options": sorted(opts, key=lambda o: (-o["count"], o["label"]))})
        if len(scope) >= 2:
            opts = []
            for c in scope:
                n = sum(counts.get(x, 0) for x in reach(c))
                if 0 < n < total:
                    opts.append({"label": CATEGORY_LABEL.get(c, c), "count": n, "set": {**CLEAR_RAYON, "category": c}})
            if opts:
                out.append({"level": "category", "key": "category", "title": "Quel rayon ?",
                            "options": sorted(opts, key=lambda o: (-o["count"], o["label"]))})
    elif options:
        sub, props, attrs = crit.get("sub"), crit.get("props") or {}, crit.get("attrs") or {}
        if sub is None:
            opts = [{"label": s["label"], "count": s["count"], "set": {"domain": d.key, "sub": s["key"]}}
                    for s in options.get("subs", ()) if 0 < s["count"] < total]
            if opts:
                out.append({"level": "sub", "key": "sub", "title": "Quel type ?", "options": opts})
        for k in d.attributes_of(sub):
            if k in props or k in attrs:
                continue
            if k in d.bools:
                opts = [{"label": p["label"], "count": p["count"], "set": {"domain": d.key, "props": {k: p["value"]}}}
                        for p in options.get("props", ()) if p["key"] == k and 0 < p["count"] < total]
            else:
                opts = [{"label": v["label"], "count": v["count"], "set": {"domain": d.key, "attrs": {k: v["value"]}}}
                        for v in (options.get("attrs", {}).get(k) or {}).get("values", ()) if 0 < v["count"] < total]
            if opts:
                out.append({"level": "attr", "key": k, "title": f"{d.attrs[k]['label']} ?", "options": opts})
    if crit.get("min_price") is None and crit.get("max_price") is None:
        opts = [{"label": f"Moins de {euros(t)}", "count": n, "set": {"min": None, "max": t}} for t, n in budgets(prices, total)]
        if opts:
            out.append({"level": "budget", "key": "budget", "title": "Votre budget ?", "options": opts})
    return out


def build(crit, d, counts, options, prices, total, room=None, category=None, implied=False):
    """L'entonnoir d'une recherche : les étapes franchies, les questions qui restent."""
    return {"path": path(crit, d, room, category, implied), "questions": questions(crit, d, counts, options, prices, total, room)}
