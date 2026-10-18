"""Extraction d'une offre (prix, devise, disponibilité, identifiants) depuis une page produit.

Cascade, de la source la plus fiable à la moins fiable :
  1. JSON-LD schema.org (Product / Offer / AggregateOffer, @graph)   confiance 0.95
  2. Règles par site (sélecteur simple ou regex), si configurées     confiance 0.90
  3. Microdonnées schema.org (itemprop)                              confiance 0.85
  4. Balises meta OpenGraph produit (product:price:amount)           confiance 0.80
Chaque champ est pris à la meilleure source qui le fournit ; la méthode du prix est retournée.
Bibliothèque standard uniquement.
"""
import json
import re
from html import unescape
from html.parser import HTMLParser

AVAIL = {
    "instock": "in_stock", "onlineonly": "in_stock", "limitedavailability": "in_stock", "instoreonly": "in_stock",
    "outofstock": "out_of_stock", "soldout": "out_of_stock", "discontinued": "out_of_stock",
    "preorder": "preorder", "presale": "preorder", "backorder": "backorder",
    "in stock": "in_stock", "out of stock": "out_of_stock", "en stock": "in_stock", "rupture": "out_of_stock",
    "disponible": "in_stock", "indisponible": "out_of_stock",
}
CURRENCY_SYMBOLS = {"€": "EUR", "$": "USD", "£": "GBP", "CHF": "CHF"}


# ------------------------------------------------------------------ normalisation
def parse_price(v):
    """'1 299,99 €' → 1299.99 ; '1.299,99' → 1299.99 ; '1,299.99' → 1299.99 ; '299€99' → 299.99 ; 499 → 499.0"""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    s = unescape(str(v)).strip().replace("\u202f", " ").replace("\xa0", " ")
    m = re.search(r"(\d[\d .]*)\s*€\s*(\d{2})\b", s)  # 299€99
    if m:
        return float(m.group(1).replace(" ", "").replace(".", "") + "." + m.group(2))
    m = re.search(r"\d[\d .,']*", s)
    if not m:
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
    if not v:
        return None
    s = str(v).strip().lower().rsplit("/", 1)[-1].replace("_", "").replace("-", "")
    if s in AVAIL:
        return AVAIL[s]
    s2 = str(v).strip().lower()
    for k, val in AVAIL.items():
        if k in s2:
            return val
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


# ------------------------------------------------------------------ JSON-LD
_LD_RE = re.compile(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.S | re.I)


def _loads_lenient(txt):
    txt = txt.strip().replace("\n", " ")
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        txt = re.sub(r",\s*([}\]])", r"\1", txt)  # virgules traînantes
        txt = re.sub(r"/\*.*?\*/", "", txt)
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            return None


def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def _types(o):
    t = o.get("@type")
    return {str(x).lower() for x in (t if isinstance(t, list) else [t])} if t else set()


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


def _is_list_price(sp):
    t = str(sp.get("priceType") or "").lower()
    return "listprice" in t or "strikethrough" in t or "msrp" in t or "srp" in t


def _props(v):
    out = {}
    for x in (v if isinstance(v, list) else [v] if v else []):
        if isinstance(x, dict) and x.get("name") is not None:
            out[str(x["name"]).strip().lower()] = str(x.get("value", "")).strip()
    return out


