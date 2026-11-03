# Autonomie — une plateforme qui se débrouille la nuit, et qui sait quand demander

La nuit tourne seule. Ce qui est sans risque, elle le fait : relancer un flux en panne passagère, mettre de côté une
source qui échoue trop, relire son flux tous les 3 jours, retenir un prix suspect, garder le catalogue de la veille
quand le nouveau fond. Ce qui engage (reprendre une source, publier malgré la garde, envoyer des e-mails en masse), elle
le propose et attend une décision. Une action interdite serait refusée et journalisée ; il n'y en a plus depuis que
seuls les flux des enseignes sont lus (v68). Tout est journalisé ; le responsable reçoit au plus un e-mail par nuit, et
seulement s'il y a lieu.

Pas de modèle de langage : des règles écrites, versionnées, testées (`tests/test_autonomy.py`) et mesurées sur des pannes
injectées (`python -m bench.autonomy`).

## La boucle de nuit (`deals/night.py`, `deals/agent.py`)

```
 registre des sources ─► collecte ─► AGENT : observer → diagnostiquer → politique → agir → vérifier → journaliser
 (partenaires lisibles)   (flux)      relance (panne passagère) · nuits ratées · mise de côté · flux relu · quarantaine
                                          │
                                          ▼
                          publication (garde) ─► e-mails des missions (garde contre l'envoi massif)
                                          │
                                          ▼
                 contrôles de santé (health.py) ─► incidents ─► conseils, propositions ─► rapport du matin
                                                                                         ─► e-mail au responsable s'il y a lieu
```
Une étape qui casse n'arrête pas les suivantes : l'erreur devient un incident critique. Un identifiant de corrélation
(`nuit-AAAAMMJJTHHMMSS-xxxx`) suit la nuit dans le journal, la passe (`runs`), les actions et les incidents.

## Politiques : qui décide quoi

| Action | Politique | Pourquoi |
|---|---|---|
| Relancer un flux en échec (injoignable, illisible, sans offre), une fois dans la nuit, et vérifier | auto | sans risque : une relecture |
| Relire le flux d'une source mise de côté, tous les 3 jours | auto | une lecture, rien d'écrit ; dit quand la source se lit de nouveau |
| Mettre un prix suspect en quarantaine, le relire, le libérer | auto | règle versionnée ; mieux vaut un prix absent une nuit qu'un prix faux |
| Mettre de côté une source après 3 nuits ratées de suite | alert | on cesse de solliciter un flux qui ne répond pas ; le responsable est prévenu |
| Retenir la publication d'un catalogue qui fond ; la relâcher après deux nuits | alert | celui de la veille reste en ligne, mais ses prix vieillissent |
| Reprendre une source mise de côté | approval | quand son flux se lit de nouveau, l'agent le propose |
| Publier malgré la garde | approval | une baisse voulue (partenaire retiré) ou une erreur de réglage : à trancher |
| Envoyer des e-mails de missions en nombre anormal | approval | un e-mail envoyé ne se reprend pas |
| Revoir la correspondance d'un flux, vérifier SMTP, partenaires, suivi des clics | recommend | réglages ou démarches : conseillés, jamais faits seuls |
| Une action interdite | forbidden | aucune aujourd'hui ; le garde-fou reste (refusée, journalisée). Contourner un anti-robot l'était, quand les fiches étaient lues |

Chaque action garde : acteur, justification, entrées, préconditions, effet attendu, clé d'idempotence (relancer la nuit
ne refait rien), résultat, vérification, plan de retour arrière, corrélation. Une proposition n'est jamais dupliquée ;
elle devient caduque quand son incident se résout ou qu'un responsable a tranché. Les gestes d'un responsable (`approve`,
`reject`, `sources enable|disable`, `quarantine release`) sont journalisés à son nom, de la même façon.

## Règles versionnées

