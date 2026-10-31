"""Démo : la vraie nuit (night.py : ingestion → agent → publication → contrôles) sur le marché simulé, nuit après nuit.

127 produits des quatre familles (dont 33 aspirateurs de tous types, fiches plus ou moins complètes : v57 ; et 43
produits d'électronique : v59), quatre enseignes fictives (une source chacune, toutes partenaires : RULES), trois
enseignes par produit, une nuit par jour du 1er octobre au 14 décembre 2025 (Black Friday compris) ; la dernière nuit est
un jour ordinaire de décembre : des remises qui commencent, d'autres qui finissent, des fausses promos écartées.
L'aspirateur balai haut de gamme (Zephyr V15) n'y est pas en remise, mais trois modèles comparables coûtent bien moins
cher, dont un en remise.

Depuis la v63, chaque enseigne simulée donne son FLUX produits, comme une enseigne partenaire : deux au format Google
Shopping (XML), deux en CSV à la française (FEEDS) ; la démo passe par le connecteur de flux (ingest/), lots et fichiers
bruts compris. mode="site" lit leurs fiches à la place, comme avant : le catalogue publié est le même (tests/test_demo.py).
"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from . import config, night, sim
from .accounts import Outbox
from .ingest.collector import Collector
from .ingest.feeds import Mapping
from .ingest.pages.crawl import Crawler
from .market import Market

FIRST_NIGHT, LAST_NIGHT = date(2025, 10, 1), date(2025, 12, 14)
HORIZON = 200                     # jours simulés : fixe, pour que le même départ donne toujours le même marché
CSV = {"format": "csv", "encoding": "cp1252",
       "fields": {"external_id": "id", "title": "nom", "brand": "marque", "gtin": "ean", "category": "categorie", "url": "lien",
                  "price": "prix", "list_price": "prix_barre", "availability": "disponibilite", "valid_until": "fin_promo",
                  "properties": "caracteristiques"}}


def retailers(merchants=sim.SHOWCASE_MERCHANTS):
    """Une source par enseigne simulée ; sa clé est le nom de l'hôte de ses fiches (« Maison & Co » → maisonco.sim)."""
    return {sim.slug(m): {"name": m, "home": f"https://{sim.slug(m)}.sim", "enabled": True,
                          "families": ["electromenager", "electronique", "ameublement", "literie"], "product_url": ".", "sitemaps": []}
            for m in merchants}


def feeds(merchants=sim.SHOWCASE_MERCHANTS):
    """Les mêmes enseignes, lues par leur flux : une sur deux en XML Google Shopping, l'autre en CSV."""
    out = {}
    for n, m in enumerate(merchants):
        fmt = "xml" if n % 2 == 0 else "csv"
        out[sim.slug(m)] = {"key": sim.slug(m), "name": m, "kind": "feed", "enabled": True, "network": "simulé",
                            "families": ["electromenager", "electronique", "ameublement", "literie"],
                            "url": f"sim://{sim.slug(m)}.{fmt}", "url_template": f"sim://{sim.slug(m)}.{fmt}", "format": fmt,
                            "mapping": Mapping.load({"preset": "google_shopping"} if fmt == "xml" else CSV, m)}
    return out


RETAILERS = retailers()
FEEDS = feeds()
RULES = {k: "partenaire=deals&clic={subid}" for k in RETAILERS}     # liens affiliés simulés (affiliate.py)


def world(store, start, seed=4, catalog=sim.SHOWCASE, mode="feed", raw_dir=None):
    """Le marché simulé branché sur `store` depuis le jour `start` (même départ, même marché) : sim (le marché simulé),
    market, clock, crawler (les fiches), collector (toutes les sources de `mode` : « feed », leurs flux ; « site », leurs
    fiches), retailers (les sources). Pour la démo, les bancs et les tests."""
    merchants = sim.SHOWCASE_MERCHANTS if catalog is sim.SHOWCASE else sim.MERCHANTS
    m = sim.Market(start=start, days=HORIZON, seed=seed, catalog=catalog, merchants=merchants,
                   extra=(sim.SHOWCASE_MORE, sim.SHOWCASE_TECH) if catalog is sim.SHOWCASE else ())
    clock = sim.SimClock(start)
    market = Market(store, clock)
    known = retailers(merchants)
    for o in m.offers:
        market.track(o["url"], sim.slug(o["merchant"]), o["merchant"])
    crawler = Crawler(market, sim.SimFetcher(m, clock), known, budget_s=10 ** 9, clock=clock)
    specs = feeds(merchants) if mode == "feed" else {k: {**v, "key": k, "kind": "site"} for k, v in known.items()}

    def transport(spec):
        k = (datetime.fromtimestamp(clock(), timezone.utc).date() - m.start).days
        return m.feed(spec["name"], k, spec["format"])
    raw = raw_dir or str(Path(store.path).parent / "raw")
    collector = Collector(store, market, crawler, specs, raw_dir=raw, transport=transport, clock=clock)
    return SimpleNamespace(sim=m, market=market, clock=clock, retailers=specs, crawler=crawler, collector=collector)


def build(store, end=LAST_NIGHT, nights=None, seed=4, catalog=sim.SHOWCASE, partners=None, settings=None, mode="feed"):
    """Remplit `store` de nuits de marché simulé jusqu'au jour `end` (depuis FIRST_NIGHT, ou `nights` nuits avant `end`) ;
    chaque nuit est une vraie nuit (night.run), sans rapport ni e-mail au responsable ; partners : les enseignes
    partenaires, seules lues et publiées (None : toutes) ; mode : « feed » (leurs flux) ou « site » (leurs fiches).
    → (Market, horloge simulée)."""
    start = end - timedelta(days=nights) if nights else FIRST_NIGHT
    w = world(store, start, seed, catalog, mode)
    settings, box = settings or config.Settings(), Outbox()
    for k in range((end - start).days + 1):
        w.clock.set(start + timedelta(days=k))
        night.run(store, settings, w.collector, box, w.retailers, partners, clock=w.clock)
    return w.market, w.clock
