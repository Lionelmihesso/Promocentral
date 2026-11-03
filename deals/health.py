"""Contrôles de santé de la nuit : ce qui doit alerter, chiffres à l'appui, et où lire quoi faire (docs/RUNBOOK.md).

`snapshot` lit l'état de la nuit (bilan de la passe, sources, quarantaine, publication, e-mails des missions, taille et
fraîcheur du catalogue, clics) ; `findings`, pure, en tire les constats d'après des seuils versionnés (RULES). Un constat
a un type, une entité, une gravité (info, warning, critical), ses preuves et sa fiche du runbook ; l'agent (agent.py) en
fait des incidents. `cause` dit pourquoi une source va mal ; l'agent s'en sert pour choisir quoi faire.
"""
import json
import statistics
from datetime import datetime, timezone

from . import sources

RULES = {"version": "h4", "suspect_min": 5, "suspect_share": 0.20,
         "catalog": 0.80, "catalog_min": 20, "freshness": 0.90, "freshness_critical": 0.70, "mass_min": 30, "mass_factor": 3,
         "clicks_drop": 0.30, "clicks_min": 20, "feed_rejects": 0.20, "feed_collapse": 0.50}
RUNBOOK = {"source_failing": "source-en-echec", "source_layout": "flux-change", "suspect_prices": "prix-suspects",
           "catalog_held": "catalogue-retenu", "catalog_small": "catalogue-reduit", "freshness": "fraicheur",
           "mission_mail": "envoi-des-missions", "mail_quota": "quota-e-mails", "mass_mail": "envoi-massif",
           "clicks_drop": "clics-en-chute", "night_error": "nuit-en-erreur", "feed_rejects": "flux-lignes-refusees",
           "feed_collapse": "flux-en-baisse"}
KIND = {"layout": "source_layout", "transient": "source_failing"}
EVIDENCE = ("pages", "success", "errors", "interrupted", "failures")


def day_start(ts):
    d = datetime.fromtimestamp(ts, timezone.utc).date()
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()


def cause(s):
    """Pourquoi une source va mal, d'après son bilan de la nuit → layout (le flux ne donne presque plus de prix barré alors
    que les prix n'ont pas bougé : sa correspondance a sans doute changé), transient (flux injoignable, illisible, ou sans
    aucune offre retenue), ou None : elle va bien."""
    if (s or {}).get("pages") and s.get("was_drop"):
        return "layout"
    return "transient" if sources.failed(s) else None


def history(store, key, n=7):
    """Les n dernières nuits complètes (runs.stats écrit par night.py) : la valeur `key` de chacune, la plus récente d'abord."""
    rows = store.q("SELECT stats FROM runs WHERE stats IS NOT NULL AND COALESCE(status, '') NOT IN ('retry', 'running') "
                   "ORDER BY id DESC LIMIT ?", (4 * n,))
    out = []
    for r in rows:
        v = json.loads(r["stats"])
        for part in key.split("."):
            v = v.get(part) if isinstance(v, dict) else None
        if isinstance(v, (int, float)):
            out.append(v)
    return out[:n]


def freshness(store, now):
    """Produits publiés, et ceux dont le prix montré a été confirmé par une lecture depuis 26 h (une tentative ratée ne
    compte pas : offers.checked_at est l'heure de la dernière tentative, prices.last_seen celle du dernier prix lu)."""
    rows = store.q("SELECT o.retailer, (SELECT MAX(p.last_seen) FROM prices p WHERE p.offer_id=c.offer_id AND p.rejected=0) >= ? AS fresh "
                   "FROM catalog c JOIN offers o ON o.id=c.offer_id", (now - 26 * 3600,))
    stale = {}
    for r in rows:
        if not r["fresh"]:
            stale[r["retailer"]] = stale.get(r["retailer"], 0) + 1
    return {"products": len(rows), "fresh": sum(bool(r["fresh"]) for r in rows), "stale_by_source": stale}


def mass_threshold(store, rules=RULES):
    """Au-delà de ce nombre de personnes à prévenir en une nuit, l'envoi attend une décision (missions.notify)."""
    past = history(store, "missions.emails")
    return max(rules["mass_min"], rules["mass_factor"] * (statistics.median(past) if past else 0))


