"""Faux sites d'enseignes, servis en local, pour les tests de bout en bout (aucun accès au web).

Chaque site a un robots.txt, un index de plans de site (dont un fichier compressé) et des fiches dont l'état se règle
pendant le test (prix, prix barré, page liste, autre produit). Site « a » : JSON-LD ; « b » : balises meta + microdonnées ;
« c » : protégé par un anti-robot (403).
"""
import gzip
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def ean(body12):
    total = sum(int(x) * (3 if i % 2 else 1) for i, x in enumerate(body12))
    return body12 + str((10 - total % 10) % 10)


EAN = {"lave_linge": ean("424200500002"), "canape": ean("366300000001"), "matelas": ean("366728702075"),
       "protege": ean("333333000004"), "lit": ean("366300000002"), "frigo": ean("880609500006"), "frigo2": ean("880609500013")}

# site -> sku -> fiche (modifiable pendant le test)
CATALOG = {
    "a": {"1001": {"slug": "lave-linge", "title": "Lave-linge hublot Bosch Série 6 9 kg", "brand": "Bosch", "gtin": EAN["lave_linge"], "price": 649, "strike": 799},
          "1002": {"slug": "canape", "title": "Canapé d'angle convertible Oslo", "brand": "Oslo", "gtin": EAN["canape"], "price": 1299},
          "1003": {"slug": "matelas", "title": "Matelas mousse 140x190 Bultex Integral 3", "brand": "Bultex", "gtin": EAN["matelas"], "price": 529.99,
                   "html_strike": 879.99},
          "1004": {"slug": "matelas", "title": "Protège-matelas 140x190 imperméable", "brand": "Dodo", "gtin": EAN["protege"], "price": 29}},
    "b": {"2001": {"slug": "lave-linge", "title": "Lave-linge Bosch Série 6 9kg hublot", "brand": "Bosch", "gtin": EAN["lave_linge"], "price": 679},
          "2002": {"slug": "lit-coffre", "title": "Lit coffre 160x200 Nils", "brand": "Nils", "gtin": EAN["lit"], "price": 459},
          "2003": {"slug": "refrigerateur", "title": "Réfrigérateur combiné Samsung RB38", "brand": "Samsung", "gtin": EAN["frigo"], "price": 699}},
    "c": {"3001": {"slug": "canape", "title": "Canapé 3 places velours Ines", "brand": "Ines", "gtin": ean("366300000003"), "price": 899}},
}
STATE = {"listing": set(), "other": {}}     # skus servies en page liste ; skus montrant un autre produit (sku → fiche)


def product_html(site, item):
    title = item["title"]
    if site == "a":
        offer = {"@type": "Offer", "price": str(item["price"]), "priceCurrency": "EUR", "availability": "https://schema.org/InStock"}
        if item.get("strike"):
            offer["priceSpecification"] = [{"@type": "UnitPriceSpecification", "priceType": "https://schema.org/StrikethroughPrice",
                                            "price": item["strike"], "priceCurrency": "EUR"}]
        ld = {"@context": "https://schema.org", "@type": "Product", "name": title, "brand": {"@type": "Brand", "name": item["brand"]},
              "gtin13": item["gtin"], "offers": offer}
        block = ""
        if item.get("html_strike"):
            block = (f"<div class='product-price'><span class='price__old'>{item['html_strike']:.2f} €".replace(".", ",") +
                     f"</span> <span class='price__now'>{item['price']:.2f} €".replace(".", ",") + "</span></div>")
        if item.get("omnibus"):
            block += f"<p class='legal'>Prix le plus bas pratiqué au cours des 30 derniers jours : {item['omnibus']}</p>"
        return (f"<html><head><title>{title}</title><script type='application/ld+json'>{json.dumps(ld, ensure_ascii=False)}</script>"
                f"</head><body><h1>{title}</h1>{block}</body></html>")
    return (f"<html><head><title>{title}</title><meta property='og:title' content=\"{title}\"><meta property='product:price:amount' "
            f"content='{item['price']}'><meta property='product:price:currency' content='EUR'><meta property='product:brand' "
            f"content='{item['brand']}'></head><body itemscope itemtype='https://schema.org/Product'><span itemprop='gtin13'>{item['gtin']}"
            f"</span><h1>{title}</h1></body></html>")


def listing_html():
    items = [{"@type": "ListItem", "position": i + 1, "item": {"@type": "Product", "name": f"Modèle {i}", "offers": {"@type": "Offer", "price": 300 + i}}}
             for i in range(5)]
    return f"<html><head><title>Matelas</title><script type='application/ld+json'>{json.dumps({'@type': 'ItemList', 'itemListElement': items})}</script></head><body><h1>Matelas</h1></body></html>"


def handler(site):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            base = f"http://127.0.0.1:{self.server.server_port}"
            if self.path == "/robots.txt":
                return self.send(200, f"User-agent: *\nDisallow: /panier\nSitemap: {base}/sitemap_index.xml\n".encode(), "text/plain")
            if self.path == "/sitemap_index.xml":
                return self.send(200, f'<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                      f'<sitemap><loc>{base}/sitemap-categories.xml</loc></sitemap>'
                                      f'<sitemap><loc>{base}/sitemap-products-1.xml.gz</loc></sitemap></sitemapindex>'.encode(), "application/xml")
            if self.path == "/sitemap-categories.xml":
                return self.send(200, f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{base}/c/canape</loc></url></urlset>'.encode(),
                                 "application/xml")
            if self.path == "/sitemap-products-1.xml.gz":
                locs = "".join(f"<url><loc>{base}/p/{it['slug']}-{sku}.html</loc></url>" for sku, it in CATALOG[site].items())
                locs += f"<url><loc>{base}/panier/1.html</loc></url>"
                return self.send(200, gzip.compress(f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>'.encode()),
                                 "application/gzip")
            if self.path.startswith("/p/"):
                sku = self.path.rsplit("-", 1)[1].split(".")[0]
                if site == "c":
                    return self.send(403, b"<html><body>Please complete the captcha (DataDome)</body></html>")
                if sku in STATE["listing"]:
                    body = listing_html()
                elif sku in STATE["other"]:
                    body = product_html(site, STATE["other"][sku])
                elif sku in CATALOG[site]:
                    body = product_html(site, CATALOG[site][sku])
                else:
                    return self.send(404, b"not found")
                etag = '"' + hashlib.md5(body.encode()).hexdigest() + '"'
                if self.headers.get("If-None-Match") == etag:
                    self.send_response(304)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                return self.send(200, body.encode(), extra={"ETag": etag})
            self.send(404, b"not found")
    return H


class Sites:
    """with Sites() as s : s.retailers (configuration des enseignes), s.url(site, sku)."""

    def __enter__(self):
        self.servers = {}
        for site in CATALOG:
            srv = ThreadingHTTPServer(("127.0.0.1", 0), handler(site))
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            self.servers[site] = srv
        self.retailers = {s: {"name": f"Site {s.upper()}", "home": f"http://127.0.0.1:{srv.server_port}", "enabled": True,
                              "families": ["electromenager", "ameublement", "literie"], "product_url": r"/p/[a-z-]+-\d+\.html", "sitemaps": []}
                          for s, srv in self.servers.items()}
        return self

    def url(self, site, sku):
        return f"{self.retailers[site]['home']}/p/{CATALOG[site][sku]['slug']}-{sku}.html"

    def __exit__(self, *a):
        for srv in self.servers.values():
            srv.shutdown()
            srv.server_close()
