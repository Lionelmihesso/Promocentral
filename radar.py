"""DEALS — radar personnel : la tâche quotidienne et quelques commandes d'administration.

  python radar.py daily                         plan adaptatif → collecte → signaux → suivis → opportunités → récapitulatifs
  python radar.py user alice --budget 1500      crée un utilisateur
  python radar.py follow alice brand Samsung    suivre une marque (ou : category televiseur)
  python radar.py watch alice <product_id> 1100 [--brand-only] [--min screen_in=55]
  python radar.py feed alice                    ce que verrait l'app : Pour vous / Vous ne cherchiez pas ça / Vous surveillez
Planification : 0 3 * * *  cd /chemin/deals && python3 radar.py daily >> logs/daily.log 2>&1
"""
import argparse
import json
import sys

from collect.pipeline import Collector
from collect.retailers import MIN_INTERVAL_S, USER_AGENT
from listener.core import Listener
from listener.fetch import Fetcher
from radar.engine import Radar


def main(argv=None):
    ap = argparse.ArgumentParser(description="Radar DEALS")
    ap.add_argument("--db", default="deals.sqlite")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("daily").add_argument("--force", action="store_true")
    u = sub.add_parser("user"); u.add_argument("name"); u.add_argument("--budget", type=float)
    f = sub.add_parser("follow"); f.add_argument("name"); f.add_argument("kind", choices=["brand", "category"]); f.add_argument("value")
    w = sub.add_parser("watch"); w.add_argument("name"); w.add_argument("product_id", type=int); w.add_argument("target", type=float)
    w.add_argument("--deadline"); w.add_argument("--no-alternatives", action="store_true"); w.add_argument("--brand-only", action="store_true")
    w.add_argument("--min", action="append", default=[], help="caractéristique minimale, ex. screen_in=55")
    sub.add_parser("feed").add_argument("name")
    a = ap.parse_args(argv)
    with Listener(a.db, Fetcher(user_agent=USER_AGENT, min_interval=MIN_INTERVAL_S), workers=1) as L:
        R = Radar(L)
        if a.cmd == "daily":
            with L.batch():                                   # une transaction par nuit (−37 % de temps mesuré)
                stats = R.run_daily(Collector(L), force=a.force)
            print(json.dumps(stats, ensure_ascii=False, indent=1))
        elif a.cmd == "user":
            print(R.user(a.name, budget_max=a.budget))
        elif a.cmd == "follow":
            R.follow(R.user(a.name), a.kind, a.value); print("ok")
        elif a.cmd == "watch":
            cons = {"brand_only": a.brand_only, "min": {k: float(v) for k, v in (m.split("=", 1) for m in a.min)}}
            print(R.watch(R.user(a.name), a.product_id, a.target, a.deadline, not a.no_alternatives, cons))
        elif a.cmd == "feed":
            print(json.dumps(R.feed(R.user(a.name)), ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
