#!/usr/bin/env python3
"""test_sonde_representativite.py — banc du PLANCHER (lot L6).

⛔ CE QUE CE BANC EXISTE POUR ATTRAPER. Une demi-variance rend TOUJOURS
un nombre, et un nombre en km/h a toujours l'air d'un plancher. La
faute qu'on craint n'est donc pas le plantage : c'est un plancher
crédible et faux d'un facteur √2, ou d'un facteur 2, ou pollué par un
doublon d'inscription — publié, cité, et repris dans la lecture des
écarts entre modèles.

La méthode, la seule qui vaille pour un estimateur : des scènes dont on
CONNAÎT la réponse parce qu'on l'a posée.

  A. PLANCHER CONNU     — deux balises = un vent commun + un bruit
                          isotrope d'échelle choisie. La sonde doit
                          retrouver cette échelle-là.
  B. LE √2 EXACT        — un décalage CONSTANT de norme c, aucun bruit :
                          le plancher médian doit valoir c/√2, au bit
                          près. C'est le seul endroit où le facteur du
                          lot est épinglé.
  C. PERSISTANT/FLUCTUANT — décalage constant + bruit : chaque part doit
                          retrouver la sienne, et l'identité de
                          König-Huygens tenir à 1e-9.
  D. SYMÉTRIE A↔B       — échanger les deux balises ne doit RIEN
                          changer. Une demi-fenêtre asymétrique, un
                          seuil de direction appliqué d'un seul côté :
                          tout ça se voit ici et nulle part ailleurs.
  E. LE PAVAGE          — comparé à la force brute en n², sur 40°-55° de
                          latitude. Un pavage à pas fixe rate des paires
                          en montant vers le nord, SANS JAMAIS LE DIRE.
  F. LE DOUBLON         — une balise inscrite deux fois est écartée ; un
                          VRAI voisinage à 20 m ne l'est pas.
  G. LA DÉRIVE          — une paire dont un bout déménage sort entière.
  H. LE PLANCHER D'HEURES — 5 heures communes ne font pas une paire-jour.
  I. LE REPLI SCALAIRE  — sous 5 km/h `pair_error` n'est plus
                          vectorielle : ces heures ne doivent pas entrer
                          dans le partage persistant/fluctuant.
  J. L'IC PAR BLOCS     — moins de 8 jours ⇒ pas d'intervalle, et le
                          rapport doit le DIRE (`window_too_short`).

⛔ ET LES SCÈNES SONT IRRÉGULIÈRES DANS LA DIMENSION TESTÉE (piège nº 2
de la phase B, 26/08) : le nombre de paires change d'un jour à l'autre,
les heures manquantes ne sont pas les mêmes partout, les vents ne sont
pas du même ordre, et certaines paires ne vivent que la moitié de la
fenêtre. Un jeu régulier laisserait passer « le plancher est la moyenne
des planchers journaliers », qui est faux.

Aucun `random` : `scoring._XorShift`, la graine de la maison, explicite.

    python3 test_sonde_representativite.py
"""
from __future__ import annotations

import math
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import inference as INF
import scoring as S
import sonde_representativite as SR

OK = 0
KO = 0


def check(label: str, cond: bool, detail: str = ""):
    global OK, KO
    if cond:
        OK += 1
    else:
        KO += 1
        print(f"  ❌ {label}" + (f"\n       {detail}" if detail else ""))


def proche(a, b, tol):
    return a is not None and b is not None and abs(a - b) <= tol


# ══════════════════════════════════════════════════════════════════
#  FABRIQUE DE JOURNÉES — des archives qu'on a écrites soi-même
# ══════════════════════════════════════════════════════════════════

JOUR0 = datetime(2026, 7, 1)


def jour_ms(d: datetime) -> int:
    return int(d.replace(tzinfo=timezone.utc).timestamp()) * 1000


def ligne(source, sid, lat, lon, d, heures, uv):
    """Une ligne d'archive obs, au format que `score.to_obs_samples` lit."""
    base = jour_ms(d) // 1000
    return {
        "source": source, "station_id": sid, "lat": lat, "lon": lon,
        "t": [base + h * 3600 for h in heures],
        # ⚠️ AUCUN ARRONDI ICI, alors que les vraies archives arrondissent
        # au dixième : la scène B épingle le facteur √2 à 1e-12, et un
        # arrondi de scène rendrait cette assertion impossible à écrire.
        # L'arrondi de production est une question de FIDÉLITÉ des
        # chiffres, pas de justesse de l'estimateur — et c'est
        # l'estimateur qu'on teste ici.
        "speed": [math.hypot(u, v) for u, v in uv],
        "dir": [S.from_uv(u, v) for u, v in uv],
    }


class Bruit:
    """Bruit isotrope d'échelle connue, tiré sans `random`.

    Chaque composante est uniforme sur [-h, +h], donc d'écart-type
    s = h/√3. Pour DEUX balises indépendantes,
    E‖Δ‖² = 2·(2s²) = 4s², et le plancher attendu vaut √(½·4s²) = s√2.
    """

    def __init__(self, h: float, graine: int = 0x5EED_1234):
        self.h = h
        self.r = S._XorShift(graine)
        self.s = h / math.sqrt(3.0)
        self.attendu = self.s * math.sqrt(2.0)

    def uv(self):
        return ((self.r.next() * 2 - 1) * self.h,
                (self.r.next() * 2 - 1) * self.h)


def vent_de_fond(d: datetime, h: int, k: int):
    """Un vent commun qui bouge — jamais deux jours pareils.

    ⚠️ IRRÉGULIER À DESSEIN : la force va de 12 à 26 km/h et la
    direction tourne. Un vent constant laisserait passer un estimateur
    qui confondrait « écart entre balises » et « variabilité du vent ».
    """
    force = 12.0 + 7.0 * (1 + math.sin(0.7 * h + 0.9 * k))
    cap = (35 * k + 13 * h) % 360
    return S.to_uv(force, cap)


