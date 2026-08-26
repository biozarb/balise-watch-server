# Phase C — la case à échéance courte : CONCEPTION

**26/08/2026.** Aucun code de production n'a bougé. Le livrable est ce
document et les sept questions du §7.

> **En une phrase** : le cadre 1 n'est pas impossible, il est **vide
> sous +4 h par le plancher `MIN_HOURS_DAILY`, et sans intérêt
> au-dessus** ; le cadre 2 est constructible, et **il ne demande aucune
> série neuve** — seulement de changer QUELS RUNS alimentent la
> construction `agrume` / `agrume_pi` existante, et de trancher le poids
> de Δ.
>
> ✅ **Et un dossier se ferme au passage** : les « 3 heures perdues »
> entre AROME et notre archive n'existent pas. Deux d'entre elles sont
> une réécriture à l'identique par le filet de sécurité (§1.3 bis) ; la
> vraie latence de chaîne est d'**une heure**, et c'est du temps de
> détection, pas de calcul.

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
première disponibilité.** Deux séries de dispatch visent le même
workflow (`bw-agrume-poller-paquets` dès les 8 paquets,
`bw-agrume-poller-rallonge` dès la rallonge @51), plus un cron de
sécurité à H+4 h 20 — et la clé porte le run : chaque passe RÉÉCRIT le
manifeste de la précédente, à l'identique, avec un `genere_le` neuf.

### 1.3 bis ✅ Les « 3 h manquantes » — élucidées

L'historique des GitHub Actions est **public** (aucun jeton) :
`api.github.com/repos/biozarb/balise-watch-server/actions/workflows/
331042625/runs`. 90 exécutions du 22 au 26/08, 84 réussies.

En les croisant avec P(R) — l'instant où le dernier des 8 paquets est vu
— on reconstruit la **première** écriture des colonnes de chaque run
(`model-verif/latence/premiere_ecriture.py`, n = 25 runs) :

| étape | médiane |
|---|---|
| Météo-France publie le dernier des 8 paquets | **H+211** |
| détection (guet + back-off) puis exécution du workflow | **+60 min** |
| ⟶ **PREMIÈRE écriture des colonnes** | **H+271** (min 140, max 350) |
| une passe ultérieure réécrit le même manifeste | **+118 min** |
| ⟶ `genere_le` tel qu'on le lit aujourd'hui | **H+399** |

⛔ **Il n'y a donc PAS 3 heures perdues.** L'archive du produit A est
lisible à **H+271**, et les 128 minutes suivantes ne sont qu'une
réécriture à l'identique par le filet de sécurité. **`genere_le` est
faux de 2 heures dans le sens pessimiste.**

⚠️ **Ce qui reste vrai** : entre la publication par Météo-France
(H+211) et notre archive (H+271), il y a **une heure**, et ce n'est
**pas** la faute du workflow — l'exécution dure **23 min médians et
n'attend JAMAIS en file** (file d'attente mesurée : 0,0 min sur 84
exécutions, max 0,0). Le reste est le temps de DÉTECTION : le guet
élargit sa période jusqu'à 15 min (`PERIODE_MAX_S`) au-delà de
`FENETRE_FINE_MIN = 120`, et les runs qui publient tard (09, 12, 15 Z)
paient 58 à 88 min quand ceux qui publient tôt (00, 03 Z) n'en paient
que 31 à 38. ⓘ **Piste : c'est là qu'une demi-heure de fraîcheur est
récupérable**, pas dans les 3 h fantômes.

