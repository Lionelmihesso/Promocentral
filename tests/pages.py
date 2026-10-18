"""Pages de test construites à partir de motifs RÉELS observés (pas des pages réelles : celles-ci se mesurent avec
`python collect.py diagnose` et `python collect.py sample`, qui demandent un accès au web).

Motifs relevés le 18/10/2026 sur des pages publiques, ou documentés :
- But (fiche matelas) : prix barré 879,99 € à côté de 529,99 €, « -40% », « dont eco-part. de 11,00€ ».
- Boulanger (fiche lave-linge) : « 433,69€ dont 15,42€ d'éco-part. 108,42€/mois en 4x », « 6 autres offres Dès 438,63€ »,
  offre principale vendue par un vendeur tiers.
- La Redoute (fiche canapé) : prix public 2900,00 € et « Prix pour les membres LR+ 2037,80 € », variantes « Dès … ».
- Electro Dépôt : prix au format « 279€98 », paires « 359€98 349€98 », fiche produit redirigée vers une page liste.
- Google, données structurées « merchant listing » : prix barré = priceSpecification avec priceType StrikethroughPrice ;
  prix membre = validForMemberTier, à ne jamais prendre pour le prix public.
- Cloudflare : en-tête « cf-mitigated: challenge » ; DataDome : en-tête x-datadome, cookie datadome, captcha-delivery.com.

Groupes : « piège » = risque d'enregistrer une donnée fausse ; « couverture » = donnée réelle manquée ;
« donnée » = information nouvelle (fin de promotion…).
"""
import json


def page(head="", body="", title="Fiche produit"):
    return (f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><title>{title}</title>{head}</head>"
            f"<body><header><nav><a href='/'>Accueil</a> <a href='/promo'>Promos jusqu'à -50%</a></nav></header>{body}</body></html>")


def ld(obj):
    return f"<script type=\"application/ld+json\">{json.dumps(obj, ensure_ascii=False)}</script>"


def product(name, price=None, offers=None, **kw):
    o = offers if offers is not None else {"@type": "Offer", "price": price, "priceCurrency": "EUR",
                                           "availability": "https://schema.org/InStock"}
    return {"@context": "https://schema.org", "@type": "Product", "name": name, "offers": o, **kw}


STRIKE = lambda p: {"@type": "UnitPriceSpecification", "priceType": "https://schema.org/StrikethroughPrice", "price": p, "priceCurrency": "EUR"}
MEMBER = lambda p: {"@type": "UnitPriceSpecification", "price": p, "priceCurrency": "EUR",
                    "validForMemberTier": {"@type": "MemberProgramTier", "@id": "https://exemple.fr/club#membre"}}

RELATED = {"@context": "https://schema.org", "@type": "ItemList", "name": "Vous aimerez aussi", "itemListElement": [
    {"@type": "ListItem", "position": i + 1, "item": product(f"Accessoire {i + 1}", p, url=f"https://exemple.fr/p/acc-{i}")}
    for i, p in enumerate([49.99, 59.99, 69.99])]}

LISTING = {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
    {"@type": "ListItem", "position": i + 1, "item": product(f"Lave-linge frontal VALBERG WF {n}", p, url=f"https://exemple.fr/lave-linge-{n}.html")}
    for i, (n, p) in enumerate([("914", 279.98), ("510", 184.83), ("1214", 349.98), ("814", 289.98), ("1014", 329.98), ("940", 319.98)])]}

