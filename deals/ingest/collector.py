"""Le collecteur : les flux des enseignes partenaires derrière une seule interface. La nuit (night.py) et l'agent
(agent.py) lui demandent de lire les sources, de relancer l'une, d'en sonder une autre.

  nightly(clés, cid, retry) → bilan de la passe (report.summarize : par source, plus fortes baisses), avec sa ligne
                              dans runs ; un lot par source lue (batches.py)
  ingest(clé, cid, file, dry_run, replay) → (bilan de la source, résultats) : un flux lu de bout en bout
  probe_source(clé)         → {readable} : une source mise de côté se lit-elle de nouveau ?

Un flux, de bout en bout : acquérir (https, fichier ; taille plafonnée) → garder le fichier brut et son empreinte →
lire (feeds.records) → normaliser (feeds.normalize) → contrôler (contract.check : rejet motivé, ligne à ligne, sans
arrêter le lot) → une offre par fiche (variantes : la moins chère en stock) → périmètre à la première lecture
(contract.in_scope) → écrire par market.py (un prix au changement seulement ; la quarantaine et la garde de
publication s'appliquent). Rien n'est supprimé : une offre absente du flux vieillit (au bout de 3 jours, plus montrée). Le même fichier relu ne crée ni doublon ni ligne de prix ; un rejeu relit le fichier
gardé du dernier lot, à l'heure de sa lecture.
Une source flux est en échec (sources.failed) quand elle est injoignable, illisible, ou ne donne aucune offre.
"""
import gzip
import json
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

from ..market import Market
from . import batches, contract, feeds
from .report import previous_retailers, summarize

CONNECTOR = "feed/1"
CHUNK = 200                   # offres écrites par transaction
REJECTS_PARTIAL = 0.20        # au-delà de 20 % de lignes refusées (hors périmètre exclu), le lot est « partial »
MAX_BYTES = 500 * 1024 * 1024


def download(spec, max_bytes=MAX_BYTES, user_agent="PromoCentralBot", timeout=120):
    """Les octets du flux d'une source : https://, http:// ou un chemin de fichier (file:// accepté)."""
    url = spec["url"]
    if url.startswith(("http://", "https://")):
        req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "gzip", **spec.get("headers", {})})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(max_bytes + 1)
    else:
        path = Path(url[7:] if url.startswith("file://") else url)
        if path.stat().st_size > max_bytes:
            raise feeds.FeedError(f"flux de {path.stat().st_size} octets, au-delà de la limite de {max_bytes}")
        data = path.read_bytes()
    if len(data) > max_bytes:
        raise feeds.FeedError(f"flux au-delà de la limite de {max_bytes} octets")
    return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data


def _better(a, b):
    """Deux lignes d'un flux pour la même fiche (variantes) : la disponible, puis la moins chère."""
    return (a["availability"] != "in_stock", a["price"]) < (b["availability"] != "in_stock", b["price"])


def _short(why):
    return "sous le seuil de prix" if "sous le seuil" in why else "accessoire" if why == "accessoire" else \
        "hors des familles suivies" if why.startswith("hors des familles") else why


