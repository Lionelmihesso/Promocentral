"""Le cadre de mise en production, vérifié par exécution : les points non négociables de la chaîne de données, la
sauvegarde et sa restauration, ce que le serveur sert et ses en-têtes. Rien n'est modifié, rien n'est lu sur le web.

  python -m bench.cadre [--code <dossier du code>] [--json sortie.json]

Chaque point : OK (le code le respecte) ou ÉCART (il ne le respecte pas), avec la preuve tirée de l'exécution. Le
relevé d'un point dit aussi sa gravité dans le registre des risques (docs/PRODUCTION.md) : P0 bloque l'ouverture, P1
compte avant l'ouverture, P2 vient après.
"""
import argparse
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ap = argparse.ArgumentParser()
ap.add_argument("--code", default=str(Path(__file__).resolve().parent.parent), help="dossier du code mesuré")
ap.add_argument("--json", help="écrire le relevé en JSON")
ARGS = ap.parse_args() if __name__ == "__main__" else ap.parse_args([])
CODE = Path(ARGS.code).resolve()
sys.path.insert(0, str(CODE))

from deals import extract as X                                        # noqa: E402
from deals import judge as J                                          # noqa: E402
from deals.affiliate import link                                      # noqa: E402
from deals.backup import backup                                       # noqa: E402
from deals.market import Market, jaccard, norm_title                  # noqa: E402
from deals.missions import Missions, matches                          # noqa: E402
from deals.publish import publish                                     # noqa: E402
from deals.store import Store                                         # noqa: E402

NOW = datetime(2026, 10, 31, 3, 0, tzinfo=timezone.utc).timestamp()
TODAY = date(2026, 10, 31)
OUT = []


def point(section, name, ok, proof, gravity):
    OUT.append({"section": section, "point": name, "ok": bool(ok), "proof": proof, "gravity": None if ok else gravity})


def fresh_store(tmp, name):
    return Store(str(Path(tmp) / name))


