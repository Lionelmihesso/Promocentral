"""Démo : la vraie chaîne (collecte → marché → publication) sur le marché simulé, jour après jour."""
from datetime import date, timedelta

from . import sim
from .collect.crawl import Crawler
from .market import Market
from .publish import publish

SIM_RETAILER = {"sim": {"name": "Simulé", "home": "https://sim", "enabled": True, "families": ["electromenager", "ameublement", "literie"],
                        "product_url": ".", "sitemaps": []}}


def build(store, days=90, start=date(2026, 1, 5), seed=4):
    """Remplit `store` avec `days` nuits de marché simulé puis publie le catalogue. → (Market, horloge simulée)."""
    m = sim.Market(start=start, days=days + 30, seed=seed)
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
