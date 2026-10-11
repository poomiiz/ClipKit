-- Revised owner workflow proof on disposable Postgres, never on hosted Supabase.
insert into auth.users(id,email,email_confirmed_at) values
 ('00000000-0000-0000-0000-000000000001','admin@test.invalid',now()),
 ('00000000-0000-0000-0000-000000000002','a@test.invalid',now()),
 ('00000000-0000-0000-0000-000000000003','b@test.invalid',now()),
 ('00000000-0000-0000-0000-000000000004','lead@test.invalid',now()),
 ('00000000-0000-0000-0000-000000000005','outside@test.invalid',now());
create function pg_temp.must_fail(q text) returns void language plpgsql as $$ begin begin execute q; exception when others then return; end;raise exception 'Expected failure: %',q;end $$;
set role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000001',false);
select public.clipkit_create_organization('Owner team') as org \gset
select public.clipkit_add_member(:'org','a@test.invalid','editor');
select public.clipkit_add_member(:'org','b@test.invalid','editor');
select public.clipkit_add_member(:'org','lead@test.invalid','lead');
select public.clipkit_add_footage(:'org','Take.mp4',123) as f \gset
select 1/case when public.clipkit_add_footage(:'org','Take.mp4',123)=:'f'::uuid then 1 else 0 end;
select public.clipkit_add_projects(:'org',:'f','[{"name":"Story","project_type":"capcut"},{"name":"Other","project_type":"hyperframes"}]');
select id as p from public.projects where name='Story' \gset
select id as p2 from public.projects where name='Other' \gset
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000002',false);
select public.clipkit_claim_project(:'org',:'p',1);
select pg_temp.must_fail(format('update public.projects set owner_id=%L where id=%L','00000000-0000-0000-0000-000000000003',:'p'));
select pg_temp.must_fail(format('select public.clipkit_project_action(%L,array[%L::uuid],%L,jsonb_build_object(%L,2),%L)',:'org',:'p','approved',:'p','fake approval'));
select pg_temp.must_fail(format('select public.clipkit_transfer_project(%L,%L,%L,2,%L)',:'org',:'p','00000000-0000-0000-0000-000000000003','steal'));
select public.clipkit_project_action(:'org',array[:'p'::uuid],'awaiting_review',jsonb_build_object(:'p',2),'','story.mp4',456);
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000003',false);
select pg_temp.must_fail(format('select public.clipkit_claim_project(%L,%L,1)',:'org',:'p'));
select 1/case when owner_id='00000000-0000-0000-0000-000000000002'::uuid then 1 else 0 end from public.projects where id=:'p';
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000004',false);
select public.clipkit_project_action(:'org',array[:'p'::uuid],'changes_requested',jsonb_build_object(:'p',3),'Shorten title');
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000002',false);
select public.clipkit_project_action(:'org',array[:'p'::uuid],'editing',jsonb_build_object(:'p',4));
select public.clipkit_project_action(:'org',array[:'p'::uuid],'awaiting_review',jsonb_build_object(:'p',5),'','fixed.mp4',789);
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000004',false);
select pg_temp.must_fail(format('select public.clipkit_project_action(%L,array[%L::uuid,%L::uuid],%L,jsonb_build_object(%L,6,%L,1),%L)',:'org',:'p',:'p2','approved',:'p',:'p2','client said yes'));
select 1/case when status='awaiting_review' and revision=6 then 1 else 0 end from public.projects where id=:'p';
select public.clipkit_project_action(:'org',array[:'p'::uuid],'approved',jsonb_build_object(:'p',6),'Client confirmed');
select 1/case when approved_by='00000000-0000-0000-0000-000000000004'::uuid and approved_at is not null then 1 else 0 end from public.projects where id=:'p';
select public.clipkit_transfer_project(:'org',:'p','00000000-0000-0000-0000-000000000003',7,'New editor');
select 1/case when detail->>'from'='00000000-0000-0000-0000-000000000002' and detail->>'to'='00000000-0000-0000-0000-000000000003' then 1 else 0 end from public.clipkit_activity where action='owner_changed' order by id desc limit 1;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000005',false);
select public.clipkit_create_organization('Other team') as other \gset
select 1/case when count(*)=0 then 1 else 0 end from public.projects;
select 1/case when count(*)=0 then 1 else 0 end from public.footage;
select pg_temp.must_fail(format('select public.clipkit_create_organization(%L)','second org'));
select pg_temp.must_fail(format('select public.clipkit_add_projects(%L,%L,%L)',:'other',:'f','[{"name":"Cross source","project_type":"capcut"}]'));
select pg_temp.must_fail(format('select public.clipkit_register_asset(%L,%L,%L)',:'other','project','shared bypass'));
select pg_temp.must_fail(format('select public.clipkit_rename_project(%L,%L,%L,8)',:'org',:'p','Outside rename'));
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000003',false);
select public.clipkit_rename_project(:'org',:'p','Short story',8);
select 1/case when name='Short story' and revision=9 then 1 else 0 end from public.projects where id=:'p';
select pg_temp.must_fail(format('select public.clipkit_rename_project(%L,%L,%L,8)',:'org',:'p','Stale rename'));
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000004',false);
select pg_temp.must_fail(format('select public.clipkit_rename_project(%L,%L,%L,9)',:'org',:'p','Lead cannot rename another owner'));
reset role;
