# 🐛 Bugs trouvés et corrigés — balise-watch-server

> Entrées courtes, un piège réutilisable par section. Pas un journal de
> session (voir le projet Claude « balise watch » pour ça) — juste ce qui
> mérite de ne pas se refaire piéger la prochaine fois.

---

## 24/08/2026 — une phrase d'explication est ce qui ferme un dossier, et celle-ci était fausse

Retour Yann : *« sur les balises Infoclimat, on n'a ni le vent max ni le
vent min ! Pourtant on le retrouve sur leur site ! »*

Le code disait déjà pourquoi, à trois endroits (`poller_infoclimat.py`,
`index.js` ×2) : **« Les 840 autres n'en mesurent pas — anémomètres
amateur. »** C'était net, ça avait l'air mesuré (ça suivait la
correction du 03/08, elle-même une vraie mesure), et c'est **faux**.

Mesuré le 24/08 par `traces/sonde_rafale_infoclimat.py` — **un** appel
opendata, deux stations :

| | `vent_rafales` (opendata) | leur page infoclimat.fr | matériel déclaré |
|---|---|---|---|
| **00003** Besse sur Issole | `null` × 225 relevés | « raf. 30.6 » à 15h30 | Davis Vantage Pro 2 (2003) |
| **00047** Plabennec (témoin) | 226/226 renseignés | idem | — |

Le relevé de 15h30 est le MÊME des deux côtés : l'API en rend le
`vent_moyen` 12.9, leur page affiche 13 km/h **et** une rafale. La
station mesure la rafale, Infoclimat la stocke et l'affiche — c'est
**l'endpoint opendata** qui la met à `null` pour ~97 % des StatIC (27
séries `raf` sur 875 stations d'historique, relevé le même jour). La
réponse annonce pourtant le champ : `hourly._params` le liste,
`metadata` le décrit « wind gust,km/h ». Il arrive vide, c'est tout.

⚠️ **Piège réutilisable — le vrai n'est pas technique.** Une donnée
absente ne coûte qu'une recherche ; une donnée absente **avec une
explication plausible à côté** coûte des mois, parce que plus personne
ne cherche. La phrase de 03/08 était une INFÉRENCE (« pas de valeur
donc pas de capteur ») écrite dans le même paragraphe qu'une mesure, et
elle en a hérité l'autorité. *Quand un commentaire explique une absence,
vérifier qu'il MESURE l'explication et pas seulement l'absence* — sinon
l'écrire au conditionnel, ou pas du tout.

ⓘ La distinction n'est pas cosmétique côté UI : « cette station n'a pas
d'anémomètre à rafale » et « notre source nous ampute la rafale » ne se
disent pas au pilote de la même façon (le rendu `noGust` du 03/08 dit
aujourd'hui le premier).

ⓘ Rien à corriger dans le code : le poller lit la bonne clé, la seule
qui existe. Le seul chemin de correction passe par Infoclimat.

ⓘ Le « vent **min** », lui, n'existe nulle part chez eux — leur propre
tableau n'a que « vent moyen » et « rafales ». Cf. l'entrée
« non-bug » du 22/07 dans `PWA/web/BUGS.md` : aucune source sauf
Pioupiou n'a de minimum natif.

---

## 23/08/2026 — supprimer un objet sur R2 ne le supprime pas pour un lecteur qui lit le LOCAL d'abord

Le lot S0.9 avait trouvé un manifeste qui déclarait deux parties là où
la nuit n'en avait écrit qu'une, et chiffré le dégât : **513 cases**
basculées en `rank_reason = 'partie_manquante'` sur une nuit complète.
L'arbitrage retenu était « supprimer l'objet ». Il a été exécuté le
23/08 vers 10 h 05 UTC — **sur R2**, et vérifié absent du bucket.

⛔ **Et il ne servait à rien.** `score.read_json` (comme
`score.read_ndjson`) lit **le disque local D'ABORD, R2 ensuite** — son
propre pavé le dit en toutes lettres : *« ⓘ LE LOCAL D'ABORD, ET ÇA
COMPTE POUR LE MANIFESTE. `score.py` tourne sur la même machine que
`collect.py` : si l'envoi R2 du manifeste a échoué, le fichier est quand
même là »*. Or `collect.py` écrit **toujours** en local **puis** monte
sur R2 : tout objet qu'il produit existe en **deux** exemplaires. Le
manifeste local du 23/08 était donc encore là, avec son témoin `.r2ok`,
à quinze heures de la notation — qui l'aurait lu, et aurait fait
exactement le dégât que la suppression R2 croyait avoir évité.

⚠️ **Piège réutilisable** : *avant de « supprimer » un objet d'archive,
énumérer TOUS les endroits d'où il peut être relu, et les supprimer dans
l'ordre inverse de la chaîne de lecture.* Ici : le local d'abord (c'est
lui qui gagne), R2 ensuite. Une suppression qui ne couvre que le
stockage distant est une suppression **qui se croit faite** — la pire
forme, parce qu'elle referme le dossier.

ⓘ Concerne les **trois** producteurs du dépôt (`collect.py`,
`agrume_fcst.py`, `arome_fcst.py`) et leurs quatre flux (`fcst/`,
`fcstagrume/`, `fcstarome/`, `fcstreduit/`), plus les six flux
d'observation : tous écrivent local → R2.
ⓘ Vérification qui clôt le dossier, jouée le 23/08 à 13 h 40 UTC :
`score.fcst_parties()` rejoué **avec un `Storage` R2 réel** rend
`avant_partition` (1 partie sur 1) pour les 21, 22 et 23/08 — pas
`fichier absent`, pas `partie_manquante`. On lit l'état voulu par le
chemin exact de la notation, pas par un `ls`.

---

## 22/08/2026 — un garde-fou dont la fenêtre dépasse ce que l'élagage retient est MUET, pas absent

Le lot S0.3 affirmait deux fois que « ajouter le plafond mensuel
Open-Meteo (300 000 en 30 jours) à `FENETRES` est une ligne ». Ligne
fausse : `Budget._reserver` élague les événements à **86 400 s (24 h)
EN DUR**, pour empêcher le fichier d'état de grossir sans fin. Ajouter
une fenêtre de 2 592 000 s (30 jours) à `FENETRES` SANS toucher cet
élagage donnerait un garde-fou qui ne verrait JAMAIS plus de 24 h
d'événements : il compterait ~4 000 pondérés au lieu des ~122 000
réels, et ne se déclencherait donc JAMAIS — tout en laissant croire,
à la lecture du code, que le plafond mensuel est couvert.

⚠️ **Piège réutilisable** : *avant d'ajouter une fenêtre temporelle à
un compteur qui élague déjà son historique, vérifier que la durée
d'élagage couvre au moins la nouvelle fenêtre — pas seulement que la
nouvelle fenêtre est arithmétiquement correcte.* Un garde-fou dont la
fenêtre nominale dépasse ce que le stockage sous-jacent retient n'est
pas un garde-fou trop large : c'est un garde-fou MUET, plus dangereux
que son absence, parce qu'il donne l'illusion d'une couverture qui
n'existe pas.

ⓘ Prouvé par le banc
(`tools/test_quota_openmeteo.py::TestVersionNaiveEstRouge`) — pas
déduit : la version naïve est reproduite à l'identique (l'ajout
littéral à `FENETRES`, élagage inchangé) et montrée muette sur
300 000 pondérés déjà consommés mais vieux de plus de 24 h. La forme
retenue (lot S0.7) compte le mensuel À PART, en seaux journaliers
agrégés, hors de l'élagage à 24 h — cf. `tools/quota_openmeteo.py`.

---

## 22/08/2026 — le rattrapage filtre par SUFFIXE, et le nouvel objet n'en avait pas le bon

Le lot S0.6 ajoute à l'archive un objet d'un TYPE nouveau : un manifeste
`fcst/2026/08/fcst_2026-08-23.**manifeste.json**`, qui déclare combien
de parties la nuit attend. Tout le reste de l'archive est en
`*.ndjson.gz`.

