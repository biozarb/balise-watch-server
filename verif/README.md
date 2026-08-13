# `verif/` — le produit A et ses confrontations

**Créé le 13/08/2026 (Lot J, arbitrage A3 de Yann) en coupant
`agrume/colonnes.py` en deux.** Ce paquet porte ce qui n'existe QUE pour
vérifier le modèle : le conteneur de l'archive, les confrontations, et la
rétention.

---

## ⛔ La règle de dépendance, et elle est bancée

```
verif/  ──peut importer──▶  agrume/        ✅
agrume/ ──────────────────▶ verif/         ⛔ sauf DEUX exceptions nommées
```

`verif/test_separation.py` lit statiquement (`ast`) tous les imports
d'`agrume/`, y compris ceux cachés dans une fonction, et refuse toute
flèche vers `verif/` qui ne figure pas dans sa liste nominative. Les deux
exceptions actuelles y sont écrites avec leur raison :

- `agrume/ingest_colonnes.py` — l'ingestion remplit les DEUX produits
  dans le **même** `sur_champ`, depuis les mêmes messages (7,6 s contre
  7,9 mesurés le 10/08). ⚠️ **On sépare les MODULES, jamais la passe.**
  L'alternative — déplacer l'ingestion ici — ferait dépendre le produit B
  du module de scoring, ce qui est pire dans les deux sens.
- `agrume/test_transect.py` et `agrume/test_profil.py` — deux bancs dont
  le travail EST de comparer le produit A au produit B.

⚠️ La liste est **nominative, pas catégorielle**. « Les bancs ont le
droit » se serait élargi tout seul ; ajouter une troisième exception
oblige à écrire pourquoi, dans le fichier, à côté des deux autres.

---

## Ce qui est resté dans `agrume/`, et pourquoi

| resté côté modèle | parce que |
|---|---|
| `quantification.py` | `grille.py` (produit B), `pi.py` (AROME-PI) et `profil.py` en dépendent tous. C'est le SEUL endroit du projet qui convertisse les unités — le dupliquer serait la pire issue possible |
| `freeze_balises.py` | ⚠️ **La note d'arbitrage le plaçait ici ; le code dit non.** Il est importé par `ingest_pi.py`, `ingest_colonnes.py` et `freeze_orographie.py` — trois modules du modèle. Le déplacer aurait créé une seconde flèche `agrume/` → `verif/` sans rien gagner. Il fige un axe, il ne vérifie rien |
| `radiosondage.py` | même raison : `freeze_balises.py` et `freeze_orographie.py` l'importent pour faire entrer les points de sondage dans l'axe et dans l'orographie. Le CLIENT du radiosondage est ici (`confronter_sondage.py`), sa SOURCE est là-bas |

---

## Les fichiers

| fichier | rôle |
|---|---|
| `colonnes.py` | le conteneur du produit A : disposition, remplissage, manifeste, npz |
| `purge.py` | **la rétention glissante 7 jours** — l'arithmétique de runs qui remplace un index |
| `sonder.py` | lire un profil en un point, en tableau ou en JSON |
| `confronter_sondage.py` | le profil contre un vrai ballon (Wyoming), À LA MAIN |
| `confronter_quotidien.py` | ⚠️ **Lot M, 13/08.** Rejoue `confronter_sondage.py` tout seul, chaque jour, pour CHAQUE station active, sur la veille (00Z + 12Z) — journal NDJSON, idempotent, jamais un silence. Timer VPS `bw-agrume-confronter-quotidien` (`systemd/`) |
| `confronter_calque.py` | le produit A contre le calque altitude du produit B |
| `marche_raccord.py` | la marche entre les deux mailles à 100 m/sol |
| `test_colonnes.py` | le banc du produit A — quantification ET conteneur |
| `test_purge.py` | la purge sur un faux backend, avec trous et panne |
| `test_separation.py` | la coupe elle-même, vérifiée statiquement |
| `test_confronter_quotidien.py` | le calcul du run, l'idempotence, la station inactive court-circuitée — hors-ligne |

```
python3 verif/test_colonnes.py
python3 verif/test_purge.py
python3 verif/test_separation.py
python3 verif/test_confronter_quotidien.py
```

Tous hors-ligne, sans réseau ni clé. Les quatre sont dans la CI
(`agrume-colonnes.yml`).

---

## La rétention — ce qu'elle coûte, et ce qu'elle interdit

⛔ **Arbitrages A1 et A2 de Yann, 13/08/2026.** Rétention **glissante de
7 jours** sur le produit A ; les scores, eux, ne se purgent jamais.

**Le prix, et il est payé, pas découvert :** on renonce à re-scorer le
passé avec une méthode future. Une vérification v2 ne s'appliquerait
qu'aux runs postérieurs à son déploiement.

**Ce que ça change, mesuré le 13/08 :**

| | avant | après |
|---|---|---|
| résident produit A | 27 Mo, **+13,9 Mo/jour** | ~100 Mo, stationnaires |
| projection | 5,06 Go/an → palier crevé au printemps 2027 | plat |

⚠️ 7 jours et pas 2 : le scoring a besoin d'horizon + ~24 h de marge
(≈ 48 h), et un diagnostic a déjà demandé 3 jours de recul (l'incident du
front de Tarentaise).

### La décision d'architecture : une FENÊTRE, pas un run

`ListObjects` est hors de portée (Class A). La purge reconstruit donc ses
clés par arithmétique — 8 réseaux par jour, à heures fixes, la clé porte
le run.

⛔ La version naïve (« supprimer le run d'il y a exactement N jours »)
fabrique des orphelins **définitifs** dès qu'une purge est manquée. À
chaque run on balaie donc les 56 runs théoriques de
`[maintenant − 14 j, maintenant − 7 j]` : chacun est visé 56 fois avant
de sortir de portée, donc il faudrait **sept jours pleins sans une seule
ingestion** pour qu'un objet s'échappe — un état que le voyant
Healthchecks signale après ~6 h de silence.

⚠️ **Ce que la purge ne saura jamais dire.** `DeleteObject` réussit sur
une clé absente : elle ne peut pas compter ce qu'elle efface, ni voir une
fuite. Son bilan compte des TENTATIVES, et le dit lui-même. Le détecteur
de fuite est ailleurs et existe déjà : `tools/audit_r2.py` (jeton
d'audit, qui a le droit de lister) mesure le résident par préfixe **et sa
pente**.

⚠️ **Elle a un plancher** : rien de plus vieux que 14 jours n'est
rattrapé. Sans conséquence au déploiement (l'archive avait 3 jours), mais
c'est écrit et bancé plutôt que découvert.

### ⛔ Où elle tourne, et pourquoi pas sur le VPS

Mesuré le 13/08, **opération par opération** :

| jeton | Put | Get | List | Delete |
|---|---|---|---|---|
| ordinaire, VPS | ✅ | 403 | 403 | **403** |
| audit (`BW_R2_AUDIT_*`) | — | ✅ | ✅ | ❌ |
| GitHub Actions | ✅ | ✅ | — | **✅** |

C'est pour ça que la purge de la grille PI n'a jamais rien supprimé
depuis le VPS. La preuve que celui des Actions supprime : l'index du
produit B en ligne porte `restes = 0` (or `index_apres_purge` n'y laisse
que les ÉCHECS), trois runs par domaine, et les runs évincés rendent 404
quand les gardés rendent 200.

⇒ `purger()` est appelée depuis `agrume/ingest_colonnes.py`, sur GitHub
Actions. **Ne pas la rebrancher sur le VPS** tant que le jeton
`Object Read & Write` demandé à Yann n'existe pas.
