# L'interface de DEALS — minimaliste, sans friction (v44)

## Principe

Une liste se lit en un regard : **marque, produit, prix, remise**. Rien d'autre sur l'accueil ni dans les listes.
La qualité est implicite : l'app ne montre que de vraies remises, elle n'a pas à l'écrire (aucune mention « vérifiée »,
aucun compteur de fausses promos). Les durées (depuis quand la remise court, jusqu'à quand l'enseigne la déclare) ne
sont que dans la fiche, en une ligne, à côté du bouton « Voir l'offre ».

Gardé des maquettes v27 à v42 : le produit comme entrée (l'enseigne n'est qu'un attribut), un deal identique pour tous,
pas d'image en V1, le signet sur chaque ligne, le suivi des marques, la connexion demandée au moment de l'action,
l'identité visuelle (noir, blanc, orange, Manrope).

## Ce que montre chaque écran

| Écran | Contenu |
|---|---|
| Aujourd'hui | « 13 remises aujourd'hui », recherche, catégories (un geste pour filtrer), le plus intéressant, les autres |
| Ligne de liste | marque, produit, prix, remise, signet |
| Fiche | marque · catégorie, produit, remise, prix et prix barré, « En remise depuis 2 jours, jusqu'au ven. 26 déc. », « Voir l'offre chez … », autres enseignes, produits similaires |
| Explorer | recherche ; catégories par famille (pictogramme et nom) ; marques |
| Favoris | produits gardés (« Baisse de 64 € » seulement quand le prix a baissé, pastille sur l'onglet), marques suivies |

Retiré de la v43, à la demande (trop d'informations, lecture alourdie) : « Toutes vérifiées », « fausses promos
écartées », « Depuis hier » (nouvelles, finissent bientôt), le signal de chaque ligne (finit bientôt, nouveau, plus bas
depuis n jours, vérifiée), l'enseigne et le prix barré dans les listes, la date de relevé dans l'en-tête, le bloc
« Pourquoi c'est un vrai deal » de la fiche, les compteurs des catégories et des marques. Les données qui ne servaient
qu'à ces éléments ne sont plus calculées ni stockées (preuve, plus bas prix relevé, filtres « depuis hier »).

## Mesures (mêmes données de démo, téléphone 390 × 844)

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

Parcours vérifié dans un vrai navigateur (Chromium), 14 étapes, dont deux contrôles du principe : aucune durée ni
mention de vérification sur l'accueil, 4 éléments par ligne ; durées présentes dans la fiche. Captures : `docs/ux/`.