| Règle | Valeur | Où |
|---|---|---|
| Nuit ratée pour une source | flux injoignable, illisible, ou aucune offre retenue | `sources.failed`, `ingest/collector.py` |
| Cause | flux changé (le prix barré disparaît à prix inchangés : moins de 30 % du taux de la veille, qui était d'au moins 10 % ; l'incident dure jusqu'à son retour) · erreurs | `health.cause`, `ingest/report.py` |
| Mise de côté | 3 nuits ratées de suite ; son flux relu tous les 3 jours | `sources.FAIL_NIGHTS`, `agent.PROBE_S` |
| Variation énorme | un prix divisé ou multiplié par deux ou plus n'est enregistré que si le flux de la nuit suivante le redonne | `market.py` |
| Quarantaine (q1) | prix enregistré à moins de 30 % du prix habituel du produit (médiane des jours relevés) ; cru s'il est redonné au même prix les 2 nuits suivantes ; revenu à la normale : libéré, le prix faux écarté des courbes et des verdicts | `quarantine.py` |
| Garde de publication | le nouveau catalogue garde au moins 80 % des produits et des offres publiés (hors sources mises de côté), à partir de 20 ; au plus deux nuits | `publish.py` |
| Contrôles de santé (h4) | catalogue sous 80 % de ses offres habituelles (médiane 7 nuits, par source) · fraîcheur des prix montrés sous 90 % (70 % : critique) · prix suspects ≥ 5 et ≥ 20 % des offres · flux : 20 % de lignes refusées ou plus, moitié moins d'offres que la veille · e-mails en échec · clics sous 30 % de la médiane (≥ 20/jour) | `health.RULES` |
| Envoi massif | plus de max(30, 3 × la médiane des 7 nuits) personnes à prévenir | `health.mass_threshold` |
| E-mail au responsable | décision à prendre · action « alert » exécutée · action automatique en échec · incident critique · incident sérieux dès la première nuit s'il ne peut pas être passager (flux changé, publication retenue, e-mails en échec…), sinon à la deuxième nuit · incident signalé (ou caché par une panne d'envoi) qui se résout | `agent.urgent`, `agent.escalate` |

## États d'un prix

| État | Quand | Ce qu'on en fait |
|---|---|---|
| frais, vérifié | lu cette nuit (moins de 26 h) | publié ; compte dans la fraîcheur du catalogue |
| vieillissant | dernière lecture entre 26 h et 3 jours (source en difficulté, offre absente du flux) | publié ; fait baisser la fraîcheur (contrôle de santé) |
| expiré | pas relu depuis 3 jours | plus publié |
| en attente | variation énorme (÷ 2, × 2 ou plus) lue une nuit | pas enregistré ; enregistré si le flux de la nuit suivante le redonne |
| suspect | enregistré à moins de 30 % du prix habituel | en quarantaine : ni publié ni envoyé ; libéré (erreur écartée) ou cru |
| écarté | suspect revenu à la normale : c'était une erreur | hors courbes et verdicts (`prices.rejected`), gardé pour l'historique |
| source indisponible | source mise de côté | ses prix vieillissent puis expirent ; son flux relu tous les 3 jours |

## L'e-mail du matin (exemple réel, banc de pannes, troisième nuit d'un flux injoignable)

```
Objet : Promo Central · nuit du 2025-11-22 : 1 incident ouvert

Nuit du 2025-11-22 — état : critique

INCIDENTS OUVERTS
- CRITIQUE · Rapido · en échec (erreurs) · 3 nuits · mise de côté
  fiche : docs/RUNBOOK.md#source-en-echec

FAIT SANS VOUS (depuis le dernier e-mail)
- Rapido · relancée — flux en échec (OSError : 503 Service Unavailable) : panne passagère probable, relu une fois (sans effet)
- Rapido · mise de côté — 3 nuits ratées de suite (erreurs) : on cesse de la solliciter
  retour arrière : deals.py sources enable rapido

Catalogue : 127 produits · 0 offre en quarantaine · état complet : deals.py status
```
Quand une décision est à prendre, elle vient en tête (« À DÉCIDER », avec `deals.py approve <n°>`) ; quand un incident
signalé se résout, une rubrique « RENTRÉ DANS L'ORDRE » le dit.

