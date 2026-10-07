// Run: node scripts/system_controls_test.cjs. No real process is controlled.
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../app/static/shell.js'), 'utf8');
const script = source.split('// Manual system controls:')[1].split('// End manual system controls.')[0];
const code = script.slice(script.indexOf('\n'));

function run({fallback = false, action = 'restart', fail = false, unchanged = false} = {}) {
  let now = 0, calls = [], reloaded = false, checks = 0;
  const buttons = [{disabled:false}, {disabled:false}];
  const status = {textContent:''};
  const ids = {ckRestart:buttons[0], ckShutdown:buttons[1], ckSystemStatus:status, sbVer:{}};
  vm.runInNewContext(code, {
    document: {createElement: () => ({querySelectorAll: () => buttons}), getElementById: id => ids[id]},
    aside: {insertBefore(){}}, AbortSignal: {timeout: () => ({})}, crypto:{randomUUID: () => 'test-id'},
    location:{port:'8770',reload:()=>{reloaded=true}}, confirm:()=>true,
    Date:{now:()=>now}, setTimeout:(fn,ms)=>{now+=ms; fn()},
    fetch:async (url,opts={})=>{
      calls.push(url);
      if(url==='/api/window/health') {
        checks++;
        if(checks>1 && action==='shutdown') throw new Error('closed');
        return {ok:true,json:async()=>({ready:true,instance:checks===1 || unchanged ? 10 : 11,busy:false})};
      }
      if(url.startsWith('/api/window/')) {
        if(fallback) throw new Error('server hung');
        return {ok:true,json:async()=>({instance:10})};
      }
      if(opts.method==='POST') return {ok:true,json:async()=>({request_id:'test-id',state:'queued'})};
      return {ok:true,json:async()=>({state:fail?'failed':'succeeded',error:fail?'foreign process refused':undefined})};
    }
  });
  return {click:()=>ids[action==='restart'?'ckRestart':'ckShutdown'].onclick(), calls,status,
    reloaded:()=>reloaded,buttons};
}
(async()=>{
  let test=run(); await test.click(); assert(test.reloaded());
  test=run({unchanged:true}); await test.click(); assert(!test.reloaded()); assert.match(test.status.textContent,/ไม่สำเร็จ/);
  test=run({action:'shutdown'}); await test.click(); assert.match(test.status.textContent,/ปิดระบบแล้ว/);
  assert(!test.calls.some(url=>url.includes('/start'))); assert(!test.reloaded());
  test=run({fallback:true}); await test.click(); assert(test.reloaded());
  assert(test.calls.includes('http://localhost:8765/bot/api/video-editor/control/test-id'));
  test=run({fallback:true,fail:true,action:'shutdown'}); await test.click();
  assert.match(test.status.textContent,/foreign process refused/); assert(!test.reloaded());
  assert(test.buttons.every(b=>!b.disabled));
  assert(!source.includes('new EventSource('), 'closed pages must not control process lifetime');
  console.log('PASS standalone controls: changed-instance restart, shutdown, hung-server fallback, failure, no auto-start');
})().catch(error=>{console.error(error);process.exitCode=1});
