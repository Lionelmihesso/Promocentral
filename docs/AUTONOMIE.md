# Autonomie — une plateforme qui se débrouille la nuit, et qui sait quand demander

La nuit tourne seule. Ce qui est sans risque, elle le fait : relancer une source en panne passagère, mettre de côté une
source qui échoue trop, relire une page témoin, retenir un prix suspect, garder le catalogue de la veille quand le
nouveau fond. Ce qui engage (reprendre une source, publier malgré la garde, envoyer des e-mails en masse), elle le
propose et attend une décision. Ce qui est interdit (contourner un anti-robot), elle ne le fait jamais, et l'écrit.
Tout est journalisé ; le responsable reçoit au plus un e-mail par nuit, et seulement s'il y a lieu.

Pas de modèle de langage : des règles écrites, versionnées, testées (`tests/test_autonomy.py`) et mesurées sur des pannes
injectées (`python -m bench.autonomy`).

## La boucle de nuit (`deals/night.py`, `deals/agent.py`)

```
 registre des sources ─► collecte ─► AGENT : observer → diagnostiquer → politique → agir → vérifier → journaliser
 (partenaires lisibles)   (passe)     relance (panne passagère) · nuits ratées · mise de côté · page témoin · quarantaine
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
| Relancer une source en panne passagère (erreurs, délais), une fois dans la nuit, et vérifier | auto | sans risque ; jamais pour un anti-robot ni un « trop de requêtes » |
| Relire une page témoin d'une source mise de côté, tous les 3 jours | auto | une requête ; dit quand la source se lit de nouveau |
| Mettre un prix suspect en quarantaine, le relire, le libérer | auto | règle versionnée ; mieux vaut un prix absent une nuit qu'un prix faux |
| Mettre de côté une source après 3 nuits ratées de suite | alert | on cesse de solliciter un site qui refuse ; le responsable est prévenu |
| Retenir la publication d'un catalogue qui fond ; la relâcher après deux nuits | alert | celui de la veille reste en ligne, mais ses prix vieillissent |
| Reprendre une source mise de côté | approval | quand la page témoin se lit de nouveau, l'agent le propose |
| Publier malgré la garde | approval | une baisse voulue (partenaire retiré) ou une erreur de réglage : à trancher |
| Envoyer des e-mails de missions en nombre anormal | approval | un e-mail envoyé ne se reprend pas |
| Écrire une règle de lecture, ralentir la lecture, relever le budget, contacter l'enseigne, vérifier SMTP, partenaires, suivi des clics | recommend | réglages globaux ou démarches : conseillés, jamais faits seuls |
| Contourner un anti-robot | forbidden | jamais ; refusé et journalisé (la voie : flux produits ou liste blanche de l'enseigne partenaire) |

Chaque action garde : acteur, justification, entrées, préconditions, effet attendu, clé d'idempotence (relancer la nuit
ne refait rien), résultat, vérification, plan de retour arrière, corrélation. Une proposition n'est jamais dupliquée ;
elle devient caduque quand son incident se résout ou qu'un responsable a tranché. Les gestes d'un responsable (`approve`,
`reject`, `sources enable|disable`, `quarantine release`) sont journalisés à son nom, de la même façon.

## Règles versionnées

| Règle | Valeur | Où |
|---|---|---|
| Nuit ratée pour une source | fiches : moins de 80 % des pages lues avec un prix, ou passe interrompue (5 refus de suite) ; flux : injoignable, illisible, ou aucune offre retenue | `sources.py`, `ingest/retailers.py`, `ingest/collector.py` |
| Cause | anti-robot (≥ 50 % de pages bloquées) · trop de requêtes (≥ 30 % de 429) · page changée (≥ 50 % sans prix, ou prix barré perdu à prix inchangé) · erreurs | `health.cause` |
| Mise de côté | 3 nuits ratées de suite ; page témoin tous les 3 jours | `sources.FAIL_NIGHTS`, `agent.PROBE_S` |
| Quarantaine (q1) | prix à moins de 30 % du prix habituel du produit (médiane des jours relevés) ; cru s'il est relu au même prix les 2 nuits suivantes ; revenu à la normale : libéré, le prix faux écarté des courbes et des verdicts | `quarantine.py` |
| Garde de publication | le nouveau catalogue garde au moins 80 % des produits et des offres publiés (hors sources mises de côté), à partir de 20 ; au plus deux nuits | `publish.py` |
| Contrôles de santé (h2) | catalogue sous 80 % de ses offres habituelles (médiane 7 nuits, par source) · fraîcheur des prix montrés sous 90 % (70 % : critique) · prix suspects ≥ 5 et ≥ 20 % des pages · e-mails en échec · clics sous 30 % de la médiane (≥ 20/jour) | `health.RULES` |
| Envoi massif | plus de max(30, 3 × la médiane des 7 nuits) personnes à prévenir | `health.mass_threshold` |
| E-mail au responsable | décision à prendre · action « alert » exécutée · action automatique en échec · incident critique · incident sérieux dès la première nuit s'il ne peut pas être passager (anti-robot, page changée, publication retenue, e-mails en échec…), sinon à la deuxième nuit · incident signalé (ou caché par une panne d'envoi) qui se résout | `agent.urgent`, `agent.escalate` |

## États d'un prix

| État | Quand | Ce qu'on en fait |
|---|---|---|
| frais, vérifié | lu cette nuit (moins de 26 h) | publié ; compte dans la fraîcheur du catalogue |
| vieillissant | dernière lecture entre 26 h et 3 jours (budget atteint, source en difficulté) | publié ; fait baisser la fraîcheur (contrôle de santé) |
| expiré | pas relu depuis 3 jours | plus publié |
| suspect | relu à moins de 30 % du prix habituel | en quarantaine : ni publié ni envoyé, relu en priorité ; libéré (erreur écartée) ou cru |
| écarté | suspect revenu à la normale : c'était une erreur | hors courbes et verdicts (`prices.rejected`), gardé pour l'historique |
| source indisponible | source mise de côté | ses prix vieillissent puis expirent ; page témoin tous les 3 jours |

## L'e-mail du matin (exemple réel, banc de pannes, troisième nuit d'un anti-robot)

```
Objet : Deals · nuit du 2025-11-22 : 1 incident ouvert

