"""Registre des sources : les enseignes lues (une par clé de deals/collect/retailers.py, ou de la démo), partenaires ou
non, et leur état d'exploitation, que la nuit et l'agent tiennent à jour.

  active       lue chaque nuit
  degraded     au moins une nuit ratée de suite (failures), toujours lue
  disabled     plus lue : mise de côté par l'agent après FAIL_NIGHTS nuits ratées de suite (anti-robot, panne durable)
               ou par un responsable ; la reprendre est une décision humaine (deals.py sources enable <clé>), que
               l'agent propose quand une page témoin se lit de nouveau

Une nuit est ratée quand moins de 80 % des pages relues donnent un prix, ou que la passe a été interrompue (coupe-circuit).
"""
from .collect.retailers import KEEP_THRESHOLD

FAIL_NIGHTS = 3
STATUSES = ("active", "degraded", "disabled")


def sync(store, retailers, rules, now):
    """Les sources à suivre : enseignes activées dans le code et, si des partenaires sont déclarés, partenaires (une
    source qui ne l'est plus reste au registre, marquée non partenaire, et n'est plus lue). L'état d'exploitation (nuits
    ratées, mise de côté) est gardé d'une nuit à l'autre."""
    with store.tx() as c:
        if rules is not None:
            c.execute("UPDATE sources SET partner=0 WHERE partner=1")
        for key, r in retailers.items():
            if not r.get("enabled") or (rules is not None and key not in rules):
                continue
            c.execute("INSERT INTO sources(key, name, partner, updated_at) VALUES (?,?,?,?) "
                      "ON CONFLICT(key) DO UPDATE SET name=excluded.name, partner=excluded.partner",
                      (key, r["name"], int(rules is not None), now))


def readable(store, keys):
    """Parmi ces clés, celles qu'on lit cette nuit (pas mises de côté), dans l'ordre donné."""
    off = {r["key"] for r in store.q("SELECT key FROM sources WHERE status='disabled'")}
    return [k for k in keys if k not in off]


def failed(stat):
    """Une nuit ratée pour une source, d'après le bilan de la passe (collect/report.py) ; None si rien n'était à relire."""
    if not stat or not (stat.get("pages") or stat.get("interrupted")):
        return None
    return bool(stat.get("interrupted")) or (stat.get("success") is not None and stat["success"] < KEEP_THRESHOLD)


def record_night(store, key, bad, now):
    """Le résultat de la nuit pour une source → le nombre de nuits ratées de suite."""
    row = store.q("SELECT failures, status FROM sources WHERE key=?", (key,), one=True)
    if row is None or bad is None:
        return row["failures"] if row else 0
    failures = row["failures"] + 1 if bad else 0
    status = row["status"] if row["status"] == "disabled" else ("degraded" if failures else "active")
    store.x("UPDATE sources SET failures=?, status=?, last_run=?, last_success=CASE WHEN ? THEN last_success ELSE ? END, "
            "updated_at=? WHERE key=?", (failures, status, now, int(bad), now, now, key))
    return failures


def status(store, key):
    row = store.q("SELECT status FROM sources WHERE key=?", (key,), one=True)
    return row and row["status"]


def set_status(store, key, status, reason, now):
    if status not in STATUSES:
        raise ValueError(f"état inconnu : {status}")
    if not store.q("SELECT 1 FROM sources WHERE key=?", (key,), one=True):
        raise KeyError(key)
    store.x("UPDATE sources SET status=?, reason=?, failures=CASE WHEN ?='active' THEN 0 ELSE failures END, updated_at=? WHERE key=?",
            (status, reason, status, now, key))


def listing(store):
    return store.q("SELECT * FROM sources ORDER BY status='disabled' DESC, failures DESC, key")
