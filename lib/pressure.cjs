// ══════════════════════════════════════════════════════════════════
//  ⚠️  FICHIER GÉNÉRÉ — NE PAS ÉDITER À LA MAIN.
//
//  Toute modification faite ici sera écrasée, et — bien pire —
//  ferait diverger la physique du serveur de celle de la fiche.
//  Ce sont les deux moitiés d'une même promesse faite au pilote :
//  elles doivent sortir du même code.
//
//  Source unique : PWA/web/src/lib/pressure.ts (+ 2 fonctions
//  d'appariement). Pour modifier la physique, on modifie LÀ-BAS,
//  puis :
//
//    cd PWA/web && node scripts/build-pressure-portable.mjs
//
//  Contrôle de dérive (échoue si ce fichier ne correspond plus) :
//
//    cd PWA/balise-watch-server && node tools/verify-pressure-sync.mjs
//
//  Provenance :
//   src/lib/pressure.ts  intégral  sha256:babfed60395ed60e
//   src/lib/utils.ts  haversineKm  sha256:c5d6d5bbe0db873f
//   src/lib/phenomena.ts  pickStationFor  sha256:31f36ca192cb9abc
//   src/lib/phenomena.ts  resolveAnchors  sha256:fb91b428c29b9153
// ══════════════════════════════════════════════════════════════════
// ─── src/lib/pressure.ts (intégral) ───
// ══════════════════════════════════════════════════════════════════
//  pressure — la pression réduite au niveau de la mer, et rien d'autre
//  (Lot 1 de la refonte « Phénomènes de gradient », 03/08/2026)
//
//  Socle du module foehn v2 : cf. PROMPT_REPRISE_FOEHN_V2.md §3.
//  Extrait de lib/foehn.ts, qui mélangeait trois métiers (physique de la
//  pression, modèle de phénomène, appariement de stations). Ici : le
//  premier seulement. Aucune dépendance React, aucun appel réseau —
//  fonctions pures, vérifiables (scripts/verify-pressure.mjs).
//
//  ⚠️ LA RAISON D'ÊTRE DE CE FICHIER, en une phrase : il existe DEUX
//  réductions au niveau de la mer, et les mélanger dans un même Δ
//  introduit un biais CORRÉLÉ au foehn qu'on prétend mesurer.
//
//    • QFF — réduction avec la température RÉELLE de la station.
//      Sources : Météo-France `pmer`, AEMET `pres_nmar`,
//      MeteoSuisse `pp0qffs0`.
//    • QNH — réduction avec l'ATMOSPHÈRE STANDARD (ISA : 15 °C au
//      niveau mer, −6,5 °C/km), arrondie au hPa entier.
//      Source : METAR `altim` — c'est-à-dire TOUTE l'Italie, faute de
//      réseau régional italien publiant de la pression (vérifié le
//      03/08/2026, cf. §2.1 du document de conception).
//
//  Mesuré sur des relevés réels du 03/08/2026, hors épisode de foehn :
//  l'axe Annecy–Aoste donne Δ = −2,00 hPa en QNH brut contre −0,43 hPa
//  une fois les deux extrémités ramenées en QFF. Le brut surestimait le
//  signal de 1,6 hPa — 40 % du seuil de vigilance — précisément parce
//  qu'Aoste était plus chaude et plus haute qu'Annecy. Entre deux
//  stations de même altitude (400 m) séparées par 15 K, l'artefact
//  atteint 2,4 hPa.
//
//  D'où la règle appliquée partout ici : on ne compare JAMAIS deux
//  pressions de conventions différentes. On convertit tout en QFF, et
//  quand on ne peut pas convertir (température manquante), on renvoie
//  `null` plutôt qu'une valeur trompeuse.
//
//  ⚠️ CE FICHIER N'IMPORTE RIEN, ET C'EST VOLONTAIRE. C'est ce qui
//  permet à scripts/verify-pressure.mjs de l'exécuter directement sous
//  Node (type stripping natif) sans compilation ni runner de test :
//  Node ne résout pas les imports relatifs sans extension comme le fait
//  Vite, donc le moindre `import ... from './utils'` rendrait le module
//  invérifiable hors navigateur. Conséquence assumée : l'appariement
//  point → station (qui a besoin de `haversineKm`) vit dans
//  lib/phenomena.ts, pas ici. La physique n'a pas de dépendance,
//  l'appariement en a une — la frontière tombe exactement là.
//  Avant d'ajouter un import ici, relire ce paragraphe.
// ══════════════════════════════════════════════════════════════════

