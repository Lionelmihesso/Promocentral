# La Recherche de Promo Central — trouver vite, garder sans e-mail

Promo Central n'est pas un fil de bons plans à faire défiler : on vient chercher quelque chose et on doit le trouver vite. Deux
leviers : **on vous recommande** (les top deals, Explorer et le feed suivent vos goûts, `docs/PERSONNALISATION.md`) et **vous
cherchez** — une phrase comme on la dit, comprise en critères qu'on modifie d'un geste, une recherche qu'on garde et que
la plateforme surveille ; dans chaque rayon et son ontologie (v58 : les aspirateurs ; v59 : tous, électronique comprise), le
**type** et un ou deux **attributs** lus dans les offres ; v60 : **Affiner en entonnoir**, une question à la fois, dans
la Recherche et sur les pages d'une marque, d'une catégorie, d'une pièce. Le tout sans IA (des règles écrites, testées)
et sans e-mail.

## Une phrase, des critères

`deals/query.py` lit la phrase tapée (`read`, pur : même phrase, même lecture) :

| Ce qui est dit | Ce qui est compris |
|---|---|
| un rayon (« aspirateur », « frigo », « aspi », « canapés », « télé », « smartphone ») | son domaine (le rayon et son ontologie) ; un rayon pas encore suivi est dit (« Les micro-ondes ne sont pas encore suivis »), sans résultat inventé |
| une pièce (« pour le salon », « chambre ») | ses rayons (`labels.ROOMS`), seulement si aucun rayon n'est nommé |
| une marque du catalogue | la marque |
| « balai », « OLED », « d'angle »… ; « sans fil », « 5G », « No Frost », « convertible »… | le type ; les attributs oui ou non (tous exigés), chacun dans la langue de son rayon (`deals/ontology`) |
| « 9 kg », « 160x200 », « 60 cm », « classe C », « 40 min », « 55 pouces », « 55" », « 139 cm » (un téléviseur), « 256 Go », « 16 Go de RAM », « 144 Hz », « 6 tiroirs » | la capacité, la taille, la largeur (à 6 % près), la classe énergie (ou mieux), l'autonomie, la taille d'écran (à 5 % près), le stockage, la mémoire, la fréquence, les tiroirs… (au moins, sauf la taille de literie, exacte) |
| « sous 300 € », « moins de 300 », « 300 € » | le budget maximum |
| « entre 200 et 400 € », « de 200 à 400 € », « dès 300 € », « à partir de 300 € » | un budget de… à…, un minimum |
| « en promo », « −30 % » | une remise (au moins), jusqu'à 90 % |
| « au plus bas », « prix bas » | un prix parmi les plus bas depuis longtemps |
| « pas cher », « petit prix », « prix croissant » | le tri par prix |
| le reste (« velours », « Lina ») | des mots cherchés dans les produits ; les mots vides (« je cherche un… ») sont ignorés |

Les mots qui restent filtrent s'ils trouvent quelque chose ; sinon, ils sont dits (« « velours gris » : aucun produit ;
voici le reste de votre recherche ») et le reste de la demande répond. Une phrase dont rien n'est compris est cherchée
mot à mot, comme avant. L'apostrophe du téléphone (« d’angle ») vaut l'apostrophe droite, partout, titres des produits
compris.

**Chaque critère se montre une fois** : le rayon, le type, les attributs et le budget sont les **étapes de l'entonnoir**
(« Aspirateurs », « Balai », « Sans fil », « Moins de 300 € », v60) ; la marque, la promo, le tri et les mots restent
des **puces** (toucher celles de la promo et du tri ouvre leur feuille). Une croix retire l'étape ou la puce et la
recherche s'élargit aussitôt. Dès qu'on touche une étape, une puce ou une réponse, la phrase devient des critères de
l'app et le champ ne garde que les mots en plus : rien n'est compris deux fois. Chaque geste part du dernier
état voulu, sans attendre la réponse du précédent. Une recherche faite de puces se garde parmi les recherches récentes
en mots lisibles (« Matelas · Moins de 500 € ») et, relue, redonne exactement les mêmes critères (vérifié pour toutes
les phrases du banc).

## Les aspirateurs : un type, deux attributs (v58)

Dans un domaine qui a son ontologie, la phrase dit aussi un **type** (robot, balai, traîneau, laveur, à main) et deux
**attributs** (sans fil, sans sac ; « filaire », « avec sac », « à sac » pour non) : « aspirateur traîneau à sac »
donne « Aspirateurs », « Traîneau » et « Avec sac » ; « aspirateur » seul, le domaine entier, robots compris. Un
produit y répond si son offre le dit (son titre ou sa catégorie) ou si son type l'est par définition (un robot est
sans fil) ; ce que l'offre ne dit pas n'est pas promis. Les besoins de la v57 (« pour mon chat », « silencieux ») ne
sont plus compris : le mot est dit sans résultat, comme ailleurs, et le reste de la demande répond. Règles et mesures
: `docs/ONTOLOGIE.md`.

