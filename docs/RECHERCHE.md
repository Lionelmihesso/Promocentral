# La Recherche de DEALS — trouver vite, comprendre un besoin, garder sans e-mail (v56, v57)

DEALS n'est pas un fil de bons plans à faire défiler : on vient chercher quelque chose et on doit le trouver vite. Deux
leviers : **on vous recommande** (l'accueil et le feed suivent vos goûts, `docs/PERSONNALISATION.md`) et **vous
cherchez** — une phrase comme on la dit, comprise en critères qu'on modifie d'un geste, une recherche qu'on garde et que
DEALS surveille ; depuis la v57, dans un domaine qui a son ontologie (les aspirateurs), un **besoin** compris, une
sélection classée et expliquée. Le tout sans IA (des règles écrites, testées) et sans e-mail.

## Une phrase, des critères

`deals/query.py` lit la phrase tapée (`read`, pur : même phrase, même lecture) :

| Ce qui est dit | Ce qui est compris |
|---|---|
| un rayon (« aspirateur », « frigo », « aspi », « canapés ») | la catégorie ; un rayon pas encore suivi est dit (« Les smartphones ne sont pas encore suivis »), sans résultat inventé |
| une pièce (« pour le salon », « chambre ») | ses rayons (`labels.ROOMS`), seulement si aucun rayon n'est nommé |
| une marque du catalogue | la marque |
| « balai », « sans fil », « d'angle »… | les fonctions (toutes exigées) |
| « 9 kg », « 160x200 », « 160 × 200 », « 60 cm », « classe C », « 40 min » | la capacité, la taille, la largeur (à 6 % près), la classe énergie (ou mieux), l'autonomie… (au moins, sauf la taille de literie, exacte) |
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

**Chaque critère devient une puce** (« Aspirateurs », « Balai », « Sans fil », « Moins de 300 € ») : la toucher ouvre
**Affiner**, sa croix la retire et la recherche s'élargit aussitôt. Dès qu'on touche une puce, la phrase devient des
critères de l'app et le champ ne garde que les mots en plus : rien n'est compris deux fois. Chaque geste part du dernier
état voulu, sans attendre la réponse du précédent. Une recherche faite de puces se garde parmi les recherches récentes
en mots lisibles (« Matelas · Moins de 500 € ») et, relue, redonne exactement les mêmes critères (vérifié pour toutes
les phrases du banc).

## Un besoin (v57, les aspirateurs)

« Aspirateur pour mon chat avec du parquet, 300 € max », « robot qui se vide tout seul », « silencieux pour le soir » :
dans un domaine qui a son ontologie, la phrase dit aussi un **type** (robot, balai, traîneau, laveur, à main), des
**caractéristiques exigées** (« sans fil », « sans sac », « HEPA ») et des **besoins** (« chat », « allergies »,
« escaliers », « 120 m² »). Les besoins deviennent des puces (« Pour Poils d'animaux ») et un encadré qui dit ce qu'ils
demandent et d'après quels mots. La sélection est classée par adéquation (d'abord ce dont la fiche dit qu'il convient,
puis ce dont elle ne dit rien, puis le reste), chaque carte dit pourquoi ; un besoin sans exception (laver le sol)
écarte ce qui ne peut pas y répondre, et le dit. Une demande vague (« quel aspirateur choisir ? ») reçoit une question
utile, qui ne bloque rien ; un type qui ne peut pas répondre à un besoin (« robot pour les escaliers ») garde sa
sélection, et un autre type est proposé avec sa raison ; une référence (« Kessler Aero 12 ») vient en premier. Règles,
format et mesures : `docs/ONTOLOGIE.md`.

## Affiner

Une feuille qui rassemble tout ce que la recherche demande, modifiable à tout moment : le **rayon** (celui choisi seul,
« Changer de rayon » déplie la liste), ses **fonctions** et ses **tailles** (celles qui existent dans ce rayon), la
**marque**, le **budget** (de… à…, ou un plafond proposé), la **promo**, le **tri**. Chaque choix dit combien de
produits la recherche donnerait avec lui, ses autres critères gardés ; un choix qui ne donnerait rien, ou qui ne
changerait rien, n'est pas proposé (sauf s'il est déjà pris, pour pouvoir le retirer). Le bouton dit le résultat
(« Voir 5 produits »). Dans un domaine qui a son ontologie, Affiner propose le **type**, l'**usage** et les
caractéristiques qui décident pour ce type (« Filtre HEPA », « Sans sac », « 2,5 kg au plus »), chacune avec son nombre.

