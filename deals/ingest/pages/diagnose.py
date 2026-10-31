"""Mesurer une enseigne avant de la garder : ce qui est lu, ce qui manque, ce qui bloque.

  diagnose → par enseigne : pages lues / avec prix / avec prix barré / EAN / bloquées (et par quelle protection), d'où
             vient chaque donnée → garder (≥ 80 % de pages avec prix) / règle de site à écrire / abandonner
  sample   → pages brutes enregistrées (samples/<enseigne>/) pour régler l'extraction hors ligne sur de vraies pages
"""
import gzip
import json
from collections import Counter
from pathlib import Path

from ..retailers import KEEP_THRESHOLD


def diagnose(crawler, key, urls):
    rows = []
    for u in urls:
        d = crawler.inspect(u)
        ex = d.get("extraction") or {}
        rows.append({"url": u, "status": d["status"], "code": d.get("code"), "page": d.get("page_kind"), "protection": d.get("protection"),
                     "price": ex.get("price"), "was": ex.get("list_price"), "was_method": ex.get("was_method"),
                     "availability": ex.get("availability"), "gtin": ex.get("gtin"), "title": ex.get("title"), "brand": ex.get("brand"),
                     "method": ex.get("method"), "seller": ex.get("seller"), "category": ex.get("category"), "scope": d.get("scope"),
                     "reasons": " ; ".join(d.get("reasons") or []), "ms": d.get("elapsed_ms")})
    n = len(rows) or 1
    rate = lambda f: round(sum(1 for r in rows if f(r)) / n, 3)
    s = {"retailer": key, "pages": len(rows), "read_ok": rate(lambda r: r["status"] == "ok"), "with_price": rate(lambda r: r["price"]),
         "with_was": rate(lambda r: r["was"]), "with_gtin": rate(lambda r: r["gtin"]), "with_brand": rate(lambda r: r["brand"]),
         "availability_known": rate(lambda r: r["availability"] not in (None, "unknown")),
         "blocked": rate(lambda r: r["status"] == "blocked"), "disallowed": rate(lambda r: r["status"] == "disallowed"),
         "gone": rate(lambda r: r["status"] == "gone"), "methods": dict(Counter(r["method"] for r in rows if r["method"])),
         "was_methods": dict(Counter(r["was_method"] for r in rows if r["was_method"])),
         "protections": dict(Counter(r["protection"] for r in rows if r["protection"])),
         "statuses": dict(Counter(r["status"] for r in rows)), "median_ms": sorted(r["ms"] or 0 for r in rows)[len(rows) // 2] if rows else None}
    s["verdict"] = ("garder" if s["with_price"] >= KEEP_THRESHOLD else
                    "abandonner (bloqué)" if s["blocked"] + s["disallowed"] >= 0.5 else
                    "règle de site à écrire" if s["read_ok"] >= KEEP_THRESHOLD else "abandonner")
    return {"summary": s, "rows": rows}


def sample(fetcher, key, urls, out_dir="samples"):
    d = Path(out_dir) / key
    d.mkdir(parents=True, exist_ok=True)
    index = []
    for i, u in enumerate(urls):
        r = fetcher.get(u)
        name = f"{i:03d}.html.gz"
        if r.get("html"):
            (d / name).write_bytes(gzip.compress(r["html"].encode("utf-8")))
        index.append({"file": name if r.get("html") else None, "url": u, "final_url": r.get("final_url"), "status": r["status"],
                      "code": r.get("code"), "protection": r.get("protection")})
    (d / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"retailer": key, "saved": sum(1 for x in index if x["file"]), "pages": len(index), "dir": str(d)}
