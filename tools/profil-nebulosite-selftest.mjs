#!/usr/bin/env node
// ══════════════════════════════════════════════════════════════════════
//  tools/profil-nebulosite-selftest.mjs — LE VOILE NUAGEUX  (20/08/2026)
//
//      node tools/profil-nebulosite-selftest.mjs
//
//  Il vérifie UNE chose, celle que Yann a vue à l'écran le 20/08 :
//  `sampleAtAltitude` (web/src/lib/profile.ts) doit interpoler la
//  nébulosité entre les niveaux QUI EN PORTENT, et entre ceux-là seuls.
//
//  ⛔⛔ LE DÉFAUT QU'IL EXISTE POUR ATTRAPER, ET QUI NE LÈVE AUCUNE
//  ERREUR : `lerp(a, b, f)` tolère les `null` en rendant l'autre valeur
//  TELLE QUELLE. Sur AGRUME, la colonne entrelace 25 niveaux HAUTEUR
//  sans nébulosité (`cc` n'existe que sur les isobares) et 14 niveaux
//  isobares qui en portent : l'ancien code peignait alors le voile gris
//  UNIQUEMENT dans la tranche entre un isobare et son voisin hauteur —
//  une RAYURE de ~100 m autour de 850, 800, 700 hPa…, à pleine valeur,
//  et RIEN entre deux rayures. Un ciel couvert se lisait comme trois
//  traits de crayon. Aucune requête en échec, aucune valeur inventée :
//  juste une image fausse.
//
//  ⚠️ ET IL SAIT ÉCHOUER : la section 4 rejoue l'ANCIENNE formule sur
//  les MÊMES points et exige qu'elle produise les rayures. Si un jour
//  elle n'en produit plus, c'est que le profil de démonstration ne
//  reproduit plus le cas — et le banc le dit au lieu de rester vert.
// ══════════════════════════════════════════════════════════════════════
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ici = dirname(fileURLToPath(import.meta.url));
const MOD = join(ici, "..", "..", "web", "src", "lib", "profile.ts");
const P = await import(process.env.BW_PROFILE_MODULE || MOD);

let echecs = 0;
const rouges = [];
const verifier = (nom, ok, detail = "") => {
  console.log(`  ${ok ? "✓" : "✗"} ${nom}${detail ? `   ${detail}` : ""}`);
  if (!ok) { echecs++; rouges.push(nom); }
};
const section = (titre, fn) => {
  console.log(`\n── ${titre}`);
  try { fn(); } catch (e) {
    echecs++; rouges.push(titre);
    console.log(`  ✗ la section a LEVÉ : ${e?.message ?? e}`);
  }
};

// ══════════════════════════════════════════════════════════════════════
//  UNE COLONNE AGRUME DE DÉMONSTRATION
//  Deux familles entrelacées, comme `agrumeProfile.ts` les construit :
//   · 25 niveaux HAUTEUR (sol + 10, 20, 50, … 3000 m), `cloud = null` ;
//   · des niveaux ISOBARES porteurs de `cc`.
//  ⓘ Une seule échéance (hi = 0) : ce qu'on teste est vertical.
// ══════════════════════════════════════════════════════════════════════
const ZSOL = 500;
const HAUTEURS = [10, 20, 50, 100, 150, 200, 300, 400, 500, 600, 700, 800,
  900, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400, 2600, 2800, 3000];
/** [altitude AMSL, nébulosité %] — 850 hPa ≈ 1500 m, 800 ≈ 1950, etc. */
const ISOBARES = [[900, 40], [1500, 90], [1950, 85], [2500, 60], [3000, 10],
  [4200, 0], [5500, 0]];

function niveau(alt, cloud) {
  return {
    pressure: NaN, altitude: [alt], windSpeed: [20], windDir: [180],
    temp: [10], cloud: [cloud], humidity: [50], tke: [null],
  };
}
function profilAgrume() {
  const levels = [
    ...HAUTEURS.map(h => niveau(ZSOL + h, null)),
    ...ISOBARES.filter(([a]) => a > ZSOL).map(([a, cc]) => niveau(a, cc)),
  ].sort((a, b) => a.altitude[0] - b.altitude[0]);
  return {
    model: "agrume", times: [Date.parse("2026-08-20T12:00:00Z")],
    elevation: ZSOL, levels,
    surface: {
      temp2m: [18], dewpoint2m: [10], windSpeed10m: [12], windDir10m: [180],
      windGust10m: [20], cloudLow: [60], cloudMid: [30], cloudHigh: [10],
      cape: [200], shortwave: [500], pressure: [960], pressureMsl: [1015],
      precipitation: [0],
    },
  };
}
/** Un profil « Open-Meteo » : QUE des niveaux isobares, tous porteurs de
 *  `cc`. C'est la forme des six autres modèles — celle qui n'a jamais
 *  montré le défaut, et qui ne doit RIEN voir changer au-dessus de son
 *  premier niveau. */
