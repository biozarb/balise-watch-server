#!/usr/bin/env python3
"""test_sonde_chaine_arome.py — banc de la SONDE DE CHAÎNE (lot L4).

Le lot demande une décomposition. Une décomposition qui rend trois
nombres qui somment au total a l'air juste MÊME QUAND ELLE ATTRIBUE À
LA MAUVAISE CAUSE — c'est le risque nommé en tête du lot, et c'est le
seul que ce banc existe pour attraper.

La méthode : des scènes où UNE SEULE cause agit, et dont on connaît
donc la réponse parce qu'on l'a fabriquée.

  1. ARRONDI SEUL      — mêmes heures, même nœud, r2 = round(agrume).
                         part_arrondi doit porter TOUT le gap.
  2. HEURES SEULES     — agrume déjà entier (l'arrondi ne fait rien),
                         r2 = agrume amputé des heures 01/02/22/23.
                         part_heures doit porter TOUT le gap.
  3. RESTE SEUL        — agrume déjà entier, mêmes heures, r2 décalé
                         d'un vent voisin. part_reste doit tout porter.
  4. LES TROIS ENSEMBLE — l'identité doit tenir AU BIT PRÈS, et chaque
                         part doit retrouver son ordre de grandeur.
  5. LE NŒUD           — `arome_dist_km` gonflée : la sonde doit voir
                         un nœud différent, et pas avant.
  6. LE BASCULEMENT    — l'arrondi fait franchir DIR_MIN_WIND_KMH à une
                         heure : l'erreur passe de scalaire à
                         vectorielle. C'est un effet RÉEL de l'arrondi,
                         et il doit tomber dans part_arrondi.

⛔ ET LES SCÈNES SONT IRRÉGULIÈRES DANS LA DIMENSION TESTÉE (piège nº 2
de la phase B) : le nombre de balises change d'un jour à l'autre, les
heures trouées ne sont pas les mêmes partout, certaines balises n'ont
qu'un seul côté, et les vitesses ne sont pas toutes du même ordre. Un
jeu régulier laisserait passer « la part est la moyenne des parts
journalières », qui est faux.

Aucun `random` : générateur congruentiel maison, graine explicite.

    python3 test_sonde_chaine_arome.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

import scoring as S
import sonde_chaine_arome as SO

OK = 0
KO = 0


def check(label: str, cond: bool, detail: str = ""):
    global OK, KO
    if cond:
        OK += 1
    else:
        KO += 1
        print(f"  ❌ {label}" + (f"\n       {detail}" if detail else ""))


class LCG:
    def __init__(self, seed: int = 20260827):
        self.s = seed & 0xFFFFFFFF

    def u(self) -> float:
        self.s = (1103515245 * self.s + 12345) & 0x7FFFFFFF
        return (self.s >> 8) / float(1 << 23)


JOUR = datetime(2026, 8, 26)
T0 = int(JOUR.replace(tzinfo=timezone.utc).timestamp())
DEBUT_MS = T0 * 1000


def ligne(model, speed, direction, lat=45.17, lon=5.52, **extra):
    d = {"station_id": "1", "source": SO.SOURCE, "lat": lat, "lon": lon,
         "model": model, "t0": T0, "step_s": 3600,
         "speed": list(speed), "dir": list(direction)}
    d.update(extra)
    return d


def obs_de(speeds, dirs, heures=range(24)):
    """Un relevé par heure ronde — la fenêtre de `pair_series` est de
    ±20 min, donc un relevé pile à l'heure est apparié et un seul."""
    return [S.ObsSample(t=(T0 + h * 3600) * 1000,
                        speed=speeds[h], dir=dirs[h])
            for h in heures if speeds[h] is not None]


def scene(n_heures=24, base=12.0, graine=1):
    """Un vent horaire irrégulier, jamais plat : un jeu régulier rend
    la mutation indétectable (piège nº 2)."""
    g = LCG(graine)
    sp = [round(base + 8.0 * g.u() - 3.0, 1) for _ in range(n_heures)]
    dr = [round(200 + 120 * g.u()) % 360 for _ in range(n_heures)]
    return sp, dr


def _dec(row_ag, row_r2, obs, min_heures=6):
    return SO.decomposer(row_ag, row_r2, obs, DEBUT_MS, min_heures=min_heures)


print("\n▶ banc de la sonde de chaîne `arome_r2` (lot L4)\n")

