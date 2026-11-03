"""Agent opérateur : il observe la nuit, diagnostique, agit dans des limites écrites, vérifie, journalise et prévient.

Il ne calcule pas les prix : il lit ce que les modules produisent (bilan de la passe, contrôles de santé, quarantaine) et
n'agit que par des outils étroits (Tools) : relancer une source, la mettre de côté, relire son flux, la reprendre,
mettre un prix en quarantaine ou l'en sortir, publier malgré la garde, envoyer des e-mails retenus. Boucle : observer →
diagnostiquer → proposer → vérifier la politique → exécuter ce qui est permis → vérifier le résultat → journaliser →
escalader. Pas de modèle de langage : des règles écrites, versionnées, testées.

Politiques (POLICY) :
  auto       fait et journalisé                                relance, sonde du flux, quarantaine
  alert      fait, journalisé, et le responsable est prévenu   mise de côté d'une source, publication retenue
  approval   proposé ; `deals.py approve <n°>` l'exécute        reprendre une source, publier malgré la garde, envoi massif
  recommend  un conseil écrit, rien à exécuter                  correspondance du flux, e-mails, suivi des clics…
  forbidden  jamais : refusé et journalisé                      aucune aujourd'hui (contourner un anti-robot, avant la v68)
Chaque action garde l'acteur, la justification, les entrées, les préconditions, l'effet attendu, une clé d'idempotence
(relancer la nuit ne répète rien), le résultat, la vérification et le plan de retour arrière.

Le responsable (DEALS_OPERATOR_EMAIL) reçoit au plus un e-mail par nuit, et seulement s'il y a lieu : décision à prendre,
action « alert » exécutée, action automatique en échec, incident critique, incident sérieux qui dure (dès la première
nuit s'il ne peut pas être passager : flux changé, e-mails en échec…), incident signalé qui se résout. Un
envoi qui échoue est retenté la nuit suivante.
"""
import json
import time
from datetime import datetime, timezone
from email.message import EmailMessage

from . import health, quarantine, sources
from .ingest.report import euros

POLICY = {
    "retry_source": "auto",             # échec passager : relue une fois dans la nuit
    "probe_source": "auto",             # source mise de côté par l'agent : son flux relu tous les 3 jours
    "quarantine_offer": "auto",         # prix suspect (quarantine.RULE)
    "confirm_offer": "auto",
    "release_offer": "auto",
    "disable_source": "alert",          # sources.FAIL_NIGHTS nuits ratées de suite : on cesse de la solliciter
    "hold_publication": "alert",        # le nouveau catalogue fondait : celui de la veille reste en ligne
    "release_publication": "alert",     # deux nuits retenu sans décision : le catalogue de la veille a trop vieilli
    "enable_source": "approval",        # reprendre une source mise de côté
    "force_publication": "approval",    # publier malgré la garde
    "mass_notification": "approval",    # envoyer des e-mails de missions en nombre anormal
    "review_rules": "recommend",        # flux changé, prix suspects en nombre : la correspondance du flux doit suivre
    "check_partners": "recommend",      # catalogue qui fond : fichier des partenaires, état des sources
    "check_mail": "recommend",
    "check_tracking": "recommend",
}
PROBE_S = 3 * 86400
DIGEST_DONE = 12                        # e-mail au responsable : au plus 12 actions faites sans lui, la suite dans deals.py actions
SEVERITY = {"info": 0, "warning": 1, "critical": 2}
IMMEDIATE = {"source_layout", "catalog_held", "catalog_small", "mission_mail",
             "mass_mail", "night_error"}       # sérieux dès la première nuit : ne passera pas tout seul
SAY = {"source_failing": "en échec (erreurs)", "source_layout": "plus de prix barré : le flux a changé",
       "suspect_prices": "prix suspects en nombre",
       "catalog_held": "publication retenue : le nouveau catalogue fondait", "catalog_small": "catalogue réduit",
       "freshness": "fraîcheur du catalogue insuffisante", "mission_mail": "e-mails des missions en échec",
       "mail_quota": "e-mails des missions différés (quota)", "mass_mail": "e-mails des missions retenus : envoi massif",
       "clicks_drop": "clics en chute", "night_error": "étape de la nuit en erreur"}
