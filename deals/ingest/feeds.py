"""Flux produits : lire le fichier d'une enseigne (CSV, TSV, XML, JSON, JSONL ; brut, gzip ou zip) et le traduire,
produit par produit, en offres normalisées (contract.py). Pur : ni base, ni réseau.

  Mapping.load(objet, base)   la correspondance des colonnes d'un flux, vérifiée (un nom inconnu, un champ obligatoire
                              absent : arrêt, avec la cause) ; « preset »: "google_shopping" part du format standard
  records(raw, mapping)       → (rang, champs bruts) pour chaque produit, sans charger tout le fichier (XML, CSV, JSONL)
  normalize(champs, mapping)  → offre normalisée : prix lus à la française ou non, devise, disponibilité, EAN vérifié,
                              catégorie, fin de promotion, livraison, caractéristiques ; rien n'est deviné
  probe(raw)                  ce qu'est un échantillon (format, encodage, séparateur, élément produit, colonnes) et la
                              correspondance proposée, à relire avant de l'enregistrer

Un prix promotionnel (sale_price) plus bas que le prix devient le prix, et le prix déclaré le prix barré (règle Google
Shopping). Les champs du format Google Shopping sont publics (Google Merchant Center) ; les noms de colonnes des
réseaux d'affiliation ne le sont pas : chaque flux réel reçoit sa correspondance, écrite sur un échantillon (probe).
"""
import csv
import gzip
import io
import json
import re
import unicodedata
import zipfile
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from xml.etree import ElementTree as ET

from ..extract import clean_gtin, parse_availability, parse_currency, parse_price

FIELDS = ("external_id", "title", "url", "tracking_url", "price", "sale_price", "list_price", "currency", "availability",
          "gtin", "mpn", "brand", "category", "image", "condition", "valid_until", "lowest_30d", "shipping", "seller",
          "properties")
REQUIRED = ("title", "url", "price")
FORMATS = ("csv", "tsv", "xml", "json", "jsonl")
OPTIONS = {"preset", "format", "encoding", "delimiter", "item", "items", "fields", "availability", "properties",
           "category_separator", "currency", "drop_params", "_note"}
MONEY = ("price", "sale_price", "list_price", "lowest_30d", "shipping")
TRACKING = re.compile(r"^(utm_[a-z0-9_]+|gclid|fbclid|msclkid|srsltid|_ga)$", re.I)
csv.field_size_limit(16 * 1024 * 1024)

PRESETS = {
    # Format standard des flux produits (Google Merchant Center) : RSS 2.0 ou Atom, espace de noms g:
    "google_shopping": {
        "format": "xml", "item": ["item", "entry"],
        "fields": {"external_id": "id", "title": "title", "url": "link", "price": "price", "sale_price": "sale_price",
                   "valid_until": "sale_price_effective_date", "availability": "availability", "gtin": "gtin", "mpn": "mpn",
                   "brand": "brand", "category": "product_type", "image": "image_link", "condition": "condition",
                   "shipping": "shipping.price", "properties": "product_detail"},
    },
}

# Valeurs de disponibilité des flux, en plus de celles de schema.org (extract.parse_availability)
AVAILABILITY = {
    "in stock": "in_stock", "in_stock": "in_stock", "instock": "in_stock", "available": "in_stock", "en stock": "in_stock",
    "disponible": "in_stock", "oui": "in_stock", "yes": "in_stock", "true": "in_stock", "y": "in_stock",
    "out of stock": "out_of_stock", "out_of_stock": "out_of_stock", "outofstock": "out_of_stock", "rupture": "out_of_stock",
    "en rupture": "out_of_stock", "rupture de stock": "out_of_stock", "épuisé": "out_of_stock", "epuise": "out_of_stock",
    "indisponible": "out_of_stock", "non": "out_of_stock", "no": "out_of_stock", "false": "out_of_stock", "n": "out_of_stock",
    "preorder": "preorder", "pre-order": "preorder", "précommande": "preorder", "en précommande": "preorder",
    "backorder": "backorder", "sur commande": "backorder", "en réapprovisionnement": "backorder",
}
CONDITION = {"new": "new", "neuf": "new", "used": "used", "occasion": "used", "refurbished": "refurbished",
             "reconditionné": "refurbished", "reconditionne": "refurbished", "seconde main": "used"}

