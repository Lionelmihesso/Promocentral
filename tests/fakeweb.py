"""Faux web local pour tester l'écoute du marché sans réseau.

FIXTURES reproduit les formats rencontrés sur les sites marchands (JSON-LD simple, @graph,
places de marché, AggregateOffer, priceSpecification, JSON cassé, microdonnées, OpenGraph,
prix en texte « 299€99 », pages sans données structurées, pages de blocage).
Le serveur sert aussi des pages « vivantes » dont le prix change à la demande.
"""
import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def page(head="", body=""):
    return f"<!doctype html><html><head><meta charset='utf-8'><title>Boutique</title>{head}</head><body>{body}</body></html>"


def ld(obj):
    import json
    return f"<script type=\"application/ld+json\">{json.dumps(obj, ensure_ascii=False)}</script>"


# nom -> (html, attendu) ; attendu None = aucun prix ne doit être trouvé
FIXTURES = {
    "jsonld_simple": (page(ld({"@context": "https://schema.org", "@type": "Product", "name": "Lave-vaisselle Nordvik Clean 60",
                                "gtin13": "4006381333931", "mpn": "NCL60", "brand": {"@type": "Brand", "name": "Nordvik"},
                                "offers": {"@type": "Offer", "price": "449.99", "priceCurrency": "EUR",
                                           "availability": "https://schema.org/InStock"}})),
                      {"price": 449.99, "currency": "EUR", "availability": "in_stock", "gtin": "4006381333931", "method": "jsonld"}),
    "jsonld_graph_marketplace": (page(ld({"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage", "name": "Fiche"}, {"@type": "BreadcrumbList", "itemListElement": []},
        {"@type": ["Product", "Thing"], "name": "Aurel Serie 6", "sku": "A6", "offers": [
            {"@type": "Offer", "price": 799, "priceCurrency": "EUR", "availability": "OutOfStock", "seller": {"name": "Vendeur A"}},
            {"@type": "Offer", "price": 829, "priceCurrency": "EUR", "availability": "InStock", "seller": {"name": "Vendeur B"}},
            {"@type": "Offer", "price": 845, "priceCurrency": "EUR", "availability": "InStock", "seller": {"name": "Vendeur C"}}]}]})),
        {"price": 829.0, "availability": "in_stock", "method": "jsonld"}),
    "jsonld_aggregate": (page(ld({"@context": "https://schema.org", "@type": "Product", "name": "Kessler KD 5000",
                                   "offers": {"@type": "AggregateOffer", "lowPrice": "399,00", "highPrice": "459,00",
                                              "priceCurrency": "EUR", "offerCount": 4}})),
                         {"price": 399.0, "currency": "EUR", "method": "jsonld"}),
    "jsonld_pricespec": (page(ld({"@context": "https://schema.org", "@type": "Product", "name": "Solenne Libre 14",
                                   "offers": {"@type": "Offer", "availability": "http://schema.org/InStock",
                                              "priceSpecification": {"@type": "UnitPriceSpecification", "price": 649.0, "priceCurrency": "EUR"}}})),
                         {"price": 649.0, "availability": "in_stock", "method": "jsonld"}),
    "jsonld_trailing_comma": (page("<script type='application/ld+json'>{\"@type\":\"Product\",\"name\":\"X\",\"offers\":{\"@type\":\"Offer\",\"price\":\"379.00\",\"priceCurrency\":\"EUR\",},}</script>"),
                              {"price": 379.0, "method": "jsonld"}),
    "jsonld_preorder": (page(ld({"@type": "Product", "name": "Nouveau modèle 2027",
                                  "offers": {"@type": "Offer", "price": "999", "priceCurrency": "EUR", "availability": "PreOrder"}})),
                        {"price": 999.0, "availability": "preorder"}),
    "microdata_content": (page(body="""<div itemscope itemtype="https://schema.org/Product"><h1 itemprop="name">Integra 60</h1>
        <meta itemprop="gtin13" content="4006381333931"><div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
        <span itemprop="price" content="529.00">529,00&nbsp;€</span><meta itemprop="priceCurrency" content="EUR">
        <link itemprop="availability" href="http://schema.org/OutOfStock"></div></div>"""),
                          {"price": 529.0, "currency": "EUR", "availability": "out_of_stock", "method": "microdata"}),
    "microdata_text": (page(body="""<div itemscope itemtype="http://schema.org/Product"><span itemprop="name">Slim 45</span>
        <div itemprop="offers" itemscope itemtype="http://schema.org/Offer"><span class="p" itemprop="price">1&nbsp;049,90 €</span>
        <span itemprop="availability">En stock</span></div></div>"""),
                       {"price": 1049.9, "currency": "EUR", "availability": "in_stock", "method": "microdata"}),
    "opengraph": (page(head="""<meta property="og:title" content="Lave-vaisselle Kessler"><meta property="product:price:amount" content="379.00">
        <meta property="product:price:currency" content="EUR"><meta property="product:availability" content="in stock">"""),
                  {"price": 379.0, "currency": "EUR", "availability": "in_stock", "method": "opengraph"}),
    "inconsistent_sources": (page(head='<meta property="product:price:amount" content="499.00">',
                                  body=ld({"@type": "Product", "name": "Y", "offers": {"@type": "Offer", "price": "459.00", "priceCurrency": "EUR"}})),
                             {"price": 459.0, "method": "jsonld", "consistent": False}),
    "text_only_needs_rule": (page(body='<div class="fiche"><h1>Lave-vaisselle Aurel</h1><div class="prix-final">299€99</div>'
                                       '<p class="stock">Disponible</p></div>'),
                             None),
    "category_page": (page(body="<h1>Lave-vaisselle</h1><ul><li>Modèle A</li><li>Modèle B</li></ul>"), None),
    "html_entities_ld": (page("<script type=\"application/ld+json\">{&quot;@type&quot;:&quot;Product&quot;,&quot;name&quot;:&quot;Z&quot;,"
                              "&quot;offers&quot;:{&quot;@type&quot;:&quot;Offer&quot;,&quot;price&quot;:&quot;589.00&quot;,&quot;priceCurrency&quot;:&quot;EUR&quot;}}</script>"),
                         {"price": 589.0, "method": "jsonld"}),
}
RULE_FIXTURE = ("text_only_needs_rule", {"price": "div.prix-final", "availability": "p.stock"},
                {"price": 299.99, "availability": "in_stock", "method": "rules"})


