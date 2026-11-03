# L'interface de Promo Central (v67)

Une page (`web/src/App.jsx` → `web/app.html`, police incluse, aucune requête vers un tiers), téléphone d'abord,
quatre onglets : **Top deals** (ouvert au lancement), **Explorer**, **Recherche**, **Profil**. Ce document décrit
l'interface telle qu'elle est ; son
historique (mesures version par version, de la v41 à la v63, et leurs captures) est dans git :
`git log -p -- docs/UX.md`, et `git show 2ca25aa:docs/UX.md` pour la dernière version qui le contenait.

## Principe

**Le moins possible, pour aller vite au produit** (v65). Rien de plus que ce qui aide à décider vite : pas d'encadré,
pas de phrase d'explication (ni sous-titre, ni accroche, ni « pourquoi » sur les cartes, ni durée de la remise), pas de
bandeau défilant, pas de cloche. La carte dit le produit et son prix comme une étiquette : la remise en pourcentage, le
prix et le prix barré, l'économie en euros (« 151 € d'économie »). La qualité reste implicite : seulement des remises
réelles, aucune mention « vérifiée ». Deux entrées : **les belles remises du moment** (Top deals, Explorer) et **le
produit qu'on regarde** (la Recherche couvre tout le catalogue suivi) ; la fiche répond alors à « existe-t-il moins
cher, et aussi bien ? ».

**D'après la maquette du responsable** (v66). Une seule police, **Manrope**, partout : les titres ne sont plus dans un
serif étroit qui se lisait comme une italique. Des gris et deux couleurs : l'**action**, anthracite (`#3C3C3E`, texte
blanc : le bouton vers l'enseigne, la puce d'univers choisie, « Promo » dans le logo) et la **remise**, violet (`#C22EA2`,
le violet des remises de Pixmania assombri pour se lire : la pastille de remise, « Prix bas », l'économie). Le logo :
**Promo** anthracite, **Central** gris clair ; l'icône de l'onglet du navigateur, le « P » blanc sur l'anthracite.

**Des cartes à l'horizontale.** Une colonne au téléphone (deux puis trois à l'ordinateur), comme sur la maquette : le
visuel à gauche, carré ; à droite la marque et la pastille de remise, le nom (deux lignes), le prix et le prix barré,
l'économie. Ni cœur ni bouton sur la carte : toute la carte mène à la fiche, et c'est sur la fiche qu'on garde un
produit (le cœur) et qu'on va chez l'enseigne. Les carrousels (« Pour vous », « Moins cher, comparable ») prennent les
mêmes cartes.

**Affiner en entonnoir.** Une question à la fois, du plus large au plus précis : l'univers (High-tech, Entretien,
Chambre, Salon, Cuisine, Buanderie), le rayon, le type, un attribut du rayon (« Taille d'écran ? », « Définition ? »),
le budget ; chaque réponse dit combien de produits elle donne, et les donne. Une question qui ne resserre pas la
sélection n'est pas posée ; **« Passer »** (une bulle colorée) passe à la suivante ; quand il n'y a plus de question,
ou que la sélection tient en trois produits, c'est la fin : **votre sélection**, et « Sauvegarder ». Le même entonnoir
est dans la Recherche, sur la page d'une marque, d'une catégorie et d'une pièce, dans les teintes de la page (fond gris
clair, options blanches). Règles : `deals/funnel.py`, [`RECHERCHE.md`](RECHERCHE.md).

**Une Recherche qui comprend.** Une phrase comme on la dit (« aspirateur balai sans fil sous 300 € ») devient des
critères : les étapes de l'entonnoir, et en puces ce qu'il ne montre pas (la marque, la promo, le tri, les mots), que
l'on retire d'une croix. Jamais d'impasse : rien sous le budget, les plus proches au-dessus ; des mots sans produit,
dits, et le reste répond. Dans chaque rayon, le type et ses attributs sont lus dans ce que l'enseigne déclare de son
offre, jamais devinés ([`ONTOLOGIE.md`](ONTOLOGIE.md)).

**Garder sans e-mail.** Favoris (le cœur de la fiche), marques suivies, rayons et recherches sauvegardées se gardent
d'un geste, sans e-mail (un compte invité pour l'appareil) ; l'e-mail, facultatif, sert aux nouveautés de vos
recherches, la nuit, et à retrouver ses choix sur un autre appareil. Une recherche sauvegardée est une **mission** : la
plateforme la surveille et dit ce qui est nouveau. Les recherches sauvegardées vivent dans le **Profil**, le centre de
commande ; l'onglet Profil compte celles qui ont du nouveau. « Me prévenir sous un prix » (l'alerte sur un produit ou
ses comparables, depuis la fiche) est arrêté en v65 : on ne peut plus en poser, et celles d'avant ne sont ni montrées
ni envoyées (`deals/missions.py`).

