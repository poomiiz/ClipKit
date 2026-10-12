// EditorKrab shared UI helpers, loaded in <head> of every page (also inside the editor iframe):
// friendly error text and in-app dialogs instead of the browser's alert / confirm / prompt boxes.
(() => {
  const report = text => fetch('/api/kit/bug-report', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({text: '[auto] ' + text, page: location.pathname + location.search, errors: [text], auto: true})})
    .catch(() => {});   // the server is down: the next error tries again

  // what a person reads when something failed: the server's own message, or a plain sentence for app bugs
  window.ckErr = e => {
    const msg = (e && e.message) || String(e);
    if (e instanceof TypeError && /fetch|network|load failed/i.test(msg))
      return 'ติดต่อ EditorKrab ไม่ได้ ตรวจว่าโปรแกรมยังเปิดอยู่ แล้วลองอีกครั้ง';
    if (e instanceof TypeError || e instanceof ReferenceError || e instanceof SyntaxError || e instanceof RangeError) {
      report(`${e.name}: ${msg}\n${(e.stack || '').split('\n').slice(0, 4).join('\n')}`);
      return 'เกิดข้อผิดพลาดในหน้านี้ ส่งรายงานให้ทีมแล้ว ลองรีเฟรชหน้าอีกครั้ง';
    }
    return msg;
  };

  const css = `.ck-dlg{border:1px solid #2f3139;border-radius:12px;padding:0;background:#16171b;color:#ececf1;width:min(420px,92vw);
    box-shadow:0 24px 64px rgba(0,0,0,.55);font:14px/1.55 "Inter","Segoe UI Variable Text","Segoe UI","Leelawadee UI",sans-serif}
  .ck-dlg::backdrop{background:rgba(0,0,0,.55)}
  .ck-dlg form{display:flex;flex-direction:column;gap:14px;padding:18px}
  .ck-dlg p{margin:0;white-space:pre-line;overflow-wrap:anywhere;max-height:50vh;overflow:auto}
  .ck-dlg input{font:inherit;color:inherit;background:#1d1f24;border:1px solid #2a2c33;border-radius:8px;padding:8px 10px;width:100%;box-sizing:border-box}
  .ck-dlg input:focus{outline:none;border-color:#7c5cff}
  .ck-dlg .ck-dlg-row{display:flex;flex-direction:row-reverse;justify-content:flex-start;gap:8px}  /* ok first in the DOM: Enter submits ok */
  .ck-dlg button{font:inherit;font-size:13.5px;font-weight:600;min-height:34px;padding:6px 14px;border-radius:8px;cursor:pointer;
    border:1px solid #2a2c33;background:#1d1f24;color:#ececf1}
  .ck-dlg button[value=ok]{background:#7c5cff;border-color:#7c5cff;color:#fff}
  .ck-dlg.danger button[value=ok]{background:#dc2626;border-color:#dc2626}
  .ck-dlg button:focus-visible{outline:2px solid #b9a8ff;outline-offset:2px}`;
  document.head.insertAdjacentHTML('beforeend', `<style>${css}</style>`);

  // one dialog for all three; resolves true / false, or the typed text / null
  const ask = (text, {input = null, ok = 'ตกลง', cancel = 'ยกเลิก', danger = false} = {}) => new Promise(resolve => {
    const d = document.createElement('dialog');
    d.className = 'ck-dlg' + (danger ? ' danger' : '');
    d.innerHTML = '<form method="dialog"><p></p>' + (input === null ? '' : '<input>') +
      '<div class="ck-dlg-row"><button value="ok"></button>' + (cancel ? '<button value="cancel"></button>' : '') + '</div></form>';
    d.querySelector('p').textContent = text;
    d.querySelector('[value=ok]').textContent = ok;
    if (cancel) d.querySelector('[value=cancel]').textContent = cancel;
    const field = d.querySelector('input');
    if (field) field.value = input;
    d.addEventListener('close', () => {
      d.remove();
      const yes = d.returnValue === 'ok';
      resolve(input === null ? yes : (yes ? field.value : null));
    });
    document.body.append(d);
    d.showModal();
    if (field) field.select(); else d.querySelector(danger && cancel ? '[value=cancel]' : '[value=ok]').focus();   // a delete starts on Cancel
  });
  window.ckConfirm = (text, opt) => ask(text, opt);
  window.ckPrompt = (text, value = '') => ask(text, {input: value});
  window.ckAlert = text => ask(text, {cancel: ''});
})();
