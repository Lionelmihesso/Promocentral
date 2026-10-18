"""Extraction d'une offre depuis une page produit. Règle : ne jamais enregistrer une donnée fausse ; une donnée manquée
coûte une bonne affaire, une donnée fausse coûte la confiance.

Sources, de la plus fiable à la moins fiable (chaque champ est pris à la meilleure source qui le fournit) :
  1. JSON-LD schema.org                                   0.95
  2. Règles de site (sélecteurs), si configurées           0.90
  3. Microdonnées schema.org                              0.85
  4. Balises meta OpenGraph produit                       0.80
  5. État applicatif embarqué (__NEXT_DATA__, …)          0.75   seulement si l'identité du produit concorde
Le prix barré peut aussi venir du bloc de prix HTML, mais seulement à côté du prix déjà trouvé par une source structurée
(barré, classe « ancien prix », « Prix de référence », « au lieu de »…), jamais deviné ailleurs dans la page.

Garde-fous :
- prix membre / carte de fidélité (validForMemberTier) jamais pris pour le prix public ni pour le prix barré ;
- produit principal choisi parmi plusieurs (produits associés, carrousels, listes) : adresse, titre, h1 ;
- page liste (fiche redirigée vers une catégorie) et page introuvable reconnues, aucun prix enregistré ;
- offre d'occasion ou reconditionnée écartée quand une offre neuve existe ; seulement d'occasion → pas de prix ;
- devise autre que l'euro refusée ; montant suivi de « % » refusé ;
- prix barré validé : au-dessus du prix, remise ≤ 85 %, cohérent avec le pourcentage affiché (bloc HTML) ;
- « à partir de » (variantes, AggregateOffer) : prix gardé, prix barré jamais associé.
Bibliothèque standard uniquement.
"""
import functools
import re
import unicodedata
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit

from . import page as S

AVAIL = {
    "instock": "in_stock", "onlineonly": "in_stock", "limitedavailability": "in_stock", "instoreonly": "in_stock",
    "outofstock": "out_of_stock", "soldout": "out_of_stock", "discontinued": "out_of_stock",
    "preorder": "preorder", "presale": "preorder", "backorder": "backorder",
    "in stock": "in_stock", "out of stock": "out_of_stock", "en stock": "in_stock", "rupture": "out_of_stock",
    "épuisé": "out_of_stock", "epuise": "out_of_stock", "indisponible": "out_of_stock", "disponible": "in_stock",
}
CURRENCY_SYMBOLS = {"€": "EUR", "$": "USD", "£": "GBP", "CHF": "CHF"}
PRODUCT_TYPES = {"product", "productgroup", "individualproduct", "productmodel", "someproducts"}
OFFER_TYPES = {"offer", "aggregateoffer"}
LIST_KEYS = {"itemlistelement", "isrelatedto", "issimilarto", "isaccessoryorsparepartfor", "isconsumablefor", "hasvariant",
             "isvariantof", "itemoffered", "recommendations"}
MAX_PRICE = 50000.0          # au-delà : centimes, référence ou erreur de saisie
MAX_DISCOUNT = 0.85
CONF = {"jsonld": 0.95, "rules": 0.90, "microdata": 0.85, "opengraph": 0.80, "state": 0.75}


