-- Organization identity and review state are authoritative here, never in an editor's local file.
create table public.clipkit_organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null check (length(btrim(name)) between 1 and 120),
  drive_folder_id text check (drive_folder_id ~ '^[A-Za-z0-9_-]{10,200}$'),
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);

create table public.clipkit_members (
  organization_id uuid not null references public.clipkit_organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id),
  role text not null check (role in ('owner', 'lead', 'editor')),
  joined_at timestamptz not null default now(),
  primary key (organization_id, user_id)
);

create function public.clipkit_role(org uuid) returns text
language sql stable security definer set search_path = ''
as $$ select role from public.clipkit_members where organization_id = org and user_id = auth.uid() $$;

create table public.clipkit_assets (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.clipkit_organizations(id),
  kind text not null check (kind in ('footage', 'project')),
  name text not null check (length(btrim(name)) between 1 and 500),
  source_id uuid,
  drive_file_id text check (drive_file_id ~ '^[A-Za-z0-9_-]{10,200}$'),
  checksum text check (checksum ~ '^[a-f0-9]{64}$'),
  status text not null default 'editing' check (status in ('editing','awaiting_lead','awaiting_review','changes_requested','approved')),
  revision integer not null default 1 check (revision > 0),
  created_by uuid not null references auth.users(id),
  updated_by uuid not null references auth.users(id),
  updated_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, drive_file_id),
  foreign key (organization_id, source_id) references public.clipkit_assets(organization_id, id),
  check (kind = 'project' or (source_id is null and status = 'editing'))
);

