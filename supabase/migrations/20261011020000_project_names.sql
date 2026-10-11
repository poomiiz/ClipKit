-- Rename the authoritative story without moving a private project out of its access binding.
create function public.clipkit_rename_project(org uuid,project uuid,project_name text,expected_revision integer) returns integer
language plpgsql security definer set search_path='' as $$
declare version integer;
begin
 if public.clipkit_role(org) is null then raise exception 'Organization member only' using errcode='42501'; end if;
 update public.projects set name=btrim(project_name),revision=revision+1,updated_by=auth.uid(),updated_at=now()
 where id=project and organization_id=org and owner_id=auth.uid() and status in ('editing','changes_requested') and revision=expected_revision
 returning revision into version;
 if not found then raise exception 'Only the current owner can rename an editable project at this revision' using errcode='42501'; end if;
 return version;
end $$;
revoke all on function public.clipkit_rename_project(uuid,uuid,text,integer) from public,anon;
grant execute on function public.clipkit_rename_project(uuid,uuid,text,integer) to authenticated;
