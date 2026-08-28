const test=require('node:test');
const assert=require('node:assert/strict');
const child=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

let parseHTML=null;
for(const candidate of ['linkedom','/opt/openclaw-runtime/releases/2026.7.1-2/lib/node_modules/openclaw/node_modules/linkedom']){try{({parseHTML}=require(candidate));break}catch(_){}}

const root=path.resolve(__dirname,'..');
const generated=child.spawnSync('python3',['-c',"from pathlib import Path; import mf885_community_r22 as p; import mf885_community_r23 as r; print(r._derive_diagnostics(p._derive_diagnostics(Path('.'))).decode())"],{cwd:root,encoding:'utf8',env:{...process.env,PYTHONPATH:path.join(root,'tools')}});
if(generated.status!==0)throw new Error(generated.stderr);
const source=generated.stdout;
const html=fs.readFileSync(path.join(root,'firmware/community-r2.3/Diagnostics.html'),'utf8');
const bootstrap=fs.readFileSync(path.join(root,'firmware/community-r2.3/community_bootstrap.js'),'utf8');

const statusXml='<RGW><sysinfo><model_name>LV01</model_name><hardware_version>MF96 Ver.D</hardware_version><version_num>2.5.94_release_MF855_NZ_CP_2.129.003</version_num><serial_number>PRIVATE-SERIAL</serial_number></sysinfo><batteryinfo><Battery_percent>74</Battery_percent><Battery_status>1</Battery_status><Charger_status>0</Charger_status><Charger_current>250</Charger_current><Output_current>90</Output_current></batteryinfo><statistics><WanStatistics><tx_byte_all>1234</tx_byte_all><rx_byte_all>5678</rx_byte_all><conn_days>1</conn_days><conn_hours>2</conn_hours><conn_minutes>3</conn_minutes><conn_seconds>4</conn_seconds></WanStatistics></statistics><message><content>PRIVATE-SMS</content></message></RGW>';
const wanXml='<RGW><wan><SIM_status>0</SIM_status><NW_register_status>1</NW_register_status><roaming>0</roaming><ConnType>3</ConnType><network_name>Example Carrier</network_name><connect_disconnect>1</connect_disconnect><pdp_type>2</pdp_type><cellular><active_apn>PRIVATE-APN</active_apn><ip_address>10.0.0.9</ip_address><v4dns1>1.1.1.1</v4dns1><v4gateway>10.0.0.1</v4gateway><password>PRIVATE-PASSWORD</password><imsi>PRIVATE-IMSI</imsi><iccid>PRIVATE-ICCID</iccid><msisdn>+79990000000</msisdn></cellular></wan><HA1>PRIVATE-HA1</HA1></RGW>';
const engineerXml='<RGW><Engineer_parameter><LTE_band>3</LTE_band><EARFCN>1300</EARFCN><PCI>77</PCI><Cell_ID>PRIVATE-CELL</Cell_ID><TAC>PRIVATE-TAC</TAC><RSRP>-94</RSRP><RSRQ>-10</RSRQ><SINR>14</SINR><RSSI>-66</RSSI></Engineer_parameter></RGW>';

function fixture(options={}){
  const {window}=parseHTML('<html><body><div id="Content"></div></body></html>');
  const document=window.document,calls=[];
  let responses={status1:statusXml,wan:wanXml,Engineer_parameter:engineerXml};
  function jquery(){return {}}jquery.fn={};jquery.i18n={map:{}};
  jquery.ajax=config=>{
    const name=(config.url.match(/file=([^&]+)/)||[])[1],headers={};
    calls.push({name,config,headers});
    config.beforeSend({setRequestHeader:(key,value)=>{headers[key]=value}});
    const reply=responses[name];
    if(reply&&reply.error)config.error({status:reply.status||0},reply.state||'error');
    else config.success(new window.DOMParser().parseFromString(reply,'text/xml'));
  };
  Object.assign(window,{jQuery:jquery,$:jquery,location:{protocol:'http:',host:'192.168.21.1'},callProductHTML:()=>html,getAuthHeader:method=>'Digest '+method,console});
  window.document.execCommand=()=>false;
  const context={window,document,console,Date,JSON,Array,Object,String,Number,Boolean,RegExp,Error,Promise,Map,Set};
  vm.createContext(context);vm.runInContext(bootstrap,context,{filename:'r23boot.js'});vm.runInContext(source,context,{filename:'r23diag.js'});
  const controller=jquery.fn.objDiagnostics.call({});controller.setXMLName('status1');if(options.auto!==false)controller.onLoad();
  return {window,document,calls,controller,setResponses(value){responses=value}};
}

