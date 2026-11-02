# Personnalisation — vos deals d'abord, l'intérêt du deal toujours (v56)

Un deal reste le même pour tout le monde : même produit, même prix, même remise. Ce qui change d'une personne à l'autre,
c'est l'ordre. L'app pèse ses rayons et ses marques d'après ce qu'elle choisit et ce qu'elle regarde, et fait passer ses
deals devant, sans jamais faire oublier l'intérêt du deal. Pas de modèle appris ni d'IA : quelques règles écrites,
versionnées et testées (`deals/profile.py`, `tests/test_profile.py`), mesurées sur des personnes simulées
(`python -m bench.profiles`) et, en production, sur des témoins.

Rien ne bloque l'entrée : on lit sans compte et sans rien dire de soi. Choisir ses rayons est facultatif, d'un geste
(Profil, ou « Mes rayons » sur la page d'une catégorie) ; le reste s'apprend en naviguant. Depuis la v56, tout ce qu'on
garde (rayons, favoris, marques, recherches sauvegardées) se garde sans e-mail : un compte invité, créé au premier geste
qui garde quelque chose, le tient pour cet appareil (`docs/RECHERCHE.md`).

## Ce qui compte

| Signal | Comment il compte | Visite sans compte | Compte (invité ou avec e-mail) |
|---|---|---|---|
| Rayon choisi (Profil, page d'une catégorie) | choisi : affinité 1 | — (le geste crée le compte invité) | `interests` |
| Marque suivie | choisi : affinité 1 | — (idem) | `follows` |
| Recherche sauvegardée ou alerte de prix : son rayon, sa marque, ou ceux de son produit | choisi : affinité 1 | — (idem) | `missions` |
| Favori | vu : 2 points | — (idem) | `saves` |
| Clic vers l'enseigne | vu : 1,5 point | la visite, en mémoire | `clicks` si le compte apprend, sinon la visite |
| Recherche qui nomme un rayon ou une marque (« lave-linge 9 kg », « matelas dormea ») | vu : 1 point | ce navigateur (`deals.recent`) | idem |
| Fiche ouverte | vu : 0,5 point | la visite, en mémoire | `views` si le compte apprend, sinon la visite |

- Un signal vu compte **moitié moins tous les 30 jours** (un compte : 90 jours au plus, depuis la dernière remise à zéro).
- **La confiance monte avec les points** : pleine à 2 points (un favori, deux clics, quatre fiches). L'affinité d'un rayon
  vu vaut 0,8 × confiance × (ses points / ceux du rayon le plus regardé) : **0,8 au plus**, sous un rayon choisi.
- Une **marque vue** pèse moitié moins (0,4 au plus) et ne compte qu'à partir d'un point (deux fiches, ou un clic) : on
  parcourt des rayons plus que des marques.
- Un rayon donne **30 % de son affinité à sa famille** (électroménager, électronique, ameublement, literie) : la découverte reste
  proche des goûts sans les noyer.
- Une recherche nomme un rayon quand elle contient l'un de ses noms, le plus précis (« lave-linge séchant » : les
  lave-linge séchants, pas les lave-linge), et à défaut quand tous ses mots le nomment (« plaque induction ») ; une marque,
  par un mot d'au moins trois lettres qui commence l'un des siens (« d'angle » ne nomme pas Dormea).

## Ce que ça change

**Le score d'un produit = l'intérêt du deal × (1 + ½ affinité)**, donc au plus × 1,5 — autant qu'une marque suivie
avant. L'intérêt du deal, c'est la remise ; pour un prix bas sans remise, ce qu'il fait économiser sur le prix habituel.
Une remise de 40 % hors de vos rayons passe devant une remise de 26 % dans vos rayons (26 × 1,5 = 39) ; une remise de
25 % dans vos rayons (37,5) passe devant une remise de 30 % ailleurs ; à égalité, la plus forte remise d'abord.

Deux garde-fous de plus : **une place sur quatre va au meilleur deal restant**, sans les goûts (découverte, et la plus
forte remise du jour reste en vue) ; **jamais plus de deux produits d'un même rayon sur quatre de suite** (trois au
plus dans les top deals).

| Écran | Avec des goûts connus |
|---|---|
| Top deals (leur onglet, ouvert au lancement) | dans l'ordre du profil ; la plus forte remise du jour y reste |
| « Pour vous » (Explorer, en premier) | les deals et les prix bas de vos rayons et de vos marques (affinité directe ≥ 0,3, pas la seule famille), dix au plus, top deals compris (ils ont leur onglet ; les en retirer vidait la section : sur la démo, après « aspirateur balai », 4 cartes → 1) ; « Vos rayons : Canapés, Matelas » (ceux que vous avez choisis), « D'après vos recherches : Aspirateurs » (vos recherches sauvegardées, vos alertes) ou « D'après vos visites : Canapés » dit pourquoi ; « Modifier » mène au Profil |
| Inspirations du moment | les pièces de vos rayons d'abord |
| Notre sélection | le reste des remises, dans l'ordre du profil |
| Recherche, avant toute saisie | « Pour vous » (« D'après vos recherches », ou « D'après vos goûts ») : les produits de vos dernières recherches, puis ceux de vos rayons et de vos marques, un sur quatre pris ailleurs, puis tout le catalogue |
| Une recherche, un filtre, une page de marque ou de catégorie | rien ne change : on répond à ce qui est demandé |

Sans goûts connus, ou pour un témoin, l'ordre est exactement celui d'avant (la remise, × 1,5 pour une marque suivie).

## Sans bloquer l'entrée

- **Le Profil, centre de commande** (v56) : vos recherches sauvegardées, vos alertes de prix, vos favoris, vos marques
  (« Ajouter » : toutes celles du catalogue, à suivre d'un geste), vos rayons (un geste chacun : « C'est noté : vos rayons
  passent en tête »), « Ce que l'app a compris » (rayons et marques vus, qui mènent à leur page) et « Oublier », et un
  interrupteur : sans e-mail, « Me reconnaître à mon retour » (désactivé par défaut) ; avec un e-mail, « Tenir compte des
  fiches que j'ouvre ». L'encart de l'accueil de la v55 (« Qu'est-ce qui vous intéresse ? ») a rejoint le Profil :
  l'accueil reste aux deals. Les rayons choisis dans le navigateur en v55 passent sur le compte invité à la visite
  suivante.
