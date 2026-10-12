const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('app/static/team.js','utf8');
const code=source.slice(source.indexOf('async function loadOrganizations()'),source.indexOf('async function loadOrganization()'));
async function check(count){
 const nodes=Object.fromEntries(['organization','teamOnboarding','teamIdentity','teamPicker','joinEmail','invitationChoices'].map(id=>[id,{hidden:false,children:[],replaceChildren(...items){this.children=items;},append(item){this.children.push(item);}}]));
 const orgs=Array.from({length:count},(_,i)=>({id:'team'+i,name:'Team '+i}));
 const context={organizations:[],identity:{user:{email:'editor@example.test'}},$:id=>nodes[id],localStorage:{getItem:()=>null},Option:function(name,value){this.name=name;this.value=value;},team:async path=>path==='organizations'?orgs:[],loadOrganization:async()=>{},document:{createElement:()=>({})},button:()=>{},ROLES:{}};
 await vm.runInNewContext(code+';loadOrganizations()',context);
 assert.equal(nodes.teamOnboarding.hidden,count>0);
 assert.equal(nodes.teamIdentity.hidden,!count);
 assert.equal(nodes.teamPicker.hidden,count<2);
 assert.equal(nodes.joinEmail.textContent,'editor@example.test');
 assert.equal(nodes.organization.value,count?'team0':'');
}
(async()=>{for(const count of [0,1,2])await check(count);console.log('PASS team entry: create/join, single team, multiple team selection');})().catch(e=>{console.error(e);process.exitCode=1;});
const roleCode=source.slice(source.indexOf('async function loadOrganization()'),source.indexOf('\n [projects,footage,members]'))+'}';
async function checkRole(role){
 const nodes=Object.fromEntries(['organizationContent','reviewShortcut','role','teamName','organization'].map(id=>[id,{hidden:false,value:'one'}]));
 const reviewLink={hidden:false};
 const context={selectedOrg:'',role:'',identity:{user:{id:'u'}},organizations:[{id:'one',name:'My team',clipkit_members:[{user_id:'u',role}]}],$:id=>nodes[id],document:{querySelector:()=>reviewLink},localStorage:{setItem:()=>{}},ROLES:{admin:'Admin',lead:'Lead',editor:'Editor'},reviewPage:false,say:()=>{}};
 await vm.runInNewContext(roleCode+';loadOrganization()',context);
 assert.equal(nodes.reviewShortcut.hidden,role==='editor');assert.equal(reviewLink.hidden,role==='editor');
 assert.equal(nodes.teamName.textContent,'My team');
}
(async()=>{for(const role of ['admin','lead','editor'])await checkRole(role);console.log('PASS review actions follow team role');})().catch(e=>{console.error(e);process.exitCode=1;});
