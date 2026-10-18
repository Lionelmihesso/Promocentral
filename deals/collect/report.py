"""Bilan de la passe de nuit et rapport du matin (reports/AAAA-MM-JJ.md et .json).

Par enseigne : pages relues, inchangées (304), prix changés, bloquées, disparues, sans prix, erreurs, hors catalogue,
taux de prix barré lu, réussite. Alertes : réussite sous 80 %, passe interrompue (coupe-circuit), budget atteint,
taux de prix barré en chute (la page a sans doute changé). Plus fortes baisses de la nuit.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

from .retailers import BREAKER, KEEP_THRESHOLD


def previous_retailers(store, day):
    row = store.q("SELECT stats FROM runs WHERE day<? AND stats IS NOT NULL ORDER BY id DESC LIMIT 1", (day.isoformat(),), one=True)
    return json.loads(row["stats"])["retailers"] if row else {}


def summarize(market, day, results, names, interrupted=None, not_read=None, confirmed=0, previous=None):
    interrupted, not_read, previous = interrupted or {}, not_read or {}, previous or {}
    per = defaultdict(Counter)
    for r in results:
        c = per[r["retailer"]]
        c[r["status"]] += 1
        c["changed"] += r.get("outcome") == "changed"
        c["with_was"] += r["status"] == "ok" and bool(r.get("was"))
    retailers = {}
    for k in set(per) | set(interrupted) | set(not_read):
        c = per[k]
        total = sum(v for s, v in c.items() if s not in ("changed", "with_was"))
        good = c["ok"] + c["not_modified"]
        was_rate = round(c["with_was"] / c["ok"], 3) if c["ok"] else None
        before = (previous.get(k) or {}).get("was_rate")
        retailers[k] = {"name": names.get(k, k), "pages": total, "ok": c["ok"], "unchanged_304": c["not_modified"], "changed": c["changed"],
                        "blocked": c["blocked"], "gone": c["gone"], "no_price": c["no_price"], "errors": c["error"] + c["rate_limited"],
                        "out_of_scope": c["out_of_scope"], "was_rate": was_rate,
                        "was_drop": bool(before and before >= 0.10 and was_rate is not None and c["ok"] >= 10 and was_rate < before * 0.3),
                        "interrupted": interrupted.get(k, 0), "not_read": not_read.get(k, 0),
                        "success": round(good / total, 3) if total else None, "alert": bool(total) and good / total < KEEP_THRESHOLD}
    drops = []
    for r in results:
        if r.get("outcome") != "changed":
            continue
        last = market.last_prices(r["offer_id"])
        if len(last) == 2 and last[0]["price"] < last[1]["price"]:
            o = market.s.q("SELECT o.url, p.title, p.brand FROM offers o LEFT JOIN products p ON p.id=o.product_id WHERE o.id=?",
                           (r["offer_id"],), one=True)
            drops.append({"title": o["title"], "brand": o["brand"], "retailer": names.get(r["retailer"], r["retailer"]),
                          "before": last[1]["price"], "after": last[0]["price"], "drop": round(1 - last[0]["price"] / last[1]["price"], 3),
                          "url": o["url"]})
    drops.sort(key=lambda d: -d["drop"])
    return {"day": day.isoformat(), "offers": len(results), "retailers": retailers, "price_drops": drops[:30], "confirmed_suspects": confirmed,
            "products": market.s.q("SELECT COUNT(*) n FROM products", one=True)["n"],
            "to_review": market.s.q("SELECT COUNT(*) n FROM products WHERE needs_review=1", one=True)["n"]}


def euros(v):
    return f"{v:,.2f} €".replace(",", " ").replace(".", ",")


def write(stats, report_dir):
    """Rapport du matin ; une relance le même jour n'écrase pas le rapport précédent. → nom du rapport."""
    d = Path(report_dir)
    d.mkdir(parents=True, exist_ok=True)
    s = stats
    lines = [f"# Collecte du {s['day']}", "", f"{s['offers']} pages relues · {s['products']} produits · {s['to_review']} à vérifier", "",
             "| Enseigne | Pages | Lues | Inchangées (304) | Prix changés | Bloquées | Disparues | Sans prix | Erreurs | Prix barré lu | Réussite |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    pct = lambda v: "—" if v is None else f"{v * 100:.0f} %"
    for k, r in sorted(s["retailers"].items()):
        lines.append(f"| {'⚠ ' if r['alert'] else ''}{r['name']} | {r['pages']} | {r['ok']} | {r['unchanged_304']} | {r['changed']} | "
                     f"{r['blocked']} | {r['gone']} | {r['no_price']} | {r['errors']} | {pct(r['was_rate'])} | {pct(r['success'])} |")
    if s["price_drops"]:
        lines += ["", "## Plus fortes baisses", ""] + [f"- {x['brand'] or ''} {x['title'] or x['url']} ({x['retailer']}) : "
                                                       f"{euros(x['before'])} → {euros(x['after'])} (−{x['drop'] * 100:.0f} %)" for x in s["price_drops"][:15]]
    notes = []
    for r in s["retailers"].values():
        if r["interrupted"]:
            notes.append(f"⚠ {r['name']} : passe interrompue après {BREAKER} refus de suite ({r['interrupted']} pages non relues).")
        if r["not_read"]:
            notes.append(f"⚠ {r['name']} : budget de nuit atteint ({r['not_read']} pages non relues ce soir).")
        if r["was_drop"]:
            notes.append(f"⚠ {r['name']} : le prix barré n'est presque plus lu ({r['was_rate'] * 100:.0f} % des pages) : "
                         "changement de page probable (python deals.py explain <adresse>).")
    alerts = [r["name"] for r in s["retailers"].values() if r["alert"]]
    if alerts:
        notes.append(f"⚠ Sous le seuil de {KEEP_THRESHOLD * 100:.0f} % : {', '.join(alerts)}. Blocage ou changement de page ? "
                     "(python deals.py diagnose <enseigne>)")
    if notes:
        lines += [""] + notes
    name, k = s["day"], 2
    while (d / f"{name}.md").exists():
        name, k = f"{s['day']}-{k}", k + 1
    (d / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (d / f"{name}.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    return name
