# Promo Central — les bonnes affaires du jour, au même endroit

Nom de code technique : `deals` (la commande, le paquet Python, les services).

On ouvre l'app pour savoir quelles bonnes affaires existent aujourd'hui, et on va les acheter chez l'enseigne en deux
gestes : la carte, puis « Voir l'offre » (un seul depuis un lien partagé). Un deal est le même pour tout le monde ;
seul l'ordre s'adapte à vos goûts. On cherche comme on parle (« aspirateur balai sans fil sous 300 € ») ou l'on se
laisse guider, une question à la fois, jusqu'à sa sélection ; une recherche se sauvegarde et dit ce qui est nouveau.
Tout se garde sans e-mail ; l'e-mail, facultatif, sert aux nouveautés et à retrouver ses choix ailleurs.

Quatre familles où une remise compte : électroménager, électronique, ameublement, literie. Seules les offres des
enseignes partenaires sont montrées, et chaque clic part par leur lien affilié.

## Comment ça marche

- **La nuit** : les flux produits des enseignes partenaires (CSV, XML Google Shopping, JSON), et eux seuls, sont lus,
  contrôlés ligne à ligne et tracés par lots ; le marché garde les prix au changement ; la publication juge chaque
  remise (réelle, sinon rien), trouve ce qui remplace un produit pour moins cher et écrit le catalogue du jour d'un
  bloc. Un agent de nuit (des règles écrites, pas d'IA) relance, met de côté, retient un prix suspect, et n'écrit au
  responsable que s'il y a lieu.
- **Le jour** : l'app ne lit que le catalogue publié ; rien du catalogue n'est écrit dans le front.
- **Un seul petit serveur** : Python, bibliothèque standard, SQLite ; aucune IA, aucune API payante.

## Commandes

```
python deals.py demo                 l'app sur http://127.0.0.1:8000/ : 75 nuits de marché simulé, 127 produits
python deals.py serve                l'app et /api/r/ (en production derrière Caddy : deploy/)
python deals.py nightly              la nuit : flux → agent → publication → missions → contrôles → rapport
python deals.py status               l'état : dernière nuit, catalogue, sources, incidents, décisions en attente
python deals.py probe|ingest|batches|replay    brancher et suivre le flux d'une enseigne (deploy/README.md § 9)
python deals.py --help               toutes les commandes (détaillées en tête de deals/cli.py)
python -m unittest discover -s tests -t .      les tests
python -m bench.cadre                le cadre de mise en production ; les autres bancs : docs/ARCHITECTURE.md
bash web/build.sh                    reconstruire web/app.html
```

## Où lire la suite

| Sujet | Document |
|---|---|
| Couches, modules, données, la nuit, les règles du produit et où elles vivent, les mesures | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Mise en production : décisions, risques, go/no-go, coût, limites connues | [`docs/PRODUCTION.md`](docs/PRODUCTION.md) |
| Installer et exploiter le serveur, pas à pas | [`deploy/README.md`](deploy/README.md) |
| Que faire pour chaque incident | [`docs/RUNBOOK.md`](docs/RUNBOOK.md) |
| L'agent de nuit : qui décide quoi, pannes injectées | [`docs/AUTONOMIE.md`](docs/AUTONOMIE.md) |
| L'interface, écran par écran | [`docs/UX.md`](docs/UX.md) |
| La Recherche et l'entonnoir | [`docs/RECHERCHE.md`](docs/RECHERCHE.md) |
| L'ontologie de chaque rayon | [`docs/ONTOLOGIE.md`](docs/ONTOLOGIE.md) |
| La personnalisation | [`docs/PERSONNALISATION.md`](docs/PERSONNALISATION.md) |
| Le contrat de l'API `/api/r/` | [`deals/api.py`](deals/api.py) |
| Consignes pour faire évoluer le dépôt | [`CLAUDE.md`](CLAUDE.md) |
| Code et données de tiers | [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) |