def heures_du_jour(k: int, sid: int) -> list[int]:
    """Des heures présentes qui ne sont pas les mêmes partout."""
    trous = {(k + sid) % 24, (3 * k + 2 * sid) % 24, (5 * sid + k) % 24}
    return [h for h in range(24) if h not in trous]


def joue(lignes_par_jour: dict, fin: datetime, jours: int, **kw):
    """Fait tourner la sonde sur des journées fabriquées."""
    return SR.sonder(pathlib.Path("/inexistant"), fin, jours,
                     lecteur=lambda d: lignes_par_jour.get(
                         d.strftime("%Y-%m-%d"), []),
                     crier=lambda *_a, **_k: None, **kw)


# ══════════════════════════════════════════════════════════════════
#  A. LE PLANCHER CONNU — on pose σ, la sonde doit le retrouver
# ══════════════════════════════════════════════════════════════════

def scene_bruit(n_jours: int, h_bruit: float, offset=(0.0, 0.0),
                force_fixe=None, graine=0x5EED_1234):
    """Huit voisinages, un vent commun, un bruit d'échelle CHOISIE."""
    br = Bruit(h_bruit, graine)
    par_jour: dict = {}
    for k in range(n_jours):
        d = JOUR0 + timedelta(days=k)
        rows = []
        for i in range(8):
            # ⚠️ irrégularité : les deux derniers voisinages ne vivent
            # qu'un jour sur deux. Une paire absente ne doit pas
            # déplacer le plancher des autres.
            if i >= 6 and k % 2:
                continue
            lat = 45.0 + 0.1 * i
            dlon = 0.004 * (i + 1)
            ha = heures_du_jour(k, 2 * i)
            hb = heures_du_jour(k, 2 * i + 1)
            communes = sorted(set(ha) & set(hb))
            uva, uvb = [], []
            for hh in communes:
                u0, v0 = vent_de_fond(d, hh, k + i)
                if force_fixe is not None:
                    # ⚠️ Ramener le vent de fond à une force CHOISIE —
                    # la scène I en a besoin pour passer sous
                    # DIR_MIN_WIND_KMH. Ailleurs on garde les 12-26 km/h
                    # irréguliers du vent de fond.
                    n = math.hypot(u0, v0)
                    u0, v0 = u0 * force_fixe / n, v0 * force_fixe / n
                au, av = br.uv()
                bu, bv = br.uv()
                uva.append((u0 + au, v0 + av))
                uvb.append((u0 + bu + offset[0], v0 + bv + offset[1]))
            rows.append(ligne("res", f"a{i}", lat, 6.0, d, communes, uva))
            rows.append(ligne("res", f"b{i}", lat, 6.0 + dlon, d, communes, uvb))
        par_jour[d.strftime("%Y-%m-%d")] = rows
    return par_jour, br


def test_a_plancher_connu():
    par_jour, br = scene_bruit(12, 2.4)
    r = joue(par_jour, JOUR0 + timedelta(days=11), 12)
    g = r["rayons"]["< 3.0 km"]["tous"]
    check("A · toutes les paires vues", g is not None and g["n_paires"] == 8,
          f"n_paires={None if not g else g['n_paires']}")
    check("A · le plancher quadratique retrouve l'échelle posée",
          proche(g["plancher_quad"], br.attendu, 0.06 * br.attendu),
          f"attendu {br.attendu:.4f}, rendu {g['plancher_quad']}")
    check("A · le plancher rms est du même ordre",
          proche(g["plancher_rms"], br.attendu, 0.15 * br.attendu),
          f"attendu ~{br.attendu:.4f}, rendu {g['plancher_rms']}")
    # ⛔ Et ce ne sont pas deux fois le même nombre : sur une
    # distribution étalée, la médiane est strictement sous la moyenne
    # quadratique. Deux colonnes égales trahiraient une agrégation qui
    # empile la même liste deux fois.
    check("A · médiane et rms sont deux nombres DIFFÉRENTS",
          g["plancher_med"] < g["plancher_rms"],
          f"med={g['plancher_med']} rms={g['plancher_rms']}")
    check("A · toutes les heures sont vectorielles",
          g["part_vectorielle"] == 1.0, f"{g['part_vectorielle']}")
    check("A · aucun doublon inventé",
          not r["exclusions"]["paires_doublon"],
          str(r["exclusions"]["paires_doublon"]))
    # ⛔ LE PIÈGE DU FACTEUR 2 : sans le ½, la sonde rendrait √2 fois
    # plus. L'assertion ci-dessus le voit ; celle-ci le NOMME.
    check("A · ce n'est PAS l'écart entre balises (facteur √2)",
          not proche(g["plancher_quad"], br.attendu * math.sqrt(2),
                     0.06 * br.attendu),
          f"rendu {g['plancher_quad']}")


# ══════════════════════════════════════════════════════════════════
#  B. LE √2, ÉPINGLÉ — un décalage constant, aucun bruit
# ══════════════════════════════════════════════════════════════════

