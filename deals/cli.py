"""DEALS — une seule ligne de commande.

  python deals.py serve [--port 8000]                l'app et son API (en production, derrière Caddy)
  python deals.py demo [--port 8000]                 l'app sur un marché simulé (base temporaire)
  python deals.py nightly                            la nuit (night.py) : collecte → agent → publication → missions →
                                                     contrôles → rapport du matin → e-mail au responsable s'il y a lieu
  python deals.py status                             l'état : dernière nuit, catalogue, sources, incidents, décisions
  python deals.py incidents [--all] | actions [--n 30] | events [--cid …]   incidents, actions auditées, journal
  python deals.py approve|reject <n°>                décider d'une proposition de l'agent
  python deals.py sources [enable|disable <clé>]     registre des sources, reprendre ou mettre de côté
  python deals.py quarantine [release <offre>]       prix suspects retenus, libérer un prix vérifié
  python deals.py partners                           enseignes partenaires déclarées (DEALS_AFFILIATE) et leur source
  python deals.py missions                           e-mails des missions arrivées à leur prix (fait par nightly)
  python deals.py publish                            republier le catalogue sans relire le web
  python deals.py discover|diagnose|sample|build <enseigne|all>     constituer et régler la base
  python deals.py explain <adresse>                  ce que l'extraction voit sur une page
  python deals.py rules <site> '<json>'              règle de lecture d'un site (sélecteurs)
  python deals.py review | estimate | metrics        rapprochements à vérifier, durée de la nuit, mesures
  python deals.py backup <dossier> [--keep 14]       sauvegarde à chaud vérifiée
Option commune, avant la commande : --db (défaut : DEALS_DB, sinon deals.sqlite). Réglages : deals/config.py.
Les commandes qui lisent les sites refusent de partir sans DEALS_USER_AGENT (nom du robot, page, contact).
Enseignes partenaires : DEALS_AFFILIATE (affiliate.py) ; seules leurs offres sont publiées, chaque clic part par leur lien
affilié. Sans ce fichier (développement), tout est publié et les liens partent tels quels ; la démo les simule.
Gestes d'un responsable (approve, reject, sources enable|disable, quarantine release) : journalisés avec son nom
(DEALS_ACTOR, que pose « sudo deals », sinon SUDO_USER, sinon l'utilisateur courant), comme les actions de l'agent.
"""
import argparse
import csv
import getpass
import json
import os
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

from . import affiliate, config, health, night, quarantine, sources
from .accounts import outbox_for
from .agent import LABEL, STATUS, Agent, Tools, describe, names
from .api import Api
from .backup import backup
from .collect import diagnose as D
from .collect.crawl import Crawler
from .collect.discover import discover
from .collect.retailers import RETAILERS
from .fetch import Fetcher
from .catalog import Catalog
from .market import Market
from .missions import Missions
from .ops import Ops, utc
from .publish import publish
from .store import Store
from .web import make_server


NETWORK = ("nightly", "discover", "diagnose", "sample", "build", "explain")
STALE_S = 36 * 3600            # plus de 36 h sans nuit : le minuteur ne tourne plus (aussi vu par /api/r/health)
NIGHT = {"succeeded": "réussie", "partial_success": "réussie en partie", "failed": "en erreur", "running": "en cours"}
SOURCE = {"active": "active", "degraded": "en difficulté", "disabled": "mise de côté"}