def extract_jsonld(html):
    products = []
    for block in _LD_RE.findall(html):
        data = _loads_lenient(unescape(block) if "&quot;" in block else block)
        if data is None:
            continue
        for o in _walk(data):
            if "product" in _types(o) or "productgroup" in _types(o):
                products.append(o)
    for p in products:
        offers = p.get("offers")
        cands = [o for o in _walk(offers) if _types(o) & {"offer", "aggregateoffer"}] if offers else []
        if isinstance(offers, dict) and not cands:
            cands = [offers]
        best = None
        for o in cands:
            specs = o.get("priceSpecification")
            specs = specs if isinstance(specs, list) else ([specs] if specs else [])
            sale_spec = next((sp for sp in specs if not _is_list_price(sp)), None) or {}
            list_spec = next((sp for sp in specs if _is_list_price(sp)), None)
            raw = o.get("price") or sale_spec.get("price") or o.get("lowPrice")
            price = parse_price(raw)
            if price is None:
                continue
            lp = parse_price(list_spec.get("price")) if list_spec else parse_price(o.get("highPrice")) if "aggregateoffer" not in _types(o) else None
            row = {"price": price, "raw_price": str(raw), "list_price": lp if lp and lp > price else None,
                   "currency": parse_currency(o.get("priceCurrency") or sale_spec.get("priceCurrency")),
                   "availability": parse_availability(o.get("availability")),
                   "seller": _name(o.get("seller")),
                   "aggregate": "aggregateoffer" in _types(o)}
            # on retient l'offre en stock la moins chère
            key = (row["availability"] == "out_of_stock", price)
            if best is None or key < best[0]:
                best = (key, row)
        if best:
            r = best[1]
            return {**r, "title": _first(p.get("name")), "brand": _name(p.get("brand")),
                    "category": _name(p.get("category")), "properties": _props(p.get("additionalProperty")),
                    "image": _image(p.get("image")),
                    "gtin": clean_gtin(p.get("gtin13") or p.get("gtin") or p.get("gtin12") or p.get("gtin14") or p.get("gtin8")),
                    "mpn": p.get("mpn"), "sku": p.get("sku"), "method": "jsonld", "confidence": 0.95}
    return None


# ------------------------------------------------------------------ microdonnées + meta + sélecteurs
class _Scan(HTMLParser):
    """Collecte itemprop, meta et le texte des éléments ciblés par des sélecteurs simples."""

    def __init__(self, selectors=()):
        super().__init__(convert_charrefs=True)
        self.itemprops, self.meta = {}, {}
        self.selectors = [_compile_selector(s) for s in selectors]
        self.sel_text = {}
        self._open = []  # (tag, itemprop, selector_idx, buffer)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            k = a.get("property") or a.get("name") or a.get("itemprop")
            if k and a.get("content") is not None:
                self.meta.setdefault(k.lower(), a["content"])
        prop = a.get("itemprop")
        if prop and ("content" in a or "href" in a or tag in ("link", "meta")):
            self.itemprops.setdefault(prop.lower(), a.get("content") or a.get("href"))
            prop = None
        idx = [i for i, s in enumerate(self.selectors) if s(tag, a) and i not in self.sel_text]
        if tag in ("br", "img", "input", "link", "meta", "hr"):
            return
        self._open.append((tag, prop.lower() if prop else None, idx, []))

    def handle_data(self, data):
        for _, _, _, buf in self._open:
            buf.append(data)

    def handle_endtag(self, tag):
        for i in range(len(self._open) - 1, -1, -1):
            if self._open[i][0] == tag:
                t, prop, idx, buf = self._open.pop(i)
                text = " ".join("".join(buf).split())
                if prop:
                    self.itemprops.setdefault(prop, text)
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
    """rules = {"price": "span.price" | {"regex": "..."} , "availability": ..., "title": ...}"""
    if not rules:
        return None
    sels = {k: v for k, v in rules.items() if isinstance(v, str)}
    scan = _Scan(list(sels.values()))
    scan.feed(html)
    out = {}
    for i, (k, _) in enumerate(sels.items()):
        out[k] = scan.sel_text.get(i)
    for k, v in rules.items():
        if isinstance(v, dict) and "regex" in v:
            m = re.search(v["regex"], html, re.S)
            out[k] = m.group(1) if m else None
    price = parse_price(out.get("price"))
    if price is None:
        return None
    return {"price": price, "raw_price": out.get("price"), "list_price": parse_price(out.get("list_price")),
            "currency": parse_currency(out.get("currency"), out.get("price") or ""),
            "availability": parse_availability(out.get("availability")), "title": out.get("title"),
            "method": "rules", "confidence": 0.90}