# ══════════════════════════════════════════════════════════════════
print("  § 0 — le treillis et l'arrondi, seuls")
# ══════════════════════════════════════════════════════════════════
check("le nœud le plus proche est un multiple EXACT de 0,01°",
      SO.noeud_le_plus_proche(45.1749, 5.5168) == (45.17, 5.52),
      f"{SO.noeud_le_plus_proche(45.1749, 5.5168)}")
check("… et il se compare ÉGAL à lui-même (pas de dérive flottante)",
      SO.noeud_le_plus_proche(45.02, 3.07)
      == SO.noeud_le_plus_proche(45.0201, 3.0699),
      f"{SO.noeud_le_plus_proche(45.02, 3.07)!r} vs "
      f"{SO.noeud_le_plus_proche(45.0201, 3.0699)!r}")
check("l'arrondi de tuile est CELUI de production : round(spd)",
      [SO.arrondi_tuile(x) for x in (3.4, 3.6, 0.4, None)]
      == [3.0, 4.0, 0.0, None])
check("… et il ne touche PAS la direction (elle est déjà entière des "
      "deux côtés)",
      not hasattr(SO, "arrondi_direction"))

# ══════════════════════════════════════════════════════════════════
print("  § 1 — ARRONDI SEUL : r2 = round(agrume), mêmes heures")
# ══════════════════════════════════════════════════════════════════
sp, dr = scene(graine=11)
o_sp, o_dr = scene(base=11.0, graine=12)
obs = obs_de(o_sp, o_dr)
ag = ligne(SO.MODEL_AGRUME, sp, dr)
r2 = ligne(SO.MODEL_R2, [SO.arrondi_tuile(x) for x in sp], dr,
           arome_dist_km=0.40)
d = _dec(ag, r2, obs)
check("la balise-jour est notable des deux côtés", d is not None)
m = d["med"]
check("part_heures est NULLE (aucune heure ne manque)",
      abs(m["part_heures"]) < 1e-12, f"{m['part_heures']}")
check("part_reste est NULLE (r2 EST l'agrume arrondi)",
      abs(m["part_reste"]) < 1e-12, f"{m['part_reste']}")
check("part_arrondi porte TOUT le gap",
      abs(m["part_arrondi"] - m["gap"]) < 1e-12,
      f"arrondi {m['part_arrondi']} vs gap {m['gap']}")
check("l'identité tient au bit près", abs(m["residu_identite"]) < 1e-12)
check("… et la même chose sur le rms",
      abs(d["rms"]["part_arrondi"] - d["rms"]["gap"]) < 1e-12)
check("le gap n'est pas nul (sinon la scène ne prouve rien)",
      abs(m["gap"]) > 1e-6, f"{m['gap']}")

# ══════════════════════════════════════════════════════════════════
print("  § 2 — HEURES SEULES : agrume déjà entier, r2 amputé de 01/02/22/23")
# ══════════════════════════════════════════════════════════════════
sp_e = [float(round(x)) for x in sp]
ag = ligne(SO.MODEL_AGRUME, sp_e, dr)
troue = [None if h in (1, 2, 22, 23) else sp_e[h] for h in range(24)]
r2 = ligne(SO.MODEL_R2, troue, dr, arome_dist_km=0.40)
d = _dec(ag, r2, obs)
m = d["med"]
check("part_arrondi est NULLE (l'arrondi d'un entier ne fait rien)",
      abs(m["part_arrondi"]) < 1e-12, f"{m['part_arrondi']}")
check("part_reste est NULLE (mêmes valeurs aux heures communes)",
      abs(m["part_reste"]) < 1e-12, f"{m['part_reste']}")
check("part_heures porte TOUT le gap",
      abs(m["part_heures"] - m["gap"]) < 1e-12,
      f"heures {m['part_heures']} vs gap {m['gap']}")
check("… et le compte d'heures le DIT (24 d'un côté, 20 de l'autre)",
      (d["n_heures_agrume"], d["n_heures_r2"], d["n_heures_inter"])
      == (24, 20, 20),
      f"{d['n_heures_agrume']} / {d['n_heures_r2']} / {d['n_heures_inter']}")
check("le gap n'est pas nul", abs(m["gap"]) > 1e-9, f"{m['gap']}")

# ══════════════════════════════════════════════════════════════════
print("  § 3 — RESTE SEUL : mêmes heures, valeurs d'un nœud voisin")
# ══════════════════════════════════════════════════════════════════
voisin = [x + 1.0 for x in sp_e]          # entiers : l'arrondi ne fait rien
ag = ligne(SO.MODEL_AGRUME, sp_e, dr)
r2 = ligne(SO.MODEL_R2, voisin, dr, arome_dist_km=1.10)
d = _dec(ag, r2, obs)
m = d["med"]
check("part_heures NULLE", abs(m["part_heures"]) < 1e-12)
check("part_arrondi NULLE", abs(m["part_arrondi"]) < 1e-12,
      f"{m['part_arrondi']}")