# probe : noms de colonnes fréquents, pour PROPOSER une correspondance (à relire : ce n'est pas une vérité)
GUESS = {
    "external_id": ["id", "sku", "product_id", "id_produit", "merchant_product_id", "aw_product_id", "offer_id", "item_id",
                    "code_article", "reference_interne", "g_id"],
    "title": ["title", "name", "nom", "product_name", "libelle", "designation", "titre", "nom_produit"],
    "url": ["link", "url", "product_url", "url_produit", "merchant_deep_link", "lien", "lien_produit", "product_link"],
    "tracking_url": ["aw_deep_link", "deeplink", "deep_link", "tracking_url", "lien_affilie", "affiliate_link", "url_tracking"],
    "price": ["price", "prix", "search_price", "current_price", "prix_ttc", "prix_vente", "store_price", "display_price"],
    "sale_price": ["sale_price", "prix_promo", "promo_price", "prix_solde"],
    "list_price": ["rrp_price", "rrp", "prix_barre", "old_price", "product_price_old", "regular_price", "price_old",
                   "prix_initial", "prix_de_reference", "list_price"],
    "currency": ["currency", "devise"],
    "availability": ["availability", "in_stock", "stock_status", "disponibilite", "dispo", "stock", "availability_status"],
    "gtin": ["gtin", "ean", "ean13", "gtin13", "product_gtin", "upc", "code_ean", "ean_code"],
    "mpn": ["mpn", "model_number", "ref_fabricant", "reference_fabricant", "manufacturer_reference", "product_model", "reference"],
    "brand": ["brand", "marque", "brand_name", "manufacturer", "fabricant"],
    "category": ["product_type", "category", "categorie", "merchant_category", "category_path", "rayon",
                 "merchant_product_category_path", "categorie_marchand"],
    "image": ["image_link", "image", "image_url", "merchant_image_url", "aw_image_url", "large_image", "url_image"],
    "condition": ["condition", "etat"],
    "valid_until": ["sale_price_effective_date", "valid_to", "promo_end", "fin_promo", "date_fin_promo"],
    "lowest_30d": ["lowest_price_30d", "prix_plus_bas_30j", "prix_reference_30j", "lowest_30d"],
    "shipping": ["shipping.price", "delivery_cost", "shipping_cost", "frais_de_port", "frais_livraison", "shipping"],
    "seller": ["seller", "vendeur", "merchant_name", "vendu_par"],
    "properties": ["product_detail", "caracteristiques", "specifications", "specs", "attributs"],
}


class FeedError(ValueError):
    """Un flux illisible (format, encodage, élément introuvable) ou une correspondance invalide."""


# ------------------------------------------------------------------------------------------------ correspondance
class Mapping:
    def __init__(self, spec):
        self.spec = spec
        self.format = spec.get("format")
        self.encoding = spec.get("encoding")
        self.delimiter = spec.get("delimiter")
        items = spec.get("item")
        self.item = [items] if isinstance(items, str) else list(items or [])
        self.items = spec.get("items")
        self.fields = {k: ([v] if isinstance(v, str) else list(v)) for k, v in spec["fields"].items()}
        self.availability = {plain_key(k): v for k, v in (spec.get("availability") or {}).items()}
        self.properties = spec.get("properties")
        self.separator = spec.get("category_separator")
        self.currency = (spec.get("currency") or "EUR").upper()
        self.drop = {p.lower() for p in spec.get("drop_params") or ()}

    @classmethod
    def load(cls, obj, where="correspondance"):
        """obj : un objet JSON (dict). where : le nom donné dans les erreurs (le fichier ou la source)."""
        if not isinstance(obj, dict):
            raise FeedError(f"{where} : un objet JSON est attendu")
        unknown = set(obj) - OPTIONS
        if unknown:
            raise FeedError(f"{where} : option inconnue {', '.join(sorted(unknown))}")
        base = {}
        if obj.get("preset"):
            if obj["preset"] not in PRESETS:
                raise FeedError(f"{where} : préréglage inconnu {obj['preset']!r} (connus : {', '.join(PRESETS)})")
            base = json.loads(json.dumps(PRESETS[obj["preset"]]))
        spec = {**base, **{k: v for k, v in obj.items() if k not in ("fields", "preset")},
                "fields": {**base.get("fields", {}), **(obj.get("fields") or {})}}
        bad = set(spec["fields"]) - set(FIELDS)
        if bad:
            raise FeedError(f"{where} : champ inconnu {', '.join(sorted(bad))} (connus : {', '.join(FIELDS)})")
        missing = [f for f in REQUIRED if not spec["fields"].get(f)]
        if missing:
            raise FeedError(f"{where} : champ obligatoire sans colonne : {', '.join(missing)}")
        if spec.get("format") and spec["format"] not in FORMATS:
            raise FeedError(f"{where} : format {spec['format']!r} inconnu ({' | '.join(FORMATS)})")
        for k, v in spec["fields"].items():
            if not (isinstance(v, str) and v) and not (isinstance(v, list) and v and all(isinstance(x, str) and x for x in v)):
                if not (k == "properties" and isinstance(v, dict)):
                    raise FeedError(f"{where} : {k} : un nom de colonne, ou une liste de noms, est attendu")
        if isinstance(spec["fields"].get("properties"), dict):
            spec["properties"] = spec["fields"].pop("properties")
        for k, v in (spec.get("availability") or {}).items():
            if v not in ("in_stock", "out_of_stock", "preorder", "backorder", "unknown"):
                raise FeedError(f"{where} : disponibilité {k!r} → {v!r} : in_stock | out_of_stock | preorder | backorder | unknown")
        return cls(spec)

    def value(self, raw, field):
        """La première colonne prévue pour ce champ qui a une valeur (casse et accents ignorés)."""
        for key in self.fields.get(field, ()):
            v = raw.get(key)
            if v is None:
                v = raw.get(_folded(raw).get(plain_key(key)))
            if v not in (None, "", [], {}):
                return v
        return None


