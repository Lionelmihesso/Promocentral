"""Bilan de la passe de nuit et rapport du matin (reports/AAAA-MM-JJ.md et .json).

Par flux : lignes reçues, offres retenues, prix changés, refusées, hors périmètre, taux de prix barré lu, réussite.
Alertes : flux en échec, 20 % de lignes refusées ou plus, taux de prix barré en chute alors que les prix, eux, n'ont pas
bougé (le flux a sans doute changé ; une fin de promotion fait remonter les prix : ce n'est pas une alerte) ; la chute
constatée garde sa référence (was_ref) les nuits suivantes, jusqu'au retour du prix barré. Plus fortes baisses de la nuit (celles retenues en quarantaine sont signalées). La nuit complète (night.py)
y ajoute ce que l'agent a vu et fait (agent.py).
"""
import json
from collections import Counter, defaultdict
from pathlib import Path


def previous_retailers(store, day):
    row = store.q("SELECT stats FROM runs WHERE day<? AND stats IS NOT NULL AND COALESCE(status, '')!='retry' ORDER BY id DESC LIMIT 1",
                  (day.isoformat(),), one=True)
    return json.loads(row["stats"])["retailers"] if row else {}


def summarize(market, day, results, names, previous=None):
    """Bilan de la passe, d'après les offres écrites (results) : par source, les offres retirées (l'adresse montre un
    autre produit), le taux de prix barré lu et sa chute ; les plus fortes baisses de la nuit. Le collecteur y ajoute le
    bilan de chaque flux (lignes reçues, retenues, refusées…). previous : le bilan par source de la nuit précédente."""
    previous = previous or {}
    per = defaultdict(Counter)
    for r in results:
        c = per[r["retailer"]]
        c[r["status"]] += 1
        c["changed"] += r.get("outcome") == "changed"
        c["with_was"] += r["status"] == "ok" and bool(r.get("was"))
        if r.get("outcome") == "changed" and not r.get("was"):            # prix barré perdu ce soir : prix inchangé ?
            last = market.last_prices(r["offer_id"])
            if len(last) == 2 and last[1]["was"] and not last[0]["was"]:
                c["lost_was"] += 1
                c["lost_was_same"] += abs(last[0]["price"] - last[1]["price"]) <= 0.01 * last[1]["price"]
    retailers = {}
    for k, c in per.items():
        was_rate = round(c["with_was"] / c["ok"], 3) if c["ok"] else None
        prev = previous.get(k) or {}
        ref = prev.get("was_ref")             # une chute déjà constatée : elle dure tant que le taux reste sous 30 % d'avant
        if ref:
            drop = was_rate is not None and c["ok"] >= 10 and was_rate < ref * 0.3
        else:
            ref = prev.get("was_rate")
            drop = bool(ref and ref >= 0.10 and was_rate is not None and c["ok"] >= 10 and was_rate < ref * 0.3
                        and c["lost_was"] and c["lost_was_same"] >= 0.5 * c["lost_was"])
        retailers[k] = {"name": names.get(k, k), "gone": c["gone"], "was_rate": was_rate, "was_drop": drop,
                        **({"was_ref": ref} if drop else {})}
    drops = []
    for r in results:
        if r.get("outcome") != "changed":
            continue
        last = market.last_prices(r["offer_id"])
        if len(last) == 2 and last[0]["price"] < last[1]["price"]:
            o = market.s.q("SELECT o.url, p.title, p.brand FROM offers o LEFT JOIN products p ON p.id=o.product_id WHERE o.id=?",
                           (r["offer_id"],), one=True)
            drops.append({"offer_id": r["offer_id"], "title": o["title"], "brand": o["brand"], "retailer": names.get(r["retailer"], r["retailer"]),
                          "before": last[1]["price"], "after": last[0]["price"], "drop": round(1 - last[0]["price"] / last[1]["price"], 3),
                          "url": o["url"]})
    drops.sort(key=lambda d: -d["drop"])
    return {"day": day.isoformat(), "offers": len(results), "retailers": retailers, "price_drops": drops[:30],
            "products": market.s.q("SELECT COUNT(*) n FROM products", one=True)["n"],
            "to_review": market.s.q("SELECT COUNT(*) n FROM products WHERE needs_review=1", one=True)["n"]}


def euros(v):
    return f"{v:,.2f} €".replace(",", " ").replace(".", ",")


def write(stats, report_dir, agent=None):
    """Rapport du matin ; agent : les lignes de la section « Agent » (night.py) ; une relance le même jour n'écrase pas le
    rapport précédent. → nom du rapport."""
    d = Path(report_dir)
    d.mkdir(parents=True, exist_ok=True)
    s = stats
    lines = [f"# Collecte du {s['day']}", "", f"{s['offers']} offres lues dans les flux · {s['products']} produits · "
             f"{s['to_review']} à vérifier"]
    flows = s["retailers"]
    if flows:
        lines += ["", "| Flux | Lignes reçues | Offres retenues | Prix changés | Refusées | Hors périmètre | Lot |",
                  "|---|---|---|---|---|---|---|"]
        for k, r in sorted(flows.items()):
            lines.append(f"| {'⚠ ' if r.get('alert') else ''}{r['name']} | {r.get('received', 0)} | {r.get('accepted', 0)} | "
                         f"{r.get('changed', 0)} | {r.get('rejected', 0)} | {r.get('ignored', 0)} | {r.get('batch')} |")
    if s["price_drops"]:
        lines += ["", "## Plus fortes baisses", ""] + [f"- {x['brand'] or ''} {x['title'] or x['url']} ({x['retailer']}) : "
                                                       f"{euros(x['before'])} → {euros(x['after'])} (−{x['drop'] * 100:.0f} %)"
                                                       f"{' — retenu : prix suspect, en quarantaine' if x.get('held') else ''}"
                                                       for x in s["price_drops"][:15]]
    notes = []
    for r in flows.values():
        if r.get("broken"):
            notes.append(f"⚠ {r['name']} : flux en échec ({r.get('error') or 'aucune offre retenue'}) : python deals.py batches "
                         f"--source <clé>, puis docs/RUNBOOK.md#source-en-echec.")
        elif r.get("reject_share", 0) >= 0.2:
            why = ", ".join(f"{k} ({v})" for k, v in (r.get("reasons") or {}).items())
            notes.append(f"⚠ {r['name']} : {r['rejected']} lignes refusées ({r['reject_share'] * 100:.0f} %) : {why}.")
        if r.get("was_drop"):
            notes.append(f"⚠ {r['name']} : le prix barré n'est presque plus donné ({r['was_rate'] * 100:.0f} % des offres) : "
                         "la correspondance du flux a sans doute changé (python deals.py probe --source <clé>).")
    if notes:
        lines += [""] + notes
    if agent:
        lines += ["", "## Agent", ""] + agent
    name, k = s["day"], 2
    while (d / f"{name}.md").exists():
        name, k = f"{s['day']}-{k}", k + 1
    (d / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (d / f"{name}.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    return name