Nuit du 2025-11-22 — état : critique

INCIDENTS OUVERTS
- CRITIQUE · Rapido · bloquée par un anti-robot · 3 nuits · mise de côté
  fiche : docs/RUNBOOK.md#source-bloquee
  conseil : contacter l'enseigne — lui demander son flux produits (via la plateforme d'affiliation) ou l'accès du
  robot (son User-Agent sur liste blanche) — deals.py diagnose rapido

FAIT SANS VOUS (depuis le dernier e-mail)
- Rapido · mise de côté — 3 nuits ratées de suite (anti-robot) : on cesse de la solliciter
  retour arrière : deals.py sources enable rapido

Catalogue : 59 produits · 0 offre en quarantaine · état complet : deals.py status
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

## Mesures : pannes injectées, avant et après

Marché simulé de la démo (59 produits, 177 offres, quatre enseignes), 50 nuits normales, puis six nuits avec la panne.
v53 : le même banc sur le code d'avant (sans agent) ; v54 : `python -m bench.autonomy`.

| Panne (6 nuits) | v53 (avant) | v54 (agent) |
|---|---|---|
| Anti-robot durable chez une enseigne | une ligne d'alerte dans le rapport, 6 nuits ; personne n'est prévenu ; 30 requêtes vers le site qui bloque | incident dès la nuit 1 (e-mail), mise de côté nuit 3 (e-mail), page témoin nuit 6 ; 16 requêtes ; jamais forcé (contournement refusé, journalisé) |
| Panne passagère (5 erreurs, coupe-circuit) | 87 % des fiches de l'enseigne non relues cette nuit-là | relancée et vérifiée la même nuit : 100 % relues ; ni incident ni e-mail |
| Page changée (plus de prix) | alerte dans le rapport, 6 nuits ; 228 requêtes inutiles | incident et commande à lancer dès la nuit 1 (e-mail), mise de côté nuit 3 (e-mail) ; 115 requêtes |
| Erreur de prix d'un soir (÷ 10) et une mission qui guette | prix faux publié (165,90 € au lieu de 1 286 €) et e-mail trompeur « Mission accomplie » | prix retenu en quarantaine : ni publié ni envoyé ; libéré nuit 2, l'erreur écartée de la courbe ; aucun e-mail |
| SMTP en panne 2 nuits, une mission atteinte | e-mail parti nuit 3 ; personne ne le sait | même retour nuit 3 (retenté sans doublon) ; incident ; le responsable l'apprend au retour du SMTP |
| Fichier des partenaires mal rempli (1 enseigne sur 4) | 125 offres sur 177 retirées dès la nuit 1, sans un mot | publication retenue 2 nuits (177 offres gardées), décision proposée, e-mails ; relâchée nuit 3, « catalogue réduit » reste ouvert |

E-mails au responsable sur les six scénarios : 8 en 36 nuits (aucun pour ce qui se règle seul : panne passagère, prix
suspect isolé). Démo sur 75 nuits ordinaires : aucun incident, aucune action.

## Ce qui reste humain, ou hors de portée

- Les réglages globaux (budget de nuit, intervalle entre requêtes, plafonds d'e-mails, seuils des règles) : conseillés,
  jamais changés par l'agent.
- Les démarches auprès des enseignes (flux produits, liste blanche) et des réseaux d'affiliation.
- Écrire une règle de lecture d'un site : l'agent dit où et comment la tester, il ne l'écrit pas (une suggestion de
  sélecteur relue par un humain serait l'étape suivante).
- Supprimer des données : jamais. Libérer un prix, reprendre une source, publier malgré la garde : un geste journalisé.
- Le SMTP de la plateforme sert aussi à prévenir le responsable : s'il tombe, la sonde extérieure prend le relais.
