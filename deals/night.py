"""La nuit de bout en bout : lire les sources, vérifier, publier, prévenir — l'agent veille à chaque étape (agent.py).

  registre des sources → ingestion des partenaires lisibles (ingest/collector.py : leurs flux, un lot par source ; leurs
  fiches en dernier recours) → agent : relance, nuits ratées, mise de côté, sonde (page témoin ou flux),
  quarantaine des prix suspects → publication (garde) → e-mails des missions (garde contre l'envoi massif) → contrôles
  de santé → incidents, conseils, décisions → rapport du matin → e-mail au responsable s'il y a lieu

Une étape qui casse n'arrête pas les suivantes : l'erreur devient un incident critique (night_error). Un identifiant de
corrélation suit la nuit dans le journal (events), la passe (runs), les actions et les incidents. Le bilan complet de la
nuit (passe, publication, missions, taille du catalogue) est gardé dans runs : il sert de référence aux nuits suivantes.
"""
import json
import time

from . import agent as A
from . import health, sources
from .accounts import expire_guests
from .catalog import Catalog
from .ingest import report
from .missions import Missions
from .ops import Ops
from .publish import publish


def sender_of(settings):
    return settings.mail_from or settings.smtp_user or "deals@localhost"


def run(store, settings, crawler, outbox, retailers, rules=None, clock=time.time, stream=None, report_dir=None):
    """Une nuit. retailers : les enseignes connues (clé → réglages, ingest/registry.py) ; rules : les enseignes
    partenaires (affiliate.py ; None en développement : tout est lu et publié) ; report_dir : où écrire le rapport du matin
    (None : pas de rapport). → bilan de la nuit."""
    ops = Ops(store, settings.env, stream, clock)
    cid, start, errors = ops.new_cid(), clock(), []
    ops.event("info", "night", "started", None, cid)

    def step(name, fn, default=None):
        try:
            return fn()
        except Exception as e:                               # une étape cassée n'arrête pas la nuit
            errors.append((name, f"{type(e).__name__} : {str(e)[:200]}"))
            ops.event("error", "night", "step_failed", name, cid, error=type(e).__name__, message=str(e)[:200])
            return default

    market, partners = crawler.m, (set(rules) if rules is not None else None)
    step("sources", lambda: sources.sync(store, retailers, partners, start))
    keys = sources.readable(store, [k for k, r in retailers.items() if r.get("enabled") and (partners is None or k in partners)])
    pub = lambda guard=True: publish(store, market.today(), clock(), partners, guard=guard)
    notify = lambda hold_above=None: Missions(store, Catalog(store)).notify(outbox, settings.public_url, sender_of(settings),
                                                                           settings.mission_mails, hold_above)
    agent = A.Agent(store, ops, A.Tools(store, clock, crawler, pub, notify), clock, cid, settings.operator_email or None)

    crawl = step("collecte", lambda: crawler.nightly(keys, cid=cid)) or {"retailers": {}}
    crawl = step("agent", lambda: agent.before_publish(crawl, start), crawl)
    held = {r["offer_id"] for r in store.q("SELECT offer_id FROM quarantine WHERE status='held'")}
    for d in crawl.get("price_drops") or ():
        d["held"] = d.get("offer_id") in held
    published = step("publication", pub)
    step("garde", lambda: agent.after_publish(published))
    missions = step("missions", lambda: notify(health.mass_threshold(store)))
    guests = step("invités", lambda: expire_guests(store, clock()), 0)          # clés expirées : plus personne ne peut les ouvrir
    found = step("contrôles", lambda: health.findings(health.snapshot(store, clock(), crawl, published, missions, errors)))
    if found is None:                                        # même sans contrôles, une étape cassée reste un incident
        found = [health.finding("night_error", name, "critical", error=e) for name, e in errors]
    step("incidents", lambda: agent.after_night(found))
    name = step("rapport", lambda: report.write(crawl, report_dir, A.journal(store, cid))) if report_dir and crawl.get("day") else None
    sent = step("escalade", lambda: agent.escalate(outbox, sender_of(settings)))

    catalog = store.q("SELECT COUNT(*) n FROM catalog", one=True)["n"]
    by_source = {r["retailer"]: r["n"] for r in store.q("SELECT o.retailer, COUNT(*) n FROM catalog_offers co JOIN offers o "
                                                        "ON o.id=co.offer_id GROUP BY o.retailer")}
    bad = any(sources.failed(r) for r in crawl["retailers"].values()) or bool((published or {}).get("held"))
    status = "failed" if errors else "partial_success" if bad else "succeeded"
    if crawl.get("run"):
        store.x("UPDATE runs SET stats=?, status=? WHERE id=?",
                (json.dumps({**crawl, "publish": published, "missions": missions, "catalog": catalog, "guests_expired": guests,
                             "catalog_sources": by_source, "errors": errors},
                            ensure_ascii=False, default=str), status, crawl["run"]))
    store.x("UPDATE runs SET status='failed', ended=COALESCE(ended, ?) WHERE cid=? AND status='running'", (clock(), cid))
    incidents = store.q("SELECT * FROM incidents WHERE status='open' ORDER BY id")
    actions = store.q("SELECT * FROM actions WHERE cid=? ORDER BY id", (cid,))
    ops.event("warning" if errors or incidents else "info", "night", "finished", None, cid, status=status, catalog=catalog,
              incidents=len(incidents), actions=len(actions), escalated=bool(sent))
    return {"cid": cid, "status": status, "crawl": crawl, "publish": published, "missions": missions, "catalog": catalog,
            "incidents": incidents, "actions": actions, "escalated": sent["Subject"] if sent else None, "report": name,
            "errors": errors}
