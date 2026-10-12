-- Queue invitations without creating Auth accounts or sending email.
create table public.clipkit_invitations (
 organization_id uuid not null references public.clipkit_organizations(id) on delete cascade,
 email text not null check(email=lower(btrim(email)) and length(email) between 3 and 320 and email ~ '^[^[:space:]@]+@[^[:space:]@]+$'),
 role text not null check(role in ('lead','editor')),
 invited_by uuid not null references auth.users(id),
 expires_at timestamptz not null default now()+interval '7 days',
 primary key(organization_id,email)
);
alter table public.clipkit_invitations enable row level security;
revoke all on public.clipkit_invitations from public,anon,authenticated;
grant select on public.clipkit_invitations to authenticated;
create policy "admins see pending invitations" on public.clipkit_invitations for select to authenticated
 using(public.clipkit_role(organization_id)='admin');

-- Keep the existing RPC signature and immediate membership for verified accounts.
create or replace function public.clipkit_add_member(org uuid,member_email text,member_role text) returns void
language plpgsql security definer set search_path='' as $$
declare member_id uuid; normalized text:=lower(btrim(member_email));
begin
 if public.clipkit_role(org) is distinct from 'admin' then raise exception 'Admin only' using errcode='42501'; end if;
 if member_role is null or member_role not in ('lead','editor') then raise exception 'Invalid role'; end if;
 if normalized is null or length(normalized) not between 3 and 320 or normalized !~ '^[^[:space:]@]+@[^[:space:]@]+$' then raise exception 'Invalid email'; end if;
 select id into member_id from auth.users where lower(email)=normalized and email_confirmed_at is not null;
 if member_id=auth.uid() then raise exception 'Cannot change your admin role'; end if;
 if member_id is not null then
  insert into public.clipkit_members values(org,member_id,member_role,now()) on conflict(organization_id,user_id) do update set role=excluded.role;
  delete from public.clipkit_invitations where organization_id=org and email=normalized;
 else
  insert into public.clipkit_invitations(organization_id,email,role,invited_by) values(org,normalized,member_role,auth.uid())
  on conflict(organization_id,email) do update set role=excluded.role,invited_by=excluded.invited_by,expires_at=excluded.expires_at;
 end if;
end $$;

create function public.clipkit_pending_invitations() returns table(organization_id uuid,organization_name text,role text,expires_at timestamptz)
language sql stable security definer set search_path='' as $$
 select i.organization_id,o.name,i.role,i.expires_at from public.clipkit_invitations i
 join public.clipkit_organizations o on o.id=i.organization_id
 join auth.users u on u.id=auth.uid() and u.email_confirmed_at is not null and lower(u.email)=i.email
 where i.expires_at>now() and not exists(select 1 from public.clipkit_members m where m.user_id=u.id)
 order by i.expires_at desc
$$;

create function public.clipkit_accept_invitation(org uuid) returns uuid
language plpgsql security definer set search_path='' as $$
declare verified_email text; invited_role text;
begin
 -- Lock the actual Auth identity; client metadata and submitted email are never trusted.
 select lower(email) into verified_email from auth.users where id=auth.uid() and email_confirmed_at is not null for update;
 if verified_email is null then raise exception 'Verified identity required' using errcode='42501'; end if;
 if exists(select 1 from public.clipkit_members where user_id=auth.uid()) then raise exception 'Already in an organization' using errcode='42501'; end if;
 select role into invited_role from public.clipkit_invitations where organization_id=org and email=verified_email and expires_at>now() for update;
 if invited_role is null then raise exception 'Invitation missing or expired' using errcode='42501'; end if;
 insert into public.clipkit_members values(org,auth.uid(),invited_role,now());
 delete from public.clipkit_invitations where email=verified_email;
 return org;
end $$;

create function public.clipkit_cancel_invitation(org uuid,member_email text) returns void
language plpgsql security definer set search_path='' as $$
begin
 if public.clipkit_role(org) is distinct from 'admin' then raise exception 'Admin only' using errcode='42501'; end if;
 delete from public.clipkit_invitations where organization_id=org and email=lower(btrim(member_email));
end $$;
revoke execute on function public.clipkit_pending_invitations(),public.clipkit_accept_invitation(uuid),public.clipkit_cancel_invitation(uuid,text) from public,anon;
grant execute on function public.clipkit_pending_invitations(),public.clipkit_accept_invitation(uuid),public.clipkit_cancel_invitation(uuid,text) to authenticated;