# ------------------------------------------------------------------ normalisation
def parse_price(v):
    """'1 299,99 €' → 1299.99 ; '1.299,99' → 1299.99 ; '1,299.99' → 1299.99 ; '299€99' → 299.99 ; 499 → 499.0 ;
    '-40 %' → None (un pourcentage n'est pas un prix)."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if 0 < v < 1e7 else None
    s = unescape(str(v)).strip().replace(" ", " ").replace("\xa0", " ")
    m = re.search(r"(\d[\d .]*)\s*€\s*(\d{2})\b", s)  # 299€99
    if m:
        return float(m.group(1).replace(" ", "").replace(".", "") + "." + m.group(2))
    m = re.search(r"\d[\d .,']*", s)
    if not m or s[m.end():].lstrip().startswith("%"):
        return None
    n = m.group(0).strip().rstrip(".,").replace(" ", "").replace("'", "")
    if "," in n and "." in n:
        n = n.replace(".", "").replace(",", ".") if n.rfind(",") > n.rfind(".") else n.replace(",", "")
    elif "," in n:
        head, _, tail = n.rpartition(",")
        n = head.replace(",", "") + "." + tail if len(tail) in (1, 2) else n.replace(",", "")
    elif n.count(".") == 1 and len(n.split(".")[1]) == 3:
        n = n.replace(".", "")  # 1.299 → 1299
    elif n.count(".") > 1:
        head, _, tail = n.rpartition(".")
        n = head.replace(".", "") + "." + tail if len(tail) == 2 else n.replace(".", "")
    try:
        p = float(n)
    except ValueError:
        return None
    return p if 0 < p < 1e7 else None


def parse_currency(v, text=""):
    if v:
        s = str(v).strip().upper()
        if re.fullmatch(r"[A-Z]{3}", s):
            return s
        for sym, code in CURRENCY_SYMBOLS.items():
            if sym in str(v):
                return code
    for sym, code in CURRENCY_SYMBOLS.items():
        if sym in (text or ""):
            return code
    return None


def parse_availability(v):
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return "in_stock" if v else "out_of_stock"
    s = str(v).strip().lower().rsplit("/", 1)[-1].replace("_", "").replace("-", "")
    if s in AVAIL:
        return AVAIL[s]
    s2 = str(v).strip().lower()
    for k in sorted(AVAIL, key=len, reverse=True):     # « indisponible » avant « disponible »
        if k in s2:
            return AVAIL[k]
    return None


def clean_gtin(v):
    if not v:
        return None
    d = re.sub(r"\D", "", str(v))
    if len(d) not in (8, 12, 13, 14):
        return None
    d = d.zfill(14)
    body, check = d[:-1], int(d[-1])
    total = sum(int(x) * (3 if i % 2 == 0 else 1) for i, x in enumerate(body))
    return d.lstrip("0").zfill(13) if (10 - total % 10) % 10 == check else None


def _plain(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _toks(s):
    return {t for t in re.split(r"[^a-z0-9]+", _plain(s)) if len(t) > 1}


def _sim(a, b):
    ta, tb = _toks(a), _toks(b)
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def _path(u):
    try:
        return urlsplit(str(u)).path.rstrip("/").lower()
    except ValueError:
        return ""


# ------------------------------------------------------------------ nœuds schema.org (JSON-LD et microdonnées)
def _walk(o, path=()):
    if isinstance(o, dict):
        yield o, path
        for k, v in o.items():
            yield from _walk(v, path + (str(k).lower(),))
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v, path)


def _types(o):
    t = o.get("@type")
    return {str(x).rstrip("/").rsplit("/", 1)[-1].lower() for x in (t if isinstance(t, list) else [t])} if t else set()


def _first(v):
    return v[0] if isinstance(v, list) and v else v


def _name(v):
    v = _first(v)
    return v.get("name") if isinstance(v, dict) else v


def _image(v):
    v = _first(v)
    if isinstance(v, dict):
        v = v.get("url") or v.get("contentUrl")
    return v if isinstance(v, str) and v.startswith(("http://", "https://", "//")) else None


def _props(v):
    out = {}
    for x in (v if isinstance(v, list) else [v] if v else []):
        if isinstance(x, dict) and x.get("name") is not None:
            out[str(x["name"]).strip().lower()] = str(x.get("value", "")).strip()
    return out


def _is_member(sp):
    if "validForMemberTier" in sp or "eligibleCustomerType" in sp:
        return True
    return bool(re.search(r"membre|adh[ée]rent|fid[ée]lit|\bclub\b|\bcarte\b", str(sp.get("name") or sp.get("description") or ""), re.I))


def _strike_type(sp):
    t = str(sp.get("priceType") or "").lower()
    if "strikethrough" in t or "listprice" in t:
        return "strikethrough"
    if "msrp" in t or t.endswith("srp"):
        return "msrp"
    return None


def _date(v):
    m = re.match(r"\d{4}-\d{2}-\d{2}", str(v or ""))
    return m.group(0) if m else None


def _offer_row(o):
    """Une offre schema.org → prix public, prix barré, devise, état… (ou None)."""
    t = _types(o)
    specs = o.get("priceSpecification")
    specs = [s for s in (specs if isinstance(specs, list) else [specs] if specs else []) if isinstance(s, dict)]
    member = [s for s in specs if _is_member(s)]
    strike = [s for s in specs if not _is_member(s) and _strike_type(s)]
    plain = [s for s in specs if not _is_member(s) and not _strike_type(s)]
    raw = o.get("price")
    if raw in (None, "") and plain:
        raw = plain[0].get("price")
    kind = None
    if raw in (None, "") and "aggregateoffer" in t:
        raw = o.get("lowPrice")
    price = parse_price(raw)
    if price is None or price > MAX_PRICE:
        return None
    if "aggregateoffer" in t:
        hp = parse_price(o.get("highPrice"))
        try:
            count = int(float(o.get("offerCount") or 0))
        except (TypeError, ValueError):
            count = 0
        if (hp and hp > price) or count > 1:
            kind = "from"
    was, was_type = None, None
    for s in strike:
        v = parse_price(s.get("price"))
        if v and v > price:
            was, was_type = v, _strike_type(s)
            break
    cur_src = o.get("priceCurrency") or next((s.get("priceCurrency") for s in plain + strike if s.get("priceCurrency")), None)
    cond = str(o.get("itemCondition") or "").lower()
    return {"price": price, "raw_price": str(raw), "list_price": was, "was_type": was_type,
            "currency": parse_currency(cur_src), "availability": parse_availability(o.get("availability")),
            "seller": _name(o.get("seller")), "used": any(w in cond for w in ("used", "refurbished", "damaged")),
            "kind": kind, "valid_until": _date(o.get("priceValidUntil") or next((s.get("validThrough") for s in plain if s.get("validThrough")), None)),
            "member_price": parse_price(member[0].get("price")) if member else None}


def _offers(p):
    """Offres d'un produit (sans descendre dans priceSpecification) ; une AggregateOffer détaillée → ses offres."""
    offers = p.get("offers")
    out = []
    for o in (offers if isinstance(offers, list) else [offers] if offers else []):
        if not isinstance(o, dict):
            continue
        kids = o.get("offers") if "aggregateoffer" in _types(o) else None
        kids = [k for k in (kids if isinstance(kids, list) else [kids] if kids else []) if isinstance(k, dict)]
        priced = [k for k in kids if k.get("price") not in (None, "") or k.get("priceSpecification")]
        out += priced or [o]
    return out