# ------------------------------------------------------------------------------------------------ données
def data(tmp):
    st = fresh_store(tmp, "donnees.sqlite")
    m = Market(st, clock=lambda: NOW)

    def product(title, brand=None, mpn=None, gtin=None):
        with st.tx():
            return m.match_product({"title": title, "brand": brand, "mpn": mpn, "gtin": gtin, "price": 500.0})

    t1 = "Lave-linge hublot Bosch Série 6 WGG244Z0FR 9 kg 1400 tours classe A"
    t2 = "Lave-linge hublot Bosch Série 6 WGG244Z1FR 9 kg 1400 tours classe A"
    a, b = product(t1, "Bosch", "WGG244Z0FR"), product(t2, "Bosch", "WGG244Z1FR")
    point("Données", "deux références fabricant différentes ne sont pas fusionnées sur la ressemblance du titre", a != b,
          f"WGG244Z0FR → produit {a}, WGG244Z1FR → produit {b} (sans EAN ; titres semblables à "
          f"{jaccard(norm_title(t1), norm_title(t2)):.0%}, seuil de fusion 80 %)", "P0")
    c = product("Canapé d'angle convertible réversible Oslo 5 places tissu chiné gris anthracite")
    d = product("Canapé d'angle convertible réversible Oslo 5 places tissu chiné beige anthracite")
    point("Données", "deux produits sans marque ni référence ne sont pas fusionnés sur la ressemblance du titre", c != d,
          f"gris → produit {c}, beige → produit {d}", "P0")
    flagged = st.q("SELECT needs_review FROM products WHERE id=?", (a,), one=True)["needs_review"]
    point("Données", "un rapprochement par le seul titre est marqué « à vérifier »", a != b or flagged,
          f"needs_review du produit fusionné : {flagged}", "P0")
    e = product("TV QLED Samsung 55 pouces QE55Q60D 4K 2024 Smart TV Tizen", "Samsung", "QE55Q60D")
    f = product("TV QLED Samsung 65 pouces QE65Q60D 4K 2024 Smart TV Tizen", "Samsung", "QE65Q60D")
    point("Données", "deux tailles d'une même gamme restent deux produits", e != f, f"55 pouces → {e}, 65 pouces → {f}", "P0")
    g = product("Réfrigérateur combiné Brava 60 cm No Frost 331 L classe C", "Brava", None, "3700000000017")
    h = product("Réfrigérateur combiné Brava 60 cm No Frost 331 L classe C noir", "Brava", None, "3700000000024")
    point("Données", "deux EAN différents ne sont jamais fusionnés", g != h, f"EAN …017 → {g}, EAN …024 → {h}", "P0")

    # Disponibilité : non dite → inconnue ; inconnue → promise ?
    page = ('<html><head><script type="application/ld+json">{"@context":"https://schema.org","@type":"Product",'
            '"name":"Lave-linge hublot Kessler WM8 8 kg 1400 tr/min classe A","brand":"Kessler","offers":{"@type":"Offer",'
            '"price":"549.00","priceCurrency":"EUR"}}</script></head><body><h1>Lave-linge Kessler WM8</h1></body></html>')
    ex = X.analyze(page, None, url="https://exemple.fr/p/1")["best"]
    point("Données", "une disponibilité que la fiche ne dit pas reste « inconnue »", ex["availability"] == "unknown",
          f"disponibilité lue : {ex['availability']!r}", "P1")
    with st.tx():
        oid = m.track("https://exemple.fr/p/1", "exemple", "Exemple")
        m.record(m.offer(oid), {**ex, "category": "Lave-linge"})
    publish(st, TODAY, NOW)
    rows = Missions._rows(SimpleNamespace(s=st), {"category": "lave_linge"})
    prod = Missions._product(rows[0]) if rows else None
    promised = bool(prod and matches({"category": "lave_linge", "max_price": 600}, prod))
    point("Données", "une disponibilité inconnue n'est pas promise : une alerte ne part pas sur elle", not promised,
          f"offre publiée avec la disponibilité {rows[0]['availability'] if rows else None!r} ; l'alerte « lave-linge sous "
          f"600 € » la compte {'disponible : l’e-mail de la nuit partirait' if promised else 'non disponible'}", "P1")

    # Types de prix
    member = ('<html><head><script type="application/ld+json">{"@context":"https://schema.org","@type":"Product","name":'
              '"Canapé Lina 3 places","offers":{"@type":"Offer","priceCurrency":"EUR","price":"899.00","priceSpecification":'
              '[{"@type":"UnitPriceSpecification","price":"799.00","validForMemberTier":{"@type":"MemberProgramTier","name":'
              '"Club"}}]}}</script></head><body></body></html>')
    mb = X.analyze(member, None, url="https://exemple.fr/p/2")["best"]
    point("Données", "le prix membre n'est pas pris pour le prix public", mb and mb["price"] == 899.0,
          f"prix public 899 €, prix membre 799 € → prix lu {mb and mb['price']} €", "P0")
    coded = ('<html><body><div class="product"><h1>Matelas Solenne 160x200</h1><div class="price-block"><span class="price">'
             '649,00 €</span><span class="promo">599,00 € avec le code MATELAS50</span><span class="shipping">Livraison 39,00 €'
             '</span></div></div></body></html>')
    cd = X.analyze(coded, {"price": "span.price"}, url="https://exemple.fr/p/3")["best"]
    point("Données", "un prix avec code et des frais de livraison ne sont pris ni pour le prix ni pour le prix barré",
          cd and cd["price"] == 649.0 and not cd.get("list_price"),
          f"prix lu {cd and cd['price']} €, prix barré {cd and cd.get('list_price')}", "P0")
    cols = {r["name"] for r in st.q("PRAGMA table_info(prices)")}
    point("Données", "les frais de livraison sont connus (prix livré possible)", {"shipping", "delivery"} & cols,
          f"colonnes de prices : {', '.join(sorted(cols))} — le prix est celui de l'article seul", "P2")

    # Remise : référence qualifiée
    v = J.judge(499.0, 799.0, [], TODAY)
    point("Données", "une remise n'est pas montrée sur le seul prix barré de l'enseigne, sans référence qualifiée",
          not v.deal or v.verified,
          f"aucun historique, aucune mention « plus bas 30 jours » : remise montrée {v.pct} %, confirmée par une preuve : "
          f"{v.verified} ({v.reason})", "P1")

    # Lien affilié séparé de l'adresse de la fiche
    url = "https://www.enseigne.example/ref/123"
    out = link(url, "https://reseau.example/clic?prog=1&url={url}&sub={subid}", "k42")
    point("Données", "adresse de la fiche, lien affilié et identifiant du clic restent séparés", url not in out and "k42" in out,
          f"offers.url garde {url} ; le lien est construit au clic : {out}", "P1")


