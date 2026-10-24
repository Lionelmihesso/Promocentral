"""Journal opérationnel : chaque étape de la nuit, chaque décision de l'agent, chaque geste d'un responsable laisse un
événement daté (UTC) avec sa gravité, son composant, l'entité concernée et l'identifiant de corrélation de la nuit ;
la même ligne part en JSON sur la sortie d'erreur du service (journald) quand on le demande. Jamais d'adresse e-mail,
de jeton ni de secret dans un événement (`scrub`). Lecture : `deals.py events [--cid …]`.
"""
import json
import re
import secrets
import time
from datetime import datetime, timezone

SEVERITIES = ("info", "warning", "error", "critical")
SENSITIVE = re.compile(r"e-?mail|token|password|passwd|secret|session|cookie|smtp_user|smtp_password", re.I)
EMAIL = re.compile(r"[^@\s\"'<>]+@[^@\s\"'<>]+\.[A-Za-z]{2,}")


def scrub(value):
    """Une donnée à journaliser, sans clé sensible ni adresse e-mail (masquée)."""
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if not SENSITIVE.search(str(k))}
    if isinstance(value, (list, tuple)):
        return [scrub(v) for v in value]
    if isinstance(value, str):
        return EMAIL.sub("[adresse masquée]", value)
    return value


def utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class Ops:
    def __init__(self, store, env="dev", stream=None, clock=time.time):
        self.s, self.env, self.stream, self.clock = store, env, stream, clock

    def new_cid(self, kind="nuit"):
        """Identifiant de corrélation : il suit une nuit (ou un geste) d'un bout à l'autre."""
        return f"{kind}-{datetime.fromtimestamp(self.clock(), timezone.utc):%Y%m%dT%H%M%S}-{secrets.token_hex(2)}"

    def event(self, severity, component, kind, entity=None, cid=None, /, **payload):
        """Un événement ; payload : les détails (sans clé sensible ; ils ne remplacent jamais les champs de l'événement)."""
        if severity not in SEVERITIES:
            raise ValueError(f"gravité inconnue : {severity}")
        now, data = self.clock(), scrub(payload)
        eid = self.s.x("INSERT INTO events(at, severity, component, kind, entity, cid, payload) VALUES (?,?,?,?,?,?,?)",
                       (now, severity, component, kind, entity, cid, json.dumps(data, ensure_ascii=False, default=str)))
        if self.stream is not None:
            print(json.dumps({**data, "ts": utc(now), "severity": severity, "service": "deals", "env": self.env,
                              "component": component, "event": kind, "entity": entity, "correlation_id": cid},
                             ensure_ascii=False, default=str), file=self.stream, flush=True)
        return eid

    def recent(self, cid=None, n=50):
        where, args = ("WHERE cid=?", (cid,)) if cid else ("", ())
        rows = self.s.q(f"SELECT * FROM events {where} ORDER BY id DESC LIMIT ?", (*args, n))
        return [{**r, "payload": json.loads(r["payload"] or "{}")} for r in reversed(rows)]
