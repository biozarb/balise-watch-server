# 🐛 Bugs trouvés et corrigés — balise-watch-server

> Entrées courtes, un piège réutilisable par section. Pas un journal de
> session (voir le projet Claude « balise watch » pour ça) — juste ce qui
> mérite de ne pas se refaire piéger la prochaine fois.

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
