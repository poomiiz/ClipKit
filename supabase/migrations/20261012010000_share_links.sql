-- A Google Drive share link on a project, so a reviewer can open the cut on a phone. The owner pastes it (or the
-- app's Share Drive link button saves it); a lead or admin may set it too. A project with a link and no synced MP4
-- can be submitted for review.
alter table public.projects add column share_url text
 check (share_url is null or (length(share_url)<=500 and share_url ~ '^https://(drive|docs)[.]google[.]com/[^[:space:]]+$'));

create function public.clipkit_set_share_link(org uuid,project uuid,link text) returns void
language plpgsql security definer set search_path='' as $$
declare item public.projects; member_role text; clean text:=nullif(btrim(link),'');
begin
 member_role:=public.clipkit_role(org);
 if member_role is null then raise exception 'Organization member only' using errcode='42501'; end if;
 select * into item from public.projects where id=project and organization_id=org for update;
 if not found then raise exception 'Project missing or outside organization'; end if;
 if item.owner_id is distinct from auth.uid() and member_role not in ('admin','lead') then
  raise exception 'Project owner, lead or admin only' using errcode='42501'; end if;
 update public.projects set share_url=clean,updated_by=auth.uid(),updated_at=now() where id=project;
 insert into public.clipkit_activity(organization_id,actor_id,asset_id,action,detail)
  values(org,auth.uid(),project,'share_link_changed',jsonb_build_object('link',clean));
end $$;
revoke all on function public.clipkit_set_share_link(uuid,uuid,text) from public,anon;
grant execute on function public.clipkit_set_share_link(uuid,uuid,text) to authenticated;

-- Same as 20261011010000 except the submit check: a pasted share link counts as the export.
create or replace function public.clipkit_project_action(org uuid,project_ids uuid[],next_status text,expected_revisions jsonb,note text default '',export_file text default null,export_bytes bigint default null) returns integer
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
    if item.export_name is null and item.share_url is null then raise exception 'Export MP4 or paste a share link before submitting'; end if;
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
