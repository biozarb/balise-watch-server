# Dépouillement du journal de latence — phase C (26/08/2026)

Les chiffres de `CONCEPTION_CADRE_COURT_26-08.md` viennent d'ici. Aucun
de ces scripts ne produit quoi que ce soit : ils LISENT et ils
impriment.

## Rejouer

Le journal n'est pas versionné (il vit sur le VPS et il grossit) :

```
scp debian@51.91.102.146:/var/lib/bw-model-verif/agrume_latence.ndjson .
python3 depouille.py     # §1.1 — latences par source
python3 dispo.py         # §3.2 — âge du plus frais disponible à T
python3 dispo2.py        # §3.2 — grille fine + couples (T, H)
python3 dispo3.py        # §1.2 et §3.2 — écart des 8 paquets, modèle vs chaîne
python3 cadre1.py        # §2  — à l'échéance L, AROME existe-t-il ?
```

`sonde_genere_le.py` se lance **sur le VPS**, il lit R2 :

```
cd ~/balise-watch/balise-watch-server
set -a && . ~/.balise-watch-r2.env && set +a
STORAGE_BACKEND=r2 ~/venv-balise/bin/python3 sonde_genere_le.py 2026-08-24 2026-08-25
```

## ⛔ Les deux pièges de ce dépouillement

1. **`latence_max_min` est une BORNE HAUTE** (« à cet instant il était
   là »), pas une latence. `latence_min_min` donne l'autre borne quand
   le run a été vu absent au moins une fois. Côté AROME l'incertitude
   médiane est de **15 min** et le milieu d'encadrement du dernier
   paquet tombe à 203 min au lieu de 211.
2. **La latence AROME est BIMODALE par heure de run** (00/03 Z ≈ 2 h,
   les autres 3 h 15 à 4 h 36). Raisonner avec la médiane globale de
   211 min sur une heure de run particulière donne des conclusions
   fausses — c'est arrivé, cf. `BUGS.md` du 26/08 (phase C).
