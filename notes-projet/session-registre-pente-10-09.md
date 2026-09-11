# Session 10/09/2026 — lot « REGISTRE ET PENTE » (surveillance de la notation)

Session Cowork (Fable), Desktop Commander + ssh depuis le Mac. Règles tenues :
aucun `systemctl start/restart/daemon-reload`, aucun SQL joué, aucun push,
aucun secret lu par valeur, rien d'écrit sur le VPS (deux sondes Python
en LECTURE sur `replay_*.json.gz`, un `systemd-analyze verify` sur une
copie dans `/tmp`, effacée). Tout le code est sur le Mac, à déployer par Yann.

## Lot A — l'enquête (`amelioration scoring/agrume/enquete-pente-10-09.md`)

1. **A1 — purge `model_score_zone` : FUITE, pas marche.** 94 436 lignes à
   effacer (une journée, `as_of` 09-02), comme chaque nuit ; 3 × 57014 en
   19 s dans le bloc purge (dont un `HEAD count`), 70 s après l'upsert de
   122 691 lignes ; `bw_character_avance` 5 × 57014 cette nuit (2 la
   veille). ⛔ Une purge ratée DOUBLE la suivante (≈ 190 000 lignes le
   11/09). `service_role` hérite des 8 s d'`authenticator` (doc Supabase) ;
   le SQL Editor (`postgres`) a 2 min → rattrapage à la main journée par
   journée, puis purge par tranches `limit`+`order` (PostgREST « Limited
   Update/Delete ») dans `score.py`. Aussi : le `HEAD count` + `DELETE`
   sur `model_character.last_day` (seq scan 1,2 M lignes, 0 ligne à
   effacer avant 02/2027) = 2 des 3 expirations → garde-fou calendaire.
2. **A2 — le porteur mémoire du régime n'est pas une requête** : `units`
   (1 253 232 balise-jours relus du cache local, 32 clés/ligne). Mesuré sur
   le VPS : 2 570 o/ligne ≈ 3 070 Mo ; élagué aux 22 clés lues
   (`COLONNES_FENETRE` + `regime`, `spread_kmh`, `err_vec_rms`, `unit`) :
   1 301 o/ligne ≈ 1 550 Mo → **−1 500 Mo**. Les jalons `VmRSS` sont des
   PLANCHERS (tas non rendu au noyau + pages swappées).
   ⛔ **FAUX — démenti le 11/09** : voir `verdict-pente-11-09.md` §6 et
   l'enquête §2.6. Le gain réel est de 99 o/ligne (−124 Mo), pas 1 269.
3. **A3 — swap 2 Go = cohabitation** : `bw-agrume-piaf` ~900 Mo toutes les
   10 min ; la vague de 07:00 (piaf 888 + reduit + infoclimat + ingest-pi)
   est tombée sur un run encore à 2 795 Mo (la veille il était fini à
   06:56). `swappiness=10`, 0 OOM. Ne pas toucher au swap.
4. ⚠️ **La durée ne monte pas à cause du swap** : +168 s de CPU sur +189 s.
   Régime +77 s, glissant +54 s, chemin J-0 +88 s (dont 57014).

## Lot B — le registre et le contrôle (écrits, bancs verts)

