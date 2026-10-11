-- Run only on an isolated database after local_stub.sql and the organization migration.
alter table auth.users add column email text;
alter table auth.users add column email_confirmed_at timestamptz;
alter table auth.users add column raw_user_meta_data jsonb default '{}';
insert into auth.users(id,email,email_confirmed_at) values
 ('00000000-0000-0000-0000-000000000001','owner@example.test',now()),
 ('00000000-0000-0000-0000-000000000002','editor@example.test',now()),
 ('00000000-0000-0000-0000-000000000003','lead@example.test',now()),
 ('00000000-0000-0000-0000-000000000004','outsider@example.test',now());

create function pg_temp.as_user(sub text) returns void language plpgsql as $$
begin perform set_config('request.jwt.claim.sub',sub,false); end $$;
create function pg_temp.must_fail(q text) returns void language plpgsql as $$
begin
  begin execute q;
  exception when others then return;
  end;
  raise exception 'Expected rejection: %',q;
end $$;

set role authenticated;
select pg_temp.as_user('00000000-0000-0000-0000-000000000001');
select public.clipkit_create_organization('First team') as org \gset
select public.clipkit_add_member(:'org','editor@example.test','editor');
select public.clipkit_add_member(:'org','lead@example.test','lead');
select 1 / case when count(*)=3 then 1 else 0 end from public.clipkit_member_directory(:'org');
select public.clipkit_set_drive_folder(:'org','sampleDriveFolder123');
select public.clipkit_register_asset(:'org','footage','Take 1') as footage \gset
select public.clipkit_register_asset(:'org','project','Clip 1',:'footage') as clip \gset
select public.clipkit_register_asset(:'org','project','Clip 2',:'footage') as second \gset

select pg_temp.as_user('00000000-0000-0000-0000-000000000002');
select pg_temp.must_fail(format('update public.clipkit_assets set status=%L where id=%L','approved',:'clip'));
select pg_temp.must_fail(format('select public.clipkit_add_member(%L,%L,%L)',:'org','outsider@example.test','lead'));
select pg_temp.must_fail(format('select public.clipkit_set_drive_folder(%L,%L)',:'org','sampleDriveFolder999'));
select pg_temp.must_fail(format('select public.clipkit_review_assets(%L,array[%L]::uuid[],%L,%L::jsonb,%L)',:'org',:'clip','approved','{}','client approved'));
select public.clipkit_review_assets(:'org',array[:'clip',:'second']::uuid[],'awaiting_lead',jsonb_build_object(:'clip',1,:'second',1));

select pg_temp.as_user('00000000-0000-0000-0000-000000000003');
-- Stale bulk decisions roll back every project, including any valid rows visited before the stale one.
select pg_temp.must_fail(format('select public.clipkit_review_assets(%L,array[%L,%L]::uuid[],%L,%L::jsonb)',:'org',:'clip',:'second','awaiting_review',jsonb_build_object(:'clip',2,:'second',1)::text));
select 1 / case when count(*)=2 then 1 else 0 end from public.clipkit_assets where kind='project' and status='awaiting_lead' and revision=2;
select public.clipkit_review_assets(:'org',array[:'clip']::uuid[],'awaiting_review',jsonb_build_object(:'clip',2));
select pg_temp.must_fail(format('select public.clipkit_review_assets(%L,array[%L]::uuid[],%L,%L::jsonb)',:'org',:'clip','approved',jsonb_build_object(:'clip',3)::text));
select pg_temp.must_fail(format('select public.clipkit_review_assets(%L,array[%L]::uuid[],%L,%L::jsonb,null)',:'org',:'clip','approved',jsonb_build_object(:'clip',3)::text));
select public.clipkit_review_assets(:'org',array[:'clip']::uuid[],'approved',jsonb_build_object(:'clip',3),'Client confirmed version 3');
select 1 / case when count(*)=1 then 1 else 0 end from public.clipkit_activity where asset_id=:'clip' and actor_id=auth.uid() and detail->>'to'='approved';

select pg_temp.as_user('00000000-0000-0000-0000-000000000002');
select public.clipkit_commit_drive_file(:'org',:'footage',1,'driveSnapshot123',repeat('a',64),'sampleDriveFolder123');
select pg_temp.must_fail(format('select public.clipkit_commit_drive_file(%L,%L,1,%L,%L,%L)',:'org',:'footage','driveSnapshot999',repeat('b',64),'sampleDriveFolder123'));
select pg_temp.must_fail(format('select public.clipkit_commit_drive_file(%L,%L,2,%L,%L,%L)',:'org',:'footage','driveSnapshot999',repeat('b',64),'wrongDriveFolder123'));
select pg_temp.must_fail(format('select public.clipkit_commit_drive_file(%L,%L,4,%L,%L,%L)',:'org',:'clip','approvedClipSnapshot',repeat('b',64),'sampleDriveFolder123'));
select public.clipkit_record_received(:'org',:'footage',2);
select 1 / case when count(*)=1 then 1 else 0 end from public.clipkit_assets where id=:'footage' and revision=2 and drive_file_id='driveSnapshot123';
select 1 / case when count(*)=2 then 1 else 0 end from public.clipkit_activity where asset_id=:'footage' and actor_id=auth.uid() and action in ('file_sent','file_received');

select pg_temp.as_user('00000000-0000-0000-0000-000000000004');
select 1 / case when count(*)=0 then 1 else 0 end from public.clipkit_assets;
select 1 / case when count(*)=0 then 1 else 0 end from public.clipkit_members;
select 1 / case when count(*)=0 then 1 else 0 end from public.clipkit_activity;
select pg_temp.must_fail(format('select * from public.clipkit_member_directory(%L)',:'org'));
select public.clipkit_create_organization('Other team') as other_org \gset
select public.clipkit_register_asset(:'other_org','project','Private clip') as other_clip \gset
select pg_temp.must_fail(format('select public.clipkit_register_asset(%L,%L,%L,%L)',:'other_org','project','Cross-team source',:'footage'));
select pg_temp.must_fail(format('select public.clipkit_review_assets(%L,array[%L]::uuid[],%L,%L::jsonb)',:'org',:'clip','editing','{}'));

select pg_temp.as_user('00000000-0000-0000-0000-000000000003');
select 1 / case when count(*)=3 then 1 else 0 end from public.clipkit_assets;
select pg_temp.must_fail(format('select public.clipkit_review_assets(%L,array[%L]::uuid[],%L,%L::jsonb)',:'org',:'other_clip','awaiting_review','{}'));
select pg_temp.must_fail(format('insert into public.clipkit_activity(organization_id,actor_id,action) values (%L,%L,%L)',:'org','00000000-0000-0000-0000-000000000001','forged'));
reset role;
select 'organization isolation, editor/lead review permissions, revision conflicts and actor audit passed';
