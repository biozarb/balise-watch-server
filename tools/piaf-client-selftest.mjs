#!/usr/bin/env node
// ══════════════════════════════════════════════════════════════════════
//  tools/piaf-client-selftest.mjs — LE BANC DU LOT Q3    (20/08/2026)
//
//      node --experimental-strip-types \
//           tools/piaf-client-selftest.mjs [--production]
//
//  Il vérifie le CÔTÉ CLIENT de la pluie à venir : la découverte par
//  l’index, les trois contrôles du manifeste, la convention de temps,
//  l’adressage de la maille, le Range par échéance et les paliers de
//  couleur.
//
//  ⛔⛔ CE BANC EXISTE POUR LES SIX FAÇONS DE MENTIR SANS UNE ERREUR :
//
//    1. prendre l’instant nommé pour le DÉBUT de la tranche — tout le
//       ruban décalé de 5 min, aucune requête en échec ;
//    2. supposer les latitudes CROISSANTES — la pluie du point
//       symétrique, une carte plausible au mauvais endroit ;
//    3. arrondir au lieu de tronquer l’indice de maille — une maille de
//       décalage, soit 2 km, sur la moitié de l’écran ;
//    4. servir un manifeste d’une passe pour les octets d’une autre — le
//       Range tombe DANS l’objet, rend 206, et la carte est fausse ;
//    5. accepter une grille au compte IMPAIR — la dernière maille du
//       calque couvre deux fois moins de terrain que ses voisines ;
//    6. rendre l’échéance de BORD quand l’instant sort de la portée, au
//       lieu de ne rien peindre.
//
//  ⚠️ ET IL DOIT SAVOIR ÉCHOUER. Chaque section rejoue au moins un
//  SABOTAGE : le contrôle doit virer au rouge quand on casse ce qu’il
//  prétend tenir. Le Lot L2 a découvert qu’un banc peut prouver
//  l’EXISTENCE d’un garde-fou sans prouver son BRANCHEMENT.
//
//  ⓘ `--production` ajoute la seule vérification qui compte vraiment :
//  les OCTETS SERVIS — et elle COMPTE LES MAILLES PLUVIEUSES, parce
//  qu’un contrôle « écart max 0,000 » sans une goutte de pluie dedans
//  aurait été aussi vert avec deux jeux totalement décalés (Lot Q2, §5).
// ══════════════════════════════════════════════════════════════════════
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ici = dirname(fileURLToPath(import.meta.url));
const MOD = join(ici, "..", "..", "web", "src", "lib", "piaf.ts");
const P = await import(process.env.BW_PIAF_MODULE || MOD);

const PROD = process.argv.includes("--production");
const BASE = process.env.BW_R2_BASE
  || "https://pub-7a401bae4fe54a6c8dbdd6b5a33a7bec.r2.dev";

let echecs = 0;
const rouges = [];
const verifier = (nom, ok, detail = "") => {
  console.log(`  ${ok ? "✓" : "✗"} ${nom}${detail ? `   ${detail}` : ""}`);
  if (!ok) { echecs++; rouges.push(nom); }
};
// ⚠️ CHAQUE SECTION EST ISOLÉE : un banc qui MEURT ne dit pas ce qui a
// cédé, il dit seulement qu’il a cédé quelque part.
const section = (titre, fn) => {
  console.log(`\n── ${titre}`);
  try { fn(); } catch (e) {
    echecs++; rouges.push(titre);
    console.log(`  ✗ la section a LEVÉ : ${e?.message ?? e}`);
  }
};
const sectionAsync = async (titre, fn) => {
  console.log(`\n── ${titre}`);
  try { await fn(); } catch (e) {
    echecs++; rouges.push(titre);
    console.log(`  ✗ la section a LEVÉ : ${e?.message ?? e}`);
  }
};

// ── Un manifeste FABRIQUÉ, minimal et EXACT ─────────────────────────
// ⚠️ Fabriqué et pas recopié d’une passe réelle : une passe réelle
// disparaît de R2 au bout de vingt minutes, et un banc qui dépend d’un
// objet jetable n’est pas un banc, c’est une alerte de rétention.
const PASSE = "2026-08-20T10:30:00Z";
const T0 = Date.parse(PASSE);
function manifesteFactice(sur = {}) {
  const echeances = [];
  for (let r = 0; r < 39; r++) {
    echeances.push({
      rang: r, debut_min: r * 5, fin_min: (r + 1) * 5,
      debut: new Date(T0 + r * 5 * 60_000).toISOString().replace(".000", ""),
      fin: new Date(T0 + (r + 1) * 5 * 60_000).toISOString().replace(".000", ""),
      instant_demande: new Date(T0 + (r + 1) * 5 * 60_000).toISOString().replace(".000", ""),
    });
  }
  return {
    passe: PASSE,
    source: {
      producteur: "Météo-France", produit: "prévision immédiate agrégée",
      licence: "Licence Ouverte 2.0", attribution: "Source : Météo-France",
      agregation: "PT5M", cadence_producteur_min: 5,
      cadence_ingestion_min: 10, latence_publication_min: 10.1,
    },
    echeances, pas_min: 5, horizon_min: 195,
    heures_entieres: [],
    parametre: { nom: "pluie_5min", unite: "mm" },
    boite: { latmin: 42.0, latmax: 50.01, lonmin: -1.85, lonmax: 9.5 },
    axes: {
      nb_lat: 802, nb_lon: 1136, pas_deg: 0.01,
      lat_premier: 50.01, lat_dernier: 42.0,
      lon_premier: -1.85, lon_dernier: 9.5,
    },
    service: {
      cle_index: "agrume/piaf/index.json", dtype: "float16",
      calque: {
        cle: `agrume/piaf/${PASSE}/carte.bin`,
        octets_par_echeance: 401 * 568 * 2,
        pas_deg: 0.02, nb_lat: 401, nb_lon: 568,
        lat_premier: 50.01, lat_dernier: 42.01,
        lon_premier: -1.85, lon_dernier: 9.49,
        regle: "MAXIMUM des 4 points natifs",
      },
      coupe: {
        gabarit_cle: `agrume/piaf/${PASSE}/colonnes-{domaine}.bin`,
        octets_par_colonne: 78, pas_deg: 0.01, domaines: {},
      },
    },
    ...sur,
  };
}