check("part_reste porte TOUT le gap",
      abs(m["part_reste"] - m["gap"]) < 1e-12,
      f"reste {m['part_reste']} vs gap {m['gap']}")

# ══════════════════════════════════════════════════════════════════
print("  § 4 — LES TROIS ENSEMBLE : l'identité, et chaque part à sa place")
# ══════════════════════════════════════════════════════════════════
melange = [None if h in (1, 2, 22, 23) else SO.arrondi_tuile(sp[h]) + 1.0
           for h in range(24)]
ag = ligne(SO.MODEL_AGRUME, sp, dr)
r2 = ligne(SO.MODEL_R2, melange, dr, arome_dist_km=1.10)
d = _dec(ag, r2, obs)
m = d["med"]
check("l'identité tient AU BIT PRÈS quand les trois causes agissent",
      abs(m["residu_identite"]) < 1e-12, f"{m['residu_identite']}")
check("… et sur le rms aussi",
      abs(d["rms"]["residu_identite"]) < 1e-12)
check("les trois parts sont non nulles (la scène teste bien trois causes)",
      all(abs(m[k]) > 1e-9
          for k in ("part_heures", "part_arrondi", "part_reste")),
      f"{ {k: m[k] for k in ('part_heures', 'part_arrondi', 'part_reste')} }")
check("aucune part n'absorbe le total à elle seule",
      all(abs(m[k]) < abs(m["gap"]) + 1.0
          for k in ("part_heures", "part_arrondi", "part_reste")))

# ⛔ L'ORDRE COMPTE, ET LE BANC LE PROUVE plutôt que l'en-tête seule.
d_inv = SO.decomposer(ag, r2, obs, DEBUT_MS, ordre_inverse=True)
check("l'ordre inverse rend le MÊME gap (c'est le même écart)",
      abs(d_inv["med"]["gap"] - m["gap"]) < 1e-12)
check("… le même reste (il est en dernier dans les deux ordres)",
      abs(d_inv["med"]["part_reste"] - m["part_reste"]) < 1e-12)
check("… mais PAS les mêmes parts heures/arrondi : les interactions "
      "changent de terme, et c'est mesurable",
      abs(d_inv["med"]["part_arrondi"] - m["part_arrondi"]) > 1e-9,
      f"{d_inv['med']['part_arrondi']} vs {m['part_arrondi']}")
check("… et l'identité tient dans l'ordre inverse aussi",
      abs(d_inv["med"]["residu_identite"]) < 1e-12)

# ══════════════════════════════════════════════════════════════════
print("  § 5 — LE NŒUD : `arome_dist_km` contre le vrai plus proche")
# ══════════════════════════════════════════════════════════════════
# ⛔ La distance du VRAI nœud se CALCULE, elle ne se devine pas : une
# scène qui poserait « 0,05 km » à la main testerait la constante du
# banc, pas la sonde. Ici la balise est à 45,1749 / 5,5168, son nœud est
# (45,17 ; 5,52), et `d_theo` est ce que la haversine en dit.
LAT_B, LON_B = 45.1749, 5.5168
D_THEO = SO.distance_km(LAT_B, LON_B, *SO.noeud_le_plus_proche(LAT_B, LON_B))
juste = ligne(SO.MODEL_R2, sp, dr, lat=LAT_B, lon=LON_B,
              arome_dist_km=round(D_THEO, 2))
en = SO.ecart_de_noeud(juste)
check("une distance cohérente = MÊME nœud", en is not None and not en[0],
      f"{en}")
check("… et le nœud trouvé est bien à moins d'une demi-diagonale (0,68 km)",
      D_THEO < 0.68, f"{D_THEO}")
gonflee = dict(juste, arome_dist_km=round(D_THEO, 2) + 0.30)
en2 = SO.ecart_de_noeud(gonflee)
check("une distance gonflée = nœud DIFFÉRENT (la tuile a imposé le sien)",
      en2[0] and en2[1] > 0.2, f"{en2}")
check("… et l'écart rendu est la DIFFÉRENCE, pas la distance archivée",
      abs(en2[1] - (gonflee["arome_dist_km"] - en2[3])) < 1e-9, f"{en2}")
