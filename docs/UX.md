# L'interface de DEALS — un flux vivant de remises, une recherche qui comprend, vos goûts, vos besoins (v57)

## Principe

**Trois portes, un besoin compris (v57).** L'accueil ouvre trois portes, une par intention : **Rechercher** (« Dites
ce qu'il vous faut, même un besoin »), **Les bonnes affaires** (les vraies remises du jour) et **Explorer** (« Par type,
par usage », sans rien régler). Aucun tunnel : chaque porte mène à un écran complet, d'où l'on passe aux autres. Dans un
domaine qui a son ontologie (les aspirateurs, pilote), la Recherche comprend un **besoin** (« pour mon chat avec du
parquet ») : il devient des puces « Pour … », un encadré dit ce qu'il demande et d'après quels mots, chaque carte dit
pourquoi elle est là (« ✓ Brosse pour les poils », « ? Brosse pour parquet non précisée »). Une demande vague reçoit une
**question** utile, qui ne bloque rien (« Comment voulez-vous faire le ménage ? », cinq réponses avec leur nombre de
produits, « Passer ») ; une demande précise n'en reçoit jamais. Un type qui ne peut pas répondre (« robot pour les
escaliers ») garde sa sélection, et un **autre type est proposé** avec sa raison ; une référence vient en premier ; un
besoin sans exception dit ce qu'il écarte. La fiche ajoute **« L'essentiel »** : ce qui décide pour ce type, chaque
valeur avec sa source, « Non précisé » quand la page ne le dit pas. Règles : `docs/ONTOLOGIE.md`.

**Pinterest × Bloomberg.** Pinterest pour donner envie : des visuels, une mosaïque, l'inspiration par pièce. Bloomberg
pour la vie et la décision : un bandeau où défilent les remises du jour avec l'heure de mise à jour, et dans chaque fiche
le prix du jour situé sur les derniers mois, en mots et d'un coup d'œil (« Au plus bas depuis 2 mois », une jauge).

Les visuels sont des **illustrations originales** par catégorie (`web/src/art.jsx`), déclinées par produit (couleurs
tirées du produit, proportions de l'objet : une armoire est haute, un canapé est large, d'où la mosaïque). Aucune image
extérieure, aucune requête vers un tiers, aucun droit de tiers. Les photos des enseignes sont lues par l'extraction mais
pas montrées : c'est une décision à prendre (droits, vie privée, coût), voir plus bas.

La qualité reste implicite : seulement des remises réelles, aucune mention « vérifiée ». Les durées (depuis quand,
jusqu'à quand) restent dans la fiche. Deux entrées : **les belles remises du moment** (l'accueil) et **le produit qu'on
regarde** (la recherche couvre tout le catalogue suivi) ; la fiche répond alors à « existe-t-il moins cher, et aussi
bien ? » (« Moins cher, comparable », règles : `deals/alternatives.py`) et à « est-ce le bon moment ? » (le verdict de
prix, règle : `catalog.position`).

