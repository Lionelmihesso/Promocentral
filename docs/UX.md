# L'interface de Promo Central (v65)

Une page (`web/src/App.jsx` → `web/app.html`, polices incluses, aucune requête vers un tiers), téléphone d'abord,
quatre onglets : **Top deals** (ouvert au lancement), **Explorer**, **Recherche**, **Profil**. Ce document décrit
l'interface telle qu'elle est ; son
historique (mesures version par version, de la v41 à la v63, et leurs captures) est dans git :
`git log -p -- docs/UX.md`, et `git show 2ca25aa:docs/UX.md` pour la dernière version qui le contenait.

## Principe

**Le moins possible, pour aller vite au produit** (v65). Rien de plus que ce qui aide à décider vite : pas d'encadré,
pas de phrase d'explication (ni sous-titre, ni accroche, ni « pourquoi » sur les cartes, ni durée de la remise), rien
d'ajouté sur la fiche. La carte dit le produit et son prix comme une étiquette : le prix, le prix barré et la remise en
pourcentage, l'économie en euros (« 151 € d'économie »). La qualité reste implicite : seulement des remises réelles,
aucune mention « vérifiée ». Deux entrées : **les belles remises du moment** (Top deals, Explorer) et **le produit qu'on
regarde** (la Recherche couvre tout le catalogue suivi) ; la fiche répond alors à « existe-t-il moins cher, et aussi
bien ? ».

**Deux couleurs** (v65). L'**action**, jaune (`#FFD60A`, texte noir) : le bouton vers l'enseigne (« Voir l'offre chez
… », sur la fiche et sur une recherche sauvegardée atteinte) et le surlignage de « Promo » dans le logo. La **remise**,
rouge (`#D63A0D`) : la remise en pourcentage (pastille), l'économie, « Prix bas », « Central » dans le logo. Le reste en
noir et gris. Le logo, **Promo** surligné et **Central** en rouge, se reconnaît d'un coup d'œil ; l'icône de l'onglet
du navigateur reprend le « P » sur le jaune.

**Pinterest × Bloomberg.** Pinterest pour donner envie : des visuels, une mosaïque, l'inspiration par pièce.
Bloomberg pour la vie : un bandeau où défilent les remises du jour avec l'heure de mise à jour. Le relevé des prix
choisit les prix bas des top deals (« Prix bas » sur la carte) ; la fiche n'a pas de jauge de prix (retirée en v60 :
elle troublait plus qu'elle n'aidait).

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

