# Runbook — quand l'agent vous écrit

Chaque incident a sa fiche ici : l'e-mail du matin, `deals.py status` et le rapport du matin y renvoient
(`docs/RUNBOOK.md#<fiche>`). Une fiche dit ce que l'agent a déjà fait seul, comment vérifier, comment corriger et comment
revenir à la normale. Sur le serveur, les commandes se lancent avec `sudo deals <commande>` (voir `deploy/README.md`) :
vos gestes sont alors journalisés à votre nom.

Pour commencer, toujours :
```
sudo deals status                     # dernière nuit, catalogue, sources, incidents, décisions en attente
sudo deals incidents                  # incidents ouverts, leurs preuves
sudo deals events --cid <corrélation> # tout ce qui s'est passé pendant la nuit (status donne l'identifiant)
sudo deals actions                    # ce que l'agent a fait, proposé, conseillé ou refusé, et pourquoi
```
Une décision proposée par l'agent s'exécute avec `sudo deals approve <n°>` ou s'écarte avec `sudo deals reject <n°>`.
Un incident se résout tout seul la nuit où la cause a disparu : rien à fermer à la main.

<a id="source-en-echec"></a>
## Source en échec : flux injoignable, illisible, ou sans offre

**Ce que l'agent a fait.** Un flux en échec (réseau injoignable, fichier illisible ou coupé, aucune offre retenue) est
relu une fois dans la nuit et vérifié : si la relance passe, rien n'est signalé. Si elle échoue, l'incident est ouvert ;
il ne vous est écrit qu'à la deuxième nuit (ce peut être passager). Après 3 nuits ratées de suite, la source est mise de
côté (plus lue) ; son flux est relu tous les 3 jours, et s'il se lit de nouveau, l'agent propose de reprendre la source.
Rien n'est supprimé pendant ce temps : ses offres vieillissent (au-delà de 3 jours, plus montrées).

**Vérifier.** `sudo deals batches --source <clé>` (l'erreur du lot : flux injoignable, illisible, ou aucune offre
retenue) ; `sudo deals probe --source <clé>` (le flux se lit-il depuis le serveur, et comment) ; les identifiants du
réseau dans `/etc/deals/deals.env` (`DEALS_FEED_<ENSEIGNE>`) ont-ils changé, l'adhésion au programme est-elle toujours
active ?

**Corriger.** Rien si le réseau est en panne chez lui : la relecture du flux tous les 3 jours dira quand il revient. Un
identifiant qui a changé : `sudoedit /etc/deals/deals.env`. Une correspondance qui ne trouve plus rien : voir [flux
changé](#flux-change).

**Revenir à la normale.** Automatique tant qu'elle n'est pas mise de côté ; sinon `sudo deals sources enable <clé>`, ou
approuvez la reprise que l'agent propose quand le flux se lit de nouveau.

<a id="flux-change"></a>
## Flux changé : plus de prix barré

**Ce que l'agent a fait.** Incident dès la première nuit, avec les commandes à lancer. Le flux se lit (rien à relancer),
mais il ne donne presque plus de prix barré alors que les prix, eux, n'ont pas bougé : la colonne du prix barré (ou du prix
promotionnel) a sans doute changé de nom ou de format chez le réseau. Une fin de promotion fait remonter les prix et n'est
pas une alerte. Le constat compare à la nuit précédente : la nuit suivante, il ne se répète pas tout seul, d'où l'e-mail
dès la première nuit.

**Vérifier.** `sudo deals probe --source <clé>` : les colonnes du flux d'aujourd'hui et la correspondance proposée, à
comparer avec `/etc/deals/feeds/<clé>.json` ; `sudo deals batches --source <clé>`.