def plain_key(s):
    s = unicodedata.normalize("NFD", str(s).strip().lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9.@]+", "_", s).strip("_")


def _folded(raw):
    f = raw.get("\0folded")
    if f is None:
        f = {plain_key(k): k for k in raw if k != "\0folded"}
        raw["\0folded"] = f
    return f


# ------------------------------------------------------------------------------------------------ lecture du fichier
def unpack(raw):
    """Les octets du flux, décompressés (gzip, zip : le premier fichier)."""
    if raw[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(raw)
        except OSError as e:
            raise FeedError(f"gzip illisible : {e}") from None
    if raw[:4] == b"PK\x03\x04":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = [n for n in z.namelist() if not n.endswith("/")]
            if not names:
                raise FeedError("zip vide")
            return z.read(names[0])
    return raw


def sniff(raw, hint=None):
    """Le format d'un flux : celui donné, sinon d'après son début (XML, JSON, JSONL), sinon CSV."""
    if hint:
        return hint
    head = raw[:4096].lstrip(b"\xef\xbb\xbf \t\r\n")
    if head[:1] == b"<":
        return "xml"
    if head[:1] == b"[":
        return "json"
    if head[:1] == b"{":
        lines = [x for x in head.splitlines() if x.strip()]
        return "jsonl" if len(lines) > 1 and all(x.strip().startswith(b"{") for x in lines[:2]) and lines[0].strip().endswith(b"}") else "json"
    return "csv"


def decode(raw, encoding=None):
    if encoding:
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError) as e:
            raise FeedError(f"encodage {encoding} : {e}") from None
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def records(raw, mapping):
    """(rang, champs bruts) pour chaque produit du flux. FeedError si le fichier ne se lit pas."""
    raw = unpack(raw)
    fmt = sniff(raw, mapping.format)
    if fmt == "xml":
        yield from _xml(raw, mapping.item or ["item", "entry", "product", "produit", "offer"])
    elif fmt in ("csv", "tsv"):
        yield from _csv(decode(raw, mapping.encoding), "\t" if fmt == "tsv" else mapping.delimiter)
    elif fmt == "json":
        yield from _json(decode(raw, mapping.encoding), mapping.items)
    else:
        for n, line in enumerate(decode(raw, mapping.encoding).splitlines(), 1):
            if line.strip():
                try:
                    yield n, flatten(json.loads(line))
                except json.JSONDecodeError as e:
                    raise FeedError(f"JSONL illisible ligne {n} : {e.msg}") from None


def _csv(text, delimiter=None):
    first = text.split("\n", 1)[0]
    d = delimiter or max((";", ",", "\t", "|"), key=first.count)
    reader = csv.DictReader(io.StringIO(text), delimiter=d)
    if not reader.fieldnames or len(reader.fieldnames) < 2:
        raise FeedError("CSV : en-tête introuvable (séparateur ?)")
    for n, row in enumerate(reader, 2):
        yield n, {(k or "").strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}


def _local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _elem(e):
    """Un élément XML → dict : enfants par nom local (répétés : une liste), attributs en « nom@attribut »."""
    out = {f"@{_local(k)}": v for k, v in e.attrib.items()}
    for c in e:
        k = _local(c.tag)
        v = _elem(c) if len(c) else (c.text or "").strip()
        if len(c) == 0 and c.attrib:
            for ak, av in c.attrib.items():
                out[f"{k}@{_local(ak)}"] = av
        if k in out:
            out[k] = (out[k] if isinstance(out[k], list) else [out[k]]) + [v]
        else:
            out[k] = v
    return out