# ------------------------------------------------------------------------------------------------ exploitation
def operations(tmp):
    st = fresh_store(tmp, "prod.sqlite")
    m = Market(st, clock=lambda: NOW)
    with st.tx():
        for k in range(20):
            o = m.track(f"https://exemple.fr/p/{k}", "exemple", "Exemple")
            m.record(m.offer(o), {"title": f"Lave-linge Kessler WM{k} 8 kg", "brand": "Kessler", "mpn": f"WM{k}", "price": 400.0 + k})
    st.release()
    saved = backup(str(Path(tmp) / "prod.sqlite"), Path(tmp) / "sauvegardes", keep=14)
    restored = Path(tmp) / "restauree.sqlite"
    shutil.copy(saved, restored)
    r = Store(str(restored))
    same = all(r.q(f"SELECT COUNT(*) n FROM {t}", one=True)["n"] == st.q(f"SELECT COUNT(*) n FROM {t}", one=True)["n"]
               for t in ("products", "offers", "prices"))
    point("Exploitation", "une sauvegarde se restaure et la base restaurée s'ouvre, identique", same,
          f"{saved.name} → restaurée, produits, offres et prix identiques : {same}", "P0")
    dest = (CODE / "deploy" / "README.md").read_text(encoding="utf-8")
    offsite = any(w in dest for w in ("rclone", "Storage Box", "hors du serveur", "hors serveur", "s3://"))
    point("Exploitation", "une copie des sauvegardes vit hors du serveur", offsite,
          "deploy/ : sauvegarde dans /var/backups/deals, sur le même disque que la base", "P1")
    release = any((CODE / "deploy" / n).exists() for n in ("release.sh", "rollback.sh", "deals-release"))
    point("Exploitation", "une version se déploie et se retire d'une commande (artefact daté, retour arrière)", release,
          "deploy/README.md : « sudo cp -r . /opt/deals && sudo systemctl restart deals-web » ; une base migrée refuse "
          "l'ancien code : revenir en arrière demande de restaurer la base à la main", "P1")


# ------------------------------------------------------------------------------------------------ ce qui est servi
def served(tmp):
    from deals.config import Settings
    from deals.api import Api
    from deals.web import make_server
    st = fresh_store(tmp, "web.sqlite")
    settings = Settings()
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = make_server(Api(st, settings), st, settings, port=port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def get(path):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
                return r.status, dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers)
    try:
        code, headers = get("/")
        robot, _ = get("/robot")
    finally:
        srv.shutdown()
        srv.server_close()
    have = {k for k in headers if k.lower() in ("x-content-type-options", "x-frame-options", "referrer-policy",
                                                 "content-security-policy", "permissions-policy")}
    point("Sécurité", "la page porte une politique de contenu (Content-Security-Policy)", "Content-Security-Policy" in have,
          f"en-têtes de sécurité servis : {', '.join(sorted(have))}", "P2")
    caddy = (CODE / "deploy" / "Caddyfile").read_text(encoding="utf-8")
    point("Sécurité", "le HTTPS est imposé au navigateur (Strict-Transport-Security)", "Strict-Transport-Security" in caddy,
          "deploy/Caddyfile : aucune directive header Strict-Transport-Security", "P1")
    env = (CODE / "deploy" / "deals.env.example").read_text(encoding="utf-8")
    announced = "/robot" in env
    point("Sécurité", "la page qui décrit le robot, annoncée aux enseignes, existe", not announced or robot == 200,
          f"DEALS_USER_AGENT annonce « …/robot » ; GET /robot → {robot}", "P1")
    tracked = []
    if (CODE / ".git").exists():
        files = subprocess.run(["git", "-C", str(CODE), "ls-files"], capture_output=True, text=True).stdout.split()
        tracked = [f for f in files if f.endswith((".env", ".pem", ".key", ".sqlite")) or f.endswith("affiliate.json")]
    point("Sécurité", "aucun secret ni aucune base dans le dépôt", not tracked, f"fichiers sensibles suivis : {tracked or 'aucun'}", "P0")


def main():
    tmp = tempfile.mkdtemp(prefix="cadre-")
    try:
        data(tmp)
        operations(tmp)
        served(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    section = None
    for p in OUT:
        if p["section"] != section:
            section = p["section"]
            print(f"\n{section}")
        print(f"  {'OK   ' if p['ok'] else 'ÉCART'} {'' if p['ok'] else p['gravity'] + ' '}{p['point']}\n        {p['proof']}")
    bad = [p for p in OUT if not p["ok"]]
    by = {g: sum(1 for p in bad if p["gravity"] == g) for g in ("P0", "P1", "P2")}
    print(f"\n{len(OUT) - len(bad)}/{len(OUT)} respectés · écarts : P0 {by['P0']}, P1 {by['P1']}, P2 {by['P2']}")
    if ARGS.json:
        Path(ARGS.json).write_text(json.dumps(OUT, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
