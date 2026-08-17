# 🐛 Bugs trouvés et corrigés — balise-watch-server

> Entrées courtes, un piège réutilisable par section. Pas un journal de
> session (voir le projet Claude « balise watch » pour ça) — juste ce qui
> mérite de ne pas se refaire piéger la prochaine fois.

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

## Voir aussi

- `agrume-implementation-tah-15-08.md` (projet Claude « balise watch ») —
  détail complet du lot qui a révélé ces deux bugs, y compris la
  réconciliation d'un écart de comptage (23 vs 25-26 annoncés) qui n'est
  PAS un bug de code mais une erreur de vérification dans l'étude
  préalable.