Or le rattrapage d'envoi R2 cherchait exactement ça :

```python
def en_retard(out):
    return sorted(p for p in out.rglob("*.ndjson.gz") if not temoin(p).exists())
```

⇒ Un manifeste dont l'envoi R2 échoue n'aurait **jamais** été retenté.
Et ce n'est pas « un fichier de moins » : côté `score.py`, un manifeste
absent sur R2 se lit **« journée d'avant la partition »**, donc « une
seule partie », donc la nuit est notée sur **une partie sur deux** — en
silence, avec un classement publié sur deux modèles au lieu de neuf.
**300 octets qui manquent, et le garde-fou tout entier devient muet.**

Le contrôle de fin de run (« ❌ N archives ne sont PAS sur R2 ») avait
le même trou, au même endroit et pour la même raison : il appelle
`en_retard()`.

⚠️ **Piège réutilisable** : *quand on ajoute un TYPE d'objet à une
archive, la question n'est pas « est-ce qu'il s'écrit » mais « qui
d'autre balaie ce répertoire, et par quoi filtre-t-il ».* Ici trois
mécanismes filtrent par suffixe — le rattrapage, le contrôle de fin de
run, et l'en-tête HTTP de l'envoi (`Content-Encoding: gzip` sur du JSON
clair aurait fait échouer tout client qui respecte l'en-tête). Les
trois ont dû être élargis, et aucun ne l'aurait dit en échouant : ils
auraient simplement **ignoré** le nouvel objet.

ⓘ Corrigé et **bancé par mutation** : rétablir le filtre d'origine rend
une assertion rouge. ⚠️ Et la première version de ce banc-là ne
prouvait rien — elle s'appuyait sur un run où l'envoi R2 était simulé
comme réussi, donc « rien en retard » était vrai sans que la propriété
le soit. Le cas est maintenant construit à la main.

---

## 22/08/2026 — un horaire déduit d'une durée espérée, quand le journal donne la mesurée

Le lot S0.4 recommandait de lancer la seconde passe de collecte à
**04:25 UTC**, sur ce raisonnement : « la passe 1 finit au plus tard
vers 03:22, son heure est donc rendue à 04:22 ».

Mesuré au lot S0.6 sur **14 nuits de `journalctl -u bw-model-collect`** :
la passe de prévisions finit ses appels Open-Meteo entre **03:24:08 et
03:28:02**. Le pire cas rend donc son heure à **04:28** — trois minutes
**après** l'horaire recommandé. Une passe 2 partie à 04:25 se serait
retrouvée dans une fenêtre horaire encore occupée par 4 730 pondérés, et
se serait fait refuser point par point.

Le raisonnement n'était pas faux, il était **incomplet** : il partait de
la durée *espérée* de la passe réduite, sans regarder la durée *mesurée*
de la passe actuelle, qui borne le pire cas.

⚠️ **Piège réutilisable** : *une heure de fin se LIT dans le journal ;
elle ne se déduit pas d'une durée qu'on attend.* Quand un horaire doit
s'intercaler entre deux voisins, les deux bornes doivent venir de
`journalctl` ou du fichier de budget — pas d'une addition. Et il faut
prendre le **pire cas observé**, pas la médiane : c'est la nuit longue
qui casse, pas la nuit moyenne.

ⓘ Corollaire tiré au passage : ce qui compte pour une fenêtre
**glissante**, c'est l'instant du **dernier appel facturé**, pas la fin
du run. La collecte du 22/08 a fini ses appels Open-Meteo à 03:28:02 et
son run à 03:45:46 — 17 minutes plus tard, sans consommer un pondéré.
Raisonner sur la fin du run aurait décalé l'horaire d'un quart d'heure
pour rien.

---

## 22/08/2026 — conclure sur le travail de la session d'à côté sans lire ce qu'elle en a écrit (deux fois, même fichier)

Deux sessions ouvertes le même matin sur le même dépôt (S0.4 : la
collecte ; S0.5 : AROME/R2). La S0.5 a déployé par `rsync -a` de **tout**
`model-verif/`, ce qui a emporté le `collect.py` que la S0.4 venait de
modifier. Jusque-là, une maladresse. **Ce qui a coûté, c'est ce qui a
été AFFIRMÉ ensuite, deux fois, sans vérifier :**

| affirmation | ce que la session voisine avait écrit |
|---|---|
| « retour en arrière **impossible** » | son **§11** décrivait la sauvegarde qu'elle avait posée : `/tmp/collect.avant-s04.py` |
| « déployé **sans validation** » | sa ligne de roadmap disait « ✅ DÉPLOYÉ, **sur l'accord explicite de Yann** » |

⇒ Sur la seconde, Yann a joué un retour arrière qui **a défait un
déploiement qu'il avait lui-même approuvé** — et le VPS s'est retrouvé
en retard de deux crans, avec une échéance de quota ressuscitée.

⚠️ **Piège réutilisable** : **la note et la roadmap de l'autre session
sont des SOURCES, pas du contexte.** Elles sont réécrites *pendant* la
séance — celle du S0.4 est passée de « ⬜ RIEN DÉPLOYÉ » à « ✅ DÉPLOYÉ,
accord explicite » en une heure. **Les relire juste avant toute
affirmation sur son travail**, jamais une seule fois au début. Et le
signal qui aurait suffi : `ls -laT` sur les fichiers voisins — une
mtime plus récente que la sienne veut dire *quelqu'un travaille ici en
ce moment*, donc *va lire ce qu'il en dit* avant de conclure.

ⓘ Corollaire côté commande : déployer **la liste de fichiers qu'on
possède**, jamais le dossier. `rsync -a model-verif/` est un
déploiement de tout ce que le dossier contient, y compris ce qu'on n'a
pas écrit.

---

## 22/08/2026 — un point de retour à DEUX fichiers restauré à moitié, et seul le banc le dit

Le lot S0.4 avait posé sa sauvegarde avant de modifier la collecte :
**`/tmp/collect.avant-s04.py` ET `/tmp/test_collect.avant-s04.py`**,
horodatés à la même seconde. Le retour arrière, joué quelques heures plus
tard, n'a copié que **le premier**.

Résultat, mesuré aussitôt sur le VPS :

| | `groupes_requete` | version |
|---|---:|---|
| `collect.py` | **0** | celle d'avant ✅ |
| `test_collect.py` | **4** | celle d'après ⛔ |

```
AttributeError: module 'collect' has no attribute 'poids_par_point'
```

⚠️ **La production n'était pas touchée** — `run.sh` n'exécute jamais un
banc, et la collecte de la nuit aurait tourné normalement. Le dégât est
ailleurs : **un banc rouge abandonné sur le VPS se lit comme une panne du
code**, alors que c'est un décalage de version. La prochaine session
aurait cherché un bug qui n'existe pas — ou, pire, aurait cessé de faire
confiance au banc.

⚠️ **Piège réutilisable** : *un point de retour composé de plusieurs
fichiers doit être restauré EN ENTIER, et le seul contrôle qui le dise
est le banc.* Le code seul « marche » — il est cohérent avec lui-même.
**Après tout retour arrière : rejouer le banc du module restauré, sur la
machine où on vient de le poser.** Deux lignes, et elles distinguent
« restauré » de « à moitié restauré ».

ⓘ Et le corollaire de l'aller : `rsync -a` d'un RÉPERTOIRE déploie tout
ce qu'il contient, y compris le travail d'une autre session ouverte le
même matin. Déployer la **liste de fichiers qu'on possède**, pas le
dossier.

---

## 22/08/2026 — le DERNIER flux qui porte `aloft_speed` vole le régime de tout le monde

**Contexte** : lot S0.5, un second collecteur R2 (`arome_fcst.py`) qui
écrit un flux de prévision à côté de `fcst` et de `fcstagrume`.

`score.daily_rows` choisit le vent d'altitude de référence ainsi :

```python
for row in snapshots.get(0, []):
    if "aloft_speed" in row:
        ref_by_st[f"{source}:{station_id}"] = row
```

**Le dernier gagne**, et `snapshot_rows` lit `fcst` en PREMIER. Or
`collect.py` ne pose `aloft_*` que sur `REGIME_REF_MODEL`
(`ecmwf_ifs025`), précisément parce que `day_regime` dit en toutes
lettres « un seul modèle de référence, le même pour tout le monde » —
sans quoi un modèle qui voit du flux là où les autres voient du
thermique se ferait juger sur une autre population de journées.

⇒ Un flux ajouté APRÈS, qui écrirait `aloft_speed` sous ce nom-là,
**changerait le régime des 570 balises déjà notées** — 13 795 lignes par
nuit — sans un message, sans un banc rouge, et sans que rien dans le
diff ne le laisse voir. Mesuré : sur une balise à 45 km/h de vent à
850 hPa, la journée passe de `fluxW` à `thermal`.

⚠️ **Piège réutilisable** : quand un dictionnaire est rempli par une
boucle « le dernier gagne » sur une liste CONCATÉNÉE, l'ordre de
concaténation est un contrat, et personne ne l'a écrit. **Chercher, à
chaque nouveau flux : quel champ, en existant simplement, change le sens
d'une colonne pour des lignes qui ne sont pas les siennes ?**

La sortie retenue : `arome_fcst.py` écrit `arome_aloft_speed` /
`arome_aloft_dir` / `arome_aloft_level`. La donnée est là dès la
première nuit — les tuiles `arome/sol` sont réécrites toutes les 3 h,
ne pas l'écrire serait irrattrapable — et la décision « d'où vient le
régime de ces balises » se prend plus tard, par un renommage, sans rien
rejouer. Tenu par `test_arome_fcst.py::test_aloft_ne_vole_pas_le_regime`,
qui ne teste pas le NOM du champ mais la propriété : *ajouter le flux ne
change pas le régime des balises déjà notées*.

---

## 22/08/2026 — « 1ᵉʳ sur 1 » publié comme un vainqueur prouvé

`inference.rank_models` rendait, quand un seul modèle d'une case
atteignait le quorum d'occurrences :

```python
if len(usable) == 1:
    return {usable[0]["model"]: 1}, "ok", None
```

Et `rankReasonFr("ok")` s'affiche **« un modèle se détache »**. Un rang 1
sous cette phrase se lit « ce modèle est le meilleur ici » — alors qu'il
n'a battu personne. C'est exactement le reproche que le lot G2 faisait au
🏆 de l'ancien score, et le fichier le dit lui-même : « on ne publie un
ordre que quand la MARCHE DU HAUT est prouvée ».

**Ce n'était pas grave, et ça le devenait.** Compté le 22/08 sur
`model_score_zone` : **2 lignes sur 276 035** passaient par là — les
cases portent neuf à dix modèles, il fallait que huit tombent sous le
quorum. Répétition à blanc du flux AROME/R2 : **363 cases fines** sur
408, parce que 2 938 balises n'ont qu'un seul modèle par construction.

⚠️ **Piège réutilisable** : une branche « cas dégénéré » écrite quand la
population rendait le cas rare devient la branche PRINCIPALE le jour où
la population change. **Chercher, avant d'élargir une population : quels
`if len(...) == 1` deviennent le cas courant ?** Un compte en base
(deux lignes) suffit à distinguer « c'est déjà faux mais invisible » de
« c'est sur le point d'être partout ».

Corrigé en `return {}, "single_model", None` ; `rank` nul est un
résultat de première classe. La contrainte en base demande
`supabase_step42_lot_s05.sql` — et `score._upsert_scores` renvoie une
fois avec `rank_reason = null` si la base refuse en nommant sa
contrainte, pour que la nuit passe quand même (le lot G avait perdu
cette nuit-là).

---

## 22/08/2026 — le manifeste d'une chaîne d'ingestion est écrit APRÈS ce qu'il décrit

`arome-wind/ingest.py` téléverse, dans cet ordre : les **63** tuiles
`arome/sol`, puis les **441** tuiles `arome/alt`, puis
`arome/manifest.json`. Mesuré sur le run 00 Z du 22/08 : `sol` entre
**05:34:25 et 05:34:44 Z**, `alt` jusqu'à **05:42:07 Z**, manifeste
juste après. **Huit minutes** pendant lesquelles le manifeste annonce
encore le run PRÉCÉDENT alors que les tuiles `sol` portent déjà le
nouveau.

Un consommateur qui daterait ses lignes d'après `manifest["run"]` les
daterait donc de **trois heures trop tôt**, sans une erreur, une nuit sur
huit environ. Et `generatedAt` n'aide pas : il porte l'heure de DÉBUT du
run (05:30:05 Z), pas celle de la publication.

⚠️ **Piège réutilisable** : dans un bucket entièrement mutable, l'index
et les objets ne sont jamais cohérents pendant la durée du
téléversement. **Préférer un objet qui se DÉCRIT LUI-MÊME** : chaque
tuile porte `times`, dont `times[0]` EST l'heure du run
(`keep_step(0)` rend toujours `True`). `arome_fcst.py` en tire son `t0`
et refuse de mélanger deux runs dans la même archive
(`test_tuiles_de_deux_runs`).

ⓘ Et le corollaire, mesuré aussi : les échéances de ces tuiles **ne
sont pas contiguës**. `keep_step()` garde l'heure pleine le jour et une
sur trois la nuit (fenêtre 22-04 UTC) — **42 échéances pour 52 heures**
d'horizon sur un run 00 Z, les heures 1, 2, 22, 23, 25, 26, 46, 47, 49
et 50 manquent. Ranger ces valeurs dans l'ordre du tableau décale tout
ce qui suit le premier trou : même défaut que la dé-accumulation
positionnelle du 13/08, sous un autre déguisement.

---

## 22/08/2026 — le commentaire qui JUSTIFIE un partage de budget se trompait de 14×, et l'app « qui n'y touche pas » y touche

**Contexte** : lot S0.4, audit des autres consommateurs Open-Meteo après
que le découpage de `collect.py` ait rendu 1 051 pondérés par nuit. La
question posée était « le même gaspillage dort-il ailleurs ? ». Réponse :
**non** — `collect.py` est le seul script du dépôt qui demande
**plusieurs modèles dans une requête**, donc le multiplicateur qui coûtait
vaut 1 partout ailleurs, et aucun des quatre scripts ne demande une
variable qu'il ne relit pas (vérifié ligne à ligne).

**Mais l'audit a rapporté deux faits écrits faux, tous deux dans des
commentaires qui servent d'ARGUMENT.**

**(a)** `traces/entretien/balise-entretien.service` justifiait
`ReadWritePaths=/var/lib/bw-quota` en écrivant que « `backfill_packs.py`
ne pèse que **18 pondérés par jour** ». Mesuré sur le fichier de budget,
**deux jours de suite : 252,0** (210 requêtes × 1,2), le 21/08 de
04:39:09 à 04:42:49 UTC et le 22/08 de 04:30:30 à 04:33:31. **Quatorze
fois l'affirmation** — 2,7 % du plafond journalier et non 0,2 %.

**(b)** `collect.py::quota_projete` affirmait que l'app « interroge
Open-Meteo depuis le navigateur des pilotes, **jamais depuis ce
serveur** ». Mesuré : `index.js` appelle Open-Meteo **côté serveur** aux
lignes 1426, 4302 et 6007 — et celui de la l. 4302 est **multi-points**
(`latitude=a,b&longitude=c,d`), donc pondéré aussi par le nombre de
lieux. Ce qui protège la collecte n'est pas la vertu de l'app : c'est
qu'`index.js` tourne sur **Render**, donc sur une **autre IP** (vérifié :
`pgrep -af "node.*index.js"` ne rend rien sur le VPS).

