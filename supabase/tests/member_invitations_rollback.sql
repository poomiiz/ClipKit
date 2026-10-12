-- Roll back code first. Preserve pending invitations and all admitted memberships.
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

revoke execute on function public.clipkit_pending_invitations(),public.clipkit_accept_invitation(uuid),public.clipkit_cancel_invitation(uuid,text) from authenticated;