function profilOpenMeteo() {
  const p = profilAgrume();
  p.levels = ISOBARES.filter(([a]) => a > ZSOL).map(([a]) =>
    // Nébulosité linéaire de 40 % (900 m) à 0 % (5500 m).
    niveau(a, Math.max(0, 40 - (40 * (a - 900)) / 4600)));
  return p;
}

/** L'ANCIENNE interpolation, reconstituée pour le sabotage : les deux
 *  niveaux qui encadrent, et `lerp` tolérant aux `null`. */
function ancienneNebulosite(p, targetAlt) {
  const pts = [{ alt: p.elevation + 10, cloud: null },
    ...p.levels.map(l => ({ alt: l.altitude[0], cloud: l.cloud[0] }))]
    .sort((a, b) => a.alt - b.alt);
  if (targetAlt <= pts[0].alt) return pts[0].cloud;
  if (targetAlt >= pts[pts.length - 1].alt) return null;
  let lo = pts[0], hi = pts[pts.length - 1];
  for (let i = 0; i < pts.length - 1; i++) {
    if (targetAlt >= pts[i].alt && targetAlt <= pts[i + 1].alt) {
      lo = pts[i]; hi = pts[i + 1]; break;
    }
  }
  const span = hi.alt - lo.alt;
  const f = span > 0 ? (targetAlt - lo.alt) / span : 0;
  if (lo.cloud == null && hi.cloud == null) return null;
  if (lo.cloud == null) return hi.cloud;
  if (hi.cloud == null) return lo.cloud;
  return lo.cloud + (hi.cloud - lo.cloud) * f;
}

// ══════════════════════════════════════════════════════════════════════
// 1. LE VOILE EST CONTINU ENTRE DEUX NIVEAUX NUAGEUX
// ══════════════════════════════════════════════════════════════════════
section("1. entre deux isobares nuageux, aucune altitude n'est muette", () => {
  const p = profilAgrume();
  let muettes = 0, total = 0;
  const exemples = [];
  for (let a = 1500; a <= 3000; a += 25) {
    total++;
    const cc = P.sampleAtAltitude(p, 0, a).cloud;
    if (cc == null) { muettes++; if (exemples.length < 4) exemples.push(`${a} m`); }
  }
  verifier("⛔ de 1 500 m à 3 000 m — tranche encadrée par des niveaux qui "
    + "PORTENT la nébulosité — aucune altitude ne rend `null`, alors que "
    + "les niveaux HAUTEUR intercalés n'en portent aucune",
    muettes === 0, `${muettes}/${total} muette(s)${exemples.length ? ` (${exemples.join(", ")})` : ""}`);
});

// ══════════════════════════════════════════════════════════════════════
// 2. C'EST UNE INTERPOLATION, PAS UNE RECOPIE
// ══════════════════════════════════════════════════════════════════════
section("2. la valeur est interpolée entre les deux niveaux nuageux", () => {
  const p = profilAgrume();
  // 1725 m = pile entre 1500 (90 %) et 1950 (85 %) → 87,5 %.
  const cc = P.sampleAtAltitude(p, 0, 1725).cloud;
  verifier("⛔ à mi-chemin de 1 500 m (90 %) et 1 950 m (85 %), on lit "
    + "87,5 % — ni 90 recopié, ni 85 recopié",
    cc != null && Math.abs(cc - 87.5) < 1e-6, `${cc?.toFixed(3)} %`);

  // 2750 m = pile entre 2500 (60 %) et 3000 (10 %) → 35 %.
  const cc2 = P.sampleAtAltitude(p, 0, 2750).cloud;
  verifier("⚠️ et sur une tranche où la nébulosité CHUTE (60 % → 10 %), le "
    + "dégradé se lit aussi : 35 % à mi-hauteur",
    cc2 != null && Math.abs(cc2 - 35) < 1e-6, `${cc2?.toFixed(3)} %`);

  const bord = P.sampleAtAltitude(p, 0, 1500).cloud;
  verifier("⚠️ SUR le niveau lui-même, la valeur du niveau, sans dérive",
    bord != null && Math.abs(bord - 90) < 1e-9, `${bord} %`);
});

