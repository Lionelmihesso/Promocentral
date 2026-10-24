"""Démo : la vraie nuit (night.py : collecte → agent → publication → contrôles) sur le marché simulé, nuit après nuit.

59 produits des trois familles, quatre enseignes fictives (une source chacune, toutes partenaires : RULES), trois
enseignes par produit, une nuit par jour du 1er octobre au 14 décembre 2025 (Black Friday compris) ; la dernière nuit est
un jour ordinaire de décembre : des remises qui commencent, d'autres qui finissent, des fausses promos écartées.
L'aspirateur balai haut de gamme (Zephyr V15) n'y est pas en remise, mais trois modèles comparables coûtent bien moins
cher, dont un en remise.
"""
from datetime import date, timedelta
from types import SimpleNamespace

from . import config, night, sim
from .accounts import Outbox
from .collect.crawl import Crawler
from .market import Market

FIRST_NIGHT, LAST_NIGHT = date(2025, 10, 1), date(2025, 12, 14)
HORIZON = 200                     # jours simulés : fixe, pour que le même départ donne toujours le même marché


def retailers(merchants=sim.SHOWCASE_MERCHANTS):
    """Une source par enseigne simulée ; sa clé est le nom de l'hôte de ses fiches (« Maison & Co » → maisonco.sim)."""
    return {sim.slug(m): {"name": m, "home": f"https://{sim.slug(m)}.sim", "enabled": True,
                          "families": ["electromenager", "ameublement", "literie"], "product_url": ".", "sitemaps": []}
            for m in merchants}


RETAILERS = retailers()
RULES = {k: "partenaire=deals&clic={subid}" for k in RETAILERS}     # liens affiliés simulés (affiliate.py)


def world(store, start, seed=4, catalog=sim.SHOWCASE):
    """Le marché simulé branché sur `store` depuis le jour `start` (même départ, même marché) : sim (le marché simulé),
    market, clock, crawler, retailers (une source par enseigne simulée). Pour la démo, le banc et les tests."""
    merchants = sim.SHOWCASE_MERCHANTS if catalog is sim.SHOWCASE else sim.MERCHANTS
    m = sim.Market(start=start, days=HORIZON, seed=seed, catalog=catalog, merchants=merchants)
    clock = sim.SimClock(start)
    market = Market(store, clock)
    known = retailers(merchants)
    for o in m.offers:
        market.track(o["url"], sim.slug(o["merchant"]), o["merchant"])
    return SimpleNamespace(sim=m, market=market, clock=clock, retailers=known,
                           crawler=Crawler(market, sim.SimFetcher(m, clock), known, budget_s=10 ** 9, clock=clock))


def build(store, end=LAST_NIGHT, nights=None, seed=4, catalog=sim.SHOWCASE, partners=None, settings=None):
    """Remplit `store` de nuits de marché simulé jusqu'au jour `end` (depuis FIRST_NIGHT, ou `nights` nuits avant `end`) ;
    chaque nuit est une vraie nuit (night.run), sans rapport ni e-mail au responsable ; partners : les enseignes
    partenaires, seules lues et publiées (None : toutes). → (Market, horloge simulée)."""
    start = end - timedelta(days=nights) if nights else FIRST_NIGHT
    w = world(store, start, seed, catalog)
    settings, box = settings or config.Settings(), Outbox()
    for k in range((end - start).days + 1):
        w.clock.set(start + timedelta(days=k))
        night.run(store, settings, w.crawler, box, w.retailers, partners, clock=w.clock)
    return w.market, w.clock
