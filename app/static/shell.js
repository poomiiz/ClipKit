// ClipKit app shell: draws the sidebar on every page and marks where you are.
(() => {
  if (window !== window.top) return;   // embedded inside the editor: no second sidebar
  const I = {
    home: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/>',
    clip: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M10 9l5 3-5 3z"/>',
    cover: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-9 9"/>',
    motion: '<path d="M4 7h10M4 12h16M4 17h7"/><path d="M18 4l1 2 2 1-2 1-1 2-1-2-2-1 2-1z"/>',
    drafts: '<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z"/>',
  };
  window.CLIPKIT_ICONS = I;
  const svg = k => `<svg viewBox="0 0 24 24">${I[k]}</svg>`;
  const NAV = [
    // starting or continuing a clip lives on the home tiles; the sidebar only moves between pages
    ['', [['home', 'หน้าแรก', '/video-editor.html'], ['settings', 'ตั้งค่า', '/settings.html']]],
  ];
  const here = location.pathname + location.hash;
  const isOn = href => href === here || (href === location.pathname && !location.hash && !href.includes('#'));
  const aside = document.createElement('nav');
  aside.className = 'sb';
  aside.innerHTML = `<a class="sb-brand" href="/video-editor.html"><span class="sb-logo">${svg('clip').replace('<svg', '<svg stroke="#fff" fill="none" stroke-width="2"')}</span>
      <span class="sb-name">ClipKit<small>Video → CapCut</small></span></a>` +
    NAV.map(([g, items]) => (g ? `<div class="sb-group">${g}</div>` : '<div style="height:8px"></div>') + items.map(([k, label, href]) =>
      `<a class="sb-item${isOn(href) ? ' on' : ''}" href="${href}">${svg(k)}<span>${label}</span></a>`).join('')).join('') +
    '<div class="sb-foot" id="sbVer">ClipKit</div>';
  document.body.prepend(aside);
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