⚠️ **Piège réutilisable** : un commentaire qui porte un CHIFFRE et qui
sert à justifier une décision d'architecture doit être remesuré quand on
passe à côté — c'est le troisième de ce genre en deux jours sur ce
chantier (après « aucun timer n'appelle `backfill_packs` », démenti le
22/08 au matin). Et une phrase qui dit « X ne fait jamais Y » mérite
qu'on cherche **pourquoi** : ici la vraie raison n'était pas celle
écrite, et elle **cesserait d'être vraie** si l'app était un jour
rapatriée sur le VPS — elle partagerait alors le plafond sans écrire
dans `/var/lib/bw-quota`, et le compteur serait faux du côté qui ne
protège pas, en silence.

✅ Les deux commentaires sont corrigés, datés et déployés.
`claude/lot-s04-seconde-passe-22-08.md` §14. ⚠️ La copie **installée**
de `balise-entretien.service` dans `/etc/systemd/system/` n'a pas été
touchée (root) — la différence est **uniquement en commentaire**, donc
sans effet sur le service.

---

## 22/08/2026 — on payait 22 % du run pour deux variables qu'un seul modèle sur neuf archive

**Contexte** : lot S0.4, ouvert pour partitionner la collecte avant que
le garde-fou horaire ne refuse de démarrer (657 points sur 659).

