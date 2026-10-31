"""Les lots : chaque lecture d'une source laisse une trace (quoi, quand, combien, empreinte, fichier brut), qui se
consulte (deals.py batches) et se rejoue (deals.py replay).

  open(store, source, kind, cid, now, replay_of=None) → id      un lot qui commence (status running)
  close(store, id, now, status, counts, **trace)                 sa fin : succeeded | partial | failed | dry_run
  reject(store, id, rows)                                        les lignes refusées et leur raison (200 au plus par lot)
  archive(raw_dir, source, id, raw, now) → chemin                le fichier reçu, compressé, gardé KEEP_DAYS jours
  prune(raw_dir, keep_days, now) → fichiers effacés              la rétention
  listing(store, source=None, n=20) ; get(store, id) ; latest(store, source, kind="feed")

Statuts : succeeded (lu, contrôlé, écrit), partial (lu, mais trop de lignes refusées), failed (injoignable ou illisible),
dry_run (lu et contrôlé sans rien écrire). Un rejeu est un lot comme un autre, qui dit de quel lot il rejoue le fichier.
"""
import gzip
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

KEEP_DAYS = 14
MAX_REJECTS = 200
STATUSES = ("running", "succeeded", "partial", "failed", "dry_run")


def checksum(raw):
    return hashlib.sha256(raw).hexdigest()


def open(store, source, kind, cid=None, now=None, replay_of=None):
    return store.x("INSERT INTO batches(source, kind, cid, started_at, status, replay_of) VALUES (?,?,?,?,'running',?)",
                   (source, kind, cid, now if now is not None else time.time(), replay_of))


def close(store, batch_id, now, status, counts=None, **trace):
    if status not in STATUSES:
        raise ValueError(f"statut de lot inconnu : {status}")
    c = counts or {}
    store.x("UPDATE batches SET ended_at=?, status=?, received=?, accepted=?, changed=?, rejected=?, ignored=?, checksum=?, "
            "bytes=?, raw_path=?, connector=?, fetched_at=?, error=?, reasons=? WHERE id=?",
            (now, status, c.get("received", 0), c.get("accepted", 0), c.get("changed", 0), c.get("rejected", 0),
             c.get("ignored", 0), trace.get("checksum"), trace.get("bytes"), trace.get("raw_path"), trace.get("connector"),
             trace.get("fetched_at"), trace.get("error"), json.dumps(trace.get("reasons") or {}, ensure_ascii=False), batch_id))


def reject(store, batch_id, rows):
    """rows : [(rang, identifiant dans le flux, raison, extrait)] ; les MAX_REJECTS premières sont gardées."""
    have = store.q("SELECT COUNT(*) n FROM batch_rejects WHERE batch_id=?", (batch_id,), one=True)["n"]
    keep = rows[:max(0, MAX_REJECTS - have)]
    if keep:
        store.many("INSERT INTO batch_rejects(batch_id, line, external_id, reason, record) VALUES (?,?,?,?,?)",
                   [(batch_id, n, ext, why, json.dumps(rec, ensure_ascii=False, default=str)[:2000]) for n, ext, why, rec in keep])


def archive(raw_dir, source, batch_id, raw, now):
    """Le fichier reçu, tel quel, compressé : <raw_dir>/<source>/<AAAA-MM-JJ>/<lot>.gz. → chemin."""
    day = datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%d")
    d = Path(raw_dir, source, day)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{batch_id}.gz"
    path.write_bytes(raw if raw[:2] == b"\x1f\x8b" else gzip.compress(raw, 6))
    return str(path)


def read_raw(path):
    data = Path(path).read_bytes()
    return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data


def prune(raw_dir, keep_days=KEEP_DAYS, now=None):
    """Efface les fichiers bruts de plus de keep_days jours (le lot reste, son raw_path ne mène plus à rien)."""
    root, gone = Path(raw_dir), []
    if not root.exists():
        return gone
    limit = (now if now is not None else time.time()) - keep_days * 86400
    for f in root.glob("*/*/*.gz"):
        if f.stat().st_mtime < limit:
            f.unlink()
            gone.append(str(f))
    for d in sorted(root.glob("*/*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    return gone


def get(store, batch_id):
    return store.q("SELECT * FROM batches WHERE id=?", (batch_id,), one=True)


def latest(store, source, kind="feed"):
    return store.q("SELECT * FROM batches WHERE source=? AND kind=? AND status IN ('succeeded', 'partial') ORDER BY id DESC LIMIT 1",
                   (source, kind), one=True)


def previous_accepted(store, source, before_id):
    """Les offres acceptées par le dernier lot réussi de la source avant celui-ci (None : pas de lot avant)."""
    r = store.q("SELECT accepted FROM batches WHERE source=? AND id<? AND status IN ('succeeded', 'partial') AND replay_of IS NULL "
                "ORDER BY id DESC LIMIT 1", (source, before_id), one=True)
    return r["accepted"] if r else None


def listing(store, source=None, n=20):
    where, args = (" WHERE source=?", (source,)) if source else ("", ())
    return store.q(f"SELECT * FROM batches{where} ORDER BY id DESC LIMIT ?", (*args, n))
