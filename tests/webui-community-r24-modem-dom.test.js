const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

let parseHTML=null;
for(const candidate of ['linkedom','/opt/openclaw-runtime/releases/2026.7.1-2/lib/node_modules/openclaw/node_modules/linkedom']){try{({parseHTML}=require(candidate));break}catch(_){}}

const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'firmware/community-r2.4/modem_monitor.js'),'utf8');
const html=fs.readFileSync(path.join(root,'firmware/community-r2.4/Modem.html'),'utf8');
const transformer=fs.readFileSync(path.join(root,'tools/mf885_community_r24.py'),'utf8');
const exactStatus='<RGW><sysinfo><model_name>LV01</model_name><hardware_version>MF96 Ver.D</hardware_version><version_num>2.5.94_release_MF855_NZ_CP_2.129.003</version_num><serial_number>PRIVATE-SERIAL</serial_number></sysinfo><batteryinfo><Battery_percent>82</Battery_percent><Battery_status>1</Battery_status></batteryinfo><wan><proto>cellular</proto><wan_link_status>1</wan_link_status><wan_conn_status>1</wan_conn_status><network_name>Example Carrier</network_name><connect_disconnect>cellular</connect_disconnect><sys_mode>17</sys_mode><cellular><sim_status>0</sim_status><roaming>0</roaming></cellular><wifi><ssid>PRIVATE-SSID</ssid><enc>WPA2</enc><cipher>AES</cipher><signal>73</signal></wifi><IMEI>PRIVATE-IMEI</IMEI></wan><wlan_settings><wlan_enable>1</wlan_enable><current_channel>11</current_channel><ssid>PRIVATE-LOCAL-SSID</ssid></wlan_settings><statistics><WanStatistics><conn_days>0</conn_days><conn_hours>1</conn_hours><conn_minutes>2</conn_minutes><conn_seconds>3</conn_seconds></WanStatistics></statistics><message><content>PRIVATE-SMS</content></message></RGW>';
const wan='<RGW><wan><proto>cellular</proto><NW_register_status>1</NW_register_status><network_name>Example Carrier</network_name><connect_disconnect>cellular</connect_disconnect><pdp_type>IP</pdp_type><cellular><sim_status>0</sim_status><roaming>0</roaming><password>PRIVATE-PASSWORD</password><imsi>PRIVATE-IMSI</imsi></cellular></wan><HA1>PRIVATE-HA1</HA1></RGW>';
const nestedEngineer='<RGW><Engi><LTE><mcc>250</mcc><mnc>02</mnc><tac>PRIVATE-TAC</tac><phyCellId>77</phyCellId><dlEuArfcn>1300</dlEuArfcn><ulEuArfcn>19300</ulEuArfcn><band>3</band><dlBandwidth>20</dlBandwidth><cellId>PRIVATE-CELL</cellId><rsrp>-94</rsrp><rsrq>-10</rsrq><sinr>14</sinr><mainRsrp>-95</mainRsrp><diversityRsrp>-97</diversityRsrp><mainRsrq>-11</mainRsrq><diversityRsrq>-12</diversityRsrq><rssi>-66</rssi><cqi>9</cqi><ECGI>PRIVATE-ECGI</ECGI></LTE><GSM><timingAdv>PRIVATE-TA</timingAdv></GSM></Engi></RGW>';
const flatEngineer='<RGW><Engineer_parameter><LTE_band>7</LTE_band><EARFCN>2850</EARFCN><PCI>12</PCI><RSRP>-101</RSRP><RSRQ>-13</RSRQ><SINR>5</SINR><RSSI>-75</RSSI></Engineer_parameter></RGW>';

function fixture(options={}){
  const {window}=parseHTML('<html><body><div id="Content"></div></body></html>');
  const document=window.document,calls=[],timers=[],storage={},pending=[];
  let responses={status1:exactStatus,wan,Engineer_parameter:options.flat?flatEngineer:nestedEngineer};
  function jquery(){return {}}jquery.fn={};
  jquery.ajax=config=>{
    const name=(config.url.match(/file=([^&]+)/)||[])[1],headers={};calls.push({name,config,headers});
    config.beforeSend({setRequestHeader:(key,value)=>{headers[key]=value}});
    const request={aborted:false,abort(){this.aborted=true}};
    const invoke=()=>{if(request.aborted)return;const reply=responses[name];if(reply&&reply.error)config.error({status:reply.status||0},reply.state||'error');else config.success(new window.DOMParser().parseFromString(reply,'text/xml'))};
    if(options.asyncAjax)pending.push({request,invoke});else invoke();return request;
  };
  Object.assign(window,{jQuery:jquery,$:jquery,location:{protocol:'http:',host:'192.168.21.1'},callProductHTML:()=>html,getAuthHeader:method=>'Digest '+method,console,
    MF885CommunityR24:{markRoot(){document.documentElement.className+=' mfCommunityR24Root'},exactStatus1Identity(){return options.identity!==false}},
    sessionStorage:{getItem:key=>storage[key]||null,setItem:(key,value)=>{storage[key]=String(value)},removeItem:key=>{delete storage[key]}},
    setTimeout:(fn,ms)=>{timers.push({fn,ms,cancelled:false});return timers.length},clearTimeout:id=>{if(timers[id-1])timers[id-1].cancelled=true}
  });
  const context={window,document,console,Date,JSON,Array,Object,String,Number,Boolean,RegExp,Error,Promise,Map,Set};
  vm.createContext(context);vm.runInContext(source,context,{filename:'r24modem.js'});
  function createController(){const result=jquery.fn.objModemMonitor.call({});result.setXMLName('status1');return result}
  const controller=createController();if(options.auto!==false)controller.onLoad();
  return {window,document,calls,timers,storage,pending,controller,createController,flushNext(){const item=pending.shift();if(item)item.invoke();return item},setResponses(value){responses=value}};
}

