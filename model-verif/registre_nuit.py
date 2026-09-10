#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  registre_nuit.py — LE REGISTRE DES NUITS DE NOTATION   (10/09/2026)
#
#  Une ligne JSON par nuit dans `/var/lib/bw-model-verif/historique.jsonl`.
#  C'est la transposition, à la durée et à la mémoire de `bw-model-score`,
#  de l'historique `audit_r2.jsonl` de la jauge R2 : sans relevés, pas de
#  pente ; sans pente, pas de date de franchissement ; et un chien de
#  garde qu'on remonte à la main la veille du jour où il aurait mordu
#  (40 → 65 → 90 min, trois fois en dix-sept jours).
#
#  ⛔ POURQUOI C'EST `run.sh` QUI ÉCRIT, ET PAS UN LECTEUR DU JOURNAL.
#  Trois raisons, toutes mesurées le 10/09 :
#    1. l'utilisateur `debian` N'A PAS le droit de lire les lignes de
#       systemd dans journald (« Users in groups 'adm', 'systemd-journal'
#       can see all messages ») — donc ni `Consumed … memory peak`, ni
#       `Failed with result 'oom-kill'`. Un lecteur du journal lancé par
#       un timer en `debian` serait aveugle sur les deux colonnes qui
#       comptent ;
#    2. le pic mémoire et le pic de swap se lisent dans le cgroup du
#       service TANT QU'IL VIT (`memory.peak`, `memory.swap.peak`,
#       cgroup v2, noyau 6.12) : ce sont les mêmes compteurs que systemd
#       résume dans `Consumed`, et seul le run peut les lire ;
#    3. le run est le seul à connaître son code de sortie et son chien
#       de garde AU MOMENT où ils comptent (`MAX_MINUTES` est lu à la
#       l. 242 de `run.sh`, avant tout `.env`).
#  Le lecteur de journal existe quand même — `--retro` — pour le
#  RÉTRO-REMPLISSAGE depuis le 03/08 (boot de la machine), joué une fois
#  avec `sudo journalctl`. On n'attend pas quinze nuits pour avoir une
#  pente honnête.
#
#  ⚠️ `swap_peak_mo` EST LA COLONNE QUE PERSONNE N'AURAIT MISE HIER.
#  Le 10/09 : `Mem peak 3.3G` (en baisse) et `swap 2G` (×7,4). `VmRSS`
#  — ce que lisent les jalons — ne compte pas les pages parties en swap :
#  un jalon qui baisse peut être une page qui est partie. Sans cette
#  colonne, la mémoire aurait eu l'air de se ranger.
#
#  ⚠️ UN JALON ABSENT N'EST PAS UN ZÉRO. Un run tué avant le régime n'a
#  pas de jalon régime ; l'écrire à 0 fabriquerait une chute de 2 900 Mo
#  dans la série, c'est-à-dire une pente négative qui ferait taire le
#  contrôle la nuit précisément où il faudrait qu'il parle. Les jalons
#  manquants sont ABSENTS du dictionnaire (voir `test_controle_quotidien`).
#
#  Usage :
#    # en fin de run, par run.sh (les deux issues, succès ET échec) :
#    registre_nuit.py --fin-de-run --log "$LOG" --duree 3860 --code 0 \
#        --garde-s 5400 --debut 2026-09-10T03:58:46Z --fin … --out "$ETAT"
#    # rétro-remplissage (une fois, avec le droit de lire systemd) :
#    sudo journalctl -u bw-model-score.service --since 2026-08-01 \
#        -o short-iso -q | registre_nuit.py --retro --out /var/lib/bw-model-verif
#    # relecture :
#    registre_nuit.py --afficher --out /var/lib/bw-model-verif
#
#  Code de sortie : toujours 0 sauf erreur d'usage (2). Ce script ne
#  décide rien ; c'est `controle_quotidien.py` qui lit et qui parle.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
NOM_REGISTRE = "historique.jsonl"

