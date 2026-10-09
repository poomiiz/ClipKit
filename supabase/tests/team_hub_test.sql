-- RLS checks for 20261009000000_team_hub.sql. Local run (fresh database, from this folder):
--   psql -v ON_ERROR_STOP=1 -f local_stub.sql -f ../migrations/20261009000000_team_hub.sql -f team_hub_test.sql
-- Raises on the first broken expectation; prints "team_hub tests passed" at the end.
insert into auth.users values ('00000000-0000-0000-0000-00000000000a'), ('00000000-0000-0000-0000-00000000000b'),
                              ('00000000-0000-0000-0000-00000000000c');
insert into public.team_members values ('00000000-0000-0000-0000-00000000000a', 'admin', 'admin'),
                                       ('00000000-0000-0000-0000-00000000000b', 'editor', 'editor');

create function pg_temp.expect_fail(q text) returns void language plpgsql as $$
begin execute q; raise exception 'expected failure: %', q;
exception when insufficient_privilege or check_violation or foreign_key_violation then null; end $$;

create function pg_temp.as_user(sub text) returns void language plpgsql as $$
begin perform set_config('request.jwt.claim.sub', sub, false); end $$;

-- anon sees nothing and cannot write
set role anon;
select pg_temp.expect_fail('select * from public.preset_packs');
select pg_temp.expect_fail('select * from public.team_members');
reset role;

-- editor adds a pack; bad manifests are refused
set role authenticated;
select pg_temp.as_user('00000000-0000-0000-0000-00000000000b');
insert into public.preset_packs (id, name, tier, covers, subtitles) values ('ed-pack', 'Editor pack', 'free', '{cover-a}', '{sub-a}');
select pg_temp.expect_fail($q$insert into public.preset_packs (id, name, tier) values ('x', 'x', 'free')$q$);  -- below tier minimum
select pg_temp.expect_fail($q$insert into public.preset_packs (id, name, tier, covers) values ('y', 'y', 'team', '{a}')$q$);  -- cover without cover-
select pg_temp.expect_fail($q$insert into public.preset_packs (id, name, tier, motion) values ('z', 'z', 'team', '{cover-a}')$q$);  -- motion named cover-
select pg_temp.expect_fail($q$insert into public.preset_packs (id, name, tier) values ('Bad', 'b', 'team')$q$);  -- id not a-z0-9-
select pg_temp.expect_fail($q$insert into public.preset_packs (id, name, tier, author_id) values ('w', 'w', 'team', '00000000-0000-0000-0000-00000000000a')$q$);  -- posing as someone else
select pg_temp.expect_fail($q$insert into public.team_members values ('00000000-0000-0000-0000-00000000000c', 'c', 'admin')$q$);  -- editor cannot add members
reset role;

-- admin adds a pack; editor sees it but cannot change it, nor hand their own pack to someone else
set role authenticated;
select pg_temp.as_user('00000000-0000-0000-0000-00000000000a');
insert into public.preset_packs (id, name, tier) values ('admin-pack', 'Admin pack', 'team');
select pg_temp.as_user('00000000-0000-0000-0000-00000000000b');
do $$ begin
  if (select count(*) from public.preset_packs) <> 2 then raise exception 'editor should see 2 packs'; end if;
  update public.preset_packs set name = 'hijack' where id = 'admin-pack';
  delete from public.preset_packs where id = 'admin-pack';
  if (select name from public.preset_packs where id = 'admin-pack') <> 'Admin pack' then raise exception 'editor changed admin pack'; end if;
end $$;
select pg_temp.expect_fail($q$update public.preset_packs set author_id = '00000000-0000-0000-0000-00000000000a' where id = 'ed-pack'$q$);
reset role;

-- signed-in user who is not on the team sees nothing and cannot add
set role authenticated;
select pg_temp.as_user('00000000-0000-0000-0000-00000000000c');
do $$ begin
  if (select count(*) from public.preset_packs) <> 0 then raise exception 'outsider sees packs'; end if;
  if (select count(*) from public.team_members) <> 0 then raise exception 'outsider sees team'; end if;
end $$;
select pg_temp.expect_fail($q$insert into public.preset_packs (id, name, tier) values ('o', 'o', 'team')$q$);
reset role;

-- admin can edit and delete any pack, and add members
set role authenticated;
select pg_temp.as_user('00000000-0000-0000-0000-00000000000a');
update public.preset_packs set name = 'Renamed' where id = 'ed-pack';
delete from public.preset_packs where id = 'ed-pack';
insert into public.team_members values ('00000000-0000-0000-0000-00000000000c', 'new', 'editor');
do $$ begin
  if exists (select 1 from public.preset_packs where id = 'ed-pack') then raise exception 'admin delete failed'; end if;
end $$;
reset role;

select 'team_hub tests passed';
