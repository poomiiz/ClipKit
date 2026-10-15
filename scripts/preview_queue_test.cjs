const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('app/static/editor.html','utf8');
const queue=source.slice(source.indexOf('let building ='),source.indexOf('// one save for b-roll'));
const action=source.slice(source.indexOf('async function run('),source.indexOf("$('bAuto').onclick"));
const textCheck=source.slice(source.indexOf('async function checkText('),source.indexOf("$('bExport').onclick"));
const exporter=source.slice(source.indexOf("$('bExport').onclick"),source.indexOf("$('bCapcut').onclick"));
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function harness() {
 const nodes={v:{currentTime:4,style:{},setAttribute(k,v){this[k]=v},addEventListener(){}},empty:{style:{}},bExport:{},off:{dataset:{off:'1'}}};
 nodes.bExport.dataset={};nodes.adv={open:false};const requests=[],pending=[],messages=[];
 const context={PATH:'generated',T:{style:{}},Date,$:id=>nodes[id],ckErr:e=>e.message,esc:String,
  document:{querySelectorAll:()=>[nodes.bExport,nodes.off]},say:value=>messages.push(value),
  WHERE:{},drawTL(){},side(){},setTimeout(){},ckConfirm:async()=>false,
  api:(name)=>{requests.push(name.split('?')[0]);if(name.startsWith('draft/text-check'))return Promise.resolve(context.checkResult||{look:true,problems:[]});if(name==='draft/hf-build')return new Promise((resolve,reject)=>pending.push({resolve,reject}));return Promise.resolve({file:'generated.mp4',seconds:8})}};
 vm.createContext(context);vm.runInContext(queue+action+textCheck+exporter,context);return {context,nodes,requests,pending,messages};
}
(async()=>{
 const h=harness();let firstDone=false,queuedDone=false;
 const first=h.context.live().then(()=>firstDone=true),queued=h.context.live().then(()=>queuedDone=true);
 h.context.live();const exported=h.nodes.bExport.onclick();await tick();
 assert.deepEqual(h.requests,['draft/hf-build'],'export/text mutation must wait for the running preview');
 assert.equal(h.nodes.bExport.disabled,true);assert.equal(queuedDone,false,'queued callers must await actual builds');
 h.pending[0].resolve({url:'first'});await tick();
 assert.deepEqual(h.requests,['draft/hf-build','draft/hf-build']);assert.equal(firstDone,false);assert.equal(queuedDone,false);
 h.pending[1].resolve({url:'latest'});await Promise.all([first,queued,exported]);
 assert.deepEqual(h.requests,['draft/hf-build','draft/hf-build','draft/text-check','draft/hf-export']);
 assert.match(h.nodes.v.src,/^latest\?t=/);assert.equal(h.nodes.bExport.disabled,false);assert.equal(h.nodes.off.disabled,true);
 assert.equal(h.messages.some(m=>m.includes('generated.mp4')),true);
 const failed=harness(),preview=failed.context.live(),afterFailure=failed.nodes.bExport.onclick();await tick();
 assert.deepEqual(failed.requests,['draft/hf-build']);failed.pending[0].reject(Error('preview failed'));
 await Promise.all([preview,afterFailure]);assert.equal(failed.nodes.empty.textContent,'❌ preview failed');
 assert.equal(failed.nodes.bExport.disabled,false);assert.equal(failed.requests.at(-1),'draft/hf-export','final export validates independently after a failed preview');
 await failed.context.run(failed.nodes.bExport,'existing progress',async()=>{throw Error('export failed')});
 assert.equal(failed.messages.at(-1),'❌ export failed');assert.equal(failed.nodes.bExport.disabled,false);assert.equal(failed.nodes.off.disabled,true);
 const declined=harness();declined.context.checkResult={look:true,problems:['unsafe']};await declined.nodes.bExport.onclick();assert.deepEqual(declined.requests,['draft/text-check']);assert.equal(declined.nodes.adv.open,true);assert.equal(declined.nodes.bExport.disabled,false);
 console.log('PASS preview queue: coalesced callers await latest build; real export/text-check wait; failures settle and controls restore');
})().catch(error=>{console.error(error);process.exitCode=1});
