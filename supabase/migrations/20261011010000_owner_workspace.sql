-- Files are synchronized externally; ownership and decisions are database-only.
-- Abort on ambiguous prior memberships rather than silently removing an organization.
alter table public.clipkit_members add constraint clipkit_one_org_per_user unique(user_id);
alter table public.clipkit_members drop constraint clipkit_members_role_check;
update public.clipkit_members set role='admin' where role='owner';
alter table public.clipkit_members add constraint clipkit_members_role_check check(role in ('admin','lead','editor'));

create table public.footage (
 id uuid primary key default gen_random_uuid(), organization_id uuid not null references public.clipkit_organizations,
 name text not null check(length(btrim(name)) between 1 and 500), size_bytes bigint not null check(size_bytes>0),
 created_by uuid not null references auth.users, created_at timestamptz not null default now(),
 unique(organization_id,name,size_bytes), unique(organization_id,id)
);
create table public.projects (
 id uuid primary key default gen_random_uuid(), organization_id uuid not null references public.clipkit_organizations,
 footage_id uuid not null, name text not null check(length(btrim(name)) between 1 and 500),
 project_type text not null check(project_type in ('capcut','hyperframes','clipkit')),
 owner_id uuid references auth.users, status text not null default 'editing' check(status in ('editing','awaiting_review','changes_requested','approved')),
 export_name text, export_size bigint, revision integer not null default 1,
 created_by uuid not null references auth.users, created_at timestamptz not null default now(),
 updated_by uuid not null references auth.users, updated_at timestamptz not null default now(),
 approved_by uuid references auth.users, approved_at timestamptz,
 foreign key(organization_id,footage_id) references public.footage(organization_id,id),
 foreign key(organization_id,owner_id) references public.clipkit_members(organization_id,user_id),
 check(export_name is null or (export_name ~* '^[^/\\]+[.]mp4$' and export_size>0))
);
alter table public.footage enable row level security;
alter table public.projects enable row level security;
revoke all on public.footage,public.projects from public,anon,authenticated;
grant select on public.footage,public.projects to authenticated;
create policy "organization sees footage" on public.footage for select to authenticated using(public.clipkit_role(organization_id) is not null);
create policy "organization sees projects" on public.projects for select to authenticated using(public.clipkit_role(organization_id) is not null);
create index projects_footage on public.projects(organization_id,footage_id);

create or replace function public.clipkit_create_organization(org_name text) returns uuid
language plpgsql security definer set search_path='' as $$
declare org uuid;
begin
 if auth.uid() is null then raise exception 'Sign in first' using errcode='42501'; end if;
 insert into public.clipkit_organizations(name,created_by) values(btrim(org_name),auth.uid()) returning id into org;
 insert into public.clipkit_members values(org,auth.uid(),'admin',now());
 return org;
end $$;
create or replace function public.clipkit_add_member(org uuid,member_email text,member_role text) returns void
language plpgsql security definer set search_path='' as $$
declare member_id uuid;
begin
 if public.clipkit_role(org) is distinct from 'admin' then raise exception 'Admin only' using errcode='42501'; end if;
 if member_role is null or member_role not in ('lead','editor') then raise exception 'Invalid role'; end if;
 select id into member_id from auth.users where lower(email)=lower(btrim(member_email)) and email_confirmed_at is not null;
 if member_id is null then raise exception 'Member must sign up and verify email first'; end if;
 if member_id=auth.uid() then raise exception 'Cannot change your admin role'; end if;
 insert into public.clipkit_members values(org,member_id,member_role,now()) on conflict(organization_id,user_id) do update set role=excluded.role;
end $$;
create function public.clipkit_add_footage(org uuid,file_name text,file_size bigint) returns uuid
language plpgsql security definer set search_path='' as $$
declare result uuid;
begin
 if public.clipkit_role(org) is null then raise exception 'Organization member only' using errcode='42501'; end if;
 if file_name is null or file_name ~ '[/\\]' then raise exception 'File name only'; end if;
 insert into public.footage(organization_id,name,size_bytes,created_by) values(org,file_name,file_size,auth.uid())
 on conflict(organization_id,name,size_bytes) do update set name=excluded.name returning id into result;
 return result;
end $$;
create function public.clipkit_add_projects(org uuid,source uuid,stories jsonb) returns integer
language plpgsql security definer set search_path='' as $$
declare story jsonb; total integer:=0;
begin
 if public.clipkit_role(org) is null then raise exception 'Organization member only' using errcode='42501'; end if;
 if jsonb_typeof(stories)<>'array' or jsonb_array_length(stories) not between 1 and 500 then raise exception '1 to 500 stories required'; end if;
 for story in select value from jsonb_array_elements(stories) loop
  insert into public.projects(organization_id,footage_id,name,project_type,created_by,updated_by)
  values(org,source,story->>'name',story->>'project_type',auth.uid(),auth.uid()); total:=total+1;
 end loop;
 return total;
