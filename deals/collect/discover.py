"""Découverte des fiches produit par les plans de site : robots.txt (lignes « Sitemap: ») → index → fichiers.

Les fichiers « produits » sont lus d'abord ; chaque adresse qui ressemble à une fiche (product_url de l'enseigne) est
rangée dans une catégorie d'après les mots de son adresse (le titre de la fiche confirmera à la première lecture).
"""
import re
from collections import defaultdict
from xml.etree import ElementTree as ET

from .retailers import CATEGORY_URL_HINTS, FAMILIES

PRODUCT_SITEMAP_HINT = re.compile(r"product|produit|pdp|article|fiche|item|offer", re.I)


def parse_sitemap(raw):
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None, []
    locs = [e.text.strip() for e in root.iter() if e.tag.split("}")[-1] == "loc" and e.text]
    return ("index" if root.tag.split("}")[-1] == "sitemapindex" else "urlset"), locs


def robots_sitemaps(fetcher, home):
    raw = fetcher.get_bytes(home.rstrip("/") + "/robots.txt")
    if not raw:
        return []
    return [line.split(":", 1)[1].strip() for line in raw.decode("utf-8", "replace").splitlines() if line.lower().startswith("sitemap:")]


def categories_of(cfg):
    fams = cfg.get("families")
    return [c for f in fams for c in FAMILIES.get(f, []) if c in CATEGORY_URL_HINTS] if fams else list(CATEGORY_URL_HINTS)


def discover(fetcher, cfg, per_category=40, max_files=60):
    """→ {"by_category": {catégorie: [adresses]}, "files_read": n, "total": n}"""
    cats, pat = categories_of(cfg), re.compile(cfg["product_url"])
    queue = list(dict.fromkeys(robots_sitemaps(fetcher, cfg["home"]) + cfg.get("sitemaps", [])))
    found, seen, read = defaultdict(list), set(), 0
    while queue and read < max_files and any(len(found[c]) < per_category for c in cats):
        queue.sort(key=lambda u: 0 if PRODUCT_SITEMAP_HINT.search(u) else 1)
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        raw = fetcher.get_bytes(sm)
        read += 1
        if not raw:
            continue
        kind, locs = parse_sitemap(raw)
        if kind == "index":
            queue.extend(u for u in locs if u not in seen)
            continue
        for u in locs:
            if not pat.search(u):
                continue
            low = u.lower()
            for c in cats:
                if len(found[c]) < per_category and any(h in low for h in CATEGORY_URL_HINTS[c]):
                    found[c].append(u)
                    break
    found = {c: v for c, v in found.items() if v}
    return {"by_category": found, "files_read": read, "total": sum(len(v) for v in found.values())}