create table public.clipkit_activity (
  id bigint generated always as identity primary key,
  organization_id uuid not null references public.clipkit_organizations(id),
  actor_id uuid not null references auth.users(id),
  asset_id uuid,
  action text not null,
  detail jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index clipkit_assets_org on public.clipkit_assets(organization_id, updated_at desc);
create index clipkit_activity_org on public.clipkit_activity(organization_id, created_at desc);

alter table public.clipkit_organizations enable row level security;
alter table public.clipkit_members enable row level security;
alter table public.clipkit_assets enable row level security;
alter table public.clipkit_activity enable row level security;
revoke all on public.clipkit_organizations, public.clipkit_members, public.clipkit_assets, public.clipkit_activity from anon, authenticated;
grant select on public.clipkit_organizations, public.clipkit_members, public.clipkit_assets, public.clipkit_activity to authenticated;
create policy "members see organization" on public.clipkit_organizations for select to authenticated using (public.clipkit_role(id) is not null);
create policy "members see members" on public.clipkit_members for select to authenticated using (public.clipkit_role(organization_id) is not null);
create policy "members see assets" on public.clipkit_assets for select to authenticated using (public.clipkit_role(organization_id) is not null);
create policy "members see activity" on public.clipkit_activity for select to authenticated using (public.clipkit_role(organization_id) is not null);

create function public.clipkit_create_organization(org_name text) returns uuid
language plpgsql security definer set search_path = '' as $$
declare org uuid;
begin
  if auth.uid() is null then raise exception 'Sign in first' using errcode = '42501'; end if;
  insert into public.clipkit_organizations(name,created_by) values (btrim(org_name),auth.uid()) returning id into org;
  insert into public.clipkit_members values (org,auth.uid(),'owner',now());
  insert into public.clipkit_activity(organization_id,actor_id,action) values (org,auth.uid(),'organization_created');
  return org;
end $$;

create function public.clipkit_add_member(org uuid, member_email text, member_role text) returns void
language plpgsql security definer set search_path = '' as $$
declare member_id uuid;
begin
  if public.clipkit_role(org) is distinct from 'owner' then raise exception 'Owner only' using errcode = '42501'; end if;
  if member_role not in ('lead','editor') then raise exception 'Invalid member role'; end if;
  select id into member_id from auth.users where lower(email) = lower(btrim(member_email)) and email_confirmed_at is not null;
  if member_id is null then raise exception 'Member must sign up and verify email first'; end if;
  if member_id = auth.uid() then raise exception 'Cannot change your owner role'; end if;
  insert into public.clipkit_members values (org,member_id,member_role,now())
  on conflict (organization_id,user_id) do update set role = excluded.role;
  insert into public.clipkit_activity(organization_id,actor_id,action,detail)
    values (org,auth.uid(),'member_added',jsonb_build_object('member_id',member_id,'role',member_role));
end $$;

create function public.clipkit_register_asset(org uuid, asset_kind text, asset_name text, source uuid default null) returns uuid
language plpgsql security definer set search_path = '' as $$
declare asset uuid;
begin
  if public.clipkit_role(org) is null then raise exception 'Not an organization member' using errcode = '42501'; end if;
  if source is not null and not exists(select 1 from public.clipkit_assets where id=source and organization_id=org and kind='footage') then
    raise exception 'Source must be footage in the same organization';
  end if;
  insert into public.clipkit_assets(organization_id,kind,name,source_id,created_by,updated_by)
    values (org,asset_kind,btrim(asset_name),source,auth.uid(),auth.uid()) returning id into asset;
  insert into public.clipkit_activity(organization_id,actor_id,asset_id,action) values (org,auth.uid(),asset,'asset_registered');
  return asset;
end $$;

create function public.clipkit_member_directory(org uuid) returns table(user_id uuid, role text, email text, display_name text)
language plpgsql stable security definer set search_path = '' as $$
begin
  if public.clipkit_role(org) is null then raise exception 'Not an organization member' using errcode='42501'; end if;
  return query select m.user_id,m.role,u.email::text,coalesce(u.raw_user_meta_data->>'display_name',u.email::text)
    from public.clipkit_members m join auth.users u on u.id=m.user_id where m.organization_id=org;
end $$;

create function public.clipkit_set_drive_folder(org uuid, folder_id text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if public.clipkit_role(org) is distinct from 'owner' then raise exception 'Owner only' using errcode='42501'; end if;
  update public.clipkit_organizations set drive_folder_id=folder_id where id=org;
  insert into public.clipkit_activity(organization_id,actor_id,action,detail)
    values (org,auth.uid(),'drive_folder_changed',jsonb_build_object('folder_id',folder_id));
end $$;

create function public.clipkit_review_assets(org uuid, asset_ids uuid[], next_status text, expected_revisions jsonb, note text default '') returns integer
language plpgsql security definer set search_path = '' as $$
declare member_role text; item public.clipkit_assets; found integer := 0; total integer;
begin
  member_role := public.clipkit_role(org);
  if member_role is null then raise exception 'Not an organization member' using errcode = '42501'; end if;
  select count(distinct x) into total from unnest(asset_ids) as x;
  if total = 0 or total > 500 then raise exception 'Select 1 to 500 projects'; end if;
  if next_status not in ('editing','awaiting_lead','awaiting_review','changes_requested','approved') then raise exception 'Invalid status'; end if;
  if next_status in ('awaiting_review','changes_requested','approved') and member_role not in ('owner','lead') then
    raise exception 'Review decisions require a lead' using errcode = '42501';
  end if;
  if next_status in ('changes_requested','approved') and length(btrim(note)) = 0 then raise exception 'Record review feedback or client approval evidence'; end if;
  for item in select * from public.clipkit_assets where organization_id=org and id=any(asset_ids) order by id for update loop
    found := found + 1;
    if item.kind <> 'project' then raise exception 'Only projects have delivery status'; end if;
    if (expected_revisions->>item.id::text)::integer is distinct from item.revision then raise exception 'Project changed; refresh before deciding' using errcode='40001'; end if;
    if not ((item.status in ('editing','changes_requested') and next_status='awaiting_lead')
      or (item.status='changes_requested' and next_status='editing')
      or (member_role in ('owner','lead') and (
        (item.status='awaiting_lead' and next_status in ('awaiting_review','changes_requested'))
        or (item.status='awaiting_review' and next_status in ('approved','changes_requested'))
        or (item.status='approved' and next_status='editing' and length(btrim(note))>0)))) then
      raise exception 'Invalid review transition: % to %',item.status,next_status;
    end if;
    update public.clipkit_assets set status=next_status,revision=revision+1,updated_by=auth.uid(),updated_at=now() where id=item.id;
    insert into public.clipkit_activity(organization_id,actor_id,asset_id,action,detail)
      values (org,auth.uid(),item.id,'delivery_changed',jsonb_build_object('from',item.status,'to',next_status,'note',note,'revision',item.revision+1));
  end loop;
  if found <> total then raise exception 'A selected project is missing or belongs to another organization'; end if;
  return found;
end $$;

revoke execute on function public.clipkit_role(uuid), public.clipkit_create_organization(text), public.clipkit_add_member(uuid,text,text), public.clipkit_register_asset(uuid,text,text,uuid), public.clipkit_review_assets(uuid,uuid[],text,jsonb,text) from public, anon;
grant execute on function public.clipkit_role(uuid), public.clipkit_create_organization(text), public.clipkit_add_member(uuid,text,text), public.clipkit_register_asset(uuid,text,text,uuid), public.clipkit_review_assets(uuid,uuid[],text,jsonb,text) to authenticated;
revoke execute on function public.clipkit_member_directory(uuid),public.clipkit_set_drive_folder(uuid,text) from public,anon;
grant execute on function public.clipkit_member_directory(uuid),public.clipkit_set_drive_folder(uuid,text) to authenticated;
