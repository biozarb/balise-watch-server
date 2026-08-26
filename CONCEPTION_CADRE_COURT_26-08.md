# Phase C — la case à échéance courte : CONCEPTION

**26/08/2026.** Aucun code de production n'a bougé. Le livrable est ce
document et les sept questions du §7.

> **En une phrase** : le cadre 1 n'est pas impossible, il est **vide
> sous +4 h par le plancher `MIN_HOURS_DAILY`, et sans intérêt
> au-dessus** ; le cadre 2 est constructible, et sa difficulté n'est pas
> la latence — c'est **la maille** et **le produit qu'on y met**.

⚠️ **NOTATION.** Aux §1 et §8, `H+n` veut dire *heure du run + n
minutes*. Aux §2 et §3, `H` est une *heure cible* et `T` un *instant de
décision*. Deux usages, deux sections — le mélange des deux a déjà
produit une faute dans la première version de ce document.

---

## 1. Ce que le journal du poller dit — enfin des MESURES

`agrume_latence.ndjson`, rapatrié du VPS : **1 973 entrées, 1 964
publications, du 10/08 au 26/08** (17 jours). Dépouillé avec
`poller.py --rapport`, puis recalculé indépendamment.

### 1.1 La publication par Météo-France

| source | n | min | **médiane** | d9 | max |
|---|---|---|---|---|---|
| **AROME-PI** (WCS, 24 runs/j) | 393 | 16 | **19 min** | 23 | 207 |
| **AROME**, dernier des 8 paquets du produit A | 108 | 116 | **211 min** | 285 | 404 |

✅ **Côté PI, ce ne sont plus des bornes** : **388 des 393 observations
sont ENCADRÉES**, incertitude médiane **2 min**.

⚠️ **Côté AROME, si.** La colonne ci-dessus est en `latence_max_min`,
c'est-à-dire « à cet instant il ÉTAIT là ». L'encadrement existe (926
observations de paquets, incertitude médiane **15 min** — la période de
guet S3), et le milieu d'encadrement du dernier des 8 paquets vaut
**203 min** au lieu de 211. **Tout ce qui suit prend la borne haute**,
qui est la seule affirmation sûre ; retenir que le vrai chiffre est
~8 min plus bas.

⛔ **La borne « ≤ 71 min et ≤ 76 min » de l'en-tête du poller est
PÉRIMÉE.** La latence réelle de PI est de **19 minutes**, trois à quatre
fois mieux que ce que ces deux observations ponctuelles laissaient
croire. C'était le but du module, et il l'a atteint.

⛔ **La doc Météo-France est tranchée par la mesure.** Elle annonçait
5 h 05 pour le run 06 et 3 h 30 pour le 09 — mutuellement incohérent.
Mesuré, par heure de run (dernier paquet, médiane, minutes) :

| run | 00 Z | 03 Z | 06 Z | 09 Z | 12 Z | 15 Z | 18 Z | 21 Z |
|---|---|---|---|---|---|---|---|---|
| médiane | **128** | **120** | **276** | 225 | 211 | 195 | 270 | 210 |

⛔⛔ **CETTE POPULATION EST BIMODALE, ET C'EST LE FAIT LE PLUS PIÉGEUX
DU DOCUMENT.** Les runs 00 et 03 Z sortent en ~2 h ; tous les autres en
3 h 15 à 4 h 36. Appliquer la médiane globale de 211 min à une heure de
run particulière donne des conclusions fausses — **la première version
de ce document l'a fait et en a tiré un « impossible » qui ne l'était
pas** (§2). PI, lui, est **plat sur les 24 heures de run** (17 à 23 min).

### 1.2 ⚠️ Une correction au rapport du poller lui-même

`rapport_ecart_paquets()` annonce « écart premier/dernier paquet :
médiane **60 min** ». Ce chiffre **mélange deux populations** : son
filtre est `":" in source`, qui ramasse aussi les paquets de rallonge
`@51` (médiane 256 min) à côté des paquets 0–24 h.

Recalculé sur les **8 paquets du produit A seuls**, run par run :

| | n | min | médiane | d9 | max |
|---|---|---|---|---|---|
| écart 1ᵉʳ → dernier paquet | 108 | 0 | **14 min** | 30 | 288 |

