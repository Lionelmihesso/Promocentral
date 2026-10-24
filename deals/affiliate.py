"""Affiliation : DEALS ne montre que les offres d'enseignes partenaires, et chaque clic part avec son identifiant.

Règles (réglage DEALS_AFFILIATE : un fichier JSON, clé d'enseigne → règle) ; deux formes :
- le gabarit de lien du réseau, avec {url} (l'adresse de la fiche, encodée) et {subid} (l'identifiant du clic) :
  "https://www.awin1.com/cread.php?awinmid=1234&awinaffid=5678&clickref={subid}&ued={url}" ;
- ou des paramètres ajoutés à l'adresse de la fiche : "tag=deals-21&ascsubtag={subid}".
L'identifiant du clic revient dans les rapports du réseau : chaque vente se rattache au clic, donc à l'écran, à la
mission et à la personne d'où il est parti (activity.py). Sans fichier (développement), rien n'est filtré et les liens
partent tels quels ; la démo utilise DEMO.
"""
import json
from pathlib import Path
from urllib.parse import quote

DEMO = {"sim": "partenaire=deals&clic={subid}"}     # les enseignes simulées de la démo, toutes partenaires


def load(path):
    """Règles du fichier JSON → {enseigne: règle} ; None sans fichier. ValueError si le fichier est illisible ou mal formé."""
    if not path:
        return None
    try:
        rules = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"DEALS_AFFILIATE : fichier illisible ({e})") from None
    if not isinstance(rules, dict) or not rules or not all(isinstance(k, str) and isinstance(v, str) and v.strip()
                                                           for k, v in rules.items()):
        raise ValueError("DEALS_AFFILIATE : un objet JSON non vide {enseigne: règle} est attendu")
    return rules


def link(url, rule, subid):
    """L'adresse envoyée à l'enseigne : le gabarit du réseau rempli, ou la fiche suivie des paramètres de la règle ;
    None sans règle (enseigne non partenaire)."""
    if not rule:
        return None
    sub = quote(str(subid), safe="")
    if "{url}" in rule:
        return rule.replace("{url}", quote(url, safe="")).replace("{subid}", sub)
    page, _, anchor = url.partition("#")
    params = rule.replace("{subid}", sub).lstrip("?&")
    return f"{page}{'&' if '?' in page else '?'}{params}" + (f"#{anchor}" if anchor else "")