`_hourly_vars()` demandait **huit** variables, dont
`wind_speed_850hPa` et `wind_direction_850hPa`. Or `forecast_rows` ne les
archive que sous `if model == REGIME_REF_MODEL`. Compté sur l'archive du
22/08 (`fcst_2026-08-22.ndjson.gz`, 5 595 lignes, 657 points) :
**657 lignes portent `aloft_speed`, toutes en `ecmwf_ifs025`.** Les huit
autres modèles recevaient ces deux variables et on jetait la réponse.

Et Open-Meteo facture **variables × modèles**, pas requêtes :

```
2 variables × 8 modèles inutiles / 10 = 1,6 pondéré par point
1,6 × 657 points = 1 051,2 pondérés par nuit = 146 points de budget = 22 % du run
```

Le poids d'un point tombe de **7,2 à 5,8** en mettant les deux variables
d'altitude dans **leur propre requête** — il en faut une seconde, parce
qu'Open-Meteo prend **UNE** liste `hourly` pour tous les modèles d'une
requête. Le garde-fou horaire passe de 659 à **818 points**, et la marge
de **2 à 161**.

⚠️ **Piège réutilisable, et il vaut au-delà d'Open-Meteo** : sur une API
qui facture **le produit** de deux listes, toute variable qu'un seul
élément de l'autre liste exploite doit être dans sa propre requête. Le
coût d'une variable inutile n'est pas « une variable », c'est « une
variable × tous les modèles ». **Chercher, sur toute requête groupée :
qu'est-ce qu'on demande à tout le monde et qu'on ne relit que d'un
seul ?** ⓘ Non vérifié ailleurs : `backfill_packs` (252 pondérés/jour),
`day_features`, `match_analogs`, `sonde_openmeteo`.

⚠️ **Deuxième piège, dans la correction** : un groupe de requête ne doit
JAMAIS contenir un seul modèle. Open-Meteo ne suffixe les clés par
`_<model>` que si **plusieurs modèles SERVENT** le point ; à un seul
modèle demandé, la réponse est nue, `forecast_rows` cherche
`wind_speed_10m_<model>` et n'écrit **rien**, en silence, avec un
HTTP 200 parfaitement formé. D'où `COMPAGNON_ALTITUDE` — et le compagnon
doit être **mondial**, vérifié sur l'archive (657/657) et non supposé.

✅ Corrigé et bancé : `groupes_requete()`, `poids_par_point()`, et
`test_collect.py` section S0.4 (170 assertions, six mutations rouges,
dont une qui compare l'archive **ligne pour ligne** entre la forme à une
requête et la forme à deux). `claude/lot-s04-seconde-passe-22-08.md` §2.

---

## 22/08/2026 — deux garde-fous qui se recouvrent, et c'était le moins utile qui parlait

**Contexte** : lot S0.4, en mutant `test_collect.py` pour vérifier qu'il
sait échouer. On a remplacé le `raise` du seuil journalier par un
`if False` — et **aucune assertion n'est devenue rouge.**

La raison est arithmétique, et elle ne dépend d'aucune mesure :

```
QUOTA_HEURE × 0,95 = 4 750    <    QUOTA_JOUR × 0,60 = 6 000
```

Tout run d'**une** passe qui franchit 6 000 franchit forcément 4 750. Le
seuil journalier, testé **en premier** dans `quota_projete`, ne décidait
donc jamais **si** le run est refusé — seulement **quel message sort**.
Et il sortait le moins utile des deux : « > 60 % du plafond JOURNALIER »,
alors que la fenêtre qui ferme réellement la porte, et pour une heure
entière, est l'**HORAIRE**. À 6 h du matin, ce message envoie chercher au
mauvais endroit.

✅ **Corrigé** : les deux gardes sont inversées, l'heure parle d'abord.
Le seuil journalier reste écrit — il redevient le **seul** garde-fou
utile le jour où la collecte sera partitionnée en plusieurs passes
horaires (chaque passe sous 4 750, c'est leur **somme** qui devra tenir
sous le plafond du jour), et il devra alors comparer au budget **mesuré**
(`Budget.etat()`) et non à 60 % d'un plafond brut, sinon il refuserait
deux passes qui passent séparément.

⚠️ **Piège réutilisable, et c'est le vrai** : deux garde-fous qui
protègent la même chose à deux seuils différents ne font pas deux
protections. Le plus strict fait tout le travail, l'autre ne change que
le libellé de l'erreur — et **il peut le changer pour le pire**. Quand on
en empile deux, ordonner du plus strict au plus large, et **vérifier par
mutation** que chacun sait encore refuser quelque chose que l'autre
laisse passer. Un mutant équivalent n'est pas un banc qui va bien : c'est
un garde-fou qui ne garde plus.

ⓘ Ce piège n'a pas été trouvé en lisant le code — il a été trouvé en
**demandant au banc de savoir échouer**. C'est l'argument pour le faire
à chaque lot, pas seulement quand le code est neuf.

---

## 22/08/2026 — un garde-fou de QUOTA qui détruit une archive que le quota ne concerne pas

**Contexte** : lot S0.3. `collect.py::quota_projete()` refuse de démarrer
si le run dépasse 95 % du plafond HORAIRE d'Open-Meteo — le garde-fou
écrit le 09/08, et il a la bonne raison (aucune cadence ne fait tenir un
volume dans une fenêtre). Mais `main()` en fait ceci :

```python
try:
    quota_projete(len(stations), args.forecast_days)
except Abort as exc:
    print(f"❌ {exc}", file=sys.stderr)
    return 1
```

Ce `return 1` est **avant `rattraper()`, avant la passe prévisions, et
avant la passe OBSERVATIONS**. Or les observations ne consomment aucun
quota Open-Meteo : elles lisent Pioupiou, winds.mobi, nos tables MF/AEMET
et notre objet R2 Infoclimat. Une nuit refusée pour dépassement de quota
perd donc **aussi** l'archive d'observation des cinq réseaux — dont trois
ont **30 à 48 h de rétention amont**, c'est-à-dire aucune reprise
possible.

Et ce n'est pas théorique : mesuré le 22/08, le référentiel Pioupiou
compte **657 points** pour un plafond d'`Abort` à **659**
(`4 750 / 7,2`). `load_stations()` le rafraîchit **tous les 7 jours** en
**ajout seul** (« on ajoute, on marque `seen_at`, on ne retire jamais ») :
648 le 07/08, 651 le 15/08, 657 le 22/08. Il ne peut que monter.