**Les huit paquets sortent quasi ensemble.** Séparé : les runs sans
rallonge donnent 15 min, ceux avec 63,5 min — c'est bien la rallonge
qui fabrique le 60. *(Piège réutilisable : un test sur le NOM d'une
source tenait lieu de définition de population.)*

### 1.3 Et la latence qui compte vraiment : NOTRE archive

⛔⛔ **Ce n'est pas la même chose.** Le poller date la publication par
Météo-France. Le pilote, lui, voit ce que NOS colonnes contiennent.

| archive | source de la mesure | n | médiane |
|---|---|---|---|
| colonnes **PI** écrites | journal `bw-agrume-ingest-pi`, 7 j | 168 | **H+40 min** (min 33, d9 46, max 104) |
| colonnes **produit A** | `manifest.json → genere_le`, 22→25/08 | 32 | **H+399 min** ⚠️ |

⚠️⚠️ **`genere_le` du produit A date la DERNIÈRE écriture, pas la
première disponibilité — et l'écart n'est pas mesuré.** Deux séries de
dispatch visent le même workflow (`bw-agrume-poller-paquets` dès les 8
paquets, `bw-agrume-poller-rallonge` dès la rallonge @51), et la clé
porte le run : la seconde passe RÉÉCRIT le manifeste de la première.

Ce qu'on sait : pour le run 00 Z du 25/08, le dispatch part vers
**H+128** et l'étape colonnes dure **15,6 min**
(`mesures.duree_min`). L'archive a donc pu être lisible dès **~H+145**.
`genere_le` dit **H+312**. **Entre H+145 et H+312, on ne sait pas.**

⛔ **Ne pas lire H+399 comme « AGRUME perd 3 heures ».** C'est une BORNE
SUPÉRIEURE. Mais l'hypothèse mérite d'être tranchée, parce que le poller
écrit lui-même que *« la fraîcheur est la seule chose qu'AGRUME
apporte »*. **→ §8, dossier ouvert.**

### 1.4 ⚠️ Le manifeste PI n'a pas d'horodatage

Vérifié dans le code (`pi.ColonnesPI.manifeste()` : 18 clés,
`ingest_pi.ecrire()` en ajoute 4) et en le lisant sur R2 : `bilan.secondes`
est une **durée** (`time.monotonic()`), il n'y a **aucun `datetime.now`
dans `pi.py`**. Les deux archives sont jumelles de forme et
**asymétriques sur le seul champ dont la phase C a besoin**.

ⓘ **Ce n'est cependant PAS irrécupérable**, contrairement à ce que la
première version de ce document affirmait. R2 porte un `LastModified`
par objet, et le dépôt sait déjà le lire — `tools/audit_r2.py` l. 886-897
le récupère depuis `list_objects_v2` (*« `LastModified` est déjà dans la
réponse du listing »*). Comme les colonnes PI, elles, ne sont **pas**
réécrites, ce `LastModified` **est** la date de mise à disposition
cherchée. Le coût est un listing Class A, donc pas de boucle — mais un
relevé ponctuel est à portée.

⚠️ Et le renoncement A2 de `verif/purge.py` ne s'applique **pas** ici :
il porte sur la rétention 7 jours du produit A (`agrume/colonnes/`). Les
colonnes PI sont définitives.

---

## 2. ⛔ Le cadre 1 — corrigé, parce que la première lecture était FAUSSE

*Cadre 1 : pour chaque heure cible H, prendre le run émis à H−L.*

> ⚠️ **La première version de ce document concluait « AROME n'existe pas
> à +1/+2/+3 h », en appliquant la médiane globale de 211 min à toutes
> les heures de run.** C'est faux, et c'est exactement le piège que le
> §1.1 signale. Compté run par run :

| L | runs AROME publiés avant l'heure cible | heures cibles/jour où AROME existe |
|---|---|---|
| **+1 h** | **0 / 108 (0 %)** | **0** |
| **+2 h** | 6 / 108 (6 %) | **0** |
| **+3 h** | 25 / 108 (23 %) | **2** — cibles 03 Z et 06 Z (runs 00 et 03 Z) |
| +4 h | 75 / 108 (69 %) | 6 |
| +5 h | 104 / 108 (96 %) | 8 |
| +6 h | 107 / 108 (99 %) | 8 |