def _best_offer(p, reasons):
    rows = [r for r in (_offer_row(o) for o in _offers(p)) if r]
    if not rows:
        return None
    new = [r for r in rows if not r["used"]]
    if not new:
        reasons.append("seulement des offres d'occasion ou reconditionnées")
        return None
    return min(new, key=lambda r: (r["availability"] == "out_of_stock", r["price"]))


def _main_product(nodes, page, url):
    cands = [(n, path) for n, path in nodes if _types(n) & PRODUCT_TYPES and not (set(path) & LIST_KEYS)]
    if not cands:
        return None
    refs = {_path(x) for x in (url, page.canonical, page.meta.get("og:url")) if x} - {""}
    titles = [t for t in (page.h1, page.meta.get("og:title"), page.title) if t]

    def score(c):
        n, path = c
        s = 2.0 if "mainentity" in path else 0.0
        u = n.get("url") or n.get("@id")
        if u and _path(u) in refs:
            s += 3
        name = _first(n.get("name"))
        if name and titles:
            s += 2 * max(_sim(str(name), t) for t in titles)
        if _offers(n) or n.get("hasVariant"):
            s += 1
        return s
    return max(cands, key=score)[0]


def _variant(group, url, reasons):
    """ProductGroup : la variante désignée par l'adresse, sinon la moins chère (« à partir de »)."""
    vs = [v for v in (group.get("hasVariant") if isinstance(group.get("hasVariant"), list) else [group.get("hasVariant")]) if isinstance(v, dict)]
    rows = [(v, _best_offer(v, reasons)) for v in vs]
    rows = [(v, r) for v, r in rows if r]
    if not rows:
        return None, None
    up = _path(url) if url else ""
    q = urlsplit(url).query if url else ""
    for v, r in rows:
        if (up and _path(v.get("url")) == up and urlsplit(str(v.get("url"))).query == q) or (v.get("sku") and str(v.get("sku")) in (q or "")):
            return v, r
    v, r = min(rows, key=lambda x: (x[1]["availability"] == "out_of_stock", x[1]["price"]))
    if len(rows) > 1 and len({x[1]["price"] for x in rows}) > 1:
        r = {**r, "kind": "from"}
    return v, r