// ══════════════════════════════════════════════════════════════════════
// 1. LE TEMPS — l’instant nommé est la FIN de la tranche
// ══════════════════════════════════════════════════════════════════════
section("1. la convention de temps : ]debut, fin]", () => {
  const man = manifesteFactice();
  const r0 = P.rangPourInstant(man, T0 + 5 * 60_000);
  verifier("l’instant `passe + 5 min` est la FIN du rang 0, pas le début "
    + "du rang 1", r0.rang === 0, `rang = ${r0.rang}`);

  const r1 = P.rangPourInstant(man, T0 + 5 * 60_000 + 1);
  verifier("une milliseconde plus tard, on bascule au rang 1 — la tranche "
    + "est FERMÉE à droite", r1.rang === 1, `rang = ${r1.rang}`);

  const rPasse = P.rangPourInstant(man, T0);
  verifier("l’instant de la passe elle-même est REFUSÉ, et nommé "
    + "« avant-la-passe » — il n’est couvert par aucune tranche",
    rPasse.refus === "avant-la-passe", JSON.stringify(rPasse));

  const rFin = P.rangPourInstant(man, T0 + 195 * 60_000);
  verifier("l’horizon exact (195 min) est le DERNIER rang servi, pas un "
    + "refus", rFin.rang === 38, `rang = ${rFin.rang}`);

  const rApres = P.rangPourInstant(man, T0 + 195 * 60_000 + 1);
  verifier("⛔ une milliseconde AU-DELÀ de l’horizon rend un refus NOMMÉ, "
    + "jamais le rang de bord", rApres.refus === "au-dela-de-l-horizon",
    JSON.stringify(rApres));

  // ⛔ SABOTAGE — prendre `debut` pour l’instant nommé.
  const sabote = manifesteFactice();
  for (const e of sabote.echeances) { e.debut_min -= 5; e.fin_min -= 5; }
  const rs = P.rangPourInstant(sabote, T0 + 5 * 60_000);
  verifier("SABOTAGE : un manifeste dont les tranches sont décalées de "
    + "5 min ne rend PAS le même rang — le banc voit le décalage",
    rs.rang !== r0.rang, `rang saboté = ${rs.rang} contre ${r0.rang}`);

  const inst = P.instantsPiaf(man);
  verifier("les 39 instants publiés tombent tous sur une MINUTE ENTIÈRE "
    + "(c’est ce qui les autorise dans l’axe maître de la carte)",
    inst.length === 39 && inst.every(ms => ms % 60_000 === 0),
    `n = ${inst.length}`);
});

// ══════════════════════════════════════════════════════════════════════
// 2. LA GÉOMÉTRIE — latitudes DÉCROISSANTES, coin NORD-OUEST
// ══════════════════════════════════════════════════════════════════════
section("2. l’adressage de la maille du calque", () => {
  const man = manifesteFactice();
  const c = man.service.calque;

  const coin = P.mailleCalque(man, c.lat_premier, c.lon_premier);
  verifier("le coin nord-ouest publié tombe sur la maille (0, 0)",
    coin && coin.j === 0 && coin.i === 0, JSON.stringify(coin));

  // Un point à l’intérieur du bloc, sans être son coin.
  const m = P.mailleCalque(man, c.lat_premier - 0.015, c.lon_premier + 0.015);
  verifier("⛔ un point au MILIEU d’un bloc appartient à CE bloc — on "
    + "tronque, on n’arrondit pas (arrondir donnerait (1,1))",
    m && m.j === 0 && m.i === 0, JSON.stringify(m));

  const sud = P.mailleCalque(man, c.lat_premier - 0.02, c.lon_premier);
  verifier("⚠️ LATITUDES DÉCROISSANTES : 0,02° plus au SUD, c’est la "
    + "maille j = 1", sud && sud.j === 1, JSON.stringify(sud));

  // ⛔⛔ LE DÉFAUT TROUVÉ PAR CE BANC LE 20/08 — la frontière de bloc.
  // `(50.01 − 46.45) / 0.02` vaut 177,999 999 999 999 77 en binaire :
  // sans correction, `Math.floor` rend 177, donc la maille du DESSUS, et
  // la pluie est peinte 2 km trop au nord. Les trois coins nord-ouest
  // des domaines de la coupe tombaient du mauvais côté.
  // ⚠️ Ce contrôle ne doit JAMAIS être « corrigé » en changeant l'attendu.
  const bords = [
    ["nord-alpes  46,45 N", 46.45, 178],
    ["pyrenees    43,40 N", 43.40, 330],
    ["pyrenees    43,39 N", 43.39, 331],
    ["tarn        44,26 N", 44.26, 287],
  ];
  verifier("⛔⛔ les latitudes qui tombent PILE sur une frontière de bloc "
    + "sont du bon côté — l'erreur d'arrondi binaire vit là, et nulle part "
    + "ailleurs",
    bords.every(([, lat, j]) => P.mailleCalque(man, lat, 5.0).j === j),
    bords.map(([n, lat, j]) => `${n} → ${P.mailleCalque(man, lat, 5.0).j} (attendu ${j})`).join(" · "));

  verifier("hors boîte au nord → `null`, jamais la maille de bord",
    P.mailleCalque(man, 55, 5) === null);
  verifier("hors boîte à l’ouest → `null`",
    P.mailleCalque(man, 45, -10) === null);

  verifier("`dansBoite` colle à la boîte publiée, bornes comprises",
    P.dansBoite(man, 42.0, -1.85) && P.dansBoite(man, 50.01, 9.5)
    && !P.dansBoite(man, 41.99, 5) && !P.dansBoite(man, 45, 9.51));

  // ⛔ SABOTAGE — la latitude croissante.
  const faux = Math.floor((45.0 - c.lat_premier) / c.pas_deg);
  const vrai = P.mailleCalque(man, 45.0, 5.0).j;
  verifier("SABOTAGE : lire la latitude comme CROISSANTE donne un indice "
    + "négatif — donc un point hors grille, pas un point voisin",
    faux < 0 && vrai > 0, `croissant = ${faux}, décroissant = ${vrai}`);
});

