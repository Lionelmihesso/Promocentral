"""DEALS — commandes d'exploitation.

  python cli.py daily [--force]     la tâche de chaque nuit : plan adaptatif → collecte → similarités (hebdo) → signaux de marché
  python cli.py metrics             clics sortants, comptes, deals du jour, fausses remises écartées
Planification : 0 3 * * *  cd /chemin/deals && python3 cli.py daily >> logs/daily.log 2>&1
"""
import argparse
import json
import sys

from collect.pipeline import Collector
from collect.retailers import MIN_INTERVAL_S, USER_AGENT
from listener.core import Listener
from listener.fetch import Fetcher
from radar.engine import Radar
from radar.shop import Shop


def main(argv=None):
    ap = argparse.ArgumentParser(description="DEALS — exploitation")
    ap.add_argument("--db", default="deals.sqlite")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("daily").add_argument("--force", action="store_true")
    sub.add_parser("metrics")
    a = ap.parse_args(argv)
    with Listener(a.db, Fetcher(user_agent=USER_AGENT, min_interval=MIN_INTERVAL_S), workers=1) as L:
        R = Radar(L)
        if a.cmd == "daily":
            with L.batch():                                   # une transaction par nuit (−37 % de temps mesuré)
                stats = R.run_daily(Collector(L), force=a.force)
            print(json.dumps(stats, ensure_ascii=False, indent=1))
        elif a.cmd == "metrics":
            print(json.dumps(Shop(R).metrics(), ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
