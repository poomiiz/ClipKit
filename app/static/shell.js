// ClipKit app shell: draws the sidebar on every page and marks where you are.
(() => {
  // one line-icon set for the whole app (same stroke style as the sidebar): emoji in page text become these icons
  const L = {
    err: '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
    ok: '<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>',
    check: '<path d="M5 12l5 5 9-10"/>',
    warn: '<path d="M12 3l10 18H2z"/><path d="M12 10v4M12 17.5v.5"/>',
    zap: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
    film: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4"/>',
    music: '<path d="M9 18V5l11-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="17" cy="16" r="3"/>',
    cut: '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M8.1 8.1L20 20M8.1 15.9L20 4"/>',
    spark: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 15l.7 1.8 1.8.7-1.8.7L19 20l-.7-1.8-1.8-.7 1.8-.7z"/>',
    tag: '<path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
    undo: '<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 010 12h-3"/>',
    save: '<path d="M5 3h11l4 4v13a1 1 0 01-1 1H5a1 1 0 01-1-1V4a1 1 0 011-1z"/><path d="M8 3v5h8V3M8 21v-7h8v7"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    bot: '<rect x="4" y="8" width="16" height="12" rx="2"/><path d="M12 4v4M9 13v1M15 13v1M9 17h6"/>',
    mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3"/>',
    image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-9 9"/>',
    palette: '<path d="M12 3a9 9 0 100 18c1.1 0 1.6-.9 1.2-1.8-.5-1-.1-2.2 1.2-2.2H17a4 4 0 004-4c0-5.5-4-10-9-10z"/><circle cx="7.5" cy="11" r="1"/><circle cx="10" cy="7" r="1"/><circle cx="15" cy="7" r="1"/>',
    export: '<path d="M12 15V3M7 8l5-5 5 5"/><path d="M4 14v5a2 2 0 002 2h12a2 2 0 002-2v-5"/>',
    up: '<path d="M12 20V4M5 11l7-7 7 7"/>',
    folder: '<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>',
    fix: '<path d="M14.7 6.3a4 4 0 00-5.4 5.2L3 17.8V21h3.2l6.3-6.3a4 4 0 005.2-5.4l-2.6 2.6-2.4-.6-.6-2.4z"/>',
    sound: '<path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M16 9a4 4 0 010 6M19 6a8 8 0 010 12"/>',
    timer: '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2M9 2h6"/>',
    chat: '<path d="M4 5h16v11H9l-5 4z"/>',
    eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    redo: '<path d="M20 11a8 8 0 00-14-5L4 8M4 4v4h4M4 13a8 8 0 0014 5l2-2M20 20v-4h-4"/>',
    spell: '<path d="M3 18l5-12 5 12M5 14h6"/><path d="M15 15l2.5 2.5L22 12"/>',
    hand: '<path d="M8 13V5.5a1.5 1.5 0 013 0V11M11 10V4.5a1.5 1.5 0 013 0V11M14 10.5V6a1.5 1.5 0 013 0v8a7 7 0 01-7 7 6 6 0 01-5-2.7L3.5 15a1.5 1.5 0 012.5-1.7L8 15"/>',
    go: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    note: '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h7M9 17h5"/>',
    pen: '<path d="M4 20l4-1 11-11-3-3L5 16z"/><path d="M14 6l3 3"/>',
    type: '<path d="M5 7V5h14v2M12 5v14M9 19h6"/>',
    square: '<rect x="4" y="4" width="16" height="16" rx="2"/>',
    kbd: '<rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10"/>',
  };
  const E = {'❌': 'err', '✅': 'ok', '✓': 'check', '⚠': 'warn', '⚡': 'zap', '🎬': 'film', '🎞': 'film', '🎵': 'music',
    '✂': 'cut', '✨': 'spark', '🏷': 'tag', '↶': 'undo', '↺': 'undo', '💾': 'save', '🔎': 'search', '🔍': 'search',
    '🤖': 'bot', '🎙': 'mic', '🖼': 'image', '🎨': 'palette', '📤': 'export', '⬆': 'up', '📂': 'folder', '📁': 'folder',
    '🩹': 'fix', '🔊': 'sound', '⏱': 'timer', '⏳': 'timer', '💬': 'chat', '👀': 'eye', '🔄': 'redo', '🔤': 'spell',
    '✋': 'hand', '🚀': 'go', '📝': 'note', '✍': 'pen',
    '🅰': 'type', '⬜': 'square', '⌨': 'kbd'};
  window.ckIcon = (k, e = '') => `<svg class="ck-ic ck-ic-${k}" viewBox="0 0 24 24" aria-hidden="true"><desc>${e}</desc>${L[k]}</svg>`;
  // <desc> keeps the emoji in textContent, so code that reads messages (the ❌ watcher below) still sees it
  const RE = new RegExp('(' + Object.keys(E).join('|') + ')️?', 'u');
  const SKIP = /^(SCRIPT|STYLE|TEXTAREA|OPTION|TITLE|desc|INPUT)$/;
  const fix = node => {
    const p = node.parentNode;
    if (!p || SKIP.test(p.nodeName) || p.isContentEditable || !RE.test(node.data)) return;
    const parts = node.data.split(new RegExp(RE.source, 'gu'));   // text, emoji, text, emoji, …
    const f = document.createDocumentFragment();
    parts.forEach((t, k) => {
      if (k % 2 === 0) { if (t) f.append(t); }
      else f.append(document.createRange().createContextualFragment(window.ckIcon(E[t], t)));
    });
    p.replaceChild(f, node);
  };
  const swap = root => {
    if (root.nodeType === 3) return fix(root);
    if (root.nodeType !== 1) return;
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), hits = [];
    while (w.nextNode()) if (RE.test(w.currentNode.data)) hits.push(w.currentNode);
    hits.forEach(fix);
  };
  swap(document.body);
  new MutationObserver(ms => ms.forEach(m => m.type === 'characterData' ? fix(m.target) : m.addedNodes.forEach(swap)))
    .observe(document.body, {subtree: true, childList: true, characterData: true});

  // progress bar for a long job: stages, the one running now (i), and a note (time, what is left)
  window.ckTime = s => Math.floor(s / 60) + ':' + String(Math.round(s % 60)).padStart(2, '0');
  window.ckBar = (stages, i, note = '') => {
    const n = stages.length, pct = Math.round(Math.min(i, n) / n * 100);
    return `<div class="ckp"><div class="ckp-top"><b>${pct}%</b><span>${i < n ? `ขั้น ${i + 1}/${n} · ${stages[i]}` : 'เสร็จ'}` +
      `${note ? ' · ' + note : ''}</span></div><div class="ckp-bar"><i style="width:${pct}%"></i></div>` +
      `<div class="ckp-steps">${stages.map((s, k) => `<span class="${k < i ? 'done' : k === i ? 'on' : ''}">${s}</span>`).join('')}</div></div>`;
  };
  // wait for a long API call while showing the step the server says it is on (GET /api/video/progress)
  window.ckTrack = async (path, call, show) => {
    let live = true;
    (async () => {
      while (live) {
        await new Promise(r => setTimeout(r, 1200));
        const r = await fetch('/api/video/progress?path=' + encodeURIComponent(path)).catch(() => null);
        if (live && r && r.ok) show(await r.json());
      }
    })();
    try { return await call; } finally { live = false; }
  };

  if (window !== window.top) return;   // embedded inside the editor: no second sidebar
  const I = {
    home: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/>',
    clip: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M10 9l5 3-5 3z"/>',
    cover: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-9 9"/>',
    motion: '<path d="M4 7h10M4 12h16M4 17h7"/><path d="M18 4l1 2 2 1-2 1-1 2-1-2-2-1 2-1z"/>',
    style: '<path d="M4 20l4-1 11-11-3-3L5 16z"/><path d="M14 6l3 3"/>',
    drafts: '<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z"/>',
  };
  window.CLIPKIT_ICONS = I;
  document.head.insertAdjacentHTML('beforeend', '<link rel="icon" href="/logo.svg" type="image/svg+xml">');
  const svg = k => `<svg viewBox="0 0 24 24">${I[k]}</svg>`;
  const NAV = [
    // starting or continuing a clip lives on the home tiles; the sidebar only moves between pages
    ['', [['home', 'หน้าแรก', '/video-editor.html'], ['style', 'คลังสไตล์', '/styles.html']]],
  ];
  const here = location.pathname + location.hash;
  const isOn = href => href === here || (href === location.pathname && !location.hash && !href.includes('#'));
  const aside = document.createElement('nav');
  aside.className = 'sb';
  aside.innerHTML = `<a class="sb-brand" href="/video-editor.html"><img class="sb-logo" src="/logo.svg" alt="">
      <span class="sb-name">ClipKit<small>Video → CapCut</small></span></a>` +
    '<button class="sb-fold" id="sbFold" title="ย่อ / ขยายแถบซ้าย"><svg viewBox="0 0 24 24"><path d="M15 6l-6 6 6 6"/></svg></button>' +
    NAV.map(([g, items]) => (g ? `<div class="sb-group">${g}</div>` : '<div style="height:8px"></div>') + items.map(([k, label, href]) =>
      `<a class="sb-item${isOn(href) ? ' on' : ''}" href="${href}" title="${label}">${svg(k)}<span>${label}</span></a>`).join('')).join('') +
    '<div class="sb-group">ไฟล์ดิบ</div><div class="sb-projects" id="sbProjects"><div class="sb-empty">กำลังอ่าน…</div></div>' +
    `<a class="sb-item" href="#" id="sbBug" title="แจ้งปัญหา"><svg viewBox="0 0 24 24"><path d="M8 8a4 4 0 018 0v6a4 4 0 01-8 0z"/><path d="M4 12h4M16 12h4M5 6l3 2M19 6l-3 2M5 19l3-2M19 19l-3-2"/></svg><span>แจ้งปัญหา</span></a>` +
    `<a class="sb-item${isOn('/settings.html') ? ' on' : ''}" href="/settings.html" title="ตั้งค่า">${svg('settings')}<span>ตั้งค่า</span></a>` +
    '<div class="sb-foot" id="sbVer">ClipKit</div>';
  document.body.prepend(aside);
  // fold the sidebar to icons only (remembered on this machine)
  let mini = false;
  try { mini = localStorage.getItem('ck_sb_mini') === '1'; } catch {}
  document.documentElement.classList.toggle('sb-mini', mini);
  document.getElementById('sbFold').onclick = () => {
    mini = !mini;
    document.documentElement.classList.toggle('sb-mini', mini);
    try { localStorage.setItem('ck_sb_mini', mini ? '1' : '0'); } catch {}
  };
  // drag the right edge to widen the sidebar (remembered on this machine)
  const SB_MIN = 180, SB_MAX = 520;
  let sbW = 0;
  const setW = w => { sbW = Math.min(SB_MAX, Math.max(SB_MIN, w)); document.documentElement.style.setProperty('--sb-user-w', sbW + 'px'); };
  try { const w = +localStorage.getItem('ck_sb_w'); if (w) setW(w); } catch {}
  const grip = document.createElement('div');
  grip.className = 'sb-grip';
  grip.title = 'ลากเพื่อขยาย / ย่อแถบซ้าย · ดับเบิลคลิก = ขนาดเดิม';
  aside.append(grip);
  grip.onpointerdown = e => {
    e.preventDefault();
    grip.setPointerCapture(e.pointerId);
    document.documentElement.classList.add('sb-drag');
    const w0 = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--sb-w')), x0 = e.clientX;
    grip.onpointermove = ev => setW(w0 + ev.clientX - x0);
    grip.onpointerup = () => {
      grip.onpointermove = grip.onpointerup = null;
      document.documentElement.classList.remove('sb-drag');
      try { if (sbW) localStorage.setItem('ck_sb_w', Math.round(sbW)); } catch {}
    };
  };
  grip.ondblclick = () => {
    document.documentElement.style.removeProperty('--sb-user-w');
    try { localStorage.removeItem('ck_sb_w'); } catch {}
  };
  // raw files on the left, the projects cut from each one underneath (click a raw file = pick its stories again)
  window.ckLoadProjects = async () => {
    const box = document.getElementById('sbProjects');
    let open = {};
    try { open = JSON.parse(localStorage.getItem('ck_sb_open') || '{}'); } catch {}
    try {
      const r = await fetch('/api/kit/raw-groups');
      if (!r.ok) throw new Error(r.status);
      const {groups} = await r.json();
      box.innerHTML = groups.length ? '' : '<div class="sb-empty">ยังไม่มีงาน · ลากไฟล์ดิบมาวางที่หน้าแรก</div>';
      groups.forEach(g => {
        const wrap = document.createElement('div');
        wrap.className = 'sb-raw' + (open[g.raw] ? ' open' : '');
        wrap.innerHTML = `<div class="sb-raw-h"><button class="tw" title="กาง/หุบ">▸</button><a class="rn"></a><span class="cnt">${g.projects.length}</span></div><div class="sb-raw-b"></div>`;
        const rn = wrap.querySelector('.rn');
        rn.textContent = g.name;
        rn.title = g.raw ? (g.exists ? g.raw : g.raw + ' (ไม่พบไฟล์แล้ว)') : 'โปรเจกต์ที่ไม่รู้ว่าตัดจากไฟล์ไหน';
        if (!g.exists) rn.classList.add('gone');
        rn.href = g.exists ? '/video-editor.html?raw=' + encodeURIComponent(g.raw) : '#';
        rn.onclick = e => {
          if (!g.exists) { e.preventDefault(); wrap.querySelector('.tw').click(); return; }
          if (window.ckOpenRaw) { e.preventDefault(); window.ckOpenRaw(g.raw); }
        };
        wrap.querySelector('.tw').onclick = () => {
          wrap.classList.toggle('open');
          open[g.raw] = wrap.classList.contains('open');
          try { localStorage.setItem('ck_sb_open', JSON.stringify(open)); } catch {}
        };
        const body = wrap.querySelector('.sb-raw-b');
        g.projects.forEach(d => {
          const a = document.createElement('a');
          a.className = 'sb-proj';
          a.href = '/video-editor.html?open=' + encodeURIComponent(d.path);
          a.title = d.name;
          a.innerHTML = `<span class="k ${d.kind}">${d.kind === 'capcut' ? 'CC' : 'HF'}</span><span class="n"></span>`;
          a.querySelector('.n').textContent = d.name;
          a.onclick = e => { if (window.ckOpenProject) { e.preventDefault(); window.ckOpenProject(d.path); } };
          body.appendChild(a);
        });
        box.appendChild(wrap);
      });
    } catch (e) { box.innerHTML = '<div class="sb-empty">❌ อ่านรายการงานไม่ได้</div>'; }
  };
  window.ckLoadProjects();
  // light refresh: coming back to the window re-reads the project list (work done in CapCut / Studio / chat)
  window.addEventListener('focus', () => window.ckLoadProjects());
  // a new version installed while this page was open: one small bar to reload, nothing reloads by itself
  let seenCommit = null;
  setInterval(() => fetch('/api/kit/version').then(r => r.json()).then(v => {
    if (seenCommit === null) { seenCommit = v.commit; return; }
    if (v.commit !== seenCommit && !document.getElementById('ckReload')) {
      const bar = document.createElement('div');
      bar.id = 'ckReload';
      bar.style.cssText = 'position:fixed;bottom:16px;right:16px;z-index:200;background:#1d2236;border:1px solid #7c5cff;' +
        'border-radius:10px;padding:8px 12px;color:#f1f4fb;font-size:13.5px;display:flex;gap:10px;align-items:center';
      bar.innerHTML = 'หน้านี้มีเวอร์ชันใหม่ <button style="background:#7c5cff;color:#fff;border:0;border-radius:7px;padding:4px 12px;cursor:pointer;font:inherit">รีเฟรช</button>';
      bar.querySelector('button').onclick = () => location.reload();
      document.body.appendChild(bar);
    }
  }).catch(() => {}), 30000);
  // bug report: keeps the last errors seen on the page so the report says what actually broke
  const errs = [];
  // a page error is also sent to the team on its own (the server sends each one once and honours auto_bug_report)
  const autoReport = msg => fetch('/api/kit/bug-report', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({text: '[auto] ' + msg, page: location.pathname + location.search, errors: errs.slice(-10), auto: true})})
    .catch(() => {});  // the server is down: nothing can take the report, and the next error tries again
  const pageError = msg => { errs.push(msg); autoReport(msg); };
  window.addEventListener('error', e => pageError(`${e.message} @ ${(e.filename || '').split('/').pop()}:${e.lineno}`));
  window.addEventListener('unhandledrejection', e => pageError('promise: ' + ((e.reason && e.reason.message) || e.reason)));
  const ce = console.error;
  console.error = (...a) => { errs.push(a.map(String).join(' ').slice(0, 300)); ce.apply(console, a); };
  new MutationObserver(() => {   // red ❌ messages the pages show to people
    document.querySelectorAll('#toast, .msg, .busy, #result').forEach(el => {
      const t = (el.textContent || '').trim();
      if (t.startsWith('❌') && errs[errs.length - 1] !== t) errs.push(t.slice(0, 300));
    });
  }).observe(document.body, {subtree: true, childList: true, characterData: true});
  document.getElementById('sbBug').onclick = e => {
    e.preventDefault();
    if (document.getElementById('ckBug')) return;
    const m = document.createElement('div');
    m.id = 'ckBug';
    m.style.cssText = 'position:fixed;inset:0;z-index:300;background:rgba(0,0,0,.55);display:grid;place-items:center';
    m.innerHTML = `<div style="background:#141824;border:1px solid #262d40;border-radius:14px;padding:20px;width:min(520px,92vw);color:#f1f4fb">
      <b style="font-size:17px">แจ้งปัญหา</b>
      <div style="color:#828ca4;font-size:13px;margin:4px 0 10px">เล่าว่ากดอะไร แล้วเกิดอะไรขึ้น · ระบบแนบหน้าที่เปิดอยู่ เวอร์ชัน และ error ล่าสุด ${errs.length} รายการให้เอง</div>
      <textarea rows="5" style="width:100%;background:#1b2030;color:#f1f4fb;border:1px solid #262d40;border-radius:10px;padding:10px;font:inherit" placeholder="เช่น กดส่งออก MP4 แล้วขึ้น error…"></textarea>
      <div class="r" style="color:#828ca4;font-size:13px;min-height:18px;margin-top:6px"></div>
      <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:10px">
        <button class="x" style="background:#1b2030;color:#c5cde0;border:1px solid #262d40;border-radius:9px;padding:8px 14px;cursor:pointer;font:inherit">ปิด</button>
        <button class="s" style="background:#7c5cff;color:#fff;border:0;border-radius:9px;padding:8px 14px;cursor:pointer;font:inherit;font-weight:600">ส่ง</button></div></div>`;
    document.body.appendChild(m);
    const ta = m.querySelector('textarea'), res = m.querySelector('.r');
    ta.focus();
    m.querySelector('.x').onclick = () => m.remove();
    m.querySelector('.s').onclick = async () => {
      try {
        const r = await fetch('/api/kit/bug-report', {method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({text: ta.value, page: location.pathname + location.search, errors: errs})});
        const j = await r.json();
        if (!r.ok) throw new Error(j.detail || r.status);
        if (j.sent) { res.textContent = '✅ ส่งถึงทีมแล้ว ไม่ต้องทำอะไรต่อ'; return; }
        res.innerHTML = '✅ บันทึกในเครื่องแล้ว · <a target="_blank" style="color:#9fb0ff">ส่งเข้า GitHub ของทีม</a> (กดแล้วกด Submit)';
        res.querySelector('a').href = j.issue_url;
        window.open(j.issue_url, '_blank');
      } catch (err) { res.textContent = '❌ ' + err.message; }
    };
  };
  document.body.classList.add('shell');
  // repaint the active item when video-editor switches screens through the hash
  window.addEventListener('hashchange', () => {
    const now = location.pathname + location.hash;
    aside.querySelectorAll('.sb-item').forEach(a => a.classList.toggle('on',
      a.getAttribute('href') === now || (!location.hash && a.getAttribute('href') === location.pathname)));
  });
  // new version on GitHub: one banner at the top when the app opens, one click to update
  if (!sessionStorage.getItem('ck_upd_checked')) {
    sessionStorage.setItem('ck_upd_checked', '1');
    fetch('/api/kit/update-check').then(r => r.json()).then(u => {
      if (!u.available) return;
      const bar = document.createElement('div');
      bar.style.cssText = 'position:fixed;top:12px;left:50%;transform:translateX(-50%);z-index:200;background:#1d2236;' +
        'border:1px solid #7c5cff;border-radius:12px;padding:10px 14px;display:flex;gap:12px;align-items:center;' +
        'color:#f1f4fb;font-size:14px;box-shadow:0 8px 30px rgba(0,0,0,.5);max-width:92vw';
      bar.innerHTML = '<span>มี ClipKit เวอร์ชันใหม่ (' + u.count + ' รายการ)</span>' +
        '<button style="background:#7c5cff;color:#fff;border:0;border-radius:8px;padding:6px 14px;font:inherit;font-weight:600;cursor:pointer">อัปเดต</button>' +
        '<button style="background:none;border:0;color:#828ca4;cursor:pointer;font:inherit">ภายหลัง</button>';
      bar.title = (u.changes || []).join('\n');
      const [go, later] = bar.querySelectorAll('button');
      later.onclick = () => bar.remove();
      go.onclick = async () => {
        go.disabled = true; go.textContent = 'กำลังอัปเดต…';
        try {
          const r = await fetch('/api/kit/update', {method: 'POST'});
          if (!r.ok) throw new Error((await r.json()).detail);
          let j;
          do { await new Promise(x => setTimeout(x, 1500)); j = await fetch('/api/kit/job/update').then(x => x.json()); }
          while (j.status === 'running');
          if (j.status !== 'done') throw new Error((j.log || '').trim().split('\n').pop());
          bar.firstChild.textContent = '✅ อัปเดตแล้ว · ปิดแล้วเปิด ClipKit ใหม่ให้ครบทุกส่วน';
          go.remove(); later.textContent = 'ปิด';
        } catch (e) { bar.firstChild.textContent = '❌ อัปเดตไม่สำเร็จ: ' + e.message; go.disabled = false; go.textContent = 'ลองอีกครั้ง'; }
      };
      document.body.appendChild(bar);
    }).catch(() => {});
  }
  fetch('/api/kit/version').then(r => r.ok ? r.json() : null).then(v => {
    if (v) document.getElementById('sbVer').innerHTML = `เวอร์ชัน <b>${v.version || ''}</b>${v.commit ? ' · ' + v.commit : ''}`;
  }).catch(() => {});
})();