#: Le chien de garde interne (`BW_MODEL_VERIF_MAX_MINUTES`) au fil du
#: temps, pour le rétro-remplissage SEULEMENT — en production `run.sh`
#: passe la valeur qu'il a réellement appliquée. Chaque ligne est un
#: constat écrit dans l'en-tête de `10-timeout-s3.conf` :
#:   · 25 min : le défaut de run.sh, jusqu'au lot S3 ;
#:   · 40 min : lot S3 (23/08), avant la notation du 25/08 ;
#:   · 65 min : 03/09, après la nuit morte en code 124 à 2 400 s ;
#:   · 90 min : 09/09, après un run à 3 min 49 du garde.
#: ⚠️ La date est celle du DÉPLOIEMENT (en journée) : la nuit du 03/09
#: est bien morte sous 40 min, celle du 09/09 a tourné sous 65.
GARDE_HISTORIQUE = (
    (date(2026, 8, 23), 40 * 60),
    (date(2026, 9, 3), 65 * 60),
    (date(2026, 9, 9), 90 * 60),
)
GARDE_DEFAUT_S = 25 * 60

#: Le timer de `bw-model-reduit` (`OnCalendar=*-*-* 05:00:00 UTC`,
#: RandomizedDelaySec=60). Un run de notation encore vivant à cette
#: heure-là partage la machine avec lui — c'est le croisement que
#: `10-timeout-s3.conf` (09/09) dit « plus garanti ».
REDUIT_UTC = (5, 0)

#: Fenêtre de départ d'un run lancé par le TIMER (03:55 UTC +
#: RandomizedDelaySec=300). Hors de cette fenêtre, c'est un rejeu à la
#: main — non comparable pour une pente (machine, heure, cache différents).
TIMER_UTC_DE, TIMER_UTC_A = (3, 50), (4, 15)

# ── Les motifs lus dans le journal ───────────────────────────────────
_TS = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:Z|[+-]\d\d:\d\d))\s+(.*)$")
_PREFIXE_JOURNALD = re.compile(r"^\S+\s+\S+\[\d+\]:\s?")
_DIRE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)\s+(.*)$")
_DEBUT = re.compile(r"▶ score — bucket R2")
_FIN_OK = re.compile(r"run score OK en (\d+)s")
_FIN_KO = re.compile(r"run score en ÉCHEC \(code (\d+), (\d+)s\)")
_RESULT = re.compile(r"Failed with result '([a-z-]+)'")
_JALON = re.compile(r"mémoire après (.+?) : (\d+) Mo")
_SEUIL = re.compile(r"AU-DESSUS DU SEUIL DE (\d+) Mo")
_CONSUMED = re.compile(r"Consumed (.+?) CPU time(?:, ([\d.]+[KMGT]?) memory peak)?"
                       r"(?:, ([\d.]+[KMGT]?) memory swap peak)?")
_ETAPES = {
    "glissant": re.compile(r"score glissant : (\d+) lignes \(([\d.]+) s\)"),
    "regime": re.compile(r"score par régime : (\d+) lignes \(([\d.]+) s\)"),
    "stabilite": re.compile(r"\(([\d.]+) s\)\s+stabilité des rangs"),
    "rejeu": re.compile(r"rejeu d'archive : (\d+) balise-jours .* en ([\d.]+) s"),
}
_LIGNES = {
    "lignes_daily": re.compile(r"→ model_verif_daily : (\d+) lignes"),
    "lignes_score_zone": re.compile(r"→ model_score_zone : (\d+) lignes"),
}
_INCIDENT = re.compile(r"(⚠️ purge [^:]+ : HTTP \d+|⚠️ compte [^:]+ : HTTP \d+"
                       r"|SELF-TEST [A-Z ]+|⛔ [^—]{0,60}— AU-DESSUS DU SEUIL"
                       r"|Failed with result '[a-z-]+')")