check("une ligne sans `arome_dist_km` ne se devine pas : elle rend None",
      SO.ecart_de_noeud({"lat": 45.0, "lon": 5.0}) is None)
# ⚠️ LA TOLÉRANCE EST UNE PROPRIÉTÉ, PAS UN CONFORT : `arome_dist_km`
# est archivée au centième de km, donc un écart de 5 m est du bruit
# d'écriture. Sans elle, TOUTES les balises passeraient pour lisant un
# autre nœud, et la cause (b) serait déclarée universelle.
limite = dict(juste, arome_dist_km=round(D_THEO + 0.005, 3))
check("5 m d'écart (le bruit d'écriture du centième) ne suffisent PAS à "
      "déclarer un nœud différent",
      not SO.ecart_de_noeud(limite)[0], f"{SO.ecart_de_noeud(limite)}")
check("… mais 20 m, oui — la tolérance n'avale pas un vrai décalage",
      SO.ecart_de_noeud(dict(juste,
                             arome_dist_km=round(D_THEO + 0.02, 3)))[0])

# ══════════════════════════════════════════════════════════════════
print("  § 5 bis — LES DEUX CHAÎNES LISENT-ELLES LE MÊME NŒUD ?")
# ══════════════════════════════════════════════════════════════════
# ⛔ La faute que cette section existe pour attraper : croire qu'une
# ligne `arome_r2` cohérente avec elle-même prouve que les deux chaînes
# lisent le même point. Elles peuvent chacune être parfaitement
# cohérente et lire deux nœuds différents — il suffit que les deux
# référentiels ne portent pas la même coordonnée de balise. Mesuré sur
# la production le 27/08 : 160 balises sur 285.
ag_ref = ligne(SO.MODEL_AGRUME, sp, dr, lat=46.3046, lon=6.0815)
r2_ref = ligne(SO.MODEL_R2, sp, dr, lat=46.3046, lon=6.0815,
               arome_dist_km=round(SO.distance_km(
                   46.3046, 6.0815,
                   *SO.noeud_le_plus_proche(46.3046, 6.0815)), 2))
m, dc, cause = SO.noeuds_lus(ag_ref, r2_ref)
check("mêmes coordonnées, tuile honnête → MÊME nœud",
      m and cause == "identique" and dc < 1e-9, f"{(m, dc, cause)}")

# 111 m d'écart, mais de part et d'autre du demi-pas : deux nœuds.
r2_dep = dict(r2_ref, lat=46.3056, lon=6.0814)
r2_dep["arome_dist_km"] = round(SO.distance_km(
    46.3056, 6.0814, *SO.noeud_le_plus_proche(46.3056, 6.0814)), 2)
m2, dc2, cause2 = SO.noeuds_lus(ag_ref, r2_dep)
check("111 m d'écart de référentiel suffisent à changer de nœud — et la "
      "cause est nommée COORDONNÉE, pas tuile",
      (not m2) and cause2 == "coordonnee" and 0.1 < dc2 < 0.15,
      f"{(m2, dc2, cause2)}")
check("… alors que chaque ligne est parfaitement cohérente avec "
      "elle-même (le contrôle de tuile ne voit RIEN)",
      not SO.ecart_de_noeud(r2_dep)[0])

# Une coordonnée qui change SANS changer de nœud : même nœud quand même.
r2_proche = dict(r2_ref, lat=46.3048, lon=6.0816)
r2_proche["arome_dist_km"] = round(SO.distance_km(
    46.3048, 6.0816, *SO.noeud_le_plus_proche(46.3048, 6.0816)), 2)
m3, dc3, cause3 = SO.noeuds_lus(ag_ref, r2_proche)
check("un écart de référentiel qui ne franchit pas le demi-pas laisse "
      "le MÊME nœud — l'écart de coordonnée ne suffit pas à condamner",
      m3 and cause3 == "identique" and dc3 > 0.0,
      f"{(m3, dc3, cause3)}")

# La tuile PRIME : si elle a imposé son nœud, la cause est la tuile.
r2_tuile = dict(r2_ref, arome_dist_km=r2_ref["arome_dist_km"] + 0.4)
m4, _, cause4 = SO.noeuds_lus(ag_ref, r2_tuile)
check("quand la tuile a imposé son nœud, la cause l'emporte sur la "
      "coordonnée (c'est un défaut de chaîne, pas de référentiel)",
      (not m4) and cause4 == "tuile", f"{(m4, cause4)}")

