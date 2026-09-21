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

---

> ⛔ **Le run du 19/09 s'est arrêté ICI**, au milieu de la phrase ci-dessus.
> Tout ce qui précède est son texte, intact. Tout ce qui suit est une
> **reconstitution du 21/09/2026** (session Cowork, sur demande de Yann),
> faite UNIQUEMENT à partir de sources écrites : la ligne du registre du
> 19/09, `claude/session-lecture-day-19-09.md` (la session d'intervention
> du même jour), et `claude/verdict-pente-20-09.md`. Rien n'y est
> deviné ; ce qui n'a pas de source est dit comme tel.

## 2. (reconstitué) La cause, et ce qui l'a réglée

Source : `claude/session-lecture-day-19-09.md`. La nuit meurt sur trois
`57014` d'affilée sur `model_verif_event [0-999]` — **la page 1**, en
relisant ce qu'elle vient de publier (`model_verif_daily` 70 642 lignes,
`model_verif_event` 49 742). La lecture `?day=gte.<J-14>&order=id`
balayait l'index de `id` depuis zéro en jetant 950 193 lignes hors
fenêtre. Le 18/09 la même requête passait encore, à 7,63 s.

Correctif `0d108d7` (19/09, poussé et déployé le jour même, sha256
identiques Mac/VPS) : les lectures filtrées sur `day` paginent sur `day`,
`RELECTURES` 2 → 3. Validé la nuit suivante (voir
`verdict-pente-20-09.md` §2 : reprise dès 1/3, journée notée).

## 3. (reconstitué) La nuit 17→18, jamais relue

Source : le tableau de `verdict-pente-20-09.md`. Nuit comparable
(`timer`/`success`) : **durée 4 739 s**, garde 8 100 s, marge 3 361 s ;
jalon max **3 385 Mo** ; swap au pic 2 163,7 Mo ; pages sorties
2 099 718 ; pic système 3 617,5 Mo (réserve 207,5 Mo) ;
`balise_jours_rejeu` 1 694 837 ; `n_57014` 4.

## 4. (reconstitué) Le garde et le contrôle

Titre d'origine : « Le garde est déployé, le contrôle s'est tu sur la
durée ». Confirmé par le 20/09 : garde à 8 100 s dans le registre depuis
le 17/09 (`10-timeout-s3.conf` déployé). Le silence sur la durée venait
de la marge élargie, pas de la pente (+64 s/nuit mesurée le 20/09).
⚠️ Le texte exact du contrôle de 07:30 le 19/09 n'est dans aucune source
écrite : non reconstitué.

## 5. (reconstitué) Tickets

En-tête d'origine : **AUCUNE écriture Jira**, conformément à la règle
« nuit morte → on ne touche pas aux tickets ». KAN-3 et KAN-4 inchangés
ce jour-là par la routine.

## 6. Épilogue (21/09)

- KAN-3 **fermé le 21/09** sur décision de Yann (trois nuits plates,
  pente +0 s/nuit). Voir `verdict-pente-21-09.md`.
- KAN-4 ouvert : mémoire record à 3 510 Mo le 21/09.
