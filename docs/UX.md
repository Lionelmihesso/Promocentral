# L'interface de Promo Central (v63)

Une page (`web/src/App.jsx` → `web/app.html`, polices incluses, aucune requête vers un tiers), téléphone d'abord,
trois onglets : **Accueil**, **Recherche**, **Profil**. Ce document décrit l'interface telle qu'elle est ; son
historique (mesures version par version, de la v41 à la v63, et leurs captures) est dans git :
`git log -p -- docs/UX.md`, et `git show 2ca25aa:docs/UX.md` pour la dernière version qui le contenait.

## Principe

**Peu de choses, et justes.** Rien de plus que ce qui aide à décider vite : pas d'encadré, pas de raisons sur les
cartes, rien d'ajouté sur la fiche. La qualité reste implicite : seulement des remises réelles, aucune mention
« vérifiée ». Deux entrées : **les belles remises du moment** (l'accueil) et **le produit qu'on regarde** (la
Recherche couvre tout le catalogue suivi) ; la fiche répond alors à « existe-t-il moins cher, et aussi bien ? ».

**Pinterest × Bloomberg.** Pinterest pour donner envie : des visuels, une mosaïque, l'inspiration par pièce.
Bloomberg pour la vie : un bandeau où défilent les remises du jour avec l'heure de mise à jour. Le relevé des prix sert
aux top deals (« Au plus bas », « Parmi les plus bas ») ; la fiche n'a pas de jauge de prix (retirée en v60 : elle
troublait plus qu'elle n'aidait).

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