# ══════════════════════════════════════════════════════════════════
print("  § 6 — LE BASCULEMENT scalaire/vectoriel provoqué par l'arrondi")
# ══════════════════════════════════════════════════════════════════
# 4,6 km/h arrondi rend 5,0 : sous le seuil `DIR_MIN_WIND_KMH` l'erreur
# est SCALAIRE, au-dessus elle devient VECTORIELLE. C'est un effet réel
# de l'arrondi sur le score, et il doit tomber dans part_arrondi.
check("le seuil de bascule est bien celui de production",
      S.DIR_MIN_WIND_KMH == 5.0)
faible = [4.6] * 24
o_faible = [9.0] * 24
o_dirs = [180] * 24
obs_f = obs_de(o_faible, o_dirs)
ag_f = ligne(SO.MODEL_AGRUME, faible, [0] * 24)
r2_f = ligne(SO.MODEL_R2, [SO.arrondi_tuile(x) for x in faible], [0] * 24,
             arome_dist_km=0.4)
d_f = _dec(ag_f, r2_f, obs_f)
check("la scène de bascule est notable", d_f is not None)
check("l'erreur d'agrume est SCALAIRE (4,6 < 5) et celle de r2 "
      "VECTORIELLE (5,0 ≥ 5)",
      d_f["vector_ratio_agrume"] == 0.0 and d_f["vector_ratio_r2"] == 1.0,
      f"{d_f['vector_ratio_agrume']} / {d_f['vector_ratio_r2']}")
check("… et tout le gap est attribué à l'ARRONDI, qui en est la cause",
      abs(d_f["med"]["part_arrondi"] - d_f["med"]["gap"]) < 1e-12
      and abs(d_f["med"]["gap"]) > 1.0,
      f"{d_f['med']}")

# ══════════════════════════════════════════════════════════════════
print("  § 7 — CE QUI NE DOIT PAS ENTRER : le filtre est ENTIER ou RIEN")
# ══════════════════════════════════════════════════════════════════
court = [None] * 24
for h in (10, 11, 12, 13):
    court[h] = 12.0
ag_c = ligne(SO.MODEL_AGRUME, sp, dr)
r2_c = ligne(SO.MODEL_R2, court, dr, arome_dist_km=0.4)
check("une variante sous MIN_HOURS_DAILY fait tomber la balise-jour "
      "ENTIÈRE (jamais un demi-résultat)",
      _dec(ag_c, r2_c, obs) is None)
check("… et le seuil est bien celui de production (6 h)",
      SO.SC.MIN_HOURS_DAILY == 6)
vide = ligne(SO.MODEL_R2, [None] * 24, dr, arome_dist_km=0.4)
check("aucune heure commune → None, pas une division par zéro",
      _dec(ag, vide, obs) is None)

# ══════════════════════════════════════════════════════════════════
print("  § 8 — LA DÉCOUPE DU JOUR, et les heures hors journée")
# ══════════════════════════════════════════════════════════════════
long_sp = [10.0] * 30                       # 30 heures : le run déborde
long_dr = [180] * 30
t, s, dd = SO.serie_du_jour(ligne(SO.MODEL_R2, long_sp, long_dr), DEBUT_MS)
check("la journée notée s'arrête à 24 heures, jamais 30",
      len(t) == 24 and len(s) == 24 and len(dd) == 24, f"{len(t)}")
check("… et elle commence à minuit UTC de CE jour",
      t[0] == DEBUT_MS and t[-1] == DEBUT_MS + 23 * 3600 * 1000)

# ══════════════════════════════════════════════════════════════════
print("  § 9 — L'ÉCART DE CHAÎNE, sans aucune observation")
# ══════════════════════════════════════════════════════════════════
ag9 = ligne(SO.MODEL_AGRUME, sp, dr)
r29 = ligne(SO.MODEL_R2, [SO.arrondi_tuile(x) for x in sp], dr,
            arome_dist_km=0.4)
tot, quant, reste_c = SO.ecarts_de_chaine(ag9, r29, DEBUT_MS)
check("l'écart de chaîne existe sur les 24 heures communes",
      len(tot) == 24 and len(quant) == 24, f"{len(tot)}/{len(quant)}")
check("quand r2 EST l'agrume arrondi, l'arrondi explique l'écart EXACTEMENT",
      max(abs(a - b) for a, b in zip(tot, quant)) < 1e-12)
check("… et chaque écart vaut |Δvitesse| quand la direction est commune",
      all(abs(t_ - abs(SO.arrondi_tuile(sp[h]) - sp[h])) < 1e-9
          for h, t_ in enumerate(tot)))
