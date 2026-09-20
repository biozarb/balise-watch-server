# Verdict de pente du 19/09/2026 — pas de verdict : la nuit 18→19 est morte. Le garde est déployé, le contrôle s'est tu sur la durée

## 09:05 — routine Balise Watch, lecture seule sur le VPS, AUCUNE écriture Jira

Étape 0 faite : `git log --since=midnight` **vide dans les deux dépôts**
(`surveillance balise` → dernier commit `c83aed3` du 18/09 ;
`balise-watch-server` → dernier commit `bebe1ca` du 18/09). Aucune autre
session n'a tourné ce matin. `notes-projet/README.md` relu.
**Il n'y a pas de note `verdict-pente-18-09.md`** : la nuit du 18/09 —
qui est pourtant une vraie nuit comparable, la première sur le code du
17/09 — n'a jamais été relue. Elle est donc instruite ici.

## 1. ⛔ La nuit 18→19 a ÉCHOUÉ

```
{"jour": "2026-09-19", "lancement": "timer", "duree_s": 1767,
 "exec_status": 1, "result": "exit-code", "n_57014": 13,
 "jalon_max_mo": 1872, "swap_peak_mo": 2200.1, "incidents": []}
```

Morte à **06:28:08**, après 1 767 s, sur `urllib.error.HTTPError:
HTTP Error 500` remontée jusqu'en haut (`score.py:964 select` →
`score.py:801 _page` → `raise derniere ... Abort`). Pas de
`lignes_score_zone`, pas de `lignes_glissant`, pas de `lignes_regime`,
pas de `balise_jours_rejeu` dans la ligne du registre :
**la journée du 18/09 n'est probablement pas notée** (même signature
qu'au 16/09, où `model_score_zone` as_of était à 0). ⛔ Non vérifié en
base : la routine n'a pas le droit de jouer du SQL.
