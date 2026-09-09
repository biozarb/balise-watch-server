-- ══════════════════════════════════════════════════════════════════════
--  add_sig_convective_cell.sql — la préférence du lot 3   (09/09/2026)
--                                « cellule qui approche » · composite
--
--  ⛔ CE FICHIER N'EST PAS EXÉCUTÉ PAR CLAUDE. Il est écrit ici pour que
--  Yann le lise, le juge et le lance lui-même — même règle que
--  `add_sig_precip.sql` et `add_sig_gust_pi.sql`.
--
--  ⚠️ TANT QU'IL N'EST PAS LANCÉ, RIEN NE CASSE. `fwPrefs()` lit
--  `row?.[k]` et retombe sur le défaut `FW_DEFAULTS.sig_convective_cell
--  = true`. Et de toute façon le lot 3 est SILENCIEUX : ce drapeau ne
--  gouverne que l'évaluation et le cache, pas un push qui n'existe pas
--  encore.
--
--  ⛔ CE QUE CETTE COLONNE NE FAIT PAS. Elle ne remplace ni `sig_precip`,
--  ni `sig_gust_pi`, ni `sig_lightning` : le composite est un QUATRIÈME
--  signal et les trois autres gardent leurs pushes (arbitrage Yann du
--  09/09). Couper le composite ne coupe donc aucune des trois sources ;
--  couper une source rend le composite incomplet, et il le DIT.
-- ══════════════════════════════════════════════════════════════════════

alter table public.user_surveillance
  add column if not exists sig_convective_cell boolean not null default true;

comment on column public.user_surveillance.sig_convective_cell is
  'Lot 3 « cellule qui approche » (09/09/2026) : composite de trois sources — pluie prévue (PIAF), rafale prévue (AROME-PI) et foudre observée (Blitzortung) — qui ne se déclare que si au moins deux d''entre elles annoncent la MÊME chose au MÊME moment (concordance temporelle). Quatrième signal : sig_precip, sig_gust_pi et sig_lightning restent indépendants. Phase silencieuse tant que CELLULE_ENABLED n''est pas posé côté serveur.';

-- Contrôle : les quatre colonnes coexistent, aucune n'a remplacé l'autre.
select column_name, data_type, column_default
  from information_schema.columns
 where table_schema = 'public'
   and table_name   = 'user_surveillance'
   and column_name in ('sig_precip', 'sig_lightning', 'sig_gust_pi', 'sig_convective_cell')
 order by column_name;
