# Revue de l'app en tant qu'utilisateur — octobre 2026 (v41 → v43)

Méthode : l'app a été ouverte comme par quelqu'un qui la découvre, sur un téléphone (390 × 844) et sur un ordinateur,
avec les mêmes données des deux côtés : la démo (`python deals.py demo`), 48 produits, 13 remises un jour ordinaire.
Chaque geste courant a été refait en comptant les étapes ; contrastes, tailles des zones à toucher et requêtes vers des
tiers ont été mesurés dans le navigateur. Captures avant / après : `docs/ux/`.

## Les quatre questions, avant la refonte

**Est-ce que je comprends ?** Je comprends que ce sont des produits en promotion (« 13 produits en remise »). Je ne
comprends pas ce qui distingue Deals d'un site de promos : rien ne dit que les remises sont vérifiées et que les fausses
sont écartées, alors que c'est tout le travail du moteur. Le « −19 % » est immense, mais ni l'économie en euros ni
l'enseigne ne sont sur l'accueil. « Aujourd'hui » est écrit trois fois sur le même écran. Pendant une recherche, le titre
annonce « 4 produits en remise » (le nombre de résultats).

**Est-ce que je trouve ce que je cherche ?** La liste est faite de lignes identiques : même typographie, même pastille
rouge, aucun repère visuel, aucune catégorie visible. Pour les matelas, il faut passer par Explorer (et souvent faire
défiler les catégories). Pour savoir où acheter, il faut ouvrir chaque fiche.

**Est-ce que je suis agréablement surpris ?** L'identité est forte et sobre (noir, blanc, orange, typographie grasse) :
c'est un bon socle. Mais rien de ce que le moteur sait ne se voit : remise vérifiée, prix le plus bas depuis des semaines,
offre qui finit vendredi, nouveauté de la nuit. Quand tout est rouge, rien ne ressort.

**Est-ce que ça donne envie de revenir ?** Rien ne change visiblement d'un jour à l'autre. Le « Depuis hier » de la
maquette v42 n'avait jamais été branché, et un favori ne dit pas si son prix a baissé.

Sur ordinateur, l'app est une colonne de téléphone au milieu d'un fond gris. La police est chargée chez Google : requête
vers un tiers (sujet RGPD, plusieurs décisions européennes) et, quand Google ne répond pas, une police de secours.

## Ce qui change (v43), et pourquoi

Gardé des maquettes v27 à v42 : le produit comme entrée (l'enseigne n'est qu'un attribut), un deal identique pour tous,
pas d'image en V1, le signet sur chaque ligne, le suivi des marques, la connexion demandée au moment de l'action,
l'identité visuelle.

| Ajout | Ce que l'utilisateur y gagne | Données |
|---|---|---|
| « 13 remises aujourd'hui · Toutes vérifiées · 2 fausses promos écartées » | la promesse de Deals, en une ligne | `counts` de `/today` |
| « Depuis hier » : nouvelles, finissent bientôt (v42) | une raison de revenir chaque jour | `since`, `ends` publiés chaque nuit |
| Catégories sur l'accueil, avec pictogrammes | 1 geste pour filtrer, un repère visuel par ligne | catégories du jour |
| Économie en euros, prix barré, enseigne sur chaque ligne | comparer sans ouvrir les fiches | déjà publié |
| Un signal par ligne : finit bientôt › nouveau › plus bas depuis n jours › vérifiée | ce qui ressort a une raison | `ends`, `since`, `low_days`, `verified` |
| Fiche : « Pourquoi c'est un vrai deal » (prix habituel relevé, plus bas prix, depuis quand, jusqu'à quand) et bouton « Voir l'offre » visible sans défiler | la confiance, puis l'action | `usual`, `proof`, `low_days`, `since`, `ends` |
| Remise annoncée non retenue expliquée sur la fiche | comprendre pourquoi un produit n'est pas en deal | `fake`, `usual` |
| Favoris : « ↓ 64 € depuis votre favori », pastille sur l'onglet | une baisse de prix fait revenir | prix au moment du favori |
| Explorer par famille (électroménager, ameublement, literie) | parcourir sans connaître le nom exact | taxonomie unique |
| Deux colonnes et navigation en haut sur ordinateur | l'écran sert enfin | — |
| Police Manrope servie avec la page, contrastes et zones à toucher aux normes | lisible pour tous, aucune requête vers un tiers | — |

## Mesures (mêmes données, mêmes écrans)

| Geste ou critère | v41 | v43 |
|---|---|---|
| Savoir si les remises sont vérifiées | impossible | visible sur l'accueil ; détail sur la fiche |
| Économie en euros du meilleur deal | 1 geste + calcul | visible sur l'accueil |
| Voir les nouveautés depuis hier · les offres qui finissent | impossible | 1 geste |
| Remises d'une catégorie (matelas) | 2 gestes (Explorer, puis la catégorie) | 1 geste, depuis l'accueil |
| Savoir où acheter le 2e produit de la liste | 1 geste | visible dans la ligne |
| Savoir si un favori a baissé | impossible | 1 geste (pastille sur l'onglet) |
| Textes sous le contraste minimal WCAG AA (accueil · fiche) | 5 · 3 | 0 · 0 |
| Zones à toucher sous 44 px (accueil · fiche) | 5 · 6 | 0 · 0 |
| Produits entièrement visibles sans défiler (téléphone) | 3 | 3, avec 7 informations par ligne au lieu de 4 |
| Requêtes vers des tiers à l'ouverture | 1 (Google Fonts) | 0 |
| Poids de la page | 218 Ko, plus la police chargée chez Google | 281 Ko, police comprise |

Parcours vérifié dans un vrai navigateur (Chromium), 14 étapes : accueil et compteurs, filtre « nouvelles », catégorie
depuis l'accueil, recherche, fiche et preuve, clic tracé vers l'enseigne, connexion par lien, favori et son prix suivi,
Explorer, marque suivie, déconnexion, lien expiré, mise en page ordinateur.

## Limites et suites

- Les pictogrammes remplacent les photos, par choix (droits sur les images des enseignes). Si des images deviennent
  possibles (flux marchands, accord), elles prennent la place du pictogramme sans rien changer d'autre.
- « Depuis hier » et la baisse d'un favori ne se voient qu'en ouvrant l'app. Un e-mail du matin, seulement à ceux qui le
  demandent (« votre canapé a baissé de 60 € »), serait le levier de retour le plus fort ; à décider (consentement,
  fréquence).
- La démo est simulée (marques et enseignes fictives) ; les textes et les longueurs de titres réels se vérifieront sur
  les premières enseignes lues depuis le serveur.
