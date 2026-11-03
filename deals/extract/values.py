"""Lecture des valeurs d'une offre, telles que les flux les écrivent — fonctions pures (ni base, ni réseau).

  parse_price("1 299,99 €") → 1299.99 ; parse_currency("EUR", texte) → "EUR" ; parse_availability("in stock") → "in_stock" ;
  clean_gtin("3 000000 000014") → "3000000000014" (clé de contrôle vérifiée, sinon None)
MAX_PRICE et MAX_DISCOUNT bornent ce que le contrat d'un flux accepte (ingest/contract.py). Avant la v68, ces lecteurs
vivaient avec l'analyse des fiches HTML (extract/offer.py), retirée avec la lecture des sites des enseignes.
"""
import re
from html import unescape

AVAIL = {
    "instock": "in_stock", "onlineonly": "in_stock", "limitedavailability": "in_stock", "instoreonly": "in_stock",
    "outofstock": "out_of_stock", "soldout": "out_of_stock", "discontinued": "out_of_stock",
    "preorder": "preorder", "presale": "preorder", "backorder": "backorder",
    "in stock": "in_stock", "out of stock": "out_of_stock", "en stock": "in_stock", "rupture": "out_of_stock",
    "épuisé": "out_of_stock", "epuise": "out_of_stock", "indisponible": "out_of_stock", "disponible": "in_stock",
}
CURRENCY_SYMBOLS = {"€": "EUR", "$": "USD", "£": "GBP", "CHF": "CHF"}
MAX_PRICE = 50000.0          # au-delà : centimes, référence ou erreur de saisie
MAX_DISCOUNT = 0.85


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