**Corriger.** La correspondance de la source (voir [brancher un flux](#brancher-un-flux)), vérifiée sur le fichier gardé
(`sudo deals ingest <clé> --file <fichier> --dry-run`), puis `sudo deals replay <clé>` relit le dernier fichier sans
attendre la nuit.

<a id="prix-suspects"></a>
## Prix suspects en nombre

**Ce que l'agent a fait.** Une variation énorme (prix divisé ou multiplié par deux, ou plus) n'est enregistrée que si le
flux de la nuit suivante la redonne. Enregistré, un prix à moins de 30 % du prix habituel du produit est mis en
quarantaine : pas publié, pas envoyé aux missions. Revenu à la normale, il est libéré et le prix faux est écarté des
courbes ; redonné au même prix les deux nuits suivantes, il est cru et publié. Beaucoup de prix suspects chez une même
enseigne (au moins 5, et 20 % de ses offres) signalent plutôt une correspondance déréglée (prix en centimes, prix
mensuel d'un financement pris pour le prix).

**Vérifier.** `sudo deals quarantine` (les offres retenues, leur prix, le prix habituel) ; `sudo deals batches --source
<clé>` et `sudo deals probe --source <clé>` (la colonne lue comme prix).

**Corriger.** La correspondance du flux (voir [flux changé](#flux-change)). Un prix vérifié chez l'enseigne (vraie
liquidation) se libère à la main : `sudo deals quarantine release <offre>` ; il est publié à la publication suivante
(`sudo deals publish` pour tout de suite).

<a id="catalogue-retenu"></a>
## Publication retenue : le nouveau catalogue fondait

**Ce que l'agent a fait.** Le nouveau catalogue perdait plus de 20 % des produits ou des offres publiés (hors sources
mises de côté, dont le départ est attendu) : il n'est pas écrit, celui de la veille reste en ligne. L'agent propose de
publier quand même. Sans décision, la garde relâche au bout de deux nuits (le catalogue de la veille vieillit) et le dit.

**Vérifier.** `sudo deals partners` (le fichier des partenaires a-t-il changé ? une clé mal écrite ?) et
`sudo deals sources` (une source à l'arrêt ?) ; le rapport du matin, enseigne par enseigne.

**Corriger.** Si la baisse est une erreur : corriger `/etc/deals/affiliate.json` ou la source, puis `sudo deals publish`
(et `sudo systemctl restart deals-web` après une modification de `affiliate.json` : l'app le lit à son démarrage).
Si elle est voulue (partenaire retiré) : `sudo deals approve <n°>` (publier malgré la garde) ; mettez aussi de côté les
sources qui ne sont plus partenaires (`sudo deals sources disable <clé> --reason "plus partenaire"`) pour que le contrôle
de taille du catalogue ne les attende plus.

<a id="catalogue-reduit"></a>
## Catalogue réduit

**Ce que l'agent a fait.** Constaté que les offres publiées sont à moins de 80 % de leur nombre habituel (médiane des 7
nuits précédentes, source par source, hors sources mises de côté). Souvent la suite d'une [publication
retenue](#catalogue-retenu) relâchée après deux nuits.

**Vérifier, corriger.** Comme pour la [publication retenue](#catalogue-retenu). L'incident se résout quand le catalogue
retrouve sa taille, ou quand les sources retirées sont mises de côté.

<a id="fraicheur"></a>
## Fraîcheur du catalogue insuffisante

**Ce que l'agent a fait.** Constaté qu'une part des prix montrés (meilleure offre de chaque produit) n'a pas été lue
depuis 26 h (moins de 90 % : attention ; moins de 70 % : critique). Si toutes les offres en cause viennent de sources
déjà signalées (en échec, mises de côté), l'incident est seulement noté : la cause a déjà son incident.

**Vérifier.** `sudo deals status` (fraîcheur, sources) ; la nuit a-t-elle tourné en entier (étape en erreur) ?

**Corriger.** La cause : une source (voir sa fiche ci-dessus), ou une publication retenue.

<a id="envoi-des-missions"></a>
## E-mails des missions en échec

**Ce que l'agent a fait.** Rien n'est marqué comme envoyé : chaque e-mail repart la nuit suivante, sans doublon. Le
responsable est prévenu par le même SMTP : s'il est en panne, l'e-mail du matin attend son retour (la sonde extérieure,
plus bas, prévient par un autre chemin).

**Vérifier.** `DEALS_SMTP_HOST`, `DEALS_SMTP_PORT`, `DEALS_SMTP_TLS` et les identifiants dans `/etc/deals/deals.env` ;
l'état du fournisseur ; `journalctl -u deals-daily`.

**Corriger.** Le réglage ou le fournisseur ; la nuit suivante renvoie ce qui attendait.

<a id="quota-e-mails"></a>
## E-mails des missions différés (quota)

**Ce que l'agent a fait.** Au-delà de `DEALS_MISSION_MAILS` e-mails dans la nuit, la suite part la nuit suivante. Noté,
pas signalé : c'est le plafond qui joue son rôle.

**Corriger.** Si cela devient courant : relever le plafond, et le quota du fournisseur avec (offre payante).

<a id="envoi-massif"></a>
## E-mails des missions retenus : envoi massif

**Ce que l'agent a fait.** Plus de personnes à prévenir cette nuit que d'habitude (au moins 30, et plus de 3 fois la
médiane des 7 nuits précédentes) : rien n'est parti, rien n'est marqué. Un e-mail envoyé ne se reprend pas ; l'agent
propose l'envoi.

**Vérifier.** La cause est-elle réelle (Black Friday, soldes) ou une erreur de prix en série (voir [prix
suspects](#prix-suspects)) ? `sudo deals quarantine`, `sudo deals status`.

**Corriger.** Si c'est réel : `sudo deals approve <n°>` envoie tout de suite. Sinon : `sudo deals reject <n°>`, corriger
la cause ; la nuit suivante recalcule.

<a id="clics-en-chute"></a>
## Clics en chute

**Ce que l'agent a fait.** Constaté que les clics des dernières 24 h sont sous 30 % de la médiane des 7 jours précédents
(à partir de 20 clics par jour d'habitude).

**Vérifier.** `sudo deals metrics` ; l'app s'ouvre-t-elle, la route `/api/r/out/<offre>` redirige-t-elle (un clic sur
« Voir l'offre ») ? Le lien affilié du réseau a-t-il changé ?

**Corriger.** Le gabarit du lien dans `/etc/deals/affiliate.json`, puis `sudo systemctl restart deals-web` (l'app lit les
partenaires à son démarrage) ; ou l'app elle-même (`journalctl -u deals-web`).

<a id="nuit-en-erreur"></a>
## Étape de la nuit en erreur

**Ce que l'agent a fait.** Une étape qui casse n'arrête pas les suivantes ; l'erreur devient un incident critique (le nom
de l'étape est l'entité) et la nuit est marquée « en erreur » (la sonde extérieure répond 503).

**Vérifier.** `sudo deals events --cid <corrélation>` (l'erreur et son message), `journalctl -u deals-daily`.

**Corriger.** La cause (disque plein, base verrouillée, bogue), puis relancer : `sudo systemctl start deals-daily`.

<a id="brancher-un-flux"></a>
## Brancher ou régler le flux d'une enseigne

Pas un incident : le geste courant. Le détail pas à pas est dans `deploy/README.md` (§ 9).
```
sudo deals probe --source <enseigne>        # l'échantillon, lu à l'adresse de la source : format, colonnes, correspondance proposée
sudoedit /etc/deals/feeds/<enseigne>.json   # la correspondance, corrigée
sudo deals ingest <enseigne> --dry-run      # tout lu et contrôlé, rien écrit : retenues, refus et raisons
sudo deals ingest <enseigne>                # un lot réel ; sudo deals batches pour le voir
sudo systemctl restart deals-web            # après une modification de affiliate.json ou de deals.env (lus au démarrage de l'app)
sudo deals replay <enseigne>                # après une correction : relire le dernier fichier gardé, sans attendre la nuit
```
Une source flux se met de côté et se reprend comme une autre (`sudo deals sources disable|enable <clé>`). Les adresses
des flux portent les identifiants du réseau : elles vivent dans `/etc/deals/deals.env` (`DEALS_FEED_<ENSEIGNE>`), jamais
dans `sources.json`, et ne sont jamais écrites dans un message, un lot ou un rapport.

<a id="flux-lignes-refusees"></a>
## Flux : trop de lignes refusées

**Ce que l'agent a fait.** Rien de plus que le dire : le flux a été lu et ses offres valides écrites ; au moins 20 % des
lignes dans le périmètre ont été refusées (prix manquant, devise, occasion, adresse invalide). Les lignes refusées ne sont
ni publiées ni comptées ; le lot passe en « partial ».

**Vérifier.** `sudo deals batches --source <clé>` (le lot et ses comptes), puis `sudo deals batches --rejects <lot>` :
chaque ligne refusée, sa raison et un extrait de la ligne. Les raisons sont aussi dans le rapport du matin.

**Corriger.** Si une colonne a changé de nom ou de format dans le flux : la correspondance de la source
(`/etc/deals/feeds/<clé>.json`), vérifiée sur le fichier gardé (`sudo deals ingest <clé> --file <fichier> --dry-run`, ou
`sudo deals probe <fichier>`), puis `sudo deals replay <clé>` relit le dernier fichier sans attendre la nuit. Si ce sont
de vraies offres sans prix (produits épuisés, hors ligne) : rien à corriger.

<a id="flux-en-baisse"></a>
## Flux : deux fois moins d'offres que la veille

**Ce que l'agent a fait.** Constaté que le lot retient moins de la moitié des offres du lot précédent. Rien n'est supprimé :
les offres absentes vieillissent (au-delà de 3 jours, plus montrées) ; si le catalogue perd plus de 20 % de ses offres, la
publication est retenue (voir [publication retenue](#catalogue-retenu)).

**Vérifier.** `sudo deals batches --source <clé>` : le nombre de lignes reçues a-t-il chuté (flux tronqué chez le réseau,
téléchargement coupé) ou est-ce le nombre de lignes refusées qui monte (voir ci-dessus) ?

**Corriger.** Un flux tronqué : relancer `sudo deals ingest <clé>` quand le réseau le sert en entier, ou attendre la nuit.
Un changement voulu de l'enseigne (catalogue réduit) : rien, l'incident se résout quand les lots se stabilisent.

<a id="mise-a-jour"></a>
## Une mise à jour ratée

**Ce qui s'est passé seul.** `deploy/release.sh install` a sauvegardé la base, basculé sur la nouvelle version, puis ses
tests de fumée ont échoué : la version d'avant est revenue d'elle-même (et la base d'avant, si la nouvelle l'avait
migrée). La sortie de la commande dit quel contrôle a échoué. Si la nouvelle version avait migré la base, la base courante est d'abord mise de côté dans `/var/backups/deals/abandonnee-*.sqlite` : les écritures faites depuis (comptes, clics, missions) y restent, et se reprennent à la main si elles comptent.

**Vérifier.** `sudo sh /opt/deals/current/deploy/release.sh list` (la version en service) ; `python3
/opt/deals/current/deploy/smoke.py http://127.0.0.1:8000` (les contrôles, un par ligne) ; `journalctl -u deals-web --since "-10 min"`.

**Corriger.** Le défaut dans le code, un nouveau commit, une nouvelle archive, essayée d'abord hors production. Si les
services ont changé (`deploy/*.service`, `*.timer`), les recopier et `sudo systemctl daemon-reload` (`deploy/README.md` § 11). Une
version qui passe ses tests mais se révèle mauvaise ensuite : `sudo sh /opt/deals/current/deploy/release.sh rollback`.

<a id="nuit-absente"></a>
## Pas de nuit depuis plus de 36 h

L'agent ne peut pas signaler une nuit qui n'a pas lieu : c'est `deals.py status` et la sonde extérieure qui le voient.

**Vérifier.** `systemctl list-timers deals-daily.timer`, `systemctl status deals-daily`, `journalctl -u deals-daily`.

**Corriger.** `sudo systemctl enable --now deals-daily.timer`, puis `sudo systemctl start deals-daily`.

<a id="sonde"></a>
## Sonde extérieure (`/api/r/health`)

Une sonde HTTP extérieure (UptimeRobot, Healthchecks, Better Stack…) sur `https://<domaine>/api/r/health` prévient par
un autre chemin que le SMTP de la plateforme, en GET ou en HEAD. Réponse 200 (`ok`, ou `degraded` : un incident sérieux ouvert) ou 503
(`critical` : aucune nuit depuis 36 h, dernière nuit en erreur, ou incident critique ouvert). Rien d'autre n'est exposé
que l'état, l'heure de la dernière nuit et la taille du catalogue.