// ── Constantes physiques ──────────────────────────────────────────
/** Température au niveau de la mer en atmosphère standard ISA (K). */
const ISA_T0 = 288.15;
/** Gradient thermique standard (K/m). */
const ISA_LAPSE = 0.0065;
/** Exposant barométrique ISA = g / (R_d · lapse). */
const ISA_EXP = 5.25588;
/** Accélération de la pesanteur (m/s²). */
const G = 9.80665;
/** Constante spécifique de l'air sec (J/(kg·K)). */
const R_D = 287.05;

/**
 * Incertitude résiduelle de la conversion QNH → QFF (hPa).
 *
 * Il existe plusieurs variantes de la formule QFF selon les services
 * (correction d'humidité, moyenne avec la température d'il y a 12 h…).
 * Notre QFF converti ne coïncide donc pas EXACTEMENT avec le `pmer` de
 * Météo-France ni le `pp0qffs0` de MeteoSuisse. L'écart est de l'ordre
 * de 0,1–0,3 hPa — un ordre de grandeur sous les 2,4 hPa que la
 * conversion élimine. On l'assume et on l'affiche, on ne le cache pas.
 */
const QFF_CONVERSION_UNCERTAINTY_HPA = 0.3;

/** Incertitude plancher d'une pression publiée nativement en QFF (hPa). */
const QFF_NATIVE_UNCERTAINTY_HPA = 0.05;

/**
 * Altitude au-delà de laquelle AUCUNE réduction au niveau de la mer
 * n'est exploitable (m). Reprise à l'identique de FOEHN_MF_MAX_ALT
 * (lib/foehn.ts, 17/07/2026) — le seuil était déjà juste, il est
 * simplement déplacé là où il a sa place.
 *
 * Vérification en direct le 03/08/2026 : Samedan (LSZS, 1708 m)
 * annonçait Q1025 quand toute la Suisse était entre Q1013 et Q1018 ; et
 * même après conversion en QFF il reste 2 à 3 hPa au-dessus de ses
 * voisins. Ce n'est pas une précaution, c'est une nécessité.
 */
const PRESSURE_MAX_ALT = 1000;

/**
 * Altitude à partir de laquelle on AVERTIT sans écarter (m). Entre 600
 * et PRESSURE_MAX_ALT la réduction reste utilisable mais une partie du
 * Δ avec la plaine devient topographique plutôt que synoptique — ex.
 * LIMK Torino/Bric della Croce à 693 m, station de colline.
 */
const PRESSURE_WARN_ALT = 600;

/** Rayon max d'appariement point → station de pression (km). */
const PRESSURE_MAX_KM = 25;

/**
 * Pénalité de distance appliquée à une station QNH face à une station
 * QFF. Une station QNH doit être DEUX FOIS plus proche pour être
 * préférée : la conversion coûte 0,3 hPa d'incertitude et la
 * quantification au hPa entier en coûte 0,5 de plus, alors qu'une
 * station QFF native est propre d'emblée. Un facteur plutôt qu'un tri
 * strict par convention — sinon on irait chercher un QFF à 24 km en
 * ignorant un QNH à 1 km, ce qui serait pire.
 */
const QNH_DISTANCE_PENALTY = 2;

// ── Types ─────────────────────────────────────────────────────────

/** Convention de réduction au niveau de la mer d'une source. */
                                              

/**
 * D'où vient la mesure. `model` est réservé au champ `pressure_msl`
 * d'Open-Meteo — il n'est PAS mélangé aux relevés réels, il constitue sa
 * propre série (règle projet : ne jamais présenter une prévision comme
 * une observation).
 */
                                
                                                                     

/**
 * Une balise de pression, telle que servie par `GET /pressure-stations`.
 *
 * ⚠️ Les noms de champs `nom` et `alt` ne sont pas un anglicisme raté :
 * c'est la convention du projet, partagée par `MfStation`, `AemetStation`
 * et la forme renvoyée par le serveur. Les faire diverger ici imposerait
 * un adaptateur à chaque site d'appel — et un adaptateur, c'est un
 * endroit où se tromper de champ sans que le typage le voie.
 *
 * Le référentiel de ces stations n'est PAS en base : il vit dans les
 * listes `METAR_ANCHORS` / `SMN_ANCHORS` du serveur, seule source de
 * vérité (cf. PROMPT_REPRISE_FOEHN_V2.md §4, décision (b)).
 */
                                  
                                                                                 
             
                             
               
              
              
              
                                                                          
              
                               
                                                                       
                        
                                                                          
                   
 