**Vos goûts d'abord, l'intérêt du deal toujours.** Sans onboarding : vos rayons (choisis d'un geste), vos marques, ce
que vous gardez et regardez. Vos deals passent devant, au plus × 1,5 ; une place sur quatre reste au meilleur deal du
jour ; une visite sur dix est témoin. Le Profil dit ce que l'app a compris et permet de l'oublier
([`PERSONNALISATION.md`](PERSONNALISATION.md)).

**La conversion d'abord.** Le modèle est l'affiliation : seules les offres d'enseignes partenaires sont montrées ; le
geste qui rapporte est le clic vers l'offre. Sur la fiche, le bouton vers l'enseigne vient juste sous le prix et
l'économie, anthracite : c'est le plus visible de l'écran. La transparence (« Offres d'enseignes partenaires, remises
vérifiées », « Comment ça marche », « Mentions légales ») est au pied du **Profil**, et seulement là (v65, choix du
responsable) ; à faire valider par le juriste avant l'ouverture ([`PRODUCTION.md`](PRODUCTION.md), P1-10).

**Les visuels** sont des **illustrations originales** par catégorie (`web/src/art.jsx`), déclinées par produit
(couleurs, proportions de l'objet). Aucune image extérieure, aucun droit de tiers. Dans une carte, le cadre est carré :
un objet haut (réfrigérateur, aspirateur) y tient entier, un objet large (lit, téléviseur) le remplit. Sur la fiche,
le visuel aux coins arrondis reste nu : Retour, cœur et partage sont au-dessus. Les photos des produits : voir plus bas.

**Accessibilité.** Contrastes WCAG AA (le texte blanc sur l'anthracite : 11 : 1 ; le violet sur le blanc et le blanc
sur le violet : 5 : 1 ; le texte secondaire : 5,1 : 1), zones à toucher de 44 px au moins, un nom pour chaque bouton et
chaque champ, chaque carte nommée par sa marque, son nom, son prix et sa remise, espaces insécables du français.

## Ce que montre chaque écran

| Écran | Contenu |
|---|---|
| En-tête | le logo (« Promo » anthracite, « Central » gris clair), qui ramène à Top deals ; à l'ordinateur, les quatre onglets. Pas de cloche (v66 : l'onglet Profil compte les recherches qui ont du nouveau) |
| Top deals | le premier onglet, ouvert au lancement : « Top deals » ; les univers, **Tout** puis ceux qui ont des top deals ce jour-là (v67 : servis par `/api/r/catalog` ; **Électroménager**, **Maison** — ameublement et literie —, **High-tech**) ; puis les top deals de l'univers en cartes (dix au plus, la plus forte remise d'abord, puis un prix bas, et ainsi de suite ; la règle est la même dans un univers) |
| Explorer | « Explorer » ; **pour vous** (les deals et prix bas de vos rayons et de vos marques, top deals compris, en carrousel), **inspirations du moment** par pièce (les pièces de vos rayons d'abord, puis les plus fournies en remises ; v67 : servies par `/api/r/catalog`, avec le produit de leur meilleure remise pour visuel), **les marques en promo** (même format), **notre sélection** en cartes (les autres remises : ni top deals, ni « pour vous »). Ni bandeau défilant (v66) ni recherche : elle est dans son onglet |
| Carte | le visuel carré à gauche ; à droite la marque et la pastille de remise (« −20 % », violet ; « Prix bas » pour un prix bas sans remise), le nom (deux lignes), le prix et le prix barré, l'économie (« 151 € d'économie ») ; « 28 € de moins » sur une alternative (au lieu de l'économie : c'est ce qu'on gagne sur le produit de la fiche) ; « Baisse de 64 € » sur un favori. Ni cœur ni bouton : toute la carte ouvre la fiche |
| Fiche | Retour, cœur (garder), partager, au-dessus du visuel ; le visuel aux coins arrondis ; **la marque et la catégorie**, qui mènent à tous leurs produits ; le nom ; la remise, le prix et le prix barré ; l'économie ; **« Voir l'offre chez … »** (l'enseigne partenaire la moins chère et disponible, la seule montrée), anthracite ; la livraison que le flux donne (v67 : « Livraison offerte », « Livraison : 4,99 € », ou « Livraison selon le marchand » s'il ne la donne pas), « Retours selon le marchand » ; **moins cher, comparable** ; à défaut, produits similaires |
| Recherche | le champ, qui comprend une phrase (« aspirateur balai sans fil sous 300 € » : les étapes « Aspirateurs », « Balai », « Sans fil », « Moins de 300 € ») ; **Promo** et **Trier** ; en puces, la marque, la promo, le tri et les mots, et « Tout effacer » ; **l'entonnoir** ; avant toute saisie, **vos recherches récentes** (« Effacer ») ou « Essayez » et cinq exemples, puis le **feed** (« À découvrir » ou « Pour vous ») ; dès qu'on tape ou choisit : « 3 produits », **« Sauvegarder »** (« Recherche sauvegardée dans votre Profil »), les cartes ; des mots sans produit, dits, et le reste de la recherche ; rien sous le budget : « Rien à moins de 300 € », les plus proches au-dessus, et « Sauvegarder » ; rien du tout : « Rien pour « xyzzy » » et « Sauvegarder », puis le feed ; un rayon non suivi : « Les smartphones ne sont pas encore suivis » |
| Affiner (l'entonnoir) | « AFFINER », des traits (fait, en cours, à venir) ; les **étapes franchies** (« High-tech × », « Téléviseurs × » : la croix revient avant elle) ; **la question** (« Quel univers ? », « Quel rayon ? », « Quel type ? », « Taille d'écran ? », « Votre budget ? ») et ses réponses, chacune avec son nombre (« OLED 3 ») ; **« Passer »** ; à la fin, « VOTRE SÉLECTION », « 3 produits », « Sauvegarder » (sur une page : « Recommencer ») ; rien ici : « retirez une étape » |
| Marque, catégorie, pièce | « 1 remise aujourd'hui · 7 produits » ; suivre la marque ; une catégorie rejoint vos rayons ; **l'entonnoir** (une marque : « Quel rayon ? », ou « Quel univers ? » au-delà de six rayons ; une marque d'un seul rayon : ses questions d'emblée ; une catégorie : ses questions ; une pièce : « Quel rayon ? ») ; le tri (remises d'abord, prix croissant, décroissant) ; les cartes ; ce qu'on y a choisi reste quand on ouvre une fiche et revient |
| Ajouter son e-mail | facultatif : « Pour recevoir par e-mail les nouveautés de vos recherches et retrouver ce que vous gardez sur un autre appareil » ; un lien, aucun mot de passe ; le lien rattache l'adresse à ce qui est gardé ici, ou verse ce qui est gardé ici dans le compte qui a déjà cette adresse |
| Profil | le centre de commande, des titres seuls et beaucoup d'air ; « Gardé sur cet appareil, sans e-mail. Ajouter mon e-mail » (ou « Connecté avec … ») ; **vos recherches** sauvegardées (ce qui y répond, « 5 NOUVEAUX », la cloche pour l'e-mail de la nuit, la croix ; atteinte, « Voir l'offre · 175 € chez … », anthracite) ; **vos favoris** (gardés depuis la fiche) ; **vos marques** ; **vos rayons**, repliés (« Vos rayons · 2 choisis ») ; **ce que l'app a compris** et « Oublier » ; « Me reconnaître à mon retour » ; « Effacer mes données », « Se déconnecter » ; au pied, et sur aucun autre écran : « Offres d'enseignes partenaires, remises vérifiées. Comment ça marche · Mentions légales » ; l'onglet compte les recherches qui ont du nouveau |
| Comment ça marche | depuis le Profil : quelles offres (enseignes partenaires seulement, prix relus chaque nuit, remises réelles seulement), dans quel ordre, comment Promo Central est rémunéré (une commission, sans effet sur le prix ni sur le classement), vos données |
| Mentions légales et données personnelles | depuis le Profil : l'éditeur, le directeur de la publication, l'hébergeur, le contact (lus dans `DEALS_LEGAL_…` ; en développement, « à compléter » ; en production, l'app ne démarre pas sans eux), ce que la plateforme garde, pourquoi, combien de temps, vos droits |
| Démonstration (`DEALS_ENV=demo`) | une ligne noire en haut de chaque page, avant l'app : « Démonstration : données fictives, aucune offre réelle. » ; dans le flux, elle ne recouvre rien (v64 : fixée en bas, elle cachait la barre d'onglets d'un téléphone et prenait ses gestes) |

## Ce qui vient du catalogue (v67)

Rien du catalogue n'est écrit dans le front : les univers de Top deals, les pièces d'Explorer, les exemples de la
Recherche (des phrases tirées des remises du jour, relues par la Recherche avant d'être proposées) et les familles
suivies (« Comment ça marche », un rayon non suivi) viennent de `/api/r/catalog`, recalculé à chaque publication. Une
nuit qui ajoute ou retire une enseigne, une marque, un rayon ou une famille ne demande aucun changement du front. Un
onglet resté ouvert se relit quand on y revient (ou toutes les 10 minutes) si la nuit a publié ; un lien vers un
produit qui n'est plus publié dit « Ce produit n'est plus en vente chez nos partenaires. » et mène aux top deals.
`tests/test_architecture.py` refuse dans `App.jsx` toute clé du catalogue (rayon, famille, pièce, univers) et tout nom de
famille, de pièce ou d'univers.

## À décider : les photos des produits

Les flux des enseignes donnent l'adresse de la photo de chaque produit (`image_link`). v67 : elle est publiée avec le
catalogue (en https) et l'app la montre si `DEALS_PHOTOS=1` (le visuel carré des cartes, celui de la fiche, les grandes
cartes d'Explorer), chargée depuis le serveur de l'enseigne sans dire d'où vient la personne ; une photo qui ne se
charge pas laisse l'illustration. Réglage par défaut : `0`, les illustrations, tant que ces points ne sont pas tranchés :
les droits d'usage prévus par chaque programme d'affiliation, et la requête vers un tiers à chaque ouverture (l'adresse
IP des visiteurs transmise à l'enseigne ; la page des mentions le dit d'elle-même quand les photos sont montrées) ; la
copier sur notre serveur l'éviterait
(stockage, bande passante). Les illustrations restent le repli d'un produit sans photo.

## Vérifier

À chaque livraison, dans un vrai navigateur (Chromium), sur la démo nourrie par flux (`python deals.py demo`) : le
parcours complet (85 étapes : accueil, Recherche et entonnoir, pages marque, catégorie et pièce, fiche, alerte,
sauvegarde, e-mail facultatif, Profil, témoin, ordinateur, mouvement réduit) et l'audit d'accessibilité (92 écrans,
téléphone et ordinateur : contrastes, zones à toucher, noms). Dernier passage complet : v63, 85/85 et 0 défaut. Leurs
scripts ne sont pas dans le dépôt ; depuis, des contrôles ciblés :

- v64 (quatre onglets) : 18 contrôles dans Chromium.
- v65 (le moins possible) : 38 contrôles. Mesures, téléphone de 390 × 844, v64 → v65 : mots hors produits, Top deals
  20 → 4, Explorer 29 → 11 ; bouton vers l'enseigne sur les mêmes 22 fiches, médiane 534 → 478 px ; bandeau de démo
  sur la barre d'onglets 50 → 0 px.
- v66 (la maquette) : 43 contrôles dans Chromium, téléphone et ordinateur : le logo et ses gris, plus de cloche, une
  seule police, les univers de Top deals (High-tech : seulement l'électronique), les cartes à l'horizontale (le visuel à
  gauche, ni cœur ni bouton, l'économie = prix barré − prix, « Prix bas », le violet), Explorer sans bandeau défilant,
  la fiche (Retour, cœur, partage au-dessus du visuel ; marque et catégorie avant le nom ; remise, prix, prix barré ;
  économie ; bouton anthracite dans le premier écran ; livraison et retours), le cœur de la fiche qui garde le produit
  et le Profil qui le montre, les mentions au Profil seulement, l'origine « top » d'un clic, Retour, trois cartes par
  ligne à l'ordinateur, aucune erreur. Mesures, v65 → v66 : Top deals, premier produit 159 → 208 px (la ligne des
  univers), 4 → 3 cartes entières au premier écran (des cartes plus larges, le nom en entier) ; bouton vers l'enseigne
  sur les mêmes 22 fiches, médiane 478 → 568 px (la barre au-dessus du visuel, la marque et la catégorie avant le nom),
  toujours entier dans le premier écran (22/22) ; la page passe de 403 à 341 ko (deux polices de moins).
- v67 (le front lit le catalogue) : l'épreuve des refresh — la démo (75 nuits), puis 6 vraies nuits où l'électronique
  quitte les flux et une enseigne nouvelle arrive (une marque jamais vue, photos et livraison dans son flux), serveur
  jamais redémarré. Avant → après : la puce « High-tech » sans produit 1 → 0 ; exemples de la Recherche qui ne trouvent
  rien 2/5 → 0/5 ; livraison du flux montrée non → oui ; photo du flux montrée jamais → si `DEALS_PHOTOS=1` (une photo
  qui ne se charge pas laisse l'illustration) ; onglet resté ouvert relu au retour non → oui ; lien vers un produit
  retiré : un message clair. Clics jusqu'au marchand inchangés (lien partagé 1, Top deals 2, Explorer 3, Recherche 3 et
  la saisie, pièce 4), 10 parcours sur 10 arrivés chez le marchand. Les 43 contrôles de la v66 passent, et 14 + 13
  contrôles de la v67 (photos montrées, puis non).