// ══════════════════════════════════════════════════════════════════════
// 3. LES TROIS CONTRÔLES DU MANIFESTE
// ══════════════════════════════════════════════════════════════════════
section("3. le couple (index, manifeste, octets)", () => {
  const man = manifesteFactice();
  verifier("un manifeste cohérent avec son index ne lève rien",
    P.verifierManifeste({ dernier: { passe: PASSE } }, man) === null);

  const m1 = P.verifierManifeste({ dernier: { passe: "2026-08-20T10:40:00Z" } }, man);
  verifier("⛔ manifeste d’une passe / index d’une autre → REFUS nommé "
    + "(c’est le cas SILENCIEUX : 206, bonne longueur, mauvais instant)",
    typeof m1 === "string" && m1.includes(PASSE) && m1.includes("2026-08-20T10:40:00Z"),
    m1 ? m1.slice(0, 60) + "…" : "null");

  const faux = manifesteFactice();
  faux.service.calque.octets_par_echeance = 400000;
  verifier("⛔ `octets_par_echeance` qui ne fait pas 2 o/maille → REFUS "
    + "(le `dtype` annoncé n’est pas celui qui a été écrit)",
    typeof P.verifierManifeste({ dernier: { passe: PASSE } }, faux) === "string");

  // ⛔ LA BOÎTE A19 TELLE QU’ÉCRITE AU CADRAGE EST UN CAS QUI DOIT LEVER.
  const impair = manifesteFactice();
  impair.axes.nb_lat = 801;
  verifier("⛔ un compte de mailles IMPAIR → REFUS : la dernière maille du "
    + "calque couvrirait deux fois moins de terrain que ses voisines",
    typeof P.verifierManifeste({ dernier: { passe: PASSE } }, impair) === "string");

  verifier("l’âge de la passe se CALCULE, il n’est jamais publié",
    Math.abs(P.agePasseMin(man, T0 + 13 * 60_000) - 13) < 1e-9);
});

// ══════════════════════════════════════════════════════════════════════
// 4. LES PALIERS DE COULEUR
// ══════════════════════════════════════════════════════════════════════
section("4. les paliers, en mm SUR LA TRANCHE", () => {
  const p = P.PALIERS_PLUIE_MM5;
  verifier("autant de teintes que de paliers",
    P.COULEURS_PLUIE.length === p.length,
    `${P.COULEURS_PLUIE.length} teintes / ${p.length} paliers`);
  verifier("sous le premier palier → `-1`, donc rien de peint (une bruine "
    + "que le radar voit et qu’un pilote ne sent pas)",
    P.palierPluie(p[0] - 1e-6) === -1 && P.palierPluie(0) === -1);
  verifier("chaque palier est atteint EXACTEMENT à sa borne inférieure",
    p.every((v, k) => P.palierPluie(v) === k),
    p.map((v, k) => `${v}→${P.palierPluie(v)}`).join(" "));
  verifier("au-delà du dernier palier on sature, on ne déborde pas du "
    + "tableau", P.palierPluie(1e6) === P.COULEURS_PLUIE.length - 1);
  // ⛔ NaN ET Infinity ne peignent RIEN, ni l’un ni l’autre. Une valeur
  // non finie veut dire « rien à en dire » — la même règle que le
  // rafraîchissement PI. Peindre le palier maximum sur un Infinity
  // ferait une averse noire là où le décodage a déraillé.
  verifier("une valeur non finie ne peint rien, y compris `Infinity`",
    P.palierPluie(NaN) === -1 && P.palierPluie(Infinity) === -1
    && P.palierPluie(-Infinity) === -1);
  verifier("⚠️ l’équivalence horaire est une ÉQUIVALENCE, pas le décodage : "
    + "0,4 mm/5 min ↔ 4,8 mm/h",
    Math.abs(P.equivalentMmH(0.4, 5) - 4.8) < 1e-9);
});