/** Un relevé courant renvoyé avec la station par `/pressure-stations`. */
                                                                 
                                                                                     
                          
                                                                       
                       
     
                                                 
    
                                                                  
                                                                        
                                                                   
                                                                   
                   
     
                    
                    
     
                                             
    
                                                                       
                                     
                                                                       
                                                                        
                                                                     
                                                                     
                                                                   
                                       
                                                                
                                         
     
                     
     
                                                                 
    
                                                                        
                                                                    
                                                                    
                                                                   
                                                                   
                                                             
     
                      
                                         
            
 

/** Un relevé brut, tel que publié par sa source. */
                                  
                                                                            
              
                               
                                    
               
                                                                       
                       
                                  
                        
                               
            
 

/** Un relevé ramené en QFF, avec ce qu'on sait de sa fiabilité. */
                                     
                                                                
                     
                                                           
                         
                                                          
                     
                                                                         
                                  
 

/** Un Δ de pression et son incertitude combinée. */
                                
                                                                     
                       
                                                   
                         
 

// ── Conversions (§3 du document de conception) ────────────────────

/**
 * QNH → pression station, en remontant l'atmosphère standard ISA.
 * C'est l'inverse exact de la définition du QNH : le calage altimétrique
 * qui, en atmosphère standard, ferait afficher l'altitude du terrain.
 *
 * @param qnh  hPa (METAR `altim`)
 * @param elev altitude de la station en m
 */
function qnhToStation(qnh        , elev        )         {
  return qnh * Math.pow(1 - (ISA_LAPSE * elev) / ISA_T0, ISA_EXP);
}

/**
 * Pression station → QFF, en descendant une colonne d'air à la
 * température RÉELLE (et non standard). C'est toute la différence :
 * la colonne fictive sous une station est plus légère quand il fait
 * chaud, donc la réduction est plus faible — d'où l'écart avec le QNH,
 * qui suppose toujours la même colonne.
 *
 * `T_moy` approxime la température moyenne de la colonne fictive par la
 * température de la station corrigée d'un demi-gradient standard.
 *
 * @param pSta  pression station en hPa
 * @param elev  altitude de la station en m
 * @param tempC température de la station en °C
 */
function stationToQff(pSta        , elev        , tempC        )         {
  const tMean = tempC + 273.15 + (ISA_LAPSE * elev) / 2;
  return pSta * Math.exp((G * elev) / (R_D * tMean));
}

/** QNH → QFF en une passe (enchaîne les deux fonctions ci-dessus). */
function qnhToQff(qnh        , elev        , tempC        )         {
  return stationToQff(qnhToStation(qnh, elev), elev, tempC);
}

/**
 * Ramène n'importe quel relevé en QFF, avec son incertitude.
 *
 * Deux refus explicites, tous deux volontaires — mieux vaut pas de
 * chiffre qu'un chiffre faux :
 *  • station au-dessus de PRESSURE_MAX_ALT → `too-high` ;
 *  • QNH sans température → `no-temp`. On ne se rabat SURTOUT PAS sur
 *    le QNH brut « faute de mieux » : ce serait exactement le mélange de
 *    conventions que ce fichier existe pour empêcher.
 */
function normalizePressure(
  r                 ,
  maxAlt = PRESSURE_MAX_ALT,
)                     {
  const quantization = Math.max(r.resolutionHpa / 2, QFF_NATIVE_UNCERTAINTY_HPA);

  if (r.elev > maxAlt) {
    return { qff: null, uncertaintyHpa: quantization, converted: false, reason: 'too-high' };
  }
  if (r.reduction === 'qff') {
    return { qff: r.raw, uncertaintyHpa: quantization, converted: false };
  }
  if (r.tempC == null) {
    return { qff: null, uncertaintyHpa: quantization, converted: false, reason: 'no-temp' };
  }
  // L'erreur de quantification traverse la conversion quasiment à
  // l'identique ; on lui ajoute en quadrature le résidu de formule.
  const u = Math.hypot(quantization, QFF_CONVERSION_UNCERTAINTY_HPA);
  return { qff: qnhToQff(r.raw, r.elev, r.tempC), uncertaintyHpa: u, converted: true };
}

/**
 * Δ = QFF(A) − QFF(B) et son incertitude combinée.
 *
 * Convention de signe INCHANGÉE depuis la v1 (lib/foehn.ts) : A est le
 * versant surveillé, B le réservoir. Δ NÉGATIF → B plus haut → le vent
 * redescend vers A.
 */