test('R2.4 Modem monitor reads exactly the three fixed GET endpoints and renders nested golden radio fields',{skip:!parseHTML},()=>{
  const value=fixture();
  assert.deepEqual(value.calls.map(call=>call.name),['status1','wan','Engineer_parameter']);
  for(const call of value.calls){assert.equal(call.config.type,'GET');assert.equal(call.config.cache,false);assert.equal(call.config.timeout,10000);assert.equal(call.headers.Authorization,'Digest GET')}
  const visible=value.document.getElementById('mfCommunityR24Modem').textContent;
  for(const expected of ['Example Carrier','Registered · home','4G · LTE','Band','-94','DL EARFCN','1300','UL EARFCN','19300','DL bandwidth','20','CQI','9','Main RSRP','-95','Cellular is the selected uplink','local AP On','channel 11'])assert.match(visible,new RegExp(expected.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')));
  assert.equal(value.document.getElementById('mfSignalLine').getAttribute('points').length>0,true);
  assert.match(value.document.documentElement.className,/mfCommunityR24Root/);
});

test('R2.4 Modem monitor accepts the observed flat Engineer_parameter representation',{skip:!parseHTML},()=>{
  const value=fixture({flat:true}),visible=value.document.getElementById('mfModemSummary').textContent;
  for(const expected of ['7','-101','-13','5','DL EARFCN','2850','PCI','12'])assert.match(visible,new RegExp(expected));
});

test('R2.4 safe trace omits Wi-Fi, cell, device, credential and SMS secrets',{skip:!parseHTML},()=>{
  const value=fixture();value.document.getElementById('mfModemCopy').click();
  const report=value.document.getElementById('mfModemReport').value,parsed=JSON.parse(report);
  assert.equal(parsed.schema,'mf885-community-safe-modem-trace/v1');assert.equal(parsed.samples.length,1);assert.equal(parsed.samples[0].rsrp,'-94');assert.equal(parsed.samples[0].bandwidth,'20');
  for(const secret of ['PRIVATE-SSID','PRIVATE-LOCAL-SSID','PRIVATE-SERIAL','PRIVATE-IMEI','PRIVATE-PASSWORD','PRIVATE-IMSI','PRIVATE-HA1','PRIVATE-SMS','PRIVATE-TAC','PRIVATE-CELL','PRIVATE-ECGI','PRIVATE-TA','1300','19300','77'])assert.doesNotMatch(report,new RegExp(secret));
});

test('R2.4 safe trace rejects secrets injected into nominally safe fields',{skip:!parseHTML},()=>{
  const value=fixture({auto:false});
  const hostileWan=wan.replace('<NW_register_status>1</NW_register_status>','<NW_register_status>PRIVATE-IMSI</NW_register_status>');
  const hostileEngineer=nestedEngineer.replace('<band>3</band>','<band>PRIVATE-IMEI</band>').replace('<rsrp>-94</rsrp>','<rsrp>-94 PRIVATE-PASSWORD</rsrp>');
  value.setResponses({status1:exactStatus,wan:hostileWan,Engineer_parameter:hostileEngineer});value.controller.onLoad();value.document.getElementById('mfModemCopy').click();
  const report=value.document.getElementById('mfModemReport').value,parsed=JSON.parse(report),sample=parsed.samples[0];
  for(const secret of ['PRIVATE-IMSI','PRIVATE-IMEI','PRIVATE-PASSWORD','Unknown (raw:'])assert.doesNotMatch(report,new RegExp(secret.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')));
  assert.equal(sample.registration,'Unknown');assert.equal(sample.band,null);assert.equal(sample.rsrp,null);assert.equal(parsed.changes,undefined);
});

test('R2.4 aborts stale controller reads and ignores late callbacks',{skip:!parseHTML},()=>{
  const value=fixture({auto:false,asyncAjax:true});value.controller.onLoad();assert.equal(value.pending.length,1);const old=value.pending[0];assert.equal(value.window.MF885_COMMUNITY_R24_MODEM_SESSION.busy,true);
  const replacement=value.createController();replacement.onLoad();assert.equal(old.request.aborted,true);assert.equal(value.pending.length,2);assert.equal(value.window.MF885_COMMUNITY_R24_MODEM_SESSION.busy,true);
  value.flushNext();assert.equal(value.calls.length,2);value.flushNext();assert.equal(value.calls.length,3);value.flushNext();assert.equal(value.calls.length,4);value.flushNext();
  assert.deepEqual(value.calls.slice(1).map(call=>call.name),['status1','wan','Engineer_parameter']);assert.equal(value.window.MF885_COMMUNITY_R24_MODEM_SESSION.busy,false);assert.match(value.document.getElementById('mfModemStatus').textContent,/updated/);
});

test('R2.4 releases an in-flight monitor read when navigation opens Messages',{skip:!parseHTML},()=>{
  const value=fixture({auto:false,asyncAjax:true});value.controller.onLoad();const pending=value.pending[0],session=value.window.MF885_COMMUNITY_R24_MODEM_SESSION;
  let updates=0;value.window.MF885_COMMUNITY_R24_MUTATION_SESSION={document:value.document,busy:false,update(){updates++;assert.equal(session.releaseDetached(),false)}};
  assert.equal(session.busy,true);value.document.getElementById('Content').textContent='Messages';
  assert.equal(session.releaseDetached(),true);assert.equal(pending.request.aborted,true);assert.equal(session.request,null);assert.equal(session.busy,false);assert.equal(session.controller,null);
  assert.equal(updates,1);assert.equal(session.releaseDetached(),false);assert.equal(updates,1);
  pending.invoke();assert.equal(value.calls.length,1);assert.match(transformer,/state\.busy&&typeof state\.releaseDetached/);
});

test('R2.4 blocks manual and watched reads while an SMS mutation is active',{skip:!parseHTML},()=>{
  const value=fixture({auto:false});value.window.MF885_COMMUNITY_R24_MUTATION_SESSION={document:value.document,busy:true};value.controller.onLoad();
  assert.equal(value.calls.length,0);assert.match(value.document.getElementById('mfModemStatus').textContent,/Waiting for the current Messages operation/);
  value.window.MF885_COMMUNITY_R24_MUTATION_SESSION.busy=false;value.controller.onLoad();assert.equal(value.calls.length,3);
});

test('R2.4 watch is opt-in, recursive, bounded and waits for an SMS mutation',{skip:!parseHTML},()=>{
  const value=fixture();assert.equal(value.timers.length,0);assert.equal(value.storage['mf885.community.r24.modem-watch.v1'],undefined);
  const check=value.document.getElementById('mfModemWatch');check.checked=true;check.dispatchEvent(new value.window.Event('change'));
  assert.equal(value.storage['mf885.community.r24.modem-watch.v1'],'1');assert.deepEqual(value.calls.slice(-3).map(call=>call.name),['status1','wan','Engineer_parameter']);
  const live=value.timers.filter(timer=>!timer.cancelled);assert.equal(live.length,1);assert.equal(live[0].ms,30000);
  value.window.MF885_COMMUNITY_R24_MUTATION_SESSION={document:value.document,busy:true};live[0].cancelled=true;live[0].fn();assert.equal(value.calls.length,6);assert.match(value.document.getElementById('mfModemStatus').textContent,/Waiting for the current Messages operation/);
  assert.equal(value.timers.filter(timer=>!timer.cancelled).length,1);
});

test('R2.4 Modem monitor uses text-only sinks and contains no write, scan, retry, or raw storage path',{skip:!parseHTML},()=>{
  const attack='<img src=x onerror=alert(1)>';const escaped='&lt;img src=x onerror=alert(1)&gt;';const value=fixture({auto:false});
  value.setResponses({status1:exactStatus.replace('Example Carrier',escaped),wan:wan.replace('Example Carrier',escaped),Engineer_parameter:nestedEngineer});value.controller.onLoad();
  assert.equal(value.document.getElementById('mfCommunityR24Modem').querySelectorAll('img').length,0);
  assert.match(value.document.getElementById('mfModemSummary').textContent,/<img src=x onerror=alert\(1\)>/);
  const combined=source+'\n'+html;
  assert.doesNotMatch(combined,/PostXML|method=set|setInterval|wlan_cli_scan|wan\/wifi\/psk|SEND_USSD|\+CUSD|localStorage|raw XML\s*:/i);
  assert.equal((source.match(/ajax\(/g)||[]).length,1);assert.match(source,/ENDPOINTS=\['status1','wan','Engineer_parameter'\]/);assert.match(source,/WATCH_MS=30000/);
});