LABEL = {"retry_source": "relancée", "probe_source": "flux relu", "disable_source": "mise de côté",
         "enable_source": "reprendre la source", "quarantine_offer": "prix mis en quarantaine", "confirm_offer": "prix suspect relu",
         "release_offer": "prix libéré", "hold_publication": "publication retenue", "release_publication": "publication relâchée",
         "force_publication": "publier malgré la garde",
         "mass_notification": "envoyer les e-mails retenus", "review_rules": "revoir la correspondance du flux",
         "check_partners": "vérifier les partenaires et les sources", "check_mail": "vérifier l'envoi des e-mails",
         "check_tracking": "vérifier le suivi des clics"}
STATUS = {"verified": "fait", "unverified": "sans effet", "failed": "échec", "proposed": "à décider", "recommended": "conseil", "refused": "refusé (interdit)",
          "executed": "exécuté", "rejected": "refusé", "expired": "caduc"}
CAUSE = {"layout": "flux changé", "transient": "erreurs"}


def utc_day(ts):
    return datetime.fromtimestamp(ts, timezone.utc).date()


def brief(stat):
    return {k: (stat or {}).get(k) for k in ("pages", "ok", "success", "errors", "interrupted")}


class Tools:
    """Ce que l'agent peut toucher, et rien d'autre. collector (les flux), publish et notify sont fournis par la nuit
    (night.py) ou la ligne de commande."""

    def __init__(self, store, clock=time.time, collector=None, publish=None, notify=None):
        self.s, self.clock, self.collector, self.publish_fn, self.notify_fn = store, clock, collector, publish, notify

    def retry_source(self, key, cid=None):
        return (self.collector.nightly([key], cid=cid, retry=True).get("retailers") or {}).get(key) or {}

    def probe_source(self, key):
        return self.collector.probe_source(key)        # le flux se lit-il de nouveau ? (ingest/collector.py)

    def disable_source(self, key, reason):
        sources.set_status(self.s, key, "disabled", reason, self.clock())
        return {"status": "disabled"}

    def enable_source(self, key):
        sources.set_status(self.s, key, "active", None, self.clock())
        return {"status": "active"}

    def force_publication(self):
        return self.publish_fn(guard=False)

    def send_missions(self):
        return self.notify_fn()