// ══════════════════════════════════════════════════════════════════════
// 5. LE DÉCODAGE ET LE RANGE
// ══════════════════════════════════════════════════════════════════════
await sectionAsync("5. les octets : offset, longueur, et les refus nommés", async () => {
  const man = manifesteFactice();
  const c = man.service.calque;
  const n = c.nb_lat * c.nb_lon;

  // float16 : 1.0 = 0x3C00, 0.0 = 0x0000, 9.0 = 0x4880
  const brut = new Uint8Array(c.octets_par_echeance * 39);
  const dv = new DataView(brut.buffer);
  // On tatoue la PREMIÈRE maille de chaque échéance avec son rang.
  for (let r = 0; r < 39; r++) {
    dv.setUint16(r * c.octets_par_echeance, 0x3C00 + r * 0x0400, true);
  }
  const faux = async (url, init) => {
    const m = /bytes=(\d+)-(\d+)/.exec(init?.headers?.Range ?? "");
    if (!m) return { ok: true, status: 200, arrayBuffer: async () => brut.buffer };
    const a = Number(m[1]), b = Number(m[2]);
    if (b >= brut.length) return { ok: false, status: 416 };
    return { ok: true, status: 206, arrayBuffer: async () => brut.buffer.slice(a, b + 1) };
  };

  const e0 = await P.chargerEcheanceCalque(BASE, man, "j", 0, faux);
  const e7 = await P.chargerEcheanceCalque(BASE, man, "j", 7, faux);
  verifier("⛔ le Range est `rang × octets_par_echeance` : le rang 7 rend "
    + "bien les octets tatoués 7, pas ceux du rang 0",
    e0.length === n && e7.length === n && e0[0] !== e7[0],
    `rang 0 → ${e0[0]}, rang 7 → ${e7[0]}`);

  let leve = null;
  const court = async () => ({
    ok: true, status: 206,
    arrayBuffer: async () => new ArrayBuffer(c.octets_par_echeance - 2),
  });
  try { await P.chargerEcheanceCalque(BASE, man, "j", 3, court); }
  catch (e) { leve = e; }
  verifier("⛔ un 206 RABOTÉ (moins d’octets que demandé) LÈVE, il ne "
    + "dessine pas une carte à moitié vide", leve?.name === "PiafIncoherent",
    leve ? leve.message.slice(0, 50) + "…" : "rien levé");

  leve = null;
  try { await P.chargerEcheanceCalque(BASE, man, "j", 0, async () => ({ ok: false, status: 404 })); }
  catch (e) { leve = e; }
  verifier("⛔ un 404 dit LA PURGE (produit jetable), pas « erreur »",
    leve && /purg/i.test(leve.message), leve?.message?.slice(0, 50));

  leve = null;
  try { await P.chargerEcheanceCalque(BASE, man, "j", 0, async () => ({ ok: false, status: 416 })); }
  catch (e) { leve = e; }
  verifier("⛔ un 416 dit LE CACHE, pas la purge — deux causes, deux "
    + "réparations", leve && /cache/i.test(leve.message), leve?.message?.slice(0, 50));

  leve = null;
  try { await P.chargerEcheanceCalque(BASE, man, "j", 39, faux); }
  catch (e) { leve = e; }
  verifier("un rang hors des échéances publiées LÈVE avant toute requête",
    leve != null, leve?.message?.slice(0, 50));

  // ⚠️ Le tampon d’un `200` n’est pas aligné sur 2 octets par
  // construction : `decoderF16` doit tenir sur un offset IMPAIR.
  const impair = new Uint8Array(9);
  new DataView(impair.buffer).setUint16(1, 0x3C00, true);
  verifier("`decoderF16` tient sur un offset IMPAIR (DataView, pas "
    + "Uint16Array)", P.decoderF16(impair.buffer, 1, 1)[0] === 1);
});

