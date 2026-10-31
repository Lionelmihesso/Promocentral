"""Ingestion : ce que les enseignes déclarent de leurs offres, lu, tracé, contrôlé, puis remis au marché (market.py).

Deux sortes de sources, une seule sortie :
  feed   le flux produits de l'enseigne (programme d'affiliation, export partenaire) : CSV, TSV, XML, JSON ou JSONL,
         compressé ou non, lu d'un bloc (feeds.py) ;
  site   ses fiches, lues une à une (pages/ : plans de site, robots.txt, extraction) : le dernier recours, pour une
         enseigne sans flux.
La sortie est la même : une offre normalisée (contract.py), contrôlée puis écrite par market.py, le seul écrivain des
produits, des offres et des prix. Chaque lecture laisse un lot (batches.py : quoi, quand, combien, empreinte, fichier
brut gardé) ; un lot se rejoue. Le registre (registry.py) dit quelles sources existent et comment les lire ; le
collecteur (collector.py) les lit toutes, la nuit, derrière une seule interface.
"""