# ══════════════════════════════════════════════════════════════════════
#  PARTIE PURE — aucune E/S, donc testable sur un journal rejoué
# ══════════════════════════════════════════════════════════════════════
def _mo_systemd(txt: str | None) -> float | None:
    """`3.3G` → 3379,2 Mo ; `269M` → 269 ; `564K` → 0,55. systemd
    formate en puissances de 1024 (`format_bytes`), pas en décimal."""
    if not txt:
        return None
    m = re.match(r"^([\d.]+)([KMGT]?)$", txt)
    if not m:
        return None
    v = float(m.group(1))
    return round(v * {"": 1 / 1048576, "K": 1 / 1024, "M": 1, "G": 1024,
                      "T": 1048576}[m.group(2)], 1)


def _secondes_systemd(txt: str) -> float | None:
    """`49min 18.943s` → 2958,9 ; `21min 704ms` → 1260,7 ; `1.647s`."""
    total, vu = 0.0, False
    for val, unite in re.findall(r"([\d.]+)(ms|s|min|h|d)", txt):
        total += float(val) * {"ms": 0.001, "s": 1, "min": 60, "h": 3600,
                              "d": 86400}[unite]
        vu = True
    return round(total, 1) if vu else None


def decouper(lignes) -> list[list[tuple[datetime | None, str]]]:
    """Découpe un flux de lignes (journald `-o short-iso`, ou le
    `score.log` de run.sh) en RUNS : chaque run est une liste de
    (horodatage ou None, message).

    Un run commence à `▶ score — bucket R2` et finit à `run score OK` /
    `run score en ÉCHEC` — OU, quand le processus a été tué sans pouvoir
    l'écrire (OOM du 28/08), à `Failed with result`. Les quelques lignes
    de systemd qui suivent (`Consumed …`) sont rattachées au run.

    ⚠️ Les lignes de fin sont DUPLIQUÉES dans journald (`tee` + le
    `systemd-cat` d'`alerter`, sous trois PID) : on ne ferme qu'une fois.
    """
    runs, courant, apres_fin = [], None, 0
    for brut in lignes:
        brut = brut.rstrip("\n")
        ts, msg = None, brut
        m = _TS.match(brut)
        if m:
            ts = datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
            msg = _PREFIXE_JOURNALD.sub("", m.group(2), count=1)
        # Une ligne `dire` de run.sh porte SON horodatage UTC en tête du
        # message (même dans journald, après celui de journald).
        d = _DIRE.match(msg)
        if d:
            if ts is None:
                ts = datetime.fromisoformat(d.group(1).replace("Z", "+00:00"))
            msg = d.group(2)
        if _DEBUT.search(msg):
            if courant:
                runs.append(courant)
            courant, apres_fin = [(ts, msg)], 0
            continue
        if courant is None:
            continue
        if apres_fin:
            courant.append((ts, msg))
            apres_fin += 1
            # ⚠️ 80 et pas 12 : entre la ligne de fin et `Consumed`,
            # `alerter` recopie dans journald les 25 dernières lignes du
            # journal (corps de l'e-mail), sous trois PID. Vu sur les
            # nuits des 13/08, 06/09 et 07/09 : à 12, `Consumed` était
            # perdu et le pic mémoire avec lui.
            if "Consumed" in msg or apres_fin > 80:
                runs.append(courant)
                courant = None
            continue
        courant.append((ts, msg))
        if _FIN_OK.search(msg) or _FIN_KO.search(msg) or _RESULT.search(msg):
            apres_fin = 1
    if courant:
        runs.append(courant)
    return runs


def garde_retro(jour: date) -> int:
    """Le chien de garde qui s'appliquait CETTE nuit-là (voir
    `GARDE_HISTORIQUE`) : une remontée déployée le jour J vaut pour la
    nuit du J+1, pas pour celle qui vient de mourir."""
    g = GARDE_DEFAUT_S
    for depuis, s in GARDE_HISTORIQUE:
        if jour > depuis:
            g = s
    return g