def test_b_racine_de_deux():
    c = (2.0, 1.5)                       # norme exactement 2,5
    norme = math.hypot(*c)
    par_jour: dict = {}
    for k in range(10):
        d = JOUR0 + timedelta(days=k)
        heures = heures_du_jour(k, 0)
        uva, uvb = [], []
        for hh in heures:
            u0, v0 = vent_de_fond(d, hh, k)
            uva.append((u0, v0))
            uvb.append((u0 + c[0], v0 + c[1]))
        par_jour[d.strftime("%Y-%m-%d")] = [
            ligne("res", "a", 45.0, 6.0, d, heures, uva),
            ligne("res", "b", 45.0, 6.006, d, heures, uvb),
        ]
    r = joue(par_jour, JOUR0 + timedelta(days=9), 10)
    g = r["rayons"]["< 3.0 km"]["tous"]
    check("B · plancher médian = ‖décalage‖ / √2, exactement",
          proche(g["plancher_med"], norme / math.sqrt(2), 1e-9),
          f"attendu {norme / math.sqrt(2)!r}, rendu {g['plancher_med']!r}")
    check("B · plancher quadratique identique (écart constant)",
          proche(g["plancher_quad"], norme / math.sqrt(2), 1e-9),
          f"rendu {g['plancher_quad']!r}")
    check("B · TOUT est persistant",
          proche(g["plancher_persistant"], norme / math.sqrt(2), 1e-9),
          f"rendu {g['plancher_persistant']!r}")
    # ⚠️ 1e-6 et pas 1e-9 ICI, et c'est mesuré : l'aller-retour
    # (u,v) → (force, direction en DEGRÉS) → (u,v) que traverse toute
    # observation coûte ~3e-8 km/h de flottant. Le signal de cette
    # scène vaut 1,77 : la tolérance reste cinq ordres de grandeur
    # sous lui. Serrer davantage testerait la précision de `math`,
    # pas la sonde.
    check("B · rien ne fluctue",
          proche(g["plancher_fluctuant"], 0.0, 1e-6),
          f"rendu {g['plancher_fluctuant']!r}")
    check("B · l'identité de König-Huygens tient",
          proche(g["residu_identite"], 0.0, 1e-9),
          f"résidu {g['residu_identite']!r}")


# ══════════════════════════════════════════════════════════════════
#  C. LE PARTAGE — chaque part doit retrouver la sienne
# ══════════════════════════════════════════════════════════════════

def test_c_persistant_fluctuant():
    c = (2.0, 1.5)
    norme = math.hypot(*c)
    par_jour, br = scene_bruit(12, 2.4, offset=c, graine=0xA11CE)
    r = joue(par_jour, JOUR0 + timedelta(days=11), 12)
    g = r["rayons"]["< 3.0 km"]["tous"]
    check("C · la part PERSISTANTE retrouve le décalage posé",
          proche(g["plancher_persistant"], norme / math.sqrt(2),
                 0.06 * norme / math.sqrt(2)),
          f"attendu {norme / math.sqrt(2):.4f}, "
          f"rendu {g['plancher_persistant']}")
    check("C · la part FLUCTUANTE retrouve le bruit posé",
          proche(g["plancher_fluctuant"], br.attendu, 0.08 * br.attendu),
          f"attendu {br.attendu:.4f}, rendu {g['plancher_fluctuant']}")
    check("C · l'identité tient malgré les deux parts",
          proche(g["residu_identite"], 0.0, 1e-9),
          f"résidu {g['residu_identite']!r}")
    check("C · et le total dépasse chacune des parts",
          g["plancher_quad"] > max(g["plancher_persistant"],
                                   g["plancher_fluctuant"]))
    # ⛔ La faute qu'on craint : un partage calculé JOUR PAR JOUR
    # noierait le persistant dans le fluctuant. Il doit rester debout.
    check("C · le persistant n'est pas noyé (≥ 80 % de sa valeur)",
          g["plancher_persistant"] >= 0.8 * norme / math.sqrt(2),
          f"rendu {g['plancher_persistant']}")


# ══════════════════════════════════════════════════════════════════
#  D. LA SYMÉTRIE — échanger A et B ne doit rien changer
# ══════════════════════════════════════════════════════════════════

def _ligne_deux_relevés(source, sid, lat, lon, d, heures, uv_00, uv_15):
    """Une balise qui relève DEUX fois par heure — à l'heure et à :15.

    ⚠️ C'est ce qui rend la demi-fenêtre observable. Avec un seul relevé
    posé pile à l'heure ronde, ±20 min et ±10 min contiennent la MÊME
    chose, et une demi-fenêtre asymétrique passerait inaperçue.
    """
    base = jour_ms(d) // 1000
    ts, sp, di = [], [], []
    for i, h in enumerate(heures):
        for dt, (u, v) in ((0, uv_00[i]), (900, uv_15[i])):
            ts.append(base + h * 3600 + dt)
            sp.append(math.hypot(u, v))
            di.append(S.from_uv(u, v))
    return {"source": source, "station_id": sid, "lat": lat, "lon": lon,
            "t": ts, "speed": sp, "dir": di}