test('R2.3 Diagnostics follows the production lifecycle and reads exactly three fixed endpoints once',{skip:!parseHTML},()=>{
  const value=fixture();
  assert.deepEqual(value.calls.map(call=>call.name),['status1','wan','Engineer_parameter']);
  for(const call of value.calls){
    assert.equal(call.config.type,'GET');assert.equal(call.config.timeout,10000);assert.equal(call.config.cache,false);
    assert.equal(call.headers.Authorization,'Digest GET');
  }
  assert.equal(typeof value.controller.setXMLName,'function');
  assert.equal(value.document.getElementById('mfDiagCopy').disabled,false);
  assert.match(value.document.getElementById('mfDiagStatus').textContent,/three fixed endpoints/i);
  assert.match(value.document.documentElement.className,/mfCommunityR23Root/);
});

test('R2.3 Diagnostics renders scoped values as text and keeps unrelated secret leaves out',{skip:!parseHTML},()=>{
  const value=fixture(),visible=value.document.getElementById('mfDiagValues').textContent;
  for(const expected of ['0.2.3-community-r2','LV01','MF96 Ver.D','Example Carrier','4G · LTE','10.0.0.9','1d 02h 03m 04s','1234','5678','250','90','-94','PRIVATE-CELL','PRIVATE-TAC'])assert.match(visible,new RegExp(expected.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')));
  for(const forbidden of ['PRIVATE-PASSWORD','PRIVATE-HA1','PRIVATE-IMSI','PRIVATE-ICCID','+79990000000','PRIVATE-SERIAL','PRIVATE-SMS'])assert.doesNotMatch(visible,new RegExp(forbidden.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')));
  assert.equal(value.document.getElementById('mfDiagValues').querySelectorAll('script').length,0);
});

test('R2.3 safe snapshot is allowlisted and marks stale values',{skip:!parseHTML},()=>{
  const value=fixture();
  value.document.getElementById('mfDiagCopy').click();
  let report=value.document.getElementById('mfDiagReport').value,parsed=JSON.parse(report);
  assert.equal(parsed.schema,'mf885-community-safe-diagnostics/v1');
  assert.deepEqual(parsed.community,{value:'0.2.3-community-r2',stale:false});
  for(const forbidden of ['PRIVATE-APN','10.0.0.9','1.1.1.1','10.0.0.1','PRIVATE-CELL','PRIVATE-TAC','1300','77','PRIVATE-PASSWORD','PRIVATE-HA1','PRIVATE-IMSI','PRIVATE-ICCID','+79990000000','PRIVATE-SERIAL','PRIVATE-SMS'])assert.doesNotMatch(report,new RegExp(forbidden.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')));
  value.setResponses({status1:statusXml,wan:{error:true,state:'timeout'},Engineer_parameter:engineerXml});
  value.document.getElementById('mfDiagRefresh').click();
  assert.deepEqual(value.calls.slice(-3).map(call=>call.name),['status1','wan','Engineer_parameter']);
  assert.match(value.document.getElementById('mfDiagStatus').textContent,/Partial diagnostics: 1 endpoint failed/);
  value.document.getElementById('mfDiagCopy').click();report=value.document.getElementById('mfDiagReport').value;parsed=JSON.parse(report);
  assert.deepEqual(parsed.cellular.operator,{value:'Example Carrier',stale:true});
  assert.deepEqual(parsed.cellular.rsrp,{value:'-94',stale:false});
});

test('R2.3 identity mismatch warns but never suppresses the fixed read sequence',{skip:!parseHTML},()=>{
  const value=fixture({auto:false});
  value.setResponses({status1:statusXml.replace('MF96 Ver.D','MF96 Ver.C'),wan:wanXml,Engineer_parameter:engineerXml});
  value.controller.onLoad();
  assert.deepEqual(value.calls.map(call=>call.name),['status1','wan','Engineer_parameter']);
  assert.match(value.document.getElementById('mfDiagStatus').textContent,/identity was not proven/i);
});

test('R2.3 Diagnostics has no retry, polling, raw-log, or browser-storage path',()=>{
  const combined=source+'\n'+html;
  assert.doesNotMatch(combined,/setInterval|detailed_log|canary_logs|localStorage|sessionStorage|XMLHttpRequest\.prototype|fetch\s*=|event log/i);
  assert.equal((source.match(/ajax\(/g)||[]).length,1);
  assert.match(source,/\['status1','wan','Engineer_parameter'\]/);
});