// ══════════════════════════════════════════════════════════════════════
// 6. LA CHAÎNE DE DÉCOUVERTE — index puis manifeste, et les refus
// ══════════════════════════════════════════════════════════════════════
await sectionAsync("6. la découverte, et ses cinq refus nommés", async () => {
  const man = manifesteFactice();
  const idxOk = { dernier: { passe: PASSE }, ecrit_le: "2026-08-20T10:40:26Z" };
  const servir = (idx, m) => async (url) => {
    if (url.includes("index.json")) return { ok: true, status: 200, json: async () => idx };
    return { ok: true, status: 200, json: async () => m };
  };

  const bon = await P.chargerPluieAVenir(BASE, servir(idxOk, man), T0 + 12 * 60_000);
  verifier("une passe de 12 min est servie, et son jeton de cache vient de "
    + "l’INDEX (la seule pièce incachable)",
    bon.ok && bon.jeton === idxOk.ecrit_le, JSON.stringify(bon.jeton));

  const vieille = await P.chargerPluieAVenir(BASE, servir(idxOk, man), T0 + 55 * 60_000);
  verifier("⛔ une passe de 55 min est REFUSÉE et nommée « passe-trop-vieille » "
    + "— à cet âge, une partie des échéances est déjà du passé",
    !vieille.ok && vieille.raison === "passe-trop-vieille", vieille.raison);

  const sansDernier = await P.chargerPluieAVenir(
    BASE, servir({ runs: [{ run: PASSE }] }, man), T0);
  verifier("⛔ un index SANS `dernier` est un refus nommé — on ne va PAS "
    + "chercher la passe la plus récente de `runs`, qui peut être une "
    + "écriture partielle", !sansDernier.ok && sansDernier.raison === "index-sans-dernier",
    sansDernier.raison);

  const injoignable = await P.chargerPluieAVenir(BASE, async () => ({ ok: false, status: 503 }), T0);
  verifier("⛔ un index injoignable n’est PAS une absence de pluie, et le "
    + "texte le dit", !injoignable.ok && injoignable.raison === "index-injoignable"
    && /absence de réponse/.test(injoignable.texte), injoignable.raison);

  const decale = manifesteFactice({ passe: "2026-08-20T10:20:00Z" });
  const incoherent = await P.chargerPluieAVenir(BASE, servir(idxOk, decale), T0 + 5 * 60_000);
  verifier("⛔ manifeste d’une passe / index d’une autre → refus nommé "
    + "« manifeste-incoherent », AVANT la moindre lecture d’octets",
    !incoherent.ok && incoherent.raison === "manifeste-incoherent", incoherent.raison);

  const a = P.aEcrirePluie(man);
  verifier("les phrases de l’écran sont construites DEPUIS le manifeste "
    + "(maille, règle de réduction, cadence, rétention, coût)",
    a.maille.includes("0.02") && /MAXIMUM/.test(a.reduction)
    && a.cadence.includes("5") && a.cadence.includes("10"),
    a.maille.slice(0, 40) + "…");
});

// ══════════════════════════════════════════════════════════════════════
// 7. LA COUPE — la colonne, et l'agrégat horaire            (Lot Q4)
// ══════════════════════════════════════════════════════════════════════
await sectionAsync("7. la coupe : la colonne et l'agrégat horaire", async () => {
  const man = manifesteFactice({
    heures_entieres: [
      { heure: new Date(T0 + 30 * 60_000).toISOString().replace(".000", ""),
        rangs: [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17],
        debut_min: 30, fin_min: 90 },
      { heure: new Date(T0 + 90 * 60_000).toISOString().replace(".000", ""),
        rangs: [18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29],
        debut_min: 90, fin_min: 150 },
    ],
  });
  man.service.coupe.domaines = {
    "nord-alpes": { nb_lat: 276, nb_lon: 261, lat_premier: 46.45, lat_dernier: 43.7, lon_premier: 5.0, lon_dernier: 7.6 },
    "pyrenees": { nb_lat: 101, nb_lon: 511, lat_premier: 43.4, lat_dernier: 42.4, lon_premier: -1.8, lon_dernier: 3.3 },
  };

  const pt = P.domaineCoupePiaf(man, 45.9, 6.2);
  verifier("un point alpin tombe dans `nord-alpes`, et le point RENDU est "
    + "celui qui est SERVI, pas celui qui a été demandé",
    pt && pt.domaine === "nord-alpes" && Math.abs(pt.lat - 45.9) < 1e-9
    && Math.abs(pt.lon - 6.2) < 1e-9, JSON.stringify(pt));

  verifier("⛔ hors des domaines de la coupe → `null` : c'est le refus "
    + "« hors emprise », EXACTEMENT celui du produit B — Innsbruck n'y est "
    + "pas", P.domaineCoupePiaf(man, 47.27, 11.4) === null);

  verifier("⚠️ le pas natif n'est pas publié partout dans la BOÎTE : un "
    + "point de la boîte hors des domaines est dans le calque et hors de "
    + "la coupe, et les deux refus sont distincts",
    P.dansBoite(man, 48.85, 2.35) && P.domaineCoupePiaf(man, 48.85, 2.35) === null);

  // Une colonne fabriquée : 39 valeurs, 0,1 mm sur les rangs 6→17.
  const col = new Float32Array(39);
  for (let r = 6; r <= 17; r++) col[r] = 0.1;
  for (let r = 18; r <= 29; r++) col[r] = 0.25;

  const heures = P.agregatHorairePiaf(man, col);
  verifier("⛔ l'agrégat SOMME les 12 rangs que le MANIFESTE désigne, sans "
    + "conversion ni division — 12 × 0,1 = 1,2 mm",
    heures.length === 2 && Math.abs(heures[0].mm - 1.2) < 1e-6
    && Math.abs(heures[1].mm - 3.0) < 1e-6,
    heures.map(h => h.mm.toFixed(2)).join(" · "));

  verifier("⛔ l'heure ronde est un epoch ENTIER — c'est ce qui autorise "
    + "l'agrégat dans une Map indexée par instant, là où le pas de 5 min "
    + "ne le serait pas", heures.every(h => Number.isInteger(h.heureMs)));

  const troue = new Float32Array(col);
  troue[11] = NaN;
  const h2 = P.agregatHorairePiaf(man, troue);
  verifier("⛔ UN SEUL rang non fini suffit à retirer l'heure : une somme "
    + "de onze douzièmes d'heure n'est pas une heure, et rien ne le dirait "
    + "à l'écran", h2.length === 1 && Math.abs(h2[0].mm - 3.0) < 1e-6,
    `${h2.length} heure(s) rendue(s)`);
  verifier("⚠️ …et l'heure retirée est bien la TROUÉE, pas l'autre",
    h2.length === 1 && h2[0].heureMs === Date.parse(man.heures_entieres[1].heure));

  const sans = P.agregatHorairePiaf(manifesteFactice(), col);
  verifier("⛔ une passe dont AUCUNE heure ronde n'est entièrement "
    + "couverte n'en rend aucune — on ne complète pas une heure à cheval",
    sans.length === 0);

  const ruban = P.rubanPiaf(man, col);
  verifier("le ruban porte les 39 tranches, et l'instant NOMMÉ de chacune "
    + "est sa FIN", ruban.length === 39
    && ruban[0].finMs === T0 + 5 * 60_000
    && ruban[0].debutMs === T0);
  verifier("le cumul du ruban est la somme des tranches finies",
    Math.abs(P.cumulRuban(ruban) - 4.2) < 1e-6, P.cumulRuban(ruban).toFixed(3));

  // Le Range de la colonne : offset et refus.
  const cp = man.service.coupe;
  const d = cp.domaines["nord-alpes"];
  const brut = new Uint8Array(d.nb_lat * d.nb_lon * cp.octets_par_colonne);
  const dv = new DataView(brut.buffer);
  const attendu = (pt.j * d.nb_lon + pt.i) * cp.octets_par_colonne;
  dv.setUint16(attendu, 0x3C00, true);        // 1.0 sur le rang 0
  let vuOffset = -1;
  const faux = async (url, init) => {
    const m = /bytes=(\d+)-(\d+)/.exec(init?.headers?.Range ?? "");
    vuOffset = Number(m[1]);
    return { ok: true, status: 206,
      arrayBuffer: async () => brut.buffer.slice(Number(m[1]), Number(m[2]) + 1) };
  };
  const lue = await P.chargerColonnePiaf(BASE, man, "j", pt, faux);
  verifier("⛔ l'offset de colonne est `(j × nb_lon + i) × octets_par_colonne`, "
    + "et la valeur tatouée sort au rang 0",
    vuOffset === attendu && lue.length === 39 && lue[0] === 1,
    `offset ${vuOffset} (attendu ${attendu})`);

  let leve = null;
  const desaccord = manifesteFactice({
    heures_entieres: [],
  });
  desaccord.service.coupe.domaines = man.service.coupe.domaines;
  desaccord.service.coupe.octets_par_colonne = 50;   // 25 valeurs, pas 39
  try { await P.chargerColonnePiaf(BASE, desaccord, "j", pt, async () => ({
    ok: true, status: 206, arrayBuffer: async () => new ArrayBuffer(50) })); }
  catch (e) { leve = e; }
  verifier("⛔ une colonne dont le nombre de valeurs ne correspond PAS à "
    + "l'axe publié LÈVE — sinon elle se lit décalée, sans erreur",
    leve?.name === "PiafIncoherent", leve?.message?.slice(0, 60));
});