def test_d_symetrie():
    br = Bruit(2.0, 0xD1CE)
    d = JOUR0
    heures_a = [h for h in range(24) if h not in (3, 11)]
    heures_b = [h for h in range(24) if h not in (11, 19, 20)]
    communes = sorted(set(heures_a) & set(heures_b))

    def uv(h, sel):
        # ⚠️ Une heure sur trois est FAIBLE (3 km/h) : sous
        # DIR_MIN_WIND_KMH, `mean_wind` jette la direction et
        # `pair_error` retombe sur |Δforce|. Un seuil appliqué d'un
        # seul côté se verrait ici, et seulement ici.
        u0, v0 = vent_de_fond(d, h, 0)
        if h % 3 == 0:
            n = math.hypot(u0, v0)
            u0, v0 = u0 * 3.0 / n, v0 * 3.0 / n
        du, dv = br.uv()
        # `sel` décale le second relevé de l'heure : les deux relevés
        # d'une même heure ne sont PAS égaux, sinon la moyenne de
        # fenêtre ne changerait rien.
        return (u0 + du + sel * 0.7, v0 + dv - sel * 0.4)

    la = _ligne_deux_relevés("res", "a", 45.0, 6.0, d, heures_a,
                             [uv(h, 0) for h in heures_a],
                             [uv(h, 1) for h in heures_a])
    lb = _ligne_deux_relevés("res", "b", 45.0, 6.006, d, heures_b,
                             [uv(h, 2) for h in heures_b],
                             [uv(h, 3) for h in heures_b])
    import score as SC
    oa, ob = SC.to_obs_samples(la), SC.to_obs_samples(lb)
    se_ab, uv_ab = SR.ecarts_paire_jour(oa, ob, jour_ms(d))
    se_ba, uv_ba = SR.ecarts_paire_jour(ob, oa, jour_ms(d))
    check("D · même nombre d'heures communes dans les deux sens",
          se_ab.n == se_ba.n == len(communes),
          f"{se_ab.n} / {se_ba.n} / attendu {len(communes)}")
    check("D · même médiane au bit près",
          se_ab.med == se_ba.med, f"{se_ab.med!r} vs {se_ba.med!r}")
    check("D · même rms au bit près",
          se_ab.rms == se_ba.rms, f"{se_ab.rms!r} vs {se_ba.rms!r}")
    check("D · même part vectorielle, et elle n'est ni 0 ni 1",
          se_ab.vector_ratio == se_ba.vector_ratio
          and 0.0 < se_ab.vector_ratio < 1.0,
          f"{se_ab.vector_ratio}")
    check("D · les écarts vectoriels sont opposés, pas différents",
          len(uv_ab) == len(uv_ba) and len(uv_ab) > 0
          and all(proche(x[0], -y[0], 1e-9) and proche(x[1], -y[1], 1e-9)
                  for x, y in zip(uv_ab, uv_ba)))
    # ⛔ Et la fenêtre de ±20 min doit avoir SERVI : si les deux relevés
    # d'une heure n'étaient pas moyennés, l'écart changerait.
    court, _uv = SR.ecarts_paire_jour(oa, ob, jour_ms(d))
    demi = SR.serie_horaire(oa, jour_ms(d), demi_fenetre_ms=5 * 60 * 1000)
    check("D · la demi-fenêtre de 20 min moyenne bien DEUX relevés",
          any(a != b for a, b in zip(demi[1], SR.serie_horaire(
              oa, jour_ms(d))[1]) if a is not None and b is not None))


# ══════════════════════════════════════════════════════════════════
#  E. LE PAVAGE — contre la force brute, sur 15° de latitude
# ══════════════════════════════════════════════════════════════════

def test_e_pavage():
    r = S._XorShift(0xBEEF_2026)
    pos = {}
    for i in range(400):
        # ⚠️ DE 40° À 55° : c'est là que se joue le pavage. Un pas fixe
        # en longitude rétrécit en kilomètres quand on monte vers le
        # nord, et se met à rater des paires — sans jamais le dire.
        lat = 40.0 + r.next() * 15.0
        lon = -2.0 + r.next() * 12.0
        pos[f"n{i}:s{i}"] = (lat, lon)
    # … et des grappes serrées, sinon presque aucune paire n'existe.
    for j in range(60):
        base = pos[f"n{j}:s{j}"]
        for m in range(3):
            pos[f"g{j}:{m}"] = (base[0] + 0.004 * (m + 1),
                                base[1] + 0.006 * (m + 1))
    # ⛔ ET DES VOISINAGES ÉTIRÉS EN LONGITUDE, DÉLIBÉRÉMENT. C'est la
    # seule direction où un pavage à pas fixe se trompe : un demi-degré
    # de longitude ne fait pas la même distance à 40° et à 55°. Des
    # grappes obliques, comme celles du dessus, ne le montreraient
    # jamais — elles ont toujours de quoi tomber dans la bonne case par
    # la latitude. Les écarts choisis (0,008° à 0,032°) valent 0,5 à
    # 2,7 km selon la latitude : ils enjambent les trois rayons testés.
    for j in range(60):
        base = pos[f"n{j}:s{j}"]
        for m in range(4):
            pos[f"e{j}:{m}"] = (base[0], base[1] + 0.008 * (m + 1))
    for rayon in (0.5, 1.5, 3.0):
        brut = set()
        cles = sorted(pos)
        for i, a in enumerate(cles):
            for b in cles[i + 1:]:
                if SR.distance_km(*pos[a], *pos[b]) <= rayon:
                    brut.add((a, b) if a < b else (b, a))
        pave = {(a, b) for a, b, _d in SR.paires_proches(pos, rayon)}
        check(f"E · pavage exact à {rayon} km", pave == brut,
              f"ratées {sorted(brut - pave)[:4]} · "
              f"inventées {sorted(pave - brut)[:4]}")


# ══════════════════════════════════════════════════════════════════
#  F. LE DOUBLON — et le VRAI voisinage qu'il ne faut pas jeter
# ══════════════════════════════════════════════════════════════════

def _paire_simple(sid_a, sid_b, lat_b, lon_b, n_jours, decale=None,
                  source_b="res"):
    br = Bruit(2.0, 0xF00D)
    par_jour = {}
    for k in range(n_jours):
        d = JOUR0 + timedelta(days=k)
        heures = heures_du_jour(k, 0)
        uva, uvb = [], []
        for hh in heures:
            u0, v0 = vent_de_fond(d, hh, k)
            uva.append((u0, v0))
            if decale is None:
                uvb.append((u0, v0))              # série IDENTIQUE
            else:
                bu, bv = br.uv()
                uvb.append((u0 + bu + decale[0], v0 + bv + decale[1]))
        par_jour[d.strftime("%Y-%m-%d")] = [
            ligne("res", sid_a, 45.0, 6.0, d, heures, uva),
            ligne(source_b, sid_b, lat_b, lon_b, d, heures, uvb),
        ]
    return par_jour