def _from_nodes(roots, page, url, method, reasons):
    nodes = list(_walk(roots))
    listed = sum(1 for n, path in nodes if _types(n) & PRODUCT_TYPES and set(path) & LIST_KEYS - {"hasvariant", "isvariantof"})
    info = {"listed": listed, "main": False}
    p = _main_product(nodes, page, url)
    if p is None:
        lone = [n for n, path in nodes if _types(n) & OFFER_TYPES and not path]
        if len(lone) == 1:                               # offre seule, sans produit déclaré
            r = _offer_row(lone[0])
            if r and not r["used"]:
                return {**r, "title": None, "method": method, "confidence": CONF[method]}, info
        return None, info
    info["main"] = True
    src, row = p, _best_offer(p, reasons)
    if row is None and p.get("hasVariant"):
        v, row = _variant(p, url, reasons)
        src = {**p, **{k: v[k] for k in ("gtin13", "gtin", "gtin12", "gtin14", "gtin8", "sku", "mpn") if v and v.get(k)}} if v else p
    ident = {"title": _first(p.get("name")), "brand": _name(p.get("brand")), "category": _name(p.get("category")),
             "properties": _props(p.get("additionalProperty")), "image": _image(p.get("image")),
             "gtin": clean_gtin(src.get("gtin13") or src.get("gtin") or src.get("gtin12") or src.get("gtin14") or src.get("gtin8")),
             "mpn": _first(src.get("mpn")), "sku": _first(src.get("sku"))}
    info["identity"] = ident          # identité utile même sans prix (EAN en microdonnées, prix en balises meta)
    if row is None:
        return None, info
    return {**row, **ident, "method": method, "confidence": CONF[method]}, info


def _from_meta(page):
    mt = page.meta
    price = parse_price(mt.get("product:price:amount") or mt.get("og:price:amount"))
    if price is None or price > MAX_PRICE:
        return None
    return {"price": price, "raw_price": mt.get("product:price:amount") or mt.get("og:price:amount"),
            "currency": parse_currency(mt.get("product:price:currency") or mt.get("og:price:currency")),
            "availability": parse_availability(mt.get("product:availability") or mt.get("og:availability")),
            "list_price": parse_price(mt.get("product:original_price:amount") or mt.get("og:original_price:amount")),
            "title": mt.get("og:title"), "brand": mt.get("product:brand"), "image": mt.get("og:image"),
            "gtin": clean_gtin(mt.get("product:ean") or mt.get("product:gtin") or mt.get("product:upc")),
            "method": "opengraph", "confidence": CONF["opengraph"]}


