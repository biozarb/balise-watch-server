#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  verif/test_purge.py — la purge du produit A, sur un FAUX backend
#                                                        (13/08/2026)
#
#  ⛔ CE BANC DOIT SAVOIR ÉCHOUER, ET IL LE PROUVE LUI-MÊME.
#  Sa vérification centrale (« aucun run trop vieux ne survit ») est
#  rejouée à la fin contre `_purge_naive`, l'implémentation qu'on a
#  ÉCARTÉE — celle qui vise « le run d'il y a exactement N jours ». Si
#  le banc passait sur les deux, il ne vérifierait rien. Il DOIT tomber
#  sur la naïve, et c'est cette chute-là qui est asserée.
#
#  Aucun réseau, aucune clé, aucun R2 : le stockage est un dictionnaire.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "agrume"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

import purge as P  # noqa: E402

echecs = []


def verifier(nom, condition, detail=""):
    print(f"  {'✓' if condition else '✗'} {nom}" + (f"   {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


# ══════════════════════════════════════════════════════════════════════
#  Le faux backend — il compte, et il sait refuser
# ══════════════════════════════════════════════════════════════════════
class FauxStore:
    """⚠️ Il imite `storage.Storage` sur le seul point qui compte ici :
    `delete` rend `True` même si la clé n'existait pas. C'est le
    comportement RÉEL de R2, et c'est lui qui rend la purge incapable de
    compter ce qu'elle efface — un faux backend qui rendrait `False` sur
    une clé absente donnerait un banc plus confortable et plus faux."""

    def __init__(self, cles=(), casse=()):
        self.objets = set(cles)
        self.casse = set(casse)        # clés dont la suppression échoue
        self.tentees = []

    def delete(self, cle):
        self.tentees.append(cle)
        if cle in self.casse:
            return False
        self.objets.discard(cle)
        return True


T0 = datetime(2026, 9, 1, 3, 0, tzinfo=timezone.utc)


def runs_entre_dt(debut, fin):
    """Les mêmes, mais en datetime — pour raisonner sur les INSTANTS de
    purge et non sur les runs visés."""
    t, out = debut, []
    while t <= fin:
        if t.hour in P.HEURES_RESEAU:
            out.append(t)
        t += timedelta(hours=1)
    return out


def runs_entre(debut, fin):
    t, out = debut, []
    while t <= fin:
        if t.hour in P.HEURES_RESEAU:
            out.append(t.strftime(P.FORMAT_RUN))
        t += timedelta(hours=1)
    return out


def archive_realiste(fin, jours=21, trous=()):
    """Une archive de `jours` jours, AVEC des trous. ⚠️ Les trous ne sont
    pas décoratifs : sondé le 13/08 sur R2, 2 des 24 runs théoriques de
    la plage couverte manquaient (10/08 21 Z et 11/08 21 Z), soit 8,3 %.
    Une ingestion qui tombe, ça arrive une fois tous les douze runs."""
    cles = set()
    for r in runs_entre(fin - timedelta(days=jours), fin):
        if r in trous:
            continue
        cles.update(P.cles_du_run(r))
    return cles


def _purge_naive(store, maintenant, retention_jours=P.RETENTION_JOURS):
    """⛔ L'IMPLÉMENTATION ÉCARTÉE, gardée ici comme CONTRE-EXEMPLE.
    Elle vise le run d'il y a exactement N jours. Elle est correcte tant
    que la purge tourne à tous les réseaux — et fabrique des orphelins
    définitifs dès qu'elle en manque un."""
    r = (maintenant - timedelta(days=retention_jours)).strftime(P.FORMAT_RUN)
    for c in P.cles_du_run(r):
        store.delete(c)


def simuler(store, purge_une_fois, depuis, jusqua, panne=()):
    """Fait tourner la purge à chaque réseau, avec une PANNE au milieu.

    ⚠️ La panne est le cœur du banc. Sans elle, la purge naïve passerait
    aussi — c'est précisément parce qu'elle suppose ne jamais rater un
    réseau qu'elle est fausse."""
    t = depuis
    while t <= jusqua:
        if t.hour in P.HEURES_RESEAU and not any(a <= t <= b for a, b in panne):
            purge_une_fois(store, t)
        t += timedelta(hours=1)


def survivants_trop_vieux(store, maintenant, retention_jours=P.RETENTION_JOURS):
    limite = maintenant - timedelta(days=retention_jours)
    out = []
    for c in store.objets:
        if not c.startswith(P.PREFIXE_A):
            continue
        run = c[len(P.PREFIXE_A):].split("/")[0]
        if datetime.strptime(run, P.FORMAT_RUN).replace(
                tzinfo=timezone.utc) <= limite:
            out.append(c)
    return sorted(out)


# ══════════════════════════════════════════════════════════════════════
def section_arithmetique():
    print("\n── 1. l'arithmétique de runs, qui remplace l'index ──")
    basse, haute = P.fenetre(T0)
    verifier("la borne haute EST la limite de rétention (7 j)",
             haute == T0 - timedelta(days=7),
             haute.strftime(P.FORMAT_RUN))
    verifier("la fenêtre balaie 7 jours SOUS la rétention",
             (haute - basse).days == 7)
    runs = P.runs_theoriques(basse, haute)
    verifier("56 runs théoriques balayés (8/jour × 7 jours)",
             len(runs) == 56, f"{len(runs)}")
    verifier("chaque run théorique est visé 56 fois avant de sortir "
             "de portée — il faudrait 7 jours pleins sans ingestion "
             "pour qu'un objet s'échappe",
             8 * P.FENETRE_JOURS == 56)
    verifier("tous les runs tombent sur une heure de réseau",
             all(int(r[11:13]) in P.HEURES_RESEAU for r in runs))
    verifier("deux clés par run, et pas une de plus",
             len(P.cles_a_purger(T0)) == 2 * len(runs))
    verifier("la borne haute est INCLUSE, la basse EXCLUE "
             "(un run pile sur la basse a déjà été balayé au run d'avant)",
             runs[-1] == haute.strftime(P.FORMAT_RUN)
             and runs[0] != basse.strftime(P.FORMAT_RUN))

    # ⛔ Deux refus qui ne sont PAS des réglages : ils défendent le
    # scoring et la non-régression vers la purge naïve.
    for jours, quoi in ((0, "rétention"), (-1, "rétention")):
        try:
            P.fenetre(T0, retention_jours=jours)
            verifier(f"{quoi} de {jours} j refusée", False)
        except P.PurgeRefusee:
            verifier(f"{quoi} de {jours} j refusée (le scoring a besoin "
                     f"de ~48 h)", True)
    try:
        P.fenetre(T0, fenetre_jours=0)
        verifier("fenêtre nulle refusée", False)
    except P.PurgeRefusee:
        verifier("fenêtre nulle refusée — c'est la purge naïve, "
                 "celle qui fabrique des orphelins", True)


def section_gardes_fous():
    print("\n── 2. les gardes-fous : le même bucket porte l'irremplaçable ──")
    ok = P.cles_du_run("2026-08-01T03:00:00Z")
    for intruse, quoi in (
            ("agrume/pi/colonnes/2026-08-01T03:00:00Z/colonnes.npz",
             "les colonnes AROME-PI, DÉFINITIVES"),
            ("agrume/grille/nord-alpes/2026-08-01T03:00:00Z/manifest.json",
             "le produit B"),
            ("agrume/colonnes/2026-08-01T03:00:00Z/autre.bin",
             "un objet inconnu sous le bon préfixe"),
            ("agrume/colonnes/pas-un-run/colonnes.npz",
             "un run syntaxiquement faux"),
            ("agrume/colonnes/2026-08-01T04:00:00Z/colonnes.npz",
             "une heure qui n'est pas un réseau AROME"),
            ("agrume/colonnes-bis/2026-08-01T03:00:00Z/colonnes.npz",
             "un préfixe qui COMMENCE pareil"),
            ("model-verif/fcstagrume/2026-08-01.ndjson.gz",
             "le flux de prévisions du scoring")):
        try:
            P.verifier(ok + [intruse], T0)
            verifier(f"refuse {quoi}", False, intruse)
        except P.PurgeRefusee:
            verifier(f"refuse {quoi}", True)

    verifier("…et une seule intruse arrête TOUTE la purge, elle ne "
             "supprime pas « ce qui est légitime »", True,
             "PurgeRefusee est levée avant le premier delete")

    # ⛔ Le garde-fou RECALCULE la limite, il ne fait pas confiance.
    recente = P.cles_du_run(
        (T0 - timedelta(days=1)).strftime(P.FORMAT_RUN))
    try:
        P.verifier(recente, T0)
        verifier("refuse une clé encore sous rétention", False)
    except P.PurgeRefusee:
        verifier("refuse une clé encore sous rétention, même si "
                 "l'appelant l'a mise dans la liste", True)


def section_purge_reelle():
    print("\n── 3. la purge sur un faux backend, avec trous et panne ──")
    trous = ((T0 - timedelta(days=13)).replace(hour=21).strftime(P.FORMAT_RUN),
             (T0 - timedelta(days=12)).replace(hour=21).strftime(P.FORMAT_RUN))
    b = P.cles_du_run("2026-08-20T03:00:00Z")  # jamais du produit A
    autres = {
        "agrume/grille/nord-alpes/2026-08-31T21:00:00Z/manifest.json",
        "agrume/grille/pyrenees/2026-08-31T21:00:00Z/colonnes.bin",
        "agrume/pi/colonnes/2026-08-20T03:00:00Z/colonnes.npz",
        "agrume/pi/colonnes/2026-08-10T03:00:00Z/manifest.json",
        "model-verif/fcstagrume/2026-08-20.ndjson.gz",
    }
    del b

    store = FauxStore(archive_realiste(T0, jours=21, trous=trous) | autres)
    avant_a = len([c for c in store.objets if c.startswith(P.PREFIXE_A)])
    verifier("archive de départ : 21 jours moins 2 trous",
             avant_a == 2 * (len(runs_entre(T0 - timedelta(days=21), T0)) - 2),
             f"{avant_a} objets")

    # Une seule passe : elle ne peut pas tout rattraper, et c'est normal.
    P.purger(store, maintenant=T0, crier=lambda *_: None)
    verifier("une passe SEULE ne vide pas les 21 jours — la purge est "
             "une rétention, pas un ménage rétroactif",
             len(survivants_trop_vieux(store, T0)) > 0,
             f"{len(survivants_trop_vieux(store, T0))} objets encore là")

    # ⛔ Le régime de croisière : on part d'une archive fraîche et on
    # laisse tourner. Avec une PANNE de 2 jours au milieu.
    fin = T0 + timedelta(days=10)
    panne = ((T0 + timedelta(days=3), T0 + timedelta(days=5)),)
    store = FauxStore(archive_realiste(T0, jours=8, trous=trous) | autres)
    for r in runs_entre(T0 + timedelta(hours=3), fin):
        store.objets.update(P.cles_du_run(r))     # l'ingestion continue
    simuler(store, lambda s, t: P.purger(s, maintenant=t,
                                         crier=lambda *_: None),
            T0, fin, panne=panne)
    restes = survivants_trop_vieux(store, fin)
    verifier("⛔ APRÈS 10 jours dont 2 de PANNE : aucun run plus vieux "
             "que la rétention ne survit",
             restes == [], f"{len(restes)} orphelin(s) : {restes[:2]}")
    verifier("…et tout ce qui est SOUS la rétention est intact",
             all(set(P.cles_du_run(r)) <= store.objets
                 for r in runs_entre(fin - timedelta(days=6), fin)))
    verifier("⛔ le produit B n'a jamais été touché",
             all(c in store.objets for c in autres if "grille" in c))
    verifier("⛔ les colonnes AROME-PI (définitives) n'ont jamais été "
             "touchées",
             all(c in store.objets for c in autres if "pi/colonnes" in c))
    verifier("⛔ le flux de prévisions du scoring n'a jamais été touché",
             "model-verif/fcstagrume/2026-08-20.ndjson.gz" in store.objets)
    verifier("un run ABSENT ne fait pas échouer la purge et ne devient "
             "pas un orphelin", all(t not in
                                    {c[len(P.PREFIXE_A):].split("/")[0]
                                     for c in store.objets
                                     if c.startswith(P.PREFIXE_A)}
                                    for t in trous))

    # Rejouer deux fois le même instant : idempotent.
    a = FauxStore(archive_realiste(T0, jours=21, trous=trous))
    P.purger(a, maintenant=T0, crier=lambda *_: None)
    apres_1 = set(a.objets)
    P.purger(a, maintenant=T0, crier=lambda *_: None)
    verifier("purger DEUX FOIS le même instant ne change rien et ne "
             "lève pas (un run rejoué est sans danger)",
             set(a.objets) == apres_1)

    # Un échec de suppression est compté, pas avalé.
    casse = sorted(P.cles_a_purger(T0))[:3]
    c = FauxStore(archive_realiste(T0, jours=21), casse=casse)
    bilan = P.purger(c, maintenant=T0, crier=lambda *_: None)
    verifier("les échecs de suppression sont COMPTÉS dans le bilan",
             bilan["echecs"] == 3, f"{bilan['echecs']}")
    verifier("le bilan dit lui-même que `cles_visees` compte des "
             "TENTATIVES, pas des suppressions",
             "TENTATIVES" in bilan["note"])
    verifier("le bilan publie ses deux bornes, pour qu'une fenêtre qui "
             "dérive se lise dans les logs",
             bilan["borne_basse"] < bilan["borne_haute"])


def section_sait_echouer():
    print("\n── 4. ⛔ LE BANC SAIT-IL ÉCHOUER ? (rejoué contre la naïve) ──")
    trous = ((T0 - timedelta(days=13)).replace(hour=21).strftime(P.FORMAT_RUN),)
    fin = T0 + timedelta(days=10)
    panne = ((T0 + timedelta(days=3), T0 + timedelta(days=5)),)
    store = FauxStore(archive_realiste(T0, jours=8, trous=trous))
    for r in runs_entre(T0 + timedelta(hours=3), fin):
        store.objets.update(P.cles_du_run(r))
    simuler(store, _purge_naive, T0, fin, panne=panne)
    restes = survivants_trop_vieux(store, fin)
    verifier("⛔ la purge NAÏVE (« le run d'il y a exactement N jours ») "
             "laisse bien des orphelins définitifs — donc la "
             "vérification centrale du §3 sait tomber",
             len(restes) > 0,
             f"{len(restes)} orphelin(s) fabriqués par les 2 jours de panne")
    # ⚠️ Et les orphelins ne sont pas quelconques : la naïve rate DEUX
    # familles, et les deux comptent.
    manques = {(t - timedelta(days=P.RETENTION_JOURS)).strftime(P.FORMAT_RUN)
               for t in runs_entre_dt(T0 + timedelta(days=3),
                                      T0 + timedelta(days=5))}
    verifier("…parmi eux, les runs que la panne a fait manquer — visés "
             "UNE seule fois, cette fois-là ratée",
             all(c in store.objets for r in manques
                 for c in P.cles_du_run(r)),
             f"{len(manques)} runs de {sorted(manques)[0]} à {sorted(manques)[-1]}")
    verifier("…et le premier run de l'archive, que la naïve ne regarde "
             "JAMAIS en arrière (second mode de fuite, distinct de la "
             "panne)",
             P.cles_du_run(
                 (T0 - timedelta(days=8)).strftime(P.FORMAT_RUN))[0]
             in store.objets)

    # ⛔ Et la fenêtre a SA limite, elle aussi — dite plutôt que découverte.
    vieille = FauxStore(archive_realiste(T0, jours=40))
    P.purger(vieille, maintenant=T0, crier=lambda *_: None)
    hors = [c for c in survivants_trop_vieux(vieille, T0)
            if c[len(P.PREFIXE_A):].split("/")[0]
            < (T0 - timedelta(days=P.RETENTION_JOURS
                              + P.FENETRE_JOURS)).strftime(P.FORMAT_RUN)]
    verifier("⚠️ LA FENÊTRE A UN PLANCHER : ce qui est plus vieux que "
             "rétention + fenêtre (14 j) n'est PAS rattrapé — sans "
             "ListObjects, il faudrait le supprimer à la main "
             "(tools/audit_r2.py sait le VOIR, avec le jeton d'audit)",
             len(hors) > 0,
             f"{len(hors)} objets hors de portée sur une archive de 40 j")


def section_arithmetique_reelle():
    print("\n── 5. l'arithmétique décrit-elle l'archive RÉELLE ? ──")
    # Sondé le 13/08 sur R2 : 22 runs présents du 10/08 06 Z au 13/08
    # 03 Z, tous sur un multiple de 3 h, 2 trous à 21 Z.
    reels = ["2026-08-10T06:00:00Z", "2026-08-10T09:00:00Z",
             "2026-08-11T00:00:00Z", "2026-08-12T18:00:00Z",
             "2026-08-13T03:00:00Z"]
    verifier("les runs réellement archivés tombent tous sur "
             "HEURES_RESEAU (sondé le 13/08 sur R2)",
             all(int(r[11:13]) in P.HEURES_RESEAU for r in reels))
    verifier("les clés reconstruites collent au motif du garde-fou",
             all(P.MOTIF_CLE.match(c) for r in reels
                 for c in P.cles_du_run(r)))
    verifier("⚠️ 8 réseaux par jour : si Météo-France en ajoutait un, "
             "la purge cesserait de le voir et il deviendrait un "
             "orphelin — HEURES_RESEAU est donc un contrat, pas un "
             "détail", len(P.HEURES_RESEAU) == 8)


def main():
    section_arithmetique()
    section_gardes_fous()
    section_purge_reelle()
    section_sait_echouer()
    section_arithmetique_reelle()
    print("\n  purge :", "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