*(« heures cibles/jour » = heures de run dont plus de la moitié des
occurrences passent avant l'heure cible.)*

✅ **La conclusion tient, mais par un autre chemin**, et il faut le
chemin exact :

- **+1 h et +2 h** : AROME n'existe effectivement pas. 0 heure cible.
- **+3 h** : AROME existe, mais pour **2 heures cibles par jour
  seulement** — grâce aux runs 00 et 03 Z, les deux rapides. ⛔ **2 est
  sous `MIN_HOURS_DAILY = 6`** : la classe ne sortirait **aucune ligne**.
  ⓘ **Elle s'auto-élimine exactement comme la classe +24 h d'AGRUME**,
  et le projet a déjà écrit ce raisonnement une fois (décision 1 du lot
  I, banc `test_lead_24_ne_sort_aucune_ligne`) : *« Le +24 h ne manque
  pas par oubli : il s'auto-élimine. On l'ÉCRIT plutôt que de le laisser
  lire comme un trou de données. »* Même mécanisme, même remède.
- **+4 h** : 6 heures cibles — **exactement sur le plancher**, et
  seulement 69 % des runs. Marge nulle. C'est la seule classe où le
  cadre 1 est presque viable.
- **+5 h et au-delà** : ça marche — et l'intérêt a disparu. À +5 h
  l'avantage de fraîcheur de PI est presque épuisé (`poids_pi` vaut déjà
  0,5), et on est de fait dans la classe « +6 h » existante.

> **Le cadre 1 n'est donc pas « impossible » : il est vide là où il
> serait intéressant, et inintéressant là où il est plein.**

---

## 3. Le cadre 2 — « ce que tu pouvais savoir à l'instant T »

### 3.1 Définition

> Pour une heure cible **H** et un instant de décision **T < H**, on
> compare la prévision de H issue du run PI le plus frais **publié à
> T**, à celle issue du run AROME le plus frais **publié à T**.
> Leurs échéances DIFFÈRENT — c'est le sujet, pas un défaut.

### 3.2 Ce que ça donne, simulé sur les latences MESURÉES

**Tableau A — âge du plus frais disponible à T.** Grille de 5 min sur
24 h.

| | PI | AROME | écart |
|---|---|---|---|
| **modèle** (publication MF, latence par heure de run) | 20 → **50** → 80 min | 125 → **295** → 455 min | 60 → **240** → 420 min |
| **chaîne** (nos colonnes) ⚠️ | 40 → **70** → 95 min | 400 → **490** → 575 min | 360 → **420** → 480 min |

*(min → médiane → max)*

⚠️ **Les deux lignes ne sont pas construites pareil.** La ligne
« modèle » utilise les **8 latences médianes par heure de run** (120 à
276 min). La ligne « chaîne » applique une **constante unique** (PI 40,
AROME 399) faute de mieux : sa dispersion 400→575 ne mesure donc rien
d'autre que l'espacement de 3 h entre réseaux. Et son 399 est lui-même
une borne supérieure (§1.3). **Cette ligne est un ordre de grandeur, pas
une mesure.**

**Tableau B — les échéances appariées.** Échantillonné à T = h:30.

| | PI | AROME |
|---|---|---|
| heures cibles couvertes | **6** (T+1 → T+6) | les mêmes |
| échéance servie pour ces heures | **+1 à +6 h** | **+3 à +13 h** |

**144 couples (T, H) par jour et par balise** avec un instant de
décision par heure. ⚠️ Le nombre d'heures cibles vaut **6 ou 5 selon la
MINUTE de T** : à T = h:30 le run de h est publié (h+19 min) et couvre
h+1…h+6 ; à T = h:10 il ne l'est pas encore, on retombe sur le run h−1
et il ne reste que 5 heures futures.

ⓘ Le « +3 h » d'AROME du tableau B est le même fait qu'au §2 : il
n'arrive que 2 fois sur 144, via les runs 00 et 03 Z.

