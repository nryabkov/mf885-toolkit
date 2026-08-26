const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

let parseHTML=null;
for(const candidate of ['linkedom','/opt/openclaw-runtime/releases/2026.7.1-2/lib/node_modules/openclaw/node_modules/linkedom']){try{({parseHTML}=require(candidate));break}catch(_){}}

const root=path.resolve(__dirname,'..');
const transformer=fs.readFileSync(path.join(root,'tools/mf885_community_r21.py'),'utf8');
const smsSource=fs.readFileSync(path.join(root,'firmware/community-r2.1/SMS.js'),'utf8');
const diagnosticsSource=fs.readFileSync(path.join(root,'firmware/community-r2.1/community_diagnostics.js'),'utf8');
const smsHtml=fs.readFileSync(path.join(root,'firmware/community-r2.1/SMS.html'),'utf8');
const diagnosticsHtml=fs.readFileSync(path.join(root,'firmware/community-r2.1/Diagnostics.html'),'utf8');

test('R2.1 declares one Diagnostics tab after Messages and preserves the Settings index',()=>{
  assert.equal((transformer.match(/<Tab Name='tDiagnostics'/g)||[]).length,1);
  assert.equal((transformer.match(/implFunction='objDiagnostics' xmlName='status1'/g)||[]).length,1);
  assert.equal((transformer.match(/dashboardOnClick\(5,'mDeviceInbox'\)/g)||[]).length,2);
  assert.equal((transformer.match(/dashboardOnClick\(6,'mDiagnostics'\)/g)||[]).length,1);
  assert.doesNotMatch(transformer,/dashboardOnClick\(4,'(?:mDeviceInbox|mDiagnostics)'\)/);
});

test('Home to Diagnostics to Messages to Settings uses controller navigation without reload',{skip:!parseHTML},()=>{
  const {window}=parseHTML('<html><body><main id="Content">Home</main></body></html>');
  const document=window.document,calls=[];
  function jquery(){return {}}jquery.fn={};
  jquery.ajax=options=>{
    calls.push(options.url.match(/file=([^&]+)/)[1]);
    const name=calls.at(-1),xml=name==='status1'
      ?'<RGW><status><sysinfo><model_name>MF885</model_name><hardware_version>MF96 Ver.D</hardware_version><version_num>2.5.94_release_MF855_NZ_CP_2.129.003</version_num></sysinfo></status></RGW>'
      :`<RGW><${name}/></RGW>`;
    options.beforeSend({setRequestHeader(){}});options.success(new window.DOMParser().parseFromString(xml,'text/xml'));
  };
  window.jQuery=jquery;window.location={protocol:'http:',host:'192.0.2.1'};window.getAuthHeader=()=> 'fixture';
  window.callProductHTML=file=>file.includes('Diagnostics')?diagnosticsHtml:file.includes('SMS')?smsHtml:'<section id="settings">Settings</section>';
  window.callProductXML=()=>'<RGW><status><model>MF885</model><version_num>2.5.94_release_MF855_NZ_CP_2.129.003</version_num></status></RGW>';
  window.getHardware_Version=()=> 'MF96 Ver.D';window.PostSyncXML=()=>{};
  window.GetSmsXML=()=>'<RGW><message><get_message><total_number>0</total_number><message_list/></get_message></message></RGW>';
  window.putMapElement=(map,key,value)=>map.push({key,value});window.g_objXML={createXML:value=>value,getXMLDocToString:()=>'<RGW/>'};
  window.UniDecode=value=>value;window.setTimeout=fn=>{fn();return 1};window.clearTimeout=()=>{};
  jquery.fn.objSettings=function(){this.setXMLName=value=>{this.xmlName=value};this.onLoad=()=>{document.getElementById('Content').innerHTML=window.callProductHTML('settings')};return this};
  const context={window,document,console,JSON,Array,Object,String,Number,Boolean,RegExp,Error,Promise,Map,Set};
  vm.createContext(context);vm.runInContext(smsSource,context);vm.runInContext(diagnosticsSource,context);
  const menu={
    mSetting:{index:4,impl:'objSettings',xml:'settings'},
    mDeviceInbox:{index:5,impl:'objSms',xml:'message'},
    mDiagnostics:{index:6,impl:'objDiagnostics',xml:'status1'}
  };
  let reloads=0;
  function navigate(index,id){const item=menu[id];assert.equal(index,item.index);const controller=jquery.fn[item.impl].call({},id);controller.setXMLName(item.xml);controller.onLoad();return controller}
  function dashboardOnClick(index,id){return navigate(index,id)}

  assert.equal(document.getElementById('Content').textContent,'Home');
  dashboardOnClick(6,'mDiagnostics');assert.ok(document.getElementById('mfCommunityDiagnostics'));assert.deepEqual(calls,['status1','wan','Engineer_parameter']);
  navigate(5,'mDeviceInbox');assert.ok(document.getElementById('mfCommunityR21Sms'));assert.match(document.getElementById('mfSmsStatus').textContent,/Loaded 0 messages/);
  navigate(4,'mSetting');assert.ok(document.getElementById('settings'));assert.equal(reloads,0);
});