def releve(run, garde_s: int | None = None, source: str = "journald",
           extra: dict | None = None) -> dict | None:
    """Un run découpé → une ligne du registre. Rend `None` si le run n'a
    ni début horodaté ni fin (fragment de journal).

    Tout ce qui n'a pas été LU est absent, jamais mis à zéro : `jalons_mo`
    ne porte que les jalons imprimés, `swap_peak_mo` est absent si
    systemd ne l'a pas dit (les nuits d'avant le 28/08 n'avaient pas de
    swap), `exec_status` est absent sur un OOM (le processus n'a pas
    rendu de code).
    """
    debut = next((ts for ts, m in run if _DEBUT.search(m)), None)
    if debut is None:
        return None
    r: dict = {"source": source}
    jalons, incidents, fin, duree, code, result = {}, [], None, None, None, None
    n_57014 = 0
    for ts, msg in run:
        if "57014" in msg:
            n_57014 += 1
        m = _JALON.search(msg)
        if m:
            jalons[m.group(1).strip()] = int(m.group(2))
        m = _SEUIL.search(msg)
        if m:
            r["seuil_mo"] = int(m.group(1))
        for cle, rx in _ETAPES.items():
            m = rx.search(msg)
            if m:
                if cle == "stabilite":
                    r.setdefault("etapes_s", {})[cle] = float(m.group(1))
                else:
                    r.setdefault("etapes_s", {})[cle] = float(m.group(2))
                    nom = {"glissant": "lignes_glissant", "regime": "lignes_regime",
                           "rejeu": "balise_jours_rejeu"}[cle]
                    r[nom] = int(m.group(1))
        for cle, rx in _LIGNES.items():
            m = rx.search(msg)
            if m:
                r[cle] = int(m.group(1))
        m = _FIN_OK.search(msg)
        if m and fin is None:
            fin, duree, code, result = ts, int(m.group(1)), 0, "success"
        m = _FIN_KO.search(msg)
        if m and fin is None:
            fin, code, duree = ts, int(m.group(1)), int(m.group(2))
            result = "exit-code"
        m = _RESULT.search(msg)
        if m:
            result = m.group(1)
            if fin is None:
                fin = ts
        m = _CONSUMED.search(msg)
        if m:
            cpu = _secondes_systemd(m.group(1))
            if cpu is not None:
                r["cpu_s"] = cpu
            mp = _mo_systemd(m.group(2))
            if mp is not None:
                r["mem_peak_mo"] = mp
            sp = _mo_systemd(m.group(3))
            if sp is not None:
                r["swap_peak_mo"] = sp
        m = _INCIDENT.search(msg)
        if m and m.group(1) not in incidents:
            incidents.append(m.group(1))
    if fin is None:
        return None
    if duree is None and fin is not None:
        duree = int((fin - debut).total_seconds())

    local = debut.astimezone(PARIS)
    r["jour"] = local.strftime("%Y-%m-%d")
    r["debut"] = local.strftime("%H:%M:%S")
    r["fin"] = fin.astimezone(PARIS).strftime("%H:%M:%S")
    r["debut_utc"] = debut.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    r["fin_utc"] = fin.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hm = (debut.astimezone(timezone.utc).hour, debut.astimezone(timezone.utc).minute)
    r["lancement"] = "timer" if TIMER_UTC_DE <= hm <= TIMER_UTC_A else "manuel"
    r["duree_s"] = duree
    if code is not None:
        r["exec_status"] = code
    r["result"] = result or "inconnu"
    r["oom"] = 1 if result == "oom-kill" else 0
    g = garde_s if garde_s is not None else garde_retro(local.date())
    r["garde_s"] = g
    r["marge_s"] = g - duree
    if jalons:
        r["jalons_mo"] = jalons
        etiq = max(jalons, key=jalons.get)
        r["jalon_max_mo"] = jalons[etiq]
        r["jalon_max_etiquette"] = etiq
    if "mem_peak_mo" in r:
        r["mem_peak_go"] = round(r["mem_peak_mo"] / 1024, 2)
    # Le run était-il VIVANT au départ de `bw-model-reduit` ? C'est-à-dire :
    # parti avant 05:00 UTC et fini après, le même jour. Un rejeu à la main
    # de l'après-midi ne croise personne.
    debut_utc, fin_utc = debut.astimezone(timezone.utc), fin.astimezone(timezone.utc)
    reduit = debut_utc.replace(hour=REDUIT_UTC[0], minute=REDUIT_UTC[1],
                               second=0, microsecond=0)
    r["chevauchement_reduit"] = bool(debut_utc <= reduit <= fin_utc)
    r["n_57014"] = n_57014
    r["incidents"] = incidents
    if extra:
        r.update({k: v for k, v in extra.items() if v is not None})
    return r