function pressureDelta(a                    , b                    )                {
  const uncertaintyHpa = Math.hypot(a.uncertaintyHpa, b.uncertaintyHpa);
  if (a.qff == null || b.qff == null) return { delta: null, uncertaintyHpa };
  return { delta: a.qff - b.qff, uncertaintyHpa };
}

// ── Lissage (mitigation de la quantification METAR) ───────────────

/**
 * Moyenne glissante centrée sur `window` points, en ignorant les trous.
 *
 * Sert au QNH METAR, arrondi au hPa entier : sur un seuil de vigilance
 * à 4 hPa, ±0,5 hPa par extrémité représente 25 % du seuil. Trois
 * relevés successifs suffisent à diviser cette dispersion par ~1,7 sans
 * lisser le signal synoptique lui-même (qui évolue en heures, pas en
 * dizaines de minutes).
 *
 * Ne comble PAS les trous : un pas sans donnée reste null (les terrains
 * METAR fermés la nuit doivent se voir, pas s'interpoler).
 */
function smoothPressureSeries(
  values                            ,
  window = 3,
)                    {
  const half = Math.floor(window / 2);
  return values.map((v, i) => {
    if (v == null) return null;
    let sum = 0;
    let n = 0;
    for (let j = i - half; j <= i + half; j++) {
      const w = values[j];
      if (j >= 0 && j < values.length && w != null) { sum += w; n++; }
    }
    return n > 0 ? sum / n : null;
  });
}

// ── Appariement point → station : PAS ICI ─────────────────────────
//  `pickStationFor` (remplaçant de `nearestFoehnStation`, qui ne
//  regardait que le réseau Météo-France — d'où le fait qu'AUCUN des 8
//  axes présets ne pouvait afficher sa courbe réelle) a besoin de
//  `haversineKm`, donc d'un import, donc il vit dans lib/phenomena.ts
//  (lot 3). Voir l'avertissement en tête de fichier.
//
//  Les constantes qui pilotent cet appariement restent ici, parce que
//  ce sont des propriétés de la MESURE, pas de l'appariement :
//  PRESSURE_MAX_KM, PRESSURE_MAX_ALT, PRESSURE_WARN_ALT et
//  QNH_DISTANCE_PENALTY. `phenomena.ts` les importe.

// ── Adaptateurs de sources ────────────────────────────────────────
//  Deux fabriques plutôt qu'un objet littéral au site d'appel : elles
//  rendent la convention EXPLICITE. Un `PressureReading` construit à la
//  main peut se tromper de `reduction` sans que rien ne le signale ; ces
//  fonctions, non.

/**
 * Relevé issu d'une source publiant nativement du QFF : Météo-France
 * (`pmer`), AEMET (`pres_nmar`), MeteoSuisse (`pp0qffs0`).
 * Aucune température requise — il n'y a rien à convertir.
 */
function readingFromQff(
  qff        ,
  elev        ,
  t        ,
  resolutionHpa = 0.1,
)                  {
  return { raw: qff, reduction: 'qff', elev, tempC: null, resolutionHpa, t };
}

/**
 * Relevé issu d'un METAR (`altim` = QNH, arrondi au hPa entier).
 * `tempC` vient du même METAR (champ `temp`) : si elle manque, la
 * normalisation refusera de convertir — c'est voulu.
 */
function readingFromMetar(
  qnh        ,
  elev        ,
  tempC               ,
  t        ,
)                  {
  return { raw: qnh, reduction: 'qnh', elev, tempC, resolutionHpa: 1, t };
}

/**
 * Relevé à partir d'une entrée de `GET /pressure-stations`, quelle que
 * soit sa source. C'est le chemin normal : le serveur transmet déjà la
 * convention, la résolution, l'altitude et la température, il n'y a donc
 * rien à deviner. Renvoie null si la station n'a pas de valeur de
 * pression à cet instant (terrain METAR fermé la nuit, capteur en panne).
 */
function readingFromStation(s                        )                         {
  if (s.pressure == null) return null;
  return {
    raw: s.pressure,
    reduction: s.reduction,
    elev: s.alt,
    tempC: s.tempC,
    resolutionHpa: s.resolutionHpa,
    t: s.t,
  };
}

// ── Lot 5 — série de Δ observés ───────────────────────────────────

/** Un point de la courbe observée : Δ et son incertitude, à un instant. */
                             
            
                                
                
                                        
                         
 