⚠️ **Piège réutilisable** : un garde-fou placé en tête de `main()` coupe
tout ce qui suit, y compris ce qu'il n'a aucune raison de protéger. La
règle « un trou nommé vaut mieux qu'un run tué » du budget partagé
s'arrête à la porte du run — alors qu'elle devrait s'appliquer **par
passe**. Chercher, dans tout garde-fou : *qu'est-ce que ce refus emporte
avec lui qui ne le concerne pas ?*

✅ **CORRIGÉ le 22/08 (lot S0.4)**, et la correction n'a pas demandé
l'arbitrage qu'on croyait. Mesuré d'abord : **aucune** des six passes
d'observation ne consomme de quota Open-Meteo — `fetch_archive` interroge
Pioupiou, les autres Iowa State / winds.mobi / Infoclimat / MF / AEMET,
et sur 24 h glissantes le fichier de budget ne connaît que **deux**
consommateurs (`collect`, `backfill_packs`). Le refus saute donc
désormais la **seule** passe qui déborde (`args.skip_forecast = True`),
laisse tourner les six autres, et **sort quand même en 1** pour que
`run.sh` alerte (`SEUIL_ALERTE=1`). **Alerter ET collecter.**

⚠️ **Et le rappel s'écrit en DERNIER dans le journal.** Le corps du mail
d'alerte de `run.sh` est un `tail -n 25` : un refus annoncé à la première
seconde du run serait noyé sous six passes d'observation et
**n'arriverait jamais dans le mail**. La dernière chose écrite est la
première chose lue. Banc : `test_collect.py`, section S0.4 — rejoué
contre le `return 1`, il devient rouge sur « le fichier d'observations
existe ».

ⓘ L'échéance elle-même (657/659) a été levée autrement — voir l'entrée
« on payait 22 % du run » ci-dessous. `claude/lot-s04-seconde-passe-22-08.md`.

---

## 22/08/2026 — `arome/sol` annonce un modèle qu'il ne contient pas, et ce nom est INTERDIT en base

**Contexte** : lot S0.3, instruction de la piste « lire AROME sur R2
plutôt que de payer du quota Open-Meteo ». Les tuiles de vent au sol
portent :

```json
{"model": "meteofrance_seamless", "kind": "sol", "level": null, ...}
```

C'est `MODEL_KEY` dans `arome-wind/ingest.py` (l. 123), commenté
`# clé "model" écrite dans le JSON (AROME)`. **Le contenu n'est pas du
seamless** : il vient de `pnt/{ref}/arome/001/SP1/`, soit de l'AROME-HD
0,01° pur, comme le dit le reste du fichier. Le libellé est un vestige de
l'époque où la tuile servait un calque de carte, où le nom du modèle
n'était qu'une étiquette d'affichage.

Trois raisons pour lesquelles ça ne peut pas rester si ce flux entre au
scoring :

* `collect.py` interdit explicitement les modèles `*_seamless`, avec la
  raison écrite : « archiver du seamless produirait un fichier où la
  colonne AROME contient de l'ARPEGE une partie du temps, sans qu'aucune
  trace ne permette de le savoir après coup » ;
* `model_verif_daily.model` porte un **CHECK `not like '%\_seamless'`** ⇒
  une insertion sous ce nom **échoue en base**, et l'upsert entier avec
  elle ;
* et un lecteur du JSON croit lire du seamless. C'est un mensonge dans un
  champ.

⚠️ **Piège réutilisable** : un champ d'identité écrit à une époque où il
n'était qu'une étiquette d'affichage devient faux le jour où quelqu'un
s'en sert pour décider. Avant de brancher un produit existant sur une
chaîne neuve, **vérifier ce que ses champs d'identité prétendent**, pas
seulement ce que ses valeurs valent.

ⓘ Trouvé au passage, même famille : `quota_projete()` affirme dans son
pavé qu'« aucun timer ni cron n'appelle `traces/backfill_packs.py` ».
Mesuré le 22/08 : `balise-entretien.timer` l'appelle **tous les jours vers
04:30 UTC, pour 252 appels pondérés**. Le commentaire servait d'argument
pour dimensionner une marge — il la sous-estime maintenant d'un
consommateur entier.

---

## 22/08/2026 — Open-Meteo a QUATRE plafonds, `FENETRES` n'en connaît que trois

**Contexte** : lot S0.3. `tools/quota_openmeteo.py` modélise 600/min,
5 000/h et 10 000/j — les trois plafonds que la panne du 09/08 avait fait
découvrir un par un. La page de tarification d'Open-Meteo en annonce
**quatre** pour le palier gratuit : « 600 calls / min, 5.000 calls /
hour, 10.000 calls / day, **300.000 calls / month** ».

On en consomme **~149 500 par mois**, soit **50 %** : il ne mord pas
aujourd'hui. Mais c'est très exactement la forme du défaut du 09/08 —
« le palier gratuit compte AUSSI 5 000 appels pondérés par HEURE, et
l'heure n'existait nulle part dans le code » — rejoué un cran plus haut.
Toute extension du référentiel (P1 = +72 %, les 2 938 candidates = 261 %)
le franchit avant que quoi que ce soit ne le signale.

⚠️ **Piège réutilisable** : quand une panne révèle un plafond manquant,
aller relire **la liste complète des plafonds annoncés**, pas seulement
ajouter celui qui vient de mordre. Un seau à trois fenêtres sur un
service qui en compte quatre donne la même illusion de surveillance
qu'un seau à deux.

⬜ **Non corrigé** : une ligne dans `FENETRES` + une constante, mais c'est
un changement du garde-fou de production — arbitrage n°5 de
`claude/lot-s03-balises-non-notees-22-08.md`.

---

## 20/08/2026 — `zip()` tronque en silence, et écrivait un domaine sous le nom d'un autre

**Contexte** : Lot Q2, écriture de la pluie à venir. `piaf.ecrire()`
construisait sa liste de clés avec `cles_de_la_passe(p.passe)`, qui
lisait la constante de module `DOMAINES_COUPE` **en dur**, puis appariait
clés et corps par `zip(p.domaines, cles[1:-1])`.

Tant que la passe portait les trois domaines de production, les deux
listes avaient la même longueur et tout allait bien. Appelée avec un
autre jeu de domaines — le banc, ou un futur `--domaines` — `zip`
s'arrêtait **à la plus courte, sans un mot** : les octets du premier
domaine partaient sous le nom `colonnes-nord-alpes.bin`, et la coupe
alpine aurait affiché la pluie d'ailleurs. Aucune exception, aucune
trace, une carte parfaitement crédible.

⚠️ **Piège réutilisable** : `zip` est un troncateur silencieux, et il
est l'outil qu'on prend d'instinct pour apparier deux listes qu'on
« sait » de même longueur. `strict=True` existe **depuis Python 3.10
seulement** — le Mac de ce projet tourne en 3.9, donc il ne protège pas
là où les bancs tournent aussi. **Quand deux listes doivent avoir la même
longueur, l'écrire en toutes lettres avant de les apparier.**

**Trouvé par le banc**, pas par relecture : `test_piaf.py` construit
volontairement une passe sur un domaine factice, et c'est le contrôle
« les clés de la passe la plus ancienne ont été supprimées » qui a rougi.

**Fix** : `cles_de_la_passe(passe, domaines)` prend les domaines en
paramètre, et `ecrire()` compare les longueurs avant d'apparier.

### Et, dans la foulée : un contrôle VERT qui ne prouvait rien

`ingest_piaf.py --verifier` confronte le calque et la coupe sur les
octets servis. Premier jet : trois points par domaine, tirés aux coins et
au centre. Première exécution réelle → « 27 mailles confrontées, écart
maximal 0,000e+00 » ✅ — **et pas une goutte de pluie dedans**. Zéro
égale zéro quel que soit l'offset : le contrôle aurait été aussi vert
avec deux jeux d'octets totalement décalés.