# ══════════════════════════════════════════════════════════════════════
#  PARTIE E/S
# ══════════════════════════════════════════════════════════════════════
def lire_cgroup() -> dict:
    """Les compteurs du cgroup de CE processus (v2) : pic mémoire, pic de
    swap, CPU. Ce sont exactement ceux que systemd résume en `Consumed`
    à la fin de l'unité — lus AVANT, parce qu'après le cgroup n'existe
    plus. Hors systemd (un `run.sh` à la main, un Mac), le chemin
    n'existe pas et on rend `{}` : absent, pas zéro."""
    out: dict = {}
    try:
        with open("/proc/self/cgroup", encoding="ascii") as f:
            chemin = f.read().strip().split("::", 1)[1]
    except (OSError, IndexError):
        return out
    base = Path("/sys/fs/cgroup") / chemin.lstrip("/")
    for nom, cle in (("memory.peak", "mem_peak_mo"),
                     ("memory.swap.peak", "swap_peak_mo")):
        try:
            out[cle] = round(int((base / nom).read_text()) / 1048576, 1)
        except (OSError, ValueError):
            pass
    try:
        for ligne in (base / "cpu.stat").read_text().splitlines():
            if ligne.startswith("usage_usec "):
                out["cpu_s"] = round(int(ligne.split()[1]) / 1e6, 1)
    except (OSError, ValueError):
        pass
    return out


def pswpout() -> int | None:
    """Pages écrites vers le swap depuis le boot (`/proc/vmstat`). Le
    DELTA entre le départ et la fin d'un run est la seule mesure de swap
    PENDANT la nuit qui ne dépende pas de systemd (dont on n'a que le
    pic). Machine entière, pas le seul run — dit tel quel."""
    try:
        with open("/proc/vmstat", encoding="ascii") as f:
            for ligne in f:
                if ligne.startswith("pswpout "):
                    return int(ligne.split()[1])
    except OSError:
        pass
    return None


def charger(chemin: Path, maxi: int = 400) -> list[dict]:
    """Même contrat que `audit_r2.charger_historique` : une ligne
    corrompue est ignorée, pas fatale."""
    if not chemin.exists():
        return []
    out = []
    for ligne in chemin.read_text(encoding="utf-8").splitlines()[-maxi:]:
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            out.append(json.loads(ligne))
        except (ValueError, TypeError):
            continue
    return out


def ajouter(chemin: Path, lignes: list[dict]) -> int:
    """Ajoute sans relire ce qui y est déjà — SAUF pour ne pas écrire deux
    fois le même run (`debut_utc`), ce qui compte en rétro-remplissage
    joué deux fois. Rend le nombre de lignes écrites."""
    deja = {r.get("debut_utc") for r in charger(chemin, maxi=100000)}
    neuves = [r for r in lignes if r.get("debut_utc") not in deja]
    if not neuves:
        return 0
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("a", encoding="utf-8") as f:
        for r in neuves:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    return len(neuves)