def extract_microdata_meta(html):
    scan = _Scan()
    scan.feed(html)
    ip, mt = scan.itemprops, scan.meta
    res = []
    price = parse_price(ip.get("price") or ip.get("lowprice"))
    if price is not None:
        res.append({"price": price, "raw_price": ip.get("price"), "currency": parse_currency(ip.get("pricecurrency"), ip.get("price") or ""),
                    "availability": parse_availability(ip.get("availability")),
                    "title": ip.get("name"), "brand": ip.get("brand"),
                    "gtin": clean_gtin(ip.get("gtin13") or ip.get("gtin")), "mpn": ip.get("mpn"),
                    "method": "microdata", "confidence": 0.85})
    price = parse_price(mt.get("product:price:amount") or mt.get("og:price:amount"))
    if price is not None:
        res.append({"price": price, "raw_price": mt.get("product:price:amount") or mt.get("og:price:amount"),
                    "currency": parse_currency(mt.get("product:price:currency") or mt.get("og:price:currency")),
                    "availability": parse_availability(mt.get("product:availability") or mt.get("og:availability")),
                    "list_price": parse_price(mt.get("product:original_price:amount") or mt.get("og:original_price:amount")),
                    "title": mt.get("og:title"), "brand": mt.get("product:brand") or ip.get("brand"), "image": mt.get("og:image"),
                    # les sites mélangent : prix en balises meta, EAN en microdonnées
                    "gtin": clean_gtin(mt.get("product:ean") or mt.get("product:gtin") or ip.get("gtin13") or ip.get("gtin")),
                    "method": "opengraph", "confidence": 0.80})
    return res, (mt.get("og:title") or _title(html))


def _title(html):
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    return " ".join(unescape(m.group(1)).split()) if m else None


OMNIBUS = re.compile(r"(?:prix\s+(?:le\s+)?plus\s+bas|prix\s+de\s+r[ée]f[ée]rence)[^0-9€]{0,80}?(?:30|trente)\s+(?:derniers\s+)?jours[^0-9]{0,40}?(\d[\d\s\u202f\u00a0.]*(?:,\d{1,2})?)\s*€", re.I)


def lowest_30d(html):
    """« Prix le plus bas pratiqué au cours des 30 derniers jours : 589,00 € » → 589.0 (affichage obligatoire sur les promos)."""
    m = OMNIBUS.search(re.sub(r"<[^>]+>", " ", html or ""))
    return parse_price(m.group(1)) if m else None


def extract(html, rules=None):
    """→ dict offre + 'found' (méthodes ayant trouvé un prix) ; None si aucun prix trouvé."""
    cands = []
    j = extract_jsonld(html)
    if j:
        cands.append(j)
    r = extract_rules(html, rules)
    if r:
        cands.append(r)
    md, fallback_title = extract_microdata_meta(html)
    cands += md
    if not cands:
        return None
    cands.sort(key=lambda c: -c["confidence"])
    best = dict(cands[0])
    for c in cands[1:]:  # complète les champs manquants
        for k in ("currency", "availability", "title", "brand", "gtin", "mpn", "sku", "seller", "list_price", "category", "image"):
            if not best.get(k) and c.get(k):
                best[k] = c[k]
    best["title"] = best.get("title") or fallback_title
    if not best.get("image"):
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, re.I)
        best["image"] = m.group(1) if m else None
    best["currency_known"] = bool(best.get("currency"))
    best["currency"] = best.get("currency") or "EUR"   # hypothèse explicite, tracée par currency_known
    best["availability"] = best.get("availability") or "unknown"
    if best.get("list_price") and best["list_price"] <= best["price"]:
        best["list_price"] = None
    prices = {c["method"]: c["price"] for c in cands}
    best["found"] = prices
    best["consistent"] = len(set(prices.values())) == 1
    return best
