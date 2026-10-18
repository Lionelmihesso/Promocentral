"""Mesure de l'extraction, reproductible hors ligne :  python -m bench.extraction

- chaînes de prix réelles (corpus price-parser, 1 040 exemples) ;
- JSON-LD mal formés tirés de bugs réels (corpus extruct, 36 cas) ;
- spécification robots.txt (cas Protego / Google, 66 cas) ;
- pages-pièges construites sur des motifs réels (tests/pages.py : 25 réglées + 8 écrites après réglage) ;
- temps CPU sur une grande page produit (~450 Ko : méga-menu, scripts, carrousel).
Les pages réelles des enseignes se mesurent sur le serveur : python deals.py diagnose all.
"""
import json
import time
from pathlib import Path

from deals import extract as X
from deals.extract.page import jsonld_items
from deals.vendor.protego import Protego
from tests.pages import HELDOUT, PAGES
from tests.test_extract import outcome

CORPUS = Path(__file__).resolve().parent.parent / "tests" / "corpus"


def prices():
    ex = json.loads((CORPUS / "price_strings.json").read_text(encoding="utf-8"))["examples"]
    ok = 0
    for e in ex:
        got, want = X.parse_price(e["price_raw"]), e["amount"]
        ok += (got in (None, 0)) if want == 0 else (got is None if want is None else got is not None and abs(got - want) < 1e-6 * max(1, want))
    return ok, len(ex)


def jsonld():
    cases = json.loads((CORPUS / "jsonld_cases.json").read_text(encoding="utf-8"))["cases"]
    return sum(jsonld_items(c["html"]) == c["expected"] for c in cases), len(cases)


def robots():
    spec = json.loads((CORPUS / "robots_spec.json").read_text(encoding="utf-8"))["cases"]
    ok = n = 0
    prec = ("user-agent: hedwig-news\ndisallow: /\nallow: /group1\nuser-agent: *\ndisallow: /\nallow: /group2\n"
            "user-agent: hedwig\ndisallow: /\nallow: /group3\n")
    for path, ua in spec["test_user_agent_precedence"]:
        n += 1
        rp = Protego.parse(prec)
        ok += next((p for p in ("/group1", "/group2", "/group3") if rp.can_fetch(p, ua)), None) == path
    for pattern, path, match in spec["test_path_matching"]:
        n += 1
        ok += (not Protego.parse(f"User-Agent: *\ndisallow: {pattern}\n").can_fetch(path, "*")) == match
    for rules, url, allowed in spec["test_record_precedence"]:
        n += 1
        ok += Protego.parse("User-Agent: *\n" + "\n".join(r.strip() for r in rules.split("\n"))).can_fetch(url, "*") == allowed
    for robots_ua, crawler_ua, applies in spec["test_user_agent_boundary_matching"]:
        n += 1
        ok += (not Protego.parse(f"User-Agent: {robots_ua}\nDisallow: /private\n").can_fetch("http://example.com/private", crawler_ua)) == applies
    return ok, n


def pages(group):
    ok = sum(all(outcome(p).get(k) == v for k, v in p["expect"].items()) for p in group.values())
    return ok, len(group)


def big_page_ms():
    menu = "".join(f"<li class='menu__item'><a class='menu__link' href='/c/categorie-{i}'>Catégorie {i}</a></li>" for i in range(1800))
    cards = "".join(f"<div class='card'><a href='/p/{i}'><span>Produit associé {i}</span><del>{199 + i},00 €</del> "
                    f"<span class='card__price'>{149 + i},00 €</span></a></div>" for i in range(40))
    state = "<script>window.__INITIAL_STATE__ = " + json.dumps({"catalog": [{"id": i, "name": f"x{i}", "tags": ["a"] * 20} for i in range(600)]}) + ";</script>"
    ld = "<script type='application/ld+json'>" + json.dumps({"@type": "Product", "name": "Canapé d'angle convertible Oslo", "offers": {
        "@type": "Offer", "price": 899.0, "priceCurrency": "EUR"}}) + "</script>"
    html = (f"<html><head><title>Canapé d'angle convertible Oslo</title>{ld}{state}</head><body><ul>{menu}</ul><h1>Canapé d'angle convertible Oslo</h1>"
            f"<div class='price'><span class='price__old'>1 299,00 €</span> <span class='price__now'>899,00 €</span></div>"
            f"<p>{'Tissu déhoussable, assise en mousse haute résilience. ' * 400}</p><section>{cards}</section><ul>{menu[:200000]}</ul></body></html>")
    X.extract(html)
    t, n = time.process_time(), 10
    for _ in range(n):
        X.extract(html)
    return len(html.encode()) // 1024, (time.process_time() - t) / n * 1000


if __name__ == "__main__":
    for label, (ok, n) in (("chaînes de prix réelles", prices()), ("JSON-LD mal formés", jsonld()), ("spécification robots.txt", robots()),
                           ("pages-pièges (réglées)", pages(PAGES)), ("pages-pièges (écrites après réglage)", pages(HELDOUT))):
        print(f"{label:<38} {ok}/{n}")
    kb, ms = big_page_ms()
    print(f"{'temps CPU, page de ' + str(kb) + ' Ko':<38} {ms:.0f} ms")