def test_f_doublon():
    # deux identifiants, un seul capteur : même point, série identique
    par_jour = _paire_simple("a", "bis", 45.0, 6.00025, 10)
    r = joue(par_jour, JOUR0 + timedelta(days=9), 10)
    check("F · le doublon est reconnu",
          len(r["exclusions"]["paires_doublon"]) == 1,
          str(r["exclusions"]))
    check("F · et il ne laisse aucun plancher derrière lui",
          r["rayons"]["< 3.0 km"]["tous"] is None)

    # un VRAI voisinage à ~20 m : même distance, mais du bruit
    par_jour = _paire_simple("a", "b", 45.0, 6.00025, 10, decale=(0.0, 0.0))
    r = joue(par_jour, JOUR0 + timedelta(days=9), 10)
    check("F · un vrai voisinage à 20 m N'EST PAS jeté",
          not r["exclusions"]["paires_doublon"], str(r["exclusions"]))
    check("F · mais il va au SOCLE, pas au plancher spatial",
          r["socle"] is not None and r["socle"]["n_paires"] == 1
          and r["rayons"]["< 3.0 km"]["tous"] is None,
          f"socle={None if not r['socle'] else r['socle']['n_paires']} "
          f"spatial={r['rayons']['< 3.0 km']['tous']}")


# ══════════════════════════════════════════════════════════════════
#  G. LA DÉRIVE — une balise qui déménage emporte sa paire
# ══════════════════════════════════════════════════════════════════

def test_g_derive():
    par_jour = _paire_simple("a", "b", 45.0, 6.008, 10, decale=(0.5, -0.3))
    # au 6ᵉ jour, `b` déménage de ~0,4 km : la paire n'a plus de distance
    cle = (JOUR0 + timedelta(days=6)).strftime("%Y-%m-%d")
    for row in par_jour[cle]:
        if row["station_id"] == "b":
            row["lon"] = 6.013
    r = joue(par_jour, JOUR0 + timedelta(days=9), 10)
    check("G · la paire déménageuse sort entière",
          len(r["exclusions"]["paires_deriveuses"]) == 1
          and r["rayons"]["< 3.0 km"]["tous"] is None,
          str(r["exclusions"]))
    check("G · et la balise mobile est comptée",
          r["exclusions"]["balises_deplacees"] == 1,
          str(r["exclusions"]["balises_deplacees"]))


# ══════════════════════════════════════════════════════════════════
#  H. LE PLANCHER D'HEURES — 5 heures ne font pas une paire-jour
# ══════════════════════════════════════════════════════════════════

def _paire_heures(heures_par_jour: list):
    br = Bruit(2.0, 0x1234_5678)
    par_jour = {}
    for k, heures in enumerate(heures_par_jour):
        d = JOUR0 + timedelta(days=k)
        uva, uvb = [], []
        for hh in heures:
            u0, v0 = vent_de_fond(d, hh, k)
            au, av = br.uv()
            bu, bv = br.uv()
            uva.append((u0 + au, v0 + av))
            uvb.append((u0 + bu, v0 + bv))
        par_jour[d.strftime("%Y-%m-%d")] = [
            ligne("res", "a", 45.0, 6.0, d, heures, uva),
            ligne("res", "b", 45.0, 6.008, d, heures, uvb),
        ]
    return par_jour


def test_h_plancher_heures():
    jours = [list(range(20))] * 10
    jours[3] = list(range(5))          # 5 heures : sous le seuil
    jours[7] = list(range(6))          # 6 heures : juste au-dessus
    r = joue(_paire_heures(jours), JOUR0 + timedelta(days=9), 10)
    g = r["rayons"]["< 3.0 km"]["tous"]
    check("H · la journée de 5 heures est tombée, celle de 6 est restée",
          g["n_paire_jours"] == 9 and g["n_jours"] == 9,
          f"paire-jours={g['n_paire_jours']} jours={g['n_jours']}")
    check("H · SR.MIN_HEURES_PAIRE_JOUR vaut bien 6",
          SR.MIN_HEURES_PAIRE_JOUR == 6, str(SR.MIN_HEURES_PAIRE_JOUR))


# ══════════════════════════════════════════════════════════════════
#  I. LE REPLI SCALAIRE — sous 5 km/h il n'y a plus de vecteur
# ══════════════════════════════════════════════════════════════════

def test_i_repli_scalaire():
    par_jour, _br = scene_bruit(10, 0.4, force_fixe=3.0, graine=0x5CA1)
    r = joue(par_jour, JOUR0 + timedelta(days=9), 10)
    g = r["rayons"]["< 3.0 km"]["tous"]
    check("I · aucune heure n'est vectorielle sous le seuil",
          g["part_vectorielle"] == 0.0, f"{g['part_vectorielle']}")
    check("I · le partage persistant/fluctuant se TAIT au lieu d'inventer",
          g["plancher_quad"] is None and g["plancher_persistant"] is None
          and g["n_heures_uv"] == 0,
          f"quad={g['plancher_quad']} n_uv={g['n_heures_uv']}")
    check("I · mais le plancher médian existe (repli |Δforce|)",
          g["plancher_med"] is not None and g["plancher_med"] > 0,
          f"{g['plancher_med']}")


# ══════════════════════════════════════════════════════════════════
#  J. L'INTERVALLE EST TIRÉ PAR BLOCS DE JOURS, ET LE DIT
# ══════════════════════════════════════════════════════════════════