## Jamais d'impasse

- **Rien sous le budget** : les plus proches au-dessus, du moins cher au plus cher (« Rien à moins de 50 € · Les plus
  proches, dès 414 € »), et « Me prévenir » : la recherche est sauvegardée avec son budget.
- **Rien du tout** : on le dit, on propose de sauvegarder (« Pas encore là ? On surveille pour vous »), et le feed
  reste là.
- **Une marque tapée** s'ouvre en raccourci au-dessus des résultats.

## Sauvegarder une recherche (les missions)

Une recherche sauvegardée est une **mission** : DEALS la surveille. Le prix est facultatif. « Sauvegarder » sur les
résultats ; la même recherche, retapée, se sait sauvegardée (« Sauvegardée », un geste pour la retirer). Elles sont
dans la Recherche (une ligne, avant toute saisie) et dans le Profil, avec ce qui y répond et **ce qui est nouveau depuis
qu'on l'a ouverte** (« 5 NOUVEAUX » ; la cloche et l'onglet Profil comptent les recherches qui ont du nouveau). L'ouvrir
remet ses critères et oublie ses nouveautés. Une alerte de prix (« Me prévenir sous un prix », depuis la fiche) est une
mission sur un produit ou ses comparables. Les recherches sauvegardées nourrissent le profil : leur rayon et leur marque
comptent comme choisis. La nuit, un e-mail part seulement pour qui a donné son adresse et laissé la cloche de la
recherche allumée, avec ce qui est nouveau à son prix (`deals/missions.py`).

## Sans e-mail

Favoris, marques suivies, rayons, recherches sauvegardées et alertes marchent **sans e-mail**. Au premier geste qui
garde quelque chose, le serveur crée un **compte invité** pour cet appareil : un cookie de session (HttpOnly, SameSite),
valable un an après le dernier geste qui garde, et aucune donnée sur la personne. Au plus 100 créations par adresse IP
et par heure (une box ou un opérateur mobile partagent une adresse) ; un geste qui échoue ne laisse aucun compte ;
chercher, filtrer et ouvrir des fiches n'en crée pas ; la nuit, un compte invité que plus personne ne peut ouvrir (sa
clé a expiré) est effacé. Un compte invité n'apprend pas des fiches ouvertes tant que la personne ne le demande pas
(Profil).

