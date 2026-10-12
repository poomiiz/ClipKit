'use strict';
const message = document.getElementById('message');
const google = document.getElementById('googleLogin');
const retry = document.getElementById('retry');
function say(text, error = false) { message.textContent = text; message.classList.toggle('error', error); }
async function account(path, body) {
  const response = await fetch('/api/team/' + path, {cache: 'no-store', signal: AbortSignal.timeout(25000),
    ...(body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {})});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'เข้าสู่ระบบไม่สำเร็จ กรุณาลองใหม่');
  return data;
}
async function connect() {
  google.disabled = true;
  retry.hidden = true;
  try {
    const state = await account('session');
    if (state.signed_in) { location.replace('/video-editor.html'); return; }
    google.disabled = !state.configured;
    say(state.configured ? (new URLSearchParams(location.search).has('login_error') ? 'เข้าสู่ระบบ Google ไม่สำเร็จ กรุณาลองใหม่' : '') : 'ระบบบัญชียังไม่พร้อม กรุณาติดต่อผู้ดูแล', !state.configured);
  } catch (error) { say('เชื่อมต่อไม่ได้ กรุณาลองใหม่', true); retry.hidden = false; }
}
google.onclick = async () => {
  google.disabled = true;
  say('กำลังเปิด Google…');
  try { const data = await account('google', {}); location.assign(data.url); }
  catch (error) { say(error.message, true); google.disabled = false; }
};
retry.onclick = connect;
document.getElementById('login').onsubmit = async event => {
  event.preventDefault();
  const form = event.currentTarget, button = form.querySelector('button');
  button.disabled = true;
  try { await account('login', Object.fromEntries(new FormData(form))); form.reset(); location.replace('/video-editor.html'); }
  catch (error) { say(error.message, true); button.disabled = false; }
};
connect();
const lang = document.getElementById('lang');
lang.textContent = window.ckLang === 'en' ? 'ภาษาไทย' : 'English';
lang.onclick = () => window.ckSetLang(window.ckLang === 'en' ? 'th' : 'en');