## Affiner en entonnoir (v60)

La feuille Affiner de la v56 à la v59 rassemblait tout (le rayon, le type, les caractéristiques, les tailles, la marque,
le budget, la promo, le tri : 53 choix d'emblée, jusqu'à 8 sections) et n'avait pas de fin : on picorait sans aller au
bout. L'entonnoir (`deals/funnel.py`, pur ; la Recherche lui donne ce qu'elle a compté) pose **une question à la fois**,
dans cet ordre :

1. **Quel univers ?** — High-tech, Entretien, Chambre, Salon, Cuisine, Buanderie (`labels.ROOMS`), seulement quand
   la sélection couvre plus de six rayons et qu'aucune pièce n'est choisie ;
2. **Quel rayon ?** — les rayons de la sélection (ceux de la pièce choisie), les plus fournis d'abord ; choisir
   « Aspirateurs », c'est aussi ses robots (le compte le dit), « Robots aspirateurs » est un rayon à lui seul ;
3. **Quel type ?** puis **chaque attribut du rayon**, dans l'ordre de son ontologie (« Taille d'écran ? »,
   « Définition ? » : 4K ou HD ; « Sac ? » ; « Capacité ? »…) ;
4. **Votre budget ?** — quatre plafonds au plus, choisis dans une échelle (50 € à 5 000 €) pour partager la sélection
   (vers un quart, la moitié, les trois quarts, neuf dixièmes) ; deux plafonds qui donnent la même sélection : le plus bas.

Chaque réponse dit combien de produits elle donne (la sélection, ses autres critères gardés : la marque d'une page, la
promo, les mots), et les donne (vérifié pour chaque réponse de chaque étape, `tests/test_funnel.py`). **Ni tout, ni
rien** : une réponse qui donnerait toute la sélection, ou aucun produit, n'est pas proposée ; une question sans autre
réponse n'est pas posée. « **Passer** » passe à la question suivante (l'app s'en souvient jusqu'à ce qu'on change
de rayon ou de phrase). **La fin** : plus de question, ou une sélection de trois produits ou moins — « Votre sélection »,
son nombre, « Sauvegarder ». Les **étapes franchies** restent au-dessus de la question ; la croix d'une étape revient
avant elle (retirer le rayon retire aussi le type et ses attributs, jamais le budget). Une sélection **toute dans un
rayon** (une marque qui ne fait que des téléviseurs, la pièce Entretien, toute en aspirateurs) y entre d'elle-même : le
rayon est une étape sans croix, et la première question est celle du rayon.

Le même entonnoir est sur la page d'une **marque** (sa marque gardée), d'une **catégorie** (sans répéter son titre) et
d'une **pièce** (ses remises) ; ce qu'on y a choisi reste quand on ouvre une fiche et revient. Rien sous le budget : les
plus proches au-dessus sont montrés, et l'entonnoir compte ceux-là.

Ce qui a disparu avec la feuille : la liste des marques (une marque se tape, ou s'ouvre depuis une fiche), le budget de…
à… (« entre 200 et 400 € » se tape, et se lit), Catégorie et Budget en accès direct (ce sont les premières questions).
Promo et Trier (pertinence, prix croissant ou décroissant, remise) restent des feuilles d'un geste.

## Jamais d'impasse

- **Rien sous le budget** : les plus proches au-dessus, du moins cher au plus cher (« Rien à moins de 50 € · Les plus
  proches, dès 414 € »), et « Sauvegarder » : la recherche est sauvegardée avec son budget (v65 : plus de « Me
  prévenir »).
- **Rien du tout** : on le dit, on propose de sauvegarder (« Pas encore là ? On surveille pour vous »), et le feed
  reste là.
- **Une marque tapée** s'ouvre en raccourci au-dessus des résultats.

## Sauvegarder une recherche (les missions)

Une recherche sauvegardée est une **mission** : la plateforme la surveille. Le prix est facultatif. « Sauvegarder » sur les
résultats ; la même recherche, retapée, se sait sauvegardée (« Sauvegardée », un geste pour la retirer). Elles sont
dans le Profil (depuis la v61, plus dans la Recherche, qui dit où les retrouver), avec ce qui y répond et **ce qui est nouveau depuis
qu'on l'a ouverte** (« 5 NOUVEAUX » ; la cloche et l'onglet Profil comptent les recherches qui ont du nouveau). L'ouvrir
remet ses critères et oublie ses nouveautés. L'alerte de prix (« Me prévenir sous un prix », depuis la fiche : une
mission sur un produit ou ses comparables) est arrêtée en v65. Les recherches sauvegardées nourrissent le profil : leur rayon et leur marque
comptent comme choisis. La nuit, un e-mail part seulement pour qui a donné son adresse et laissé la cloche de la
recherche allumée, avec ce qui est nouveau à son prix (`deals/missions.py`).

## Sans e-mail

Favoris, marques suivies, rayons et recherches sauvegardées marchent **sans e-mail**. Au premier geste qui
garde quelque chose, le serveur crée un **compte invité** pour cet appareil : un cookie de session (HttpOnly, SameSite),
valable un an après le dernier geste qui garde, et aucune donnée sur la personne. Au plus 100 créations par adresse IP
et par heure (une box ou un opérateur mobile partagent une adresse) ; un geste qui échoue ne laisse aucun compte ;
chercher, filtrer et ouvrir des fiches n'en crée pas ; la nuit, un compte invité que plus personne ne peut ouvrir (sa
clé a expiré) est effacé. Un compte invité n'apprend pas des fiches ouvertes tant que la personne ne le demande pas
(Profil).