**L'e-mail est facultatif** : « Ajouter mon e-mail » (Profil), ou la cloche d'une recherche sauvegardée. Il sert à
recevoir les alertes et à retrouver ses choix sur un autre appareil (« J'ai déjà un compte »). Le lien ouvert rattache
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
ce qui est demandé (mêmes règles que les missions). Chaque version est mesurée avec son banc : en v57, les phrases sur
les aspirateurs demandent le domaine (robots compris tant qu'aucun type n'est nommé, « balai » est un type), et la
démo compte 25 aspirateurs de plus.

| | v55 démo | v56 démo | v57 démo | v55 3 000 produits | v56 3 000 | v57 3 000 |
|---|---|---|---|---|---|---|
| Produits | 59 | 59 | 84 | 3 000 | 3 000 | 3 000 |
| Phrases dont le catalogue a la réponse | 24 | 24 | 25 | 19 | 19 | 19 |
| Impasses (« Rien pour … » alors que des produits répondent) | 15 | **0** | **0** | 15 | **0** | **0** |
| Première carte juste | 9 | **24** | **25** | 4 | **19** | **19** |
| Pertinence (les n premières cartes) · rappel | 36 % · 36 % | **100 % · 100 %** | **100 % · 100 %** | 21 % · 21 % | **100 % · 100 %** | **100 % · 100 %** |
| Phrases sans réponse au catalogue : réponse vide | 17 | **0** (les plus proches) | **0** | 22 | 20 | 20 |

Lecture honnête : la pertinence à 100 % vient en partie de la construction (la Recherche et la vérité du banc suivent
les mêmes règles que les missions) ; ce que le banc mesure vraiment, c'est que la phrase est comprise et que plus aucune
ne tombe dans une impasse. Le catalogue de 3 000 produits n'a que 8 rayons (lave-linge, réfrigérateurs,
lave-vaisselle, fours, canapés, lits, matelas, tables), aucun aspirateur, et des marques numérotées : 20 phrases n'y ont
aucun produit qui réponde, même au-dessus du budget ; l'écran le dit, propose de sauvegarder et garde le feed. Ce que
la v57 change pour les besoins se mesure sur un autre banc, à vérité connue (`python -m bench.needs`,
`docs/ONTOLOGIE.md`) : bons parmi les 6 premières cartes 35 % → 96 %, mots ignorés 42 → 0.

## Vérifier

- Tests : `tests/test_query.py` (lecture d'une phrase, puces relues à l'identique, migration v11 → v12),
  `tests/test_catalog.py` (Affiner et ses nombres, `said`, le parcours d'un besoin), `tests/test_ontology.py` et
  `tests/test_journey.py` (v57), `tests/test_missions.py`, `tests/test_accounts.py` (comptes invités, adresse
  rattachée ou versée, clé renouvelée, effacement), `tests/test_autonomy.py` (invités expirés la nuit). 125 mutations
  des règles v57 (ontologie, code et données ; moteur de parcours ; phrase ; Recherche ; missions ; API ; profil) :
  toutes détectées. Les 104 mutations de la v56, rejouées sur la v57 : 97 s'appliquent encore, 93 détectées ; des
  quatre autres, l'une visait du code devenu mort (retiré), trois ont reçu un test (détectées).
- Navigateur (Chromium, 79 étapes, deux passages) et audit d'accessibilité (86 écrans : contrastes, zones à toucher,
  noms accessibles, feuilles modales titrées) : sans défaut.
- Temps, 3 000 produits (`python -m bench.scale`) : une phrase comprise ~2,6 ms (~11 ms en v56 : seuls les produits
  du rayon sont lus), critères choisis ~6 ms, une pièce ~16 ms, les recherches d'un invité ~7 ms ; avec 640
  aspirateurs de plus (`--aspirateurs 640`) : un besoin ~12 ms, la question d'une demande vague ~15 ms, Affiner par type
  ~12 ms, Explorer ~4 ms.

## Où sont les règles

| Règle | Où |
|---|---|
| Lire une phrase, dire ses critères en puces, une caractéristique répond-elle | `deals/query.py` (`read`, `chips`, `fits`, `satisfies`) ; libellés `deals/labels.py` |
| Chercher : la phrase et les critères de l'app, les mots qui restent, les plus proches, Affiner et ses nombres | `deals/catalog.py` (`search`, `_options`) |
| Un besoin (v57) : l'ontologie du domaine, le moteur de parcours, Affiner par type et usage, Explorer | `deals/ontology/`, `deals/journey.py`, `deals/catalog.py` (`_journey`, `_domain_options`, `explore`) ; `docs/ONTOLOGIE.md` |
| Sauvegarder, ce qui est nouveau, la cloche, la nuit | `deals/missions.py` |
| Compte invité, adresse rattachée ou versée, effacer | `deals/accounts.py`, `deals/api.py` (`_keep`) |
| L'écran | `web/src/App.jsx` (Recherche, `RefineSheet`, `EmailSheet`, `BrandSheet`, Profil ; v57 : les trois portes, Explorer, « L'essentiel ») |