# ------------------------------------------------------------------ état applicatif embarqué
@functools.lru_cache(maxsize=8192)
def _k(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


PRICE_KEYS = {_k(x) for x in ("price", "salePrice", "finalPrice", "currentPrice", "sellingPrice", "priceValue", "displayPrice",
                              "prix", "prixVente", "prixFinal")}
INNER_PRICE_KEYS = PRICE_KEYS | {"current", "value", "amount", "final", "sale", "selling", "now", "actual"}
OLD_KEYS = {_k(x) for x in ("oldPrice", "crossedPrice", "crossedOutPrice", "strikePrice", "strikethroughPrice", "strikedPrice",
                            "originalPrice", "listPrice", "regularPrice", "basePrice", "referencePrice", "refPrice", "previousPrice",
                            "wasPrice", "compareAtPrice", "compare_at_price", "priceBeforeDiscount", "initialPrice", "fullPrice",
                            "prixBarre", "prixReference", "prixAvantRemise")}
INNER_OLD_KEYS = OLD_KEYS | {"old", "was", "before", "original", "regular", "reference", "strike", "crossed", "initial"}
NAME_KEYS = {"name", "title", "label", "productname", "libelle"}
GTIN_KEYS = {"ean", "gtin", "gtin13", "ean13", "barcode"}
PRICE_OBJ_KEYS = {"price", "prices", "pricing", "priceinfo", "priceinformation", "offer", "prix"}


def _num(v, inner=None):
    if isinstance(v, dict):
        for k, x in v.items():
            if _k(k) in (inner or {"value", "amount", "current"}):
                return _num(x)
        return None
    if isinstance(v, str) and not re.search(r"\d", v):
        return None
    return parse_price(v)


def _prices_of(d):
    price = was = None
    avail = None
    for k, v in d.items():
        kk = _k(k)
        if kk in PRICE_KEYS and not isinstance(v, (dict, list)):
            price = price or _num(v)
        elif kk in OLD_KEYS:
            was = was or _num(v)
        elif kk in PRICE_OBJ_KEYS and isinstance(v, dict):
            for k2, v2 in v.items():
                k2 = _k(k2)
                if k2 in INNER_PRICE_KEYS and price is None:
                    price = _num(v2, INNER_PRICE_KEYS)
                elif k2 in INNER_OLD_KEYS and was is None:
                    was = _num(v2, INNER_PRICE_KEYS)
        if kk in ("available", "isavailable", "instock", "availability") and avail is None:
            avail = parse_availability(v)
        elif kk == "stock" and isinstance(v, dict):
            for k2, v2 in v.items():
                if _k(k2) in ("available", "isavailable", "instock", "status") and avail is None:
                    avail = parse_availability(v2)
    return price, was, avail


def _from_states(states, identity, page):
    titles = [t for t in (identity.get("title"), page.h1, page.meta.get("og:title")) if t]
    best = None
    for st in states:
        for d, _ in _walk(st):
            name = next((v for k, v in d.items() if _k(k) in NAME_KEYS and isinstance(v, str)), None)
            gtin = clean_gtin(next((v for k, v in d.items() if _k(k) in GTIN_KEYS), None))
            if not name and not gtin:
                continue
            same_gtin = bool(gtin and identity.get("gtin") and gtin == identity["gtin"])
            sim = max((_sim(name, t) for t in titles), default=0) if name else 0
            if not same_gtin and sim < 0.6:
                continue
            price, was, avail = _prices_of(d)
            if price is None or price > MAX_PRICE:
                continue
            score = (same_gtin, sim)
            if best is None or score > best[0]:
                best = (score, {"price": price, "raw_price": str(price), "list_price": was, "availability": avail,
                                "title": name, "gtin": gtin, "method": "state", "confidence": CONF["state"]})
    return best[1] if best else None


# ------------------------------------------------------------------ prix barré dans le bloc de prix HTML
OLD_TOKENS = {"old", "strike", "striked", "strikethrough", "strikeout", "barre", "barré", "crossed", "was", "before", "initial",
              "reference", "référence", "regular", "original", "ancien", "previous", "msrp", "rrp", "oldprice", "crossedout"}
CUE_RX = re.compile(r"au lieu de|prix de r[ée]f[ée]rence|prix conseill[ée]|ancien prix|prix barr[ée]|prix initial|avant remise|"
                    r"prix habituel|prix public|\bvs\.?\s|\bwas\b", re.I)
EXCL_RX = re.compile(r"/\s*mois|par mois|mensualit|\b\d\s?x\b|\bx\s?\d\b|\d\s?fois|en \d|fois sans frais|[ée]co[- .]?(?:part|partic|contrib)|"
                     r"\bdont\b|rembours|\bODR\b|livraison|frais de port|[ée]conomi|\bsoit\b|cagnott|\bcarte\b|membre|adh[ée]rent|"
                     r"fid[ée]lit|\bclub\b|code promo|avec le code|reprise|autres? offres?|\bd[èe]s\b|[àa] partir de|vendeurs?", re.I)
BADGE_RX = re.compile(r"[-–−]\s?(\d{1,2})\s?%")
BANNER_RX = re.compile(r"jusqu|sur une s[ée]lection|soldes|promos?\b|\bd[èe]s\b|suppl[ée]mentaire|code", re.I)
_FRAG = re.compile(r"[\d\s  .,€]{1,8}")
_AMOUNT = re.compile(r"(?:\d{1,3}(?:[   .]\d{3})+|\d+)(?:,\d{1,2})?\s?€(?:\s?\d{2}(?!\d))?|(?:\d{1,3}(?:[   .]\d{3})+|\d+),\d{2}(?!\d)(?!\s?%)")


def _merge(nodes):
    """Recolle les prix éclatés en plusieurs éléments voisins : « 349€ » + « 98 », « 1 199 » + « ,00 € ».
    Seulement deux fragments purement numériques du même élément : un titre qui finit par un chiffre ne se colle jamais."""
    out = []
    for text, ctx, struck, path in nodes:
        if out and _FRAG.fullmatch(text) and _FRAG.fullmatch(out[-1][0]) and out[-1][2] == struck \
                and _common(out[-1][3], path) >= min(len(path), len(out[-1][3])) - 2:
            prev = out[-1][0]
            incomplete = "€" not in prev or (re.search(r"€\s?$", prev) and re.fullmatch(r"\s?\d{2}\s?", text))
            if incomplete and re.search(r"[\d€,]\s?$", prev):
                out[-1] = [prev + text.strip(), (out[-1][1] + " " + ctx).strip(), struck, out[-1][3]]
                continue
        out.append([text, ctx, struck, path])
    return out


def _common(p, q):
    n = 0
    for x, y in zip(p, q):
        if x != y:
            break
        n += 1
    return n


def _amounts(text):
    return [v for v in (parse_price(m.group(0)) for m in _AMOUNT.finditer(text)) if v]


def html_strike(page, price, window=8):
    """Prix barré et pourcentage affichés autour du prix (déjà connu). → (prix barré | None, pourcentage | None, motif)."""
    nodes = _merge(page.nodes)
    amounts = [_amounts(n[0]) if ("€" in n[0] or "," in n[0]) and any(ch.isdigit() for ch in n[0]) else [] for n in nodes]
    anchors = [i for i, a in enumerate(amounts) if any(abs(v - price) < 0.006 for v in a)
               and not EXCL_RX.search(nodes[i][0]) and not (i and EXCL_RX.search(nodes[i - 1][0]) and len(nodes[i][0]) < 20)]
    best = badge = None
    for a in anchors:
        apath = nodes[a][3]
        need = max(3, len(apath) - 4)            # même bloc de prix : ancêtre commun proche du prix
        for i in range(max(0, a - window), min(len(nodes), a + window + 1)):
            text, ctx, struck, path = nodes[i]
            if _common(path, apath) < need:
                continue
            prev = nodes[i - 1][0] if i else ""
            if badge is None or abs(i - a) < badge[0]:
                m = BADGE_RX.search(text)
                if m and not EXCL_RX.search(text) and not BANNER_RX.search(text):
                    badge = (abs(i - a), int(m.group(1)))
            if i == a or EXCL_RX.search(text) or (EXCL_RX.search(prev) and len(text) < 20):
                continue
            for v in amounts[i]:
                if not (price * 1.01 < v <= price * 6):
                    continue
                why = "barré" if struck else "classe" if S.tokens(ctx) & OLD_TOKENS else "mention" if (CUE_RX.search(text) or CUE_RX.search(prev)) else None
                if not why:
                    continue
                rank = (abs(i - a), {"barré": 0, "classe": 1, "mention": 2}[why])
                if best is None or rank < best[0]:
                    best = (rank, v, why)
    return (best[1] if best else None), (badge[1] if badge else None), (best[2] if best else None)


# ------------------------------------------------------------------ règles par site
class _Scan(HTMLParser):
    """Texte des éléments ciblés par des sélecteurs simples (règles de site)."""

    def __init__(self, selectors=()):
        super().__init__(convert_charrefs=True)
        self.selectors = [_compile_selector(s) for s in selectors]
        self.sel_text = {}
        self._open = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        idx = [i for i, s in enumerate(self.selectors) if s(tag, a) and i not in self.sel_text]
        if tag in S.VOID:
            for j in idx:
                if a.get("content"):
                    self.sel_text.setdefault(j, a["content"])
            return
        self._open.append((tag, idx, []))

    def handle_data(self, data):
        for _, _, buf in self._open:
            buf.append(data)

    def handle_endtag(self, tag):
        for i in range(len(self._open) - 1, -1, -1):
            if self._open[i][0] == tag:
                t, idx, buf = self._open.pop(i)
                text = " ".join("".join(buf).split())
                for j in idx:
                    self.sel_text.setdefault(j, text)
                break


def _compile_selector(sel):
    """Sélecteur simple : tag, .classe, #id, [attr=valeur], combinables (ex. span.price[data-x=1])."""
    m = re.fullmatch(r"([a-z0-9]*)((?:[.#][\w-]+|\[[\w-]+(?:=[^\]]+)?\])*)", sel.strip())
    if not m:
        raise ValueError(f"Sélecteur non supporté : {sel}")
    tag, rest = m.group(1), m.group(2)
    parts = re.findall(r"([.#])([\w-]+)|\[([\w-]+)(?:=([^\]]+))?\]", rest)

    def match(t, a):
        if tag and t != tag:
            return False
        for kind, name, attr, val in parts:
            if kind == "." and name not in (a.get("class") or "").split():
                return False
            if kind == "#" and a.get("id") != name:
                return False
            if attr and (attr not in a or (val and a.get(attr) != val.strip("\"'"))):
                return False
        return True
    return match


def extract_rules(html, rules):
    """rules = {"price": "span.price" | {"regex": "..."} , "list_price": …, "availability": …, "title": …}"""
    if not rules:
        return None
    sels = {k: v for k, v in rules.items() if isinstance(v, str)}
    scan = _Scan(list(sels.values()))
    scan.feed(html)
    out = {k: scan.sel_text.get(i) for i, k in enumerate(sels)}
    for k, v in rules.items():
        if isinstance(v, dict) and "regex" in v:
            m = re.search(v["regex"], html, re.S)
            out[k] = m.group(1) if m else None
    price = parse_price(out.get("price"))
    if price is None or price > MAX_PRICE:
        return None
    return {"price": price, "raw_price": out.get("price"), "list_price": parse_price(out.get("list_price")),
            "currency": parse_currency(out.get("currency"), out.get("price") or ""),
            "availability": parse_availability(out.get("availability")), "title": out.get("title"),
            "gtin": clean_gtin(out.get("gtin")), "method": "rules", "confidence": CONF["rules"]}


# ------------------------------------------------------------------ mention légale « plus bas 30 jours »
OMNIBUS = re.compile(r"(?:prix\s+(?:le\s+)?plus\s+bas|prix\s+de\s+r[ée]f[ée]rence)[^0-9€]{0,80}?(?:30|trente)\s+(?:derniers\s+)?jours"
                     r"[^0-9]{0,40}?(\d[\d\s  .]*(?:,\d{1,2})?)\s*€", re.I)


def lowest_30d(html):
    """« Prix le plus bas pratiqué au cours des 30 derniers jours : 589,00 € » → 589.0 (affichage obligatoire sur les promos)."""
    m = OMNIBUS.search(re.sub(r"<[^>]+>", " ", html or ""))
    return parse_price(m.group(1)) if m else None


NOT_FOUND_RX = re.compile(r"page introuvable|page non trouv|n'existe plus|n’existe plus|erreur 404|\b404\b|page inexistante|"
                          r"produit introuvable|plus commercialis", re.I)


# ------------------------------------------------------------------ assemblage
def analyze(html, rules=None, url=None, merchant=None):
    """→ {page_kind: product|listing|not_found|unknown, best: offre | None, candidates: [...], reasons: [...]}"""
    page = S.scan(html)
    reasons, cands = [], []
    j, j_info = _from_nodes(page.ld, page, url, "jsonld", reasons)
    m, m_info = _from_nodes(page.micro, page, url, "microdata", reasons)
    for c in (j, extract_rules(html, rules), m, _from_meta(page)):
        if c:
            cands.append(c)
    idents = [i.get("identity") for i in (j_info, m_info) if i.get("identity")]
    identity = cands[0] if cands else (idents[0] if idents else {})
    st = _from_states(page.states, identity, page)
    if st:
        cands.append(st)
    main = j_info["main"] or m_info["main"]
    listed = j_info["listed"] + m_info["listed"]
    if not main and listed >= 3:
        return {"page_kind": "listing", "best": None, "candidates": cands, "reasons": reasons + [f"page liste ({listed} produits)"]}
    foreign = [c for c in cands if c.get("currency") not in (None, "EUR")]
    if foreign:
        reasons.append(f"devise {foreign[0]['currency']} refusée")
        cands = [c for c in cands if c.get("currency") in (None, "EUR")]
    if not cands:
        nf = NOT_FOUND_RX.search(" ".join(t for t in (page.title, page.h1) if t))
        return {"page_kind": "not_found" if nf else ("product" if main else "unknown"), "best": None, "candidates": [], "reasons": reasons}

    cands.sort(key=lambda c: -c["confidence"])
    best = dict(cands[0])
    for c in cands[1:]:
        same_price = abs(c["price"] - best["price"]) <= 0.005 * best["price"]
        for k in ("currency", "availability", "title", "brand", "gtin", "mpn", "sku", "seller", "category", "image", "valid_until"):
            if not best.get(k) and c.get(k):
                best[k] = c[k]
        if not best.get("list_price") and c.get("list_price") and same_price:   # prix barré d'une autre source, même prix
            best["list_price"], best["was_method"] = c["list_price"], c["method"]
    for ident in idents:
        for k in ("title", "brand", "gtin", "mpn", "sku", "category", "image", "properties"):
            if not best.get(k) and ident.get(k):
                best[k] = ident[k]
    if best.get("list_price") and not best.get("was_method"):
        best["was_method"] = best["method"]
    best["title"] = best.get("title") or page.meta.get("og:title") or page.h1 or page.title
    best["image"] = best.get("image") or page.meta.get("og:image")
    best["currency_known"] = bool(best.get("currency"))
    best["currency"] = best.get("currency") or "EUR"   # hypothèse explicite, tracée par currency_known
    best["availability"] = best.get("availability") or "unknown"
    best["lowest_30d"] = lowest_30d(html)
    if merchant and best.get("seller"):
        best["marketplace"] = _sim(str(best["seller"]), merchant) < 0.5 and _plain(merchant) not in _plain(str(best["seller"]))

    # prix barré : structuré d'abord, sinon bloc de prix HTML ancré sur le prix
    if best.get("kind") == "from":
        if best.get("list_price"):
            reasons.append("« à partir de » : prix barré ignoré")
        best["list_price"] = best["was_method"] = None
    else:
        was, badge, why = html_strike(page, best["price"])
        best["discount_badge"] = badge
        if not best.get("list_price") and was:
            best["list_price"], best["was_method"] = was, f"html ({why})"
            if badge is not None and abs(round((1 - best["price"] / was) * 100) - badge) > 3:
                reasons.append(f"prix barré HTML {was} incohérent avec « -{badge} % » : ignoré")
                best["list_price"] = best["was_method"] = None
    lp = best.get("list_price")
    if lp and (lp <= best["price"] * 1.01 or 1 - best["price"] / lp > MAX_DISCOUNT):
        reasons.append(f"prix barré {lp} invraisemblable pour {best['price']} : ignoré")
        best["list_price"] = best["was_method"] = None
    prices = {c["method"]: c["price"] for c in cands}
    best["found"] = prices
    best["consistent"] = len(set(prices.values())) == 1
    best["reasons"] = reasons
    return {"page_kind": "product", "best": best, "candidates": cands, "reasons": reasons}


def extract(html, rules=None, url=None, merchant=None):
    """→ dict offre (prix, prix barré, devise, disponibilité, identifiants, provenance) ; None si aucun prix fiable."""
    return analyze(html, rules, url, merchant)["best"]


compile_selector = _compile_selector
