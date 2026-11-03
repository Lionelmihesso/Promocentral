"""Ingestion : ce que les enseignes partenaires déclarent de leurs offres, lu, tracé, contrôlé, puis remis au marché
(market.py).

Une seule sorte de source depuis la v68 : le flux produits de l'enseigne (programme d'affiliation, export partenaire),
en CSV, TSV, XML, JSON ou JSONL, compressé ou non, lu d'un bloc (feeds.py). Les fiches des enseignes ne sont plus lues.
Chaque ligne devient une offre normalisée (contract.py), contrôlée puis écrite par market.py, le seul écrivain des
produits, des offres et des prix. Chaque lecture laisse un lot (batches.py : quoi, quand, combien, empreinte, fichier
brut gardé) ; un lot se rejoue. Le registre (registry.py) dit quelles sources existent et comment les lire ; le
collecteur (collector.py) les lit toutes, la nuit, derrière une seule interface.
"""