⚠️ **Piège réutilisable** : un contrôle d'égalité sur une grandeur
majoritairement nulle est vide tant qu'on n'a pas compté les valeurs NON
NULLES qu'il a réellement mordues. **Publier ce compte, et dire
« contrôle vide » plutôt qu'afficher un ✅ quand il vaut zéro.**

---

## 17/08/2026 — jauge R2 : deux faux motifs dans le même mail, et le second n'était pas une pente

**Contexte** : mail de 04:32 UTC, `garde-fou-r2` en ÉCHEC (code 1), deux
motifs — « +12,22 Go/mois, palier atteint dans 12 jours » et « 82 objets
ORPHELINS sous `agrume/grille/` ». Contrôlé à la main le même matin :
**496 présentes / 496 réclamées, 0 orphelin, plateau à 3,375 Go, compte
à 4,39 Go sur 10.** Les deux motifs étaient faux.

### 1. La médiane de différences ne survit pas à DEUX marches

Série réelle de `agrume/grille` : 2,002 · 2,002 · 2,422 · 4,054 Go →
différences 0 · +0,420 · +1,632. Deux marches (tarn-aveyron-hérault le
15/08, boîte élargie des Alpes le 16/08) pour trois différences : la
médiane tombe **sur** une marche.

⚠️ **Piège réutilisable, et c'est le troisième mail de suite qu'il
produit** : la correction du 16/08 tenait à un mot non écrit — « une
marche ISOLÉE ne peut pas être la médiane ». Rien n'avait jamais promis
qu'il n'y en aurait qu'une par fenêtre. **Quand une correction repose sur
une hypothèse de cardinalité (une seule, au plus deux…), l'écrire dans le
banc, sinon c'est le prochain incident qui l'écrira.**

**Fix** : 25e centile des différences au lieu de la médiane, et 5 relevés
minimum au lieu de 4. Un quantile bas ignore les grandes différences *en
nombre* : quatre différences en absorbent deux, cinq en absorbent trois.
Une fuite reste vue parce que **toutes** ses différences sont positives.
Prix payé et dit : une nuit de plus sans pente après un changement de
méthode, et la croissance en escalier encore plus sous-estimée.

### 2. Un objet non réclamé n'est pas forcément un orphelin

La publication d'un run écrit les **objets** puis l'**index** (l'ordre
inverse ferait des orphelins invisibles — décision de l'étape 6). Entre
les deux, ces objets ressemblent trait pour trait à des orphelins.
L'audit de 04:32 est tombé dedans : 55 clés de `nord-alpes/00Z` + 27 de
`pyrenees/00Z` = **82 objets, 0,679 Go**, réclamés à 05:29.

⛔ **Ce que l'ordre de lecture ne peut pas sauver** : `main()` lit déjà
l'index APRÈS le listing, ce qui protège une fenêtre de 3 secondes. La
fenêtre à couvrir était d'**une heure** — celle de la publication.

**Fix** : le `LastModified` du listing (gratuit, déjà dans la réponse).
Un objet non réclamé de moins de 3 h (le pas entre deux réseaux AROME)
est « en vol » : dit dans le rapport, jamais fatal. **La frontière est
l'ÂGE, pas un nombre toléré** — un seul objet non réclamé de 4 h crie
encore, et un run en vol qui ne se déclare jamais devient orphelin tout
seul en vieillissant. ⚠️ Un objet **sans** date est jugé ANCIEN : même
principe que `lu=False`, une vérification qui n'a pas pu avoir lieu ne
doit pas se lire comme une vérification réussie.

**Vérifié** : 89 bancs verts (80 avant), dont les deux moitiés de chaque
contrat — le run en vol est muet / les mêmes clés le lendemain crient, la
marche double ne fait pas de pente / la fuite continue crie toujours.
Essai à blanc du code corrigé sur le compte réel : **code 0**.

---

## 16/08/2026 — AGRUME : le `except Abort` du 15/08 n'avait été corrigé qu'à moitié

**Contexte** : élargissement de `DOMAINE` aux Alpes entières
(44,8-46,3 N × 5,5-7,6 E → 43,70-46,45 × 5,00-7,60), après qu'un pilote
de Bernex (74) a signalé qu'AGRUME ne marchait pas chez lui.

**Le bug, trouvé AVANT de le déclencher** : l'entrée du 15/08 ci-dessous
raconte comment `geler()` a perdu 3 balises en lisant « artefact
incohérent » comme « artefact inexistant ». Le fix du 15/08 a corrigé
*la cause de cet Abort-là* (contrôle de cohérence trop strict) — mais a
laissé en place **le `except Abort` générique qui transformait l'erreur
en perte de données**. Le piège était donc intact : il suffisait d'une
AUTRE cause d'Abort pour rejouer exactement la même perte. Changer les
bornes d'un domaine déjà figé en est une, et c'était précisément
l'opération du jour.

**Piège réutilisable, et c'est le même que celui de la jauge R2 juste
en dessous** : corriger *une cause* d'un symptôme laisse le mécanisme
qui transforme cette cause en dégât. ⚠️ **Le dégât est le bug ; la cause
n'en est qu'un déclencheur.** Ici le dégât était « un `except` large
avale une erreur de validation et vide l'axe » — deux corrections de
cause de suite ne l'auraient jamais touché.

**Fix** : `ArtefactAbsent(Abort)`, levée uniquement quand le fichier
n'existe pas, et c'est la SEULE que `geler()` rattrape. Toute autre
incohérence remonte à l'utilisateur. Le rebornage assumé passe par un
drapeau explicite, `--rebornage <domaine>`, qui conserve l'axe.

**Vérifié** : 222 → 303 balises, **0 identifiant perdu** (diff des
ensembles d'IDs avant/après, comme le 15/08 — ce contrôle-là n'est
toujours pas automatique).

### Effet de bord : cinq bancs recopiaient le domaine au lieu de le lire

`agrume/test_grille.py` portait `J0, I0, NJ, NI = 364, 700, 61, 85`, les
quatre bornes `46.3 / 44.8 / 5.5 / 7.6` et la forme `(5, 25, 3, 61, 85)`
en dur ; `agrume/test_orographie.py` attendait `(61, 85)` et
`(151, 211)` ; `agrume/test_transect.py` mesurait l'orthodromie contre
une diagonale de « 233 km » ; **`verif/test_colonnes.py` plaçait une
balise-témoin à `lat=44.79`, commentée « juste sous latmin »** — elle
s'est retrouvée DEDANS, et le conteneur est passé de 3 à 4 balises
(`could not broadcast input array from shape (3,) into shape (4,)`).
⚠️ Celui-là n'est **pas tombé sur le Mac au premier passage** : la
tournée de bancs n'avait couvert que `agrume/`. C'est
`deploy-agrume-vps.sh` qui l'a arrêté, sur le VPS, avant tout
redémarrage — le script a fait exactement son travail.

Tous sont tombés à l'élargissement — **pas sur une régression, sur leur
propre copie périmée**.

⚠️ **C'est exactement ce que `domaine.py` existe pour empêcher** (« les
indices se DÉDUISENT des métadonnées, jamais codés en dur »), et ça
s'était glissé dans les BANCS, où personne ne le cherchait. Un banc qui
recopie une constante ne vérifie plus le code : il vérifie que personne
n'a touché à la constante, et il devient un frein le jour où on y touche
pour de bonnes raisons.

**Fix** : les bancs dérivent de `fenetre(META)` et de `DOMAINE`. Pour
`test_transect`, la section a été réécrite pour vérifier **la loi** (l'écart
croît comme le carré de la longueur) plutôt que deux nombres — élargir
les bornes pour les faire repasser aurait effacé ce qu'elle mesure.

### Ce qui remplace le sha256 comme preuve de continuité

L'interdit d'élargir `DOMAINE` reposait sur le sha256 de l'orographie de
production. Il est levé, et remplacé par plus fort :
`freeze_orographie.py --comparer-orographie <ancien.npz>` compare, balise
par balise et grille par grille, le sol rendu avant et après.
**Mesuré au regel : 0,000 m d'écart sur 252 couples.** ⛔ La règle qui
reste : on n'élargit pas un domaine sans rejouer ce banc et publier son
écart max.

