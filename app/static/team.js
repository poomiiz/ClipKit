const $ = id => document.getElementById(id);
const LABELS = {editing:'✂️ กำลังตัด',awaiting_lead:'📤 รอหัวหน้าตรวจ',awaiting_review:'⏳ รอลูกค้าตรวจ',changes_requested:'🛠️ ส่งกลับแก้',approved:'✅ ลูกค้าอนุมัติ'};
const ROLES = {owner:'เจ้าขององค์กร',lead:'หัวหน้าตรวจงาน',editor:'คนตัด'};
let identity, organizations = [], selectedOrg = '', assets = [], members = [];
const reviewPage = document.body.dataset.teamPage === 'review';
function say(text, error=false) { $('message').textContent=text; $('message').classList.toggle('error',error); }
async function team(path, body) {
  const response = await fetch('/api/team/'+path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'คำขอใช้ไม่ได้');
  return result;
}
function form(id, action) {
  if (!$(id)) return;
  $(id).onsubmit = async event => {
    event.preventDefault(); const button=$(id).querySelector('button'); button.disabled=true;
    try { await action(Object.fromEntries(new FormData($(id)))); }
    catch(e) { say(e.message,true); }
    finally { button.disabled=false; }
  };
}
async function loadIdentity() {
  identity=await team('session');
  $('auth').hidden=identity.signed_in;
  $('signedIn').hidden=!identity.signed_in;
  if (!identity.configured) {
    document.querySelectorAll('#auth input,#auth button').forEach(el=>{el.disabled=true;});
    say('ระบบบัญชีทีมยังไม่เปิดใช้งาน ต้องตั้งค่าบริการบัญชีส่วนกลางก่อน',true); return;
  }
  if (!identity.signed_in) return;
  $('userName').textContent=identity.user.display_name || identity.user.email;
  await loadOrganizations();
}
async function loadOrganizations() {
  organizations=await team('organizations');
  $('organization').replaceChildren(new Option('เลือกองค์กร',''));
  organizations.forEach(org=>$('organization').add(new Option(org.name,org.id)));
  const remembered=localStorage.getItem('ck-organization');
  selectedOrg=organizations.some(org=>org.id===remembered) ? remembered : organizations.length===1 ? organizations[0].id : '';
  $('organization').value=selectedOrg; await loadOrganization();
}
function person(id) { const member=members.find(m=>m.user_id===id); return member?.display_name || member?.email || id; }
async function loadOrganization() {
  selectedOrg=$('organization').value;
  $('organizationContent').hidden=true; $('role').textContent='';
  if (!selectedOrg) return;
  localStorage.setItem('ck-organization',selectedOrg);
  const org=organizations.find(o=>o.id===selectedOrg);
  const role=org.clipkit_members.find(m=>m.user_id===identity.user.id)?.role;
  $('role').textContent=ROLES[role] || '';
  if (reviewPage && !['owner','lead'].includes(role)) { say('การตัดสินใจตรวจงานเป็นสิทธิ์ของหัวหน้า คนตัดส่งงานได้จากหน้าทีม',true); return; }
  const [all,directory,activity]=await Promise.all([team('organizations/'+selectedOrg+'/assets'),team('organizations/'+selectedOrg+'/members'),team('organizations/'+selectedOrg+'/activity')]);
  assets=all;members=directory; $('organizationContent').hidden=false;
  if (reviewPage) $('leadControls').hidden=false;
  else {
    $('ownerControls').hidden=role!=='owner';
    $('members').replaceChildren(...members.map(member=>{const row=document.createElement('div');row.textContent=person(member.user_id)+' · '+ROLES[member.role];return row;}));
    $('driveFolder').elements.folder.value=org.drive_folder_id || '';
    renderAssets('footage',all.filter(a=>a.kind==='footage'));
  }
  renderAssets('projects',all.filter(a=>a.kind==='project'));
  $('activity').replaceChildren(...activity.map(entry=>{
    const row=document.createElement('div');row.className='activity';
    const detail=entry.action==='delivery_changed' ? (LABELS[entry.detail.from]+' → '+LABELS[entry.detail.to]+(entry.detail.note ? ' · '+entry.detail.note : '')) : {organization_created:'สร้างองค์กร',member_added:'เพิ่ม / เปลี่ยนสิทธิ์สมาชิก',asset_registered:'เพิ่มฟุต / โปรเจกต์',drive_folder_changed:'ตั้งค่าโฟลเดอร์ Drive'}[entry.action] || entry.action;
    row.textContent=person(entry.actor_id)+' · '+detail+' · '+new Date(entry.created_at).toLocaleString('th-TH');return row;
  }));
}
function renderAssets(id, list) {
  const box=$(id);box.replaceChildren();
  if (!list.length) {box.textContent='ยังไม่มีรายการในองค์กรนี้';return;}
  list.forEach(asset=>{
    const card=document.createElement('div');card.className='asset';
    const label=document.createElement('label');
    if (reviewPage) {const check=document.createElement('input');check.type='checkbox';check.value=asset.id;check.setAttribute('aria-label','เลือก '+asset.name);label.append(check);}
    const name=document.createElement('span');name.className='name';name.textContent=asset.name;name.title=asset.name;label.append(name);card.append(label);
    if (asset.kind==='project') {
      const status=document.createElement('div');status.className='status';status.textContent=LABELS[asset.status];card.append(status);
      if (!reviewPage && ['editing','changes_requested'].includes(asset.status)) {
        const submit=document.createElement('button');submit.textContent='📤 ส่งหัวหน้าตรวจ';
        submit.onclick=async()=>{submit.disabled=true;try{await decide([asset],'awaiting_lead','');await loadOrganization();say('ส่งหัวหน้าตรวจแล้ว');}catch(e){say(e.message,true);}finally{submit.disabled=false;}};
        card.append(submit);
      }
    }
    const changed=document.createElement('div');changed.className='muted';changed.textContent='แก้ไขล่าสุด: '+person(asset.updated_by)+' · รุ่น '+asset.revision;card.append(changed);box.append(card);
  });
}
async function decide(list, status, note) {
  if (!list.length) throw new Error('เลือกโปรเจกต์ก่อน');
  return team('organizations/'+selectedOrg+'/review',{asset_ids:list.map(a=>a.id),status,note,expected_revisions:Object.fromEntries(list.map(a=>[a.id,a.revision]))});
}
form('login',async body=>{await team('login',body);$('login').reset();say('เข้าสู่ระบบแล้ว');await loadIdentity();});
form('signup',async body=>{const result=await team('signup',body);$('signup').reset();say(result.verification_required ? 'เปิดอีเมลเพื่อยืนยันบัญชี แล้วเข้าสู่ระบบ' : 'สมัครบัญชีแล้ว');await loadIdentity();});
form('createOrg',async body=>{const org=await team('organizations',body);localStorage.setItem('ck-organization',org.id);$('createOrg').reset();await loadOrganizations();say('สร้างองค์กรแล้ว');});
form('addMember',async body=>{await team('organizations/'+selectedOrg+'/members',body);await loadOrganizations();say('บันทึกสมาชิกแล้ว');});
form('driveFolder',async body=>{const match=body.folder.match(/\/folders\/([A-Za-z0-9_-]+)/);await team('organizations/'+selectedOrg+'/drive-folder',{folder_id:match ? match[1] : body.folder.trim()});await loadOrganizations();say('บันทึกโฟลเดอร์แล้ว การรับส่งไฟล์ต้องเชื่อมบัญชี Drive');});
form('review',async body=>{const ids=[...document.querySelectorAll('#projects input:checked')].map(e=>e.value);const result=await decide(assets.filter(a=>ids.includes(a.id)),body.status,body.note);await loadOrganization();say('บันทึกผลตรวจแล้ว '+result.updated+' โปรเจกต์');});
$('organization').onchange=()=>loadOrganization().catch(e=>say(e.message,true));
$('logout').onclick=async()=>{try{await team('logout',{});selectedOrg='';await loadIdentity();say('ออกจากระบบแล้ว');}catch(e){say(e.message,true);}};
loadIdentity().catch(e=>say(e.message,true));
