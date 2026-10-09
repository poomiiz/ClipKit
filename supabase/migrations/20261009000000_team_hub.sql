-- ClipKit team hub: team members (Supabase Auth) and the shared preset pack library.
-- The pack row mirrors the .clipkit manifest checked in app/preset_pack.py (check_manifest); keep TIERS in sync.
-- Every table has RLS on and is granted to `authenticated` only; `anon` gets nothing.
-- The app ships only SUPABASE_URL and the anon key. The service key and DB password never leave the server.
-- First admin: run once in the SQL editor (service role bypasses RLS):
--   insert into public.team_members (user_id, display_name, role) values ('<auth user id>', 'โอม', 'admin');

create table public.team_members (
  user_id      uuid primary key references auth.users (id) on delete cascade,
  display_name text not null check (btrim(display_name) <> ''),
  role         text not null default 'editor' check (role in ('admin', 'editor')),
  created_at   timestamptz not null default now()
);

-- security definer so policies can ask "is this user on the team" without recursing through team_members RLS
create function public.team_role() returns text
  language sql stable security definer set search_path = ''
  as $$ select role from public.team_members where user_id = (select auth.uid()) $$;

create table public.preset_packs (
  id         text primary key check (id ~ '^[a-z0-9][a-z0-9-]{0,47}$'),
  format     int  not null default 1 check (format = 1),
  name       text not null check (btrim(name) <> ''),
  author_id  uuid not null default auth.uid() references public.team_members (user_id),
  tier       text not null check (tier in ('team', 'free', 'basic', 'standard', 'pro')),
  covers     text[] not null default '{}',
  subtitles  text[] not null default '{}',
  motion     text[] not null default '{}',
  fonts      jsonb  not null default '[]' check (jsonb_typeof(fonts) = 'array'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (array_to_string(covers || subtitles || motion, ',') ~ '^([a-z0-9][a-z0-9-]{0,47}(,|$))*$'),
  check (array_to_string(covers, ',') ~ '^(cover-[a-z0-9-]*(,|$))*$'),
  check (array_to_string(motion, ',') !~ '(^|,)cover-'),
  -- minimum covers, subtitle styles, motion per tier (TIERS in app/preset_pack.py)
  check (case tier
           when 'free'     then cardinality(covers) >= 1  and cardinality(subtitles) >= 1
           when 'basic'    then cardinality(covers) >= 3  and cardinality(subtitles) >= 2 and cardinality(motion) >= 2
           when 'standard' then cardinality(covers) >= 6  and cardinality(subtitles) >= 4 and cardinality(motion) >= 4
           when 'pro'      then cardinality(covers) >= 12 and cardinality(subtitles) >= 8 and cardinality(motion) >= 8
           else true end)
);

create function public.touch_updated_at() returns trigger
  language plpgsql set search_path = ''
  as $$ begin new.updated_at := now(); return new; end $$;

create trigger preset_packs_touch before update on public.preset_packs
  for each row execute function public.touch_updated_at();

alter table public.team_members enable row level security;
alter table public.preset_packs enable row level security;

revoke all on public.team_members, public.preset_packs from anon, authenticated;
revoke execute on function public.team_role(), public.touch_updated_at() from public, anon;
grant select, insert, update, delete on public.team_members, public.preset_packs to authenticated;
grant execute on function public.team_role() to authenticated;

create policy "team sees team" on public.team_members
  for select to authenticated using ((select public.team_role()) is not null);
create policy "admin manages team" on public.team_members
  for all to authenticated
  using ((select public.team_role()) = 'admin') with check ((select public.team_role()) = 'admin');

create policy "team sees packs" on public.preset_packs
  for select to authenticated using ((select public.team_role()) is not null);
create policy "member adds own packs" on public.preset_packs
  for insert to authenticated
  with check ((select public.team_role()) is not null and author_id = (select auth.uid()));
create policy "author or admin edits packs" on public.preset_packs
  for update to authenticated
  using (author_id = (select auth.uid()) or (select public.team_role()) = 'admin')
  with check (author_id = (select auth.uid()) or (select public.team_role()) = 'admin');
create policy "author or admin deletes packs" on public.preset_packs
  for delete to authenticated
  using (author_id = (select auth.uid()) or (select public.team_role()) = 'admin');