r29b = ligne(SO.MODEL_R2, [x + 2.0 for x in sp], dr, arome_dist_km=0.4)
tot2, quant2, reste2 = SO.ecarts_de_chaine(ag9, r29b, DEBUT_MS)
check("quand r2 lit ailleurs, l'arrondi n'explique PLUS l'écart",
      S.median(tot2) > 1.5 and S.median(quant2) < 0.6,
      f"{S.median(tot2)} / {S.median(quant2)}")

# ⭐ L'ÉCART RÉSIDUEL — la mesure du lot qui ne passe ni par une médiane
# ni par une observation. Nulle, elle dit que les deux chaînes lisent le
# MÊME nœud et qu'il n'y a plus rien à expliquer.
check("quand r2 EST l'agrume arrondi, il ne reste RIEN après l'arrondi",
      max(reste_c) < 1e-12, f"{max(reste_c)}")
check("… et quand r2 lit ailleurs, le reste vaut exactement l'écart au "
      "point ARRONDI (le décalage de nœud, l'arrondi déjà retiré)",
      all(abs(v - abs(sp[h] + 2.0 - SO.arrondi_tuile(sp[h]))) < 1e-9
          for h, v in enumerate(reste2)), f"{reste2[:3]}")

# ⛔ UN NŒUD DIFFÉRENT NE CHANGE PAS QUE LA FORCE : il change aussi la
# DIRECTION. La part d'arrondi doit rester celle de l'arrondi — donc se
# calculer à direction d'`agrume` CONSTANTE. La prendre chez `arome_r2`
# ferait entrer le nœud dans la part de l'arrondi, sans que le total
# bouge d'un chiffre.
r29c = ligne(SO.MODEL_R2, [SO.arrondi_tuile(x) for x in sp],
             [(d + 20) % 360 for d in dr], arome_dist_km=1.10)
tot3, quant3, reste3 = SO.ecarts_de_chaine(ag9, r29c, DEBUT_MS)
check("le reste porte le décalage de DIRECTION, que l'arrondi n'explique "
      "pas",
      S.median(reste3) > 2.0, f"{S.median(reste3)}")
check("la part d'arrondi n'emprunte PAS la direction d'`arome_r2` : elle "
      "vaut toujours |Δvitesse| seule",
      all(abs(q - abs(SO.arrondi_tuile(sp[h]) - sp[h])) < 1e-9
          for h, q in enumerate(quant3)),
      f"{quant3[:4]}")
check("… alors que l'écart TOTAL, lui, a bien grossi de la direction",
      S.median(tot3) > 2.0 and S.median(tot3) > 4 * S.median(quant3),
      f"total {S.median(tot3)} vs arrondi {S.median(quant3)}")

# ══════════════════════════════════════════════════════════════════
print("  § 10 — BOUT EN BOUT : trois journées IRRÉGULIÈRES sur disque")
# ══════════════════════════════════════════════════════════════════
import gzip as _gz                                            # noqa: E402
import json as _json                                          # noqa: E402
import pathlib as _pl                                         # noqa: E402
import tempfile as _tmp                                       # noqa: E402
from datetime import timedelta as _td                         # noqa: E402

import score as SC                                            # noqa: E402


def _ecrire(root, cle, lignes):
    p = _pl.Path(root) / cle
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(_gz.compress("\n".join(
        _json.dumps(l, ensure_ascii=False) for l in lignes).encode("utf-8")))


tmp = _tmp.mkdtemp()
FIN = datetime(2026, 8, 26)
# ⛔ Irrégulier EXPRÈS : 5 balises le 24, 3 le 25 (dont une SANS agrume),
# 4 le 26 ; les heures trouées ne sont pas les mêmes d'un jour à l'autre.
PLAN = {
    "2026-08-24": [("1", True), ("2", True), ("3", True), ("4", True),
                   ("5", True)],
    "2026-08-25": [("1", True), ("2", False), ("3", True)],
    "2026-08-26": [("1", True), ("3", True), ("4", True), ("6", True)],
}
TROUS = {"2026-08-24": (1, 2, 22, 23), "2026-08-25": (1, 2, 3, 22, 23),
         "2026-08-26": (1, 2, 22, 23)}