def test_j_intervalle():
    court, _ = scene_bruit(5, 2.4, graine=0x0C0C)
    r = joue(court, JOUR0 + timedelta(days=4), 5)
    g = r["rayons"]["< 3.0 km"]["tous"]
    check("J · 5 jours : pas d'intervalle, et la RAISON est publiée",
          g["plancher_med_bas"] is None
          and g["ci_raison"] == "window_too_short",
          f"{g['ci_raison']} {g['plancher_med_bas']}")
    check("J · mais le plancher, lui, est rendu",
          g["plancher_med"] is not None)

    long_, _ = scene_bruit(14, 2.4, graine=0x0C0D)
    r = joue(long_, JOUR0 + timedelta(days=13), 14)
    g = r["rayons"]["< 3.0 km"]["tous"]
    check("J · 14 jours : intervalle rendu, et il encadre le plancher",
          g["ci_raison"] == "ok" and g["plancher_med_bas"] is not None
          and g["plancher_med_bas"] <= g["plancher_med"]
          <= g["plancher_med_haut"],
          f"{g['ci_raison']} [{g['plancher_med_bas']} ; "
          f"{g['plancher_med_haut']}] méd {g['plancher_med']}")
    check("J · la longueur de bloc est celle d'`inference`",
          g["block_days"] == INF.block_length(g["n_jours"]),
          f"{g['block_days']} vs {INF.block_length(g['n_jours'])}")


# ══════════════════════════════════════════════════════════════════
#  K. LES AXES — terrain, dénivelé, réseau
# ══════════════════════════════════════════════════════════════════

def test_k_axes():
    par_jour, _ = scene_bruit(12, 2.4, graine=0x0A2E)
    zones = {}
    for i in range(8):
        # a0/b0 … a3/b3 : même classe des deux côtés ; a4/b4 … : mixtes.
        forme = ("ridge", "valley", "plain", "slope")[i % 4]
        zones[f"res:a{i}"] = {"landform": forme, "alt": 1000.0}
        zones[f"res:b{i}"] = {
            "landform": forme if i < 4 else "plain",
            "alt": 1000.0 + (20.0 if i < 4 else 300.0)}
    r = joue(par_jour, JOUR0 + timedelta(days=11), 12, zones=zones)
    check("K · les quatre classes pures sont là, plus « mixte »",
          set(r["terrain"]) >= {"ridge", "valley", "plain", "slope"},
          str(sorted(r["terrain"])))
    check("K · une paire dont les deux bouts diffèrent est « mixte », "
          "pas jetée",
          r["terrain"].get("mixte") is not None
          and r["terrain"]["mixte"]["n_paires"] == 3,
          str({k: (v or {}).get("n_paires") for k, v in r["terrain"].items()}))
    check("K · les bandes de dénivelé séparent les mêmes paires",
          (r["denivele"]["< 50 m"]["n_paires"] == 4
           and r["denivele"]["≥ 150 m"]["n_paires"] == 4),
          str({k: (v or {}).get("n_paires")
               for k, v in r["denivele"].items()}))
    check("K · tout est intra-réseau ici, donc inter-réseaux est vide",
          r["rayons"]["< 3.0 km"]["inter_reseaux"] is None)
    check("K · sans `station_zone`, la classe est « ? » et rien ne casse",
          joue(par_jour, JOUR0 + timedelta(days=11), 12)["terrain"]
          .get("?") is not None)


def test_k2_inter_reseaux():
    par_jour = _paire_simple("a", "b", 45.0, 6.008, 12, decale=(0.4, 0.2),
                             source_b="autre")
    r = joue(par_jour, JOUR0 + timedelta(days=11), 12)
    check("K2 · une paire de deux réseaux est comptée inter-réseaux",
          r["rayons"]["< 3.0 km"]["inter_reseaux"] is not None
          and r["rayons"]["< 3.0 km"]["intra_reseau"] is None,
          str({k: bool(v) for k, v in r["rayons"]["< 3.0 km"].items()}))
    check("K2 · et le couple de réseaux est nommé dans les deux sens "
          "de la même façon",
          list(r["reseaux"]) == [] or "autre ↔ res" in r["reseaux"],
          str(list(r["reseaux"])))


# ══════════════════════════════════════════════════════════════════
#  L. LE RAPPORT — il doit se lire, et dire ce qu'il ne sait pas
# ══════════════════════════════════════════════════════════════════

