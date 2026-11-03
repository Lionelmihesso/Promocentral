"""Le registre des sources : quelles enseignes on lit, et comment. Une source par enseigne, sous sa clé, déclarée dans
le fichier DEALS_SOURCES (JSON). v68 : seuls les flux sont lus (kind « feed ») ; la lecture des fiches des enseignes est
retirée, une source « site » est refusée au démarrage.

Une source dit :
  url       où lire le flux : https://…, http://… ou un chemin de fichier ; ${NOM} y est remplacé par la variable
            d'environnement NOM (les identifiants des réseaux vivent dans /etc/deals/deals.env, jamais dans ce fichier)
  mapping   la correspondance de ses colonnes : un objet, ou le chemin d'un fichier JSON (relatif au fichier des sources)
            — voir feeds.Mapping ; {"preset": "google_shopping"} pour un flux au format standard
  headers   des en-têtes HTTP (${NOM} remplacé), facultatif
  name      le nom de l'enseigne (affiché), network (le réseau d'affiliation, information), families (familles
            attendues ; toutes par défaut), enabled
Un réglage invalide arrête le démarrage en nommant la source et le champ, plutôt qu'une nuit qui tourne mal.
"""
import json
import os
import re
from pathlib import Path

from ..extract.categories import FAMILIES
from .feeds import FeedError, Mapping

KINDS = ("feed",)
KEYS = {"kind", "name", "enabled", "families", "network", "url", "mapping", "headers", "disabled_reason", "_note"}
VAR = re.compile(r"\$\{([A-Z0-9_]+)\}")


def resolve(value, env, where):
    def one(m):
        if m.group(1) not in env or not env[m.group(1)]:
            raise ValueError(f"{where} : variable d'environnement {m.group(1)} absente")
        return env[m.group(1)]
    return VAR.sub(one, value)


def load(path=None, env=None):
    """→ {clé: source} : les flux du fichier `path` (aucun sans fichier)."""
    env = os.environ if env is None else env
    specs = {}
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
        kind = src.get("kind", "feed")
        if kind == "site":
            raise ValueError(f"{w} : kind « site » : la lecture des fiches des enseignes est retirée (v68), seuls les flux "
                             "sont lus")
        if kind not in KINDS:
            raise ValueError(f"{w} : kind {kind!r} au lieu de {' | '.join(KINDS)}")
        spec = {**{k: v for k, v in src.items() if k != "_note"}, "key": key, "kind": kind}
        spec["enabled"] = bool(spec.get("enabled", True))
        spec["families"] = list(spec.get("families") or FAMILIES)
        if not spec.get("name"):
            raise ValueError(f"{w} : name manquant (le nom de l'enseigne, affiché)")
        if set(spec["families"]) - set(FAMILIES):
            raise ValueError(f"{w} : famille inconnue {', '.join(sorted(set(spec['families']) - set(FAMILIES)))}")
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


def feeds(specs):
    return {k: s for k, s in specs.items() if s["kind"] == "feed"}


def public(spec):
    """Ce qu'on peut montrer d'une source (journal, deals.py sources) : jamais l'adresse résolue ni les en-têtes, qui
    portent les identifiants du réseau."""
    return {k: v for k, v in spec.items() if k not in ("url", "headers", "mapping", "headers_template")}