def status_lines(store, now=None):
    """Le centre de commande en quelques lignes : dernière nuit, catalogue, sources, incidents, décisions en attente."""
    now = now or time.time()
    last = store.q("SELECT * FROM runs WHERE COALESCE(status, '')!='retry' ORDER BY id DESC LIMIT 1", one=True)
    open_ = store.q("SELECT * FROM incidents WHERE status='open' ORDER BY severity='critical' DESC, id")
    proposed = store.q("SELECT * FROM actions WHERE status='proposed' ORDER BY id")
    age = now - (last["ended"] or last["started"]) if last else None
    late = age is not None and (age > STALE_S or last["status"] == "failed")      # comme la sonde (/api/r/health)
    state = "en attente de la première nuit" if last is None else "critique" if late or any(
        i["severity"] == "critical" for i in open_) else "dégradé" if open_ else "normal"
    lines = [f"Deals · état {state} · {utc(now)}"]
    if last:
        st = json.loads(last["stats"] or "{}")
        lines.append(f"Dernière nuit : {last['day']} · {NIGHT.get(last['status'], last['status'] or '—')} · "
                     f"{st.get('offers', 0)} pages relues · corrélation {last['cid'] or '—'}")
        if age > STALE_S:
            lines.append(f"⚠ aucune nuit depuis {age / 3600:.0f} h : le minuteur tourne-t-il ? (docs/RUNBOOK.md#nuit-absente)")
    else:
        lines.append("Aucune nuit encore : python deals.py nightly")
    cat = store.q("SELECT COUNT(*) n, SUM(pct > 0) d FROM catalog", one=True)
    fresh = health.freshness(store, now)
    share = round(100 * fresh["fresh"] / fresh["products"]) if fresh["products"] else 0
    held = len(quarantine.held(store))
    lines.append(f"Catalogue : {cat['n']} produits · {cat['d'] or 0} remises · fraîcheur {share} % · {held} offre(s) en quarantaine")
    parts, reg = [], sources.listing(store)
    partners = any(r["partner"] for r in reg)                # sans fichier de partenaires (développement), aucune ne l'est
    for r in reg:
        note = f" ({r['reason']})" if r["status"] == "disabled" and r["reason"] else \
            f" ({r['failures']} nuit(s) ratée(s))" if r["failures"] else ""
        parts.append(f"{r['name']} {'plus partenaire, plus lue' if partners and not r['partner'] else SOURCE[r['status']] + note}")
    if parts:
        lines.append("Sources : " + " · ".join(parts))
    who = names(store)
    if open_:
        lines += ["Incidents ouverts :"] + [f"  [{i['id']}] {describe(store, i, who)} — docs/RUNBOOK.md#{i['runbook']}" for i in open_]
    if proposed:
        lines += ["À décider :"] + [f"  [{x['id']}] {LABEL[x['action']]} · {who(x['entity'])} — {x['justification']} → "
                                    f"deals.py approve {x['id']} | deals.py reject {x['id']}" for x in proposed]
    if last and last["cid"]:
        n = store.q("SELECT COUNT(*) n FROM actions WHERE cid=?", (last["cid"],), one=True)["n"]
        lines.append(f"Cette nuit : {n} action(s) de l'agent (deals.py actions) · journal : deals.py events --cid {last['cid']}")
    return lines


def _serve(store, settings, port, rules=None):
    srv = make_server(Api(store, settings, rules=rules), store, settings, port=port)
    print(f"App : http://127.0.0.1:{port}/")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