for k in (2, 1, 0):
    j = FIN - _td(days=k)
    cle_j = f"{j:%Y-%m-%d}"
    t0 = int(j.replace(tzinfo=timezone.utc).timestamp())
    ags, r2s, obss = [], [], []
    for idx, (sid, avec_agrume) in enumerate(PLAN[cle_j]):
        s, dd = scene(base=10.0 + idx, graine=100 + idx + 7 * k)
        os_, od = scene(base=9.5 + idx, graine=500 + idx + 11 * k)
        tr = [None if h in TROUS[cle_j] else SO.arrondi_tuile(s[h])
              for h in range(24)]
        lat = 45.0 + 0.013 * idx
        base = dict(station_id=sid, source=SO.SOURCE, lat=lat, lon=5.5,
                    t0=t0, step_s=3600)
        if avec_agrume:
            ags.append(dict(base, model=SO.MODEL_AGRUME, speed=s, dir=dd))
        r2s.append(dict(base, model=SO.MODEL_R2, speed=tr, dir=dd,
                        arome_dist_km=round(SO.distance_km(
                            lat, 5.5, *SO.noeud_le_plus_proche(lat, 5.5)), 2)))
        obss.append(dict(station_id=sid, source=SO.SOURCE, lat=lat, lon=5.5,
                         t=[t0 + h * 3600 for h in range(24)],
                         speed=os_, dir=od))
    _ecrire(tmp, SC.fcst_agrume_key(j), ags)
    _ecrire(tmp, SC.fcst_arome_key(j), r2s)
    _ecrire(tmp, SC.obs_key(j), obss)

r = SO.sonder(_pl.Path(tmp), FIN, 3, avec_om=False,
              crier=lambda *a, **k: None)
check("les trois journées sont lues", r["fenetre"]["jours_lus"]
      == ["2026-08-24", "2026-08-25", "2026-08-26"],
      f"{r['fenetre']['jours_lus']}")
check("la balise SANS agrume ne compte pas (11 balise-jours, pas 12)",
      r["n_balise_jours"] == 11, f"{r['n_balise_jours']}")
check("le nombre de balises distinctes est compté, pas déduit "
      "(6 balises apparaissent, 11 balise-jours seulement)",
      r["n_balises"] == 6, f"{r['n_balises']}")
check("la série journalière porte les TROIS jours",
      len(r["med"]["gap"]["par_jour"]) == 3,
      f"{sorted(r['med']['gap']['par_jour'])}")
check("… avec des n DIFFÉRENTS d'un jour à l'autre (jeu irrégulier)",
      len({v["n"] for v in r["med"]["gap"]["par_jour"].values()}) > 1,
      f"{ {j: v['n'] for j, v in r['med']['gap']['par_jour'].items()} }")
check("sur 3 jours l'IC REFUSE de se prononcer (socle MIN_DAYS_BLOCK = 8)",
      r["med"]["gap"]["reason"] == "window_too_short"
      and r["med"]["gap"]["ci_low"] is None,
      f"{r['med']['gap']['reason']}")
check("… mais la médiane, elle, est publiée (le refus porte sur l'IC)",
      r["med"]["gap"]["mediane"] is not None)
check("le résidu d'identité reste nul sur toute la population",
      r["residu_identite_max"] < 1e-12, f"{r['residu_identite_max']}")
check("le treillis s'accorde à 100 % (les distances sont calculées "
      "depuis le vrai nœud)",
      r["treillis"]["taux_accord"] == 1.0
      and r["treillis"]["balises_noeud_different"] == 0,
      f"{r['treillis']}")
check("les heures manquantes sont VUES (20 côté r2, 24 côté agrume)",
      r["heures"]["r2_median"] == 20 and r["heures"]["agrume_median"] == 24,
      f"{r['heures']}")
check("l'écart de chaîne est mesuré sur les balise-heures communes",
      r["chaine"]["n_balise_heures"] > 0)
check("par construction, part_reste est nulle sur toute la scène "
      "(r2 EST l'agrume arrondi et amputé)",
      abs(r["med"]["part_reste"]["mediane"]) < 1e-12,
      f"{r['med']['part_reste']['mediane']}")
check("… et les deux autres agissent, jour après jour",
      all(abs(v["mediane"]) > 1e-9
          for v in r["med"]["part_heures"]["par_jour"].values())
      and all(abs(v["mediane"]) > 1e-9
              for v in r["med"]["part_arrondi"]["par_jour"].values()),
      f"{ {j: v['mediane'] for j, v in r['med']['part_heures']['par_jour'].items()} }")
