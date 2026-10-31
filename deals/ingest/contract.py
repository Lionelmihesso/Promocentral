"""Le contrat de l'ingestion : une offre normalisée, la même qu'elle vienne d'un flux (feeds.py) ou d'une fiche
(extract/), contrôlée avant d'entrer au marché (market.py). Pur.

Champs : url (adresse de la fiche, canonique), title, brand, gtin (EAN vérifié), mpn (référence fabricant), category
(catégorie déclarée par l'enseigne), image, price (prix payé aujourd'hui, en euros), list_price (prix barré déclaré),
lowest_30d (« prix le plus bas des 30 derniers jours » déclaré), valid_until (fin de la promotion), availability
(in_stock | out_of_stock | preorder | backorder | unknown), currency, condition (new | used | refurbished), shipping
(frais de livraison ; None : inconnus), seller, properties (caractéristiques déclarées), external_id (l'identifiant de
l'offre dans le flux), tracking_url (le lien de suivi donné par le réseau), method et was_method (provenance).

  check(offre)    → (offre, None) si elle est recevable, sinon (None, raison) ; un prix barré invraisemblable est écarté
                    sans écarter l'offre (offre["notes"] le dit)
  in_scope(offre) → None si l'offre entre au catalogue à sa première lecture, sinon la raison (accessoire, famille non
                    suivie, sous le seuil de prix du rayon)
Les mêmes règles pour toutes les sources : une enseigne qui passe de ses fiches à son flux garde les mêmes garde-fous.
"""
from .. import extract as X
from ..extract.offer import MAX_DISCOUNT, MAX_PRICE
from ..labels import CATEGORY_LABEL
from .retailers import FAMILY_OF, MIN_PRICE, MIN_PRICE_CATEGORY

AVAILABILITY = ("in_stock", "out_of_stock", "preorder", "backorder", "unknown")


def check(rec):
    if not rec.get("url"):
        return None, "adresse de fiche manquante ou invalide"
    if not rec.get("title"):
        return None, "titre manquant"
    currency = (rec.get("currency") or "EUR").upper()
    if currency != "EUR":
        return None, f"devise {currency} refusée"
    price = rec.get("price")
    if not price or price <= 0:
        return None, "prix manquant"
    if price > MAX_PRICE:
        return None, "prix invraisemblable"
    if rec.get("condition") in ("used", "refurbished"):
        return None, "occasion ou reconditionné"
    out, notes = {**rec, "currency": "EUR"}, []
    listed = out.get("list_price")
    if listed and (listed <= price * 1.01 or 1 - price / listed > MAX_DISCOUNT):
        out["list_price"] = out["was_method"] = None
        notes.append("prix barré invraisemblable écarté")
    if out.get("lowest_30d") is not None and out["lowest_30d"] <= 0:
        out["lowest_30d"] = None
    if out.get("shipping") is not None and out["shipping"] < 0:
        out["shipping"] = None
    if out.get("availability") not in AVAILABILITY:
        out["availability"] = "unknown"
    out["notes"] = notes
    return out, None


def in_scope(ex):
    """Première lecture d'une offre : None si elle entre au catalogue, sinon la raison."""
    cat, src = X.categorize(ex.get("title"), ex.get("category"))
    fam = FAMILY_OF.get(cat)
    if fam is None:
        return "accessoire" if src == "accessory" else f"hors des familles suivies ({cat or 'catégorie inconnue'})"
    floor = MIN_PRICE_CATEGORY.get(cat, MIN_PRICE[fam])
    if ex["price"] < floor:
        return f"{ex['price']:.2f} € : sous le seuil de {floor:.0f} € ({CATEGORY_LABEL.get(cat, fam).lower()}), accessoire probable"
    return None