def main(argv=None):
    try:
        settings = config.load()
        rules = affiliate.load(settings.affiliate)             # enseignes partenaires ; None : développement
    except ValueError as e:
        sys.exit(f"Réglage invalide : {e}")
    ap = argparse.ArgumentParser(prog="deals", description="DEALS — les bons deals du jour")
    ap.add_argument("--db", default=settings.db)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("serve", "demo"):
        sub.add_parser(name).add_argument("--port", type=int, default=settings.port)
    for name in ("nightly", "publish", "missions", "status", "partners"):
        sub.add_parser(name)
    sub.add_parser("incidents").add_argument("--all", action="store_true", help="aussi les incidents résolus (30 derniers)")
    sub.add_parser("actions").add_argument("--n", type=int, default=30)
    e = sub.add_parser("events")
    e.add_argument("--cid", help="identifiant de corrélation d'une nuit (deals.py status le donne)")
    e.add_argument("--n", type=int, default=50)
    for name in ("approve", "reject"):
        sub.add_parser(name).add_argument("id", type=int, help="numéro de la proposition (deals.py status)")
    so = sub.add_parser("sources")
    so.add_argument("op", nargs="?", choices=("enable", "disable"))
    so.add_argument("key", nargs="?")
    so.add_argument("--reason", default="")
    qu = sub.add_parser("quarantine")
    qu.add_argument("op", nargs="?", choices=("release",))
    qu.add_argument("offer", nargs="?", type=int)
    for name in ("discover", "diagnose", "sample", "build"):
        s = sub.add_parser(name)
        s.add_argument("retailer", help="clé d'enseigne ou « all »")
        s.add_argument("--per", type=int, default=40, help="discover : fiches par catégorie")
        s.add_argument("--n", type=int, default=20, help="diagnose / sample : pages par enseigne")
    sub.add_parser("explain").add_argument("url")
    r = sub.add_parser("rules")
    r.add_argument("host")
    r.add_argument("rules", help="JSON : sélecteurs (price, list_price, availability, title, gtin…)")
    for name in ("review", "estimate", "metrics"):
        sub.add_parser(name)
    b = sub.add_parser("backup")
    b.add_argument("dest")
    b.add_argument("--keep", type=int, default=14)
    a = ap.parse_args(argv)
    settings = replace(settings, db=a.db)
    if a.cmd in NETWORK and settings.user_agent == config.Settings.user_agent:
        sys.exit("Avant de lire les sites, réglez DEALS_USER_AGENT : nom du robot, page qui le décrit, contact "
                 "(voir deploy/deals.env.example). Les enseignes doivent savoir qui les lit.")

    if a.cmd == "demo":
        from .demo import FIRST_NIGHT, LAST_NIGHT, RULES, build
        store = Store(os.path.join(tempfile.mkdtemp(prefix="deals-demo-"), "demo.sqlite"))
        print(f"Marché simulé : {(LAST_NIGHT - FIRST_NIGHT).days + 1} nuits de collecte et de publication…")
        build(store, partners=set(RULES))                    # enseignes simulées, toutes partenaires (liens simulés)
        return _serve(store, settings, a.port, RULES)
    if a.cmd == "backup":
        print(backup(settings.db, a.dest, a.keep))
        return 0
    store = Store(settings.db)
    if a.cmd == "serve":
        return _serve(store, settings, a.port, rules)
    partners = set(rules) if rules else None
    if partners is None and a.cmd in ("nightly", "publish"):
        print("Aucune enseigne partenaire (DEALS_AFFILIATE) : tout est publié et les liens partent tels quels (développement).")
    missions = lambda: Missions(store, Catalog(store)).notify(outbox_for(settings), settings.public_url,
                                                             settings.mail_from or settings.smtp_user or "deals@localhost",
                                                             settings.mission_mails)
    if a.cmd == "missions":
        print(json.dumps(missions(), ensure_ascii=False))
        return 0

    market = Market(store)
    fetcher = Fetcher(user_agent=settings.user_agent, min_interval=settings.min_interval_s)
    crawler = Crawler(market, fetcher, RETAILERS, settings.night_budget_s)
    keys = lambda: [k for k in RETAILERS if RETAILERS[k]["enabled"]] if a.retailer == "all" else [a.retailer]

    def urls(k, n=None):
        f = Path(f"urls/{k}.json")
        if not f.exists():
            print(f"{k} : lancez d'abord « python deals.py discover {k} »")
            return None
        by_cat = json.loads(f.read_text(encoding="utf-8"))
        if n is None:
            return by_cat
        flat = [u for v in by_cat.values() for u in v]
        return flat[::max(1, len(flat) // n)][:n]

    who = os.environ.get("DEALS_ACTOR") or os.environ.get("SUDO_USER") or getpass.getuser()
    ops = Ops(store, settings.env, sys.stderr if settings.log_json else None)
    publish_now = lambda guard=False: publish(store, market.today(), market.clock(), partners, guard=guard)
    agent = lambda: Agent(store, ops, Tools(store, publish=publish_now, notify=missions), cid=ops.new_cid("geste"),
                          operator=settings.operator_email or None, actor=who)

    if a.cmd == "nightly":
        if partners is not None and not partners & {k for k in RETAILERS if RETAILERS[k]["enabled"]}:
            store.close()
            sys.exit("DEALS_AFFILIATE : aucune des enseignes déclarées n'est suivie (clés de deals/collect/retailers.py).")
        if partners is not None and partners - set(RETAILERS):
            print("Enseignes partenaires inconnues, ignorées :", ", ".join(sorted(partners - set(RETAILERS))))
        out = night.run(store, settings, crawler, outbox_for(settings), RETAILERS, rules, stream=ops.stream,
                        report_dir=settings.reports_dir)
        if out["report"]:
            print(Path(settings.reports_dir, f"{out['report']}.md").read_text(encoding="utf-8"))
        print(f"Nuit {out['cid']} : {out['status']} · catalogue {out['catalog']} produits"
              f"{' (publication retenue)' if (out['publish'] or {}).get('held') else ''} · "
              f"{len(out['incidents'])} incident(s) ouvert(s) · {len(out['actions'])} action(s)"
              f"{' · responsable prévenu' if out['escalated'] else ''}")
        print("Missions :", json.dumps(out["missions"], ensure_ascii=False))
        for step, error in out["errors"]:
            print(f"⚠ étape « {step} » en erreur : {error}")
    elif a.cmd == "status":
        print("\n".join(status_lines(store)))
    elif a.cmd == "incidents":
        rows = store.q("SELECT * FROM incidents ORDER BY status='open' DESC, id DESC LIMIT 30") if a.all else \
            store.q("SELECT * FROM incidents WHERE status='open' ORDER BY id")
        who_ = names(store)
        for i in rows:
            print(f"[{i['id']}] {describe(store, i, who_)} · ouvert le {utc(i['opened_at'])[:10]}"
                  f"{' · résolu le ' + utc(i['resolved_at'])[:10] if i['resolved_at'] else ''}\n"
                  f"     preuves : {i['evidence']}\n     fiche : docs/RUNBOOK.md#{i['runbook']}")
        if not rows:
            print("Aucun incident ouvert.")
    elif a.cmd == "actions":
        who_ = names(store)
        for x in reversed(store.q("SELECT * FROM actions ORDER BY id DESC LIMIT ?", (a.n,))):
            print(f"[{x['id']}] {utc(x['at'])} · {x['actor']} · {LABEL.get(x['action'], x['action'])} · {who_(x['entity'])} · "
                  f"{x['policy']} · {STATUS.get(x['status'], x['status'])}{' par ' + x['decided_by'] if x['decided_by'] else ''}\n"
                  f"     {x['justification']}{chr(10) + '     retour arrière : ' + x['rollback_plan'] if x['rollback_plan'] else ''}")
    elif a.cmd == "events":
        for ev in ops.recent(a.cid, a.n):
            print(f"{utc(ev['at'])} {ev['severity']:<8} {ev['component']:<9} {ev['kind']:<18} {ev['entity'] or '—'} "
                  f"{json.dumps(ev['payload'], ensure_ascii=False)} [{ev['cid'] or '—'}]")
    elif a.cmd in ("approve", "reject"):
        try:
            x = getattr(agent(), a.cmd)(a.id, who)
        except ValueError as err:
            store.close()
            sys.exit(str(err))
        print(f"[{x['id']}] {LABEL.get(x['action'], x['action'])} : {STATUS[x['status']]}"
              f"{' — ' + x['result'] if x['result'] and x['status'] != 'rejected' else ''}")
    elif a.cmd == "sources":
        if a.op:
            if not a.key:
                store.close()
                sys.exit(f"deals.py sources {a.op} <clé>")
            ag = agent()
            try:
                if a.op == "enable":
                    ag.manual("enable_source", a.key, who, f"reprise à la main{' : ' + a.reason if a.reason else ''}",
                              lambda: ag.tools.enable_source(a.key), rollback=f"deals.py sources disable {a.key}")
                else:
                    ag.manual("disable_source", a.key, who, a.reason or "mise de côté à la main",
                              lambda: ag.tools.disable_source(a.key, f"{who} : {a.reason or 'à la main'}"),
                              rollback=f"deals.py sources enable {a.key}")
            except KeyError:
                store.close()
                sys.exit(f"source inconnue : {a.key} (deals.py sources les liste)")
        for r in sources.listing(store):
            print(f"{r['key']:<16} {r['name']:<18} {r['status']:<9} {'partenaire' if r['partner'] else '—':<11} "
                  f"nuits ratées {r['failures']} · dernière réussite {utc(r['last_success'])[:10] if r['last_success'] else '—'}"
                  f"{' · ' + r['reason'] if r['reason'] else ''}")
    elif a.cmd == "quarantine":
        if a.op == "release":
            if a.offer is None or not store.q("SELECT 1 FROM quarantine WHERE offer_id=? AND status='held'", (a.offer,), one=True):
                store.close()
                sys.exit("aucune offre en quarantaine sous ce numéro (deals.py quarantine les liste)")
            ag = agent()
            ag.manual("release_offer", f"offre {a.offer}", who, "libérée à la main : prix vérifié chez l'enseigne",
                      lambda: {"rejected": quarantine.release(store, a.offer, f"libéré par {who}", time.time())})
            print(f"offre {a.offer} libérée : publiée à la prochaine publication (deals.py publish pour tout de suite)")
        for q in quarantine.held(store):
            print(f"offre {q['offer_id']} · {q['merchant']} · {q['title'] or q['url']} : {q['price']:.2f} € pour {q['usual']:.2f} € "
                  f"d'habitude · depuis le {utc(q['since'])[:10]} · relue {q['confirmed']} fois au même prix")
        if not quarantine.held(store):
            print("Aucune offre en quarantaine.")
    elif a.cmd == "partners":
        if rules is None:
            print("Aucun fichier de partenaires (DEALS_AFFILIATE) : développement, tout est lu et publié.")
        reg = {r["key"]: r for r in sources.listing(store)}
        for k in sorted(rules or ()):
            known = k in RETAILERS
            src = reg.get(k)
            print(f"{k:<16} {RETAILERS[k]['name'] if known else 'inconnue':<18} "
                  f"{('suivie' if RETAILERS[k]['enabled'] else 'désactivée dans le code') if known else 'clé absente de retailers.py'}"
                  f"{' · source ' + src['status'] if src else ''}")
    elif a.cmd == "publish":
        print(json.dumps(publish(store, market.today(), market.clock(), partners), ensure_ascii=False))
    elif a.cmd == "discover":
        Path("urls").mkdir(exist_ok=True)
        for k in keys():
            res = discover(fetcher, RETAILERS[k], a.per)
            Path(f"urls/{k}.json").write_text(json.dumps(res["by_category"], ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"{RETAILERS[k]['name']:<16} {res['total']:>5} fiches · {res['files_read']} plans de site lus · "
                  + ", ".join(f"{c} {len(v)}" for c, v in res["by_category"].items()))
    elif a.cmd == "diagnose":
        Path(settings.reports_dir).mkdir(exist_ok=True)
        pct = lambda x: f"{x * 100:.0f} %"
        lines = ["| Enseigne | Pages | Lues | Avec prix | Prix barré | EAN | Bloquées | Protection | Verdict |", "|---|---|---|---|---|---|---|---|---|"]
        for k in keys():
            u = urls(k, a.n)
            if u is None:
                continue
            res = D.diagnose(crawler, k, u)
            s = res["summary"]
            with open(Path(settings.reports_dir, f"diagnostic-{k}.csv"), "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(res["rows"][0]) if res["rows"] else ["url"])
                w.writeheader()
                w.writerows(res["rows"])
            prot = ", ".join(f"{v} ({n})" for v, n in s["protections"].items()) or "—"
            lines.append(f"| {RETAILERS[k]['name']} | {s['pages']} | {pct(s['read_ok'])} | {pct(s['with_price'])} | {pct(s['with_was'])} | "
                         f"{pct(s['with_gtin'])} | {pct(s['blocked'])} | {prot} | {s['verdict']} |")
            print(lines[-1])
            print(f"    prix : {s['methods'] or '—'} · prix barré : {s['was_methods'] or '—'} · statuts : {s['statuses']}")
        Path(settings.reports_dir, "diagnostic.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif a.cmd == "sample":
        for k in keys():
            u = urls(k, a.n)
            if u:
                res = D.sample(fetcher, k, u)
                print(f"{RETAILERS[k]['name']:<16} {res['saved']}/{res['pages']} pages enregistrées dans {res['dir']}")
        print("Compressez le dossier samples/ et joignez-le : l'extraction se règle alors sur vos vraies pages.")
    elif a.cmd == "build":
        for k in keys():
            u = urls(k)
            if u:
                print(json.dumps(crawler.build(k, u), ensure_ascii=False))
    elif a.cmd == "explain":
        d = crawler.inspect(a.url)
        print(f"statut {d['status']} (HTTP {d.get('code')}) · page {d.get('page_kind')} · protection {d.get('protection') or '—'}")
        for c in d.get("candidates") or []:
            print(f"  source {c['method']:<10} prix {c['price']} · barré {c['list_price']} · {c['currency']} · {c['availability']} · EAN {c['gtin']}")
        ex = d.get("extraction")
        if ex:
            print(f"→ retenu : {ex['price']} € ({ex['method']}) · prix barré {ex.get('list_price')} ({ex.get('was_method') or '—'}) · "
                  f"{ex['availability']} · {ex.get('title')} · vendeur {ex.get('seller') or '—'} · catalogue : {d.get('scope') or 'oui'}")
        for reason in d.get("reasons") or []:
            print(f"  ! {reason}")
        if d.get("hint"):
            print(d["hint"])
    elif a.cmd == "rules":
        market.set_rules(a.host, json.loads(a.rules))
        print(f"règle enregistrée pour {a.host} : relancez « python deals.py diagnose <enseigne> »")
    elif a.cmd == "review":
        for p in store.q("SELECT id, title, brand, gtin FROM products WHERE needs_review=1 LIMIT 50"):
            merchants = " | ".join(o["merchant"] for o in store.q("SELECT merchant FROM offers WHERE product_id=?", (p["id"],)))
            print(f"[{p['id']}] {p['brand'] or ''} {p['title']} (EAN {p['gtin'] or '—'}) : {merchants}")
    elif a.cmd == "estimate":
        print(crawler.estimate())
    elif a.cmd == "metrics":
        from .activity import Activity
        last = store.q("SELECT day, stats FROM runs WHERE stats IS NOT NULL AND COALESCE(status, '')!='retry' "
                       "ORDER BY id DESC LIMIT 1", one=True)
        print(json.dumps({**Activity(store).metrics(),
                          "catalog": store.q("SELECT COUNT(*) products, SUM(pct > 0) deals, SUM(verified) verified FROM catalog", one=True),
                          "last_night": {"day": last["day"], **{k: v for k, v in json.loads(last["stats"]).items() if k in ("offers", "products")}}
                          if last else None}, ensure_ascii=False, indent=1, default=str))
    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