class Agent:
    def __init__(self, store, ops, tools, clock=time.time, cid=None, operator=None, actor="agent"):
        self.s, self.ops, self.tools, self.clock, self.cid, self.operator, self.actor = store, ops, tools, clock, cid, operator, actor
        self.day = utc_day(clock()).isoformat()

    # ------------------------------------------------------------ une action
    def act(self, action, entity, justification, *, inputs=None, preconditions=None, expected=None, rollback=None,
            incident=None, run=None, verify=None, key=None):
        """Une action, selon sa politique → sa ligne d'audit (dict). Idempotente : même clé, même ligne, rien n'est refait ;
        une proposition déjà en attente pour la même chose n'est pas dupliquée."""
        key = key or f"{action}:{entity}:{self.day}"
        done = self.s.q("SELECT * FROM actions WHERE idempotency_key=?", (key,), one=True)
        if done:
            return done
        policy = POLICY[action]
        if policy == "approval":
            pending = self.s.q("SELECT * FROM actions WHERE action=? AND entity IS ? AND status='proposed'", (action, entity), one=True)
            if pending:
                return pending
        status = {"forbidden": "refused", "approval": "proposed", "recommend": "recommended"}.get(policy)
        result = verification = None
        if policy in ("auto", "alert"):
            try:
                result = run() if run else None
                ok, verification = verify(result) if verify else (True, None)
                status = "verified" if ok else "unverified"          # fait, mais l'effet attendu n'est pas là
            except Exception as e:                           # un outil qui casse : l'action échoue, la nuit continue
                status, result = "failed", {"error": type(e).__name__, "message": str(e)[:200]}
        aid = self.s.x("INSERT INTO actions(at, actor, action, entity, incident_id, policy, status, justification, inputs, "
                       "preconditions, expected_effect, idempotency_key, result, verification, rollback_plan, cid) "
                       "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (self.clock(), self.actor, action, entity, incident, policy, status, justification, _j(inputs),
                        _j(preconditions), expected, key, _j(result), _j(verification), rollback, self.cid))
        self.ops.event("warning" if status in ("failed", "refused") or policy == "alert" else "info", "agent", action, entity,
                       self.cid, policy=policy, status=status, action_id=aid)
        return self.s.q("SELECT * FROM actions WHERE id=?", (aid,), one=True)

    # ------------------------------------------------------------ avant la publication : sources et prix suspects
    def before_publish(self, collect, night_start):
        """Relance une source en échec passager, compte les nuits ratées, met de côté une source qui échoue trop, relit le
        flux des sources mises de côté, met en quarantaine les prix suspects. → le bilan de la passe, mis à jour des
        relances réussies."""
        per = dict((collect or {}).get("retailers") or {})
        now = self.clock()
        for key in [r["key"] for r in self.s.q("SELECT key FROM sources WHERE status!='disabled' ORDER BY key")]:
            stat = per.get(key)
            bad = sources.failed(stat)
            if bad is None:
                continue                                     # pas lue cette nuit : rien à juger
            why = health.cause(stat) if bad else None
            if why == "transient":
                a = self.act("retry_source", key, f"flux en échec ({stat.get('error') or 'aucune offre retenue'}) : panne "
                             "passagère probable, relu une fois",
                             inputs={"before": brief(stat)}, preconditions={"cause": why, "relances cette nuit": 0},
                             expected="le flux relu, au moins une offre retenue", rollback="rien à défaire : une relecture",
                             run=lambda key=key: self.tools.retry_source(key, self.cid),
                             verify=lambda res: (sources.failed(res) is False, brief(res)))
                if a["status"] == "verified":
                    per[key], bad = json.loads(a["result"]), False
            failures = sources.record_night(self.s, key, bad, now)
            if bad and failures >= sources.FAIL_NIGHTS:
                self.act("disable_source", key, f"{failures} nuits ratées de suite ({CAUSE[why]}) : on cesse de la solliciter",
                         inputs={"last_night": brief(stat), "failures": failures}, preconditions={"failures": f">= {sources.FAIL_NIGHTS}"},
                         expected="la source n'est plus lue ; son flux relu tous les 3 jours dira s'il se lit de nouveau",
                         rollback=f"deals.py sources enable {key}",
                         run=lambda key=key, n=failures, w=why: self.tools.disable_source(key, f"agent : {n} nuits ratées ({CAUSE[w]})"),
                         verify=lambda res, key=key: (sources.status(self.s, key) == "disabled", res))
        self._probe(now)
        self._quarantine(night_start, now)
        return {**(collect or {}), "retailers": per}

    def _probe(self, now):
        for src in self.s.q("SELECT * FROM sources WHERE status='disabled' AND reason LIKE 'agent%' ORDER BY key"):
            key = src["key"]
            if src["last_run"] and now - src["last_run"] < PROBE_S - 3600:
                continue
            a = self.act("probe_source", key, f"mise de côté ({src['reason']}) : son flux relu, pour savoir s'il se lit de nouveau",
                         expected="le flux relu, rien d'écrit", rollback="rien à défaire : une lecture",
                         run=lambda key=key: self.tools.probe_source(key), verify=lambda res: (True, None))
            self.s.x("UPDATE sources SET last_run=? WHERE key=?", (now, key))
            res = json.loads(a["result"] or "{}")
            if res.get("readable"):
                self.act("enable_source", key, "le flux se lit de nouveau : la source peut reprendre", inputs=res,
                         expected="la source relue dès la nuit suivante", rollback=f"deals.py sources disable {key}",
                         key=f"enable_source:{key}:{a['id']}")

    def _quarantine(self, night_start, now):
        hold, confirm, release = quarantine.review(self.s, night_start, self.day)
        held = lambda oid: bool(self.s.q("SELECT 1 FROM quarantine WHERE offer_id=? AND status='held'", (oid,), one=True))
        for r in hold:
            self.act("quarantine_offer", f"offre {r['offer_id']}", f"{r['merchant']} · {r['title']} : {euros(r['price'])} relu, "
                     f"{euros(r['usual'])} d'habitude", inputs=dict(r), preconditions={"règle": quarantine.RULE},
                     expected="l'offre n'est plus publiée ; le flux des nuits suivantes dira si le prix tient",
                     rollback=f"deals.py quarantine release {r['offer_id']}", key=f"quarantine_offer:{r['offer_id']}:{r['price']}:{self.day}",
                     run=lambda r=r: quarantine.hold(self.s, r, now, self.day), verify=lambda res, r=r: (held(r["offer_id"]), None))
        for r in confirm:
            self.act("confirm_offer", f"offre {r['offer_id']}", f"{r['merchant']} · {r['title']} : relu au même prix "
                     f"({euros(r['price'])}), une nuit de plus", inputs=dict(r),
                     run=lambda r=r: quarantine.confirm(self.s, r["offer_id"], self.day))
        for r in release:
            self.act("release_offer", f"offre {r['offer_id']}", f"{r['merchant']} · {r['title']} : {r['why']} ({euros(r['price'])})",
                     inputs=dict(r), expected="l'offre est de nouveau publiée",
                     run=lambda r=r: {"rejected": quarantine.release(self.s, r["offer_id"], r["why"], now, self.day)},
                     verify=lambda res, r=r: (not held(r["offer_id"]), res))

    def after_publish(self, published):
        """La garde a relâché la publication (deux nuits retenue sans décision) : on le dit, preuves à l'appui."""
        ev = (published or {}).get("unguarded")
        if ev:
            self.act("release_publication", "catalogue", f"retenue deux nuits sans décision, le catalogue de la veille vieillissait : "
                     f"publié avec {ev['after']} produits et {ev['offers_after']} offres (au lieu de {ev['before']} et "
                     f"{ev['offers_before']})", inputs=ev, expected="un catalogue aux prix frais, plus petit",
                     rollback="corriger la cause puis deals.py publish", run=lambda: ev)

    # ------------------------------------------------------------ après la nuit : incidents, conseils, décisions
    def after_night(self, found):
        """Des constats aux incidents (ouverts, suivis, résolus) et, pour chacun, ce qu'on fait ou propose. → incidents ouverts."""
        now, seen = self.clock(), set()
        for f in found:
            seen.add((f["kind"], f["entity"]))
            inc = self.s.q("SELECT * FROM incidents WHERE status='open' AND kind=? AND entity=?", (f["kind"], f["entity"]), one=True)
            ev = json.dumps(f["evidence"], ensure_ascii=False, default=str)
            if inc:
                again = int(utc_day(inc["last_seen"]).isoformat() != self.day)
                worse = f["severity"] if SEVERITY[f["severity"]] > SEVERITY[inc["severity"]] else inc["severity"]
                self.s.x("UPDATE incidents SET last_seen=?, nights=nights+?, severity=?, evidence=?, "
                         "escalated=CASE WHEN ?!=severity THEN 0 ELSE escalated END WHERE id=?", (now, again, worse, ev, worse, inc["id"]))
                iid = inc["id"]
            else:
                iid = self.s.x("INSERT INTO incidents(kind, entity, severity, opened_at, last_seen, evidence, runbook, cid) "
                               "VALUES (?,?,?,?,?,?,?,?)", (f["kind"], f["entity"], f["severity"], now, now, ev, f["runbook"], self.cid))
                self.ops.event("info" if f["severity"] == "info" else "warning", "health", f["kind"], f["entity"], self.cid,
                               incident_id=iid, grade=f["severity"], evidence=f["evidence"])
            self._advise(f, iid)
        disabled = {r["key"] for r in self.s.q("SELECT key FROM sources WHERE status='disabled'")}
        for inc in self.s.q("SELECT * FROM incidents WHERE status='open'"):
            if (inc["kind"], inc["entity"]) in seen or (inc["kind"].startswith("source_") and inc["entity"] in disabled):
                continue                                     # une source mise de côté reste un incident ouvert
            with self.s.tx() as c:
                c.execute("UPDATE incidents SET status='resolved', resolved_at=? WHERE id=?", (now, inc["id"]))
                c.execute("UPDATE actions SET status='expired' WHERE incident_id=? AND status='proposed'", (inc["id"],))
            self.ops.event("info", "health", "resolved", inc["entity"], self.cid, incident_id=inc["id"], incident=inc["kind"])
        return self.s.q("SELECT * FROM incidents WHERE status='open' ORDER BY id")

    def _advise(self, f, iid):
        e, k, ev = f["entity"], f["kind"], f["evidence"]
        once = lambda action: f"{action}:{e}:{iid}"
        if k in ("source_layout", "suspect_prices"):
            why = "plus de prix barré dans le flux" if k == "source_layout" else f"{ev['held']} prix suspects sur {ev['pages']} offres"
            self.act("review_rules", e, f"{why} : le flux a sans doute changé, sa correspondance doit suivre", incident=iid,
                     inputs={"commands": [f"deals.py probe --source {e}", f"deals.py batches --source {e}", f"deals.py replay {e}"]},
                     key=once("review_rules"))
        elif k == "catalog_held":
            self.act("hold_publication", "catalogue", f"le nouveau catalogue passait de {ev['before']} à {ev['after']} produits et de "
                     f"{ev['offers_before']} à {ev['offers_after']} offres : celui de la veille reste en ligne", incident=iid, inputs=ev,
                     expected="le catalogue de la veille reste en ligne (au plus 3 jours : ses prix vieillissent)",
                     rollback="publier malgré la garde (décision à prendre) ou corriger la cause", run=lambda: ev,
                     verify=lambda res: (self.s.q("SELECT COUNT(*) n FROM catalog", one=True)["n"] == ev["before"], None))
            self.act("force_publication", "catalogue", f"publier quand même ({ev['after']} produits, {ev['offers_after']} offres), si "
                     "la baisse est voulue (enseigne retirée, partenaire en moins)", incident=iid, inputs=ev,
                     expected=f"{ev['after']} produits et {ev['offers_after']} offres publiés",
                     rollback="deals.py publish une fois la cause corrigée", key=once("force_publication"))
            self.act("check_partners", "catalogue", "une baisse pareille vient souvent du fichier des partenaires ou d'une source "
                     "à l'arrêt", incident=iid, inputs={"commands": ["deals.py sources", "deals.py partners"]}, key=once("check_partners"))
        elif k == "catalog_small":
            self.act("check_partners", "catalogue", f"{ev['offers']} offres publiées pour {ev['reference']:.0f} d'habitude "
                     "(sources mises de côté exclues)",
                     incident=iid, inputs={"commands": ["deals.py sources", "deals.py partners"]}, key=once("check_partners"))
        elif k == "mission_mail":
            self.act("check_mail", "smtp", f"{ev['failed']} e-mail(s) de mission non partis : ils repartiront la nuit suivante",
                     incident=iid, inputs={"settings": ["DEALS_SMTP_HOST", "DEALS_SMTP_PORT", "DEALS_SMTP_TLS"]}, key=once("check_mail"))
        elif k == "mass_mail":
            self.act("mass_notification", "missions", f"{ev['held']} personnes à prévenir cette nuit, bien plus que d'habitude : "
                     "rien n'est parti", incident=iid, inputs=ev, expected=f"{ev['held']} e-mails envoyés",
                     rollback="aucun : un e-mail envoyé ne se reprend pas", key=once("mass_notification"))
        elif k == "clicks_drop":
            self.act("check_tracking", "clics", f"{ev['last_day']} clics en 24 h pour {ev['median_7d']:.0f} d'habitude", incident=iid,
                     inputs={"route": "/api/r/out/<offre>", "commands": ["deals.py metrics"]}, key=once("check_tracking"))

    # ------------------------------------------------------------ gestes humains
    def approve(self, action_id, who):
        """Exécute une proposition en attente ; les autres propositions pour la même chose deviennent caduques."""
        a = self.s.q("SELECT * FROM actions WHERE id=? AND status='proposed'", (action_id,), one=True)
        if a is None:
            raise ValueError(f"aucune décision en attente sous le n° {action_id}")
        run = {"enable_source": lambda: self.tools.enable_source(a["entity"]), "force_publication": self.tools.force_publication,
               "mass_notification": self.tools.send_missions}[a["action"]]
        try:
            result, status = run(), "executed"
        except Exception as e:
            result, status = {"error": type(e).__name__, "message": str(e)[:200]}, "failed"
        with self.s.tx() as c:
            c.execute("UPDATE actions SET status=?, result=?, decided_by=?, decided_at=? WHERE id=?",
                      (status, _j(result), who, self.clock(), action_id))
            c.execute("UPDATE actions SET status='expired' WHERE action=? AND entity IS ? AND status='proposed'", (a["action"], a["entity"]))
        self.ops.event("warning", "operator", "approve", a["entity"], self.cid, action_id=action_id, action=a["action"],
                       status=status, by=who)
        return self.s.q("SELECT * FROM actions WHERE id=?", (action_id,), one=True)

    def reject(self, action_id, who):
        a = self.s.q("SELECT * FROM actions WHERE id=? AND status='proposed'", (action_id,), one=True)
        if a is None:
            raise ValueError(f"aucune décision en attente sous le n° {action_id}")
        self.s.x("UPDATE actions SET status='rejected', decided_by=?, decided_at=? WHERE id=?", (who, self.clock(), action_id))
        self.ops.event("info", "operator", "reject", a["entity"], self.cid, action_id=action_id, action=a["action"], by=who)
        return self.s.q("SELECT * FROM actions WHERE id=?", (action_id,), one=True)

    def manual(self, action, entity, who, justification, run, rollback=None):
        """Un geste d'un responsable depuis la ligne de commande (reprendre ou mettre de côté une source, libérer un prix) :
        exécuté et journalisé comme les actions de l'agent ; les propositions en attente pour la même chose deviennent caduques."""
        now = self.clock()
        result = run()
        aid = self.s.x("INSERT INTO actions(at, actor, action, entity, policy, status, justification, idempotency_key, result, "
                       "rollback_plan, decided_by, decided_at, cid) VALUES (?,?,?,?,?,'executed',?,?,?,?,?,?,?)",
                       (now, who, action, entity, POLICY.get(action, "approval"), justification, f"{action}:{entity}:{who}:{now}",
                        _j(result), rollback, who, now, self.cid))
        self.s.x("UPDATE actions SET status='expired' WHERE action=? AND entity IS ? AND status='proposed'", (action, entity))
        self.ops.event("warning", "operator", action, entity, self.cid, action_id=aid, by=who)
        return self.s.q("SELECT * FROM actions WHERE id=?", (aid,), one=True)

    # ------------------------------------------------------------ prévenir le responsable
    def escalate(self, outbox, sender):
        """Écrit au responsable s'il y a lieu → le message envoyé, ou None. Échec d'envoi : retenté la nuit suivante."""
        if not self.operator:
            return None
        open_ = self.s.q("SELECT * FROM incidents WHERE status='open' ORDER BY id")
        due = [i for i in open_ if urgent(i)]
        fresh = [i for i in due if not i["escalated"]]
        settled = [i for i in self.s.q("SELECT * FROM incidents WHERE status='resolved' AND escalated IN (0, 1) AND resolved_at>=? "
                                       "ORDER BY id", (self.clock() - 7 * 86400,)) if i["escalated"] or urgent(i)]
        acts = self.s.q("SELECT * FROM actions WHERE notified=0 AND ((policy='alert' AND status IN ('verified', 'unverified', 'failed')) "
                        "OR (policy='approval' AND status='proposed') OR (policy='auto' AND status='failed')) ORDER BY id")
        if not (fresh or settled or acts):
            return None
        msg = digest(self.s, self.day, sender, self.operator, settled)
        try:
            outbox.send_mail(self.operator, msg)
        except Exception as e:                               # SMTP indisponible (errors.Unavailable) ou autre
            self.ops.event("error", "agent", "escalation_failed", None, self.cid, error=type(e).__name__,
                           reason="e-mail au responsable non parti : retenté la nuit suivante")
            return None
        with self.s.tx() as c:
            c.executemany("UPDATE incidents SET escalated=1 WHERE id=?", [(i["id"],) for i in due])
            c.executemany("UPDATE incidents SET escalated=2 WHERE id=?", [(i["id"],) for i in settled])
            c.execute("UPDATE actions SET notified=1 WHERE notified=0")
        self.ops.event("info", "agent", "escalated", None, self.cid, subject=msg["Subject"], incidents=len(due), actions=len(acts))
        return msg