def _xml(raw, items):
    want, n = set(items), 0
    try:
        for _, e in ET.iterparse(io.BytesIO(raw), events=("end",)):
            if _local(e.tag) in want:
                n += 1
                yield n, flatten(_elem(e))
                e.clear()
    except ET.ParseError as err:
        raise FeedError(f"XML illisible après {n} produit(s) : {err}") from None
    if n == 0:
        raise FeedError(f"XML : aucun élément produit ({' | '.join(sorted(want))})")


def _json(text, path=None):
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise FeedError(f"JSON illisible : {e.msg} (ligne {e.lineno})") from None
    if path:
        for part in path.split("."):
            data = data.get(part) if isinstance(data, dict) else None
    elif isinstance(data, dict):
        data = next((v for k, v in data.items() if isinstance(v, list) and v and isinstance(v[0], dict)), None)
    if not isinstance(data, list):
        raise FeedError("JSON : liste de produits introuvable (option items)")
    for n, x in enumerate(data, 1):
        if isinstance(x, dict):
            yield n, flatten(x)


def flatten(d, prefix=""):
    """{"shipping": {"price": "0 EUR"}} → {"shipping.price": "0 EUR"} ; les listes restent des listes."""
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
            out.setdefault(key, v)
        else:
            out[key] = v
    return out


# ------------------------------------------------------------------------------------------------ normalisation
def text(v):
    if v is None:
        return None
    if isinstance(v, list):
        v = next((x for x in v if x not in (None, "")), None)
        if v is None:
            return None
    s = re.sub(r"\s+", " ", unescape(str(v))).strip()
    return s or None


def money(v, default=None):
    """(montant, devise) : « 549.00 EUR », « 549,00 € », « EUR 549 », 549 → (549.0, devise ou default)."""
    s = text(v)
    if s is None:
        return None, None
    code = re.search(r"\b([A-Z]{3})\b", s)
    cur = code.group(1) if code else parse_currency(None, s) or default
    return parse_price(re.sub(r"\b[A-Z]{3}\b", " ", s)), cur


def availability(v, extra=None):
    s = text(v)
    if s is None:
        return "unknown"
    k = plain_key(s).replace("_", " ")
    if extra:
        hit = extra.get(plain_key(s))
        if hit:
            return hit
    if re.fullmatch(r"\d+", s.strip()):
        return "in_stock" if int(s) > 0 else "out_of_stock"
    return AVAILABILITY.get(s.lower()) or AVAILABILITY.get(k) or parse_availability(s) or "unknown"


def end_date(v):
    """Fin d'une promotion : « 2026-11-01T00:00+0100/2026-11-30T23:59+0100 » → 2026-11-30 ; « 30/11/2026 » aussi."""
    s = text(v)
    if s is None:
        return None
    if re.match(r"\d{4}-\d{2}-\d{2}", s) and "/" in s:
        s = s.rsplit("/", 1)[-1].strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return "-".join(m.groups())
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", s)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def clean_url(u, drop=()):
    """L'adresse canonique de la fiche : http(s), sans paramètres de suivi (utm_…, gclid…) ni ancre."""
    s = text(u)
    if not s:
        return None
    p = urlsplit(s)
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not TRACKING.match(k) and k.lower() not in drop]
    return urlunsplit((p.scheme, p.netloc.lower(), p.path or "/", urlencode(q, doseq=True), ""))


def category(v, separator=None):
    if isinstance(v, list):
        v = " > ".join(x for x in (text(y) for y in v) if x)
    s = text(v)
    if s and separator and separator != ">":
        s = " > ".join(x.strip() for x in s.split(separator) if x.strip())
    return s


def properties(raw, mapping):
    """Les caractéristiques déclarées : {nom en minuscules: valeur} (comme extract : additionalProperty)."""
    out = {}
    if isinstance(mapping.properties, dict):
        for name, col in mapping.properties.items():
            v = text(raw.get(col))
            if v:
                out[name.strip().lower()] = v
        return out
    v = mapping.value(raw, "properties")
    if v is None:
        return out
    for x in v if isinstance(v, list) else [v]:
        if isinstance(x, dict):                              # Google : product_detail (attribute_name, attribute_value)
            name, val = text(x.get("attribute_name") or x.get("name")), text(x.get("attribute_value") or x.get("value"))
            if name and val:
                out[name.lower()] = val
        elif isinstance(x, str):                             # « Nom : valeur | Nom : valeur »
            for pair in re.split(r"\s*[|;]\s*", x):
                if ":" in pair:
                    name, _, val = pair.partition(":")
                    if name.strip() and val.strip():
                        out[name.strip().lower()] = val.strip()
    return out