⚠️ **C'est une RECONSTRUCTION, pas une mesure**, et son hypothèse est
unique : `choisir_run()` retient le run le plus récent dont les 8
paquets sont couverts, donc un workflow démarrant dans la fenêtre
[P(R), P(R suivant)[ traite R. L'API ne donne pas l'entrée `run` du
dispatch ; seuls les journaux de job la porteraient.

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
| **chaîne** (nos colonnes) ⚠️ | 40 → **70** → 95 min | 275 → **365** → 450 min | 180 → **300** → 360 min |

*(min → médiane → max)*

⚠️ **Les deux lignes ne sont pas construites pareil.** La ligne
« modèle » utilise les **8 latences médianes par heure de run** (120 à
276 min). La ligne « chaîne » applique une **constante unique** (PI 40,
AROME **271** — la première écriture reconstruite du §1.3 bis, pas le
`genere_le` de 399) : sa dispersion ne mesure donc rien d'autre que
l'espacement de 3 h entre réseaux. **Cette ligne est un ordre de
grandeur, pas une mesure.**

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

### 3.3 ⛔ QUEL produit compare-t-on ? — section RÉÉCRITE le 26/08 au soir

> ⛔⛔ **La première version de cette section inventait un problème que
> le projet avait déjà résolu**, et Yann l'a vu tout de suite. Elle
> concluait qu'il fallait « deux séries neuves à maille égale » à cause
> de l'écart 0,01° / 0,025°. **Faux.** L'architecture n'a jamais fait
> entrer PI comme une série RIVALE d'AROME : elle le fait entrer comme
> un **Δ**, et un Δ mesuré à maille constante ne transporte aucun écart
> de maille. C'est écrit noir sur blanc dans `agrume_fcst.MAILLE_DELTA`
> depuis le 26/08 au matin — je l'avais cité deux sections plus haut
> sans en tirer la conséquence.

#### La maille : ce que dit le catalogue, énuméré et non deviné

⚠️ Ma première sonde interrogeait **quatre identifiants écrits à la
main**, tous en `SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND`. Or le portail rend
le même `NoSuchCoverage` pour un champ absent et pour un nom mal écrit —
`Portail.existe` le dit lui-même. **Une absence ne se prouve pas en
demandant les noms qu'on a imaginés.** `GetCapabilities` a donc été
énuméré en entier (`model-verif/latence/catalogue_pi.py`) :

| | `aromepi/001` | `aromepi/0025` |
|---|---|---|
| taille du catalogue | 2,24 Mo | 3,49 Mo |
| couvertures | 7 056 | 10 976 |
| **familles distinctes** | **33** | **52** |
| familles WIND/GUST | 7 | 10 |
| `U_/V_COMPONENT_OF_WIND` (vent moyen) | ⛔ **absent** | ✅ |
| `WIND_SPEED` | ⛔ **absent** | ✅ |
| `*_GUST`, `*_GUST_15MIN`, `MAXIMUM_GUST` | ✅ | ✅ |
| `TKE` | ⛔ absent | ✅ |

✅ **Confirmé sur les 33 familles, pas sur quatre noms.** Le 0,01° de
PI est un catalogue de nowcasting du DANGER — `HAIL`, `DIAG_GRELE`,
`CONVECTIVE_AVAILABLE_POTENTIAL_ENERGY`, `REFLECTIVITY_MAX_DBZ`,
`VISIBILITY_MINI_15MIN`, `PRECIPITATION_TYPE_15_MIN`,
`BRIGHTNESS_TEMPERATURE`, `WETB_TEMPERATURE` — plus les rafales, la
température, l'humidité et le point de rosée. **Le vent moyen n'y est
pas**, et ce n'est pas une question de type de niveau : `TEMPERATURE` et
`DEW_POINT_TEMPERATURE` y sont bien sur niveaux hauteur.

ⓘ La doc Météo-France annonce les deux résolutions pour AROME-PI mais ne
détaille aucune liste de paramètres par résolution — elle ne pouvait pas
trancher. Le catalogue, si.

#### ✅ Et c'est sans conséquence, parce que Δ ne traverse jamais les mailles

```
Δ = PI(0,025°) − AROME(0,025°)          ← même maille des deux côtés
composite = AROME(0,01°) + w · Δ        ← appliqué à la base fine
```

`agrume_fcst.MAILLE_DELTA` porte déjà l'arbitrage, mot pour mot :

> *« Calculer `PI(0,025°) − AROME(0,01°)` ferait entrer l'écart de
> RÉSOLUTION dans Δ — deux orographies différentes, deux plus proches
> voisins différents — et on créditerait AROME-PI d'une différence de
> maille. Δ se mesure donc en 0,025° contre 0,025°, puis s'applique à la
> base 0,01° du score. »*

⛔ **Les 0,122 km/h de « coût de la maille » mesurés en phase B ne
s'appliquent donc PAS ici.** Ils décrivent AROME₁₀ 0,025° contre
AROME₁₀ 0,01° servis tels quels. Dans le composite, la maille grossière
n'apparaît que dans une DIFFÉRENCE, où elle se retranche.

#### La conception qui en découle — et elle est bien plus courte

La classe à échéance courte **n'a pas besoin de séries neuves**. Elle
réutilise la construction existante et ne change qu'**une seule chose :
quels runs l'alimentent**.

| | aujourd'hui (classe +6 h) | classe à échéance courte |
|---|---|---|
| base 0,01° | AROME run 00 ou 03 Z | AROME **le plus frais publié à T** |
| Δ(0,025°) | PI et AROME du **même run** | PI **le plus frais publié à T** − AROME du run de base |
| poids | `poids_pi(τ)`, rampe 1 → 0 sur 4→6 h | **à trancher** (§7 Q7) |

⚠️ **Et il faut nommer ce que Δ devient.** Aujourd'hui, PI et AROME
viennent du même run : Δ est *la correction de PI*. Dans la classe
courte, Δ = PI(09 Z) − AROME(03 Z) : il porte **la correction ET les six
heures de fraîcheur**, mélangées. C'est exactement ce qu'on veut mesurer
— mais l'étiquette doit le dire, sinon on republie l'« avantage
silencieux » refusé le 13/08 sous un autre habit.

⛔ **La rampe, en revanche, n'a aucun sens dans ce cadre.** `poids_pi`
descend à 0 à 6 h parce qu'au-delà PI n'existe plus et qu'il faut
rejoindre AROME en douceur. À échéance courte, PI existe partout : à
+6 h la rampe servirait `w = 0`, c'est-à-dire **AROME pur sous une
étiquette PI**. Et la phase B a montré que `w = 1` n'est pas non plus le
bon choix (optimum hors échantillon ≈ 0,5). **C'est le seul paramètre
qui reste vraiment ouvert.**

ⓘ **Et une piste qui dort depuis le 10/08** : `WIND_SPEED_GUST_15MIN`
en 0,01° sur niveaux hauteur **n'a aucun équivalent dans AROME
classique**. Rafale à maille fine, pas de 15 min, 19 min de latence.
Hors périmètre de la phase C, mais c'est le seul endroit du portail où
« maille fine + forte fraîcheur » existe vraiment ensemble.

### 3.4 ⚠️ Ce que la phase B a déjà tranché, et qui cadre l'attente

**Il faut le dire AVANT la mesure, pas après.** La phase B a mesuré, à
échéance égale **et à maille égale**, que **PI(10 m) est à +0,08 km/h
d'AROME(10 m)** — comparable, très légèrement moins bon, pas meilleur.

> **PI ne peut donc pas gagner sur la qualité. Le cadre 2 est le seul
> cadre où il peut gagner du tout, et il ne peut y gagner que par la
> fraîcheur.**

✅ **La phase B est le témoin de la phase C**, et la condition de maille
est satisfaite d'office par la construction en Δ (§3.3). Si la classe
courte donne `agrume_pi` gagnant, on saura que c'est la fraîcheur — la
qualité à échéance égale est déjà mesurée, et elle est nulle.

⚠️ **Un seul confondant demeure, et il est réel** : `w`. La phase B dit
que `w = 1` dégrade et que `w ≈ 0,5` améliore, *à fraîcheur constante*.
Si la classe courte change à la fois la fraîcheur ET `w`, elle mesurera
les deux ensemble. **D'où la Q7** : garder `w = 1` (le même défaut
qu'aujourd'hui, donc comparable) coûte de la performance mais préserve
la lisibilité du verdict ; publier les deux `w` la préserve aussi et
coûte des lignes.

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

**Q3 · ~~Deux séries neuves à maille égale ?~~ — QUESTION RETIRÉE**
✅ Elle reposait sur une erreur (§3.3). La classe réutilise la
construction `agrume` / `agrume_pi` telle quelle et ne change que les
runs qui l'alimentent. **Aucune série neuve, aucun problème de maille** :
Δ se mesure en 0,025° contre 0,025° et ne transporte pas la résolution.
ⓘ Reste vrai : les modèles Open-Meteo ne peuvent pas entrer dans cette
classe — leur instant de publication n'est pas mesuré, et leur
`fetched_at` est l'heure de NOTRE appel de 03:15. La classe oppose donc
`agrume` à `agrume_pi`, deux concurrents. Un classement à deux, ou un
simple écart affiché ? **C'est ce qu'il reste à trancher ici.**

**Q4 · Combien d'instants de décision T par jour ?**
6 heures cibles par T, plancher à 6 : aucune marge (§6.2). Deux T par
jour (p. ex. 06:30 et 12:30 Z) doublent la matière, au prix de deux fois
plus de lignes.

**Q5 · Fraîcheur du MODÈLE ou fraîcheur de la CHAÎNE ?**
Écart **médian 4 h** à la publication Météo-France ; **médian 5 h** à
l'écriture de nos colonnes (§1.3 bis — et non 7 h, `genere_le`
surestimait de 2 h). Le pilote vit le second. **L'heure d'écart entre
les deux est notre chaîne**, et elle est presque entièrement du temps de
DÉTECTION, pas de calcul : la classe créditerait donc PI d'une heure qui
est la nôtre — à moins qu'on ne la récupère d'abord (§8).

