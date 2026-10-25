# DEALS — les bons deals du jour, au même endroit

On ouvre l'app pour savoir quelles bonnes affaires existent aujourd'hui, et, pour le produit qu'on regarde (en remise ou
non), ce qui le remplace pour moins cher. Un deal est un deal : le même pour tout le monde, sans onboarding ; seul l'ordre
s'adapte à vos goûts. L'entrée est le produit ; la marque et la catégorie sont des entrées secondaires ; l'enseigne n'est
qu'un attribut de l'offre. Quand ce n'est pas encore le bon prix, on dit ce qu'on veut et son prix (« aspirateur balai sous
300 € ») : une **mission**, et un e-mail la nuit où c'est le cas. On lit sans compte ; un e-mail suffit pour garder des
favoris, suivre des marques et lancer des missions.

Trois familles chères, où une remise compte : **électroménager (aspirateurs compris), ameublement, literie**. Une collecte par nuit,
aucune IA, un seul petit serveur (Python, bibliothèque standard, SQLite) : environ 6 € HT par mois.

**Modèle d'affiliation** : seules les offres d'enseignes partenaires sont montrées ; chaque clic part par leur lien
affilié avec son identifiant, qui revient dans les rapports du réseau (la vente se rattache à l'écran, à la mission, à
la personne). La plateforme est une aide à la décision d'achat : savoir quels deals existent, être compris (feed
« Pour vous », missions), acheter au bon moment. Une page « Comment ça marche » dit comment les offres sont choisies,
classées et rémunérées.

**Vos goûts d'abord, l'intérêt du deal toujours** : un profil simple (pas d'IA) pèse les rayons et les marques de la
personne d'après ce qu'elle choisit (ses rayons, d'un geste et sans bloquer l'entrée ; ses marques suivies ; ses
missions) et ce qu'elle regarde (favoris, clics vers l'enseigne, recherches, fiches ouvertes). Ses deals passent devant,
au plus × 1,5 : une forte remise ailleurs reste devant ; une place sur quatre va au meilleur deal, quels que soient les
goûts. Sans compte, rien n'est gardé par le serveur ; une visite sur dix est témoin, pour mesurer ce que ça rapporte.
Modèle, vie privée et mesures : [`docs/PERSONNALISATION.md`](docs/PERSONNALISATION.md).

