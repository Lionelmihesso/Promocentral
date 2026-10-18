"""Lecture d'une page produit — fonctions pures (aucune base, aucun réseau).

  analyze(html, rules, url, merchant) → {page_kind, best, candidates, reasons}
  extract(html, rules, url, merchant) → offre | None
  categorize(title, declared) → (catégorie | None, source) ; attributes(title, properties) → dict

Offre (dict) : price, list_price (prix barré validé), was_method, currency, currency_known, availability, title, brand,
gtin, mpn, sku, seller, marketplace, category, image, properties, valid_until, lowest_30d, kind ("from" : à partir de),
member_price, method (source du prix), confidence, found (prix par source), consistent, reasons.
"""
from .categories import attributes, categorize, plain
from .offer import (analyze, clean_gtin, compile_selector, extract, lowest_30d, parse_availability, parse_currency,
                    parse_price)

__all__ = ["analyze", "extract", "categorize", "attributes", "plain", "parse_price", "parse_currency",
           "parse_availability", "clean_gtin", "lowest_30d", "compile_selector"]