// ══════════════════════════════════════════════════════════════════════
// 8. ⛔⛔ L'AXE EN MINUTES — le piège d'arithmétique du §5 du cadrage
// ══════════════════════════════════════════════════════════════════════
section("8. l'axe en MINUTES, jamais en heures", () => {
  // La preuve du danger, refaite ici et pas recopiée : c'est la SEULE
  // façon que ce contrôle reste vrai si quelqu'un change le pas.
  let nonEntiers = 0, total = 0;
  const exemples = [];
  for (let m = 0; m <= 3120; m += 5) {
    total++;
    const parLesHeures = (m / 60) * 3_600_000;
    if (!Number.isInteger(parLesHeures)) {
      nonEntiers++;
      if (exemples.length < 3) exemples.push(`${m} min → ${parLesHeures}`);
    }
  }
  verifier("⛔ passer par les HEURES (`m / 60`, puis `h × 3 600 000`) donne "
    + "un epoch NON ENTIER 81 fois sur 625 au pas de 5 min — c'est mesuré, "
    + "pas supposé", nonEntiers === 81 && total === 625,
    `${nonEntiers}/${total} · ${exemples.join(" · ")}`);

  let n15 = 0, t15 = 0;
  for (let m = 0; m <= 3120; m += 15) { t15++; if (!Number.isInteger((m / 60) * 3_600_000)) n15++; }
  verifier("⚠️ et le MÊME calcul est EXACT au pas de 15 min : 0,25 est "
    + "représentable en binaire. Une conversion juste pour un pas ne l'est "
    + "pas pour le suivant, et elle ne prévient pas",
    n15 === 0 && t15 === 209, `${n15}/${t15} non entier(s)`);

  let faux = 0;
  for (let m = 0; m <= 3120; m += 5) {
    if (!Number.isInteger(P.instantDeMinute(T0, m))) faux++;
  }
  verifier("⛔⛔ `instantDeMinute` (minutes × 60 000, deux entiers) est "
    + "EXACT sur les 625 offsets — c'est la seule fabrique d'instant de ce "
    + "lot", faux === 0, `${faux} epoch(s) non entier(s)`);

  // ══════════════════════════════════════════════════════════════════
  // ⓘ ET MAINTENANT LA NUANCE QUE CE BANC A TROUVÉE LE 20/08, ET QUI
  //   DÉMENT À MOITIÉ LE §5 DU CADRAGE.
  //
  //   Le §5 concluait : « tout ce qui indexe par epoch exact —
  //   `precipNearKmByTs`, `wstarByTs` — manquerait ces instants ». Mesuré
  //   ici : **c'est faux tant que l'epoch est ABSOLU**. À la magnitude
  //   d'un epoch de 2026 (~1,79 × 10¹²), l'écart entre deux doubles
  //   voisins vaut 0,000 244 ms ; l'erreur d'arrondi de `h × 3 600 000`
  //   plafonne à ~3 × 10⁻⁸ ms. Elle est donc AVALÉE par l'addition, avec
  //   une marge d'environ quatre mille. `t0 + h × 3 600 000` retombe
  //   exactement sur `t0 + m × 60 000`, aux 625 offsets.
  //
  //   Le danger est réel ailleurs : dès qu'un OFFSET RELATIF en ms sert
  //   de clé (une durée, un delta, un axe qui part de zéro), il n'y a
  //   plus de grand nombre pour absorber l'erreur, et les 81 collisions
  //   manquées reviennent — c'est ce que prouve la seconde Map.
  //
  //   ⇒ On garde la voie des MINUTES quand même, et ce n'est pas de la
  //   superstition : elle est exacte PAR CONSTRUCTION, là où l'autre
  //   n'est sauve que par une coïncidence de magnitude qu'aucune ligne
  //   de code ne surveille. Mais on n'écrit pas que le bug existait
  //   là où il n'existait pas.
  // ══════════════════════════════════════════════════════════════════
  const absolus = new Map();
  const relatifs = new Map();
  for (let m = 0; m <= 3120; m += 5) {
    absolus.set(T0 + (m / 60) * 3_600_000, m);
    relatifs.set((m / 60) * 3_600_000, m);
  }
  let rateAbsolu = 0, rateRelatif = 0;
  for (let m = 0; m <= 3120; m += 5) {
    if (!absolus.has(T0 + m * 60_000)) rateAbsolu++;
    if (!relatifs.has(m * 60_000)) rateRelatif++;
  }
  verifier("ⓘ sur un epoch ABSOLU, l'erreur est avalée par l'addition "
    + "(0,000 244 ms d'écart entre deux doubles à cette magnitude contre "
    + "3 × 10⁻⁸ d'erreur) : la Map ne rate RIEN. Le §5 du cadrage était "
    + "trop affirmatif sur ce point",
    rateAbsolu === 0, `${rateAbsolu} instant(s) raté(s) sur 625`);
  verifier("⛔ mais sur un OFFSET RELATIF en ms, il n'y a plus de grand "
    + "nombre pour l'absorber : la Map rate bien 81 instants sur 625",
    rateRelatif === 81, `${rateRelatif} instant(s) raté(s) sur 625`);
  verifier("⛔⛔ et la voie des minutes est exacte DANS LES DEUX CAS — "
    + "elle ne dépend d'aucune coïncidence de magnitude", faux === 0);
});