- **L'e-mail, quand on veut** : rattaché au compte invité, il garde tout (rien n'est perdu) ; s'il a déjà un compte, ce
  que l'invité gardait y est versé.

## Vie privée : ce qui est gardé, et où

- **Une visite sans compte** : le serveur ne garde rien des goûts ; l'app envoie avec chaque lecture les fiches ouvertes
  et les clics de la visite (`p`, au plus 60, avec leur âge en jours) et les recherches récentes (`recent`) ; ni table
  ni journal d'accès ne les retient (`deploy/Caddyfile`). Les fiches vues restent comptées pour la mesure de conversion,
  sans identifiant.
- **Un compte invité** (sans e-mail, créé au premier geste qui garde quelque chose) : ce que la personne a choisi de
  garder (rayons, favoris, marques, recherches sauvegardées et alertes), sous un identifiant sans rien d'elle, que seul
  le cookie de cet appareil désigne. Il n'apprend pas des fiches ouvertes ni des clics (`prefs.learn` à 0) tant que la
  personne n'active pas « Me reconnaître à mon retour » : la visite les envoie (`p`), comme sans compte.
- **Avec un e-mail** : la même chose, plus l'adresse. « Oublier » efface l'effet des fiches et des clics passés sur
  l'ordre ; ils restent dans les mesures de conversion. « Effacer mes données » efface le compte et tout ce qu'il
  gardait (fiches vues et clics restent dans les mesures, sans lien avec personne).
- Je ne suis pas juriste : garder ce que la personne a choisi elle-même (ses rayons, ses favoris, ses recherches, par
  le cookie du compte invité ou dans le navigateur) relève du service qu'elle demande ; garder ce qu'elle a regardé pour la reconnaître plus tard est de la
  personnalisation, d'où l'accord demandé (interrupteur désactivé par défaut), dans l'esprit des recommandations de la
  CNIL sur les traceurs. Pour les comptes, l'apprentissage par les fiches et les clics se refuse d'un geste et doit
  figurer dans la politique de confidentialité, avec sa base légale. À faire valider avant la mise en ligne.

## Mesurer