**Q6 · Heures rondes, ou faut-il payer le pas de 15 min ?**
Le pas de 15 min oblige à rouvrir `OBS_HALF_WINDOW_MS` (§6.1).
**Recommandation : heures rondes pour la v1**, en écrivant que la
réserve de la phase B reste ouverte.

**Q7 · Quel poids donner à Δ dans cette classe ?** *(la vraie question,
maintenant que Q3 est retirée)*
⛔ La rampe `poids_pi` n'a pas de sens ici : à +6 h elle vaut 0, donc
elle servirait de l'AROME pur sous une étiquette PI (§3.3). Et la phase
B a montré que `w = 1` n'est pas bon non plus (optimum hors échantillon
≈ 0,5, gain +0,08 à +0,15 km/h). Trois options :
- **w = 1 sur les 6 heures** — « on fait confiance au plus frais ». Le
  plus lisible, et c'est ce que la fraîcheur mérite si elle vaut ce que
  tu penses.
- **w = 0,5** — la moyenne des deux, ce que la phase B mesure comme
  optimal, mais appris sur 8 journées d'août seulement.
- **w laissé libre et NOTÉ** — publier deux sous-séries (w=1 et w=0,5)
  et laisser le tableau de fiabilité trancher sur plusieurs semaines.
  Plus cher en lignes, mais c'est la seule qui ne devine pas.

