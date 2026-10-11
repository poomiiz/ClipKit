const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('app/static/team.js','utf8');
const polling=source.slice(source.indexOf('// Refresh'),source.lastIndexOf('loadIdentity().catch'));
let callback,calls=0,busy=false;
const selectors=[];
vm.runInNewContext(polling,{
 identity:{signed_in:true},selectedOrg:'organization',
 document:{querySelectorAll:()=>[],querySelector:selector=>{selectors.push(selector);return busy?{}:null;}},
 loadOrganization:()=>{calls++;return Promise.resolve();},say:()=>{},
 setInterval:fn=>{callback=fn;}
});
callback();assert.equal(calls,1,'Idle lead page must refresh even when transfer selects exist');
busy=true;callback();assert.equal(calls,1,'Editing must prevent refresh');
busy=false;callback();assert.equal(calls,2,'Refresh must resume after editing');
assert(selectors.some(s=>s.includes('select[data-pending="true"]')));
assert(selectors.some(s=>s.includes('form[data-dirty="true"]')));
console.log('PASS idle team refresh and preservation of pending edits');
const activity=source.slice(source.indexOf('d.textContent=(projects.find'),source.indexOf('return d;}',source.indexOf('d.textContent=(projects.find')));
const rendered=vm.runInNewContext('const d={};'+activity+'d.textContent',{
 projects:[{id:'story',name:'เรื่องทดสอบ'}],a:{asset_id:'story',actor_id:'lead',action:'delivery_changed',detail:{from:'awaiting_review',to:'changes_requested',note:'แก้เสียง'},created_at:'2026-10-11T00:00:00Z'},
 person:id=>id,LABELS:{awaiting_review:'รอตรวจ',changes_requested:'ต้องแก้'}
});
assert(rendered.includes('เรื่องทดสอบ · lead · รอตรวจ → ต้องแก้ · แก้เสียง'));