// ══════════════════════════════════════════════════════════════════════
// 9. LES OCTETS SERVIS — la seule vérification qui compte  (--production)
// ══════════════════════════════════════════════════════════════════════
if (!PROD) {
  console.log("\n── 9. les octets servis : SAUTÉE (relancer avec --production)");
} else {
  await sectionAsync("9. les octets SERVIS, en production", async () => {
    const etat = await P.chargerPluieAVenir(BASE, fetch, Date.now());
    verifier("la chaîne sert", etat.ok, etat.ok ? etat.man.passe : etat.texte);
    if (!etat.ok) return;
    const man = etat.man;
    const age = P.agePasseMin(man, Date.now());
    verifier("l’âge de la passe est sous la cadence de la chaîne + sa "
      + "latence", age < 25, `${age.toFixed(1)} min`);

    const rang = 5;
    const mm = await P.chargerEcheanceCalque(BASE, man, etat.jeton, rang, fetch);
    const c = man.service.calque;
    verifier("l’échéance décodée a exactement nb_lat × nb_lon mailles",
      mm.length === c.nb_lat * c.nb_lon, `${mm.length}`);
    let max = 0, pluvieuses = 0;
    for (const v of mm) { if (v > max) max = v; if (v > 0.05) pluvieuses++; }
    verifier("les valeurs sont physiquement plausibles (< 100 mm sur une "
      + "tranche de 5 min — le plafond du banc serveur)", max < 100,
      `max ${max.toFixed(3)} mm, ${pluvieuses} maille(s) pluvieuse(s)`);

    // ⛔⛔ LE CONTRÔLE DU LOT : le calque ne SOUS-ESTIME jamais la coupe.
    // Il est réduit par MAXIMUM de bloc 2×2 : à la maille qui contient un
    // point, sa valeur doit être ≥ celle de la colonne à ce point.
    const cp = man.service.coupe;
    // ⚠️ ON TIRE LES TROIS OBJETS DE COLONNES ENTIERS (11 Mo) plutôt
    // qu’un damier de Range : un damier de 81 points par domaine avait
    // ramené UNE seule maille pluvieuse le 20/08, donc un contrôle
    // pratiquement vide. Le prix d’un banc qui prouve quelque chose est
    // ici de trois requêtes, une fois par exécution.
    const noms = Object.keys(cp.domaines);
    let comptees = 0, pluie = 0, viole = 0, pire = 0, absents = 0;
    for (const nom of noms) {
      const d = cp.domaines[nom];
      const cle = P.avecJetonPiaf(`${BASE}/${cp.gabarit_cle.replace("{domaine}", nom)}`, etat.jeton);
      const r = await fetch(cle);
      if (!r.ok) { absents++; continue; }
      const buf = await r.arrayBuffer();
      const attendu = d.nb_lat * d.nb_lon * cp.octets_par_colonne;
      if (buf.byteLength !== attendu) { absents++; continue; }
      for (let j = 0; j < d.nb_lat; j++) {
        const lat = d.lat_premier - j * cp.pas_deg;
        for (let i = 0; i < d.nb_lon; i++) {
          const lon = d.lon_premier + i * cp.pas_deg;
          const m = P.mailleCalque(man, lat, lon);
          if (!m) { viole++; continue; }
          const v = P.decoderF16(buf, (j * d.nb_lon + i) * cp.octets_par_colonne + rang * 2, 1)[0];
          const calque = mm[m.j * c.nb_lon + m.i];
          comptees++;
          if (v > 0.05) pluie++;
          if (v - calque > 1e-6) { viole++; pire = Math.max(pire, v - calque); }
        }
      }
    }
    verifier("les trois objets de colonnes ont exactement la taille que le "
      + "manifeste décrit", absents === 0, `${absents} objet(s) écarté(s)`);

    // ── L'AGRÉGAT HORAIRE, SUR UNE VRAIE COLONNE (Lot Q4) ──────────
    const pt = P.domaineCoupePiaf(man, 45.90, 6.20);
    verifier("un point alpin trouve sa colonne dans la passe en ligne",
      pt != null, JSON.stringify(pt));
    if (pt) {
      const col = await P.chargerColonnePiaf(BASE, man, etat.jeton, pt, fetch);
      verifier("la colonne servie porte exactement une valeur par échéance",
        col.length === man.echeances.length, `${col.length}`);
      const hh = P.agregatHorairePiaf(man, col);
      // ⛔ LE MANIFESTE DÉSIGNE LES RANGS, ON NE LES RECALCULE PAS —
      // mais on VÉRIFIE que la somme rendue est bien celle de ces
      // rangs-là, sur les octets servis. Recalculer différemment est le
      // vrai risque ; ne jamais recalculer du tout empêche de le voir.
      const bon = hh.every(h => {
        let s = 0;
        for (const r of h.rangs) s += col[r];
        return Math.abs(s - h.mm) < 1e-6 && h.rangs.length === 12;
      });
      verifier("⛔ chaque heure agrégée est la SOMME des 12 rangs que le "
        + "manifeste désigne, et de ceux-là seulement", bon,
        hh.map(h => `${new Date(h.heureMs).toISOString().slice(11, 16)} = `
          + `${h.mm.toFixed(2)} mm (${h.rangs.length} rangs)`).join(" · ")
        || "aucune heure entièrement couverte par cette passe");
      verifier("⚠️ les heures rondes NON entièrement couvertes sont "
        + "absentes — sur 195 min à partir d'une passe quelconque, il y en "
        + "a au plus 3",
        hh.length <= 3 && hh.every(h => Number.isInteger(h.heureMs)),
        `${hh.length} heure(s)`);
      const rub = P.rubanPiaf(man, col);
      verifier("⛔ le ruban de la coupe et le calque ne se contredisent "
        + "pas : à ce point, la valeur du calque est ≥ celle du ruban au "
        + "même rang (réduction par MAXIMUM)",
        (() => {
          const m = P.mailleCalque(man, pt.lat, pt.lon);
          return m != null && mm[m.j * c.nb_lon + m.i] >= rub[rang].mm - 1e-6;
        })(),
        `ruban rang ${rang} = ${rub[rang].mm.toFixed(3)} mm`);
    }
    // ⛔ LE COMPTE DE MAILLES PLUVIEUSES EST PUBLIÉ, ET UN CONTRÔLE VIDE
    // N’EST PAS UN CONTRÔLE VERT. Zéro ≥ zéro est vrai quel que soit
    // l’offset : sans une goutte dedans, ce contrôle aurait été aussi
    // vert avec deux jeux totalement décalés (Lot Q2, §5).
    if (pluie === 0) {
      console.log(`  ⓘ CONTRÔLE VIDE : ${comptees} maille(s) confrontée(s), `
        + `aucune pluvieuse. Il ne prouve rien aujourd’hui — à rejouer par `
        + `temps de pluie.`);
    } else {
      verifier("⛔⛔ le calque ne SOUS-ESTIME jamais la coupe : à chaque "
        + "point, `carte.bin ≥ colonnes.bin` — la réduction par MAXIMUM "
        + "tient sur les octets SERVIS", viole === 0,
        `n = ${comptees}, dont ${pluie} pluvieuse(s), ${viole} violation(s), `
        + `pire écart ${pire.toExponential(2)} mm`);
    }
  });
}

// ══════════════════════════════════════════════════════════════════════
console.log(`\n${echecs ? "✗" : "✓"} ${echecs} contrôle(s) au rouge`
  + `${echecs ? ` : ${rouges.join(" · ")}` : ""}`);
process.exit(echecs ? 1 : 0);