end $$;
create function public.clipkit_claim_project(org uuid,project uuid,expected_revision integer) returns integer
language plpgsql security definer set search_path='' as $$
declare version integer;
begin
 if public.clipkit_role(org) is null then raise exception 'Organization member only' using errcode='42501'; end if;
 update public.projects set owner_id=auth.uid(),revision=revision+1,updated_by=auth.uid(),updated_at=now()
 where id=project and organization_id=org and owner_id is null and status='editing' and revision=expected_revision returning revision into version;
 if not found then raise exception 'Project already claimed or changed' using errcode='40001'; end if;
 insert into public.clipkit_activity(organization_id,actor_id,asset_id,action,detail) values(org,auth.uid(),project,'owner_changed',jsonb_build_object('from',null,'to',auth.uid(),'revision',version));
 return version;
end $$;
create function public.clipkit_transfer_project(org uuid,project uuid,next_owner uuid,expected_revision integer,note text) returns integer
language plpgsql security definer set search_path='' as $$
declare item public.projects;
begin
 if public.clipkit_role(org) not in ('admin','lead') or public.clipkit_role(org) is null then raise exception 'Lead only' using errcode='42501'; end if;
 if note is null or length(btrim(note)) not between 1 and 5000 then raise exception 'Transfer reason required'; end if;
 select * into item from public.projects where id=project and organization_id=org for update;
 if not found or item.revision is distinct from expected_revision then raise exception 'Project changed' using errcode='40001'; end if;
 if next_owner is not null and not exists(select 1 from public.clipkit_members where organization_id=org and user_id=next_owner) then raise exception 'Owner must belong to organization'; end if;
 update public.projects set owner_id=next_owner,status='editing',revision=revision+1,approved_by=null,approved_at=null,updated_by=auth.uid(),updated_at=now() where id=project;
 insert into public.clipkit_activity(organization_id,actor_id,asset_id,action,detail) values(org,auth.uid(),project,'owner_changed',jsonb_build_object('from',item.owner_id,'to',next_owner,'note',note,'revision',item.revision+1));
 return item.revision+1;
end $$;
create function public.clipkit_project_action(org uuid,project_ids uuid[],next_status text,expected_revisions jsonb,note text default '',export_file text default null,export_bytes bigint default null) returns integer
language plpgsql security definer set search_path='' as $$
declare item public.projects; member_role text; total integer:=0; requested integer;
begin
 member_role:=public.clipkit_role(org);
 if member_role is null then raise exception 'Organization member only' using errcode='42501'; end if;
 select count(distinct id) into requested from unnest(project_ids) id;
 if export_file is not null and (cardinality(project_ids)<>1 or next_status<>'awaiting_review' or export_bytes is null) then raise exception 'Export belongs to one owner submission'; end if;
 if requested=0 or cardinality(project_ids)>500 or array_position(project_ids,null) is not null then raise exception '1 to 500 projects required'; end if;
 if note is null or length(note)>5000 then raise exception 'Invalid note'; end if;
 for item in select * from public.projects where organization_id=org and id=any(project_ids) order by id for update loop
  if item.revision is distinct from (expected_revisions->>item.id::text)::integer then raise exception 'Project changed' using errcode='40001'; end if;
  if next_status='awaiting_review' and item.status in ('editing','changes_requested') then
   if item.owner_id is distinct from auth.uid() then raise exception 'Project owner only' using errcode='42501'; end if;
   if export_file is null or export_bytes is null then
    if item.export_name is null then raise exception 'Export MP4 before submitting'; end if;
   end if;
  elsif next_status='editing' and item.status='changes_requested' then
   if item.owner_id is distinct from auth.uid() then raise exception 'Project owner only' using errcode='42501'; end if;
  elsif member_role in ('admin','lead') and ((item.status='awaiting_review' and next_status in ('approved','changes_requested')) or (item.status='approved' and next_status='editing')) then
   if length(btrim(note))=0 then raise exception 'Decision note required'; end if;
  else raise exception 'Transition not permitted' using errcode='42501'; end if;
  update public.projects set status=next_status,revision=revision+1,updated_by=auth.uid(),updated_at=now(),
   export_name=coalesce(export_file,export_name),export_size=coalesce(export_bytes,export_size),
   approved_by=case when next_status='approved' then auth.uid() else null end,approved_at=case when next_status='approved' then now() else null end where id=item.id;
  insert into public.clipkit_activity(organization_id,actor_id,asset_id,action,detail) values(org,auth.uid(),item.id,'delivery_changed',jsonb_build_object('from',item.status,'to',next_status,'note',note,'revision',item.revision+1));
  total:=total+1;
 end loop;
 if total<>requested then raise exception 'Project missing or outside organization'; end if;
 return total;