---

## 8. Ce qui reste ouvert

- ✅ **Les « 3 h » entre la publication AROME et `genere_le` : ÉLUCIDÉES**
  (§1.3 bis). Deux heures sont une réécriture à l'identique par le filet
  de sécurité ; la vraie latence de chaîne est d'**une heure**, et elle
  est du temps de DÉTECTION.
- ⬜ **Récupérer cette heure de détection.** Le back-off du guet monte à
  15 min au-delà de `FENETRE_FINE_MIN = 120`, alors que le journal sait
  maintenant que 6 réseaux sur 8 publient APRÈS H+2 h. Une fenêtre fine
  apprise par heure de run (le poller apprend déjà `debut_de_guet_min`,
  mais pas `FENETRE_FINE_MIN`) rendrait ~30 min sur ces réseaux-là, pour
  quelques centaines d'octets de requêtes en plus.
- ⬜ **Cesser de réécrire un manifeste identique.** Le filet à H+4 h 20
  refait 23 min de travail pour un objet déjà correct, et efface au
  passage la seule trace de la vraie disponibilité.
- ⬜ **La cadence de report des Pioupiou**, qui décide si le pas de
  15 min est atteignable.
- ✅ **« Il faut deux séries neuves à maille égale » : ANNULÉ.** C'était
  une erreur (§3.3) — Δ ne traverse jamais les mailles, la construction
  existante convient telle quelle.
- ⬜ **La rafale fine à 15 min de `aromepi/001`**, sans équivalent dans
  AROME classique, et que rien n'utilise.
- ⬜ **Le rendu à l'écran** — aucun navigateur connecté à cette session.
- ✅ **Poussé** : `b39538e` (phase A), `4573e34` (phase B), `ac2f56f`
  (phase C).

## 9. Ce qui n'a PAS été vérifié

- ⬜ **L'attribution d'un workflow à un run AROME est une
  RECONSTRUCTION** (§1.3 bis), fondée sur `choisir_run()` : l'API des
  Actions ne rend pas l'entrée `run` du dispatch, seuls les journaux de
  job la porteraient. n = 25 runs.
- ⬜ **`H+40` pour les colonnes PI** vient de `journalctl` sur **7 jours**
  (n = 168), pas d'un champ d'archive.
- ⬜ **`H+399` pour le produit A** repose sur **4 journées** (n = 32).
- ⬜ **Une autre route pour AROME.** `poller.fabriquer_source` connaît un
  `arome-wcs` (le portail plutôt que le miroir S3) et personne n'a
  mesuré s'il publie plus tôt. Si oui, le §2 changerait encore.
- ⬜ **Aucun score du cadre 2 n'a été calculé.** Ce document dit ce qu'il
  faudrait pour en calculer un.
