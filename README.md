# Promo Central — les bonnes affaires du jour, au même endroit

(Nom de code technique : `deals` — la commande, le paquet Python, les services.)

On ouvre l'app pour savoir quelles bonnes affaires existent aujourd'hui, et, pour le produit qu'on regarde (en remise ou
non), ce qui le remplace pour moins cher. Un deal est un deal : le même pour tout le monde, sans onboarding ; seul l'ordre
s'adapte à vos goûts. L'entrée est le produit ; la marque et la catégorie sont des entrées secondaires ; l'enseigne n'est
qu'un attribut de l'offre. On cherche comme on parle (« aspirateur balai sans fil sous 300 € ») : la phrase devient des
critères qu'on modifie d'un geste ; ou l'on se laisse guider, **une question à la fois** (quel univers, quel rayon,
quel type, quel budget), jusqu'à **votre sélection** — dans la Recherche comme sur la page d'une marque ou d'une
catégorie. Une recherche se **sauvegarde** — Promo Central la surveille et dit ce qui est nouveau
(une **mission**, avec un e-mail la nuit si on le souhaite). Tout se garde **sans e-mail** (favoris, marques, rayons,
recherches, alertes de prix) ; l'e-mail, facultatif, sert aux alertes et à retrouver ses choix sur un autre appareil.

Quatre familles chères, où une remise compte : **électroménager (aspirateurs compris), électronique (téléviseurs,
smartphones, ordinateurs, tablettes, casques, enceintes, montres, consoles, écrans), ameublement, literie**. Une lecture
par nuit des **flux produits** des enseignes partenaires (leurs fiches en dernier recours), aucune IA, un seul petit
serveur (Python, bibliothèque standard, SQLite) : environ 6 € HT par mois.

**Modèle d'affiliation** : seules les offres d'enseignes partenaires sont montrées ; chaque clic part par leur lien
affilié avec son identifiant, qui revient dans les rapports du réseau (la vente se rattache à l'écran, à la mission, à
la personne). La plateforme est une aide à la décision d'achat : savoir quels deals existent, être compris (feed
« Pour vous », missions), acheter au bon moment. Une page « Comment ça marche » dit comment les offres sont choisies,
classées et rémunérées.

**Vos goûts d'abord, l'intérêt du deal toujours** : un profil simple (pas d'IA) pèse les rayons et les marques de la
personne d'après ce qu'elle choisit (ses rayons, d'un geste et sans bloquer l'entrée ; ses marques suivies ; ses
missions) et ce qu'elle regarde (favoris, clics vers l'enseigne, recherches, fiches ouvertes). Ses deals passent devant,
au plus × 1,5 : une forte remise ailleurs reste devant ; une place sur quatre va au meilleur deal, quels que soient les
goûts. Tant qu'on ne garde rien, le serveur ne retient rien de la visite ; ce qu'on garde l'est par un compte invité,
sans e-mail ; une visite sur dix est témoin, pour mesurer ce que ça rapporte.
Modèle, vie privée et mesures : [`docs/PERSONNALISATION.md`](docs/PERSONNALISATION.md).