**Architecture** : une chaîne de nuit qui calcule (collecte → marché → publication du catalogue), une app de jour qui
lit le catalogue publié. Modules, règles et données : [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Audit et refonte
d'octobre 2026, mesures avant / après : [`docs/AUDIT.md`](docs/AUDIT.md).

**Exploitation quasi autonome** : un agent de nuit (des règles écrites, pas d'IA) relance une source en panne passagère,
met de côté celle qui échoue trop sans jamais forcer un anti-robot, retient un prix suspect, garde le catalogue de la
veille quand le nouveau fond, journalise tout et n'écrit au responsable que s'il y a lieu ; ce qui engage (reprendre une
source, publier malgré la garde, envoi massif) attend `deals.py approve`. Politiques, règles et mesures sur pannes
injectées : [`docs/AUTONOMIE.md`](docs/AUTONOMIE.md) ; que faire pour chaque incident : [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

## Commandes
```
python deals.py demo                         app sur http://127.0.0.1:8000/ : 75 nuits de marché simulé, 59 produits
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
python deals.py discover|diagnose|sample|build <enseigne|all>     constituer et régler la base
python deals.py explain <adresse>            ce que l'extraction voit sur une page, et pourquoi
python deals.py rules <site> '<json>'        règle de lecture d'un site (sélecteurs)
python deals.py review|estimate|metrics      rapprochements à vérifier, durée de la nuit, mesures de conversion
python deals.py backup <dossier>             sauvegarde à chaud vérifiée (14 conservées)
python -m unittest discover -s tests -t .    tests (133, ~22 s)
python -m bench.extraction | bench.deals_truth | bench.alternatives | bench.missions | bench.scale | bench.autonomy
          | bench.profiles [--scale]           mesures
ESBUILD=<esbuild> REACT_DIR=<node_modules> ./web/build.sh          reconstruire web/app.html
```
`--db` (avant la commande) choisit la base ; réglages par variables `DEALS_*` (`deals/config.py`,
`deploy/deals.env.example`). Les commandes qui lisent les sites exigent `DEALS_USER_AGENT` (nom du robot, contact).

## API `/api/r/` (contrat de l'app)
Lecture ouverte : `today?category=&q=` (remises du jour), `top` (top deals de l'accueil ; `why` : la remise, le prix
bas et depuis quand), `search?q=&category=&min=&max=&off=&low=&sort=&recent=` (tout le catalogue suivi ; filtres :
catégorie, budget, promo : remise minimale en % ou `low=1`, prix parmi les plus bas ; tri : `relevance`, `price`,
`discount` ; `categories` : les catégories trouvées et leur nombre ; `offs` : les produits de chaque palier de promo ; sans mot ni filtre, le feed, orienté par `recent` : les
dernières recherches gardées par le navigateur, séparées par `|`),
`categories` et `brands` (celles qui ont des remises ; `?all=1` : toutes), `brand/<nom>` et `category/<clé>` (tous
leurs produits, remises d'abord), `item/<id>`,
`out/<offer_id>?from=`, `missions/parse` {text} et `missions/preview` {mission} (ce qui est compris, ce qui y répond
déjà ; une mission : `product_id`, ou `like` (comparables à ce produit), ou `category`, `brand`, `features`, `attrs` ;
et `max_price`).
Ajoutés depuis la v41 : `search`, `since` et `ends` (fiche), `alternatives` avec `saving` (fiche), `kind` (cartes :
catégorie au singulier), `history` (fiche : prix des 90 derniers jours) et `position` (fiche : le prix du jour sur ces
jours, voir plus bas), `published_at` (today : heure de la dernière publication), `saved_price` (favoris), `family`,
`best` et `products` (catégories), `best`, `products`, `top` et `categories` (marques), `attrs` (fiche : caractéristiques
lues, pour les missions) ; retiré en v49 : `specs` (la description n'est plus montrée) ;
`today?category=` accepte plusieurs catégories séparées par des virgules (univers, pièce).
Session requise (sinon 401) : `save`, `saves`, `brand/follow`, `follows`, `missions` (GET : les miennes et leur état ;
POST : lancer, ou changer le prix d'une même cible), `missions/delete` {id}.
Comptes : `auth/request` {email}, `auth/verify?token=` (pose le cookie, ou renvoie vers `/?auth=expired`), `auth/me`
(et `variant` : `p` personnalisé, `t` témoin), `auth/logout`.
Goûts (v55) : `today`, `top`, le feed de `search` et `foryou` (« pour vous » : les deals et prix bas de vos rayons et de
vos marques, dix au plus ; `taste` : ce que l'app a compris) suivent le profil. Sans compte, l'app envoie `p` (fiches
ouvertes `v<id>.<âge en jours>`, clics `c…`, au plus 60), `i` (rayons choisis, séparés par des virgules) et `v=t`
(témoin) ; le serveur n'en garde rien. `profile` : rayons choisis, ce qui est compris, apprentissage, variante ; avec un
compte : `interests` {categories} (rayons choisis, douze au plus, la liste remplace la précédente), `profile` {learn}
(tenir compte des fiches ouvertes et des clics, ou non), `profile/reset` (oublier ce qui a été déduit). `view` {v} et
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
  prix et le prix barré. Les durées (depuis quand, jusqu'à quand) et le verdict de prix ne sont que dans la fiche. La
  qualité est implicite. Aucune description technique ni autre enseigne : elles sont chez l'enseigne, qui est proposée
  seule (la moins chère, disponible).
- **Le prix du jour sur les derniers mois** (fiche) : face au meilleur prix de chaque jour relevé (toutes enseignes
  suivies, jusqu'à 90 jours, aujourd'hui exclu), « Au plus bas depuis N mois » si aucun jour n'était moins cher et que
  le prix était plus haut au moins un jour sur deux ; « Un des prix les plus bas » s'il est moins cher qu'au moins 2
  jours sur 3 ; « Plus cher que d'habitude » s'il est plus cher qu'au moins 2 jours sur 3 (« Souvent à X € », la
  médiane) ; « Son prix habituel » sinon, prix immobile compris ; rien avant 14 jours relevés. « N mois » est arrondi en
  dessous. La jauge va du plus bas au plus haut relevés ; le point place le jour parmi les jours relevés, dans la zone
  du verdict (`catalog.position`).
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
- **Recherche** : tout le catalogue suivi, pas seulement les remises, pour une intention précise ; filtres catégorie,
  budget et remise minimale, même sans mot ; tri par pertinence (d'abord les produits dont la requête nomme la
  catégorie ou la marque, puis les remises, puis le prix), par prix croissant ou par remise ; insensible aux accents, à
  la casse et aux tirets, synonymes courants (frigo, sofa, congélo…). Jamais vide : sans mot ni filtre, un feed (les
  produits des quatre dernières recherches d'abord, puis ceux de vos rayons et de vos marques, un sur quatre pris
  ailleurs, puis tout le catalogue, une catégorie à tour de rôle), que chaque mot, filtre ou tri adapte.
- **Marque et catégorie** (fiche) : deux étiquettes sur le visuel, qui mènent à tous les produits de la marque ou de la
  catégorie, les remises d'abord, même sans remise aujourd'hui.
- **Missions** : une envie et un prix maximum, pour un produit, ses comparables (même catégorie, mêmes fonctions, même
  taille ou capacité) ou ce que dit une phrase. Ce qui est dit est exigé, ce qui ne l'est pas ne l'est pas : catégorie,
  marque, fonctions (balai, sans fil…), capacité, couverts, foyers, places, volume, autonomie au moins ; taille de
  literie exacte ; largeur à 6 % près ; bruit au plus ; classe énergie au moins. Un produit remplit une mission s'il est
  disponible, au prix voulu et conforme (une caractéristique demandée mais inconnue du produit : pas de promesse). Une
  phrase sur une catégorie non suivie est refusée en le disant ; un prix impossible n'est pas retenu, il est demandé.
  Une mission par cible (relancer change le prix), 20 par personne. La nuit, après la publication : un e-mail au plus
  par personne, avec les produits arrivés à son prix ou descendus plus bas qu'au dernier e-mail (les cinq moins chers
  par mission, les autres dans l'app) ; jamais deux fois le même produit au même prix ; rien pour ce qu'elle voyait déjà
  en lançant la mission ; au-delà du plafond de la nuit (`DEALS_MISSION_MAILS`), la suite part la nuit suivante
  (`deals/missions.py`).
- **Connexion au moment de l'action** (favori, suivre, lancer une mission), jamais à l'entrée ; une mission lancée
  avant la connexion attend avec le lien, sur le serveur, et démarre quand il est ouvert, sur n'importe quel appareil
  (l'e-mail la nomme : « Confirmez votre mission : … »). Lien à usage unique valable 15 min ; 5 liens
  par adresse et par heure, 20 par adresse IP, plafond quotidien global ; même réponse qu'un compte existe ou non ;
  seuls les hachages des jetons sont stockés.
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
avec l'heure de mise à jour, verdict de prix et sa jauge). Les visuels sont des illustrations originales par catégorie
(`web/src/art.jsx`) ; les photos des enseignes ne sont pas montrées tant que la question des droits n'est pas tranchée.
Téléphone d'abord, mosaïque de 4 à 5 colonnes sur ordinateur, contrastes et zones à toucher aux normes WCAG AA, bandeau
immobile si l'appareil demande moins d'animations, lien partageable vers chaque fiche (`/?p=<id>`). Quatre onglets :
Accueil (les top deals d'abord, l'encart facultatif « Qu'est-ce qui vous intéresse ? », « Pour vous », puis pièces,
marques en promo, sélection), Recherche (un champ, trois filtres dont Promo, un tri, un feed qui s'adapte), Missions,
Profil (les favoris, les marques suivies, vos rayons, ce que l'app a compris) ; « Comment ça marche » au pied de chaque
écran. Principe, écrans et mesures v41 à v55 : [`docs/UX.md`](docs/UX.md).

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

`DEALS_AFFILIATE` désigne un fichier JSON : clé d'enseigne (`deals/collect/retailers.py`) → règle de lien. Deux formes :
le gabarit du réseau, avec `{url}` (l'adresse de la fiche, encodée) et `{subid}` (l'identifiant du clic), ou des
paramètres ajoutés à l'adresse de la fiche (`tag=…&sub={subid}`) ; exemple : `deploy/affiliate.example.json`, gabarits
exacts dans l'espace affilié de chaque réseau. Seules ces enseignes sont lues la nuit et publiées ; un fichier mal formé
arrête le démarrage. Sans ce fichier (développement), tout est publié et les liens partent tels quels ; la démo simule
des enseignes partenaires.

## Collecte

Familles : **électroménager** (lave-linge, sèche-linge, lave-vaisselle, réfrigérateurs, congélateurs, fours, plaques,
hottes, cuisinières, aspirateurs, robots aspirateurs), **ameublement** (canapés, fauteuils, lits, armoires, tables, buffets, meubles TV, commodes),
**literie** (matelas, sommiers). Un titre qui commence par un accessoire ou un prix sous 100 € n'entre pas au catalogue.

Enseignes actives : Boulanger, Electro Dépôt, Ubaldi, Cdiscount, But, IKEA, Maisons du Monde, La Redoute, Vente-unique.
Désactivées, avec la raison dans `deals/collect/retailers.py` : Conforama (défi Cloudflare, prix chargés par le
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
  par nuit. Publication, alternatives et courbes de 90 jours comprises : ~2,5 s pour 3 000 produits.
- Base : quelques dizaines de Mo par an (seuls les changements sont écrits).
- Missions de la nuit : ~5,5 s pour 10 000 missions sur 3 000 produits (~2 s une nuit sans changement).
- Serveur : Hetzner CX23, 5,49 € HT + 0,50 € d'IPv4 = **5,99 € HT par mois** (tarifs d'août 2026).
- E-mails (connexion, et missions : au plus un par personne et par nuit) : Brevo gratuit jusqu'à 300 par jour, partagés
  par les deux plafonds (`DEALS_MAILS_PER_DAY` 250, `DEALS_MISSION_MAILS` 50) ; au-delà, une offre payante. Nom de
  domaine : quelques euros par an. Aucun proxy, aucune API payante, aucune IA.

## Limites connues
- Les taux de lecture réels par enseigne restent à mesurer depuis le serveur (`diagnose`) : l'environnement de
  développement n'a pas accès au web ; tout est vérifié sur faux sites locaux, corpus publics et pages-pièges.
- Pas de navigateur : un site dont les prix n'existent qu'après exécution du JavaScript reste illisible (Conforama).
- Une baisse sans prix barré n'est pas montrée (choix produit et juridique, voir `docs/AUDIT.md`).
- Les favoris choisis avant connexion ne sont pas repris (la connexion est demandée avant l'action) ; une mission, si,
  et les rayons choisis aussi.
- Personnalisation : des règles simples sur les rayons et les marques, pas de « ceux qui ont aimé ceci » ni de budget
  appris ; sans compte, les fiches ouvertes ne sont gardées d'une visite à l'autre que si la personne l'accepte (Profil),
  et le témoin est tiré à chaque visite. Le gain mesuré par `bench.profiles` repose sur un modèle de clic : le vrai
  gain se lit sur les témoins en production (`metrics`, `by_variant`).
- Exploitation : l'agent prévient le responsable par le SMTP de la plateforme ; s'il tombe, seule une sonde extérieure
  sur `/api/r/health` le voit (à brancher, voir `docs/RUNBOOK.md#sonde`). L'agent conseille une règle de lecture quand
  une page change ; il ne l'écrit pas.
- Missions : prévenues par e-mail, la nuit, et dans l'app (onglet, cloche) ; pas de notification sur le téléphone (l'app
  est une page web, pas une app installée). Une phrase n'est comprise que dans ce que l'extraction sait lire (catégories
  suivies, marques présentes au catalogue, fonctions et tailles connues) : « une marque inconnue » ou « un joli
  canapé » n'ajoutent rien à la mission, et l'aperçu montre exactement ce qui a été compris.
- Alternatives : jugées sur ce que disent le titre et les caractéristiques déclarées par l'enseigne ; un critère absent
  des deux (puissance d'aspiration, matériaux, finition) n'est pas comparé. Un produit sans comparable dans le
  catalogue n'a pas de section (sur la démo de 59 produits, 27 fiches ; sur 3 000 produits, aucune).
