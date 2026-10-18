"""Démo : la vraie chaîne (collecte → marché → publication) sur le marché simulé, nuit après nuit.

48 produits des trois familles, trois enseignes fictives par produit, une nuit de collecte par jour du 1er octobre au
23 décembre 2025 (Black Friday compris) ; la dernière nuit est un jour ordinaire d'avant Noël : des remises qui
commencent, d'autres qui finissent, des fausses promos écartées.
"""
from datetime import date, timedelta

from . import sim
from .collect.crawl import Crawler
from .market import Market
from .publish import publish

SIM_RETAILER = {"sim": {"name": "Simulé", "home": "https://sim", "enabled": True, "families": ["electromenager", "ameublement", "literie"],
                        "product_url": ".", "sitemaps": []}}
FIRST_NIGHT, LAST_NIGHT = date(2025, 10, 1), date(2025, 12, 23)
HORIZON = 200                     # jours simulés : fixe, pour que le même départ donne toujours le même marché


def build(store, end=LAST_NIGHT, nights=None, seed=4, catalog=sim.SHOWCASE):
    """Remplit `store` de nuits de marché simulé jusqu'au jour `end` (depuis FIRST_NIGHT, ou `nights` nuits avant `end`) ;
    le catalogue est publié chaque nuit, comme en production. → (Market, horloge simulée)."""
    start = end - timedelta(days=nights) if nights else FIRST_NIGHT
    days = (end - start).days
    m = sim.Market(start=start, days=HORIZON, seed=seed, catalog=catalog,
                   merchants=sim.SHOWCASE_MERCHANTS if catalog is sim.SHOWCASE else sim.MERCHANTS)
    clock = sim.SimClock(start)
    market = Market(store, clock)
    crawler = Crawler(market, sim.SimFetcher(m, clock), SIM_RETAILER, budget_s=10 ** 9, clock=clock)
    for o in m.offers:
        market.track(o["url"], "sim", o["merchant"])
    for k in range(days + 1):
        clock.set(start + timedelta(days=k))
        crawler.nightly()
        publish(store, market.today(), clock())
    return market, clock
