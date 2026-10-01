from kitconfig import DRAFTS, ROOT_META, font_file  # machine paths live in config.json
# -*- coding: utf-8 -*-
"""Move mouse-click SFX to the orange card pop times. usage: python clicks_follow.py "<project>" """
import json,os,sys,glob,shutil
P=os.path.join(DRAFTS,sys.argv[1],'draft_content.json'); d=json.load(open(P,encoding='utf-8'))
tex={t['id']:t for t in d['materials']['texts']}; auds={a['id']:a for a in d['materials']['audios']}
def size(s): return json.loads(tex[s['material_id']]['content'])['styles'][0]['size']
cards=[t for t in d['tracks'] if t['type']=='text' and len(t['segments'])>5 and not all(size(s)<=10 for s in t['segments'])]
white=min(cards,key=lambda t:sum(size(s) for s in t['segments'])/len(t['segments']))
orange=[t for t in cards if t is not white][0]
starts=sorted(s['target_timerange']['start'] for s in orange['segments'])
for t in d['tracks']:
    if t['type']=='audio' and t['segments'] and 'mouse' in auds[t['segments'][0]['material_id']]['name'].lower():
        segs=sorted(t['segments'],key=lambda s:s['target_timerange']['start'])
        for c,a in zip(segs,starts): c['target_timerange']['start']=a
        print('clicks',len(segs),'orange',len(starts))
json.dump(d,open(P,'w',encoding='utf-8'),ensure_ascii=False)
for tl in glob.glob(os.path.join(os.path.dirname(P),'Timelines','*','draft_content.json')): shutil.copy(P,tl)