def snapshot(store, now, collect=None, publish=None, missions=None, errors=()):
    """L'état de la nuit, pour les contrôles : par source (bilan de la passe et état), offres en quarantaine par source,
    publication, missions, offres publiées par source face aux 7 nuits d'avant, fraîcheur (produits dont le prix montré a
    été lu depuis 26 h), clics des dernières 24 h face aux 7 jours d'avant."""
    reg = {r["key"]: r for r in store.q("SELECT * FROM sources")}
    per = (collect or {}).get("retailers") or {}
    fresh = freshness(store, now)
    start = day_start(now)
    days = [store.q("SELECT COUNT(*) n FROM clicks WHERE at>=? AND at<?", (start - k * 86400, start - (k - 1) * 86400), one=True)["n"]
            for k in range(1, 8)]
    offers = {r["retailer"]: r["n"] for r in store.q("SELECT o.retailer, COUNT(*) n FROM catalog_offers co JOIN offers o "
                                                     "ON o.id=co.offer_id GROUP BY o.retailer")}
    ref = {k: statistics.median(h) for k in set(reg) | set(offers) if (h := history(store, f"catalog_sources.{k}"))}
    return {"sources": {k: {**(per.get(k) or {}), "status": r["status"], "failures": r["failures"]} for k, r in reg.items()},
            "quarantine": {r["retailer"]: r["n"] for r in store.q("SELECT o.retailer, COUNT(*) n FROM quarantine q JOIN offers o "
                                                                  "ON o.id=q.offer_id WHERE q.status='held' GROUP BY o.retailer")},
            "publish": publish or {}, "missions": missions or {}, "errors": list(errors),
            "catalog": {"products": fresh["products"], "offers": offers, "reference": ref},
            "freshness": fresh,
            "clicks": {"last_day": store.q("SELECT COUNT(*) n FROM clicks WHERE at>=?", (now - 86400,), one=True)["n"],
                       "median_7d": statistics.median(days)}}


def finding(kind, entity, severity, **evidence):
    return {"kind": kind, "entity": entity or "", "severity": severity, "evidence": evidence, "runbook": RUNBOOK[kind]}


def findings(snap, rules=RULES):
    """Les constats d'une nuit (pur) : sources en échec, flux changé, lignes refusées en nombre, flux en baisse, prix
    suspects en nombre, publication retenue, catalogue réduit, fraîcheur insuffisante, e-mails des missions en échec,
    différés ou retenus (envoi massif), clics en chute, étape de la nuit en erreur."""
    out = []
    for key, s in sorted(snap["sources"].items()):
        pages = s.get("pages") or 0
        if not (pages or s.get("interrupted")):
            continue                                         # pas lue cette nuit : mise de côté, pas partenaire
        c = cause(s)
        if c:
            out.append(finding(KIND[c], key, "critical" if s.get("failures", 0) >= sources.FAIL_NIGHTS else "warning",
                               **{k: s.get(k) for k in EVIDENCE}, **({"was_drop": True} if s.get("was_drop") else {})))
        if s.get("kind") == "feed" and not s.get("broken"):     # un flux lu : la qualité de ses lignes
            if s.get("pages") and s.get("reject_share", 0) >= rules["feed_rejects"]:
                out.append(finding("feed_rejects", key, "warning", rejected=s.get("rejected"), pages=s.get("pages"),
                                   share=s.get("reject_share"), reasons=s.get("reasons")))
            if s.get("previous_accepted") and s.get("accepted", 0) < rules["feed_collapse"] * s["previous_accepted"]:
                out.append(finding("feed_collapse", key, "warning", accepted=s.get("accepted"), before=s["previous_accepted"]))
        held = (snap.get("quarantine") or {}).get(key, 0)
        if held >= rules["suspect_min"] and pages and held / pages >= rules["suspect_share"]:
            out.append(finding("suspect_prices", key, "warning", held=held, pages=pages))
    pub = snap.get("publish") or {}
    if pub.get("held"):
        out.append(finding("catalog_held", "", "critical", **pub["held"]))
    cat = snap.get("catalog") or {}
    off = {k for k, s in snap["sources"].items() if s.get("status") == "disabled"}      # départ attendu : déjà signalé
    expected = sum(v for k, v in (cat.get("reference") or {}).items() if k not in off)
    actual = sum(v for k, v in (cat.get("offers") or {}).items() if k not in off)
    if expected >= rules["catalog_min"] and actual < rules["catalog"] * expected:
        out.append(finding("catalog_small", "", "critical", offers=actual, reference=expected, products=cat.get("products")))
    f = snap["freshness"]
    if f["products"]:
        share = round(f["fresh"] / f["products"], 3)
        if share < rules["freshness"]:
            stale = f.get("stale_by_source") or {}
            known = {k for k, s in snap["sources"].items() if s.get("status") in ("degraded", "disabled") or s.get("failures")}
            explained = bool(stale) and set(stale) <= known          # déjà signalé : les sources en cause ont leur incident
            out.append(finding("freshness", "", "info" if explained else "critical" if share < rules["freshness_critical"] else "warning",
                               share=share, products=f["products"], stale_by_source=stale,
                               **({"explained_by": sorted(stale)} if explained else {})))
    m = snap.get("missions") or {}
    if m.get("failed"):
        out.append(finding("mission_mail", "", "warning", failed=m["failed"]))
    if m.get("deferred"):
        out.append(finding("mail_quota", "", "info", deferred=m["deferred"]))
    if m.get("held"):
        out.append(finding("mass_mail", "", "warning", held=m["held"]))
    c = snap["clicks"]
    if c["median_7d"] >= rules["clicks_min"] and c["last_day"] < rules["clicks_drop"] * c["median_7d"]:
        out.append(finding("clicks_drop", "", "warning", last_day=c["last_day"], median_7d=c["median_7d"]))
    for step, error in snap.get("errors") or ():
        out.append(finding("night_error", step, "critical", error=error))
    return out