def live_page(pid, price, avail="InStock", gtin=None):
    return page(ld({"@context": "https://schema.org", "@type": "Product", "name": f"Produit {pid}", "gtin13": gtin,
                    "brand": {"name": "Nordvik"}, "mpn": f"MPN-{pid}",
                    "offers": {"@type": "Offer", "price": f"{price:.2f}", "priceCurrency": "EUR", "availability": avail}}))


class FakeWeb:
    """Serveur local. LIVE[pid] = (prix, disponibilité, gtin) modifiable pendant les tests."""

    def __init__(self, port=0, robots="User-agent: *\nDisallow: /private/\n"):
        self.live, self.hits, self.robots = {}, {}, robots
        web = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body="", headers=None):
                data = body.encode()
                self.send_response(code)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                p = self.path
                web.hits[p] = web.hits.get(p, 0) + 1
                if p == "/robots.txt":
                    return self._send(200, web.robots) if web.robots is not None else self._send(404)
                if p.startswith("/f/"):
                    name = p[3:]
                    return self._send(200, FIXTURES[name][0]) if name in FIXTURES else self._send(404)
                if p.startswith("/live/"):
                    pid = p[6:]
                    if pid not in web.live:
                        return self._send(404)
                    price, avail, gtin = web.live[pid]
                    body = live_page(pid, price, avail, gtin)
                    etag = '"' + hashlib.md5(body.encode()).hexdigest()[:12] + '"'
                    if self.headers.get("If-None-Match") == etag:
                        return self._send(304, "", {"ETag": etag})
                    return self._send(200, body, {"ETag": etag})
                if p == "/blocked":
                    return self._send(403, "<html><body>Please complete the captcha — DataDome</body></html>")
                if p == "/soft-blocked":
                    return self._send(200, "<html><body><div id='px-captcha'></div>Are you a robot?</body></html>")
                if p == "/rate":
                    return self._send(429, "Too many requests", {"Retry-After": "600"})
                if p == "/boom":
                    return self._send(503, "maintenance")
                return self._send(404)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def __enter__(self):
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()