**Trouver vite, garder sans e-mail (v56).** DEALS n'est pas un fil de bons plans à faire défiler : on vient chercher
quelque chose. La **Recherche comprend une phrase** comme on la dit (« aspirateur balai sans fil sous 300 € ») et la
montre en **puces** — le rayon, les fonctions, la taille, la marque, le budget, la promo — que l'on retire d'une croix ou
que l'on change dans **Affiner**, où chaque choix dit ce qu'il donnerait. Jamais d'impasse : rien sous le budget, les
plus proches au-dessus ; des mots sans produit, dits, et le reste de la recherche répond ; rien du tout, on le dit et on
propose de surveiller. Une recherche se **sauvegarde** d'un geste (c'est une mission : DEALS la surveille, le prix est
facultatif) et dit ensuite ce qui est nouveau. Tout ce qu'on garde — favoris, marques, rayons, recherches, alertes de
prix — se garde **sans e-mail** (un compte invité pour l'appareil) ; l'e-mail, facultatif, sert aux alertes et à
retrouver ses choix ailleurs. Le **Profil** devient le centre de commande ; trois onglets (Accueil, Recherche, Profil).
Règles et mesures : `docs/RECHERCHE.md`.

**L'accueil inspire, la recherche répond (v49 à v56).** L'**Accueil** est éditorial : le bandeau, les top deals, « Pour
vous », les inspirations par pièce, les marques en promo (au même format que les pièces), notre sélection ; aucun outil
de recherche en haut, une seule entrée après deux rangées (« Une envie précise ? », une phrase qui ouvre la Recherche).
La **Recherche** répond à une intention précise : un champ qui comprend, les critères en puces, Affiner, des résultats en
mosaïque. Elle n'est jamais vide (v51) : avant toute saisie, vos recherches sauvegardées, vos recherches récentes ou des
exemples, puis un **feed** qui montre l'étendue du catalogue, une catégorie à tour de rôle, ou « **Pour vous** » ;
chaque lettre ou critère l'adapte sur place, sans écran blanc. Une marque tapée s'ouvre en raccourci au-dessus des
résultats. Les pages d'une marque et d'une catégorie se trient (remises d'abord, prix croissant, décroissant). La fiche ne garde que ce qui sert la
décision : le prix, le verdict de prix, l'enseigne la moins chère, l'alerte, les comparables moins chers ; la description
technique et les autres enseignes restent chez l'enseigne.

**Vos goûts d'abord, sans rien bloquer (v55, v56).** L'app apprend ce qui intéresse chacun, sans onboarding : vos
rayons, choisis d'un geste dans le Profil ou sur la page d'une catégorie (« Mes rayons » ; en v55, un encart sous les
top deals, qui a rejoint le Profil en v56 : l'accueil reste aux deals), et, en naviguant, les fiches ouvertes, les clics
vers l'enseigne, les recherches, les favoris, les marques suivies, les recherches sauvegardées. Ses deals passent alors devant (au plus × 1,5 : l'intérêt du deal prime, et une place
sur quatre reste au meilleur deal du jour) ; « **Pour vous** », sous les top deals, montre les deals et les prix bas de
ses rayons et dit pourquoi (« Vos rayons : Canapés, Matelas ») ; le feed de la Recherche les suit aussi. Le Profil dit
ce que l'app a compris, permet de l'oublier et de décider de ce qu'elle retient (règles et vie privée :
`docs/PERSONNALISATION.md`).

**Le meilleur d'abord (v53).** L'accueil s'ouvre sur les **top deals** : les plus fortes remises réelles et les produits
dont le prix est parmi les plus bas depuis au moins deux mois (au moins 10 % sous leur prix habituel, même sans
promotion déclarée), à tour de rôle ; chaque carte dit pourquoi elle est là (la remise, « Au plus bas », « Parmi les plus
bas »), et notre sélection ne les répète pas. La Recherche filtre par **promo** : un palier de remise (−10 % à −50 %) ou
les prix parmi les plus bas, chaque choix avec son nombre de produits, seuls ceux qui donnent quelque chose. Les favoris
sont une partie du **Profil** : quatre onglets.

**La conversion d'abord (v52).** Le modèle est l'affiliation : seules les offres d'enseignes partenaires sont montrées,
et le geste qui rapporte est le clic vers l'offre, suivi d'un achat. L'app aide à décider : savoir quels deals existent
(l'accueil), être compris (le feed « Pour vous », les missions), acheter au bon moment (le verdict de prix). Les
**missions** sont le moteur : qui a dit ce qu'il veut et son prix est le plus engagé ; une mission atteinte mène à
l'offre en un geste, l'e-mail de la nuit aussi ; depuis la v56, une recherche sauvegardée ou une alerte de prix est une
mission, posée sans e-mail. Tout se mesure : fiches vues et clics, par écran et
par personne ; l'identifiant de chaque clic part chez le réseau, qui rattache la vente. Et c'est dit : « enseigne
partenaire » près de l'offre, « Comment ça marche » au pied de chaque écran.

**Continuer, puis guetter (v48).** Arriver sur un produit, c'est s'intéresser à sa marque ou à sa catégorie : elles sont
posées sur le visuel de la fiche comme des étiquettes et mènent à tous leurs produits, remises d'abord, même quand la
marque n'a aucune remise aujourd'hui (plus de cul-de-sac). Et si ce n'est pas le bon prix : « Me prévenir sous un prix »,
pour ce produit ou pour tous les comparables (même catégorie, mêmes fonctions, même taille), avec trois prix proposés
(le plus bas des derniers mois, −10 %, −20 %). Plus largement, **une mission** : une envie et un prix en une phrase
(« aspirateur balai sous 300 € ») ; l'app dit ce qu'elle a compris et ce qui y répond déjà, et un e-mail part la nuit où
c'est le cas (`deals/missions.py`). Un onglet à part entière, un module dans le flux de l'accueil, la cloche qui compte
les missions atteintes.

Gardé des versions précédentes : le produit comme entrée (l'enseigne n'est qu'un attribut), un deal identique pour tous,
le suivi des marques, contrastes et zones à toucher aux normes. Retiré de la v56 : la connexion demandée au moment de
l'action (tout se garde sans e-mail), l'onglet Missions (les recherches sauvegardées et les alertes sont dans le
Profil), l'encart de l'accueil (dans le Profil). Retiré de
la v46 : la liste à pictogrammes et le regroupement par marque × catégorie (les cartes portent un visuel et un nom
court, qui suffisent à départager), le signet (remplacé par le cœur).

## Ce que montre chaque écran

| Écran | Contenu |
|---|---|
| Accueil | bandeau défilant (« MAJ 14 déc. 11:00 », marque, catégorie, remise, prix ; immobile si l'appareil demande moins d'animations), « De bonnes affaires, pour vos envies. », **trois portes** (Rechercher, Les bonnes affaires : la Recherche en promo, par remise, Explorer), **top deals** (« Remises et prix bas » : jusqu'à dix cartes à faire défiler, la plus forte remise d'abord, puis un prix bas, et ainsi de suite), **pour vous** (les deals et prix bas de vos rayons et de vos marques, sans répéter les top deals : « Vos rayons : Canapés, Matelas », « D'après vos recherches : Aspirateurs » ou « D'après vos visites : Canapés », et « Modifier », qui mène au Profil), **inspirations du moment** par pièce (Chambre, Salon, Cuisine, Buanderie, Entretien : « Jusqu'à −20 % » et les catégories ; les pièces de vos rayons d'abord), **les marques en promo** (même format : le produit de la meilleure remise, « Jusqu'à −19 % », les catégories), **notre sélection** en mosaïque (les autres remises) ; après deux rangées, **« Une envie précise ? »** : une phrase, qui ouvre la Recherche déjà comprise |
| Carte | visuel, remise sur le visuel, cœur, marque, nom (une ligne), prix en orange et prix barré ; « Baisse de 64 € » sur un favori ; « 481 € de moins » sur une alternative ; dans les top deals, « Au plus bas » ou « Parmi les plus bas », et « Prix bas » sur le visuel d'un produit sans remise |
| Pièce | ses remises en mosaïque |
| Explorer | « Par type, par usage : rien à régler, tout se précise ensuite. » ; chaque domaine qui a son ontologie : son chemin (« Maison › Entretien › Aspirateurs »), « 33 produits · dès 39 € · 5 remises », « Tout voir » ; **Quel type ?** (une carte par type : « Robots aspirateurs · Dès 143 € · Il passe tout seul, même en votre absence ») ; **Pour quel usage ?** (« Poils d'animaux 7 », « Escaliers 6 »… : les produits qui conviennent tout à fait) ; puis tous les rayons, par pièce ; chaque geste ouvre la Recherche avec ce critère |
| Fiche | grand visuel, partager (lien vers la fiche), cœur, **étiquettes marque et catégorie** posées sur le visuel ; nom ; remise, prix, prix barré ; **le verdict de prix** (« Au plus bas depuis 2 mois », « Un des prix les plus bas… », « Son prix habituel », « Plus cher que d'habitude » + « Souvent à 482 € ces 2 derniers mois ») et sa jauge (du plus bas au plus haut relevés, un point pour aujourd'hui, dans la zone verte, jaune ou orange du verdict) ; « En remise depuis 3 jours, jusqu'au ven. 19 déc. » ; « Voir l'offre chez … » (l'enseigne partenaire la moins chère, la seule montrée), et dessous « Enseigne partenaire : si vous achetez, nous touchons une commission, sans surcoût pour vous. Comment ça marche » ; **« Me prévenir sous un prix »** (« Alerte à 550 € » une fois posée) ; dans un domaine qui a son ontologie, **« L'essentiel »** (« Aspirateur balai : ce qui décide » ; chaque caractéristique, dans l'ordre où elle décide pour ce type, avec sa valeur et sa source — fiche de l'enseigne, titre, nom du modèle, déduit, selon le type — ou « Non précisé » ; « Caractéristiques lues sur la page de l'enseigne le 1 oct. ; ce qui n'y est pas reste « non précisé », jamais deviné. ») ; **moins cher, comparable** ; à défaut, produits similaires |
| Me prévenir (alerte de prix) | pour : ce produit, ou tous les comparables (ce qui est guetté est dit : « Lit 160 × 200 ») ; prix maximum : trois prix proposés ou le sien ; ce qui en est aujourd'hui (« Aujourd'hui 612 € : encore 62 € », « 2 comparables déjà sous 550 € ») ; « Me prévenir sous 550 € » : posée tout de suite, sans e-mail (« Alerte à 550 € » sur la fiche, l'alerte dans le Profil) ; « Arrêter l'alerte à 550 € » |
| Marque, catégorie | tous leurs produits en mosaïque, remises d'abord, ou par prix croissant ou décroissant ; « 1 remise aujourd'hui · 7 produits » ; suivre la marque (« Suivre », « Suivie ») ; une catégorie rejoint vos rayons (« Mes rayons », « Dans vos rayons ») |
| Affiner | une feuille : le **rayon** (celui choisi, « Changer de rayon » déplie la liste), ses **fonctions** et ses **tailles** (celles du rayon : « Autonomie : 40 min et plus », « Capacité : 9 kg et plus »…), la **marque**, le **budget** (de… à…, ou moins de 200, 500, 1 000, 2 000 €), la **promo**, le **tri** ; chaque choix avec ce qu'il donnerait (« Balai 5 »), ceux qui ne donneraient rien ou ne changeraient rien ne sont pas proposés ; « Voir 5 produits », « Tout effacer » ; dans un domaine qui a son ontologie : le **type**, l'**usage**, ce qui décide pour ce type (« Filtre HEPA 1 », « Sans sac 1 · Avec sac 1 »), poids, bruit et autonomie par paliers (« 2,5 kg au plus ») |
| Ajouter son e-mail | facultatif : « Pour recevoir vos alertes par e-mail et retrouver vos favoris, vos marques et vos recherches sur un autre appareil » ; un lien, aucun mot de passe ; « Ouvrez le lien reçu » ; le lien rattache l'adresse à ce qui est gardé ici (rien n'est perdu), ou verse ce qui est gardé ici dans le compte qui a déjà cette adresse |
| Recherche | le champ, qui comprend une phrase (« aspirateur balai sans fil sous 300 € ») ; **Affiner** et les **puces** des critères compris ou choisis (« Aspirateurs », « Balai », « Sans fil », « Moins de 300 € » : toucher ouvre Affiner, la croix retire) et « Tout effacer » ; sans critère, **Catégorie**, **Budget**, **Promo** en accès direct ; avant toute saisie, **vos recherches sauvegardées** (une ligne, « 5 » sur celles qui ont du nouveau, « Tout voir » mène au Profil), **vos recherches récentes** (en mots lisibles : « Matelas · Moins de 500 € », « Effacer ») ou « Essayez » et cinq exemples, puis le **feed** (« À découvrir » ou « Pour vous ») ; dès qu'on tape ou choisit : la marque tapée en raccourci, « 3 produits » et **« Sauvegarder »** (« Sauvegardée » : un geste la retire), la mosaïque ; des mots sans produit : « « velours gris » : aucun produit ; voici le reste de votre recherche » ; rien sous le budget : « Rien à moins de 50 € · Les plus proches, dès 414 € » et « Me prévenir » ; rien du tout : « Rien pour « xyzzy » », « Pas encore là ? On surveille pour vous » et « Sauvegarder », puis le feed ; un rayon non suivi : « Les smartphones ne sont pas encore suivis » ; l'onglet touché à nouveau remonte en haut ; dans un domaine qui a son ontologie : les puces d'un type (« Robots aspirateurs ») et des besoins (« Pour Escaliers »), l'encadré de ce qui est compris (« Escaliers · Des escaliers : un aspirateur à main, ou un balai qui en devient un (d'après « escaliers ») · Une puce se retire d'un geste : rien d'autre n'est supposé. »), l'autre type proposé (« Un robot ne monte pas les marches. Voir les aspirateurs à main (3) »), la question d'une demande vague (« Comment voulez-vous faire le ménage ? » : « Il passe tout seul · Robot 8 »… et « Passer »), la référence (« Votre référence · Kessler Aspirateur balai sans fil Aero 12 Animal » et « Voir l'offre » en un geste), ce qu'un besoin sans exception écarte (« 22 produits écartés : ne lave pas le sol. »), et sur chaque carte jusqu'à deux raisons (✓ oui, ≈ en partie, ✗ non, ? non précisé) |
| Comment ça marche | quelles offres (enseignes partenaires seulement, prix relus chaque nuit, remises réelles seulement), dans quel ordre (chaque écran), comment Deals est rémunéré (une commission, sans effet sur le prix ni sur le classement), vos données ; joignable depuis le pied de chaque écran et depuis l'offre |
| Profil | le centre de commande : « Gardé sur cet appareil, sans e-mail. Ajouter mon e-mail » (ou « Connecté avec … », ou, avant tout geste, « Rien n'est gardé pour l'instant… J'ai déjà un compte ») ; **vos recherches** sauvegardées (ce qui y répond, « 5 NOUVEAUX », la cloche pour l'e-mail de la nuit, la croix ; toucher ouvre la recherche et oublie ses nouveautés) ; **vos alertes de prix** (en veille ou atteinte : « Voir l'offre · 175 € chez … » en un geste) ; **vos favoris** (« 2 baisses de prix ») ; **vos marques** (« Ajouter » : toutes les marques, à suivre d'un geste) ; **vos rayons** (un geste chacun) ; **ce que l'app a compris** et « Oublier » ; l'interrupteur (« Me reconnaître à mon retour » sans e-mail, désactivé par défaut ; « Tenir compte des fiches que j'ouvre » avec un e-mail) ; « Effacer mes données » (avec confirmation), « Se déconnecter » ; la cloche de l'en-tête et l'onglet comptent les recherches qui ont du nouveau (et les baisses des favoris) |

## À décider : les photos des produits

L'extraction lit déjà l'adresse de la photo de chaque produit (`products.image`, JSON-LD ou `og:image`). La montrer
demande un choix : la charger depuis le site de l'enseigne (requêtes vers un tiers à chaque ouverture, adresse IP des
visiteurs transmise, images parfois bloquées), la copier sur notre serveur (stockage et bande passante, et une
reproduction de photos dont les droits appartiennent aux marques ou aux enseignes), ou passer par les flux produits
que fournissent les programmes d'affiliation, photos comprises, à utiliser selon leurs conditions : depuis la v52
(affiliation), c'est la voie naturelle. Tant que ce n'est pas tranché, les illustrations tiennent la place ; elles
restent de toute façon le repli d'un produit sans photo.

## Historique

Retiré de la v43, à la demande (trop d'informations, lecture alourdie) : « Toutes vérifiées », « fausses promos
écartées », « Depuis hier » (nouvelles, finissent bientôt), le signal de chaque ligne (finit bientôt, nouveau, plus bas
depuis n jours, vérifiée), l'enseigne et le prix barré dans les listes, la date de relevé dans l'en-tête, le bloc
« Pourquoi c'est un vrai deal » de la fiche, les compteurs des catégories et des marques. Les données qui ne servaient
qu'à ces éléments ne sont plus calculées ni stockées (preuve, plus bas prix relevé, filtres « depuis hier »).

## Mesures v41 → v44 (mêmes données de démo, téléphone 390 × 844)

| | v41 | v43 | v44 |
|---|---|---|---|
| Mots sur le premier écran de l'accueil | 59 | 128 | 82 |
| Éléments par ligne de liste | 4 | 7 | **4** |
| Produits entièrement visibles sans défiler | 3 | 3 | **4** |
| Mots sur le premier écran de la fiche | 49 | 90 | 56 (dont la ligne des durées) |
| Remises d'une catégorie | 2 gestes | 1 geste | 1 geste |
| Aller chez l'enseigne depuis l'accueil | 2 gestes | 2 gestes | 2 gestes |
| Textes sous le contraste minimal WCAG AA (accueil · fiche) | 5 · 3 | 0 · 0 | 0 · 0 |
| Zones à toucher sous 44 px (accueil · fiche) | 5 · 6 | 0 · 0 | 0 · 0 |
| Requêtes vers un tiers à l'ouverture | 1 (Google Fonts) | 0 | 0 |
| Poids de la page | 218 Ko + police | 281 Ko | 267 Ko, police comprise |

Les mots en plus de la v41 sur l'accueil sont ceux des catégories et du quatrième produit visible ; une ligne porte
exactement autant d'informations qu'en v41.

## Mesures v44 → v45 : « je regarde ce produit, existe-t-il moins cher ? »

Mêmes données (démo du 14 décembre, 59 produits) et catalogue synthétique de 3 000 produits (`bench.scale`). Les
suggestions de la fiche sont jugées par une grille indépendante du code, écrite avant le moteur (`bench/alternatives.py`) ;
v44 = l'ancien calcul « Produits similaires » (caractéristiques proches, à défaut prix le plus proche).

| | v44 | v45 |
|---|---|---|
| Trouver un produit qui n'est pas en remise (recherche « v15 ») | 0 résultat | 1 résultat |
| Du produit regardé à une alternative moins chère | impossible | 2 gestes après la saisie (le résultat, l'alternative) |
| Suggestions incompatibles (démo · 3 000 produits) | 55 % · 1 % | **0 % · 0 %** |
| Fiches qui ont une alternative moins chère et la montrent (démo · 3 000) | 90 % · 63 % | **95 % · 100 %** |
| Économie moyenne montrée, pour une économie possible de 259 € (démo) · 398 € (3 000) | 223 € · 204 € | **243 € · 398 €** |
| Fiches sans suggestion (démo · 3 000) | 5 · 0 | 27 · 0 |
| Mots sur le premier écran : accueil · fiche d'un deal · fiche avec alternatives | 78 · 49 · — | 78 · 49 · 70 |
| Textes sous le contraste minimal · zones à toucher sous 44 px | 0 · 0 | 0 · 0 |
| Poids de la page | 267 Ko | 267 Ko |

Exemples de suggestions v44 écartées par la grille : un lave-vaisselle de 45 cm pour un 60 cm, un lave-linge de 8 kg
pour un 10 kg, un réfrigérateur américain de 91 cm pour un combiné de 60 cm, un matelas 140x190 pour un 160x200, un
canapé droit pour un canapé d'angle, un aspirateur balai pour un traîneau. La fiche manquée en v45 (démo) :
un four vapeur dont l'alternative est un four encastrable, écarté parce que la forme (encastrable) doit être la même.
Les 27 fiches sans suggestion de la démo n'ont aucun produit comparable dans un catalogue de 59 produits ; sur 3 000
produits, aucune fiche n'est vide.

Parcours vérifié dans un vrai navigateur (Chromium), 17 étapes, deux passages, dont : aucune durée ni mention de
vérification sur l'accueil, 4 éléments par ligne ; un produit sans remise trouvé par la recherche, sans badge ; sa fiche
montre « Moins cher, comparable » sur le premier écran, chaque ligne au moins 10 % moins chère et son économie égale à
la différence de prix ; une alternative s'ouvre, et son clic sortant est compté comme venu de « Moins cher,
comparable » (`deals.py metrics`, par source). Captures : `docs/ux/` (`5-alternatives.png` : v44 et v45 côte à côte).

## Mesures v45 → v46 : « trop de texte, on ne voit pas ce qui se passe »

Mêmes données (démo du 14 décembre), téléphone 390 × 844.

| | v45 | v46 |
|---|---|---|
| Mots sur le premier écran de l'accueil | 78 | **60** |
| Caractères par ligne de produit (accueil) | 62 | **26** |
| Lignes avec un pictogramme de catégorie | 0 sur 4 | **5 sur 5** |
| Caractéristiques (taille, capacité…) sur l'accueil | oui (« 160x200 », « 331 L »…) | **aucune** |
| Lignes pour 13 remises | 13 (deux « Nordvik, lit » à la suite) | **11**, une par marque × catégorie |
| Produits ou groupes entièrement visibles sans défiler | 4 | 5 |
| Recherche « aspirateur » : mots sur le premier écran · caractères par ligne | 78 · 52 | **51 · 25** |
| Fiche avec alternatives : mots sur le premier écran · caractères par alternative | 70 · 67 | **53 · 26** |
| Fiche d'un deal : mots sur le premier écran | 49 | 53 (la description y est maintenant) |
| Textes sous le contraste minimal · zones à toucher sous 44 px (tous les écrans) | 0 · 0 | 0 · 0 |
| Poids de la page | 267 Ko | 271 Ko |

Sur le catalogue synthétique de 3 000 produits, les 759 remises du jour tiennent en 538 lignes (177 groupes de plusieurs
produits). Le parcours navigateur v46 (19 étapes, deux passages) vérifie en plus : aucun titre ni caractéristique sur
l'accueil, un pictogramme par ligne, une ligne par marque × catégorie, un groupe qui s'ouvre sur ses produits
départagés, la description de la fiche, « Retour » qui ramène au groupe puis à l'accueil ; les mêmes contrôles échouent
sur la v45. Planche : `docs/ux/6-v46.png`.

## Mesures v46 → v47 : Pinterest × Bloomberg

Mêmes données (démo du 14 décembre), téléphone 390 × 844.

| | v46 | v47 |
|---|---|---|
| Part du premier écran de l'accueil occupée par des visuels | 5 % | **32 %** |
| Part de toute la page d'accueil occupée par des visuels | 5 % | **52 %** |
| Part du premier écran de la fiche occupée par des visuels | 1 % | **49 %** |
| Fraîcheur visible sur l'accueil | rien | bandeau défilant, heure de mise à jour |
| Prix sur 90 jours dans la fiche | non | courbe, plus bas, habituel, verdict |
| Mots sur le premier écran : accueil · fiche | 55 · 56 | 76 · 42 |
| Entrées entièrement visibles sans défiler (accueil) | 5 lignes | 2 pièces, la mosaïque commence dessous |
| Textes sous le contraste minimal · zones à toucher sous 44 px (7 écrans) | 0 · 0 | 0 · 0 ; texte blanc des pièces mesuré au pixel : 5,5:1 au pire |
| Requêtes vers un tiers à l'ouverture | 0 | 0 |
| Poids de la page | 271 Ko | 354 Ko (deux polices de plus, les illustrations) |

L'accueil porte plus de mots qu'en v46 : ceux du titre, du bandeau et des pièces de la maquette. La mosaïque porte, par
carte, la marque, un nom sur une ligne et le prix. Parcours vérifié dans un vrai navigateur (Chromium), 21 étapes, deux
passages : bandeau et compteur justes, une carte par remise (visuel, remise, prix, prix barré), un univers et une pièce
qui filtrent, recherche dans tout le catalogue, courbe et verdict, alternatives et leur économie, lien partagé qui
rouvre la fiche, durées et clic tracé, connexion, favori, tri d'Explorer, marque suivie dans Profil, mosaïque de 4
colonnes et plus sur ordinateur, bandeau immobile quand l'appareil demande moins d'animations. Planche :
`docs/ux/7-v47.png`.

## Mesures v47 → v48 : continuer depuis un produit, guetter son prix

Mêmes produits et mêmes prix (démo du 14 décembre, 59 produits), téléphone 390 × 844. Depuis chacune des 59 fiches, on
cherche à rejoindre la marque et la catégorie du produit ; « produits vus » additionne, fiche par fiche, ce que la page
atteinte montre de cette marque ou de cette catégorie.

| | v47 | v48 |
|---|---|---|
| Fiches d'où l'on rejoint la marque du produit | 40 / 59, en 3 gestes (Explorer, réglages, la marque) ; 19 fiches sans issue (marque sans remise : page introuvable) | **59 / 59, en 1 geste** |
| Produits de la marque vus depuis une fiche | 78 / 341 (23 %, les remises seulement) | **341 / 341** |
| Fiches d'où l'on rejoint la catégorie du produit | 36 / 59, en 2 gestes (Explorer, la catégorie) | **59 / 59, en 1 geste** |
| Produits de la catégorie vus depuis une fiche | 61 / 247 (25 %) | **247 / 247** |
| Être prévenu à un prix | impossible | depuis la fiche, 2 gestes (un prix proposé est déjà choisi) ; e-mail demandé la première fois |
| Une envie et un prix en une phrase | non | 37 / 37 phrases comprises (`python -m bench.missions`) |
| Part du premier écran occupée par des visuels : accueil · fiche | 32 % · 49 % | 31 % · 43 % |
| Mots sur le premier écran : accueil · fiche | 76 · 42 | 76 · 46 |
| Textes sous le contraste minimal · zones à toucher sous 44 px | 0 · 0 (7 écrans) | 0 · 0 (18 écrans) |
| Poids de la page | 354 Ko | 374 Ko |

Les 37 phrases : 25 écrites d'abord (toutes comprises), puis 12 tournures du quotidien ajoutées pour chercher les
failles ; 6 échouaient (« aspi », « 250 balles », « 160 sur 200 », « lit 2 places » pris pour des places assises,
« meuble télé », un prix impossible retenu, « TV » non reconnue) et ont été corrigées : ce second lot n'est donc plus une
mesure indépendante. Sur la fiche, les deux actions (« Voir l'offre », « Me prévenir ») font passer la courbe sous le
premier écran ; les étiquettes posées sur le visuel évitent d'y ajouter une ligne. Sur l'accueil, le point de moins
vient d'une correction : la première pièce n'est plus collée au bord de l'écran ; le module mission prend place après
deux rangées de remises, pour garder la mosaïque visible dès le premier écran.

La nuit, sur 10 000 missions de 2 000 personnes (catalogue de 3 000 produits) : 5,6 s la première nuit, 2,3 s une nuit
sans changement (`python -m bench.scale`) ; un e-mail au plus par personne, les cinq produits les moins chers par
mission, jamais deux fois le même produit au même prix. Parcours vérifié dans un vrai navigateur (Chromium), 34 étapes,
deux passages : les 21 étapes de la v47, plus les étiquettes de la fiche vers une marque sans remise et vers la
catégorie (remises d'abord, « Retour »), « Mission » depuis une catégorie, les prix proposés et l'état du jour, les
comparables, la connexion demandée au lancement puis la mission lancée au retour du lien, l'alerte visible sur la fiche
et relancée sans doublon, le module de l'accueil, l'aperçu qui suit le prix, une phrase non suivie expliquée, la cloche,
la mission depuis une recherche, l'arrêt d'une mission. Planche : `docs/ux/8-v48.png`.

## Mesures v48 → v49 : un accueil éditorial, une Recherche par marque, un verdict de prix lisible

Mêmes produits et mêmes prix (démo du 14 décembre, 59 produits, 11 marques, 20 catégories), téléphone 390 × 844, sans
compte.

| | v48 | v49 |
|---|---|---|
| Phrase sous le titre de l'accueil | « 13 remises en ce moment sur les grandes marques. Mise à jour chaque jour. » | aucune |
| Outils présents dans les deux onglets (champ de recherche, puces de filtre, mosaïque des remises) | 3 | **0** |
| Entrées par marque sur l'accueil | 0 | **7** (les marques en promo) |
| Marques visibles sans geste dans l'onglet de recherche | 0 (dans une feuille de réglages) | **8**, les 11 en un geste |
| Marques atteignables depuis cet onglet | 7 sur 11 (celles qui ont une remise) | **11 sur 11** |
| Gestes de l'accueil à la page d'une marque | 3 | **1** (une carte de l'accueil) ou 2 (l'onglet, une tuile) |
| Part du premier écran de l'accueil occupée par des visuels · mots | 31 % · 70 | **49 %** · 72 |
| Verdict de prix sur la fiche | au bas du premier écran (à 715 px), la courbe en dessous | **sous le prix** (à 470 px), jauge comprise |
| Pour le lire | une courbe en marches, deux points, une ligne pointillée, deux dates, trois valeurs : 9 textes, 5 nombres | une phrase, une jauge, un point, deux bornes : 6 textes, 3 nombres |
| Verdicts possibles | 2 (« au plus bas », « X € au-dessus du plus bas ») | 4 (au plus bas, parmi les plus bas, habituel, plus cher que d'habitude) |
| Enseignes et description sur la fiche | toutes les enseignes, « À propos » | l'enseigne la moins chère seulement |
| Textes sous le contraste minimal · zones à toucher sous 44 px | 0 · 0 (18 écrans) | 0 · 0 (21 écrans) |

Les mots du premier écran de l'accueil ne baissent pas : la phrase retirée laisse la place aux cartes des marques en
promo, qui montent dans le premier écran (d'où la part des visuels). Les verdicts, sur les 59 fiches de la démo : au
plus bas 2, parmi les plus bas 14, habituel 31, plus cher que d'habitude 12 ; sur les 13 remises du jour : 2, 6, 5, 0.
Cinq remises sont donc à leur « prix habituel » : la démo simule des promotions qui reviennent souvent, et le verdict le
dit plutôt que de laisser croire à une occasion rare. La jauge place le jour parmi les jours relevés (pas en euros) :
ainsi le point tombe toujours dans la couleur du verdict (sur une première version en euros, « Son prix habituel »
s'affichait dans le vert). Règle et seuils : `catalog.position` (tests : `tests/test_catalog.py`, chaque seuil vérifié par mutation).

Parcours vérifié dans un vrai navigateur (Chromium), 37 étapes, deux passages : accueil sans phrase ni outils de
recherche et ses trois sections, marques en promo vers leur page, Recherche (8 tuiles puis les 11 marques, les 20
catégories par univers, une marque sans remise trouvée en tapant trois lettres, catégories et produits pour « lave »),
le verdict et la jauge des quatre états (le point dans sa zone), une seule enseigne et c'est la moins chère, ni courbe
ni « À propos » ni autres enseignes, tri par prix d'une catégorie, suivre une marque depuis la Recherche ; et les étapes
des versions précédentes (missions, alertes, connexion, favoris, partage, alternatives). Planche : `docs/ux/9-v49.png`.

## Mesures v49 → v50 : la Recherche répond à une intention précise

Mêmes produits et mêmes prix (démo du 14 décembre), téléphone 390 × 844, sans compte.

| | v49 | v50 |
|---|---|---|
| Éléments à toucher avant toute recherche · mots du premier écran | 30 · 58 | **9 · 15** |
| Filtres catégorie, budget, remise | aucun | **les trois, visibles d'emblée** |
| Tri des résultats | aucun (remises d'abord) | **pertinence, prix croissant, remise** |
| « lave » : rang du premier produit qui n'est ni lave-linge ni lave-vaisselle | 2 (un robot laveur en remise) | **10** (après les 9 lave-linge et lave-vaisselle) |
| « Un lave-linge sous 500 € » : ce qui est montré | les 5 lave-linge de la catégorie, à trier soi-même | **les 3 sous 500 €**, en 5 gestes sans rien taper |
| Mission depuis la Recherche | la requête seule | la requête ou la catégorie, et le budget (« lave-linge sous 500 € ») |
| Textes sous le contraste minimal · zones à toucher sous 44 px | 0 · 0 (21 écrans) | 0 · 0 (24 écrans) |

Les marques ne sont plus listées dans la Recherche : on y entre par l'accueil (les marques en promo), par les étiquettes
de chaque fiche, ou en tapant le nom (le raccourci « Marque » s'affiche au-dessus des résultats, même pour une marque
sans remise). Le filtre de catégorie propose, quand on a tapé quelque chose, les seules catégories trouvées et leur
nombre de produits. La pertinence met d'abord les produits dont la requête nomme la catégorie ou la marque, puis les
remises, puis le prix (`Catalog.search`, chaque règle et chaque filtre vérifiés par mutation).

Parcours vérifié dans un vrai navigateur (Chromium), 41 étapes, deux passages : l'écran sobre (le champ, les trois
filtres, les cinq exemples, aucun bloc), un exemple qui lance la recherche, la marque sans remise trouvée en tapant trois
lettres, la pertinence de « lave », catégorie et budget sans rien taper (3 produits, tous sous 500 €, les puces
montrent le choix), le tri par prix, la mission qui reprend catégorie et budget ; et les étapes des versions
précédentes. Planche : `docs/ux/10-v50.png`.

## Mesures v50 → v51 : un feed dans la Recherche, qui s'adapte à la recherche

Mêmes produits et mêmes prix (démo du 14 décembre), téléphone 390 × 844, sans compte.

| | v50 | v51 |
|---|---|---|
| Avant toute saisie : produits montrés · sur le premier écran | 0 · 0 | **59 · 4** |
| Part du premier écran occupée par des visuels de produits | 0 % | **34 %** |
| Frappe de « lave-linge » : images sans aucun produit à l'écran | 80 sur 128 | **0 sur 135** |
| Champ vidé · requête sans résultat (« xyzzy ») : produits montrés | 0 · 0 | **59 · 59** (le feed) |
| Feed par défaut : catégories dans les 6 premières cartes · cartes communes avec les 6 premières de l'accueil | — | 6 · 3 |
| Après une recherche (« lave-linge », une fiche ouverte), le champ vidé : les 4 premières cartes | rien | **4 lave-linge**, « Pour vous » |
| Textes sous le contraste minimal · zones à toucher sous 44 px | 0 · 0 (24 écrans) | 0 · 0 (28 écrans) |

Le feed, c'est `Catalog.search` sans mot ni filtre : les produits des quatre dernières recherches d'abord (`lead` : la plus
récente d'abord, une recherche à tour de rôle, six produits au plus chacune), puis tout le catalogue, une catégorie à tour
de rôle, en commençant par celles qui offrent le plus de choix, la meilleure remise de chacune d'abord (`breadth`) : ce
n'est pas « Notre sélection » de l'accueil. Les recherches sont retenues par le navigateur (une fiche ouverte depuis les
résultats, la touche Entrée, un exemple touché), jamais par le serveur ; « Effacer » les oublie. Le feed est chargé avec
l'app : il est là dès qu'on touche l'onglet. Pendant la frappe, les résultats montrés restent (pâlis) jusqu'à la réponse
suivante, et une réponse arrivée en retard est ignorée. Un clic sortant depuis le feed est tracé `feed`, depuis des
résultats `search` : `python deals.py metrics` dit ainsi si l'on cherche vraiment, la mesure qui déciderait de simplifier
encore la page. Les règles du feed sont vérifiées par mutation, une à une.

Parcours vérifié dans un vrai navigateur (Chromium), 46 étapes, deux passages : le feed avant toute saisie (six catégories
dans les six premières cartes), aucune image sans produit pendant la frappe, le feed qui revient quand on vide le champ,
la requête sans résultat (le message, la mission, le feed), les sources tracées (`feed`, `search`), « Pour vous » après
une recherche puis son oubli, l'onglet qui remonte en haut ; et les étapes des versions précédentes. Planche :
`docs/ux/11-v51.png`.

## Mesures v51 → v52 : la conversion d'abord (affiliation)

Mêmes produits et mêmes prix (démo du 14 décembre), téléphone 390 × 844 ; v51 et v52 côte à côte, sur la même base.

| | v51 | v52 |
|---|---|---|
| Mission atteinte, dans l'app : gestes jusqu'à l'enseigne | 3 | **2** |
| E-mail de mission : clics jusqu'à l'enseigne · d'où vient le clic | 2 · « fiche » | **1** · « e-mail », mission connue |
| Mission lancée sans compte, lien ouvert sur un autre appareil | perdue | **lancée** |
| Adresse envoyée à l'enseigne : l'identifiant du clic (sous-ID du réseau) | non | **oui** (`…?partenaire=deals&clic=3` en démo) |
| Fiches vues comptées (taux de clic par écran, par personne) | non | **oui** |
| « Enseigne partenaire » près de l'offre · « Comment ça marche » | non · non | **oui · au pied de chaque écran** |
| Fiche : « Voir l'offre » visible sans défiler | 54 sur 59 | 54 sur 59 |
| Textes sous le contraste minimal · zones à toucher sous 44 px | 0 · 0 (28 écrans) | 0 · 0 (33 écrans) |

Ce qui ne fuyait pas : le bouton de la fiche, déjà visible sans défiler sur 54 fiches sur 59. Ce qui fuyait : les
missions, le canal le plus engagé, invisibles dans la mesure (le clic venu de l'e-mail était compté « fiche ») et
fragiles (la mission lancée sans compte attendait dans le navigateur, 30 minutes, et se perdait si l'on ouvrait le lien
ailleurs) ; et l'affiliation elle-même, impossible à suivre (aucun identifiant de clic transmis, aucune fiche vue
comptée). `python deals.py metrics` donne désormais, par écran et par personne (avec mission, connectée sans mission,
sans compte), les fiches vues, les clics vers l'enseigne et le taux de clic, la part des clics partis chez un partenaire
et les clics venus des missions.

Parcours vérifié dans un vrai navigateur (Chromium), 52 étapes, deux passages : la mission jointe à la demande de lien
(rien dans le navigateur), lancée à l'ouverture du lien et ouverte dans Missions, lancée aussi depuis un autre appareil ;
« Voir l'offre » direct sur une mission atteinte (source `mission`, identifiant de mission) ; la fiche ouverte depuis
l'e-mail (source `mail`) ; le lien partenaire avec l'identifiant du clic ; la mention près de l'offre, « Comment ça
marche » et son pied de page sur les cinq onglets ; et les étapes des versions précédentes. Planche : `docs/ux/12-v52.png`.

## Mesures v52 → v53 : les top deals en premier, le filtre Promo, les favoris dans le Profil

Mêmes produits, mêmes prix et mêmes remises (démo du 14 décembre), téléphone 390 × 844 ; v52 et v53 côte à côte.

| | v52 | v53 |
|---|---|---|
| Onglets | 5 (Favoris à part) | **4** (les favoris dans le Profil) |
| Accueil : première section · produits sur le premier écran | « Inspirations du moment » · 0 | **« Top deals » · 3** |
| La plus forte remise (−20 %) sur le premier écran de l'accueil | non | **oui** |
| Produits au prix parmi les plus bas depuis 2 mois (8) : sur l'accueil · sur son premier écran | 7 · 0 | **8 · 3** |
| Recherche, filtre de remise : choix · nombre de produits affiché · « prix bas » | 4 · non · non | **jusqu'à 8 · oui · oui** |
| Favoris : gestes depuis l'accueil · cartes sur le premier écran | 1 · 2 | 1 · 2 |
| Textes sous le contraste minimal · zones à toucher sous 44 px | 0 · 0 (33 écrans) | 0 · 0 (36 écrans) |

Le filtre de remise existait (« Remise » : en remise, −10 %, −20 % et plus) ; il devient « Promo », avec le nombre de
produits de chaque choix (calculé avant ce filtre, comme les catégories), des paliers jusqu'à −50 % proposés quand ils
donnent quelque chose, et les prix parmi les plus bas. Le produit au prix bas sans promotion déclarée (une table à 16 %
sous son prix habituel) n'apparaissait nulle part sur l'accueil ; il est dans les top deals, marqué « Prix bas ». La
règle du prix bas est une fonction pure (`catalog.cheap`) sur le verdict de prix calculé à la publication (`level`,
`span`, `usual`), vérifiée par mutation comme l'ordre des top deals et le filtre.

Parcours vérifié dans un vrai navigateur (Chromium), 56 étapes, deux passages : quatre onglets ; les top deals en
premier (la plus forte remise en tête, au moins un prix bas sans remise, chaque carte dit pourquoi, notre sélection sans
doublon), la fiche ouverte depuis le top (source `top`) ; le filtre Promo (les choix et leurs nombres, prix bas, −20 % et
plus) ; les favoris dans le Profil (source `saved`) ; et les étapes des versions précédentes. Planche :
`docs/ux/13-v53.png`.

## Mesures v54 → v55 : vos goûts d'abord, sans rien bloquer

Mêmes produits, mêmes prix et mêmes remises (démo du 14 décembre), téléphone 390 × 844 ; v54 et v55 côte à côte.

| | v54 | v55 |
|---|---|---|
| Écran bloquant à l'entrée | aucun | aucun |
| Dire ce qui vous intéresse | impossible sans compte (suivre une marque demande la connexion) | **un geste, sans compte** : l'encart facultatif sous les top deals, ou le Profil |
| L'ordre de l'accueil et du feed suit | la marque suivie (compte) ; le feed : les recherches récentes | **rayons choisis, fiches ouvertes, clics, recherches, favoris, marques, missions** |
| Accueil, rang de la première carte de ses rayons (démo, rayons choisis) | 5,1 | **1,1** |
| Top deals, clics attendus (démo, selon la situation) | 0,79 (0,88 avec un compte) | **1,00 à 1,10** |
| Accueil, cartes de ses rayons (3 000 produits, selon la situation) | 19 à 22 % | **43 à 60 %** |
| Une recherche précise (« canapés pas cher ») oriente le feed | non (18 % de ses rayons) | **oui (77 %)** |
| Ce que l'app retient : visible, corrigible, oubliable | — | **Profil** : vos rayons, ce que l'app a compris, « Oublier », l'interrupteur |
| Textes sous le contraste minimal · zones à toucher sous 44 px | 0 · 0 (36 écrans) | 0 · 0 (50 écrans) |

Clics attendus : un modèle (attrait de la carte selon son rayon et sa remise, × biais de position), pas une mesure ; en
production, une visite sur dix sans les goûts (témoin) dit le vrai gain (`metrics`, `by_variant`). La remise moyenne
montrée sur l'accueil baisse à peine (29,6 % → 28,7 à 29,1 % sur 3 000 produits) : l'intérêt du deal reste premier. Sur
la démo d'un jour ordinaire (13 remises), « Pour vous » est souvent vide : les deals des rayons choisis sont déjà dans
les top deals, qui passent devant ; sur 3 000 produits, il montre 5 à 7 cartes, de 54 % (compte avec historique) à
100 % (rayons choisis) dans les rayons de la personne. En chemin : 4 des 5 exemples de la Recherche (« aspirateur balai », « lave-linge 9 kg »…) ne comptaient pour
aucun rayon, et « canapé d'angle » nommait la marque Dormea (« d ») ; une recherche nomme désormais le rayon le plus
précis qu'elle contient.

Parcours vérifié dans un vrai navigateur (Chromium), 64 étapes, deux passages : l'encart se propose sans bloquer, se
ferme et ne revient pas ; les rayons choisis passent en tête sans écarter la plus forte remise, « Pour vous » ne montre
qu'eux, le choix reste à la visite suivante et dans la Recherche (un produit sur quatre ailleurs) ; les fiches ouvertes
orientent la visite sans rien garder par défaut ; le Profil dit ce qui est compris, l'oublie, et ne garde les fiches que
sur demande ; fiches vues et liens vers l'enseigne portent la variante ; à la connexion, les rayons passent sur le
compte ; un témoin voit l'ordre d'avant ; et les étapes des versions précédentes. Planche : `docs/ux/14-v55.png`.

## Mesures v55 → v56 : trouver vite, garder sans e-mail

Mêmes produits, mêmes prix et mêmes remises (démo du 14 décembre), téléphone 390 × 844 ; v55 et v56 côte à côte.

| | v55 | v56 |
|---|---|---|
| « aspirateur balai sans fil sous 300 € » tapé dans la Recherche | « Rien pour … » (les filtres ne savent ni « balai » ni « sans fil ») | **3 produits**, et 4 puces : Aspirateurs · Balai · Sans fil · Moins de 300 € |
| 41 phrases tapées comme on parle (`bench.search`, démo) : impasses · première carte juste | 15 · 9 sur 24 | **0 · 24 sur 24** |
| Même banc, 3 000 produits | 15 · 4 sur 19 | **0 · 19 sur 19** |
| Changer un critère | retaper la phrase, ou trois filtres (catégorie, budget, promo) | **une puce** (la croix) ou **Affiner** : rayon, fonctions, tailles, marque, budget de… à…, promo, tri, chaque choix avec ce qu'il donnerait |
| Rien sous le budget | « Rien pour … » | **les plus proches au-dessus**, « Me prévenir » |
| Garder une recherche | impossible (une mission : une phrase et un prix, dans un onglet à part, avec connexion) | **« Sauvegarder »**, prix facultatif ; ce qui est nouveau se voit (« 5 NOUVEAUX », pastilles) |
| Gestes qui demandaient un e-mail (favori, marque suivie, mission, alerte de prix) | 4 | **0** (un compte invité pour l'appareil) |
| Où se règle ce qu'on garde | Profil (favoris, marques, rayons) et onglet Missions ; l'encart des rayons sur l'accueil | **Profil, centre de commande** : recherches, alertes, favoris, marques (« Ajouter »), rayons, ce que l'app a compris, e-mail facultatif, effacer |
| Onglets | 4 | **3** (Accueil, Recherche, Profil) |
| Textes sous le contraste minimal · zones à toucher sous 44 px · éléments sans nom | 0 · 0 (50 écrans) | 0 · 0 · 0 (65 écrans) |

Lecture honnête : sur le banc, la pertinence (100 %) vient en partie de la construction — la Recherche et la vérité du
banc suivent les mêmes règles que les missions ; ce qui se mesure vraiment, c'est qu'aucune phrase ne tombe plus dans une
impasse et que la première carte répond. Sur 3 000 produits aux titres générés (sans « balai » ni ces marques), 20
phrases n'ont aucun produit qui y réponde : l'écran le dit, propose de sauvegarder et garde le feed (`docs/RECHERCHE.md`).
En chemin : « canapé d’angle » tapé sur un téléphone (apostrophe typographique) ne comprenait pas « d'angle », ni dans
la phrase ni dans les titres des produits ; « dès 300 € » était lu comme un maximum ; « de 200 à 400 € » perdait son
minimum ; chaque choix d'Affiner comptait les produits de taille exacte au lieu de ce qu'il donnerait ; deux gestes
rapides dans Affiner pouvaient effacer le premier (corrigé : chaque geste part du dernier état voulu, et seule la
réponse à la dernière demande s'applique).

Parcours vérifié dans un vrai navigateur (Chromium), 68 étapes, deux passages : la phrase en puces, retirer une puce,
Affiner (rayon seul puis « Changer de rayon », fonctions et tailles avec leurs nombres, budget de… à…, tri), les plus
proches, les mots ignorés, un rayon non suivi, rien du tout ; une recherche faite de puces gardée en mots et rejouée ;
sauvegarder sans e-mail, la reconnaître, la retirer, l'ouvrir ; une nouveauté de la nuit (pastilles, « NOUVEAUX »)
oubliée une fois ouverte ; une alerte de prix posée, relancée, arrêtée, atteinte (« Voir l'offre ») ; suivre une marque
et en ajouter une depuis le Profil ; un rayon depuis sa page ; le Profil centre de commande ; ajouter son e-mail sans rien
perdre, retrouver son compte sur un autre appareil, un invité versé dans un compte sans doublon ; effacer ses données ;
rien ne déborde à 390 px ; et les étapes des versions précédentes. Planche : `docs/ux/15-v56.png`.

## Mesures v56 → v57 : trois portes, un besoin compris

Démo du 14 décembre, téléphone 390 × 844 ; v56 et v57 côte à côte. La démo v57 compte 25 aspirateurs de plus (marques
fictives, fiches plus ou moins complètes) : 84 produits au lieu de 59 ; une part des écarts de nombres vient de là.

| | v56 | v57 |
|---|---|---|
| Entrées de l'accueil | une, après deux rangées (« Une envie précise ? ») | **trois portes, en haut** : Rechercher, Les bonnes affaires, Explorer |
| « aspirateur pour mon chat avec du parquet, 300 € max » | 4 produits ; « « chat parquet, » : aucun produit » | **24 produits classés**, puces « Pour Poils d'animaux » et « Pour Parquet », ce qu'elles demandent, et deux raisons par carte |
| « quel aspirateur choisir ? » | 6 produits, « choisir » ignoré | **une question** (« Comment voulez-vous faire le ménage ? », 5 réponses avec leur nombre, « Passer »), la sélection dessous |
| « robot aspirateur pour les escaliers » | 2 robots, « escaliers » ignoré | les robots, et **« Un robot ne monte pas les marches. Voir les aspirateurs à main (3) »** |
| « aspirateur qui lave le sol » | 6 aspirateurs, « lave sol » ignorés | **11** qui lavent (ou dont la page ne dit rien, après), « 22 produits écartés : ne lave pas le sol. » |
| Explorer par type, par usage | — | **5 types et 15 usages**, chacun avec ses produits, à un geste de la Recherche |
| Ce que la fiche dit du produit | le prix, le verdict, l'offre (la description reste chez l'enseigne) | et **L'essentiel** : ce qui décide pour son type, chaque valeur avec sa source, « Non précisé » sinon |
| 27 besoins à vérité connue (`bench.needs`) : bons parmi les 6 premières cartes · mots ignorés | 35 % · 42 | **96 % · 0** |
| Textes sous le contraste minimal · zones à toucher sous 44 px · éléments sans nom | 0 · 0 · 0 (65 écrans) | 0 · 0 · 0 (85 écrans) |

Lecture honnête : le banc des besoins a une vérité écrite par le même auteur que l'ontologie et des fiches que
l'ontologie sait lire (`docs/ONTOLOGIE.md`) ; il dit que le moteur suit ses règles, la production dira si les règles
sont bonnes. Rien n'est imposé : un type nommé n'est jamais remplacé, une demande précise ne reçoit pas de question, un
besoin qui ne fait que situer (« un appartement ») est dit sans rien changer, et ce que la page ne dit pas reste « non
précisé ». En chemin : un rayon nommé (« aspirateur à main ») perdait ses produits sous 100 € (le seuil du catalogue :
30 € pour les aspirateurs) ; « Zephyr Max 90 » se lisait comme un prix ; un produit dont la fiche dit « non » passait
avec ceux dont elle ne dit rien (il passe désormais après) ; une recherche sauvegardée d'aspirateurs ne nourrissait plus
les goûts (son rayon compte de nouveau).

Parcours vérifié dans un vrai navigateur (Chromium), 79 étapes, deux passages : les trois portes ; Explorer (chemin,
types, usages, rayons) et un type qui ouvre la Recherche ; un besoin compris en puces, ce qu'il demande, l'ordre par
adéquation et deux raisons par carte (une source faible dite : « d'après le nom ») ; une demande vague, sa question, sa
réponse, la seconde question et « Passer » ; aucune question pour une demande précise ; Affiner par type, usage et ce
qui décide ; un autre type proposé avec sa raison, et la raison seule quand aucun autre type n'a de produits ; un besoin
sans exception qui écarte et le dit ; la référence exacte et son offre en un geste ; « L'essentiel » de la fiche et ses
sources ; une recherche de besoin gardée, qui ne promet que ce qui convient ; et les étapes des versions précédentes.
Planche : `docs/ux/16-v57.png`.