---

## 16/08/2026 — Jauge R2 : une MARCHE lue comme une PENTE, la troisième fois

**Symptôme** : mail « au rythme mesuré (+7.26 Go/mois), palier atteint
dans 27 jours » à 04:31 UTC, sur un compte à **3,40 Go sur 10**.

**Cause** : le domaine `tarn-aveyron-herault` est entré en production
le 15/08. `agrume/grille` est passé de 2,0016 à 2,4223 Go en une nuit —
+0,4207 Go, exactement le poids du domaine neuf, **déjà à son plateau**
(165 objets, comme ses deux voisins ; contrôle croisé 1,238/0,764 =
1,62, le rapport des tailles de maille Pyrénées/Alpes). Sur les trois
seuls relevés disponibles, les moindres carrés ne peuvent pas
distinguer cette marche d'une croissance : ils en tirent +6,31 Go/mois,
soit 87 % de l'alerte.

**Piège réutilisable — et c'est le vrai sujet** : c'est la **troisième**
fois, et à chaque fois un cran plus bas. 10/08 : un BUCKET apparaît →
correctif `meme_perimetre` (filtre par bucket). 13/08 : un PRODUIT
apparaît dans un bucket connu → correctif « pente par préfixe ». 16/08 :
un DOMAINE apparaît dans un préfixe connu. **Deux correctifs de suite
ont déplacé la GRANULARITÉ ; le problème était le CALCUL.** Un correctif
qui ne fait que descendre d'un cran ne corrige pas une classe de bug, il
déplace l'endroit où elle ressortira. Mesuré : descendre encore
(profondeur 3) mettrait 3,39 Go sur 3,41 « hors échéance ».

**Fix** : la pente d'un préfixe est désormais la **médiane des
différences entre relevés consécutifs**, sur **4 relevés minimum**.
Quatre relevés font trois différences, et la médiane de trois valeurs
ignore toujours l'extrême : une marche isolée ne peut plus être la
médiane, **quelle que soit la granularité où elle tombe**.

⚠️ **Le piège que ce fix INTRODUIT** : une différence divisée par un
petit Δt explose. L'historique réel en contient — le 10/08, la jauge a
tourné six fois en une heure, dont deux relevés à 24 s d'écart (0,784 Go
÷ 24 s ≈ 2,8 millions de Go/mois). Les moindres carrés noyaient ça ; une
médiane pourrait le prendre pour la valeur centrale. D'où `_degrouper` :
les relevés plus rapprochés que 0,25 j ne comptent que pour un point, et
c'est le plus récent du groupe qui gagne.

⚠️ **Le prix, assumé** : une croissance réellement EN ESCALIER est
sous-estimée, et un produit neuf est hors échéance pendant 4 relevés au
lieu de 3. Une fuite, elle, est continue — `test_une_vraie_fuite_reste_vue`
et `NuitDu30Juillet` la clouent contre le calcul de production.

Bancs : 51 → **64 verts**. Les trois marches sont rejouées avec leurs
vrais chiffres, et les moindres carrés sont **gardés en contre-exemple**
— sans eux, le banc passerait sur les deux implémentations, donc ne
vérifierait rien.

### Suite du même jour : ⛔ une pente ne répondra JAMAIS à « est-ce légitime ? »

**Le vrai trou, découvert en répondant à « et si j'agrandis la boîte des
Alpes ? »** : une fois les marches correctement ignorées, une croissance
faite **uniquement** de marches n'a plus aucune tendance. Un domaine de
plus, une boîte élargie, et la règle d'horizon ne dit plus rien du
tout — il ne resterait que la règle de niveau à 7 Go, c'est-à-dire un
constat.

**Piège réutilisable** : *rendre un détecteur robuste au bruit le rend
aveugle à un signal qui ressemble au bruit.* Le correctif du matin est
juste, et il crée ce trou-là. Il fallait le mesurer, pas le supposer :
simulé sur l'historique réel, deux marches à moins de trois jours
d'écart traversent quand même la médiane (le 17/08 : deux mails ; le
18/08 : un ; à partir du 19/08 : silence).

**Fix** : ajouter une question que la pente ne pose pas.
`agrume/grille` et `agrume/pi/grille` publient un `index.json` qui
déclare **clé par clé** tout ce qui doit exister sous leur préfixe —
c'est ce qui leur permet de purger sans jamais faire de `ListObjects`.
La jauge le confronte au bucket : **tout objet présent doit être RÉCLAMÉ
par quelqu'un.** Agrandir une boîte ne crée aucun orphelin ; une purge
qui cesse de mordre en crée dès la nuit suivante. Coût : 1 GetObject par
produit (classe B), le listing étant déjà fait.

⚠️ **Le contrôle qui donne son sens au banc** : `MarcheEtOrphelin`
vérifie que les deux cas **PÈSENT PAREIL**. Sans lui, les deux tests
auraient pu passer sans rien prouver sur ce que le poids sait ou ne sait
pas distinguer.

⚠️ **Un index illisible ne rend pas « 0 orphelin »** — il rend
`lu=False`. Jumeau exact de `couverture_partielle` : un rapprochement
qui n'a pas eu lieu ne doit jamais se lire comme un rapprochement
réussi. Un index **vide**, en revanche, rend bien tout orphelin : c'est
une information (le produit a perdu son index), pas une panne de
lecture.

**Trouvé dès le premier tir, en production** : 18 orphelins sous
`agrume/pi/grille/` (24 Mo, 9 runs du 13/08) — le résidu du `TypeError`
de `purger()` des 12-13/08, repéré à la main ce jour-là et **toujours
présent trois jours plus tard**, faute d'outil de nettoyage posé. Ce
mécanisme les aurait nommés le 14 au matin. Supprimés le 16/08 après
vérification par `head` (⚠️ `DeleteObject` réussit sur une clé absente —
sans le `head`, « supprimé » et « n'a jamais existé » sont
indistinguables). Compte : 3,407 → 3,383 Go, 0 orphelin des deux côtés.

Bancs : 64 → **80 verts**. Et `tools/test_audit_r2.py` tourne désormais
au déploiement (15 → 16 bancs sur le VPS).

---

## 15/08/2026 — AGRUME : `freeze_balises.py`, deux bugs liés à l'ajout d'un 3e domaine

Contexte : ajout du domaine `tarn-aveyron-herault` à AGRUME (cf. le
projet Claude, `agrume-implementation-tah-15-08.md`). Les deux bugs
ci-dessous existaient déjà dans le code AVANT ce lot, mais ne s'étaient
jamais déclenchés parce que l'axe n'avait jamais eu besoin d'apprendre
un TROISIÈME domaine.

### 1. `charger_artefact()` perdait des balises en silence

**Symptôme** : `freeze_balises.py --catalogue` a fait disparaître 3
balises connues (1333, 1361, 365) dès le premier essai après l'ajout du
3e domaine.

**Cause** : le contrôle de cohérence comparait l'ensemble des domaines
figés dans l'artefact à `DOMAINES` actuel avec une égalité stricte (un
seul cas de transition toléré, codé en dur). Dès qu'un domaine NOUVEAU
apparaissait dans le code, la comparaison échouait et levait `Abort`.
`geler()` attrapait cet `Abort` avec un `except` large et repartait
d'un axe VIDE (`existantes = []`) au lieu de le régénérer proprement —
perte silencieuse, aucune erreur visible en sortie normale.

**Piège réutilisable** : un `except Abort` générique autour d'une
opération de chargement d'axe stable est dangereux — il transforme
n'importe quelle erreur de VALIDATION (même bénigne, comme « domaine
pas encore connu ») en perte de données. Séparer explicitement « je ne
sais pas lire cet artefact » de « cet artefact est incohérent avec le
code actuel, mais partiellement exploitable ».