✅ **C'est le cadre du pilote, et il est calculable.** À 09:30 pour
12:00 Z : PI sert son run 09 Z (**+3 h**, âge 30 min) contre AROME son
run 03 Z (**+9 h**, âge 6 h 30). Les deux sont ce qu'un pilote pouvait
réellement avoir.

### 3.3 ⛔ QUEL produit compare-t-on ? La vraie difficulté est là

Le §3.1 dit « la prévision issue du run PI ». **Ce n'est pas assez
précis, et les séries qui existent aujourd'hui ne conviennent ni l'une
ni l'autre.**

Ce qui existe dans `model_verif_daily` :

| série | ce que c'est | maille |
|---|---|---|
| `agrume` | AROME 10 m **BRUT** | **0,01°** |
| `agrume_pi` | le **COMPOSITE** AROME + Δ(AROME-PI) | base 0,01°, Δ en 0,025° |

⛔ **`agrume_pi` n'est pas « PI ».** C'est AROME corrigé par PI. Le
noter à échéance courte reviendrait à noter en même temps la fraîcheur
ET le réglage `α` que la phase B vient de remettre en cause (optimum
hors échantillon ≈ 0,5, alors que `poids_pi` plafonne à 1) — sans
pouvoir séparer les deux.

⛔ **Et la rampe n'a aucun sens dans ce cadre.** `poids_pi` descend à 0 à
6 h parce qu'au-delà PI n'existe plus et qu'il faut rejoindre AROME en
douceur. À échéance courte, PI existe partout : à +6 h la rampe servirait
`w = 0`, c'est-à-dire **AROME pur sous une étiquette PI**.

⛔⛔ **Et si l'on crée une série « PI brut », elle bute sur la MAILLE.**
PI n'existe qu'en **0,025°** (`domaine.GRID_3D`), quand la base
d'`agrume` est en **0,01°** (décision 2 du lot I). La phase B a chiffré
ce que coûte cette différence : **AROME₁₀ en 0,025° perd 0,122 km/h
contre le 0,01°** — soit **plus** que les 0,08 km/h qui séparent PI
d'AROME à maille égale. ⓘ Le code nomme déjà ce piège :
`agrume_fcst.MAILLE_DELTA` porte le commentaire *« on créditerait
AROME-PI d'une différence de maille »*.

> **Conséquence : une classe à échéance courte doit opposer PI(0,025°) à
> AROME(0,025°), pas à `agrume`(0,01°).** Sinon PI part avec ~0,20 km/h
> de handicap qui n'est pas de la fraîcheur. **Cela veut dire DEUX
> séries neuves, pas une.**

### 3.4 ⚠️ Ce que la phase B a déjà tranché, et qui cadre l'attente

**Il faut le dire AVANT la mesure, pas après.** La phase B a mesuré, à
échéance égale **et à maille égale**, que **PI(10 m) est à +0,08 km/h
d'AROME(10 m)** — comparable, très légèrement moins bon, pas meilleur.

> **PI ne peut donc pas gagner sur la qualité. Le cadre 2 est le seul
> cadre où il peut gagner du tout, et il ne peut y gagner que par la
> fraîcheur.**

✅ **La phase B est le témoin de la phase C** — *à condition que le §3.3
soit respecté*. Si les deux séries sont à maille égale et que PI gagne,
on saura que c'est la fraîcheur, parce que la qualité à échéance égale
est déjà mesurée. Si les mailles diffèrent, cette séparation est perdue
et la phase C ne conclura rien.

---

## 4. Les trois verrous

### ⚠️ Verrou 1 — l'horodatage de disponibilité

Le cadre 2 repose entièrement sur « publié à T ».

- **produit A** : `genere_le` existe, mais date la dernière passe (§1.3).
- **PI** : rien dans le manifeste (§1.4), mais `LastModified` sur R2 le
  donne, et les colonnes PI ne sont pas réécrites.

**Ce n'est donc pas une urgence** — c'est de l'hygiène : un champ
auto-portant survit à une recopie de bucket, un `LastModified` non.
Deux lignes dans `pi.py` et `ingest_colonnes.py`, à faire quand on
touchera ces fichiers, pas avant.

