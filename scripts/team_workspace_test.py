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
  root=Path(tmp);shared=root/'team';shared.mkdir();local=root/'private';local.mkdir()
  cfg={'team_workspaces':{str(org):{'path':str(shared),'tool':'syncthing'}}}
  app=FastAPI();app.include_router(w.router)
  item={'id':str(project),'owner_id':owner,'status':'editing','revision':2,'project_type':'capcut'}
  with patch.object(w.kit,'_read_config',return_value=cfg),patch.object(w.kit,'_project_roots',return_value={'capcut':local}),patch.object(w,'BINDINGS',root/'bindings.json'),patch.object(w.hub,'rpc',return_value=3) as rpc,patch.object(w.hub,'session',return_value={'user':{'id':owner}}),patch.object(w,'projects',return_value=[item]),TestClient(app) as client:
   w.writable(shared);(shared/'footage'/'take.mp4').write_bytes(b'footage');(shared/'exports'/'cut.mp4').write_bytes(b'mp4')
   assert w.workspace(org)==shared
   assert w.file_at(shared/'footage','take.mp4',7)
   assert not w.file_at(shared/'footage','take.mp4',8)
   try:w.file_at(shared/'footage','../secret',1)
   except HTTPException as e:assert e.status_code==400
   else:raise AssertionError('traversal accepted')
   path='/api/team/organizations/'+str(org)+'/projects/'+str(project)
   with patch.object(w.kit,'_project',return_value=('capcut',local/'mine')):
    assert client.post(path+'/bind',json={'path':str(local/'mine')}).status_code==200
   assert not list(shared.rglob('*bindings*')) and set(p.name for p in shared.iterdir())=={'footage','exports'}
   request=object();w.guard_paths({'path':str(local/'mine')},request)
   item['owner_id']='00000000-0000-0000-0000-000000000002'
   try:w.guard_paths({'body':{'path':str(local/'mine'/'draft_content.json')}},request)
   except HTTPException as e:assert e.status_code==403
   else:raise AssertionError('old owner bypassed API guard')
   assert client.post(path+'/open',json={'expected_revision':2}).status_code==403
   item['owner_id']=owner;item['status']='approved'
   assert client.post(path+'/open',json={'expected_revision':2}).status_code==409
   item['status']='editing'
   assert client.post(path+'/export',json={'expected_revision':2,'name':'cut.mp4','size_bytes':3}).status_code==200
   assert rpc.call_args.args[1]=='clipkit_project_action'
   assert client.post(path+'/export',json={'expected_revision':2,'name':'missing.mp4','size_bytes':3}).status_code==409
   with patch.object(w.kit,'_project_roots',return_value={'capcut':shared/'footage'/'drafts'}):
    try:w.workspace(org)
    except HTTPException as e:assert e.status_code==409
    else:raise AssertionError('private drafts inside sync accepted')
 print('PASS workspace isolation, stable filename/size lookup, private project binding, owner and approved locks, MP4 submission')
if __name__=='__main__':main()
