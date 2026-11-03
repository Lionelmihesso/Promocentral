# Mise en production de Promo Central : où en est-on, que reste-t-il

État au 3 novembre 2026 (v68). Le chemin critique n'est plus le code : ce sont les programmes d'affiliation, puis
trois semaines de pré-collecte sur le serveur. L'installation pas à pas est dans [`deploy/README.md`](../deploy/README.md)
(rejouée de bout en bout sur un serveur simulé : l'audit d'octobre, `git show 2ca25aa:docs/AUDIT.md`). L'audit de
départ (J1–3, sur la v24 : mesures de base, cartographie, registre complet des risques, plan par lots) est dans git :
`git show 2ca25aa:docs/PRODUCTION.md`.

## Décisions

| # | Décision | État |
|---|---|---|
| D1 | Programmes d'affiliation et leurs flux | **à obtenir** : Boulanger (Kwanko, flux annoncés), Fnac (Awin, flux XML ou CSV), Darty (Effinity ou Awin, à confirmer), puis Conforama, But, IKEA, Maisons du Monde, La Redoute, Cdiscount ; partir avec 2 à 4 acceptés |
| D2 | Identité | nom affiché **Promo Central** (31 octobre) ; **à fournir** : société éditrice, directeur de la publication, contact, domaine (`DEALS_LEGAL_…`) |
| D3 | Pré-collecte silencieuse avant d'ouvrir | **retenue** (31 octobre) : la nuit tourne sur le serveur, sans public, 3 semaines au moins |
| D4 | Comptes de service | hébergement **OVHcloud VPS** (1er novembre) ; **à ouvrir** : stockage objet pour la copie des sauvegardes (OVHcloud Object Storage), SMTP, sonde extérieure |
| D5 | Page légale en pied de page, et seulement elle (v63) ; v65 : au pied du Profil seulement, avec « Comment ça marche », et plus de mention « enseigne partenaire » près de l'offre (interface minimale) | **faite** (v65) ; à valider : P1-10 |
| D6 | Photos des produits données par les flux (v67) : publiées avec le catalogue ; montrées si `DEALS_PHOTOS=1`, chargées chez l'enseigne (sans référent), illustration sinon ; la page des mentions le dit d'elle-même quand elles sont montrées | **décidée** (3 novembre) : `DEALS_PHOTOS=1` dès que les droits d'usage prévus par chaque programme sont vérifiés ; `0` d'ici là |
| D7 | Les flux seulement (v68) : la lecture des fiches des enseignes est retirée (extraction des pages, robots.txt, anti-robots, page `/robot`, commandes `discover`, `diagnose`, `sample`, `build`, `explain`, `rules`, `estimate`) ; une enseigne sans flux n'est pas lue | **faite** (3 novembre) |

## Ce qui est fait

