-- ══════════════════════════════════════════════════════════════════════
--  add_sig_gust_pi.sql — la préférence de compte du lot 2  (09/09/2026)
--                        « cellule qui approche » · signal `gust_pi`
--
--  ⛔ CE FICHIER N'EST PAS EXÉCUTÉ PAR CLAUDE. Il est écrit ici pour que
--  Yann le lise, le juge et le lance lui-même dans Supabase — même règle
--  que `add_sig_precip.sql`.
--
--  ⚠️ TANT QU'IL N'EST PAS LANCÉ, RIEN NE CASSE. `fwPrefs()` lit
--  `row?.[k]` et retombe sur le défaut `FW_DEFAULTS.sig_gust_pi = true`
--  quand la colonne est absente. Le signal est donc actif pour tout le
--  monde — mais la chaîne entière est gatée par `PI_RAFALE_ENABLED`, qui
--  est OFF par défaut. Cette colonne sert le jour où un compte voudra
--  couper CE signal-là sans couper les autres.
--
--  ⛔ NE PAS CONFONDRE AVEC `sig_gust_front`, qui existe déjà et qui
--  gouverne le front de rafales OBSERVÉ (RADOME). Deux colonnes, deux
--  signaux, deux sources. Les fusionner ferait taire la mesure en
--  coupant la prévision, ou l'inverse.
-- ══════════════════════════════════════════════════════════════════════

alter table public.user_surveillance
  add column if not exists sig_gust_pi boolean not null default true;

comment on column public.user_surveillance.sig_gust_pi is
  'Lot 2 « cellule qui approche » (09/09/2026) : rafale PRÉVUE par AROME-PI (tranche 15 min, calque agrume/pi-rafale). Distinct de sig_gust_front, qui est le front de rafales OBSERVÉ sur RADOME. Le push est gaté en plus par PI_RAFALE_ENABLED côté serveur.';

-- Contrôle : les deux colonnes coexistent, aucune n'a remplacé l'autre.
select column_name, data_type, column_default
  from information_schema.columns
 where table_schema = 'public'
   and table_name   = 'user_surveillance'
   and column_name in ('sig_gust_front', 'sig_gust_pi')
 order by column_name;