PAGES = {
    # ------------------------------------------------------------------ pièges
    "membre_seul_en_specs": dict(group="piège", html=page(ld(product("Canapé compact convertible velours Lazare", offers={
        "@type": "Offer", "availability": "https://schema.org/InStock",
        "priceSpecification": [MEMBER(2037.80), {"@type": "UnitPriceSpecification", "price": 2900.00, "priceCurrency": "EUR"}]}))),
        expect={"status": "ok", "price": 2900.0, "was": None}),
    "membre_et_barre": dict(group="piège", html=page(ld(product("Lave-vaisselle Bosch Série 4", offers={
        "@type": "Offer", "price": 899.0, "priceCurrency": "EUR", "availability": "https://schema.org/InStock",
        "priceSpecification": [MEMBER(849.0), STRIKE(1099.0)]}))),
        expect={"status": "ok", "price": 899.0, "was": 1099.0}),
    "produits_associes_avant": dict(group="piège", html=page(
        ld({"@context": "https://schema.org", "@graph": [RELATED, product("Réfrigérateur combiné Samsung RB38", 649.0,
                                                                          url="https://exemple.fr/p/rb38")]}),
        "<h1>Réfrigérateur combiné Samsung RB38</h1>"), url="https://exemple.fr/p/rb38",
        expect={"status": "ok", "price": 649.0}),
    "microdonnees_carrousel_avant": dict(group="piège", html=page(body="""
        <section class="carousel"><h2>Vous aimerez aussi</h2>
          <div itemscope itemtype="https://schema.org/Product"><span itemprop="name">Pieds de lit x4</span>
            <div itemprop="offers" itemscope itemtype="https://schema.org/Offer"><span itemprop="price" content="59.00">59 €</span></div></div>
          <div itemscope itemtype="https://schema.org/Product"><span itemprop="name">Tête de lit</span>
            <div itemprop="offers" itemscope itemtype="https://schema.org/Offer"><span itemprop="price" content="79.00">79 €</span></div></div>
        </section>
        <main><div itemscope itemtype="https://schema.org/Product"><h1 itemprop="name">Lit coffre 160x200 Oslo</h1>
          <div itemprop="offers" itemscope itemtype="https://schema.org/Offer"><span itemprop="price">1&nbsp;049,90 €</span>
          <meta itemprop="priceCurrency" content="EUR"><link itemprop="availability" href="https://schema.org/InStock"></div></div></main>"""),
        expect={"status": "ok", "price": 1049.9}),
    "redirige_vers_liste": dict(group="piège", html=page(ld(LISTING), "<h1>Lave-linge frontal</h1>", title="Lave-linge frontal | Enseigne"),
                                expect={"status": "not_product"}),
    "offre_reconditionnee_moins_chere": dict(group="piège", html=page(ld(product("Lave-linge LG F94N", offers=[
        {"@type": "Offer", "price": 299.0, "priceCurrency": "EUR", "availability": "https://schema.org/InStock",
         "itemCondition": "https://schema.org/RefurbishedCondition", "seller": {"@type": "Organization", "name": "Reconditionneur X"}},
        {"@type": "Offer", "price": 449.0, "priceCurrency": "EUR", "availability": "https://schema.org/InStock",
         "itemCondition": "https://schema.org/NewCondition", "seller": {"@type": "Organization", "name": "Enseigne"}}]))),
        expect={"status": "ok", "price": 449.0}),
    "devise_etrangere": dict(group="piège", html=page(ld(product("Four encastrable Neff", offers={
        "@type": "Offer", "price": 999.0, "priceCurrency": "CHF", "availability": "https://schema.org/InStock"}))),
        expect={"status": "no_price"}),
    "regle_sur_badge_pourcentage": dict(group="piège", html=page(body="<div class='fiche'><h1>Canapé Milo</h1><span class='badge'>-40 %</span>"
                                                                     "<span class='prix'>599 €</span></div>"),
                                        rules={"price": "span.badge"}, expect={"status": "no_price"}),
    "financement_et_autres_offres": dict(group="piège", html=page(ld(product("Lave-linge hublot Samsung WW90", 433.69)), """
        <div class="buybox"><div class="price"><span class="price__amount">433,69€</span></div>
        <p class="eco">dont 15,42€ d'éco-part.</p><p class="credit">108,42€/mois en 4x (Coût du financement : 11.06€)</p>
        <a class="offers">6 autres offres Dès 438,63€</a><p>Produit neuf vendu &amp; expédié par icoza</p></div>"""),
        expect={"status": "ok", "price": 433.69, "was": None}),
    "badge_incoherent": dict(group="piège", html=page(ld(product("Table à manger chêne Nordic", 500.0)),
                                                      "<div class='price'><del>1 000 €</del> <span class='now'>500 €</span> "
                                                      "<span class='flag'>-20%</span></div>"),
                             expect={"status": "ok", "price": 500.0, "was": None}),
    "page_avec_recaptcha_legitime": dict(group="piège", html=page(body="""
        <form class="newsletter"><div class="g-recaptcha" data-sitekey="x"></div><small>Protégé par reCAPTCHA</small></form>
        <div itemscope itemtype="https://schema.org/Product"><h1 itemprop="name">Armoire 3 portes Hugo</h1>
        <div itemprop="offers" itemscope itemtype="https://schema.org/Offer"><span itemprop="price" content="799.00">799 €</span>
        <meta itemprop="priceCurrency" content="EUR"></div></div>"""), expect={"status": "ok", "price": 799.0}),
    "page_introuvable_200": dict(group="piège", html=page(ld({"@context": "https://schema.org", "@type": "Organization", "name": "Enseigne"}),
                                                          "<h1>Oups ! Cette page n'existe plus</h1><p>Le produit que vous cherchez n'est plus disponible.</p>",
                                                          title="Page introuvable | Enseigne"), expect={"status": "gone"}),
    "variantes_a_partir_de": dict(group="piège", html=page(ld(product("Matelas mousse Bultex Integral 3", offers={
        "@type": "AggregateOffer", "lowPrice": "399.00", "highPrice": "699.00", "priceCurrency": "EUR", "offerCount": 4})),
        "<div class='price'><span>À partir de 399,00 €</span> <del>999,00 €</del></div>"),
        kind="from", expect={"status": "ok", "price": 399.0, "was": None}),
    # ------------------------------------------------------------------ blocages
    "datadome_403": dict(group="piège", status=403, headers={"x-datadome": "protected", "Set-Cookie": "datadome=abc; Path=/"},
                         html="<html><head><title>exemple.fr</title></head><body><script>var dd={'rt':'c','cid':'AHrlq','t':'fe',"
                              "'host':'geo.captcha-delivery.com'}</script><script src='https://ct.captcha-delivery.com/c.js'></script></body></html>",
                         vendor="datadome", expect={"status": "blocked"}),
    "cloudflare_defi": dict(group="piège", status=403, headers={"cf-mitigated": "challenge", "Server": "cloudflare"},
                            html="<!DOCTYPE html><html><head><title>Just a moment...</title></head><body><script src='/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page/v1'></script></body></html>",
                            vendor="cloudflare", expect={"status": "blocked"}),
    "datadome_interstitiel_200": dict(group="piège", status=200, headers={"x-datadome": "protected"},
                                      html="<html><body><iframe src='https://geo.captcha-delivery.com/captcha/?initialCid=x'></iframe></body></html>",
                                      vendor="datadome", expect={"status": "blocked"}),
    # ------------------------------------------------------------------ couverture
    "jsonld_barre_google": dict(group="couverture", html=page(ld(product("Matelas mousse 140x190 Bultex Integral 3", offers={
        "@type": "Offer", "price": 529.99, "priceCurrency": "EUR", "availability": "https://schema.org/InStock",
        "priceSpecification": [STRIKE(879.99)]}))), expect={"status": "ok", "price": 529.99, "was": 879.99}),
    "jsonld_mal_forme": dict(group="couverture", html=page("<script type='application/ld+json'>\n// <![CDATA[\n{\"@type\": \"Product\", "
                                                          "\"name\": \"Lave-vaisselle Beko 60 cm\", \"offers\": {\"@type\": \"Offer\", "
                                                          "\"price\": \"449.00\", \"priceCurrency\": \"EUR\",},}\n// ]]>\n</script>"),
                             expect={"status": "ok", "price": 449.0}),
    "barre_en_html_seulement": dict(group="couverture", html=page(ld(product("Matelas mousse 140x190 Bultex Integral 3", 529.99)), """
        <div class="product-price"><span class="price__old">879,99€</span> <span class="price__current">529,99€</span>
        <span class="badge">-40%</span> <span>(jusqu'au 10/02/27)</span><p class="eco">dont eco-part. de 11,00€</p></div>"""),
        expect={"status": "ok", "price": 529.99, "was": 879.99}),
    "barre_mention_reference": dict(group="couverture", html=page(ld(product("Canapé d'angle convertible Oslo", 1199.0)),
                                                                  "<div class='prix'><p class='prix-actuel'>1 199,00 €</p>"
                                                                  "<p class='mention'>Prix de référence : 1 499,00 €</p></div>"),
                                    expect={"status": "ok", "price": 1199.0, "was": 1499.0}),
    "euro_decimal_ancien_nouveau": dict(group="couverture", html=page(ld(product("Lave-linge frontal VALBERG WF 1214", "349.98")),
                                                                      "<div class='prices'><del>359€98</del> <strong class='prix'>349€<sup>98</sup></strong></div>"),
                                        expect={"status": "ok", "price": 349.98, "was": 359.98}),
    "etat_next_data": dict(group="couverture", html=page(
        "<script id='__NEXT_DATA__' type='application/json'>" + json.dumps({"props": {"pageProps": {
            "breadcrumbs": [{"name": "Canapés", "price": None}],
            "recommendations": [{"name": "Pouf Oslo", "price": {"current": 89.0}}],
            "product": {"name": "Canapé d'angle convertible Oslo", "ean": "3663000000001",
                        "price": {"current": 899.0, "old": 1299.0, "currency": "EUR"}, "stock": {"available": True}}}}}) + "</script>",
        "<h1>Canapé d'angle convertible Oslo</h1>"), expect={"status": "ok", "price": 899.0, "was": 1299.0}),
    "rupture_jsonld": dict(group="couverture", html=page(ld(product("Hotte décorative Électrolux 90 cm", offers={
        "@type": "Offer", "price": "349.00", "priceCurrency": "EUR", "availability": "https://schema.org/OutOfStock"}))),
        expect={"status": "ok", "price": 349.0, "availability": "out_of_stock"}),
    # ------------------------------------------------------------------ donnée nouvelle
    "fin_de_promotion": dict(group="donnée", html=page(ld(product("Matelas mousse 140x190 Bultex Integral 3", offers={
        "@type": "Offer", "price": 529.99, "priceCurrency": "EUR", "priceValidUntil": "2027-02-10",
        "availability": "https://schema.org/InStock", "priceSpecification": [STRIKE(879.99)]}))),
        expect={"status": "ok", "price": 529.99, "was": 879.99, "valid_until": "2027-02-10"}),
    "plus_bas_30_jours": dict(group="donnée", html=page(ld(product("Four encastrable Bosch Série 6", 499.0)),
                                                        "<div class='price'><s>649,00 €</s> <b>499,00 €</b></div><p class='legal'>"
                                                        "Prix le plus bas pratiqué au cours des 30 derniers jours : 589,00 €</p>"),
                              expect={"status": "ok", "price": 499.0, "was": 649.0, "lowest_30d": 589.0}),
}

