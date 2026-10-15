// Real manual editor handlers must keep cue identity and explicitly separate spelling from choices.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const editor = fs.readFileSync('app/static/editor.html', 'utf8');
const workbench = fs.readFileSync('app/static/video-editor.html', 'utf8');
for (const html of [editor, workbench]) {
  for (const match of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) new vm.Script(match[1]);
}
const phraseCode = editor.slice(editor.indexOf('function sidePhrase('), editor.indexOf('function sideBroll('));
function phrase() {
  const nodes = {}, calls = [];
  const item = {start: 0, end: 2, lead: 'normal', punch: 'keyword', line: 'normal keyword', cue_id: 'second'};
  const context = vm.createContext({
    T: {phrases: [item], caption_en: {}, subtitle_events: [{cue_id: 'second', end: 3}]}, PATH: 'synthetic',
    $: id => nodes[id] ||= {value: ''}, back: () => '', mm: String, esc: String,
    api: async (path, body) => calls.push([path, JSON.parse(JSON.stringify(body))]),
    reload: async () => {}, say() {}, ckErr: e => e.message,
  });
  vm.runInContext(phraseCode, context);
  context.sidePhrase({innerHTML: ''}, item);
  return {nodes, calls};
}
(async () => {
  let {nodes, calls} = phrase();
  nodes.pl.value = 'normal keyword'; nodes.pp.value = '';
  await nodes.ps.onclick();
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], 'draft/phrases');
  assert.equal(calls[0][1].cue_id, 'second');
  assert.ok(!('source_text' in calls[0][1]), 'redistributing words must not rewrite source text');

  ({nodes, calls} = phrase());
  nodes.pp.value = 'different'; nodes.pc.value = 'translation';
  await nodes.ps.onclick();
  assert.equal(calls.length, 1, 'one Save must not persist caption separately before phrase validation');
  assert.equal(calls[0][1].source_text, 'normal different');
  assert.equal(calls[0][1].caption, 'translation');

  ({nodes, calls} = phrase());
  await nodes.pm.onclick();
  assert.equal(calls[0][0], 'draft/overlay');
  assert.equal(calls[0][1].end, 3, 'motion must include canonical caption/hold end');
  assert.equal(calls[0][1].text, 'normal keyword');

  const created = [], submitted = [];
  function node(tag) {
    return {tag, dataset: {}, children: [], appendChild(child) { this.children.push(child); },
      querySelector(selector) {
        const find = n => selector === 'button' ? n.tag === 'button' : n.className === 't';
        return this.children.flatMap(n => [n, ...n.children]).find(find);
      }};
  }
  const controls = {mainAction: {}, subsBusy: {}, emSize: {value: '20'}, emY: {value: '-.2'}, emColor: {value: '#ffffff'}};
  const context = vm.createContext({
    state: {draft: {path: 'synthetic'}}, document: {
      createElement: node, getElementById: id => controls[id], querySelectorAll: () => created,
    }, countEmphasis() {}, ckErr: e => e.message,
    api: async (path, body) => { submitted.push([path, body]); return {subtitles: [], added: 2}; },
  });
  vm.runInContext(workbench.slice(workbench.indexOf('function subRow('), workbench.indexOf('function countEmphasis(')), context);
  vm.runInContext(workbench.slice(workbench.indexOf('async function saveSubs('), workbench.indexOf('/* ── stock footage')), context);
  for (const id of ['first', 'second']) created.push(context.subRow({id, start: 1.234, end: 2.345, text: 'same words'}, false));
  await context.saveSubs();
  assert.deepEqual([...submitted[0][1].subs].map(s => s.id), ['first', 'second']);
  assert.equal(submitted[0][1].subs[0].start, 1.234);
  assert.ok(submitted[0][1].subs.every(s => !('words' in s)), 'manual save must preserve existing word clocks');
  console.log('manual subtitle UI: cue IDs, exact clock, spelling, combined save and motion hold PASS');
})().catch(error => { console.error(error); process.exitCode = 1; });
