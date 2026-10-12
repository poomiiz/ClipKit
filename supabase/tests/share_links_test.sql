-- Share link proof on disposable Postgres, never on hosted Supabase: who may set it, what it accepts,
-- and that a project with only a link can be submitted for review.
insert into auth.users(id,email,email_confirmed_at) values
 ('00000000-0000-0000-0000-000000000001','admin@test.invalid',now()),
 ('00000000-0000-0000-0000-000000000002','a@test.invalid',now()),
 ('00000000-0000-0000-0000-000000000003','b@test.invalid',now()),
 ('00000000-0000-0000-0000-000000000004','lead@test.invalid',now()),
 ('00000000-0000-0000-0000-000000000005','outside@test.invalid',now());
create function pg_temp.must_fail(q text) returns void language plpgsql as $$ begin begin execute q; exception when others then return; end;raise exception 'Expected failure: %',q;end $$;
set role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000001',false);
select public.clipkit_create_organization('Link team') as org \gset
select public.clipkit_add_member(:'org','a@test.invalid','editor');
select public.clipkit_add_member(:'org','b@test.invalid','editor');
select public.clipkit_add_member(:'org','lead@test.invalid','lead');
select public.clipkit_add_footage(:'org','Take.mp4',123) as f \gset
select public.clipkit_add_projects(:'org',:'f','[{"name":"Story","project_type":"capcut"}]');
select id as p from public.projects where name='Story' \gset
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000002',false);
select public.clipkit_claim_project(:'org',:'p',1);
-- nothing to show yet: submitting still needs an MP4 or a link
select pg_temp.must_fail(format('select public.clipkit_project_action(%L,array[%L::uuid],%L,jsonb_build_object(%L,2))',:'org',:'p','awaiting_review',:'p'));
-- only Google Drive / Docs https links
select pg_temp.must_fail(format('select public.clipkit_set_share_link(%L,%L,%L)',:'org',:'p','http://drive.google.com/file/d/abc/view'));
select pg_temp.must_fail(format('select public.clipkit_set_share_link(%L,%L,%L)',:'org',:'p','https://evil.example/drive.google.com/x'));
select pg_temp.must_fail(format('select public.clipkit_set_share_link(%L,%L,%L)',:'org',:'p','https://drive.google.com/file/d/abc view'));
-- another editor and an outsider may not set it
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000003',false);
select pg_temp.must_fail(format('select public.clipkit_set_share_link(%L,%L,%L)',:'org',:'p','https://drive.google.com/file/d/abc/view'));
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000005',false);
select pg_temp.must_fail(format('select public.clipkit_set_share_link(%L,%L,%L)',:'org',:'p','https://drive.google.com/file/d/abc/view'));
-- the owner pastes it (spaces trimmed); the revision does not move
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000002',false);
select public.clipkit_set_share_link(:'org',:'p','  https://drive.google.com/file/d/abc_123/view?usp=sharing ');
select 1/case when share_url='https://drive.google.com/file/d/abc_123/view?usp=sharing' and revision=2 then 1 else 0 end from public.projects where id=:'p';
select 1/case when detail->>'link'='https://drive.google.com/file/d/abc_123/view?usp=sharing' then 1 else 0 end from public.clipkit_activity where action='share_link_changed' order by id desc limit 1;
-- a link alone is enough to submit
select public.clipkit_project_action(:'org',array[:'p'::uuid],'awaiting_review',jsonb_build_object(:'p',2));
select 1/case when status='awaiting_review' and export_name is null then 1 else 0 end from public.projects where id=:'p';
-- a lead may replace it while reviewing; an empty value clears it
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000004',false);
select public.clipkit_set_share_link(:'org',:'p','https://docs.google.com/file/d/xyz/view');
select 1/case when share_url='https://docs.google.com/file/d/xyz/view' then 1 else 0 end from public.projects where id=:'p';
select public.clipkit_set_share_link(:'org',:'p','');
select 1/case when share_url is null then 1 else 0 end from public.projects where id=:'p';
-- the old MP4 path still works unchanged
select public.clipkit_project_action(:'org',array[:'p'::uuid],'changes_requested',jsonb_build_object(:'p',3),'Shorter');
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000002',false);
select public.clipkit_project_action(:'org',array[:'p'::uuid],'editing',jsonb_build_object(:'p',4));
select public.clipkit_project_action(:'org',array[:'p'::uuid],'awaiting_review',jsonb_build_object(:'p',5),'','fixed.mp4',789);
select 1/case when status='awaiting_review' and export_name='fixed.mp4' then 1 else 0 end from public.projects where id=:'p';
-- anon cannot call it at all
reset role;
set role anon;
select pg_temp.must_fail(format('select public.clipkit_set_share_link(%L,%L,%L)',:'org',:'p','https://drive.google.com/file/d/abc/view'));