## Journal et centre de commande

- **Journal opérationnel** (`events`) : chaque étape, décision et geste, daté en UTC, avec gravité, composant, entité et
  corrélation ; la même ligne en JSON sur la sortie d'erreur (`DEALS_LOG_JSON=1`, journald). Jamais d'adresse e-mail ni
  de secret (`ops.scrub`) ; l'e-mail au responsable ne contient aucune adresse d'utilisateur.
- **Incidents** : ouverts, suivis nuit après nuit (gravité qui monte, nombre de nuits), résolus quand la cause disparaît ;
  une source mise de côté garde son incident ouvert. Chacun a sa fiche dans `docs/RUNBOOK.md`.
- **Centre de commande** : `deals.py status` (dernière nuit, catalogue, fraîcheur, quarantaine, sources, incidents,
  décisions), `incidents`, `actions`, `events --cid`, `sources`, `quarantine`, `partners`, `approve`, `reject`.
- **Sonde extérieure** : `GET /api/r/health` → 200 (`ok`, `degraded`) ou 503 (`critical` : aucune nuit depuis 36 h,
  dernière nuit en erreur, incident critique). Elle prévient par un autre chemin quand le SMTP ou la nuit elle-même
  tombent.

## Mesures : pannes injectées

Marché simulé de la démo (127 produits, 381 offres, quatre enseignes, une source chacune : son flux), 50 nuits normales,
puis six nuits avec la panne : `python -m bench.autonomy` (v68, les flux seulement). Les mesures d'avant, sur la lecture
des fiches (v53 sans agent, v54 avec), sont dans git : `git show 1582e13:docs/AUTONOMIE.md`.

| Panne (6 nuits) | Ce que fait la plateforme (v68) |
|---|---|
| Flux injoignable durable | relu une fois chaque nuit (sans effet) ; incident, e-mail nuit 2 (une panne d'une nuit peut être passagère) ; mise de côté nuit 3 (e-mail) ; flux relu nuit 6 ; ses offres expirent après 3 jours (381 → 283 offres publiées, sans garde : un départ attendu) |
| Panne passagère (flux injoignable une fois) | relu et vérifié la même nuit : 100 % des offres relues ; ni incident ni e-mail |
| Flux changé (plus de prix barré, prix inchangés) | incident et commandes à lancer dès la nuit 1 (un e-mail) ; ouvert les 6 nuits, sans faux « rentré dans l'ordre » |
| Erreur de prix d'un soir (÷ 10), une mission qui guette | jamais enregistrée (une variation énorme attend la nuit suivante) : ni publiée ni envoyée, aucun e-mail. Redonnée deux nuits : quarantaine, puis libérée et écartée de la courbe (`tests/test_autonomy.py`) |
| SMTP en panne 2 nuits, une mission atteinte | e-mail parti nuit 3, sans doublon ; incident « e-mails des missions en échec » ; le responsable l'apprend au retour du SMTP |
| Fichier des partenaires mal rempli (1 enseigne sur 4) | publication retenue 2 nuits (381 offres gardées), décision proposée, e-mails ; relâchée nuit 3 (98 offres), « catalogue réduit » reste ouvert |

E-mails au responsable sur les six scénarios : 7 en 36 nuits (aucun pour ce qui se règle seul : panne passagère, prix
faux d'un soir). Démo sur 75 nuits ordinaires : aucun incident, aucune action.

## Ce qui reste humain, ou hors de portée

- Les réglages globaux (plafonds d'e-mails, seuils des règles) : conseillés, jamais changés par l'agent.
- Les démarches auprès des enseignes et des réseaux d'affiliation (adhésion, flux, identifiants).
- Corriger la correspondance d'un flux : l'agent dit quoi lancer (`probe`, `batches`, `replay`), il ne l'écrit pas.
- Supprimer des données : jamais. Libérer un prix, reprendre une source, publier malgré la garde : un geste journalisé.
- Le SMTP de la plateforme sert aussi à prévenir le responsable : s'il tombe, la sonde extérieure prend le relais.