**L'e-mail est facultatif** : « Ajouter mon e-mail » (Profil), ou la cloche d'une recherche sauvegardée. Il sert à
recevoir les nouveautés de ses recherches et à retrouver ses choix sur un autre appareil (« J'ai déjà un compte »). Le lien ouvert rattache
l'adresse au compte invité — rien n'est perdu — ou, si un compte existe déjà pour elle, y verse tout ce que l'invité
gardait (sans doublon : la même recherche n'est gardée qu'une fois) ; ce que la personne voyait déjà dans l'app ne lui
est pas envoyé par e-mail. « Effacer mes données » efface le compte et ce qu'il gardait (fiches vues et clics restent
dans les mesures, sans lien avec personne), et le navigateur oublie ses recherches récentes.

Note (je ne suis pas juriste) : le cookie du compte invité sert seulement à garder ce que la personne a demandé de
garder (un favori, une marque, un rayon, une recherche) ; il paraît relever des traceurs strictement nécessaires au
service demandé, dispensés de consentement selon les lignes directrices de la CNIL. Les recherches récentes gardées par
le navigateur (pour les reproposer et orienter le feed) relèvent du même examen ; garder les fiches ouvertes d'une
visite à l'autre reste soumis à l'accord (« Me reconnaître à mon retour », désactivé par défaut). Aucun traceur de
publicité n'est posé. À faire valider avant la mise en ligne, avec la mention correspondante dans « Comment ça marche »
et la politique de confidentialité (durée : un an, renouvelée à chaque geste qui garde).

## Mesures (`python -m bench.search`)

41 phrases comme on les tape (celles du banc des missions et les exemples de la Recherche), la première réponse de
l'API, sans rien toucher d'autre. Ce qu'attend chaque phrase est écrit à la main ; une carte y répond si elle a tout
ce qui est demandé (mêmes règles que les missions). Chaque version est mesurée avec son banc : depuis la v57, les
phrases sur les aspirateurs demandent le domaine (robots compris tant qu'aucun type n'est nommé, « balai » est un
type), et la démo compte 25 aspirateurs de plus. La v58 donne, phrase par phrase, les mêmes chiffres que la v57 (démo
et 3 000 produits).

| | v55 démo | v56 démo | v57 démo | v59 démo | v55 3 000 produits | v56 3 000 | v57 3 000 | v59 3 000 |
|---|---|---|---|---|---|---|---|---|
| Produits | 59 | 59 | 84 | 127 | 3 000 | 3 000 | 3 000 | 3 000 |
| Phrases | 41 | 41 | 41 | 62 | 41 | 41 | 41 | 62 |
| Phrases dont le catalogue a la réponse | 24 | 24 | 25 | 43 | 19 | 19 | 19 | 19 |
| Impasses (« Rien pour … » alors que des produits répondent) | 15 | **0** | **0** | **0** | 15 | **0** | **0** | **0** |
| Première carte juste | 9 | **24** | **25** | **43** | 4 | **19** | **19** | **19** |
| Pertinence (les n premières cartes) · rappel | 36 % · 36 % | **100 % · 100 %** | **100 % · 100 %** | **100 % · 100 %** | 21 % · 21 % | **100 % · 100 %** | **100 % · 100 %** | **100 % · 100 %** |
| Phrases sans réponse au catalogue : réponse vide | 17 | **0** (les plus proches) | **0** | **0** | 22 | 20 | 20 | 41 |