def dernier_run_du_log(chemin: Path) -> list[str]:
    """Les lignes du DERNIER run dans `score.log` (rotation à 20 Mo : le
    dernier run y est toujours entier, `run.sh` rotate AVANT de lancer)."""
    try:
        lignes = chemin.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for i in range(len(lignes) - 1, -1, -1):
        if _DEBUT.search(lignes[i]):
            return lignes[i:]
    return []


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Le registre des nuits de notation.")
    p.add_argument("--out", default=os.environ.get("BW_MODEL_VERIF_ETAT",
                                                   "/var/lib/bw-model-verif"))
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--fin-de-run", action="store_true",
                   help="appelé par run.sh : une ligne pour le run qui s'achève")
    g.add_argument("--retro", action="store_true",
                   help="lit un `journalctl -o short-iso` sur l'entrée standard")
    g.add_argument("--afficher", action="store_true")
    p.add_argument("--log", help="score.log du run (avec --fin-de-run)")
    p.add_argument("--duree", type=int)
    p.add_argument("--code", type=int)
    p.add_argument("--garde-s", type=int)
    p.add_argument("--debut", help="ISO UTC (…Z), départ du run")
    p.add_argument("--fin", help="ISO UTC (…Z), fin du run")
    p.add_argument("--pswpout-depart", type=int,
                   help="valeur de /proc/vmstat pswpout lue au départ")
    p.add_argument("--sans-ecriture", action="store_true",
                   help="imprime la ligne, n'écrit rien")
    a = p.parse_args(argv)
    registre = Path(a.out) / NOM_REGISTRE

    if a.afficher:
        for r in charger(registre):
            print(f"{r.get('jour')}  {r.get('debut')}→{r.get('fin')}  "
                  f"{r.get('duree_s', '?'):>5} s  garde {r.get('garde_s', '?')}  "
                  f"code {r.get('exec_status', '—')}  "
                  f"jalon max {r.get('jalon_max_mo', '—')} Mo  "
                  f"swap {r.get('swap_peak_mo', '—')} Mo  "
                  f"{r.get('lancement', '')}  {' · '.join(r.get('incidents') or [])}")
        return 0

    if a.retro:
        runs = decouper(sys.stdin)
        lignes = [x for x in (releve(run) for run in runs) if x]
        if a.sans_ecriture:
            for r in lignes:
                print(json.dumps(r, ensure_ascii=False, sort_keys=True))
            return 0
        n = ajouter(registre, lignes)
        print(f"registre : {len(lignes)} run(s) lus, {n} ligne(s) ajoutée(s) "
              f"dans {registre}")
        return 0

    # ── --fin-de-run ──
    if not (a.log and a.duree is not None and a.code is not None and a.debut):
        print("--fin-de-run exige --log, --duree, --code, --debut", file=sys.stderr)
        return 2
    lignes = dernier_run_du_log(Path(a.log))
    if not lignes:
        # Pas de journal lisible : on écrit QUAND MÊME une ligne minimale
        # — une nuit sans relevé est un trou dans la pente, et un trou se
        # lit comme un silence.
        lignes = [f"{a.debut} ▶ score — bucket R2 (journal illisible)"]
    fin = a.fin or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if a.code == 0:
        lignes.append(f"{fin} run score OK en {a.duree}s")
    else:
        lignes.append(f"{fin} run score en ÉCHEC (code {a.code}, {a.duree}s) — n consécutif(s)")
    extra = lire_cgroup()
    if a.pswpout_depart is not None:
        maintenant = pswpout()
        if maintenant is not None:
            extra["swap_out_pages"] = max(0, maintenant - a.pswpout_depart)
    run = decouper(lignes)
    r = releve(run[-1], garde_s=a.garde_s, source="run.sh", extra=extra) if run else None
    if r is None:
        print("registre : run illisible, rien écrit", file=sys.stderr)
        return 0
    if a.sans_ecriture:
        print(json.dumps(r, ensure_ascii=False, sort_keys=True))
        return 0
    try:
        n = ajouter(registre, [r])
        print(f"registre : {n} ligne écrite ({r['jour']}, {r['duree_s']} s, "
              f"jalon max {r.get('jalon_max_mo', '—')} Mo, "
              f"swap {r.get('swap_peak_mo', '—')} Mo)")
    except OSError as e:
        print(f"⚠️ registre non écrit ({e}) — la pente de demain aura un trou",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