# ⭐ ET LA LEÇON DE CETTE SCÈNE, qui n'était pas attendue : la médiane
# POOLÉE de part_heures vaut exactement 0 alors que chaque jour, elle,
# est franchement non nulle. Retirer quatre heures d'une journée ne
# déplace pas toujours la MÉDIANE des erreurs horaires — elle est faite
# pour ça. Un banc qui n'aurait regardé que le chiffre poolé aurait
# conclu « les heures n'y sont pour rien », et c'est faux : elles
# agissent, mais leur effet ne survit pas toujours à une médiane.
check("la médiane poolée peut valoir 0 quand les journées, elles, ne le "
      "sont pas — la médiane des heures est ROBUSTE, et le rapport doit "
      "publier la série journalière à côté",
      r["med"]["part_heures"]["mediane"] == 0.0
      and len(r["med"]["part_heures"]["par_jour"]) == 3,
      f"{r['med']['part_heures']['mediane']}")
# ⛔ L'ADDITIVITÉ EST SUR LA MOYENNE, PAS SUR LA MÉDIANE — la propriété
# que la sonde a failli publier de travers le 27/08.
mg = r["med"]["gap"]["moyenne"]
somme = sum(r["med"][k]["moyenne"] for k in
            ("part_heures", "part_arrondi", "part_reste"))
check("les MOYENNES des trois parts somment exactement à celle du gap",
      abs(somme - mg) < 1e-9, f"{somme} vs {mg}")
check("… ce que les MÉDIANES, elles, ne font PAS sur cette scène — "
      "et c'est pour ça que la part se lit sur la moyenne",
      abs(sum(r["med"][k]["mediane"] for k in
              ("part_heures", "part_arrondi", "part_reste"))
          - r["med"]["gap"]["mediane"]) > 1e-9)
check("chaque terme publie sa moyenne à côté de sa médiane",
      all(r["med"][k]["moyenne"] is not None for k in
          ("gap", "part_heures", "part_arrondi", "part_reste")))
check("l'écart résiduel après arrondi est publié, et il est nul ici "
      "(r2 EST l'agrume arrondi)",
      r["chaine"]["ecart_apres_arrondi"]["max"] < 1e-12
      and r["chaine"]["n_au_dessus_1kmh"] == 0,
      f"{r['chaine']['ecart_apres_arrondi']}")

# ⛔ LA PART IMPRIMÉE est celle des MOYENNES. Sur cette scène, la part
# médiane et la part moyenne diffèrent franchement : le banc lit le
# TEXTE, pas l'intention.
_txt = SO.rapport(r)
_pm = 100 * r["med"]["part_arrondi"]["moyenne"] / r["med"]["gap"]["moyenne"]
_pmed = 100 * r["med"]["part_arrondi"]["mediane"] / r["med"]["gap"]["mediane"]
check("la scène sépare bien les deux lectures de la part",
      abs(_pm - _pmed) > 5.0, f"{_pm:.1f} vs {_pmed:.1f}")
check("le rapport IMPRIME la part des moyennes, pas celle des médianes",
      f"{_pm:5.1f} %" in _txt and f"{_pmed:5.1f} %" not in _txt,
      f"attendu {_pm:5.1f} %, trouvé {_pmed:5.1f} %")
check("… et les trois parts imprimées somment à 100 % (aux arrondis près)",
      abs(sum(100 * r["med"][k]["moyenne"] / r["med"]["gap"]["moyenne"]
              for k in ("part_heures", "part_arrondi", "part_reste"))
          - 100.0) < 0.2)

check("le bloc des coordonnées est publié et compte ses causes",
      r["coordonnees"]["n"] == r["n_balise_jours"]
      and sum(r["coordonnees"]["par_cause"].values()) == r["n_balise_jours"],
      f"{r['coordonnees']}")
check("sur cette scène les deux référentiels sont d'accord partout",
      r["coordonnees"]["n_differentes"] == 0
      and r["coordonnees"]["par_cause"]["identique"] == r["n_balise_jours"],
      f"{r['coordonnees']}")
check("le reste par groupe de nœud porte les TROIS causes, toujours",
      sorted(r["reste_par_noeud"]) == ["coordonnee", "identique", "tuile"])

check("le rapport se rend en texte sans lever",
      isinstance(SO.rapport(r), str) and "DÉCOMPOSITION" in SO.rapport(r))
check("… et en JSON sérialisable tel quel",
      isinstance(_json.dumps(r), str))

# ══════════════════════════════════════════════════════════════════
print(f"\n{'✅' if KO == 0 else '❌'} {OK} assertions vertes, {KO} rouges.\n")
sys.exit(1 if KO else 0)
