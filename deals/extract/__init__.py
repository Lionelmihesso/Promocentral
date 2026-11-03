"""Ce que dit une offre — fonctions pures (aucune base, aucun réseau).

  categorize(title, declared) → (catégorie | None, source) ; attributes(title, properties, category, declared) → dict ;
  product_attributes(title, category, stored, props, declared) → les caractéristiques gardées d'un produit
  parse_price, parse_currency, parse_availability, clean_gtin : les valeurs d'une ligne de flux (values.py)

v68 : la plateforme ne lit plus que les flux des enseignes partenaires ; l'analyse des fiches HTML (JSON-LD,
microdonnées, règles de site) est retirée.
"""
from .categories import attributes, categorize, plain, product_attributes
from .values import clean_gtin, parse_availability, parse_currency, parse_price

__all__ = ["categorize", "attributes", "product_attributes", "plain", "parse_price", "parse_currency", "parse_availability",
           "clean_gtin"]