def test_l_rapport():
    par_jour, br = scene_bruit(12, 2.4, graine=0x11FE)
    r = joue(par_jour, JOUR0 + timedelta(days=11), 12)
    txt = SR.rapport(r, {"jour": "2026-08-26", "lead_h": 6, "n_lignes": 4242,
                         "err_vec_med": 4.2, "err_vec_rms": 5.6,
                         "par_source": {}})
    for attendu in ("MINORANT", "MAJORANT", "fluctuant", "15 % ⇒", "identité"):
        check(f"L · le rapport porte « {attendu} »", attendu in txt)
    check("L · et il amplifie l'écart au lieu de l'atténuer "
          "(colonne « 15 % ⇒ » > 15 %)",
          any(float(l.rsplit("%", 2)[-2].split()[-1]) > 15.0
              for l in txt.splitlines() if "toutes paires" in l),
          "\n".join(l for l in txt.splitlines() if "toutes paires" in l))
    check("L · les deux échelles sont SÉPARÉES (médiane / quadratique)",
          "face à `err_vec_med`" in txt and "face à `err_vec_rms`" in txt)
    sans = SR.rapport(r, {})
    check("L · sans erreur typique, le rapport ne fabrique pas de lecture",
          "CE QUE ÇA CHANGE" not in sans)

    # ── la comparaison CLASSE PAR CLASSE, et son garde-fou ──────────
    zones = {}
    for i in range(8):
        f_ = ("ridge", "valley", "plain", "slope")[i % 4]
        zones[f"res:a{i}"] = {"landform": f_, "alt": 1000.0}
        zones[f"res:b{i}"] = {"landform": f_, "alt": 1010.0}
    rz = joue(par_jour, JOUR0 + timedelta(days=11), 12, zones=zones)
    txt = SR.rapport(rz, {
        "jour": "2026-08-26", "lead_h": 6, "n_lignes": 4242,
        "err_vec_med": 4.2, "err_vec_rms": 5.6, "par_source": {},
        # `valley` reçoit une erreur SOUS le plancher : le rapport doit
        # écrire IMPOSSIBLE au lieu d'une racine de nombre négatif.
        "par_landform": {"ridge": {"n": 10, "med": 4.9},
                         "valley": {"n": 10, "med": 0.4},
                         "plain": {"n": 10, "med": 3.8},
                         "slope": {"n": 10, "med": 4.1}}})
    check("L · la table classe-par-classe est écrite",
          "CLASSE PAR CLASSE" in txt and "err_vec_med" in txt)
    check("L · et une erreur SOUS le plancher rend « IMPOSSIBLE », "
          "pas une racine de nombre négatif",
          any("vallée" in l and "IMPOSSIBLE" in l
              for l in txt.splitlines()),
          "\n".join(l for l in txt.splitlines() if "vallée" in l))


# ══════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════
#  N. LA PARTITION À 100 m — deux populations qui ne se mélangent pas
# ══════════════════════════════════════════════════════════════════

def _deux_paires(lon_proche, lon_loin, n_jours=10, network=None):
    br = Bruit(2.0, 0x0FF5)
    par_jour = {}
    for k in range(n_jours):
        d = JOUR0 + timedelta(days=k)
        heures = heures_du_jour(k, 0)
        série = {}
        for nom in ("a", "b", "c", "e"):
            uv = []
            for hh in heures:
                u0, v0 = vent_de_fond(d, hh, k)
                du, dv = br.uv()
                uv.append((u0 + du, v0 + dv))
            série[nom] = uv
        rows = [
            ligne("res", "a", 45.0, 6.0, d, heures, série["a"]),
            ligne("res", "b", 45.0, lon_proche, d, heures, série["b"]),
            ligne("res", "c", 46.0, 6.0, d, heures, série["c"]),
            ligne("res", "e", 46.0, lon_loin, d, heures, série["e"]),
        ]
        if network:
            for row in rows:
                if row["station_id"] in network:
                    row["network"] = network[row["station_id"]]
        par_jour[d.strftime("%Y-%m-%d")] = rows
    return par_jour


def test_n_partition():
    # a↔b à ~40 m (co-implantées) ; c↔e à ~1,6 km (plancher spatial)
    r = joue(_deux_paires(6.0005, 6.021), JOUR0 + timedelta(days=9), 10)
    check("N · la paire à 40 m va au socle et NULLE PART ailleurs",
          r["socle"]["n_paires"] == 1
          and r["rayons"]["< 3.0 km"]["tous"]["n_paires"] == 1
          and r["profil"]["1.5–2.2 km"]["n_paires"] == 1,
          f"socle={r['socle']['n_paires']} "
          f"spatial={r['rayons']['< 3.0 km']['tous']['n_paires']}")
    check("N · et le socle ne descend PAS dans le profil par distance",
          r["profil"].get("0.0–0.3 km") is None,
          str({k: bool(v) for k, v in r["profil"].items()}))
    # ⛔ Le profil doit porter CHAQUE bande une fois — ni deux fois la
    # première, ni zéro fois la dernière (défaut trouvé le 27/08 en
    # relisant le rapport réel : il s'arrêtait à 2,2 km sans le dire).
    etq = SR._etiquettes_bandes()
    check("N · le profil porte toutes les bandes, chacune une seule fois",
          len(etq) == len(SR.BANDES_KM) == len(set(etq))
          and etq[-1] == "2.2–3.0 km" and list(r["profil"]) == etq,
          f"{etq} vs {list(r['profil'])}")
    check("N · et chaque étiquette est bien celle que rend "
          "`bande_distance`",
          all(SR.bande_distance((b0 + b1) / 2) == e for b0, b1, e in zip(
              (0.0,) + SR.BANDES_KM[:-1], SR.BANDES_KM, etq)),
          str(etq))
    check("N · SR.DIST_MIN_KM vaut bien 100 m",
          SR.DIST_MIN_KM == 0.1, str(SR.DIST_MIN_KM))


def test_n2_fournisseur():
    """⛔ `windsmobi` agrège seize fournisseurs derrière une seule
    source. Deux balises « du même réseau » peuvent donc être deux
    capteurs de deux constructeurs — et « intra-réseau = minorant »
    serait faux pour elles."""
    reseaux = {"c": "holfuy", "e": "ffvl"}
    r = joue(_deux_paires(6.0005, 6.021, network=reseaux),
             JOUR0 + timedelta(days=9), 10)
    check("N2 · le champ `network` sépare deux fournisseurs d'une "
          "même source",
          r["rayons"]["< 3.0 km"]["inter_reseaux"] is not None
          and r["rayons"]["< 3.0 km"]["intra_reseau"] is None,
          str({k: bool(v) for k, v in r["rayons"]["< 3.0 km"].items()}))
    # ⓘ Le couple lui-même n'apparaît pas dans le rapport : une seule
    # paire est SOUS `MIN_PAIRES_CLASSE`, et c'est la règle du lot (on
    # écrit `n` et on se tait). L'étiquette se vérifie donc à la source.
    check("N2 · et le fournisseur nomme la source ET le producteur",
          (SR.fournisseur("res:c", {"res:c": "holfuy"}) == "res/holfuy"
           and SR.fournisseur("res:c", {}) == "res"
           and SR.fournisseur("res:c", {"res:c": "res"}) == "res"),
          SR.fournisseur("res:c", {"res:c": "holfuy"}))
    sans = joue(_deux_paires(6.0005, 6.021), JOUR0 + timedelta(days=9), 10)
    check("N2 · sans `network`, on retombe sur la source, sans casser",
          sans["rayons"]["< 3.0 km"]["intra_reseau"] is not None,
          str(list(sans["reseaux"])))