def _j(v):
    return None if v is None else json.dumps(v, ensure_ascii=False, default=str)


def urgent(inc):
    """Un incident qui vaut un e-mail : critique ; sérieux dès la première nuit s'il ne peut pas être passager, sinon s'il dure."""
    return inc["severity"] == "critical" or (inc["severity"] == "warning" and (inc["kind"] in IMMEDIATE or inc["nights"] >= 2))


SUBJECT = {"catalog_held": "catalogue", "catalog_small": "catalogue", "freshness": "catalogue", "mission_mail": "e-mails",
           "mail_quota": "e-mails", "mass_mail": "e-mails", "clicks_drop": "clics"}


def names(store):
    """Le nom à montrer pour une entité : l'enseigne d'une source, sinon l'entité telle quelle."""
    by = {r["key"]: r["name"] for r in store.q("SELECT key, name FROM sources")}
    return lambda e, kind=None: by.get(e) or e or SUBJECT.get(kind, "plateforme")


def describe(store, inc, who=None):
    """Une ligne lisible pour un incident : gravité, entité, quoi, depuis quand, état de la source."""
    who = who or names(store)
    off = inc["kind"].startswith("source_") and sources.status(store, inc["entity"]) == "disabled"
    nights = f" · {inc['nights']} nuits" if inc["nights"] > 1 else ""
    grade = {"critical": "CRITIQUE", "warning": "ATTENTION", "info": "info"}[inc["severity"]]
    cause = json.loads(inc["evidence"] or "{}").get("explained_by")
    return (f"{grade} · {who(inc['entity'], inc['kind'])} · {SAY[inc['kind']]}{nights}{' · mise de côté' if off else ''}"
            f"{' · en cause : ' + ', '.join(who(k) for k in cause) if cause else ''}")