| Sujet | Preuve |
|---|---|
| Socle des données : plus de fusion de produits sur la ressemblance du titre (EAN, ou marque et référence ; un titre semblable n'est qu'un candidat à revoir), deux EAN jamais fusionnés, une alerte seulement sur une offre en stock | `tests/test_market.py` ; `bench.cadre` : 0 écart P0 |
| Ingestion par flux, la seule depuis la v68 : CSV, XML Google Shopping, JSON ; correspondance des colonnes par source (`deals.py probe`), lots tracés et rejouables, fichier brut gardé, refus motivés ; ajouter une enseigne ne demande aucun code | `tests/test_ingest.py`, `tests/test_flow.py` (de bout en bout, des flux à l'API) ; v68 : la démo publie à l'identique de la v67 (catalogue, offres, prix, lots comparés table par table) |
| Architecture : couches et contrats écrits, frontières vérifiées par un test ; grille « Du flux à l'écran » | `docs/ARCHITECTURE.md` ; `tests/test_architecture.py` |
| Exploitation : versions datées, tests de fumée, retour arrière d'une commande (base restaurée si elle avait été migrée) ; HSTS ; HEAD pour les sondes ; copie chiffrée hors du serveur outillée | `deploy/` ; `tests/test_release.py`, `tests/test_deploy.py` ; le guide rejoué (53 vérifications) |
| Conformité : le nom Promo Central partout, la page « Mentions légales et données personnelles » (l'app ne démarre pas sans elle en production) | parcours e2e 85/85, audit de 92 écrans sans défaut |

## Risques ouverts

| # | Risque | Réponse | Attend |
|---|---|---|---|
| P0-1 | Aucune donnée réelle encore lue : taux de lecture, EAN, prix barrés, disponibilités inconnus par enseigne | Premier flux réel : `probe`, lot à blanc, audit à la main de 20 offres par source et par famille (grille « Du flux à l'écran ») ; seuils fixés sur cet échantillon | D1 |
| P0-2 | Aucun partenaire confirmé | Seules les enseignes de `affiliate.json` sont lues et publiées ; le modèle n'en déclare aucune (vérifié par un test) ; sans partenaire, rien n'ouvre | D1 |
| P0-4 | Mentions légales : la page existe, l'identité manque ; information RGPD à faire relire | `DEALS_LEGAL_…` ; relecture par un juriste | D2 |
| P1-2 | Remises peu confirmées le premier mois (81 % de précision, 18 % confirmées par une preuve sur le marché simulé, `bench.deals_truth`) | Pré-collecte de 3 semaines au moins (D3) : à l'ouverture, l'historique existe (99 % confirmées en régime établi). Règle des annonces de réduction (prix de référence = plus bas des 30 derniers jours, Code de la consommation, art. L112-1-1) à faire valider par un juriste pour la reprise des remises par une plateforme | D3, juriste |
| P1-5 | Sauvegardes sur le même disque que la base | Outillé : `deals-offsite` (restic, chiffré, chaque jour), procédure et essai de restauration dans `deploy/README.md` § 10 ; à activer | D4 |
| P1-6 | Sonde extérieure non branchée | `/api/r/health` (GET ou HEAD) ; 503 = critique | D4 |
| P1-7 | Pas de préproduction | La pré-collecte se fait sur le serveur de production, sans public : mise à jour, retour arrière et restauration s'y répètent avant l'ouverture (`deploy/README.md` § 11, § 12) | serveur |
| P1-9 | E-mails de connexion en indésirables sans SPF, DKIM, DMARC | DNS du domaine selon le fournisseur SMTP ; essai vers 3 messageries | D2, D4 |
| P1-10 | Transparence de l'affiliation depuis la v65 (D5) : « Comment ça marche » et les mentions au pied du Profil seulement, plus de mention près de l'offre. Le Code de la consommation (L111-7 ; D111-6 dans sa version du 9 juillet 2024) demande à une plateforme qui classe des offres une rubrique « directement et aisément accessible à partir de toutes les pages » et, pour chaque résultat classé, à proximité de l'offre, l'information que son classement a été influencé par une relation contractuelle ou une rémunération, quand c'est le cas | Faire trancher par le juriste avant l'ouverture (seules les offres de partenaires sont montrées) ; si une mention est due, elle tient en un mot près du bouton, et le lien sur chaque écran | juriste |
| P2-1 | Frais de livraison : montrés sur la fiche depuis la v67 (« Livraison offerte », leur montant, ou « selon le marchand » si le flux ne les donne pas) ; pas encore dans le prix des cartes ni dans le classement | Prix livré dans les listes : après l'ouverture | — |
| P2-2 | Pas de politique de contenu (CSP) | Par empreinte du script de `app.html`, calculée au build, vérifiée par le parcours e2e | après l'ouverture |
| P2-3 | Aucune limite de débit en lecture | Surveiller ; limite dans Caddy si le trafic le demande | après l'ouverture |
| P2-4 | `App.jsx` d'un seul tenant | Découpage reporté : le front est validé, le parcours e2e le protège | — |
| P2-5 | Manquent la latence et les erreurs de l'API, les erreurs JS, le disque | Dans le journal, puis un tableau de bord | après l'ouverture |

## Périmètre de lancement

| Inclus | Reporté |
|---|---|
| 2 à 4 sources confirmées (D1), par leur flux | les autres enseignes ; une enseigne sans flux n'est pas lue (D7) |
| Les rayons qui passent l'audit de l'échantillon réel, dans les 4 familles | les rayons sous le seuil, jusqu'à correction |
| Catalogue canonique, offres et prix tracés, rapprochement prudent | rapprochement au-delà de l'EAN et de la référence fabricant |
| Le front v63 tel quel | toute refonte ; les photos des produits (décision de front, `docs/UX.md`) |
| Un serveur, versions, retour arrière, sauvegarde locale et hors du serveur, sonde, runbook | PostgreSQL, conteneurs, files de messages |

Le périmètre se règle par les données, pas par le code : un rayon non retenu n'est pas publié, et l'entonnoir s'y
adapte (avec six rayons ou moins, « Quel univers ? » n'est pas posée).

## Le chemin jusqu'à l'ouverture

1. **Serveur** (dès maintenant, sans attendre D1) : `deploy/README.md` § 1 à 8.
2. **Programmes** (D1) : pour chacun, l'adresse du flux et le gabarit du lien de suivi.
3. **Premier flux réel** : `deploy/README.md` § 9 ; audit de 20 offres ; la nuit s'active.
4. **Pré-collecte** (D3), 3 semaines au moins, sans public. Pendant ce temps : la copie hors du serveur et son essai
   de restauration, la sonde, SPF/DKIM/DMARC, une mise à jour et un retour arrière répétés sur le serveur, la relecture
   du juriste.
5. **Go/no-go**, puis ouverture et surveillance renforcée la première semaine.

## Go/no-go

Le serveur : la liste de `deploy/README.md` § 12 (DNS et HTTPS, pare-feu, mentions légales, SMTP, flux et
affiliation, fumée, sauvegardes et restauration, mise à jour et retour arrière, aucun secret dans le dépôt). Et le
produit :
1. Tests, parcours e2e et audit d'accessibilité verts sur la version installée (étiquetée dans git).
2. `python -m bench.cadre` : 0 écart P0 ; les écarts P1 restants acceptés par écrit.
3. Au moins 2 sources partenaires actives, leur lien de suivi vérifié par un clic réel remonté dans le réseau.
4. Audit de l'échantillon réel : 0 prix faux publié ; les rayons publiés listés.
5. Pré-collecte d'au moins 3 semaines : la part des remises confirmées par une preuve, mesurée et acceptée.
6. Note du juriste sur la reprise des remises.
7. Un incident simulé traité avec le runbook ; l'e-mail au responsable reçu.

## Compromis

**Gardé**, parce que ça fonctionne et que c'est vérifié : les flux des programmes, la quarantaine et l'agent de nuit,
le seul écrivain du marché, la publication d'un bloc avec sa garde, SQLite, la bibliothèque standard.

**Retiré en v68**, parce que les flux suffisent et qu'il fallait maintenir ce qui ne servait plus : la lecture des
fiches des enseignes (extraction des pages, robots.txt, anti-robots reconnus, budget de nuit, page `/robot`, et les
commandes pour la régler), les routes que le front n'appelait pas (`/api/r/brand/<nom>`, `/api/r/category/<clé>` : la
recherche les remplace ; `missions/parse`, `missions/preview`). Restent dans la base, inertes, la table `site_rules`
et trois colonnes d'`offers` (`etag`, `last_modified`, `protection`) : les retirer demanderait une migration pour rien.

**Non retenu, le front étant validé** : l'historique des prix et les autres vendeurs sur la fiche (retirés par choix
produit), le découpage d'`App.jsx`, un panneau « Tous les critères » (l'entonnoir le remplace).

**Après l'ouverture** : frais de livraison affichés, CSP, limite de débit, tableau de bord ; rapprochement au-delà de
l'EAN et de la référence ; personnalisation au-delà des préférences explicites et des signaux simples déjà en place.

## Coût de fonctionnement

- Lecture : un fichier par enseigne et par nuit. Publication, alternatives et courbes de 90 jours comprises : ~3 s pour
  3 000 produits (~1 ms par produit, aspirateurs compris, dont l'ontologie relit la catégorie gardée).
- Base : quelques dizaines de Mo par an (seuls les changements de prix sont écrits) ; fichiers bruts des flux gardés
  14 jours.
- Missions de la nuit : ~6 s pour 10 000 missions sur 3 000 produits (~1,6 à 2,2 s une nuit sans changement).
- Serveur : un VPS OVHcloud d'entrée de gamme suffit ; VPS-1 (2 vCore, 4 Go, 40 Go NVMe) affiché **3,81 € HT par
  mois** le 1er novembre 2026 (à confirmer à la commande selon l'engagement), sauvegarde quotidienne de la machine sur
  7 jours comprise. Copie chiffrée des sauvegardes hors du serveur : un bucket OVHcloud Object Storage, facturé au
  volume (quelques Go).
- E-mails (connexion, et missions : au plus un par personne et par nuit) : Brevo gratuit jusqu'à 300 par jour, partagés
  par les deux plafonds (`DEALS_MAILS_PER_DAY` 250, `DEALS_MISSION_MAILS` 50) ; au-delà, une offre payante. Nom de
  domaine : quelques euros par an. Aucun proxy, aucune API payante, aucune IA.

## Limites connues

- Aucun flux réel n'a encore été lu : le connecteur est prouvé sur des flux d'essai (CSV en Windows-1252, XML Google
  Shopping, JSONL compressé) et sur ceux de la démo. Chaque vrai flux reçoit sa correspondance écrite sur un échantillon
  (`probe`), puis un premier lot à blanc (`ingest --dry-run`) ; les noms de colonnes d'un réseau ne s'écrivent pas de
  mémoire.
- Une enseigne sans flux n'est pas lue (v68) : sans programme d'affiliation qui en fournit un, elle n'apparaît pas.
- Un flux changé n'est reconnu que par la disparition du prix barré à prix inchangés ; une colonne de prix qui change
  de sens (centimes, prix mensuel) se voit par les prix suspects et la quarantaine, ou par les lignes refusées.
- Une baisse sans prix barré n'est pas montrée : choix produit et juridique, les règles françaises sur les annonces de
  réduction (prix de référence : le plus bas des 30 derniers jours) sont à valider avant tout affichage.
- Sans e-mail, ce qu'on garde tient à l'appareil et à son cookie : effacer les données du navigateur le perd ; un compte
  invité ne se retrouve pas sur un autre appareil. 100 comptes invités au plus par adresse IP et par heure : un très
  grand réseau derrière une seule adresse (opérateur mobile) pourrait l'atteindre aux heures de pointe.
- Personnalisation : des règles simples sur les rayons et les marques, pas de « ceux qui ont aimé ceci » ni de budget
  appris ; sans compte, les fiches ouvertes ne sont gardées d'une visite à l'autre que si la personne l'accepte
  (Profil), et le témoin est tiré à chaque visite. Le gain mesuré par `bench.profiles` repose sur un modèle de clic :
  le vrai gain se lit sur les témoins en production (`metrics`, `by_variant`).
- Exploitation : l'agent prévient le responsable par le SMTP de la plateforme ; s'il tombe, seule une sonde extérieure
  sur `/api/r/health` le voit (à brancher, `docs/RUNBOOK.md#sonde`). L'agent conseille de revoir la correspondance d'un
  flux qui change ; il ne l'écrit pas.
- Recherches sauvegardées : ce qui est nouveau se voit dans l'app et par e-mail la nuit, pour qui a donné son adresse ;
  pas de notification sur le téléphone (l'app est une page web). Une phrase n'est comprise que dans ce que la lecture
  des offres sait reconnaître (catégories suivies, marques présentes au catalogue, fonctions et tailles connues) ; pas
  de correction des fautes de frappe ni de synonymes appris (une liste écrite, `SLANG`, `deals/query.py`).
- Ontologie : seulement ce que le titre et la catégorie déclarée disent ; des règles écrites à la main, en français
  (« cordless » n'est pas lu). Les bancs ont une vérité et des offres écrites par le même auteur que les règles : la
  lecture sur de vrais flux reste à mesurer, sur un échantillon réel de chaque enseigne (`probe`, `ingest --dry-run`).
- Alternatives : jugées sur ce que disent le titre et les caractéristiques déclarées ; un critère absent des deux
  (puissance d'aspiration, matériaux, finition) n'est pas comparé ; un produit dont le type n'est pas dit n'est comparé
  qu'à ceux qui ne le disent pas non plus.