**Trouver vite, sans bazar de bons plans** : on vient chercher quelque chose, on doit le trouver vite. La Recherche
comprend une phrase (rayon, pièce, marque, fonctions, taille ou capacité, budget de… à…, promo, prix bas, et les mots
qui restent), la montre en puces modifiables, affine d'un geste (chaque choix dit ce qu'il donnerait), et ne mène jamais
dans une impasse (rien sous le budget : les plus proches au-dessus). Sur 41 phrases tapées comme on parle, plus aucune
impasse (15 avant) et la première carte juste 24 fois sur 24 (9 avant). **Affiner en entonnoir (v60)** : une question
à la fois — l'univers (High-tech, Entretien, Chambre…), le rayon, le type, un attribut (4K, une taille d'écran), le
budget —, chaque réponse avec ce qu'elle donne, « Passer » pour passer, et une fin : votre sélection ; de la
Recherche vide à des téléviseurs OLED, 3 gestes et une fin (5 gestes et aucune fin avec la feuille de la v59, qui
montrait 53 choix d'un coup) ; le même entonnoir sur la page d'une marque, d'une catégorie, d'une pièce. Règles et
mesures : [`docs/RECHERCHE.md`](docs/RECHERCHE.md).

**Une ontologie pour chaque rayon, bâtie sur ce que déclarent les enseignes (v58, v59)** : trois niveaux seulement — la
catégorie, le type (OLED ou QLED, hublot ou top, balai ou robot, d'angle…) et un ou deux attributs (4K, 5G, sans fil,
No Frost ; une taille d'écran, une capacité) —, lus dans ce que l'enseigne déclare de son offre sur sa fiche (données
structurées : le titre et sa catégorie, « TV - Vidéo > Téléviseurs > TV QLED »), ou dans son flux produits, qui donne
les mêmes champs (v63, `deals/ingest/feeds.py`). Rien n'est rédigé ni deviné : ce que l'offre
ne dit pas reste inconnu. « TV OLED 55 pouces » devient trois étapes de l'entonnoir (Téléviseurs, OLED, 55 pouces) ;
l'entonnoir demande le type, les attributs et les tailles, chacun avec ce qu'il donnerait ; « Moins cher,
comparable » ne remplace un téléviseur OLED de 55 pouces que par un OLED de 55 pouces. Sur 146 produits et 41 pièges
écrits comme des flux, tout est rangé et lu juste, rien de deviné (v58 : 98 rangés, l'électronique pas du tout) ; sur
52 offres inédites, 49 rangées à la première lecture, 52 après correction. Ontologie et mesures :
[`docs/ONTOLOGIE.md`](docs/ONTOLOGIE.md).

**Architecture** : un monolithe modulaire, une chaîne de nuit qui calcule (ingestion → marché → publication du
catalogue), une app de jour qui lit le catalogue publié ; des couches qui se parlent par des contrats, et des frontières
vérifiées par un test. **Ingestion (v63)** : le flux produits de chaque enseigne (CSV, XML Google Shopping, JSON ; gzip
ou zip), décrit par une entrée de configuration et la correspondance de ses colonnes — ajouter une enseigne ne demande
aucun code ; chaque lecture est un lot tracé (empreinte, fichier brut gardé, lignes refusées et leur raison) et
rejouable ; le même fichier relu ne crée ni doublon ni ligne de prix ; un flux tronqué ne supprime rien. La démo est
nourrie par les flux de ses enseignes simulées et publie exactement le catalogue de la lecture de leurs fiches.
Modules, contrats et données : [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Audit et refonte
d'octobre 2026, mesures avant / après : [`docs/AUDIT.md`](docs/AUDIT.md). Mise en production à J+30 (audit J1–3,
registre des risques, décisions, plan par lots, go/no-go) : [`docs/PRODUCTION.md`](docs/PRODUCTION.md), vérifié par
`python -m bench.cadre`.

**Exploitation quasi autonome** : un agent de nuit (des règles écrites, pas d'IA) relance une source en panne passagère,
met de côté celle qui échoue trop sans jamais forcer un anti-robot, retient un prix suspect, garde le catalogue de la
veille quand le nouveau fond, journalise tout et n'écrit au responsable que s'il y a lieu ; ce qui engage (reprendre une
source, publier malgré la garde, envoi massif) attend `deals.py approve`. Politiques, règles et mesures sur pannes
injectées : [`docs/AUTONOMIE.md`](docs/AUTONOMIE.md) ; que faire pour chaque incident : [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

## Commandes
```
python deals.py demo                         app sur http://127.0.0.1:8000/ : 75 nuits de marché simulé, 127 produits
python deals.py serve                        l'app et /api/r/ (en production derrière Caddy, voir deploy/)
python deals.py nightly                      la nuit : collecte → agent → publication → e-mails des missions → contrôles →
                                             rapport du matin → e-mail au responsable s'il y a lieu
python deals.py status                       l'état : dernière nuit, catalogue, sources, incidents, décisions en attente
python deals.py incidents|actions|events     incidents ouverts, actions auditées, journal d'une nuit (--cid)
python deals.py approve|reject <n°>          décider d'une proposition de l'agent
python deals.py sources [enable|disable <clé>]     registre des sources ; reprendre ou mettre de côté
python deals.py quarantine [release <offre>] prix suspects retenus ; libérer un prix vérifié chez l'enseigne
python deals.py partners                     enseignes partenaires déclarées et leur source
python deals.py publish                      republier le catalogue sans relire le web
python deals.py missions                     envoyer les e-mails des missions sur le catalogue publié
python deals.py ingest <source|all> [--file F] [--dry-run]   lire le flux d'une enseigne (la nuit le fait pour toutes)
python deals.py batches [--source <clé>] [--rejects <lot>]  les lots : quoi, quand, combien, lignes refusées
python deals.py replay <source>              relire le fichier gardé du dernier lot (correspondance corrigée)
python deals.py probe <fichier>              un échantillon de flux : format, colonnes, correspondance proposée
python deals.py discover|diagnose|sample|build <enseigne|all>     lire les fiches d'une enseigne sans flux
python deals.py explain <adresse>            ce que l'extraction voit sur une page, et pourquoi
python deals.py rules <site> '<json>'        règle de lecture d'un site (sélecteurs)
python deals.py review|estimate|metrics      rapprochements à vérifier, durée de la nuit, mesures de conversion
python deals.py backup <dossier>             sauvegarde à chaud vérifiée (14 conservées)
python -m unittest discover -s tests -t .    tests (254, ~70 s)
python -m bench.extraction | bench.deals_truth | bench.alternatives | bench.missions | bench.scale [--aspirateurs N]
          | bench.autonomy | bench.profiles [--scale] | bench.search [--scale] | bench.aspirateurs     mesures
python -m bench.cadre                        le cadre de mise en production : points non négociables, sauvegarde,
                                             en-têtes (docs/PRODUCTION.md)
ESBUILD=<esbuild> REACT_DIR=<node_modules> ./web/build.sh          reconstruire web/app.html
```
`--db` (avant la commande) choisit la base ; réglages par variables `DEALS_*` (`deals/config.py`,
`deploy/deals.env.example`). Les commandes qui lisent les sites exigent `DEALS_USER_AGENT` (nom du robot, contact).

## API `/api/r/` (contrat de l'app)
Lecture ouverte : `today?category=&q=` (remises du jour), `top` (top deals de l'accueil ; `why` : la remise, le prix
bas et depuis quand), `search?q=&category=&room=&brand=&feat=&attr=&min=&max=&off=&low=&sort=&recent=` (tout le
catalogue suivi ; `q` est une phrase comprise, les autres paramètres sont les critères choisis dans l'app et l'emportent
sur elle : `feat` des fonctions séparées par des virgules, `attr` des `clé:valeur` (`capacity_kg:9`, `bed_size:160x200`,
`energy_class:C`) ; promo : remise minimale en % ou `low=1` ; tri : `relevance`, `price`, `discount` ; la réponse dit
`criteria` (ce qui est appliqué), `said` (ce que la phrase seule demande), `chips` (les critères en mots, un par puce,
avec ce qu'on retire en la fermant), `words` (les mots qui filtrent), `ignored` (ceux qui ne trouvaient rien),
`unsupported` (un rayon pas encore suivi), `relaxed` (rien sous le budget : les plus proches au-dessus, dès quel prix),
`options` (fonctions, tailles et marques du rayon ou de la pièce, avec ce que chacune donnerait), `funnel` (v60,
l'entonnoir : `path`, les étapes franchies — `label`, `fixed`, `back` (les critères qui reviennent avant elle), `chips`
(les puces qu'elle montre déjà) — et `questions`, dans l'ordre — `title`, `options` : `label`, `count`, `set` (les
critères que la réponse ajoute)), `categories`
(les catégories trouvées et leur nombre), `offs` (les produits de chaque palier de promo) ; sans mot ni filtre, le feed,
orienté par `recent` : les dernières recherches gardées par le navigateur, séparées par `|` ; dans un rayon et son
ontologie (v58 : les aspirateurs ; v59 : tous) : `domain=aspirateurs&sub=balai&prop=cordless:1` — le type, les
attributs oui/non exigés `clé:1` ou `clé:0`, les mesures en `attr` (`screen_in:55`, `storage_gb:256`) — et la réponse
dit `domain` (avec ses rayons), et dans `options` (Affiner) `subs` (les types, nom court, les plus fournis
d'abord) et `props` (sans fil, sans sac : oui ou non, avec ce que chacun donnerait)),
`categories` et `brands` (celles qui ont des remises ; `?all=1` : toutes), `brand/<nom>` et `category/<clé>` (tous
leurs produits, remises d'abord), `item/<id>`,
`out/<offer_id>?from=`, `missions/parse` {text} et `missions/preview` {mission} (ce qui est compris, ce qui y répond
déjà ; une mission : `product_id`, ou `like` (comparables à ce produit), ou `category`, `brand`, `features`, `attrs` ;
et `max_price`).
Ajoutés depuis la v41 : `search`, `since` et `ends` (fiche), `alternatives` avec `saving` (fiche), `kind` (cartes :
catégorie au singulier), `published_at` (today : heure de la dernière publication), `saved_price` (favoris), `family`,
`best` et `products` (catégories), `best`, `products`, `top` et `categories` (marques), `attrs` (fiche : caractéristiques
lues, pour les missions) ; retirés : `specs` en v49 (la description n'est plus montrée), `history` et `position` en v60
(la fiche n'a plus la jauge du prix) ; tri `price_desc` (prix décroissant) en v60 ;
`today?category=` accepte plusieurs catégories séparées par des virgules (univers, pièce).
Garder (v56 : sans e-mail ; sans session, le premier geste crée un compte invité et pose son cookie, un an, renouvelé à
chaque geste qui garde) : `save`, `brand/follow`, `interests`, `profile` {learn}, `missions` (POST : sauvegarder une
recherche ou poser une alerte — `category`, `room`, `brand`, `features`, `attrs`, `words`, `min_price`, `max_price`
facultatif, `off`, `low`, ou `product_id`, ou `like` ; la même cible change seulement de prix). Lire ce qu'on garde
(vide sans compte) : `saves`, `follows`, `missions` (les miennes, ce qui y répond, `fresh` : ce qui est nouveau depuis
qu'on l'a ouverte, `reached`, `alert`). `missions/seen` {id} (ouverte : plus nouveau), `missions/alert` {id, on} (l'e-mail
de la nuit ; il faut une adresse), `missions/delete` {id}, `account/delete` (effacer le compte et ce qu'il gardait).
Comptes : `auth/request` {email} (depuis un compte invité : l'adresse lui sera rattachée, ou ce qu'il garde versé dans
le compte qui a déjà cette adresse), `auth/verify?token=` (pose le cookie, ou renvoie vers `/?auth=expired`), `auth/me`
(`email`, `guest`, et `variant` : `p` personnalisé, `t` témoin), `auth/logout`.
Goûts (v55) : `today`, `top`, le feed de `search` et `foryou` (« pour vous » : les deals et prix bas de vos rayons et de
vos marques, dix au plus ; `taste` : ce que l'app a compris) suivent le profil. Sans compte (ou un compte qui n'apprend
pas des fiches), l'app envoie `p` (fiches ouvertes `v<id>.<âge en jours>`, clics `c…`, au plus 60) et, sans compte,
`v=t` (témoin) ; le serveur n'en garde rien (`i`, les rayons choisis dans le navigateur, reste lu pour les navigateurs
d'avant la v56). `profile` : rayons choisis, ce qui est compris, apprentissage, variante, `guest`, `email` ;
`interests` {categories} (rayons choisis, douze au plus, la liste remplace la précédente), `profile` {learn} (tenir
compte des fiches ouvertes et des clics, ou non), `profile/reset` (oublier ce qui a été déduit). `view` {v} et
`out?v=` rapportent la variante dans les mesures.
Surveillance : `health` (pour une sonde extérieure : `status` ok, degraded ou critical, heure de la dernière nuit, taille
du catalogue ; 503 si aucune nuit depuis 36 h, si la dernière a eu une étape en erreur ou si un incident critique est
ouvert).

## Règles du produit
- **Seulement des remises réelles.** Une remise affichée par l'enseigne est crue, sauf preuve du contraire : notre
  historique hors promotion (au moins 14 jours observés), la mention légale « prix le plus bas des 30 derniers jours »,
  ou un « prix barré » inchangé depuis 60 jours (c'est alors le prix). Fausse remise : 10 points de plus que la remise
  réelle, sauf si celle-ci dépasse 30 %. Une fiche reste consultable, sans remise affichée (`deals/judge.py`).
- **Une carte** : le visuel (illustration de la catégorie), la remise posée dessus, la marque, un nom sur une ligne, le
  prix et le prix barré. Les durées (depuis quand, jusqu'à quand) ne sont que dans la fiche. La
  qualité est implicite. Aucune description technique ni autre enseigne : elles sont chez l'enseigne, qui est proposée
  seule (la moins chère, disponible).
- **Le prix du jour sur les derniers mois** : face au meilleur prix de chaque jour relevé (toutes enseignes suivies,
  jusqu'à 90 jours, aujourd'hui exclu), « au plus bas » si aucun jour n'était moins cher et que le prix était plus haut
  au moins un jour sur deux ; « parmi les plus bas » s'il est moins cher qu'au moins 2 jours sur 3 ; rien avant 14
  jours relevés (`catalog.position`). Il sert au prix bas des top deals. La fiche le montrait en mots et en jauge de la
  v49 à la v59 ; retiré en v60 (la jauge troublait plus qu'elle n'aidait).
- **Affiner en entonnoir (v60)** : une question à la fois — l'univers, le rayon, le type, les attributs du rayon, le
  budget —, chaque réponse avec ce qu'elle donne, ni tout ni rien, « Passer », une fin (« Votre sélection »), dans
  la Recherche et sur les pages d'une marque, d'une catégorie, d'une pièce (`deals/funnel.py`, `docs/RECHERCHE.md`).
- **Classement** : l'intérêt du deal (remise en % ; pour un prix bas, ce qu'il fait économiser sur le prix habituel)
  × (1 + ½ affinité de la personne pour le rayon ou la marque), donc au plus × 1,5 : une remise de 40 % hors de vos
  rayons passe devant une remise de 26 % dans vos rayons. Une place sur quatre va au meilleur deal restant, sans les
  goûts ; jamais plus de deux produits d'un même rayon sur quatre de suite dans les listes, ni plus de trois dans les
  top deals. Sans
  goûts connus, ou pour un témoin (une personne sur dix) : remise, × 1,5 pour une marque suivie, comme avant ; une
  recherche ou un filtre répond à ce qui est demandé, sans les goûts (`deals/profile.py`).
- **Vos goûts** : choisis (rayons de l'encart de l'accueil ou du Profil, marques suivies, rayon et marque d'une mission :
  affinité 1) ou vus (favori 2 points, clic vers l'enseigne 1,5, recherche qui nomme un rayon ou une marque 1, fiche
  ouverte 0,5 ; moitié moins tous les 30 jours ; un rayon vu vaut au plus 0,8, une marque vue 0,4 et seulement à partir
  d'un point ; la famille du rayon reçoit 30 %). « Pour vous » : affinité d'au moins 0,3 pour le rayon ou la marque
  eux-mêmes. Le Profil dit ce qui est compris et permet de l'oublier ; un compte peut refuser l'apprentissage par ses
  fiches et ses clics (`docs/PERSONNALISATION.md`).
- **Moins cher, comparable** (fiche) : jusqu'à trois produits qui remplacent vraiment celui qu'on regarde et coûtent au
  moins 10 % de moins, disponibles, la plus forte économie d'abord, une marque par ligne, avec l'économie en euros.
  Remplacer = même catégorie ; même usage (même taille de literie, largeur à 6 % près en électroménager et 20 % en
  ameublement, places à une près, même forme : balai, traîneau, encastrable, d'angle, américain) ; au moins les mêmes
  fonctions (sans fil, laveur, convertible, induction, électrique) ; pas moins bien (classe énergie au plus une lettre
  en dessous ; capacité, couverts, foyers au plus un de moins ; volume au plus 15 % de moins ; autonomie au moins les
  deux tiers ; bruit au plus 3 dB de plus). Sans alternative moins chère : les autres comparables, au prix le plus
  proche (« Produits similaires ») ; sans comparable : rien (`deals/alternatives.py`).
- **Recherche** : tout le catalogue suivi, pas seulement les remises, pour une intention précise. Une phrase est
  comprise en critères (`deals/query.py`) : rayon (ou pièce), marque, fonctions, taille ou capacité, budget (maximum,
  de… à…, minimum), remise minimale, prix bas, tri par prix (« pas cher ») ; ce qui est dit est exigé (mêmes règles que
  les missions), ce qui ne l'est pas ne l'est pas ; les mots qui restent filtrent s'ils trouvent, sinon ils sont dits
  et le reste répond ; une phrase dont rien n'est compris est cherchée mot à mot ; un rayon non suivi est dit. Le
  rayon, le type, les attributs et le budget sont les étapes de l'entonnoir, la marque, la promo, le tri et les mots
  des puces (une croix élargit aussitôt) ; l'entonnoir pose la question suivante, chaque réponse avec ce qu'elle
  donnerait, ses autres critères gardés (une réponse qui donne tout ou rien n'est pas proposée). Rien sous le budget :
  les plus proches au-dessus, du moins cher au plus cher. Tri par pertinence (d'abord les produits que les mots
  nomment, puis les remises, puis le prix), par prix croissant ou décroissant, ou par remise ; insensible aux accents,
  à la casse et aux tirets, synonymes courants (frigo, sofa, aspi…).
  Jamais vide : sans mot ni filtre, un feed (les produits des quatre dernières recherches d'abord, puis ceux de vos
  rayons et de vos marques, un sur quatre pris ailleurs, puis tout le catalogue, une catégorie à tour de rôle).
- **Chaque rayon a son ontologie (v58 : les aspirateurs ; v59 : tous, électronique comprise)** : le type et un ou deux
  attributs lus dans le titre de l'offre et la catégorie déclarée par l'enseigne, le plus précis des types d'abord (un
  « balai laveur » est un laveur) ; un niveau de catégorie qui en nomme plusieurs (« Casques et écouteurs ») n'en dit
  aucun ; un attribut que l'offre ne dit pas reste inconnu, et une recherche ne le promet pas ; ce qu'un type est par
  définition (un robot est sans fil) ne remplace jamais ce que l'offre dit. La catégorie déclarée est gardée et relue à
  chaque publication : une ontologie révisée s'applique sans relire les offres (`deals/ontology/*.json`, un fichier par
  famille ; `docs/ONTOLOGIE.md`).
- **Marque et catégorie** (fiche) : deux étiquettes sur le visuel, qui mènent à tous les produits de la marque ou de la
  catégorie, les remises d'abord, même sans remise aujourd'hui.
- **Recherches sauvegardées et alertes de prix (missions)** : une recherche sauvegardée (prix maximum facultatif), ou
  une alerte sur un produit ou ses comparables (même rayon, même type, ses attributs, même taille d'écran ou capacité). Chacune dit ce
  qui y répond et ce qui est nouveau depuis qu'on l'a ouverte (un produit arrivé, ou moins cher d'au moins 0,50 €) ; la
  rouvrir l'oublie. Ce qui est dit est exigé, ce qui ne l'est pas ne l'est pas : catégorie,
  marque, fonctions (balai, sans fil…), capacité, couverts, foyers, places, volume, autonomie au moins ; taille de
  literie exacte ; largeur à 6 % près ; bruit au plus ; classe énergie au moins. Un produit remplit une mission s'il est
  disponible, au prix voulu et conforme (une caractéristique demandée mais inconnue du produit : pas de promesse). Une
  phrase sur une catégorie non suivie est refusée en le disant ; un prix impossible n'est pas retenu, il est demandé.
  Une mission par cible (relancer change le prix), 20 par personne. La nuit, après la publication : un e-mail au plus
  par personne qui a donné son adresse, pour les missions dont la cloche est allumée, avec les produits arrivés à son
  prix ou descendus plus bas qu'au dernier e-mail (les cinq moins chers par mission, les autres dans l'app) ; jamais
  deux fois le même produit au même prix ; rien pour ce qu'elle voyait déjà en sauvegardant ou dans l'app avant de
  donner son adresse ; au-delà du plafond de la nuit (`DEALS_MISSION_MAILS`), la suite part la nuit suivante
  (`deals/missions.py`).
- **Sans e-mail** : favori, marque suivie, rayon, recherche sauvegardée, alerte de prix se gardent d'un geste ; le
  premier crée un compte invité pour l'appareil (cookie HttpOnly, un an, renouvelé à chaque geste qui garde ; 100
  créations au plus par adresse IP et par heure ; un geste qui échoue ne laisse aucun compte ; chercher ou regarder
  n'en crée pas ; la nuit, un compte invité que plus personne ne peut ouvrir est effacé). L'e-mail est facultatif
  (« Ajouter mon e-mail », « J'ai déjà un compte ») : le lien rattache l'adresse au compte invité, ou verse ce qu'il
  garde dans le compte qui a déjà cette adresse (sans doublon). Lien à usage unique valable 15 min ; 5 liens par
  adresse et par heure, 20 par adresse IP, plafond quotidien global ; même réponse qu'un compte existe ou non ; seuls
  les hachages des jetons sont stockés. « Effacer mes données » efface le compte et ce qu'il gardait.
- **Favoris** : le prix du jour où le favori a été posé est gardé ; une baisse se voit dans Favoris et sur l'onglet.
- **Clics sortants** : `out/<offer_id>?from=&m=&v=` trace le clic (avec ou sans compte), sa source (`item`, ou d'où la
  fiche a été ouverte : `top`, `foryou`, `home`, `room`, `alternative`, `similar`, `mission`, `mail`, `brand`,
  `category`, `search`, `feed`, `saved`), sa mission et sa variante (personnalisé ou témoin), puis envoie vers l'offre
  par le lien affilié de l'enseigne, avec l'identifiant du clic ; jamais ailleurs que vers une offre connue. Chaque
  fiche ouverte est comptée (`view`), sans identifiant pour une personne sans compte.
- **Mesures de conversion** (`python deals.py metrics`) : fiches vues, clics vers l'enseigne et taux de clic par écran
  et par personne (avec mission, connectée sans mission, sans compte) ; par variante et par écran (`by_variant` :
  personnalisé `p` ou témoin `t`, ce que la personnalisation rapporte) ; part des clics partis chez un partenaire ; clics
  venus des missions. Les ventes et commissions viennent des rapports du réseau, rattachées par l'identifiant du clic.
- **Missions vers l'achat** : une mission atteinte propose « Voir l'offre » en un geste ; dans l'e-mail, chaque produit
  mène en un clic à l'offre ou à sa fiche (source `mail`, mission connue).
- **Fraîcheur** : toutes les offres sont relues chaque nuit tant que la passe tient dans le budget (4 h) ; sinon, par
  ordre de valeur (prix en quarantaine à revérifier, deal en cours, favori, clic récent, puis le plus ancien relu). Un
  prix non relu depuis 3 jours n'est plus montré.
- **Seulement des données validées** : un prix relu à moins de 30 % du prix habituel du produit est retenu (ni publié
  ni envoyé aux missions) jusqu'à ce qu'il revienne à la normale (il est alors écarté des courbes) ou soit relu au même
  prix les deux nuits suivantes (il est cru) ; un catalogue qui perdrait plus de 20 % de ses produits ou de ses offres
  n'est pas publié, celui de la veille reste en ligne (au plus deux nuits) ; un envoi d'e-mails de missions bien plus
  nombreux que d'habitude attend une décision (`deals/quarantine.py`, `deals/publish.py`, `deals/night.py`).

## Interface

Une page (`web/src/App.jsx` → `web/app.html`, polices incluses, aucune requête vers un tiers) : un flux vivant de
remises, à la croisée d'un Pinterest (mosaïque de visuels, inspiration par pièce) et d'un Bloomberg (bandeau défilant
avec l'heure de mise à jour ; la jauge du prix sur la fiche, de la v49 à la v59, est retirée en v60). Les visuels sont
des illustrations originales par catégorie (`web/src/art.jsx`) ; les photos des enseignes ne sont pas montrées tant
que la question des droits n'est pas tranchée.
Téléphone d'abord, mosaïque de 4 à 5 colonnes sur ordinateur, contrastes et zones à toucher aux normes WCAG AA, bandeau
immobile si l'appareil demande moins d'animations, lien partageable vers chaque fiche (`/?p=<id>`). Trois onglets :
Accueil (les top deals, « Pour vous », puis pièces, marques en promo, sélection), Recherche (une phrase comprise, l'entonnoir — une question à la fois, jusqu'à votre sélection —, Promo et
Trier, Sauvegarder ; vos recherches sauvegardées et récentes ; un feed qui s'adapte ; le même entonnoir sur les pages
d'une marque, d'une catégorie, d'une pièce), Profil, le centre de commande (vos recherches et alertes, favoris,
marques, rayons — repliés, ouverts d'un geste —, ce que l'app a compris, l'e-mail facultatif, effacer : des titres
seuls, beaucoup d'air) ; « Comment ça marche » au pied de chaque écran ; espaces insécables du français dans les
textes.
Principe, écrans et mesures v41 à v60 : [`docs/UX.md`](docs/UX.md).

## Extraction : ne jamais enregistrer une donnée fausse

Une donnée manquée coûte une bonne affaire ; une donnée fausse (prix membre pris pour le prix public, prix d'un produit
voisin, fiche devenue page liste) coûte la confiance. L'extraction lit dans l'ordre : JSON-LD, règles de site,
microdonnées, balises meta, état applicatif embarqué (seulement si l'identité du produit concorde). Le prix barré peut
aussi venir du bloc de prix HTML, mais seulement à côté du prix trouvé par une source structurée, dans le même bloc.

Repris de l'existant (BSD-3, voir `THIRD_PARTY_NOTICES.md`) : **Protego** (Scrapy) pour robots.txt, la chaîne de
réparation JSON-LD d'**extruct** (Zyte), les corpus de test d'extruct, de price-parser et de Protego.

| `python -m bench.extraction` | Extracteur d'origine | Actuel |
|---|---|---|
| Chaînes de prix réelles (corpus price-parser) | 1 035 / 1 040 | 1 036 / 1 040 |
| JSON-LD mal formés tirés de bugs réels (corpus extruct) | 5 / 36 | 36 / 36 |
| Spécification robots.txt (Python 3.11 / 3.12 du serveur) | 37 / 66 | 66 / 66 |
| Pages-pièges construites sur des motifs réels | 9 / 26 | 26 / 26 |
| Pages-pièges écrites après réglage (généralisation) | 3 / 8 | 8 / 8 |
| Temps CPU, grande page produit (~450 Ko) | 80 ms | ~100 ms |

Garde-fous : prix membre jamais pris pour le prix public ; produit principal choisi parmi plusieurs (carrousels) ; fiche
devenue page liste, introuvable ou montrant un autre produit → offre retirée, rien d'enregistré ; offre reconditionnée
écartée si une offre neuve existe ; devise autre que l'euro refusée ; « -40 % » jamais lu comme un prix ; prix barré
validé (au-dessus du prix, remise ≤ 85 %, cohérent avec le pourcentage affiché ; bandeaux « jusqu'à -50 % » ignorés) ;
financement, éco-participation, ODR, « autres offres dès … » jamais pris pour un prix. Blocage reconnu par signature
(DataDome, Cloudflare, Akamai, Imperva, PerimeterX, Kasada, Queue-it) sans faux positif sur une page lisible.

## Enseignes partenaires (affiliation)

`DEALS_AFFILIATE` désigne un fichier JSON : clé d'enseigne (`deals/ingest/retailers.py` ou `DEALS_SOURCES`) → règle de lien. Deux formes :
le gabarit du réseau, avec `{url}` (l'adresse de la fiche, encodée) et `{subid}` (l'identifiant du clic), ou des
paramètres ajoutés à l'adresse de la fiche (`tag=…&sub={subid}`) ; exemple : `deploy/affiliate.example.json`, gabarits
exacts dans l'espace affilié de chaque réseau. Seules ces enseignes sont lues la nuit et publiées ; un fichier mal formé
arrête le démarrage. Sans ce fichier (développement), tout est publié et les liens partent tels quels ; la démo simule
des enseignes partenaires.

## Sources : les flux d'abord, les fiches en dernier recours

Chaque enseigne partenaire est une source (`DEALS_SOURCES`, exemple : `deploy/sources.example.json`) : son **flux
produits**, fourni par son programme d'affiliation, lu chaque nuit par le connecteur (`deals/ingest/`) ; ou, à défaut et
si ses conditions le permettent, ses fiches. Enseignes visées (leaders de l'électroménager, de l'électronique et de
l'ameublement) : Boulanger, Darty, Fnac, Conforama, But, IKEA, Maisons du Monde, La Redoute, Cdiscount — chacune
s'active quand son programme est accepté et son flux branché (`deploy/README.md`). Relevé le 31/10/2026 : Boulanger
annonce des flux produits à ses affiliés via Kwanko ; Fnac (profil Awin « Fnac FR ») des flux XML ou CSV ; Darty
(Effinity selon darty.com, et un profil Awin « Darty FR ») un flux d'environ 15 000 produits — à confirmer à
l'inscription. Le flux est aussi la seule voie pour Darty et Conforama, dont les fiches ne se lisent pas sans forcer.

Familles : **électroménager** (lave-linge, sèche-linge, lave-vaisselle, réfrigérateurs, congélateurs, fours, plaques,
hottes, cuisinières, aspirateurs, robots aspirateurs), **ameublement** (canapés, fauteuils, lits, armoires, tables, buffets, meubles TV, commodes),
**literie** (matelas, sommiers). Un titre qui commence par un accessoire ou un prix sous 100 € (30 € pour les
aspirateurs : un aspirateur à main coûte souvent moins) n'entre pas au catalogue.

Enseignes actives : Boulanger, Electro Dépôt, Ubaldi, Cdiscount, But, IKEA, Maisons du Monde, La Redoute, Vente-unique.
Désactivées, avec la raison dans `deals/ingest/retailers.py` : Conforama (défi Cloudflare, prix chargés par le
navigateur), Darty (anti-robot signalé contre les centres de données, à vérifier avec `diagnose darty`), Amazon
(conditions d'utilisation). Un site qui bloque est signalé, jamais forcé.

Constituer la base : `discover` (plans de site) → `diagnose` (verdict par enseigne : garder si ≥ 80 % des pages ont un
prix, règle de site à écrire, ou abandonner) → `explain` et `rules` pour une page qui résiste → `sample` (pages brutes
pour un réglage hors ligne) → `build` (première lecture, rapprochement par EAN) → `review` → `estimate`. Sur le
serveur : `sudo deals <commande>` (voir `deploy/README.md`).

La passe de nuit : une requête par page, robots.txt et Crawl-delay respectés, au moins 5 s entre deux requêtes vers un
même site, les sites en parallèle ; requêtes conditionnelles (ETag / Last-Modified) ; seuls les changements de prix
sont enregistrés ; les fortes variations sont relues avant d'être crues ; rapport du matin avec alertes.

## Coût de fonctionnement
- ~4 600 fiches (40 par catégorie et par enseigne) ; le site le plus chargé (~840 fiches × 5 s) fixe la passe : ~70 min
  par nuit. Publication, alternatives et courbes de 90 jours comprises : ~3 s pour 3 000 produits (~1 ms par produit,
  aspirateurs compris, dont l'ontologie relit la catégorie gardée).
- Base : quelques dizaines de Mo par an (seuls les changements sont écrits).
- Missions de la nuit : ~6 s pour 10 000 missions sur 3 000 produits (~1,6 à 2,2 s une nuit sans changement).
- Serveur : Hetzner CX23, 5,49 € HT + 0,50 € d'IPv4 = **5,99 € HT par mois** (tarifs d'août 2026).
- E-mails (connexion, et missions : au plus un par personne et par nuit) : Brevo gratuit jusqu'à 300 par jour, partagés
  par les deux plafonds (`DEALS_MAILS_PER_DAY` 250, `DEALS_MISSION_MAILS` 50) ; au-delà, une offre payante. Nom de
  domaine : quelques euros par an. Aucun proxy, aucune API payante, aucune IA.

## Limites connues
- Aucun flux réel n'a encore été lu : le connecteur est prouvé sur des flux d'essai (CSV en Windows-1252, XML Google
  Shopping, JSONL compressé) et sur ceux de la démo. Chaque vrai flux reçoit sa correspondance écrite sur un échantillon
  (`probe`), puis un premier lot à blanc (`ingest --dry-run`) ; les noms de colonnes d'un réseau ne s'écrivent pas de
  mémoire.
- Les taux de lecture réels par enseigne restent à mesurer depuis le serveur (`diagnose`) : l'environnement de
  développement n'a pas accès au web ; tout est vérifié sur faux sites locaux, corpus publics et pages-pièges.
- Pas de navigateur : un site dont les prix n'existent qu'après exécution du JavaScript reste illisible (Conforama).
- Une baisse sans prix barré n'est pas montrée (choix produit et juridique, voir `docs/AUDIT.md`).
- Sans e-mail, ce qu'on garde tient à l'appareil et à son cookie : effacer les données du navigateur le perd ; un
  compte invité ne se retrouve pas sur un autre appareil. 100 comptes invités au plus par adresse IP et par heure : un
  très grand réseau derrière une seule adresse (opérateur mobile) pourrait l'atteindre aux heures de pointe.
- Personnalisation : des règles simples sur les rayons et les marques, pas de « ceux qui ont aimé ceci » ni de budget
  appris ; sans compte, les fiches ouvertes ne sont gardées d'une visite à l'autre que si la personne l'accepte (Profil),
  et le témoin est tiré à chaque visite. Le gain mesuré par `bench.profiles` repose sur un modèle de clic : le vrai
  gain se lit sur les témoins en production (`metrics`, `by_variant`).
- Exploitation : l'agent prévient le responsable par le SMTP de la plateforme ; s'il tombe, seule une sonde extérieure
  sur `/api/r/health` le voit (à brancher, voir `docs/RUNBOOK.md#sonde`). L'agent conseille une règle de lecture quand
  une page change ; il ne l'écrit pas.
- Recherches sauvegardées : ce qui est nouveau se voit dans l'app (cloche, Profil) et par e-mail la nuit, pour qui a
  donné son adresse ; pas de notification sur le téléphone (l'app est une page web, pas une app installée). Une phrase
  n'est comprise que dans ce que l'extraction sait lire (catégories suivies, marques présentes au catalogue, fonctions
  et tailles connues) : « une marque inconnue » reste un mot cherché, « un joli canapé » un canapé ; les puces montrent
  exactement ce qui a été compris. Pas de correction des fautes de frappe (« aspirateru ») ni de synonymes appris : une
  liste écrite (`SLANG`, `deals/query.py`). Un produit dont le titre ne dit pas une fonction (« balai ») n'y répond pas :
  pas de promesse sur ce qui n'est pas lu.
- Ontologie (v59) : seulement ce que le titre et la catégorie déclarée disent : une offre qui ne dit ni le type ni ses
  attributs n'est trouvée que par son rayon. Des règles écrites à la main, en français (« cordless » n'est pas lu). Les
  bancs ont une vérité et des offres écrites par le même auteur que les règles (les 64 offres inédites aussi, écrites
  après) : la lecture sur de vrais flux reste à mesurer, sur un échantillon réel de chaque enseigne (`sample`). Pas de
  besoin compris (« pour mon chat ») : le mot est dit sans résultat, rien n'est supposé.
- Alternatives : jugées sur ce que disent le titre et les caractéristiques déclarées par l'enseigne ; un critère absent
  des deux (puissance d'aspiration, matériaux, finition) n'est pas comparé. Un produit sans comparable dans le
  catalogue n'a pas de section (sur la démo de 127 produits, 46 fiches ; sur 3 000 produits, aucune) ; un produit dont le
  type n'est pas dit n'est comparé qu'à ceux qui ne le disent pas non plus.