end $$;
-- Old shared-project APIs cannot bypass the private owner workflow.
revoke execute on function public.clipkit_register_asset(uuid,text,text,uuid),public.clipkit_review_assets(uuid,uuid[],text,jsonb,text,boolean),public.clipkit_commit_drive_file(uuid,uuid,integer,text,text,text),public.clipkit_record_received(uuid,uuid,integer),public.clipkit_set_drive_folder(uuid,text) from authenticated;
revoke all on function public.clipkit_add_footage(uuid,text,bigint),public.clipkit_add_projects(uuid,uuid,jsonb),public.clipkit_claim_project(uuid,uuid,integer),public.clipkit_transfer_project(uuid,uuid,uuid,integer,text),public.clipkit_project_action(uuid,uuid[],text,jsonb,text,text,bigint) from public,anon;
grant execute on function public.clipkit_add_footage(uuid,text,bigint),public.clipkit_add_projects(uuid,uuid,jsonb),public.clipkit_claim_project(uuid,uuid,integer),public.clipkit_transfer_project(uuid,uuid,uuid,integer,text),public.clipkit_project_action(uuid,uuid[],text,jsonb,text,text,bigint) to authenticated;

-- Preserve legacy sign-ins and assign the first legacy team deterministically.
do $$
declare org uuid; admin_id uuid;
begin
 if to_regclass('public.team_members') is null then return; end if;
 select user_id into admin_id from public.team_members where role='admin' order by created_at,user_id limit 1;
 if admin_id is null then
  if exists(select 1 from public.team_members) then raise exception 'Legacy team has no admin; assign one before migration'; end if;
 end if;
 select organization_id into org from public.clipkit_members where user_id=admin_id;
 if org is null and admin_id is not null then
  insert into public.clipkit_organizations(name,created_by) values('ทีมเดิม',admin_id) returning id into org;
 end if;
 if exists(select 1 from public.team_members t join public.clipkit_members m on t.user_id=m.user_id where m.organization_id<>org) then raise exception 'Legacy members already belong to different organizations; resolve before migrating'; end if;
 insert into public.clipkit_members(organization_id,user_id,role)
 select org,user_id,case when role='admin' then 'admin' else 'editor' end from public.team_members
 on conflict(user_id) do nothing;
 alter table public.team_members add column organization_id uuid references public.clipkit_organizations;
 update public.team_members t set organization_id=m.organization_id from public.clipkit_members m where t.user_id=m.user_id;
 alter table public.preset_packs add column organization_id uuid references public.clipkit_organizations;
 update public.preset_packs p set organization_id=m.organization_id from public.clipkit_members m where m.user_id=p.author_id;
 alter table public.team_members alter column organization_id set not null;
 drop policy "team sees team" on public.team_members;
 drop policy "admin manages team" on public.team_members;
 revoke insert,update,delete on public.team_members from authenticated;
 create policy "org sees legacy members" on public.team_members for select to authenticated using(public.clipkit_role(organization_id) is not null);
 alter table public.preset_packs drop constraint preset_packs_author_id_fkey;
 alter table public.preset_packs add constraint preset_packs_author_id_fkey foreign key(author_id) references auth.users(id);
 alter table public.preset_packs alter column organization_id set not null;
 drop policy "team sees packs" on public.preset_packs;
 drop policy "member adds own packs" on public.preset_packs;
 drop policy "author or admin edits packs" on public.preset_packs;
 drop policy "author or admin deletes packs" on public.preset_packs;
 create policy "org sees packs" on public.preset_packs for select to authenticated using(public.clipkit_role(organization_id) is not null);
 create policy "org adds packs" on public.preset_packs for insert to authenticated with check(public.clipkit_role(organization_id) is not null and author_id=auth.uid());
 create policy "org edits packs" on public.preset_packs for update to authenticated using(public.clipkit_role(organization_id) is not null and (author_id=auth.uid() or public.clipkit_role(organization_id)='admin')) with check(public.clipkit_role(organization_id) is not null and (author_id=auth.uid() or public.clipkit_role(organization_id)='admin'));
 create policy "org deletes packs" on public.preset_packs for delete to authenticated using(public.clipkit_role(organization_id) is not null and (author_id=auth.uid() or public.clipkit_role(organization_id)='admin'));
end $$;
