const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/video-editor.html', 'utf8');
const box = source.slice(source.indexOf('function webAiBox('), source.indexOf('// plain white subtitles', source.indexOf('function webAiBox(')));
const editor = fs.readFileSync('app/static/editor.html', 'utf8');
const editorAi = editor.slice(editor.indexOf('async function downloadAi()'), editor.indexOf('function sideClip('));

async function checkEditor(failure = '', empty = false) {
  const nodes = {aiDownload: {}, aiImport: {}, aiAnswer: {value: empty ? '' : '{"cut":[1]}'}, aiMessage: {}}, calls = [], timers = [];
  let loads = 0;
  const context = {
    $: id => nodes[id], PATH: 'project', SEL: {type: 'sub'},
    document: {createElement: () => ({click() {}})}, Blob: class {},
    URL: {createObjectURL: () => 'blob:test', revokeObjectURL() {}}, setTimeout: fn => timers.push(fn),
    ckErr: e => e.message, say: text => { nodes.aiMessage.textContent = text; },
    load: async () => { loads++; if (failure === 'refresh') throw new Error('refresh failed'); },
    api: async (path, body) => {
      calls.push([path, body]);
      assert.equal(body.step, 'clip'); assert.equal(body.target, 'project');
      if (failure === 'import' && path === 'web-ai/import') throw new Error('invalid answer');
      if (path === 'web-ai/export') return {text: 'packet', name: 'packet.md'};
      if (path === 'web-ai/import') return {lines: 2, cut: 1};
      throw new Error('unexpected ' + path);
    }
  };
  vm.runInNewContext(editorAi, context);
  await context.downloadAi();
  assert.equal(nodes.aiDownload.disabled, false);
  assert.equal(timers.length, 1);
  await context.importAi();
  assert.equal(calls.filter(([p]) => p === 'web-ai/import').length, empty ? 0 : 1);
  assert.equal(loads, empty || failure === 'import' ? 0 : 1);
  assert.equal(nodes.aiAnswer.value, failure === 'import' ? '{"cut":[1]}' : '');
  if (!empty) assert.equal(nodes.aiImport.disabled, false);
  if (failure === 'refresh') {
    await context.importAi();
    assert.equal(calls.filter(([p]) => p === 'web-ai/import').length, 1, 'refresh failure must not replay imported cuts');
  }
}

async function check(via, step = 'clip', fail = false, switched = false, pollFailure = false) {
  const nodes = {}, calls = [], timers = [];
  let guide = 0, filmstrip = 0;
  const context = {
    document: {getElementById: id => nodes[id] ||= {value: '{}'}, createElement: () => ({click() {}})},
    Blob: class {}, URL: {createObjectURL: () => 'blob:test', revokeObjectURL() {}},
    setTimeout: fn => timers.push(fn),
    state: {draft: {path: switched ? 'other' : 'project', subtitles: 9}}, drafts: [],
    renderGuide: () => guide++, loadFilmstrip: () => filmstrip++, ckErr: e => e.message,
    api: async (path, body) => {
      calls.push([path, body]);
      if (path === 'web-ai/export') return {text: 'packet', name: 'packet.md'};
      if (path === 'web-ai/import') return step === 'stories' ? {stories: [{}]} : {lines: 2, cut: 1};
      if (path.startsWith('draft/timeline?')) {
        if (fail) throw new Error('timeline unavailable');
        return {via};
      }
      if (path === 'draft/prepare') return {steps: []};
      if (path === 'drafts') return {drafts: [{path: 'project', subtitles: 2}]};
      throw new Error('unexpected ' + path);
    }
  };
  vm.runInNewContext(box + `; webAiBox('${step}', 'project', 'AI');`, context);
  timers.shift()();
  if (pollFailure) {
    await Object.entries(nodes).find(([id]) => id.endsWith('dl'))[1].onclick();
    timers.shift()(); // release the download URL
    await timers.shift()(); // saved answer imported, then timeline refresh rejects
    assert.equal(timers.length, 0, 'an imported cut answer must not be polled again after refresh fails');
    assert.equal(calls.filter(([path]) => path === 'web-ai/import').length, 1);
  } else {
    await Object.entries(nodes).find(([id]) => id.endsWith('in'))[1].onclick();
  }
  const message = Object.entries(nodes).find(([id]) => id.endsWith('msg'))[1].textContent;
  if (step === 'stories') {
    assert.equal(calls.length, 1);
    assert.match(message, /1 เรื่อง/);
  } else if (fail) {
    assert.match(message, /timeline unavailable/);
    assert.equal(context.state.draft.subtitles, 9);
  } else {
    assert.equal(calls.filter(([p]) => p === 'draft/prepare').length, via === 'clipkit' ? 0 : 1);
    if (via !== 'clipkit') assert.equal(calls.find(([p]) => p === 'draft/prepare')[1].capcut, true);
    assert.equal(context.state.draft.subtitles, switched ? 9 : 2);
    assert.equal(guide, switched ? 0 : 1);
    assert.equal(filmstrip, switched ? 0 : 1);
  }
}

(async () => {
  await check('clipkit');
  await check('capcut');
  await check('clipkit', 'stories');
  await check('clipkit', 'clip', true);
  await check('clipkit', 'clip', true, false, true);
  await check('clipkit', 'clip', false, true);
  await checkEditor();
  await checkEditor('import');
  await checkEditor('refresh');
  await checkEditor('', true);
  assert.match(editor, /\$\('aiDownload'\)\.onclick = downloadAi/);
  assert.match(editor, /\$\('aiImport'\)\.onclick = importAi/);
  assert.match(editor.slice(editor.indexOf('async function load()'), editor.indexOf('let building')), /live\(\)/);
  const auto = source.slice(source.indexOf('async function autoRun()'), source.indexOf('async function saLoad('));
  assert.match(auto, /webAiBox\('clip', state\.draft\.path/);
  assert.doesNotMatch(auto, /agentBox\(/);
  console.log('PASS web AI callers: route, refresh, navigation guard, stories, errors, auto entry');
})().catch(e => { console.error(e); process.exitCode = 1; });
