"""Cut regeneration uses real cue/layout planning; the encoder boundary is a fixture."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import trim_timing_test as fixture
import capcut_edit
import draft_quality
import host_platform
import kit_settings
import motion_plan
import render
import video_editor
import web_ai_transaction as transaction
import web_ai_identity as identity
import web_ai_json as web


class MotionCutTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.TrimTiming();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.folder=self.f.folder;self.path=str(self.folder);self.calls=[]
        config=self.folder.parent/'config.json';config.write_text('{"render_encoder":"libx264"}')
        self.enterContext(patch.object(render.video_edit.kitconfig,'_CANDIDATES',[config]))
        self.enterContext(patch.object(host_platform,'capcut_running',return_value=False))
        metadata={'duration':8,'width':1920,'height':1080,'fps':30}
        self.enterContext(patch.object(render,'probe',return_value=metadata))
        self.enterContext(patch.object(draft_quality,'probe',return_value=metadata))
        self.make=self.enterContext(patch.object(kit_settings,'make_motion',side_effect=self.encode))

    def encode(self,body):
        self.calls.append(body)
        plan=motion_plan.prepare_template(body.template,body.params,width=body.width,height=body.height,placement=body.placement)
        assets=kit_settings._motion_destination.get() or self.folder/'fixture_motion'
        assets.mkdir(parents=True,exist_ok=True)
        file=assets/f'{len(self.calls)}.mov';file.write_bytes(f'fixture encoded {len(self.calls)}'.encode())
        recipe={key:plan[key] for key in ('template','inputs','hashes','layout_sha256','canvas','placement','bounds','duration')}
        recipe.update(version=1,params=plan['source_params'],media={'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
        return {'file':str(file),'recipe':recipe}

    def install(self,template='sentence-pair',start=2,end=6):
        return video_editor.draft_overlay_add(video_editor.OverlayRequest(path=self.path,template=template,start=start,end=end,
            text='normal keyword',cue_id='0' if template=='sentence-pair' else None))['overlays'][-1]

    def files(self):
        return {name:file.read_bytes() for name,file in transaction._files(self.folder).items()}

    def test_pair_silence_cut_regenerates_actual_word_events_and_undo_keeps_original(self):
        old=self.install();original=Path(old['file']).read_bytes();self.calls.clear()
        video_editor.draft_cut(video_editor.CutRange(path=self.path,start=3.25,end=3.75))
        new=self.f.read('clipkit_overlays.json')[0]
        self.assertEqual(len(self.calls),1)
        self.assertEqual((new['start'],new['duration']),(2,3.5))
        self.assertEqual(new['placement_id'],old['placement_id'])
        events=new['params']['subtitle_events']
        self.assertEqual(next(e for e in events if e['role']=='emphasis')['start'],1.5)
        self.assertEqual(next(e for e in events if e['role']=='normal')['end'],3.5)
        self.assertNotEqual(new['file'],old['file']);self.assertEqual(Path(old['file']).read_bytes(),original)
        video_editor.draft_uncut(video_editor.DraftPath(path=self.path))
        self.assertEqual(self.f.read('clipkit_overlays.json')[0],old)
        self.assertTrue(Path(new['file']).is_file());self.assertEqual(Path(old['file']).read_bytes(),original)

    def test_generic_cut_rerenders_duration_and_subject_zone_clock(self):
        old=self.install('hook-title');self.calls.clear()
        style=self.f.read('clipkit_style.json');style['motion_subject_zones']=[{'start':6,'end':8,'x':0,'y':.8,'w':.1,'h':.1}]
        self.f.write('clipkit_style.json',style)
        video_editor.draft_cut(video_editor.CutRange(path=self.path,start=3.25,end=3.75))
        row=self.f.read('clipkit_overlays.json')[0]
        self.assertEqual(row['params']['duration'],3.5)
        self.assertEqual(row['placement_id'],old['placement_id'])
        self.assertEqual(self.f.read('clipkit_style.json')['motion_subject_zones'][0]['start'],5.5)
        video_editor.draft_uncut(video_editor.DraftPath(path=self.path))
        self.assertEqual(self.f.read('clipkit_style.json'),style)

    def test_cut_before_motion_updates_timeline_anchor_without_render(self):
        old=self.install('hook-title');self.calls.clear()
        capcut_edit.trim_pauses(self.path,ranges=[(0,.5)])
        row=self.f.read('clipkit_overlays.json')[0]
        self.assertEqual(row['anchor'],{'kind':'timeline','start':1.5})
        self.assertEqual(row['file'],old['file']);self.assertEqual(self.calls,[])

    def test_changed_original_or_template_refuses_before_any_project_write(self):
        old=self.install();before=self.files();self.calls.clear()
        Path(old['file']).write_bytes(b'externally changed')
        with self.assertRaisesRegex(capcut_edit.VideoEditError,'เปลี่ยน'):
            capcut_edit.trim_pauses(self.path,ranges=[(3.25,3.75)])
        self.assertEqual(self.files(),before);self.assertEqual(self.calls,[])

    def test_cut_through_owned_spoken_word_requires_new_content_decision(self):
        self.install();before=self.files();self.calls.clear()
        with self.assertRaisesRegex(capcut_edit.VideoEditError,'โดนคำพูด'):
            capcut_edit.trim_pauses(self.path,ranges=[(4.2,4.4)])
        self.assertEqual(self.files(),before);self.assertEqual(self.calls,[])

    def test_render_or_metadata_failure_retains_originals_and_cleans_new_assets(self):
        old=self.install();before=self.files();original=Path(old['file']).read_bytes()
        with patch.object(kit_settings,'make_motion',side_effect=RuntimeError('encoder failed')),self.assertRaisesRegex(RuntimeError,'encoder failed'):
            capcut_edit.trim_pauses(self.path,ranges=[(3.25,3.75)])
        self.assertEqual(self.files(),before)
        with patch.object(capcut_edit,'_save',side_effect=OSError('disk full')),self.assertRaisesRegex(OSError,'disk full'):
            capcut_edit.trim_pauses(self.path,ranges=[(3.25,3.75)])
        self.assertEqual(self.files(),before);self.assertEqual(Path(old['file']).read_bytes(),original)
        self.assertEqual(list((self.folder/'clipkit_motion').rglob('*.mov')),[])

    def test_whole_list_preflight_rejects_short_second_motion_before_render(self):
        self.install('hook-title',0,2);self.install('hook-title',6,8)
        before=self.files();self.calls.clear()
        with self.assertRaises(video_editor.HTTPException):
            capcut_edit.trim_pauses(self.path,ranges=[(.5,1),(6.1,7.9)])
        self.assertEqual(self.files(),before);self.assertEqual(self.calls,[])

    def test_second_render_failure_removes_first_new_asset(self):
        self.install('hook-title',0,2);self.install('hook-title',2,4)
        before=self.files();self.calls.clear()
        def fail(body):
            if self.calls:raise RuntimeError('second encoder failed')
            return self.encode(body)
        with patch.object(kit_settings,'make_motion',side_effect=fail),self.assertRaisesRegex(RuntimeError,'second encoder'):
            capcut_edit.trim_pauses(self.path,ranges=[(.5,1),(3.25,3.75)])
        self.assertEqual(self.files(),before)
        self.assertEqual(list((self.folder/'clipkit_motion').rglob('*.mov')),[])

    def test_source_change_during_render_refuses_cut_and_retains_external_source(self):
        self.install();before=self.files();self.calls.clear()
        def changed(body):
            result=self.encode(body);self.f.source.write_bytes(b'new external source');return result
        with patch.object(kit_settings,'make_motion',side_effect=changed),self.assertRaisesRegex(capcut_edit.VideoEditError,'ข้อมูลอ้างอิงเปลี่ยน'):
            capcut_edit.trim_pauses(self.path,ranges=[(3.25,3.75)])
        self.assertEqual(self.files(),before);self.assertEqual(self.f.source.read_bytes(),b'new external source')

    def test_mid_save_error_restores_metadata_and_removes_failed_undo_step(self):
        self.install();before=self.files();self.calls.clear();write=capcut_edit.atomic.write_text;failed=False
        def fail(file,*args,**kwargs):
            nonlocal failed
            if Path(file)==self.folder/'clipkit_words.json' and not failed:
                failed=True;raise OSError('injected sidecar write')
            return write(file,*args,**kwargs)
        with patch.object(capcut_edit.atomic,'write_text',side_effect=fail),self.assertRaisesRegex(OSError,'sidecar'):
            video_editor.draft_cut(video_editor.CutRange(path=self.path,start=3.25,end=3.75))
        self.assertTrue(failed);self.assertEqual(self.files(),before)
        self.assertEqual(list((self.folder/'clipkit_undo').iterdir()),[])
        self.assertEqual(list((self.folder/'clipkit_motion').rglob('*.mov')),[])

    def test_legacy_undo_does_not_remove_existing_style(self):
        video_editor.draft_cut(video_editor.CutRange(path=self.path,start=0,end=.5))
        undo=next((self.folder/'clipkit_undo').iterdir());manifest=json.loads((undo/'files.json').read_text())
        (undo/'files.json').write_text(json.dumps([name for name in manifest['files'] if name!='clipkit_style.json']))
        (undo/'clipkit_style.json').unlink();style=self.f.read('clipkit_style.json');style['new_setting']='keep'
        self.f.write('clipkit_style.json',style)
        video_editor.draft_uncut(video_editor.DraftPath(path=self.path))
        self.assertEqual(self.f.read('clipkit_style.json'),style)

    def test_failed_rollback_keeps_undo_and_recovery_media(self):
        self.install();before=self.files()
        def failed_save(folder,draft,*args,**kwargs):
            self.f.write('draft_content.json',draft)
            raise OSError('rollback unavailable')
        with patch.object(capcut_edit,'_save',side_effect=failed_save),self.assertRaisesRegex(OSError,'rollback unavailable'):
            video_editor.draft_cut(video_editor.CutRange(path=self.path,start=3.25,end=3.75))
        self.assertEqual(len(list((self.folder/'clipkit_undo').iterdir())),1)
        self.assertEqual(len(list((self.folder/'clipkit_motion').rglob('*.mov'))),1)
        video_editor.draft_uncut(video_editor.DraftPath(path=self.path))
        after=self.files()
        self.assertEqual({name:after.get(name) for name in video_editor.UNDO_FILES},
                         {name:before.get(name) for name in video_editor.UNDO_FILES})

    def test_ai_preview_of_cut_plans_regeneration_without_render_or_original_writes(self):
        self.install('hook-title',0,8);self.calls.clear()
        answer={'clipkit_web_ai':2,'step':'clip','project':self.folder.name,**identity.issue('clip',self.path),
                'cut':[1],'hook':[],'lines':[{'n':1,'cue_id':'0'}, {'n':2,'cue_id':'1','items':[['next','']]}]}
        before={p.relative_to(self.folder).as_posix():p.read_bytes() for p in self.folder.rglob('*') if p.is_file()}
        self.make.reset_mock()
        result=web.preview_clip(self.path,json.dumps(answer))
        self.make.assert_not_called();self.assertEqual(result['motion_action'],'regenerate')
        self.assertEqual(result['motion_plan'][0]['duration'],4)
        self.assertEqual(result['motion_after'],1)
        self.assertEqual(before,{p.relative_to(self.folder).as_posix():p.read_bytes() for p in self.folder.rglob('*') if p.is_file()})


if __name__=='__main__':unittest.main()