# ══════════════════════════════════════════════════════════════════
#  O. LES QUASI-IDENTIQUES — une republication n'est pas un voisin
# ══════════════════════════════════════════════════════════════════

def test_o_quasi_identiques():
    """Trois paires à 350 m qui s'accordent à 0,2 km/h (le même capteur
    republié sous une autre coordonnée) et trois vrais voisinages à la
    MÊME distance. La sonde doit nommer les premières, et publier le
    plancher deux fois."""
    fin_ = Bruit(0.15, 0x9E01)      # republication : rien que du bruit d'arrondi
    gros = Bruit(2.4, 0x9E02)       # vrai voisinage
    par_jour = {}
    for k in range(12):
        d = JOUR0 + timedelta(days=k)
        rows = []
        for i in range(6):
            br = fin_ if i < 3 else gros
            heures = heures_du_jour(k, i)
            uva, uvb = [], []
            for hh in heures:
                u0, v0 = vent_de_fond(d, hh, k + i)
                au, av = br.uv()
                bu, bv = br.uv()
                uva.append((u0 + au, v0 + av))
                uvb.append((u0 + bu, v0 + bv))
            lat = 45.0 + 0.1 * i
            rows.append(ligne("res", f"a{i}", lat, 6.0, d, heures, uva))
            rows.append(ligne("autre", f"b{i}", lat, 6.0045, d, heures, uvb))
        par_jour[d.strftime("%Y-%m-%d")] = rows
    r = joue(par_jour, JOUR0 + timedelta(days=11), 12)
    q = r["quasi_identiques"]
    check("O · les trois republications sont nommées, et elles seules",
          q["n_paires"] == 3, f"{q['n_paires']} · {q['paires'][:2]}")
    check("O · elles restent DANS le plancher « tous » (rien n'est jeté)",
          r["rayons"]["< 3.0 km"]["tous"]["n_paires"] == 6,
          str(r["rayons"]["< 3.0 km"]["tous"]["n_paires"]))
    check("O · et le plancher relu SANS elles ne porte plus que 3 paires",
          r["hors_quasi"]["n_paires"] == 3,
          str(r["hors_quasi"]["n_paires"]))
    check("O · … et il est plus HAUT : c'est le prix de la duplication",
          r["hors_quasi"]["plancher_med"]
          > r["rayons"]["< 3.0 km"]["tous"]["plancher_med"],
          f"{r['hors_quasi']['plancher_med']} vs "
          f"{r['rayons']['< 3.0 km']['tous']['plancher_med']}")
    check("O · un vrai voisinage n'est JAMAIS classé quasi-identique",
          all("a3" not in e["paire"] and "a4" not in e["paire"]
              and "a5" not in e["paire"] for e in q["paires"]),
          str(q["paires"]))


# ══════════════════════════════════════════════════════════════════
#  M. DEUX PASSES DE COLLECTE — une balise, deux lignes, le même jour
# ══════════════════════════════════════════════════════════════════

def test_m_deux_lignes():
    """Le lot S0.6 partitionne les passes : une balise peut arriver en
    DEUX lignes d'archive le même jour. Les écraser perdrait une
    demi-journée en silence — le genre de perte qui ne fait rien
    rougir, puisqu'il reste des heures."""
    par_jour = {}
    br = Bruit(2.0, 0x2A55)
    for k in range(10):
        d = JOUR0 + timedelta(days=k)
        matin, soir = list(range(0, 12)), list(range(12, 24))
        uva_m, uva_s, uvb = [], [], []
        for hh in range(24):
            u0, v0 = vent_de_fond(d, hh, k)
            au, av = br.uv()
            bu, bv = br.uv()
            (uva_m if hh < 12 else uva_s).append((u0 + au, v0 + av))
            uvb.append((u0 + bu, v0 + bv))
        par_jour[d.strftime("%Y-%m-%d")] = [
            ligne("res", "a", 45.0, 6.0, d, matin, uva_m),
            ligne("res", "a", 45.0, 6.0, d, soir, uva_s),
            ligne("res", "b", 45.0, 6.008, d, list(range(24)), uvb),
        ]
    r = joue(par_jour, JOUR0 + timedelta(days=9), 10)
    g = r["rayons"]["< 3.0 km"]["tous"]
    check("M · les deux passes sont recollées (24 heures, pas 12)",
          g["n_heures"] == 240, f"{g['n_heures']}")


# ══════════════════════════════════════════════════════════════════

def main() -> int:
    for f in (test_a_plancher_connu, test_b_racine_de_deux,
              test_c_persistant_fluctuant, test_d_symetrie, test_e_pavage,
              test_f_doublon, test_g_derive, test_h_plancher_heures,
              test_i_repli_scalaire, test_j_intervalle, test_k_axes,
              test_k2_inter_reseaux, test_n_partition,
              test_n2_fournisseur, test_o_quasi_identiques,
              test_m_deux_lignes, test_l_rapport):
        f()
    print(f"\n  {OK} vertes, {KO} rouges")
    return 1 if KO else 0


if __name__ == "__main__":
    sys.exit(main())
