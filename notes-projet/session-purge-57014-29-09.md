# Session du 29/09/2026 — le 57014 de la purge n'était pas la purge

## 08:10 — Yann + Claude, débogage sur le verdict du 28/09 (purge « en échec », retard « qui double »)

### Ce qui était vrai, ce qui ne l'était pas

Le verdict du 28/09 disait : « la purge par tranches a échoué sur une vraie journée, la journée du 21/09 reste en base, le retard double ». Relecture du journal du VPS (28 et 29/09) :

- **28/09 07:25** : 18 tranches = deux journées (20/09 et 21/09) × 9. Les **huit tranches par régime du 21/09 ont réussi**. La seule qui a rendu 57014 est la neuvième, `?as_of=eq.2026-09-21` **sans `&regime=`** — « le reste de la journée ». Or `regime` est `not null` + CHECK sur exactement les huit valeurs de `TRANCHES_SCORE_ZONE` (step35) : cette tranche ne pouvait **rien** trouver. Elle a expiré à vide.
- Les deux `⚠️ compte model_score_zone : HTTP 500` (07:24:39 et 07:25:19) sont le `HEAD … Prefer: count=exact` sur `as_of < seuil`, **pas** le DELETE. C'est lui qui a produit le `? ligne(s) effacée(s)`.
- **29/09 07:23** : le compte expire encore (sur une table qui ne contient plus rien sous le seuil), la sonde « plus vieille journée » revient vide, et la boucle repart **aveugle de `seuil − 60 j` : 540 DELETE à vide en 30 s**, tous réussis, aucun 57014 dans le bloc purge.
- **Épreuve à 08:35** : `score.py --purge-seule` (code neuf) → `ⓘ purge model_score_zone : rien à effacer (?as_of=lt.2026-09-22)`. **Il n'y avait aucun retard.**

Mécanisme probable (à confirmer par le diagnostic SQL) : un filtre qui couvre ≥ ~10 % de la table (`as_of < seuil` pour le compte, `as_of = J` sans régime pour la 9e tranche) laisse le planificateur choisir un balayage séquentiel, surtout avec des statistiques d'avant la purge. Les tranches par régime (≈ 1/8 de journée, clé primaire) n'ont jamais été le problème.

### Ce qui a été fait

1. **`delete_par_tranches` réécrite** (`model-verif/score.py`, commit local **`e83d814`** du dépôt serveur) : plus aucun `count` — la plus vieille journée se lit par une sonde d'index (`select=as_of&order=as_of&limit=1`, rejouée une fois) ; plus de tranche sans régime ; sonde illisible ⇒ on s'arrête et on le dit (fini le repli aveugle) ; chaque tranche en 57014 est rejouée une fois après 5 s ; le nombre de lignes effacées vient du `Content-Range` de chaque DELETE (`_lignes_touchees`, vérifié en vrai : un DELETE à vide rend `content-range: */0`) ; borne alignée sur `lt.` (la boucle effaçait la journée du seuil en plus).
2. **Bancs** : `test_score.py` 1 157 vertes (cas 29/09 ajoutés : aucun HEAD, régime sur chaque DELETE, journée du seuil épargnée, sonde illisible ⇒ 0 DELETE, 9 appels pour 3 échecs, lecture du Content-Range). `mutations_memoire.py` : motif 18 réécrit, 5 mutations neuves, toutes vues ; restent 3 non vues (2, 5, 13 — motifs anciens qui ont bougé, dette antérieure).
3. **BUGS.md** (serveur) : entrée du 29/09.
4. **Déployé** sur le VPS à 08:35 : `rsync` de `score.py` seul, sha256 `e32c2b42a614843f…` identique des deux côtés ; `--purge-seule` joué en épreuve (4,5 s, rien à effacer).
5. **Prompt de la routine** (`Balise Watch — contrôle de pente quotidien`) corrigé : KAN-5 **ouvert** (il n'a jamais été clos), KAN-3 **Terminé** (pas de réouverture sans Yann), lecture du bloc purge sans sur-interpréter, attendu de la nuit 29→30, arbitrage `bw-regime-sensibilite`.
6. **Arbitrage de Yann** : `bw-regime-sensibilite` = **simple veille**, pas de ticket ; question à reposer seulement si la hausse s'additionne encore deux nuits.
7. **Dossier « base sous tension »** : `model-verif/diagnostic_base_sous_tension_2026-09-29.sql` (lecture seule, 9 blocs, correctifs candidats en commentaire) et `model-verif/rattrapage_purge_2026-09-29.sql` — **à jouer par Yann** dans le SQL Editor, rien n'a été joué. Fichiers non suivis par git (convention `.sql`).

### Ce qui reste

- **Nuit du 29→30** : première vraie épreuve du code (journée du 22/09, ≈ 125 000 lignes). Attendu : `→ purge model_score_zone : N ligne(s) effacée(s) en 8 tranche(s)`, aucune ligne `compte`.
- `rpc/bw_character_avance` : 57014 repris 1/3, ×1 le 28/09, ×2 le 29/09 (06:13, 06:19). Pas neuf (10/09, 16/09). Le diagnostic SQL (blocs 2, 5, 8) doit dire si c'est l'autovacuum, le plan, ou l'instance.
- Mémoire (KAN-4) : inchangé, rien de décidé sur la ligne en tuple.
- Pas de `git push`.

Miroir git : `notes-projet/session-purge-57014-29-09.md` (dépôt serveur), commit local, pas de push.