class Collector:
    def __init__(self, store, market, specs, raw_dir="raw", keep_days=batches.KEEP_DAYS, transport=None,
                 clock=None, max_bytes=MAX_BYTES, user_agent="PromoCentralBot"):
        self.s, self.m, self.specs = store, market, specs
        self.raw_dir, self.keep_days, self.max_bytes, self.ua = raw_dir, keep_days, max_bytes, user_agent
        self.transport = transport or (lambda spec: download(spec, self.max_bytes, self.ua))
        self.clock = clock or market.clock

    # ------------------------------------------------------------------ la nuit
    def nightly(self, retailers=None, cid=None, retry=False):
        """La passe : retailers, les clés à lire (None : toutes les sources activées) ; cid, l'identifiant de corrélation de
        la nuit ; retry : relance d'une source par l'agent. Chaque passe laisse une ligne dans runs (état : succeeded,
        partial_success — au moins une source en alerte —, ou retry). → bilan (report.summarize), avec son numéro."""
        keys = [k for k in (self.specs if retailers is None else retailers) if self.specs.get(k, {}).get("enabled")]
        day = self.m.today()
        run = self.s.x("INSERT INTO runs(day, started, cid, status) VALUES (?,?,?,'running')", (day.isoformat(), self.clock(), cid))
        before = previous_retailers(self.s, day)
        results, per = [], {}
        for k in keys:
            stat, res = self.ingest(k, cid=cid)
            per[k], results = stat, results + res
        stats = summarize(self.m, day, results, {k: self.specs[k]["name"] for k in keys}, previous=before)
        for k, stat in per.items():
            stats["retailers"][k] = {**(stats["retailers"].get(k) or {}), **stat}
        status = "retry" if retry else "partial_success" if any(r.get("alert") or r.get("interrupted") for r in stats["retailers"].values()) \
            else "succeeded"
        self.s.x("UPDATE runs SET ended=?, stats=?, status=? WHERE id=?", (self.clock(), json.dumps(stats, ensure_ascii=False), status, run))
        if not retry:
            batches.prune(self.raw_dir, self.keep_days, self.clock())
        return {**stats, "run": run}

    # ------------------------------------------------------------------ un flux
    def ingest(self, key, cid=None, file=None, dry_run=False, replay=None):
        """Un flux lu de bout en bout → (bilan de la source, résultats par offre écrite). replay : le lot dont on relit
        le fichier gardé (le dernier lot de la source) ; dry_run : tout est lu et contrôlé, rien n'est écrit."""
        spec, now = self.specs[key], self.clock()
        mapping = spec.get("mapping")
        if mapping is None:
            raise ValueError(f"{key} : source désactivée ou sans correspondance (DEALS_SOURCES)")
        bid = batches.open(self.s, key, "feed", cid, now, replay["id"] if replay else None)
        trace = {"connector": CONNECTOR}
        known = {r["url"]: r for r in self.s.q("SELECT id, url, product_id FROM offers WHERE retailer=?", (key,))}
        received, refused, rejected, ignored, reasons, chosen, doubles = 0, 0, [], 0, Counter(), {}, 0
        try:
            if replay:
                raw, fetched = batches.read_raw(replay["raw_path"]), replay["fetched_at"] or replay["started_at"]
                trace["raw_path"] = replay["raw_path"]
            else:
                raw, fetched = (Path(file).read_bytes() if file else self.transport(spec)), now
            trace.update(checksum=batches.checksum(raw), bytes=len(raw), fetched_at=fetched)
            if not (dry_run or replay):
                trace["raw_path"] = batches.archive(self.raw_dir, key, bid, raw, now)
            data = feeds.unpack(raw)
            fmt = feeds.sniff(data, mapping.format)
            # une passe, en continu : seules les offres à écrire restent en mémoire (un flux de 500 000 lignes, dont
            # une minorité dans les familles suivies, ne charge pas la machine) ; une erreur de lecture au milieu du
            # fichier fait échouer le lot entier, avant toute écriture
            for n, raw_rec in feeds.records(data, mapping):
                received += 1
                rec, why = contract.check(feeds.normalize(raw_rec, mapping, fmt))
                if why:
                    reasons[why] += 1
                    refused += 1
                    if len(rejected) < batches.MAX_REJECTS:          # un échantillon des refus, gardé avec le lot
                        rejected.append((n, feeds.text(mapping.value(raw_rec, "external_id")), why,
                                         {k: v for k, v in raw_rec.items() if k != "\0folded"}))
                    continue
                o = known.get(rec["url"])
                if not (o and o["product_id"]):
                    out = contract.in_scope(rec)
                    if out:
                        ignored += 1
                        reasons[_short(out)] += 1
                        continue
                prev = chosen.get(rec["url"])
                if prev is None or _better(rec, prev[1]):
                    chosen[rec["url"]] = (n, rec)
                doubles += prev is not None
        except (feeds.FeedError, OSError, urllib.error.URLError, ValueError, TimeoutError) as e:
            error = self._scrub(f"{type(e).__name__} : {e}", spec)
            batches.close(self.s, bid, self.clock(), "failed", {"received": received}, error=error[:300], **trace)
            return ({"name": spec["name"], "kind": "feed", "batch": bid, "pages": 0, "interrupted": 1, "errors": 1,
                     "received": received, "accepted": 0, "rejected": 0, "ignored": 0, "broken": True, "error": error[:300],
                     "success": None, "alert": True}, [])
        todo = [rec for _, rec in chosen.values()]
        if doubles:
            reasons["variante d'une même fiche"] += doubles
            ignored += doubles
        results = [] if dry_run else self._write(key, spec, bid, todo, fetched if replay else None)
        accepted = len(todo) if dry_run else sum(1 for r in results if r["status"] == "ok")
        changed = sum(1 for r in results if r.get("outcome") == "changed")
        scoped = accepted + refused
        broken = accepted == 0
        share = refused / scoped if scoped else 0.0
        status = "dry_run" if dry_run else "partial" if broken or share >= REJECTS_PARTIAL else "succeeded"
        if not dry_run:
            batches.reject(self.s, bid, rejected)
        counts = {"received": received, "accepted": accepted, "changed": changed, "rejected": refused, "ignored": ignored}
        batches.close(self.s, bid, self.clock(), status, counts, reasons=dict(reasons.most_common(12)), **trace)
        prev = batches.previous_accepted(self.s, key, bid)
        return ({"name": spec["name"], "kind": "feed", "batch": bid, "pages": scoped, "ok": accepted, "changed": changed,
                 "received": received, "accepted": accepted, "rejected": refused, "ignored": ignored,
                 "reasons": dict(reasons.most_common(8)), "broken": broken, "interrupted": 0, "errors": 0,
                 "success": round(accepted / scoped, 3) if scoped else None, "alert": broken or share >= REJECTS_PARTIAL,
                 "reject_share": round(share, 3), "previous_accepted": prev,
                 "collapse": bool(prev and accepted < 0.5 * prev)}, results)

    def _write(self, key, spec, bid, recs, at=None):
        market = self.m if at is None else Market(self.s, clock=lambda: at)
        results = []
        for k in range(0, len(recs), CHUNK):
            with self.s.tx():
                for rec in recs[k:k + CHUNK]:
                    oid = market.track(rec["url"], key, spec["name"])
                    o = market.offer(oid)
                    if market.other_product(o, rec):
                        market.set_result(oid, "gone", False, "l'adresse montre un autre produit")
                        results.append({"offer_id": oid, "retailer": key, "status": "gone", "outcome": None})
                        continue
                    outcome = market.record(o, {**rec, "batch_id": bid})
                    market.set_result(oid, "active", True, "; ".join(rec.get("notes") or ()) or None)
                    market.mark(oid, key, rec.get("external_id"), rec.get("tracking_url"), bid)
                    results.append({"offer_id": oid, "retailer": key, "status": "ok", "outcome": outcome,
                                    "was": rec.get("list_price"), "method": rec.get("method")})
        return results

    def replay(self, key, cid=None):
        """Relit le fichier gardé du dernier lot réussi de la source (une correspondance corrigée, une règle revue), à
        l'heure où il avait été lu. Seul le dernier se rejoue (batches.latest) : un fichier plus ancien ferait revenir
        des prix dépassés."""
        last = batches.latest(self.s, key)
        if not last or not last["raw_path"] or not Path(last["raw_path"]).exists():
            raise ValueError(f"{key} : aucun lot récent avec son fichier brut à rejouer")
        return self.ingest(key, cid=cid, replay=last)

    # ------------------------------------------------------------------ l'agent
    def probe_source(self, key):
        spec = self.specs.get(key)
        if spec is None:
            return {"readable": False, "why": "source inconnue"}
        try:
            raw = self.transport(spec)
            n = next(iter(feeds.records(raw, spec["mapping"])), None)
            return {"readable": n is not None, "bytes": len(raw)}
        except (feeds.FeedError, OSError, urllib.error.URLError, ValueError, TimeoutError) as e:
            return {"readable": False, "why": self._scrub(f"{type(e).__name__} : {e}", spec)[:200]}

    @staticmethod
    def _scrub(message, spec):
        """Jamais l'adresse résolue (elle porte les identifiants du réseau) dans un message."""
        url = spec.get("url") or ""
        return message.replace(url, spec.get("url_template") or "<flux>") if url else message

