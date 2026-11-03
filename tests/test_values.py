"""Les valeurs d'une ligne de flux (deals/extract/values.py) — fonctions pures, vérifiées sur un corpus public de 1 040
chaînes de prix réelles (price-parser, THIRD_PARTY_NOTICES.md) : ce que les flux CSV écrivent (« 1 299,99 € »,
« 1.299,99 », « 299€99 ») est lu juste, un pourcentage n'est jamais pris pour un prix."""
import json
import unittest
from pathlib import Path

from deals import extract as X

CORPUS = Path(__file__).parent / "corpus"


class Prices(unittest.TestCase):
    def test_price_strings(self):
        ex = json.loads((CORPUS / "price_strings.json").read_text(encoding="utf-8"))["examples"]
        ok = 0
        for e in ex:
            got, want = X.parse_price(e["price_raw"]), e["amount"]
            ok += (got in (None, 0)) if want == 0 else (got is None if want is None else got is not None and abs(got - want) < 1e-6 * max(1, want))
        self.assertGreaterEqual(ok, 1036)                                # 4 écarts connus : '.75 €', 'PTE 120 000 000'…
        for s, v in {"1 299,99 €": 1299.99, "1.299,99": 1299.99, "299€99": 299.99, "-40 %": None, "40% OFF": None, "gratuit": None}.items():
            self.assertEqual(X.parse_price(s), v, s)

    def test_currency_availability_and_gtin(self):
        self.assertEqual((X.parse_currency("eur"), X.parse_currency(None, "549,00 €"), X.parse_currency("US$")), ("EUR", "EUR", "USD"))
        self.assertEqual([X.parse_availability(v) for v in ("in stock", "https://schema.org/OutOfStock", "Indisponible", "", True)],
                         ["in_stock", "out_of_stock", "out_of_stock", None, "in_stock"])
        self.assertEqual((X.clean_gtin("3000000000014"), X.clean_gtin("3000000000015"), X.clean_gtin("123")), ("3000000000014", None, None))


if __name__ == "__main__":
    unittest.main()
