# `notes-projet/` — le miroir git des notes du projet Claude

Le projet Claude « surveillance balise » porte des notes de session
(`claude/*.md`). Elles sont pratiques — visibles depuis n'importe quelle
conversation — mais **elles n'ont aucun historique** : `project_write`
remplace le document en place, sans version précédente, et réinitialise
même son `created_at`. Un écrasement est définitif côté projet.

C'est arrivé le 11/09/2026 : deux runs de la même routine ont tourné le
même matin, le second a réécrit `claude/verdict-pente-11-09.md` sans
avoir lu ce que le premier y avait mis. Le texte n'a été récupéré que
parce qu'il restait dans le transcript du premier run.

Ce dossier est le filet. **Le document projet est la vitrine ; git est
l'historique.** Un écrasement redevient un `git show`.

## Les quatre règles (à rappeler dans tout prompt de routine)

1. **Lire avant d'écrire.** Tout `project_write` vers un chemin qui
   existe déjà est précédé d'un `project_read`, et le résultat est une
   FUSION — jamais un remplacement. Le contexte d'ouverture de session
   liste les documents existants : c'est là qu'on voit la collision.
2. **Une note par jour, en sections horodatées** (`## HH:MM — qui, quoi`),
   pas un document par session. Deux runs du même jour coexistent au lieu
   de s'écraser, et la série reste lisible dans trois semaines.
3. **Miroir ici, puis commit**, avant ou juste après l'écriture dans le
   projet. Même nom de fichier que le chemin projet, sans le dossier
   `claude/`.
4. **Commencer par regarder ce qui a déjà été fait aujourd'hui** :
   `git log --since=midnight` dans `balise-watch-server` ET dans le dépôt
   principal, plus la note du jour si elle existe. C'est ce qui évite le
   doublon entier, pas seulement l'écrasement.

## Pourquoi ici et pas dans le dépôt principal

`amelioration scoring/` n'est pas suivi par git, et
`PWA/balise-watch-server/` est exclu du dépôt principal par
`.gitignore:5` (dépôt séparé). Ce dossier-ci est à la RACINE du dépôt
serveur : les `rsync` de déploiement ne visent que `model-verif/` et
`tools/`, donc il ne part jamais sur le VPS.