# Jeu « écrit après réglage » : variantes de balisage jamais vues pendant la mise au point (mesure de généralisation).
HELDOUT = {
    "prix_public_conseille": dict(group="couverture", html=page(ld(product("Lave-linge Miele WCA 030", 649.99)),
        "<p class='prix'><span class='prix-promo'>649,99 €</span> <span class='prix-public'>Prix public conseillé 799,99 €</span></p>"),
        expect={"status": "ok", "price": 649.99, "was": 799.99}),
    "barre_par_style": dict(group="couverture", html=page(ld(product("Canapé 3 places velours Ines", 999.0)),
        "<div class='bloc-prix'><span style='text-decoration: line-through'>1 299 €</span> <span class='final'>999 €</span></div>"),
        expect={"status": "ok", "price": 999.0, "was": 1299.0}),
    "prix_eclates_entier_decimales": dict(group="couverture", html=page(ld(product("Réfrigérateur américain LG GSXV90", 999.99)),
        "<div class='price-box'><del><span class='int'>1 199</span><span class='dec'>,99 €</span></del> "
        "<span class='int'>999</span><span class='dec'>,99 €</span></div>"),
        expect={"status": "ok", "price": 999.99, "was": 1199.99}),
    "financement_et_barre": dict(group="piège", html=page(ld(product("Four Bosch HBA534", 899.0)),
        "<div class='prices'><del>1 099 €</del> <b>899 €</b> <span>ou 4x 224,75 €</span></div>"),
        expect={"status": "ok", "price": 899.0, "was": 1099.0}),
    "listprice_jsonld_sans_devise": dict(group="couverture", html=page(ld(product("Plaque induction Sauter", offers={
        "@type": "Offer", "price": 399, "priceSpecification": {"@type": "UnitPriceSpecification", "price": 499,
                                                              "priceType": "https://schema.org/ListPrice"}}))),
        expect={"status": "ok", "price": 399.0, "was": 499.0}),
    "microdonnees_et_ancien_prix_html": dict(group="couverture", html=page(body="""
        <div itemscope itemtype="https://schema.org/Product"><h1 itemprop="name">Lit coffre 140x190 Nils</h1>
        <div class="price-area" itemprop="offers" itemscope itemtype="https://schema.org/Offer"><meta itemprop="price" content="459">
        <meta itemprop="priceCurrency" content="EUR"><span class="old-price">599 €</span> <span class="current">459 €</span></div></div>"""),
        expect={"status": "ok", "price": 459.0, "was": 599.0}),
    "prix_absent_du_html_carrousel_barre": dict(group="piège", html=page(ld(product("Armoire 2 portes Lina", 349.0)),
        "<div id='app'></div><div class='reco'><div class='card'><del>99 €</del> <span>79 €</span></div></div>"),
        expect={"status": "ok", "price": 349.0, "was": None}),
    "barre_d_un_autre_produit_voisin": dict(group="piège", html=page(ld(product("Buffet chêne Oslo", 499.0)),
        "<div class='buy'><span class='p'>499 €</span></div><div class='reco'><div class='card'><del>899 €</del> <span>699 €</span></div></div>"),
        expect={"status": "ok", "price": 499.0, "was": None}),
}