- `model-verif/registre_nuit.py` — une ligne JSON par nuit
  (`/var/lib/bw-model-verif/historique.jsonl`) : durée, code, garde
  appliqué, jalons, pic mémoire ET pic de swap (cgroup v2, lus par le run
  tant qu'il vit), étapes, lignes, incidents, delta `pswpout`. Appelé par
  `run.sh` (deux issues). `--retro` depuis journald (testé sur le vrai
  journal : 41 runs depuis le 07/08, la ligne du 10/09 = le prompt).
  Pourquoi run.sh et pas un lecteur : `debian` ne lit pas les lignes
  systemd dans journald (pas de `Consumed`, pas d'`oom-kill`).
- `model-verif/controle_quotidien.py` — date de franchissement (durée vs
  garde de la dernière nuit, mémoire vs `MAX_RSS_MO` importé) ; pente
  basse (25e centile) décide du silence, pente haute (75e) donne la date
  la plus proche → « entre le 17/09 et le 27/09 ». Se tait si plate /
  négative / hors horizon 30 j. Ne remonte jamais le garde : PROPOSE la
  commande. Motif `bw-purge-57014` quand la purge de la nuit a échoué.
  **Rejoué au 04/09 sur les nuits réelles : mémoire « entre le 09/09 et le
  17/09 » (réel 09/09), garde 3 900 « entre le 11/09 et le 30/09 » (réel
  11/09).** Le 08/09 : « franchit le seuil (2 800 Mo) le 09/09 ».
- `controle_quotidien.sh` + `systemd/bw-model-controle.{service,timer}`
  (07:30 Europe/Paris, attend la fin de la notation, Jira + journald +
  `BW_MODEL_CONTROLE_PING_URL`).
- `test_controle_quotidien.py` 35/35 · `mutations_controle_quotidien.py`
  17/17 vues (les 5 du prompt + 12) · `test_run_selftest.py` 39/39.

## Lot C — Jira

- `tools/bw_jira.sh` : `curl -K -` (jamais `-u`), cherche
  (`/rest/api/3/search/jql`, `labels = motif AND statusCategory != Done`)
  → commente, sinon crée (labels `bw-surveillance` + motif, KAN / Bug,
  ADF) ; jeton `cri.jira.<motif>` écrit en dernier et seulement si parti.
- `alerter()` de run.sh appelle enfin `BW_WEBHOOK_URL` (push des ⛔), pas
  depuis un banc.
- Inventaire : `BW_JIRA_*` et `BW_MODEL_CONTROLE_PING_URL` sont LUS
  (`bw_inventaire_alertes.sh`, exemple mis à jour) ; `test_alertes.sh` §H
  (20 assertions). 82/85 vertes — les 3 rouges (E1, E2, G11) viennent de
  `discord-bridge/` (dossier NON SUIVI par git, unité en 600), pas de ce
  lot. Au passage : `agrume/run-ingest-pi-rafale.sh` (859970c, 09/09 soir)
  manquait à `BW_RUNNERS_ALERTE` (C1 rouge) — ajouté.

## Reste à faire (par Yann — commandes exactes dans `model-verif/README.md`,
## section « Le registre des nuits et le contrôle de pente »)

1. rsync `model-verif/` + `tools/{bw_jira,bw_inventaire_alertes,test_alertes}.sh` ;
   copie des deux unités + du drop-in dans `/etc` (en-tête seul) ;
   `daemon-reload` ; `enable --now bw-model-controle.timer` ; sha256 des
   deux côtés.
2. rétro-remplissage : `journalctl … | registre_nuit.py --retro`.
3. `BW_JIRA_*` + `BW_MODEL_CONTROLE_PING_URL` dans `~/.balise-watch-alertes.env`
   ; test `GET /rest/api/3/myself` (200 attendu) — **pas encore passé**.
4. ⛔ La purge : SQL de rattrapage (journée par journée) puis purge par
   tranches dans `score.py` — enquête §1.6, BUGS.md 10/09.
5. Le porteur mémoire : élaguer `units` dans `replay_window` (enquête §2.5).
6. Un `git commit` (rien n'a été commité).

## Suite, même matin (08:04-08:20 CEST) — feu vert de Yann : commit, écriture VPS, les 4 points

- **Commits** `2580dfc` puis `b7fab52` sur main (pas poussés).
- **Déployé** : rsync `model-verif/` + `tools/`, copie des unités et du
  drop-in dans `/etc`, `daemon-reload`, `bw-model-controle.timer` armé
  (11/09 07:30 Paris), sha256 identiques Mac ↔ VPS ↔ /etc,
  `--controle-unites` : 33 identiques (les ⛔ restants sont d'avant :
  rafale jamais installée, balise-entretien 3 542 o).
- **Purge** : `score.py --purge-seule` — 09-02 (94 488 lignes) puis 09-03
  (95 373, 9 tranches, 28 s). ⛔ **`limit` est IGNORÉ par cette base**
  (PostgREST 14.5 / passerelle Supabase ; `PATCH …&limit=2` → 21 lignes) :
  `delete_par_tranches` découpe par `as_of=eq.<jour>` × `regime=eq.<r>`.
  Même une tranche `calm` a rendu 57014 avant d'être rattrapée par « le
  reste de la journée » — la base est vraiment lente (un HEAD count sur
  96 k lignes indexées a expiré aussi).
- **`model_character`** : garde-fou calendaire (`PREMIER_JOUR_CHARACTER`),
  aucune requête avant le 04/02/2027.
- **`units`** élaguée (`CLES_REJEU`, 22 clés) — effet attendu cette nuit :
  jalon régime ≈ −1 500 Mo, swap ≈ 0.
  ⛔ **Démenti le 11/09** : −124 Mo mesurés, et le nombre de clés n'était
  pas le levier. Voir `verdict-pente-11-09.md` §6.
- **Registre** rétro-rempli (41 runs). **Jira** : `/myself` → 200 ; premier
  run réel du contrôle → KAN-3 (durée), KAN-4 (mémoire), KAN-5 (purge
  57014 — déjà corrigée, à fermer).
- **Poussé** (`f17a60c..b7fab52`). **Healthchecks** : check
  `bw-model-controle` créé via Chrome (1 j / grâce 2 h, e-mail, tag
  model-verif), `BW_MODEL_CONTROLE_PING_URL` posée dans
  `~/.balise-watch-alertes.env` (600), premier ping reçu, jeton `cri.`
  effacé. **KAN-5** commenté et passé en Terminé. Plus rien n'attend
  Yann ; demain 07:30 le contrôle tourne seul.
- Bancs : test_score 1 101/0, mutations_memoire 17/17, test_controle 35/35,
  mutations_controle 17/17, test_run_selftest 39/39.

---

⚠️ Miroir git ajouté le 11/09/2026 (voir `README.md` de ce dossier). Deux
renvois ⛔ ont été insérés là où le 10/09 annonçait les −1 500 Mo, que la
sonde du 11/09 a démentis. Le reste est le texte d'origine du projet.