/**
 * Δ observé au cours du temps, à partir des deux historiques bruts.
 *
 * Les deux séries ne sont PAS synchrones — METAR toutes les 20 à 30 min
 * (parfois 3 h à Valence-Chabeuil), SwissMetNet toutes les 10 min, AEMET
 * toutes les heures. On apparie donc chaque point de A au point de B le
 * plus proche dans le temps, et on REFUSE la paire au-delà de
 * `toleranceMs`.
 *
 * Refuser plutôt qu'interpoler est un choix : un Δ calculé entre deux
 * instants éloignés n'est pas une mesure bruitée, c'est une mesure
 * d'autre chose. Un trou dans la courbe se voit et s'interprète ; un
 * point interpolé se croit.
 *
 * Chaque point est normalisé AVANT soustraction (conversion QNH→QFF si
 * nécessaire), jamais après : c'est tout le propos du §3 du document de
 * conception.
 */
function deltaSeries(
  a                            ,
  b                            ,
  toleranceMs = 45 * 60 * 1000,
)               {
  if (!a.length || !b.length) return [];
  const sortedB = [...b].sort((x, y) => x.t - y.t);
  const out               = [];

  for (const ra of [...a].sort((x, y) => x.t - y.t)) {
    // Recherche dichotomique du voisin temporel le plus proche dans B.
    let lo = 0, hi = sortedB.length - 1, best = sortedB[0];
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (Math.abs(sortedB[mid].t - ra.t) < Math.abs(best.t - ra.t)) best = sortedB[mid];
      if (sortedB[mid].t < ra.t) lo = mid + 1; else hi = mid - 1;
    }
    if (Math.abs(best.t - ra.t) > toleranceMs) continue;

    const na = normalizePressure(ra);
    const nb = normalizePressure(best);
    const d = pressureDelta(na, nb);
    if (d.delta == null) continue;
    out.push({ t: ra.t, delta: d.delta, uncertaintyHpa: d.uncertaintyHpa });
  }
  return out;
}

// ── Lot 4bis — construction du référentiel ────────────────────────

/**
 * Forme MINIMALE d'une station qui publie une pression déjà réduite au
 * niveau de la mer. `MfStation` et `AemetStation` la satisfont
 * structurellement, sans import : c'est délibéré, `lib/pressure.ts` n'a
 * pas à connaître les types d'application pour faire son travail.
 */
                                       
             
              
              
              
                                                                             
                     
                                                                                  
                      
                    
                    
                              
 

/**
 * Fond les trois sources en LE référentiel de pression, seule liste à
 * passer ensuite à `pickStationFor` / `resolveAnchors`.
 *
 * Extrait d'`AppContext` pour une raison précise : `verify-phenomena.mjs`
 * doit vérifier que les 27 phénomènes de l'étape 30 résolvent leurs
 * ancres, et il ne peut le faire honnêtement qu'en construisant le
 * référentiel EXACTEMENT comme l'application. Deux copies du même
 * `map` dériveraient, et le contrôle finirait par valider autre chose
 * que ce qui tourne.
 *
 * @param server  entrées de `GET /pressure-stations` (`metar:`, `smn:`),
 *                déjà complètes — le serveur transmet sa convention.
 * @param mf      `mfStations` — versées en `mf:<id>`.
 * @param aemet   `aemetStations` — versées en `aemet:<id>`.
 */
function buildPressureReferential(
  server                                   ,
  mf                                 ,
  aemet                                 ,
)                           {
  const out                           = [...server];
  const verser = (list                                 , prefix        , source                    ) => {
    for (const s of list) {
      // Filtrer sur la présence de la PRESSION, pas sur celle du vent :
      // une station sans `pmer` ferait échouer l'appariement sans le
      // dire. Et sans `alt`, aucune réduction n'est vérifiable et
      // PRESSURE_MAX_ALT ne peut pas filtrer.
      if (s.pmer == null || s.alt == null) continue;
      out.push({
        id: `${prefix}${s.id}`, source, code: s.id, nom: s.nom,
        lat: s.lat, lon: s.lon, alt: s.alt,
        // QFF NATIF, surtout pas 'qnh' : `pmer` est déjà réduit par le
        // service météo avec la température réelle. Le déclarer en QNH
        // ferait convertir une deuxième fois, et le biais corrélé au
        // foehn reviendrait par la fenêtre après tout le travail du §3.
        reduction: 'qff', resolutionHpa: 0.1,
        pressure: s.pmer,
        // Sans conséquence : la température ne sert qu'à convertir un
        // QNH. Un QFF natif n'a rien à convertir — c'est sa valeur même.
        tempC: null,
        dd: s.dd, ff: s.ff,
        // La rafale n'est pas dans `SeaLevelStationInput` : ce
        // référentiel sert au Δ de pression, pas à l'affichage du vent,
        // et MF/AEMET ont déjà leurs propres calques pour ça. `null`
        // ici veut dire « non transmise par ce chemin », pas « pas de
        // rafale » — d'où le champ explicite plutôt qu'un oubli.
        raf: null,
        t: s.validityTime ? Date.parse(s.validityTime) : 0,
      });
    }
  };
  verser(mf, 'mf:', 'meteofrance');
  verser(aemet, 'aemet:', 'aemet');
  return out;
}