**Sur des personnes simulées** (`python -m bench.profiles`, `--scale` pour 3 000 produits ; v56 : mêmes chiffres qu'en v55, à
un millième près) : chaque personne a un ou deux
rayons ; on mesure ce que montrent l'accueil (top deals, « pour vous », sélection) et le feed de la Recherche, selon ce
qu'elle a fait avant, sur le code d'avant (v54) et sur celui-ci. Clics attendus : un modèle simple (attrait de la carte
× biais de position) ; l'attrait d'une carte dépend de son rayon (1 pour ceux de la personne, 0,3 pour leur famille, 0,1
sinon) et de sa remise.

| 3 000 produits, 80 personnes (v54 → v55) | Accueil : cartes de ses rayons | Accueil : clics attendus | Remise moyenne montrée | Feed : cartes de ses rayons |
|---|---|---|---|---|
| Nouvelle visite | 19 % → 19 % | 1,81 → 1,81 | 29,6 % → 29,6 % | 18 % → 18 % |
| Rayons choisis (encart) | 19 % → **60 %** | 1,81 → **3,76** (+107 %) | 29,6 % → 29,1 % | 18 % → **75 %** |
| 3 fiches ouvertes | 19 % → **56 %** | 1,81 → **3,56** (+97 %) | 29,6 % → 28,9 % | 18 % → **75 %** |
| A cherché son rayon, ouvert 2 fiches | 19 % → **55 %** | 1,81 → **3,56** (+96 %) | 29,6 % → 29,0 % | 53 % → **94 %** |
| A cherché « canapés pas cher » | 19 % → **54 %** | 1,81 → **3,51** (+93 %) | 29,6 % → 29,0 % | 18 % → **77 %** |
| Compte avec historique | 22 % → **43 %** | 1,97 → **3,02** (+54 %) | 28,7 % → 28,7 % | 21 % → **45 %** |
| Mission en cours | 19 % → **50 %** | 1,81 → **3,28** (+81 %) | 29,6 % → 29,1 % | 18 % → **69 %** |

Accueil : les 20 premières cartes (top deals, « pour vous », notre sélection). Une nouvelle visite voit exactement
l'ordre d'avant ; la remise moyenne montrée baisse à peine. Sur la démo (59 produits, 13 remises un jour ordinaire),
l'accueil ne peut que réordonner : la première carte des rayons de la personne passe du rang 5,1 au rang 1,1 à 2,1, et
les clics attendus sur les top deals de 0,79 à 1,00–1,10 (+27 à +39 %) ; « Pour vous » y est presque toujours vide (ses
deals sont déjà dans les top deals). Coût, sur 3 000 produits : une lecture sans goûts comme avant (deals du jour
~1,9 ms ; ~2 ms de plus avec un compte, pour lire ses signaux) ; top deals et « pour vous » personnalisés 9 à 11 ms ;
le feed orienté par des fiches ouvertes ou quatre recherches ~21 à 26 ms (~12 ms sans goûts).

**En production, sur des témoins** : une personne sur dix voit l'ordre sans les goûts (un compte : toujours le même, par
un hachage de son identifiant ; sans compte : tiré à chaque visite). Fiches vues et clics portent leur variante (`p`
personnalisé, `t` témoin) ; `python deals.py metrics` donne `by_variant` : fiches vues, clics et taux de clic par
variante et par écran. Pour lire un écart de taux de clic de 10 % à 12 %, il faut environ 3 500 fiches vues du côté
témoin (soit ~35 000 au total) : quelques semaines selon le trafic.

## Limites, et la suite

- Des règles sur les rayons et les marques : pas de « ceux qui ont aimé ceci ont aussi aimé », pas de budget appris
  (le prix maximum d'une mission, les prix des fiches ouvertes le diraient), pas de saisonnalité.
- Un compte invité tient à un appareil et à son cookie : effacer les données du navigateur le perd, sauf si un e-mail
  y a été ajouté.
- La rétention passe par le retour : « nouveau dans vos rayons depuis votre dernière visite » sur l'accueil, et, avec
  accord, un e-mail des meilleurs deals de vos rayons, seraient les étapes suivantes.
- Le témoin d'une personne sans compte est tiré à chaque visite : le mesurer par visite est juste, par personne non.
