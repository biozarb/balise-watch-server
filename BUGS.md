# 🐛 Bugs trouvés et corrigés — balise-watch-server

> Entrées courtes, un piège réutilisable par section. Pas un journal de
> session (voir le projet Claude « balise watch » pour ça) — juste ce qui
> mérite de ne pas se refaire piéger la prochaine fois.

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
