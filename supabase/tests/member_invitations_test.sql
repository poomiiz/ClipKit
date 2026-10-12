-- Isolated Postgres only, after all migrations. No emails or real identities.
create function pg_temp.must_fail(q text) returns void language plpgsql as $$
begin
 begin execute q; exception when others then return; end;
 raise exception 'Expected rejection: %',q;
end $$;
insert into auth.users(id,email,email_confirmed_at,raw_user_meta_data) values
 ('00000000-0000-0000-0000-000000000001','admin@example.test',now(),'{}'),
 ('00000000-0000-0000-0000-000000000003','other@example.test',now(),'{"email":"future@example.test"}'),
 ('00000000-0000-0000-0000-000000000004','lead@example.test',now(),'{}'),
 ('00000000-0000-0000-0000-000000000005','admin2@example.test',now(),'{}'),
 ('00000000-0000-0000-0000-000000000006','unverified@example.test',null,'{}');
set role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000001',false);
select public.clipkit_create_organization('Invite team') as org \gset
select public.clipkit_add_footage(:'org','shared.mp4',123) as footage \gset
select public.clipkit_add_projects(:'org',:'footage','[{"name":"First story","project_type":"capcut"}]');
select public.clipkit_add_member(:'org',' FUTURE@example.test ','editor');
select public.clipkit_add_member(:'org','future@example.test','editor');
select public.clipkit_add_member(:'org','unverified@example.test','editor');
select public.clipkit_add_member(:'org','expired@example.test','editor');
select public.clipkit_add_member(:'org','cancelled@example.test','editor');
select public.clipkit_cancel_invitation(:'org','cancelled@example.test');
select 1/case when count(*)=3 then 1 else 0 end from public.clipkit_invitations;
select pg_temp.must_fail(format('select public.clipkit_add_member(%L,%L,%L)',:'org','bad@example.test','admin'));
select public.clipkit_add_member(:'org','lead@example.test','lead');
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000004',false);
select pg_temp.must_fail(format('select public.clipkit_add_member(%L,%L,%L)',:'org','attacker@example.test','editor'));
select pg_temp.must_fail(format('select public.clipkit_cancel_invitation(%L,%L)',:'org','future@example.test'));
select 1/case when count(*)=0 then 1 else 0 end from public.clipkit_invitations;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000003',false);
select 1/case when count(*)=0 then 1 else 0 end from public.clipkit_pending_invitations();
select pg_temp.must_fail(format('select public.clipkit_accept_invitation(%L)',:'org'));
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000006',false);
select pg_temp.must_fail(format('select public.clipkit_accept_invitation(%L)',:'org'));
reset role;
-- The first Google login creates this confirmed Auth identity after the invitation.
insert into auth.users(id,email,email_confirmed_at) values ('00000000-0000-0000-0000-000000000002','future@example.test',now());
insert into auth.users(id,email,email_confirmed_at) values ('00000000-0000-0000-0000-000000000007','expired@example.test',now());
update public.clipkit_invitations set expires_at=now()-interval '1 minute' where email='expired@example.test';
set role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000007',false);
select pg_temp.must_fail(format('select public.clipkit_accept_invitation(%L)',:'org'));
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000002',false);
select 1/case when count(*)=1 then 1 else 0 end from public.clipkit_pending_invitations();
select public.clipkit_accept_invitation(:'org');
select 1/case when public.clipkit_role(:'org')='editor' then 1 else 0 end;
select 1/case when count(*)=1 then 1 else 0 end from public.footage;
select 1/case when count(*)=1 then 1 else 0 end from public.projects;
select pg_temp.must_fail(format('select public.clipkit_accept_invitation(%L)',:'org'));
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000005',false);
select public.clipkit_create_organization('Other team') as org2 \gset
select 1/case when count(*)=0 then 1 else 0 end from public.clipkit_invitations;
select pg_temp.must_fail(format('select public.clipkit_add_member(%L,%L,%L)',:'org2','future@example.test','editor'));
set role anon;
select pg_temp.must_fail('select * from public.clipkit_pending_invitations()');
reset role;