def digest(store, day, sender, to, settled=()):
    """L'e-mail au responsable : ce qui demande une décision, les incidents ouverts et les conseils, ce qui a été fait sans
    lui, ce qui est rentré dans l'ordre (settled : incidents résolus dont il n'a pas encore su la fin, même ceux qu'un envoi
    en panne lui a cachés), quelques chiffres. Aucune adresse d'utilisateur."""
    who = names(store)
    open_ = store.q("SELECT * FROM incidents WHERE status='open' ORDER BY severity='critical' DESC, id")
    proposed = store.q("SELECT * FROM actions WHERE status='proposed' ORDER BY id")
    advice = {}
    for a in store.q("SELECT * FROM actions WHERE policy='recommend' AND status='recommended' ORDER BY id"):
        advice.setdefault(a["incident_id"], []).append(a)
    done = [a for a in store.q("SELECT * FROM actions WHERE notified=0 AND policy IN ('auto', 'alert') AND action!='confirm_offer' "
                               "ORDER BY id") if a["action"] != "probe_source" or json.loads(a["result"] or "{}").get("readable")]
    crit = any(i["severity"] == "critical" for i in open_)
    lines = [f"Nuit du {day} — état : {'critique' if crit else 'dégradé' if open_ else 'normal'}", ""]
    if proposed:
        lines += ["À DÉCIDER"]
        for a in proposed:
            lines += [f"- [{a['id']}] {LABEL[a['action']]} · {who(a['entity'])} : {a['justification']}.",
                      f"  deals.py approve {a['id']}   (ou : deals.py reject {a['id']})"]
        lines.append("")
    if open_:
        lines += ["INCIDENTS OUVERTS"]
        for i in open_:
            lines += [f"- {describe(store, i, who)}", f"  fiche : docs/RUNBOOK.md#{i['runbook']}"]
            for a in advice.get(i["id"], []):
                cmds = (json.loads(a["inputs"] or "{}").get("commands") or [])[:2]
                lines.append(f"  conseil : {LABEL[a['action']]} — {a['justification']}{' — ' + ' ; '.join(cmds) if cmds else ''}")
        lines.append("")
    if done:
        lines += ["FAIT SANS VOUS (depuis le dernier e-mail)"]
        for a in done[:DIGEST_DONE]:
            lines.append(f"- {who(a['entity'])} · {LABEL[a['action']]} — {a['justification']}{outcome(a)}"
                         f"{ {'verified': '', 'unverified': ' (sans effet)'}.get(a['status'], ' (ÉCHEC : à regarder)') }")
            if a["policy"] == "alert" and a["rollback_plan"]:
                lines.append(f"  retour arrière : {a['rollback_plan']}")
        if len(done) > DIGEST_DONE:
            lines.append(f"- … et {len(done) - DIGEST_DONE} autres : deals.py actions")
        lines.append("")
    if settled:
        lines += ["RENTRÉ DANS L'ORDRE"] + [f"- {who(i['entity'], i['kind'])} · {SAY[i['kind']]}"
                                            f"{' (' + str(i['nights']) + ' nuits)' if i['nights'] > 1 else ''}" for i in settled] + [""]
    n = store.q("SELECT COUNT(*) n FROM catalog", one=True)["n"]
    q = len(quarantine.held(store))
    lines.append(f"Catalogue : {n} produits · {q} offre{'s' if q > 1 else ''} en quarantaine · état complet : deals.py status")
    head = (f"{len(proposed)} décision{'s' if len(proposed) > 1 else ''} à prendre" if proposed else
            f"{len(open_)} incident{'s' if len(open_) > 1 else ''} ouvert{'s' if len(open_) > 1 else ''}" if open_ else
            "tout est rentré dans l'ordre")
    m = EmailMessage()
    m["Subject"], m["From"], m["To"] = f"Promo Central · nuit du {day} : {head}", sender, to
    m.set_content("\n".join(lines) + "\n")
    return m


def outcome(a):
    """Ce que l'action a donné, quand la justification ne le dit pas (sonde du flux)."""
    if a["action"] != "probe_source" or not a["result"]:
        return ""
    res = json.loads(a["result"])
    return " → se lit de nouveau" if res.get("readable") else f" → toujours illisible ({res.get('status') or res.get('why')})"


def journal(store, cid):
    """La section « Agent » du rapport du matin : ce qui a été fait ou proposé cette nuit, les incidents ouverts."""
    who = names(store)
    acts = [a for a in store.q("SELECT * FROM actions WHERE cid=? ORDER BY id", (cid,)) if a["action"] != "confirm_offer"]
    lines = [f"- {LABEL[a['action']]} · {who(a['entity'])} · {STATUS[a['status']]} — {a['justification']}{outcome(a)}" for a in acts]
    lines += [f"- incident : {describe(store, i, who)} (docs/RUNBOOK.md#{i['runbook']})"
              for i in store.q("SELECT * FROM incidents WHERE status='open' ORDER BY id")]
    return lines or ["Rien à signaler : aucune action, aucun incident ouvert."]