def normalize(raw, mapping, fmt="feed"):
    """Les champs bruts d'un produit → l'offre normalisée (contract.py la contrôle ensuite)."""
    g = lambda f: mapping.value(raw, f)
    price, cur = money(g("price"), mapping.currency)
    sale, sale_cur = money(g("sale_price"), mapping.currency)
    listed, _ = money(g("list_price"), mapping.currency)
    if sale and (not price or sale < price):
        listed, price, cur = listed or price, sale, sale_cur or cur
    currency = (text(g("currency")) or cur or mapping.currency).upper()
    shipping, _ = money(g("shipping"), mapping.currency)
    if shipping is None and text(g("shipping")) and re.fullmatch(r"0+([.,]0+)?(\s*\w{0,3})?", text(g("shipping"))):
        shipping = 0.0                                       # « 0.00 EUR » : livraison offerte
    lowest, _ = money(g("lowest_30d"), mapping.currency)
    cond = text(g("condition"))
    return {"external_id": text(g("external_id")), "title": text(g("title")), "url": clean_url(g("url"), mapping.drop),
            "tracking_url": text(g("tracking_url")), "price": price, "list_price": listed, "currency": currency,
            "availability": availability(g("availability"), mapping.availability), "gtin": clean_gtin(text(g("gtin"))),
            "mpn": text(g("mpn")), "brand": text(g("brand")), "category": category(g("category"), mapping.separator),
            "image": text(g("image")), "condition": CONDITION.get((cond or "new").lower(), "new"),
            "valid_until": end_date(g("valid_until")), "lowest_30d": lowest, "shipping": shipping, "seller": text(g("seller")),
            "properties": properties(raw, mapping), "method": f"feed:{fmt}", "was_method": f"feed:{fmt}" if listed else None}


# ------------------------------------------------------------------------------------------------ échantillon
def probe(raw, hint=None, n=200):
    """Un échantillon de flux → {format, encoding, delimiter, item, columns, proposed, sample} : ce qui a été reconnu
    et la correspondance proposée (à relire, puis à enregistrer pour la source)."""
    data = unpack(raw)
    fmt = sniff(data, hint)
    info = {"format": fmt, "encoding": None, "delimiter": None, "item": None}
    if fmt in ("csv", "tsv", "json", "jsonl"):
        txt = decode(data)
        try:
            data.decode("utf-8-sig")
            info["encoding"] = "utf-8"
        except UnicodeDecodeError:
            info["encoding"] = "cp1252"
        if fmt == "csv":
            first = txt.split("\n", 1)[0]
            info["delimiter"] = max((";", ",", "\t", "|"), key=first.count)
    else:
        info["item"] = _repeated(data)
    spec = {k: v for k, v in (("format", fmt), ("encoding", info["encoding"] if info["encoding"] != "utf-8" else None),
                              ("delimiter", info["delimiter"]), ("item", info["item"])) if v}
    rows = []
    for _, r in records(data, Mapping({**spec, "fields": {"title": "title", "url": "url", "price": "price"}})):
        rows.append(r)
        if len(rows) >= n:
            break
    columns = sorted({k for r in rows for k in r if k != "\0folded"})
    google = fmt == "xml" and any(c in columns for c in ("g:price", "price")) and "link" in columns and "availability" in columns
    proposed = {"preset": "google_shopping"} if google else {**spec, "fields": guess(columns)}
    info.update(columns=columns, proposed=proposed, rows=len(rows),
                sample=[{k: v for k, v in r.items() if k != "\0folded"} for r in rows[:3]])
    return info


def guess(columns):
    folded = {plain_key(c): c for c in columns}
    out = {}
    for field, names in GUESS.items():
        hit = next((folded[plain_key(x)] for x in names if plain_key(x) in folded), None)
        if hit and hit not in out.values():
            out[field] = hit
    return out


ITEMS = ("item", "entry", "product", "produit", "offer", "article")


def _repeated(raw):
    """L'élément produit d'un XML inconnu : un nom d'usage (item, entry, product…) s'il y est, sinon l'élément répété le
    plus souvent qui a des enfants, et à égalité celui qui en a le plus (un produit plutôt que l'une de ses parties)."""
    counts, kids = {}, {}
    try:
        for _, e in ET.iterparse(io.BytesIO(raw), events=("end",)):
            if len(e):
                k = _local(e.tag)
                counts[k], kids[k] = counts.get(k, 0) + 1, kids.get(k, 0) + len(e)
    except ET.ParseError:
        pass
    if not counts:
        return None
    return max(counts, key=lambda k: (k in ITEMS, counts[k] > 1, kids[k] / counts[k], counts[k]))
