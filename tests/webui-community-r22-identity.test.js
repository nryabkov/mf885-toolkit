const test=require('node:test');
const assert=require('node:assert/strict');
const child=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

let parseHTML=null;
for(const candidate of ['linkedom','/opt/openclaw-runtime/releases/2026.7.1-2/lib/node_modules/openclaw/node_modules/linkedom']){try{({parseHTML}=require(candidate));break}catch(_){}}
const root=path.resolve(__dirname,'..');
const generated=child.spawnSync('python3',['-c',"from pathlib import Path; import mf885_community_r22 as r; print(r._derive_sms(Path('.')).decode())"],{cwd:root,encoding:'utf8',env:{...process.env,PYTHONPATH:path.join(root,'tools')}});
if(generated.status!==0)throw new Error(generated.stderr);
const source=generated.stdout;
const bootstrap=fs.readFileSync(path.join(root,'firmware/community-r2.2/community_bootstrap.js'),'utf8');
const html=fs.readFileSync(path.join(root,'firmware/community-r2.2/SMS.html'),'utf8');

function identity(model='LV01',hardware='MF96 Ver.D',version='2.5.94_release_MF855_NZ_CP_2.129.003'){
  return `<RGW><sysinfo><model_name>${model}</model_name><hardware_version>${hardware}</hardware_version><version_num>${version}</version_num></sysinfo></RGW>`;
}
function fixture(status1=identity()){
  const {window}=parseHTML('<html><body><div id="Content"></div></body></html>');
  const document=window.document,posts=[];let identityReads=0,currentFlag='';
  function jquery(){return {}}jquery.fn={};window.jQuery=jquery;window.jQuery.i18n={map:{}};
  window.callProductHTML=()=>html;window.callProductXML=name=>{assert.equal(name,'status1');identityReads++;return status1};
  window.getHardware_Version=()=>{throw new Error('must not be used')};
  window.putMapElement=(map,key,value)=>map.push({key,value:String(value)});window.g_objXML={createXML:value=>value,getXMLDocToString:map=>'<RGW><message>'+map.map(item=>`<${item.key.split('/').at(-1)}>${item.value}</${item.key.split('/').at(-1)}>`).join('')+'</message></RGW>'};
  window.PostSyncXML=(_name,body)=>{currentFlag=(body.match(/<message_flag>([^<]+)<\/message_flag>/)||[])[1]||''};
  window.GetSmsXML=()=>'<RGW><message><get_message><total_number>0</total_number><message_list/></get_message></message></RGW>';
  window.PostXMLWithResponse=(_name,body)=>posts.push(body);window.getData=()=>'<RGW><message><sms_cmd>4</sms_cmd><sms_cmd_status_result>1</sms_cmd_status_result></message></RGW>';
  window.UniDecode=value=>value;window.UniEncode=value=>String(value).split('').map(ch=>ch.charCodeAt(0).toString(16).padStart(4,'0')).join('').toUpperCase();window.GetSmsTime=()=>'';
  window.setTimeout=fn=>{fn();return 1};window.clearTimeout=()=>{};window.confirm=()=>false;
  const context={window,document,console,Date,JSON,Array,Object,String,Number,Boolean,RegExp,Error,Promise,Map,Set};vm.createContext(context);vm.runInContext(bootstrap,context);vm.runInContext(source,context);
  const controller=jquery.fn.objSms.call({},'mDeviceInbox');controller.setXMLName('message');controller.onLoad();
  return {window,document,posts,get identityReads(){return identityReads},currentFlag};
}

test('R2.2 exact live identity enables review controls after one status1 read and no mutation POST',{skip:!parseHTML},()=>{
  const value=fixture();assert.equal(value.identityReads,1);assert.equal(value.document.getElementById('mfSmsNew').disabled,false);assert.equal(value.posts.length,0);
  value.document.getElementById('mfSmsNew').click();value.document.getElementById('mfSmsNumber').value='+15551234567';value.document.getElementById('mfSmsBody').value='review only';value.document.getElementById('mfSmsReview').click();
  assert.equal(value.posts.length,0);assert.equal(value.document.getElementById('mfSmsConfirm').hidden,false);
  value.document.getElementById('mfSmsBack').click();assert.equal(value.posts.length,0);
});

test('R2.2 rejects missing, wrong, duplicate, conflicting and nested identity with zero mutation POST',{skip:!parseHTML},()=>{
  const exact=identity();const invalid=[identity('LV02'),identity('LV01','MF96 Ver.C'),identity('LV01','MF96 Ver.D','2.5.94'),exact.replace('</RGW>','<login_status>UNAUTHORIZED</login_status></RGW>'),exact.replace('</sysinfo>','<decoy><login_status>KICKOFF</login_status></decoy></sysinfo>'),exact.replace('</sysinfo>','<model_name>LV01</model_name></sysinfo>'),exact.replace('</RGW>','<sysinfo><model_name>MF885</model_name><hardware_version>MF96 Ver.D</hardware_version><version_num>2.5.94_release_MF855_NZ_CP_2.129.003</version_num></sysinfo></RGW>'),'<RGW><decoy>'+exact+'</decoy></RGW>'];
  for(const xml of invalid){const value=fixture(xml);assert.equal(value.identityReads,1);assert.equal(value.document.getElementById('mfSmsNew').disabled,true);assert.equal(value.posts.length,0)}
});

test('R2.2 transformed SMS keeps one mutation callsite and the inherited no-retry contract',()=>{
  assert.equal((source.match(/PostXMLWithResponse/g)||[]).length,1);
  assert.match(source,/MF885_COMMUNITY_R22_MUTATION_SESSION/);
  assert.match(source,/html\/Community\/r22sms\.html/);
  assert.doesNotMatch(source,/getHardware_Version|html\/SMS\/SMS\.html|MF885_COMMUNITY_R21/);
  assert.match(source,/automatic retry|No retry was sent|submitted once/i);
});