**Fix** : ne valider que les domaines DÉJÀ présents dans l'artefact figé
(bornes identiques exigées), tolérer les domaines nouveaux pas encore
gelés sans lever.

**Détecté avant tout commit** par diff des IDs de balises (ancien vs
nouveau JSON) — pas par un test automatique. À garder en tête : ce
genre de régression silencieuse ne casse aucun test si le test ne
compare pas explicitement les ENSEMBLES d'IDs avant/après.

### 2. `fusionner()` ne rafraîchissait jamais `hors_domaine` pour les balises déjà connues

**Symptôme** : 10 balises géométriquement couvertes par le nouveau
domaine gardaient `hors_domaine: true` après le regel — elles auraient
continué à être traitées comme hors production alors qu'elles y
entraient désormais.

**Cause** : le flag `hors_domaine` n'était calculé qu'au moment de la
PREMIÈRE entrée d'une balise dans l'axe (branche « balise nouvelle »).
Pour une balise déjà connue, il n'était jamais recalculé, même quand un
nouveau domaine de production apparaît et la couvre.

**Piège réutilisable** : tout champ dérivé d'une géométrie qui peut
CHANGER de sens quand le référentiel géométrique évolue (ici :
l'ensemble des domaines) doit être recalculé pour TOUTES les entrées à
chaque régénération, pas seulement pour les entrées nouvelles.

**Fix** : recalcul autorisé dans un seul sens (`True → False`, jamais
l'inverse) pour les balises déjà connues, sur leur position FIGÉE (pas
leur position live, pour ne pas mélanger deux bugs différents —
correction de coordonnées vs évolution du domaine).

**Vérifié** : `n_hors_domaine` passé de 23 à 13 après le fix, soit un
écart de 10 = exactement les 10 balises listées dans le commit.

---

---

## Un estimateur qui conditionne sur la prévision fabrique le biais qu'il mesure (22/08/2026, lot S2)

**Symptôme** : `bias_ratio` (colonne de `model_verif_daily`, et métrique
`speedRatio` de `model_character`) annonçait depuis le 08/08 que TOUS
les modèles surestiment le vent d'environ 25 % à toutes les balises —
médiane 0,70 sur 195 696 balise-jours. Un défaut aussi uniforme aurait
dû alerter : neuf centres de prévision indépendants ne se trompent pas
tous du même quart dans le même sens.

**Cause** : `scoring.site_bias()` rendait `median(obs/prev)` sur les
seules heures où `fcst_speed >= BIAS_MIN_WIND_KMH` (8 km/h).
Conditionner sur la PRÉVISION sélectionne les heures où le modèle est
haut — donc, comme c'est lui qui se trompe, celles où son erreur est
POSITIVE. Le rapport y est mécaniquement inférieur à 1 même sur un
modèle sans aucun biais. C'est un retour vers la moyenne, pas un biais
de site.

**Ce qui l'a prouvé** : le MIROIR. Le même calcul, conditionné sur
l'OBSERVATION au lieu de la prévision, bascule de l'autre côté.
Mesuré le 22/08 sur 40 539 heures appariées, ECMWF IFS 0,25° :

| estimateur | valeur |
|---|---:|
| `med(obs/prev \| prev >= 8)` — l'ancien | **0,761** |
| `med(obs/prev \| prev >= 1)` | 1,003 |
| `Somme(obs) / Somme(prev)` | **1,112** |
| `Somme(obs*prev) / Somme(prev^2)` — le neuf | 0,894 |
| `med(obs/prev \| obs >= 8)` — le miroir | **1,514** |

**Piège réutilisable, et c'est le vrai enseignement** : *un ratio
conditionné sur l'une des deux grandeurs qu'il compare mesure d'abord sa
propre condition.* Le test qui le détecte tient en une ligne — refaire
le calcul en conditionnant sur l'AUTRE grandeur. Si les deux réponses
encadrent 1 au lieu de coïncider, le seuil parle plus fort que la
donnée. À appliquer partout où un seuil trie avant un rapport ; le
scoring en compte plusieurs autres (`DIR_MIN_WIND_KMH`, les quorums
d'événements) qui n'ont pas été audités dans ce lot.

**Second enseignement, sur l'AMPLEUR** : l'effet dépend entièrement de
la loi de la grandeur. Un premier banc, qui tirait la vérité
UNIFORMÉMENT sur [4, 24] km/h (médiane 14), ne voyait presque rien — le
seuil de 8 n'y coupait qu'une queue étroite. Le vent réel est très
dissymétrique (médiane mesurée : **7,12 km/h**), le seuil tombe en plein
milieu, et c'est là qu'il mord. Un banc de sélection doit reproduire la
LOI, pas seulement le mécanisme.

**Fix** : `speed_ratio` est désormais la pente des moindres carrés
`Somme(obs*prev)/Somme(prev^2)`, sans seuil — le facteur qui minimise
l'erreur quadratique, ce qui est précisément ce qu'on lui demande.
⚠️ Il ne vaut PAS 1 sur un modèle sans biais : il vaut
`Var(verite)/(Var(verite)+Var(erreur))`, l'atténuation classique. Le CAP
garde sa médiane conditionnée à 8 km/h **des deux côtés** — une
condition symétrique ne fabrique pas le biais qu'elle mesure. Jumeau TS
(`verifScore.penteMoindresCarres`) écrit le même jour, parité rejouée.

**Effet de bord découvert en réparant** : l'ancien seuil faisait taire
l'estimateur sur toute journée entièrement sous 8 km/h — donc les sites
ABRITÉS, ceux qui auraient le plus besoin d'une correction, n'en avaient
jamais.

**Vérifié** : `test_scoring.py` §1 ter reproduit la version d'avant et
la montre fausse (patron `TestVersionNaiveEstRouge` du S0.7) ; 89
assertions vertes dont la parité TS ; `model_character.speedRatio` purgé
par `supabase_step50_lot_s2_purge_speedratio.sql` pour ne pas mélanger
deux définitions dans une même moyenne exponentielle. Aucun écran ne
lisait cette métrique (`modelCharacter.ts` n'est importé par aucun
composant), donc aucune régression visible.

---

## Un « corrigé » peut gagner sans rien corriger (22/08/2026, lot S2)

**Symptôme** : appliquer le biais des jours antérieurs fait tomber
l'erreur vectorielle médiane de 29,4 % (mesuré hors échantillon sur
30 268 balise-jours). Chiffre spectaculaire, et à moitié faux.

**Cause** : multiplier une prévision bruitée par un facteur inférieur à
1 réduit une erreur quadratique **quel que soit ce facteur**, parce que
c'est un rétrécissement de la variance, pas une correction de biais.

**Ce qui l'a prouvé** : le TÉMOIN PLACEBO — appliquer à une balise le
biais d'une AUTRE balise. Il gagne **13,0 %**, soit 44 % du gain
affiché. Et descendre de la case fine à la balise ne rapporte que
**0,5 point** (28,9 % → 29,4 %).

**Piège réutilisable** : *toute correction apprise doit être comparée à
la même correction apprise sur le mauvais sujet.* Sans ce témoin, un
gain de rétrécissement se lit comme un gain d'information, et on
attribue au site ce qui appartient à l'arithmétique. Le témoin coûte
une balise-jour sur sept.

**Fix** : `score.bilan_temoin()` mesure les trois erreurs (brut,
corrigé, placebo) à chaque run et publie la part imputable au site dans
le journal ET dans le `meta` du JSON publié — pour qu'on ne puisse pas
lire le gain sans son témoin.

## Voir aussi

- `agrume-implementation-tah-15-08.md` (projet Claude « balise watch ») —
  détail complet du lot qui a révélé ces deux bugs, y compris la
  réconciliation d'un écart de comptage (23 vs 25-26 annoncés) qui n'est
  PAS un bug de code mais une erreur de vérification dans l'étude
  préalable.
