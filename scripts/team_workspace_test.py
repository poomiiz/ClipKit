"""Owner boundary and external workspace checks without a hosted provider."""
import sys,json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import UUID
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
import team_workspace as w
org=UUID('00000000-0000-0000-0000-000000000010');project=UUID('00000000-0000-0000-0000-000000000020');owner='00000000-0000-0000-0000-000000000001'
def main():
 with TemporaryDirectory() as tmp:
  root=Path(tmp).resolve();shared=root/'team';shared.mkdir();local=root/'private';local.mkdir()
  cfg={'team_workspaces':{str(org):{'path':str(shared),'tool':'syncthing'}}}
  app=FastAPI();app.include_router(w.router)
  item={'id':str(project),'owner_id':owner,'status':'editing','revision':2,'project_type':'capcut'}
  with patch.object(w.kit,'_read_config',return_value=cfg),patch.object(w.kit,'_project_roots',return_value={'capcut':local}),patch.object(w,'BINDINGS',root/'bindings.json'),patch.object(w.hub,'rpc',return_value=3) as rpc,patch.object(w.hub,'session',return_value={'user':{'id':owner}}),patch.object(w,'projects',return_value=[item]),TestClient(app) as client:
   w.writable(shared);(shared/'footage'/'take.mp4').write_bytes(b'footage');(shared/'exports'/'cut.mp4').write_bytes(b'mp4')
   assert w.workspace(org)==shared
   with patch.object(w,'rows',return_value=[{'name':'take.mp4','size_bytes':7},{'name':'not-yet.mp4','size_bytes':100}]):
    available,missing=w.footage(org,object())
    assert available['synced'] and available['path']==str((shared/'footage'/'take.mp4').resolve())
    assert not missing['synced'] and missing['path'] is None
   with patch.object(w.kit.Path,'home',return_value=root/'no-user-search'):
    located=w.kit.locate(w.kit.LocateRequest(name='take.mp4',size=7))
    assert located['path']==str(shared/'footage'/'take.mp4')

   assert w.file_at(shared/'footage','take.mp4',7)
   assert not w.file_at(shared/'footage','take.mp4',8)
   try:w.file_at(shared/'footage','../secret',1)
   except HTTPException as e:assert e.status_code==400
   else:raise AssertionError('traversal accepted')
   path='/api/team/organizations/'+str(org)+'/projects/'+str(project)
   with patch.object(w.kit,'_project',return_value=('capcut',local/'mine')):
    assert client.post(path+'/bind',json={'path':str(local/'mine')}).status_code==200
   assert not list(shared.rglob('*bindings*')) and set(p.name for p in shared.iterdir())=={'footage','exports'}
   from types import SimpleNamespace
   request=SimpleNamespace(method='POST',url=SimpleNamespace(path='/api/kit/draft-open'));w.guard_paths({'path':str(local/'mine')},request)
   item['status']='changes_requested'
   for endpoint in ('/api/kit/draft-open','/api/video/draft'):
    w.guard_paths({'path':str(local/'mine')},SimpleNamespace(method='POST',url=SimpleNamespace(path=endpoint)))
    assert rpc.call_args.args[1]=='clipkit_project_action' and rpc.call_args.args[2]['next_status']=='editing'
   item['status']='editing'
   item['owner_id']='00000000-0000-0000-0000-000000000002'
   try:w.guard_paths({'body':{'path':str(local/'mine'/'draft_content.json')}},request)
   except HTTPException as e:assert e.status_code==403
   else:raise AssertionError('old owner bypassed API guard')
   import os
   here=os.getcwd();os.chdir(root)  # relative to cwd; relpath cannot cross Windows drives (repo on D:, TEMP on C:)
   try:w.guard_paths({'path':os.path.join('private','mine')},request)
   except HTTPException as e:assert e.status_code==403
   else:raise AssertionError('relative path bypassed owner guard')
   finally:os.chdir(here)
   assert client.post(path+'/open',json={'expected_revision':2}).status_code==403
   from app import app as full_app
   import base64
   key=base64.urlsafe_b64encode(str(local/'mine').encode()).decode().rstrip('=')
   with TestClient(full_app,base_url='http://127.0.0.1:8770') as original:
    assert original.post('/api/kit/draft-open',json={'path':str(local/'mine')}).status_code==403
    assert original.get('/api/video/hfp/'+key+'/index.html').status_code==403
   item['owner_id']=owner
   try:w.guard_paths({'path':str(local/'mine')},SimpleNamespace(method='POST',url=SimpleNamespace(path='/api/kit/draft-rename')))
   except HTTPException as e:assert e.status_code==409
   else:raise AssertionError('folder rename would orphan team permissions')
   assert client.post(path+'/rename',json={'name':'Short name','expected_revision':2}).status_code==200
   assert rpc.call_args.args[1]=='clipkit_rename_project'
   item['status']='approved'
   assert client.post(path+'/open',json={'expected_revision':2}).status_code==409
   item['status']='editing'
   assert client.post(path+'/export',json={'expected_revision':2,'name':'cut.mp4','size_bytes':3}).status_code==200
   assert rpc.call_args.args[1]=='clipkit_project_action'
   assert client.post(path+'/share-link',json={'link':'https://evil.example/drive.google.com/x'}).status_code==400
   assert client.post(path+'/share-link',json={'link':' https://drive.google.com/file/d/abc/view '}).json()=={'share_url':'https://drive.google.com/file/d/abc/view'}
   assert rpc.call_args.args[1:]==('clipkit_set_share_link',{'org':str(org),'project':str(project),'link':'https://drive.google.com/file/d/abc/view'})
   assert client.post(path+'/share-link',json={'link':''}).json()=={'share_url':None}
   assert client.post(path+'/export',json={'expected_revision':2,'name':'missing.mp4','size_bytes':3}).status_code==409
   item.update(status='awaiting_review',updated_by=owner,updated_at='2026-10-11T00:00:00Z')
   historical={str((local/'mine').resolve()).lower():{'status':'approved'},str((local/'unbound').resolve()).lower():{'status':'editing'}}
   with patch.object(w,'projects',return_value=[item]) as get_projects:
    statuses=w.delivery_view(request,historical)
    team_record=statuses[str((local/'mine').resolve()).lower()]
    assert team_record['source']=='team' and team_record['status']=='awaiting_review'
    assert statuses[str((local/'unbound').resolve()).lower()]['source']=='historical'
    get_projects.assert_called_once()
   for code in (401,502):
    with patch.object(w,'projects',side_effect=HTTPException(code,'provider unavailable')):
     record=w.delivery_view(request,historical)[str((local/'mine').resolve()).lower()]
     assert 'error' in record and 'status' not in record
   with TestClient(full_app,base_url='http://127.0.0.1:8770') as original,patch.object(w.kit,'_delivery_statuses',return_value=historical):
    response=original.get('/api/kit/delivery-status')
    assert response.status_code==200 and response.json()['statuses'][str((local/'mine').resolve()).lower()]['source']=='team'
    for role in ('editor','lead','admin'):
     with patch.object(w.hub,'organizations',return_value=[{'clipkit_members':[{'user_id':owner,'role':role}]}]):
      for page in ('/review.html','/REVIEW.HTML','/%2e/review.html','/%5Creview.html'):
       response=original.get(page)
       assert response.status_code in ((403,) if role=='editor' else (200,404)),(role,page,response.status_code)
    with patch.object(w.hub,'session',side_effect=HTTPException(401,'sign in')):
     assert original.get('/review.html',follow_redirects=False).status_code==303

   with patch.object(w.kit,'KIT',shared/'footage'):
    try:w.workspace(org)
    except HTTPException as e:assert e.status_code==409
    else:raise AssertionError('machine metadata inside sync accepted')
   with patch.object(w.kit,'_project_roots',return_value={'capcut':shared/'footage'/'drafts'}):
    try:w.workspace(org)
    except HTTPException as e:assert e.status_code==409
    else:raise AssertionError('private drafts inside sync accepted')
 print('PASS workspace isolation, stable filename/size lookup, private project binding, owner and approved locks, MP4 submission')
if __name__=='__main__':main()