// ══════════════════════════════════════════════════════════════════════
// 3. HORS DE LA PLAGE NUAGEUSE : `null`, ET PAS UNE VALEUR PROLONGÉE
// ══════════════════════════════════════════════════════════════════════
section("3. sous le plus bas niveau nuageux, on ne sait pas — on le dit", () => {
  const p = profilAgrume();
  const sous = P.sampleAtAltitude(p, 0, 700).cloud;
  verifier("⛔ à 700 m — au-dessus du sol, SOUS le premier niveau qui porte "
    + "une nébulosité (900 m) — la réponse est `null` : prolonger aurait "
    + "AFFIRMÉ 40 % à une altitude où personne n'a regardé",
    sous === null, `${sous}`);

  const hautDeGamme = P.sampleAtAltitude(p, 0, 5400).cloud;
  verifier("⚠️ sous le dernier niveau, la lecture reste servie",
    hautDeGamme != null, `${hautDeGamme}`);
});

// ══════════════════════════════════════════════════════════════════════
// 4. ⚠️ LE SABOTAGE — l'ancienne formule DOIT rayer
// ══════════════════════════════════════════════════════════════════════
section("4. le banc sait échouer : l'ancienne formule fait des rayures", () => {
  const p = profilAgrume();
  let muettesAvant = 0, recopiesAvant = 0, total = 0;
  for (let a = 1500; a <= 3000; a += 25) {
    total++;
    const v = ancienneNebulosite(p, a);
    if (v == null) muettesAvant++;
    // Une valeur EXACTEMENT égale à celle d'un niveau isobare loin de ce
    // niveau = une recopie, pas une interpolation.
    else if (ISOBARES.some(([alt, cc]) => Math.abs(v - cc) < 1e-9 && Math.abs(alt - a) > 60)) {
      recopiesAvant++;
    }
  }
  verifier("⛔ rejouée sur la MÊME colonne, l'ancienne interpolation laisse "
    + "des altitudes muettes entre deux isobares nuageux — c'est la rayure "
    + "vue à l'écran", muettesAvant > 0,
    `${muettesAvant}/${total} muette(s) avec l'ancien code`);
  verifier("⚠️ …et là où elle parlait, elle RECOPIAIT la valeur du niveau "
    + "voisin au lieu de l'interpoler", recopiesAvant > 0,
    `${recopiesAvant}/${total} recopie(s) avec l'ancien code`);

  const cc = P.sampleAtAltitude(p, 0, 1725).cloud;
  const ancien = ancienneNebulosite(p, 1725);
  verifier("⛔⛔ et les deux ne disent PAS la même chose à 1 725 m — sans "
    + "ça, ce banc serait vert sur le code d'avant comme sur celui d'après",
    ancien !== cc, `avant ${ancien} · après ${cc?.toFixed(2)}`);
});

// ══════════════════════════════════════════════════════════════════════
// 5. LES SIX AUTRES MODÈLES — ce qui change, et ce qui ne change pas
// ══════════════════════════════════════════════════════════════════════
section("5. sur une colonne dont TOUS les niveaux portent la nébulosité", () => {
  const p = profilOpenMeteo();
  let ecartMax = 0, comptees = 0;
  for (let a = 1000; a <= 5000; a += 50) {
    const avant = ancienneNebulosite(p, a);
    const apres = P.sampleAtAltitude(p, 0, a).cloud;
    if (avant == null || apres == null) continue;
    comptees++;
    ecartMax = Math.max(ecartMax, Math.abs(avant - apres));
  }
  verifier("⛔ RIEN NE CHANGE pour les six modèles Open-Meteo au-dessus du "
    + "premier niveau : même valeur qu'avant, à l'epsilon près",
    comptees > 50 && ecartMax < 1e-9,
    `n = ${comptees}, écart max ${ecartMax.toExponential(2)} %`);

  const sousLePremier = P.sampleAtAltitude(p, 0, ZSOL + 30).cloud;
  verifier("⚠️ CE QUI CHANGE, ET C'EST VOULU : juste au-dessus du sol, sous "
    + "le premier niveau porteur, l'ancienne formule recopiait ce niveau "
    + "jusqu'au sol — un voile AFFIRMÉ que le modèle n'avait pas dit. "
    + "Désormais `null`", sousLePremier === null,
    `avant ${ancienneNebulosite(p, ZSOL + 30)?.toFixed(1)} · après ${sousLePremier}`);
});

// ══════════════════════════════════════════════════════════════════════
console.log(`\n${echecs ? "✗" : "✓"} ${echecs} contrôle(s) au rouge`
  + `${echecs ? ` : ${rouges.join(" · ")}` : ""}`);
process.exit(echecs ? 1 : 0);