Lecture honnête : la pertinence à 100 % vient en partie de la construction (la Recherche et la vérité du banc suivent
les mêmes règles que les missions) ; ce que le banc mesure vraiment, c'est que la phrase est comprise et que plus aucune
ne tombe dans une impasse. Le catalogue de 3 000 produits n'a que 8 rayons (lave-linge, réfrigérateurs,
lave-vaisselle, fours, canapés, lits, matelas, tables), aucun aspirateur, et des marques numérotées : 20 phrases n'y ont
aucun produit qui réponde, même au-dessus du budget ; l'écran le dit, propose de sauvegarder et garde le feed. Ce que
la plateforme lit des aspirateurs (le type, sans fil, sans sac) se mesure sur un autre banc, à vérité connue
(`python -m bench.aspirateurs`, `docs/ONTOLOGIE.md`) : type lu juste 149 fois sur 149 quand l'offre le dit, rien de
deviné. v59 : 21 phrases de plus (13 d'électronique, 8 recherches courtes) ; les phrases d'un rayon demandent son
domaine (« frigo américain » : le type américain, « canapé convertible » : l'attribut convertible). Le catalogue de
3 000 produits n'a toujours ni électronique ni aspirateurs : 41 phrases n'y trouvent rien, et l'écran le dit. Ce que la
plateforme lit de chaque rayon se mesure sur `python -m bench.ontologie` (146 produits et 41 pièges, et 64 offres
inédites).

## Vérifier

- Tests : `tests/test_query.py` (lecture d'une phrase, puces relues à l'identique, migration v11 → v12),
  `tests/test_catalog.py` (les options et leurs nombres, `said`, les aspirateurs : type, attributs),
  `tests/test_funnel.py` (v60 : l'ordre des questions, chaque réponse donne son nombre — 187 réponses vérifiées —, la
  fin, les retours, le rayon implicite, ni tout ni rien, les plafonds de budget),
  `tests/test_ontology.py` (le fichier relu, ce qui se lit d'une offre, rien de deviné, la v57 relue),
  `tests/test_missions.py`, `tests/test_accounts.py` (comptes invités, adresse rattachée ou versée, clé renouvelée,
  effacement), `tests/test_autonomy.py` (invités expirés la nuit). 91 mutations des règles v58, puis 54 des règles v59
  (l'ontologie de chaque rayon, code et données ; l'électronique ; les alternatives ; la phrase ; Affiner ; missions ;
  API) : toutes détectées (sept ne l'étaient pas au premier passage de la v59 : elles ont reçu un test) ; v60 : 35
  mutations des règles de l'entonnoir et de sa place dans la Recherche (l'ordre des questions, ni tout ni rien, la
  fin, les retours, les plafonds, le rayon implicite, les comptes quand rien n'est sous le budget, la pièce dite par
  la phrase, le tri décroissant, la fiche sans courbe) : toutes détectées.
- Navigateur (Chromium, 85 étapes, deux passages) et audit d'accessibilité (91 écrans : contrastes, zones à toucher,
  noms accessibles, feuilles modales titrées) : sans défaut.
- Temps, 3 000 produits (`python -m bench.scale`) : une phrase comprise ~2,2 ms, critères choisis ~6 à 8 ms, une
  pièce ~15 ms, les recherches d'un invité ~7 ms ; avec 640 aspirateurs de plus (`--aspirateurs 640`) : « aspirateur
  balai sans fil sous 300 € » ~8 à 10 ms (un besoin ~11 ms en v57), « aspirateur » ~9 ms, Affiner par type ~9 ms
  (~11 ms en v57), une fiche 0,2 ms.

## Où sont les règles

| Règle | Où |
|---|---|
| Lire une phrase, dire ses critères en puces, une caractéristique répond-elle | `deals/query.py` (`read`, `chips`, `fits`, `satisfies`) ; libellés `deals/labels.py` |
| Chercher : la phrase et les critères de l'app, les mots qui restent, les plus proches, les options et leurs nombres | `deals/catalog.py` (`search`, `_options`) |
| Affiner en entonnoir (v60) : l'ordre des questions, ni tout ni rien, la fin, les retours, les plafonds, le rayon implicite | `deals/funnel.py` ; sa place dans la Recherche : `deals/catalog.py` (`search`) |
| Les aspirateurs (v58) : l'ontologie du domaine, Affiner par type et par attribut | `deals/ontology/`, `deals/catalog.py` (`_domain_options`), `deals/query.py` (`fitter`) ; `docs/ONTOLOGIE.md` |
| Sauvegarder, ce qui est nouveau, la cloche, la nuit | `deals/missions.py` |
| Compte invité, adresse rattachée ou versée, effacer | `deals/accounts.py`, `deals/api.py` (`_keep`) |
| L'écran | `web/src/App.jsx` (Recherche, `Funnel` et `funnelAt`, `applyPatch`, les pages d'une marque, d'une catégorie, d'une pièce, `EmailSheet`, `BrandSheet`, Profil ; v58 : vos rayons repliés) |