// ─── src/lib/utils.ts → haversineKm ───
/**
 * Distance à vol d'oiseau (km) entre deux points, formule de haversine.
 * Précision largement suffisante ici — pas besoin d'un modèle ellipsoïdal.
 */
function haversineKm(lat1        , lon1        , lat2        , lon2        )         {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2
    + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// ─── src/lib/phenomena.ts → pickStationFor ───
/**
 * La station la plus PERTINENTE pour un point — pas la plus proche.
 *
 * Remplace `nearestFoehnStation` (lib/foehn.ts), qui ne cherchait que
 * dans le réseau Météo-France : c'est pour ça qu'aucun des 8 axes
 * présets ne pouvait afficher sa courbe réelle, leur extrémité
 * italienne ou espagnole n'étant jamais appariée.
 *
 * On préfère une station QFF native à une station QNH qui demanderait
 * une conversion — mais par un FACTEUR de distance, pas par un tri
 * strict : trier d'abord par convention irait chercher un QFF à 24 km en
 * ignorant un QNH à 1 km, ce qui serait pire que le problème.
 */
function pickStationFor(
  lat        ,
  lon        ,
  stations                            ,
  opts                     = {},
)                      {
  const maxKm = opts.maxKm ?? PRESSURE_MAX_KM;
  const maxAlt = opts.maxAlt ?? PRESSURE_MAX_ALT;
  const qnhPenalty = opts.qnhPenalty ?? QNH_DISTANCE_PENALTY;

  let best                      = null;
  let bestScore = Infinity;
  for (const s of stations) {
    if (s.alt > maxAlt) continue;
    if (opts.sources && !opts.sources.includes(s.source)) continue;
    const km = haversineKm(lat, lon, s.lat, s.lon);
    if (km > maxKm) continue;
    const score = s.reduction === 'qnh' ? km * qnhPenalty : km;
    if (score < bestScore) { best = { station: s, km, forced: false }; bestScore = score; }
  }
  return best;
}

// ─── src/lib/phenomena.ts → resolveAnchors ───
/**
 * Résout les deux extrémités : ancre déclarée si elle existe, sinon
 * appariement par proximité.
 *
 * Une ancre déclarée mais INTROUVABLE est signalée dans `missing`, pas
 * silencieusement remplacée par le voisin le plus proche. Sans table de
 * référentiel côté base (décision (b), §4 du document), `station_a` n'est
 * contraint que par sa FORME : une faute de frappe ne peut être
 * détectée qu'ici, et se taire reviendrait à mesurer un axe autre que
 * celui qu'on croit afficher.
 */
function resolveAnchors(
  ph                ,
  stations                            ,
  opts                     = {},
)                    {
  const missing           = [];
  const resolve = (
    declared               , lat        , lon        ,
  )                      => {
    if (declared) {
      const s = stations.find(x => x.id === declared);
      if (s) return { station: s, km: haversineKm(lat, lon, s.lat, s.lon), forced: true };
      missing.push(declared);
      return null;
    }
    return pickStationFor(lat, lon, stations, opts);
  };
  return {
    a: resolve(ph.stationA, ph.aLat, ph.aLon),
    b: resolve(ph.stationB, ph.bLat, ph.bLon),
    missing,
  };
}

module.exports = { QFF_CONVERSION_UNCERTAINTY_HPA, QFF_NATIVE_UNCERTAINTY_HPA, PRESSURE_MAX_ALT, PRESSURE_WARN_ALT, PRESSURE_MAX_KM, QNH_DISTANCE_PENALTY, qnhToStation, stationToQff, qnhToQff, normalizePressure, pressureDelta, smoothPressureSeries, readingFromQff, readingFromMetar, readingFromStation, deltaSeries, buildPressureReferential, haversineKm, pickStationFor, resolveAnchors };