**Garder sans e-mail.** Favoris, marques suivies, rayons et recherches sauvegardées se gardent d'un geste, sans e-mail
(un compte invité pour l'appareil) ; l'e-mail, facultatif, sert aux nouveautés de vos recherches, la nuit, et à
retrouver ses choix sur un autre appareil. Une recherche sauvegardée est une **mission** : la plateforme la surveille
et dit ce qui est nouveau. Les recherches sauvegardées vivent dans le **Profil**, le centre de commande ; la Recherche
dit où les retrouver. « Me prévenir sous un prix » (l'alerte sur un produit ou ses comparables, depuis la fiche) est
arrêté en v65 : on ne peut plus en poser, et celles d'avant ne sont ni montrées ni envoyées (`deals/missions.py`).

**Vos goûts d'abord, l'intérêt du deal toujours.** Sans onboarding : vos rayons (choisis d'un geste), vos marques, ce
que vous gardez et regardez. Vos deals passent devant, au plus × 1,5 ; une place sur quatre reste au meilleur deal du
jour ; une visite sur dix est témoin. Le Profil dit ce que l'app a compris et permet de l'oublier
([`PERSONNALISATION.md`](PERSONNALISATION.md)).

**La conversion d'abord.** Le modèle est l'affiliation : seules les offres d'enseignes partenaires sont montrées ; le
geste qui rapporte est le clic vers l'offre. Sur la fiche, le bouton vers l'enseigne vient juste sous le prix, dans la
couleur action : c'est le plus visible de l'écran. La transparence (« Offres d'enseignes partenaires, remises
vérifiées », « Comment ça marche », « Mentions légales ») est au pied du **Profil**, et seulement là (v65, choix du
responsable) ; à faire valider par le juriste avant l'ouverture ([`PRODUCTION.md`](PRODUCTION.md), P1-10).

**Les visuels** sont des **illustrations originales** par catégorie (`web/src/art.jsx`), déclinées par produit
(couleurs, proportions de l'objet : une armoire est haute, un canapé est large, d'où la mosaïque). Aucune image
extérieure, aucun droit de tiers. Sur la fiche, le visuel reste nu : rien n'est posé dessus que Retour, Partager et le
cœur. Les photos des produits : voir plus bas.

**Accessibilité.** Contrastes WCAG AA (le texte noir sur le jaune : 13 : 1 ; la remise sur le blanc et le blanc sur la
remise : 4,7 : 1), zones à toucher de 44 px au moins, un nom pour chaque bouton et chaque champ, bandeau immobile si
l'appareil demande moins d'animations, espaces insécables du français.

## Ce que montre chaque écran

| Écran | Contenu |
|---|---|
| Top deals | le premier onglet, ouvert au lancement : « Top deals », puis les top deals en mosaïque (dix au plus, la plus forte remise d'abord, puis un prix bas, et ainsi de suite) |
| Explorer | bandeau défilant (« MAJ 14 déc. 11:00 », marque, catégorie, remise, prix), **pour vous** (les deals et prix bas de vos rayons et de vos marques, top deals compris), **inspirations du moment** par pièce (les pièces de vos rayons d'abord), **les marques en promo** (même format), **notre sélection** en mosaïque (les autres remises : ni top deals, ni « pour vous »). Pas de recherche sur Explorer : elle est dans son onglet |
| Carte | visuel et cœur ; marque, nom (une ligne) ; le prix ; le prix barré et la remise (« −20 % », pastille rouge) ; l'économie (« 151 € d'économie ») ; un prix bas sans remise : « Prix bas », sans prix barré ; « 481 € de moins » sur une alternative (au lieu de l'économie : c'est ce qu'on gagne sur le produit de la fiche) ; « Baisse de 64 € » sur un favori |
| Fiche | grand visuel nu, Retour, Partager (lien vers la fiche), cœur ; nom ; le prix, le prix barré et la remise sur une ligne, l'économie dessous ; **« Voir l'offre chez … »** (l'enseigne partenaire la moins chère et disponible, la seule montrée), jaune, 58 px, juste sous le prix ; la marque et la catégorie, qui mènent à tous leurs produits ; **moins cher, comparable** ; à défaut, produits similaires |
| Recherche | le champ, qui comprend une phrase (« aspirateur balai sans fil sous 300 € » : les étapes « Aspirateurs », « Balai », « Sans fil », « Moins de 300 € ») ; **Promo** et **Trier** ; en puces, la marque, la promo, le tri et les mots, et « Tout effacer » ; **l'entonnoir** ; avant toute saisie, **vos recherches récentes** (« Effacer ») ou « Essayez » et cinq exemples, puis le **feed** (« À découvrir » ou « Pour vous ») ; dès qu'on tape ou choisit : « 3 produits », **« Sauvegarder »** (« Recherche sauvegardée dans votre Profil »), la mosaïque ; des mots sans produit, dits, et le reste de la recherche ; rien sous le budget : « Rien à moins de 300 € », les plus proches au-dessus, et « Sauvegarder » ; rien du tout : « Rien pour « xyzzy » » et « Sauvegarder », puis le feed ; un rayon non suivi : « Les smartphones ne sont pas encore suivis » |
| Affiner (l'entonnoir) | « AFFINER », des traits (fait, en cours, à venir) ; les **étapes franchies** (« High-tech × », « Téléviseurs × » : la croix revient avant elle) ; **la question** (« Quel univers ? », « Quel rayon ? », « Quel type ? », « Taille d'écran ? », « Votre budget ? ») et ses réponses, chacune avec son nombre (« OLED 3 ») ; **« Passer »** ; à la fin, « VOTRE SÉLECTION », « 3 produits », « Sauvegarder » (sur une page : « Recommencer ») ; rien ici : « retirez une étape » |
| Marque, catégorie, pièce | « 1 remise aujourd'hui · 7 produits » ; suivre la marque ; une catégorie rejoint vos rayons ; **l'entonnoir** (une marque : « Quel rayon ? », ou « Quel univers ? » au-delà de six rayons ; une marque d'un seul rayon : ses questions d'emblée ; une catégorie : ses questions ; une pièce : « Quel rayon ? ») ; le tri (remises d'abord, prix croissant, décroissant) ; la mosaïque ; ce qu'on y a choisi reste quand on ouvre une fiche et revient |
| Ajouter son e-mail | facultatif : « Pour recevoir par e-mail les nouveautés de vos recherches et retrouver ce que vous gardez sur un autre appareil » ; un lien, aucun mot de passe ; le lien rattache l'adresse à ce qui est gardé ici, ou verse ce qui est gardé ici dans le compte qui a déjà cette adresse |
| Profil | le centre de commande, des titres seuls et beaucoup d'air ; « Gardé sur cet appareil, sans e-mail. Ajouter mon e-mail » (ou « Connecté avec … ») ; **vos recherches** sauvegardées (ce qui y répond, « 5 NOUVEAUX », la cloche pour l'e-mail de la nuit, la croix ; atteinte, « Voir l'offre · 175 € chez … », jaune) ; **vos favoris** ; **vos marques** ; **vos rayons**, repliés (« Vos rayons · 2 choisis ») ; **ce que l'app a compris** et « Oublier » ; « Me reconnaître à mon retour » ; « Effacer mes données », « Se déconnecter » ; au pied, et sur aucun autre écran : « Offres d'enseignes partenaires, remises vérifiées. Comment ça marche · Mentions légales » ; la cloche de l'en-tête et l'onglet comptent les recherches qui ont du nouveau |
| Comment ça marche | depuis le Profil : quelles offres (enseignes partenaires seulement, prix relus chaque nuit, remises réelles seulement), dans quel ordre, comment Promo Central est rémunéré (une commission, sans effet sur le prix ni sur le classement), vos données |
| Mentions légales et données personnelles | depuis le Profil : l'éditeur, le directeur de la publication, l'hébergeur, le contact (lus dans `DEALS_LEGAL_…` ; en développement, « à compléter » ; en production, l'app ne démarre pas sans eux), ce que la plateforme garde, pourquoi, combien de temps, vos droits |
| Démonstration (`DEALS_ENV=demo`) | une ligne noire en haut de chaque page, avant l'app : « Démonstration : données fictives, aucune offre réelle. » ; dans le flux, elle ne recouvre rien (v64 : fixée en bas, elle cachait la barre d'onglets d'un téléphone et prenait ses gestes) |

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
téléphone et ordinateur : contrastes, zones à toucher, noms). Dernier passage complet : v63, 85/85 et 0 défaut. Leurs
scripts ne sont pas dans le dépôt ; depuis, des contrôles ciblés :

- v64 (quatre onglets) : 18 contrôles dans Chromium.
- v65 (le moins possible) : 38 contrôles dans Chromium, téléphone (390 × 844) et ordinateur : le logo et ses deux
  couleurs, l'étiquette de prix de chaque carte (l'économie = prix barré − prix), « Prix bas », plus de remise sur le
  visuel ni de « pourquoi », la fiche (titre, prix, bouton, puis marque et catégorie ; bouton jaune de 58 px dans le
  premier écran), plus de « Me prévenir », les mentions au Profil seulement (et leurs pages, Retour), le bandeau de
  démo en haut sans recouvrir d'onglet, l'origine « top » d'un clic, Retour, le logo, l'API qui refuse une alerte,
  aucune erreur. Mesures, téléphone de 390 × 844, avant (v64) → après (v65) : mots hors produits, Top deals 20 → 4,
  Explorer 29 → 11 (37 → 13 avec « Pour vous ») ; premier produit d'Explorer avec « Pour vous » à 280 → 188 px ;
  bouton vers l'enseigne sur les mêmes 22 fiches, médiane 534 → 478 px, toujours entier dans le premier écran
  (22/22 avant et après) ; bandeau de démo sur la barre d'onglets 50 → 0 px (avant, il prenait les gestes des
  quatre onglets).