### ⚠️ Verrou 2 — `genere_le` du produit A date la dernière passe

Cf. §1.3. Un `genere_le_premier`, ou un refus de réécrire un manifeste
existant, lèverait l'ambiguïté.

### ⛔ Verrou 3 — le SQL, et il faudra que Yann l'exécute

```
check (lead_h in (6, 24, 48))
```

présent dans **quatre tables** de `supabase_step35_model_verification.sql`
(+ une dans `step41`), et `rank_reason` a son propre CHECK. Toute
nouvelle classe d'échéance est donc une **migration**, préparée en `.sql`
et lancée par Yann.

✅ Le geste est rodé : `step40`, `step42` et `step48` élargissent déjà le
CHECK de `rank_reason` par `drop constraint … / add constraint …`.
ⓘ En revanche **aucun CHECK ne contraint les noms de modèle** — ajouter
une série ne coûte pas de SQL.

---

## 5. Ce que le dispositif sait déjà faire — et qu'il ne faut pas refaire

1. **La classe d'échéance EST DÉJÀ une bande, et c'est écrit.**
   L'en-tête de `score.py` : la classe « +6 h » couvre en réalité les
   échéances **3 à 21 h**, et *« `lead_exact_h` porte l'échéance réelle
   moyenne de la journée, parce que la classe seule ferait croire à une
   précision qu'elle n'a pas »*.
   ✅ **La discipline que Yann exige — l'étiquette porte l'échéance —
   est déjà bâtie.** Le cadre 2 réutilise `lead_h` (l'étiquette) +
   `lead_exact_h` (la vérité), il n'invente rien.

2. **`rank_reason`** sait déjà dire pourquoi un rang n'existe pas
   (`window_too_short`, `too_few_pairs`, `tied`, `insufficient`,
   `partie_manquante`).

3. **Le poller** mesure les latences depuis le 10/08 — c'est ce document.

---

## 6. Les deux contraintes qui ferment des portes

### 6.1 ⛔ Le pas de 15 min n'est pas gratuit

`scoring.OBS_HALF_WINDOW_MS = ±20 min`, et la raison est écrite :
*« ±20 min plutôt que ±30 pour que deux heures consécutives ne partagent
aucun relevé — condition d'indépendance du test apparié »*.

À un pas de 15 min, deux échéances consécutives partageraient l'essentiel
de leur fenêtre : **le test apparié perdrait son indépendance**, et les
n annoncés seraient faux. Il faudrait resserrer la fenêtre, donc
connaître la cadence réelle de report des Pioupiou. **Non mesuré ici.**

⚠️ Conséquence à assumer : la réserve de la phase B — *« c'est à :15,
:30 et :45 que le composite justifie son existence »* — **reste
ouverte**, et le cadre 2 aux heures rondes ne la refermera pas.

### 6.2 ⚠️ `MIN_HOURS_DAILY = 6`, et un instant T donne 6 heures

**Déduit** (ce n'est pas une mesure, c'est de l'arithmétique sur
`HORIZON_MINUTES = 360`) : **6 heures cibles par instant T** au mieux,
et **5** si T tombe avant la publication du run de l'heure (§3.2). Le
plancher est à 6. **Marge : zéro, voire négative.** Une seule heure sans
relevé, et la journée entière tombe.

Trois issues, à trancher (§7, Q4) : plusieurs instants T par jour ·
abaisser le plancher pour cette classe seule · agréger plusieurs runs.

---

## 7. ⛔ LES QUESTIONS À YANN — rien ne se code avant

**Q1 · Cadre 1 ou cadre 2 ?**
→ **Recommandation : cadre 2.** Le cadre 1 est vide sous +4 h par le
plancher (§2) et sans intérêt au-dessus. ⓘ Il reste une variante
minoritaire : **cadre 1 à +4 h seulement**, 6 heures cibles pile, 69 %
des runs — honnête et simple, mais sans marge et à l'endroit où PI a
déjà presque tout perdu de son avance.

**Q2 · Comment la classe est-elle NOMMÉE et CLÉE ?**
- (a) une **nouvelle valeur de `lead_h`** + CHECK élargi, `lead_exact_h`
  portant la vérité comme aujourd'hui. Coût : une migration SQL.
- (b) de **nouveaux noms de modèle** dans `lead_h = 6`. Coût : zéro SQL.
⛔ **(b) est exactement ce que tu as refusé le 13/08** (décision 1 du lot
I : *« AGRUME serait ~10 h plus frais que les autres sous le même
intitulé +24 h — un avantage silencieux »*). **Recommandation : (a).**

**Q3 · Quelles séries entrent dans cette classe ?**
⛔ **Ni `agrume` ni `agrume_pi` ne conviennent** (§3.3) : le premier est
en 0,01°, le second est le composite avec sa rampe. La classe demande
**deux séries neuves à maille égale** — PI(0,025°) contre AROME(0,025°).
Est-ce un coût que tu acceptes, ou préfères-tu accepter le biais de
maille en l'ÉCRIVANT ?
ⓘ Les modèles Open-Meteo ne peuvent de toute façon pas entrer : leur
instant de publication n'est pas mesuré, et leur `fetched_at` est
l'heure de NOTRE appel de 03:15.

**Q4 · Combien d'instants de décision T par jour ?**
6 heures cibles par T, plancher à 6 : aucune marge (§6.2). Deux T par
jour (p. ex. 06:30 et 12:30 Z) doublent la matière, au prix de deux fois
plus de lignes.

**Q5 · Fraîcheur du MODÈLE ou fraîcheur de la CHAÎNE ?**
Écart **médian 4 h** à la publication Météo-France ; **médian ~7 h**
(max 8 h) à l'écriture de nos colonnes — ce second chiffre étant un
ordre de grandeur, pas une mesure (§3.2). Le pilote vit le second. Mais
si une partie de l'écart est notre propre chaîne, la classe créditerait
PI d'une lenteur qui est la nôtre.

**Q6 · Heures rondes, ou faut-il payer le pas de 15 min ?**
Le pas de 15 min oblige à rouvrir `OBS_HALF_WINDOW_MS` (§6.1).
**Recommandation : heures rondes pour la v1**, en écrivant que la
réserve de la phase B reste ouverte.

**Q7 · PI brut, ou le composite ?**
Cf. §3.3. **Recommandation : PI brut à maille égale** — le composite
mélangerait la fraîcheur avec le réglage `α`, et sa rampe servirait de
l'AROME pur sous une étiquette PI à l'échéance +6 h.

---

## 8. Ce qui reste ouvert

- ⬜ **Les ~3 h entre la publication AROME (H+211) et `genere_le`
  (H+399).** Borne supérieure, cause non établie. Dossier propre, et
  potentiellement plus gros que la phase C entière.
- ⬜ **La cadence de report des Pioupiou**, qui décide si le pas de
  15 min est atteignable.
- ⬜ **Une série PI(0,025°) et une série AROME(0,025°)** n'existent pas
  et devraient être créées (§3.3, Q3).
- ⬜ **Le rendu à l'écran** — aucun navigateur connecté à cette session.
- ⬜ **Accord pour pousser** `b39538e` (phase A) et `4573e34` (phase B).

## 9. Ce qui n'a PAS été vérifié

- ⬜ **La double écriture du manifeste produit A est une DÉDUCTION**
  (deux séries de dispatch sur le même workflow, clé portant le run),
  pas une observation run par run : l'historique des Actions n'est pas
  accessible d'ici (`gh` absent du Mac).
- ⬜ **`H+40` pour les colonnes PI** vient de `journalctl` sur **7 jours**
  (n = 168), pas d'un champ d'archive.
- ⬜ **`H+399` pour le produit A** repose sur **4 journées** (n = 32) ;
  le « H+312 » et le « 15,6 min » du run 00 Z sont **une seule
  observation**.
- ⬜ **Une autre route pour AROME.** `poller.fabriquer_source` connaît un
  `arome-wcs` (le portail plutôt que le miroir S3) et personne n'a
  mesuré s'il publie plus tôt. Si oui, le §2 changerait encore.
- ⬜ **Aucun score du cadre 2 n'a été calculé.** Ce document dit ce qu'il
  faudrait pour en calculer un.