**Garder sans e-mail.** Favoris, marques suivies, rayons, recherches sauvegardées et alertes de prix se gardent d'un
geste, sans e-mail (un compte invité pour l'appareil) ; l'e-mail, facultatif, sert aux alertes de la nuit et à
retrouver ses choix sur un autre appareil. Une recherche sauvegardée est une **mission** : la plateforme la surveille
et dit ce qui est nouveau. Les recherches sauvegardées vivent dans le **Profil**, le centre de commande ; la Recherche
dit où les retrouver.

**Vos goûts d'abord, l'intérêt du deal toujours.** Sans onboarding : vos rayons (choisis d'un geste), vos marques, ce
que vous gardez et regardez. Vos deals passent devant, au plus × 1,5 ; une place sur quatre reste au meilleur deal du
jour ; une visite sur dix est témoin. Le Profil dit ce que l'app a compris et permet de l'oublier
([`PERSONNALISATION.md`](PERSONNALISATION.md)).

**La conversion, dite.** Le modèle est l'affiliation : seules les offres d'enseignes partenaires sont montrées ; le
geste qui rapporte est le clic vers l'offre. C'est dit : « Enseigne partenaire » près de l'offre, « Comment ça
marche » et « Mentions légales » au pied de chaque écran.

**Les visuels** sont des **illustrations originales** par catégorie (`web/src/art.jsx`), déclinées par produit
(couleurs, proportions de l'objet : une armoire est haute, un canapé est large, d'où la mosaïque). Aucune image
extérieure, aucun droit de tiers. Les photos des produits : voir plus bas.

**Accessibilité.** Contrastes WCAG AA, zones à toucher de 44 px au moins, un nom pour chaque bouton et chaque champ,
bandeau immobile si l'appareil demande moins d'animations, espaces insécables du français.

## Ce que montre chaque écran

| Écran | Contenu |
|---|---|
| Accueil | bandeau défilant (« MAJ 14 déc. 11:00 », marque, catégorie, remise, prix), « De bonnes affaires, pour vos envies. », **top deals** (« Remises et prix bas » : jusqu'à dix cartes à faire défiler, la plus forte remise d'abord, puis un prix bas, et ainsi de suite), **pour vous** (les deals et prix bas de vos rayons et de vos marques, sans répéter les top deals, avec pourquoi : « Vos rayons : Canapés, Matelas » ; « Modifier » mène au Profil), **inspirations du moment** par pièce (les pièces de vos rayons d'abord), **les marques en promo** (même format), **notre sélection** en mosaïque. Pas de recherche sur l'accueil : elle est dans son onglet |
| Carte | visuel, remise sur le visuel, cœur, marque, nom (une ligne), prix et prix barré ; « Baisse de 64 € » sur un favori ; « 481 € de moins » sur une alternative ; dans les top deals, « Au plus bas » ou « Parmi les plus bas », et « Prix bas » sur le visuel d'un produit sans remise |
| Fiche | grand visuel, partager (lien vers la fiche), cœur, **étiquettes marque et catégorie** posées sur le visuel ; nom ; remise, prix, prix barré ; « En remise depuis 3 jours, jusqu'au ven. 19 déc. » ; « Voir l'offre chez … » (l'enseigne partenaire la moins chère et disponible, la seule montrée) et « Enseigne partenaire : si vous achetez, nous touchons une commission, sans surcoût pour vous. Comment ça marche » ; **« Me prévenir sous un prix »** ; **moins cher, comparable** ; à défaut, produits similaires |
| Me prévenir (alerte de prix) | pour ce produit, ou tous les comparables (ce qui est guetté est dit : « Lit 160 × 200 ») ; trois prix proposés (−5 %, −10 %, −20 % du prix du jour) ou le sien ; ce qui en est aujourd'hui (« Aujourd'hui 612 € : encore 62 € ») ; posée tout de suite, sans e-mail |
| Recherche | le champ, qui comprend une phrase (« aspirateur balai sans fil sous 300 € » : les étapes « Aspirateurs », « Balai », « Sans fil », « Moins de 300 € ») ; **Promo** et **Trier** ; en puces, la marque, la promo, le tri et les mots, et « Tout effacer » ; **l'entonnoir** ; avant toute saisie, **vos recherches récentes** (« Effacer ») ou « Essayez » et cinq exemples, puis le **feed** (« À découvrir » ou « Pour vous ») ; dès qu'on tape ou choisit : « 3 produits », **« Sauvegarder »** (« Recherche sauvegardée dans votre Profil »), la mosaïque ; des mots sans produit, dits, et le reste de la recherche ; rien sous le budget : les plus proches au-dessus, et « Me prévenir » ; rien du tout : « Rien pour « xyzzy » » et « Sauvegarder », puis le feed ; un rayon non suivi : « Les smartphones ne sont pas encore suivis » |
| Affiner (l'entonnoir) | « AFFINER », des traits (fait, en cours, à venir) ; les **étapes franchies** (« High-tech × », « Téléviseurs × » : la croix revient avant elle) ; **la question** (« Quel univers ? », « Quel rayon ? », « Quel type ? », « Taille d'écran ? », « Votre budget ? ») et ses réponses, chacune avec son nombre (« OLED 3 ») ; **« Passer »** ; à la fin, « VOTRE SÉLECTION », « 3 produits », « Sauvegarder » (sur une page : « Recommencer ») ; rien ici : « retirez une étape » |
| Marque, catégorie, pièce | « 1 remise aujourd'hui · 7 produits » ; suivre la marque ; une catégorie rejoint vos rayons ; **l'entonnoir** (une marque : « Quel rayon ? », ou « Quel univers ? » au-delà de six rayons ; une marque d'un seul rayon : ses questions d'emblée ; une catégorie : ses questions ; une pièce : « Quel rayon ? ») ; le tri (remises d'abord, prix croissant, décroissant) ; la mosaïque ; ce qu'on y a choisi reste quand on ouvre une fiche et revient |
| Ajouter son e-mail | facultatif : « Pour recevoir vos alertes par e-mail et retrouver vos favoris, vos marques et vos recherches sur un autre appareil » ; un lien, aucun mot de passe ; le lien rattache l'adresse à ce qui est gardé ici, ou verse ce qui est gardé ici dans le compte qui a déjà cette adresse |
| Profil | le centre de commande, des titres seuls et beaucoup d'air ; « Gardé sur cet appareil, sans e-mail. Ajouter mon e-mail » (ou « Connecté avec … ») ; **vos recherches** sauvegardées (ce qui y répond, « 5 NOUVEAUX », la cloche pour l'e-mail de la nuit, la croix) ; **vos alertes de prix** (« Voir l'offre · 175 € chez … » une fois atteinte) ; **vos favoris** ; **vos marques** ; **vos rayons**, repliés (« Vos rayons · 2 choisis ») ; **ce que l'app a compris** et « Oublier » ; « Me reconnaître à mon retour » ; « Effacer mes données », « Se déconnecter » ; la cloche de l'en-tête et l'onglet comptent les recherches qui ont du nouveau |
| Comment ça marche | quelles offres (enseignes partenaires seulement, prix relus chaque nuit, remises réelles seulement), dans quel ordre, comment Promo Central est rémunéré (une commission, sans effet sur le prix ni sur le classement), vos données |
| Mentions légales et données personnelles | l'éditeur, le directeur de la publication, l'hébergeur, le contact (lus dans `DEALS_LEGAL_…` ; en développement, « à compléter » ; en production, l'app ne démarre pas sans eux), ce que la plateforme garde, pourquoi, combien de temps, vos droits |

## À décider : les photos des produits

Les flux des enseignes donnent l'adresse de la photo de chaque produit (`image_link`) ; elle est gardée
(`products.image`) mais pas montrée. La montrer est une décision de front : la charger depuis l'enseigne (une requête
vers un tiers à chaque ouverture, l'adresse IP des visiteurs transmise), ou la copier sur notre serveur (stockage,
bande passante), dans tous les cas selon les conditions du programme d'affiliation. Tant que ce n'est pas décidé, les
illustrations tiennent la place ; elles restent de toute façon le repli d'un produit sans photo.

## Vérifier

À chaque livraison, dans un vrai navigateur (Chromium), sur la démo nourrie par flux (`python deals.py demo`) : le
parcours complet (85 étapes : accueil, Recherche et entonnoir, pages marque, catégorie et pièce, fiche, alerte,
sauvegarde, e-mail facultatif, Profil, témoin, ordinateur, mouvement réduit) et l'audit d'accessibilité (92 écrans,
téléphone et ordinateur : contrastes, zones à toucher, noms). Dernier passage : v63, 85/85 et 0 défaut.
