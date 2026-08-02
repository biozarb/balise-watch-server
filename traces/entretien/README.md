# Entretien quotidien des packs météo

> Créé le 02/08/2026, au lendemain du backfill. Trois fichiers, dans
> l'ordre où on s'en sert.

| Fichier | Rôle |
|---|---|
| `balise-watch-r2.env.exemple` | modèle des identifiants R2. **Ne contient aucune vraie valeur** et ne doit jamais en contenir. |
| `entretien.sh` | enveloppe du run : verrou, chien de garde, journal rotaté, compte d'échecs consécutifs. |
| `app.balisewatch.entretien.plist` | déclencheur launchd, 06:30 locales. |

---

## Avant tout — le run à la main, une fois

Le mode `entretien` n'avait **jamais tourné** avant le 02/08, et sa
première version aurait détruit les 210 packs (cf. l'en-tête de
`backfill_packs.py`, § « un pack ne rétrécit jamais »). Le correctif est
vérifié en simulation, pas encore contre le vrai R2. **Ce premier run
manuel est la vérification, pas une formalité.**

```bash
cp entretien/balise-watch-r2.env.exemple ~/.balise-watch-r2.env
chmod 600 ~/.balise-watch-r2.env
$EDITOR ~/.balise-watch-r2.env          # y coller les vraies valeurs

cd "PWA/balise-watch-server/traces"
source ~/.balise-watch-r2.env

# 1. À blanc : rien n'est écrit, rien n'est appelé. Lire le bloc
#    DIMENSIONNEMENT, en particulier la ligne « entretien quotidien ».
python3 backfill_packs.py --mode entretien --dry-run

# 2. UN SEUL déco, pour de vrai. C'est ce run-là qui compte.
python3 backfill_packs.py --mode entretien --limit 1 --go

# 3. Si le point 2 est conforme : le catalogue.
python3 backfill_packs.py --mode entretien --go
```

### Ce qu'il faut voir au point 2

| | attendu |
|---|---|
| Fenêtre annoncée | `dernière journée du pack → <J-1>`, pas une plage de 92 jours |
| Journées fetchées | **1** (ou le nombre de jours de retard) |
| Compteurs | `R2 Class A 1 Class B 1` — une lecture, une écriture |
| Appels pondérés | ~0,09 |

Puis, la seule vérification qui prouve que le corpus a survécu :

```bash
curl -s --compressed \
  "https://pub-14b7b6ffdba34729b51280359c8f2c01.r2.dev/packs/v1/45.1757_5.4370.json.gz" \
  | python3 -c "import json,sys; p=json.load(sys.stdin); \
      print(p['nom'], 'n=', p['n'], p['dates'][0], '→', p['dates'][-1], \
            'généré le', p['genere_le'])"
```

`n` doit avoir **augmenté** (941 → 942…), jamais diminué, et la première
date rester `2024-01-02`. Si `n` a chuté, ne relancez rien et
supprimez-en la cause avant tout autre run — mais le garde-fou
anti-régression devrait avoir provoqué un `ABORT` bien avant l'écriture.

⚠️ `--limit N` ne veut pas dire « les N mêmes » mais « N parmi ceux qui
restent » (piège du 01/08). Pour vérifier un déco précis, lisez le
checkpoint, pas la sortie de `--limit`.

---

## Installer le déclencheur

```bash
cp entretien/app.balisewatch.entretien.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/app.balisewatch.entretien.plist
launchctl kickstart -p gui/$(id -u)/app.balisewatch.entretien   # test immédiat
```

État et journaux :

```bash
launchctl print gui/$(id -u)/app.balisewatch.entretien | head -20
tail -40 ~/.balise-watch-entretien/entretien.log
cat ~/.balise-watch-entretien/dernier_succes
cat ~/.balise-watch-entretien/echecs_consecutifs   # alerte macOS dès 2
```

Désinstaller : `launchctl bootout gui/$(id -u)/app.balisewatch.entretien`

---

## Coûts, une fois pour toutes

Mesuré au dry-run du 02/08 sur 210 décos :

| | par jour | par mois | palier gratuit | part |
|---|---|---|---|---|
| Open-Meteo pondéré | **18** | 540 | 10 000/j · 300 000/mois | **0,18 %** |
| R2 Class B (lecture des packs) | ≤210 | ≤6 300 | 10 M/mois | **0,06 %** |
| R2 Class A (écriture) | ≤210 | ≤6 300 | 1 M/mois | **0,63 %** |
| Stockage | — | ~3,5 Mo | 10 Go-mois | **0,035 %** |

⚠️ Le prompt de reprise du 02/08 annonçait « ~3 % du quota Open-Meteo » :
c'était le chiffre d'une fenêtre de 92 jours (~15 % en réalité), pas
celui d'un entretien à J-1. Le vrai coût est deux ordres de grandeur en
dessous.

« ≤ 210 » et non « 210 » : un pack qui n'a gagné aucune journée n'est
**pas** réécrit. Un run relancé le même jour ne coûte donc que ses
lectures — et n'invalide pas le cache navigateur des pilotes pour rien.

---

## ⚠️ Pourquoi PAS une GitHub Action

Ce repo contient déjà cinq pipelines Python déclenchés par
`.github/workflows/` (`arome-wind`, `arome-thermal`, `arpege-isobars`,
`arpege-thermal`, `arome-gustfront`). Faire de l'entretien le sixième
est l'idée qui vient immédiatement, et **c'est une fausse bonne idée.**

Ces cinq-là téléchargent des GRIB publics de Météo-France : **aucun
quota**, l'IP d'exécution n'a aucune importance. L'entretien, lui,
appelle **Open-Meteo, dont le quota se compte PAR IP**. Le faire tourner
depuis les runners GitHub reviendrait à consommer un quota partagé avec
tous les autres projets qui font pareil — la même faute que le VPN
écarté le 01/08, et que l'interdiction d'appeler Open-Meteo depuis l'IP
de Render.

C'est aussi pour ça que ce dossier contient un `plist` launchd et pas un
`.yml` : la cible d'exécution est **le poste de Yann**, et le fichier le
dit de lui-même.

Si un jour l'entretien doit tourner sans le poste de Yann, la sortie
propre n'est pas un runner partagé : c'est la Route 3 de
`SOURCES_ARCHIVE_METEO_01-08.md` (dump AWS + API Open-Meteo locale),
qui supprime le quota au lieu de le déplacer chez quelqu'un d'autre.

---

## Ce que ce dispositif ne sait pas faire

**Détecter sa propre absence.** Si launchd cesse d'appeler le script,
rien ici ne s'exécutera pour le dire — le compteur d'échecs ne compte
que les runs qui ont eu lieu. Le témoin qui ne dépend pas du mécanisme
surveillé est ailleurs, et il est gratuit : chaque pack porte
`genere_le` et sa dernière date, et le bloc « journées comparables » de
la fiche déco affiche jusqu'à quand va le corpus. Un pack qui n'avance
plus se voit à l'écran, côté pilote.
