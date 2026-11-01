"""Le registre des sources : quelles enseignes on lit, et comment. Une source par enseigne, sous sa clé.

Deux origines, fusionnées par clé :
  - les enseignes connues du code (retailers.py) : leurs fiches, lues par pages/ (kind « site ») ;
  - le fichier DEALS_SOURCES (JSON) : une entrée par enseigne, qui remplace ou complète celle du code — le plus souvent
    son flux (kind « feed »), ou le réglage de ses fiches (enabled…).

Une source « feed » dit :
  url       où lire le flux : https://…, http://… ou un chemin de fichier ; ${NOM} y est remplacé par la variable
            d'environnement NOM (les identifiants des réseaux vivent dans /etc/deals/deals.env, jamais dans ce fichier)
  mapping   la correspondance de ses colonnes : un objet, ou le chemin d'un fichier JSON (relatif au fichier des sources)
            — voir feeds.Mapping ; {"preset": "google_shopping"} pour un flux au format standard
  headers   des en-têtes HTTP (${NOM} remplacé), facultatif
  network   le réseau d'affiliation (information), name, families (familles attendues), enabled
Un réglage invalide arrête le démarrage en nommant la source et le champ, plutôt qu'une nuit qui tourne mal.
"""
import json
import os
import re
from pathlib import Path

from .feeds import FeedError, Mapping
from .retailers import FAMILIES, RETAILERS

KINDS = ("site", "feed")
KEYS = {"kind", "name", "enabled", "families", "network", "url", "mapping", "headers", "home", "product_url", "sitemaps",
        "disabled_reason", "_note"}
VAR = re.compile(r"\$\{([A-Z0-9_]+)\}")


def resolve(value, env, where):
    def one(m):
        if m.group(1) not in env or not env[m.group(1)]:
            raise ValueError(f"{where} : variable d'environnement {m.group(1)} absente")
        return env[m.group(1)]
    return VAR.sub(one, value)


def load(path=None, env=None, base=None):
    """→ {clé: source} : les enseignes du code (fiches), puis celles du fichier `path` qui les remplacent ou s'ajoutent."""
    env = os.environ if env is None else env
    specs = {k: {**v, "key": k, "kind": "site"} for k, v in (base if base is not None else RETAILERS).items()}
    if not path:
        return specs
    where = f"DEALS_SOURCES ({path})"
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"{where} : fichier illisible ({e})") from None
    if not isinstance(data, dict):
        raise ValueError(f"{where} : un objet JSON {{clé: source}} est attendu")
    for key, src in data.items():
        w = f"{where} : {key}"
        if not isinstance(src, dict):
            raise ValueError(f"{w} : un objet est attendu")
        unknown = set(src) - KEYS
        if unknown:
            raise ValueError(f"{w} : champ inconnu {', '.join(sorted(unknown))}")
        kind = src.get("kind", "site")
        if kind not in KINDS:
            raise ValueError(f"{w} : kind {kind!r} au lieu de {' | '.join(KINDS)}")
        known = RETAILERS.get(key, {})
        spec = {**(known if kind == "site" else {"name": known.get("name"), "families": known.get("families")}),
                **{k: v for k, v in src.items() if k != "_note"}, "key": key, "kind": kind}
        spec["enabled"] = bool(spec.get("enabled", True))
        spec["families"] = list(spec.get("families") or FAMILIES)
        if not spec.get("name"):
            raise ValueError(f"{w} : name manquant (enseigne inconnue du code)")
        if set(spec["families"]) - set(FAMILIES):
            raise ValueError(f"{w} : famille inconnue {', '.join(sorted(set(spec['families']) - set(FAMILIES)))}")
        if kind == "site" and spec["enabled"] and not (spec.get("home") and spec.get("product_url")):
            raise ValueError(f"{w} : une source « site » demande home et product_url")
        if kind == "feed":
            spec.update(_feed(src, spec, Path(path).parent, env, w))
        specs[key] = spec
    return specs


def _feed(src, spec, root, env, w):
    if not src.get("url"):
        raise ValueError(f"{w} : url du flux manquante")
    if not src.get("mapping"):
        raise ValueError(f"{w} : mapping manquant (un objet, un fichier, ou {{\"preset\": \"google_shopping\"}})")
    headers = dict(src.get("headers") or {})
    if not spec["enabled"]:                   # désactivée : rien à lire ni à résoudre ; vérifiée le jour où elle s'active
        return {"mapping": None, "url_template": src["url"], "headers": {}, "headers_template": headers}
    m = src["mapping"]
    if isinstance(m, str):
        f = Path(m) if Path(m).is_absolute() else root / m
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise ValueError(f"{w} : mapping illisible ({f} : {e})") from None
    try:
        mapping = Mapping.load(m, w)
    except FeedError as e:
        raise ValueError(str(e)) from None
    return {"mapping": mapping, "url_template": src["url"], "url": resolve(src["url"], env, w),
            "headers": {k: resolve(str(v), env, w) for k, v in headers.items()}, "headers_template": headers}


def address(spec, env=None):
    """L'adresse et les en-têtes d'une source « feed », résolus dans l'environnement, qu'elle soit activée ou non : pour
    lire un échantillon avant de l'activer (deals.py probe --source). Ils portent les identifiants du réseau : à ne
    jamais montrer ni journaliser."""
    env = os.environ if env is None else env
    w = f"DEALS_SOURCES : {spec['key']}"
    return {"url": resolve(spec["url_template"], env, w),
            "headers": {k: resolve(str(v), env, w) for k, v in (spec.get("headers_template") or {}).items()}}


def sites(specs):
    """Les sources lues par leurs fiches (le crawler de pages/)."""
    return {k: s for k, s in specs.items() if s["kind"] == "site"}


def feeds(specs):
    return {k: s for k, s in specs.items() if s["kind"] == "feed"}


def public(spec):
    """Ce qu'on peut montrer d'une source (journal, deals.py sources) : jamais l'adresse résolue ni les en-têtes, qui
    portent les identifiants du réseau."""
    return {k: v for k, v in spec.items() if k not in ("url", "headers", "mapping", "headers_template")}
