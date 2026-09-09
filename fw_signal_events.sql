-- ══════════════════════════════════════════════════════════════════════
--  fw_signal_events.sql — LE JOURNAL des signaux de veille   (09/09/2026)
--                          P1.5 de la revue d'intégration
--
--  ⛔ CE FICHIER N'EST PAS EXÉCUTÉ PAR CLAUDE. Yann le lit, le juge et le
--  lance lui-même dans le SQL Editor — même règle que tous les .sql.
--
--  ⚠️ TANT QU'IL N'EST PAS LANCÉ, RIEN NE CASSE : `fwJournal()` côté
--  serveur avale l'échec d'insertion (journalisé UNE fois), et tout le
--  reste — push, état, voix — continue exactement comme avant.
--
--  CE QUE C'EST : un journal d'ÉVÉNEMENTS, pas un journal de polls. Une
--  ligne par TRANSITION d'un signal (start / repeat / force / end), plus
--  `silent` pour le composite en phase d'observation. Un signal actif et
--  stable n'écrit rien. Il remplace `celluleStats` (RAM, perdu à chaque
--  déploiement), donne enfin la mesure des RECOUVREMENTS entre signaux
--  (l'arbitrage du 09/09 : « on mesure combien de fois ils se
--  recouvrent »), et un historique d'alertes qui ne s'arrête pas aux
--  seuils vent.
--
--  CE QUE ÇA NE REMPLACE PAS : `user_flightwatch_alerts` reste la table
--  d'ÉTAT (une ligne par (compte, scope, signal), lue par le client pour
--  les pastilles et la voix). Le journal ne se lit jamais pour décider
--  d'un push.
-- ══════════════════════════════════════════════════════════════════════

create table if not exists public.fw_signal_events (
  id          bigint generated always as identity primary key,
  t           timestamptz not null default now(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  scope       text not null,      -- même vocabulaire que user_flightwatch_alerts : <beacon_id> | site:<clé> | zone:<ancre> | dept:<code> | axis:<uuid>
  signal      text not null,      -- wind_surge | breeze_reversal | pressure_drop | convection | vigilance | lightning | precip | gust_pi | convective_cell | wind_threshold | foehn
  transition  text not null check (transition in ('start', 'repeat', 'force', 'end', 'silent')),
  level       smallint not null,
  sent        boolean not null default false,  -- un push est-il PARTI ?
  notify      boolean not null default false,  -- la veille était-elle armée ?
  meta        jsonb                            -- ce que le push disait : { value, unit, source, etaMin, run, passe, … } ; pour `silent` : le composite
);

create index if not exists fw_signal_events_user_t   on public.fw_signal_events (user_id, t desc);
create index if not exists fw_signal_events_scope_t  on public.fw_signal_events (scope, t desc);
create index if not exists fw_signal_events_signal_t on public.fw_signal_events (signal, t desc);

comment on table public.fw_signal_events is
  'P1.5 (09/09/2026) : journal des TRANSITIONS des signaux de veille (start/repeat/force/end, silent pour le composite). Écrit par le serveur (service_role) dans evaluateFwSignal ; lu par le compte (RLS self) pour l''historique. Rétention 90 j, purge quotidienne côté serveur (FW_JOURNAL_RETENTION_DAYS).';

alter table public.fw_signal_events enable row level security;

-- Le compte LIT ses propres lignes (historique « 🔔 Alertes »). Aucune
-- policy insert/update/delete : les écritures passent par service_role.
drop policy if exists fw_signal_events_select_self on public.fw_signal_events;
create policy fw_signal_events_select_self
  on public.fw_signal_events for select
  using (auth.uid() = user_id);

-- Contrôle.
select column_name, data_type
  from information_schema.columns
 where table_schema = 'public' and table_name = 'fw_signal_events'
 order by ordinal_position;

-- ── Les trois requêtes qui trancheront (à garder sous la main) ─────────
-- 1. Recouvrements : deux signaux qui DÉMARRENT sur le même scope à ±30 min.
-- select a.signal, b.signal, count(*)
--   from fw_signal_events a join fw_signal_events b
--     on a.user_id = b.user_id and a.scope = b.scope and a.signal < b.signal
--    and a.transition = 'start' and b.transition = 'start'
--    and abs(extract(epoch from a.t - b.t)) < 1800
--  group by 1, 2 order by 3 desc;
-- 2. Le composite : niveau atteint par jour, et désaccords.
-- select date_trunc('day', t) j, meta->>'niveau' niveau, count(*)
--   from fw_signal_events where signal = 'convective_cell' group by 1, 2 order by 1, 2;
-- 3. Le bruit réel : push par pilote et par jour.
-- select user_id, date_trunc('day', t) j, count(*) filter (where sent) push
--   from fw_signal_events group by 1, 2 order by 2 desc, 3 desc;
