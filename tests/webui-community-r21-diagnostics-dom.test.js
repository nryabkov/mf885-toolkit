const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');

let parseHTML=null;
for(const candidate of ['linkedom','/opt/openclaw-runtime/releases/2026.7.1-2/lib/node_modules/openclaw/node_modules/linkedom']){try{({parseHTML}=require(candidate));break}catch(_){}}

const source=fs.readFileSync(path.join(__dirname,'../firmware/community-r2.1/community_diagnostics.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../firmware/community-r2.1/Diagnostics.html'),'utf8');
const statusXml='<RGW><sysinfo><model_name>MF885</model_name><hardware_version>MF96 Ver.D</hardware_version><version_num>2.5.94_release_MF855_NZ_CP_2.129.003</version_num><current_device_mac>secret-mac</current_device_mac></sysinfo><batteryinfo><Battery_percent>74</Battery_percent><Battery_status>1</Battery_status><Charger_status>0</Charger_status><Charger_current>250</Charger_current><Output_current>90</Output_current></batteryinfo><wan><ip/><cellular><pdp_context_list><Item><ipv4>NA</ipv4><v4dns1>NONE</v4dns1><v4gateway>NULL</v4gateway></Item></pdp_context_list></cellular><IMEI>secret-imei</IMEI><ICCID>secret-iccid</ICCID><MSISDN>secret-msisdn</MSISDN></wan><statistics><WanStatistics><tx_byte_all>1234</tx_byte_all><rx_byte_all>5678</rx_byte_all><tx_byte>12</tx_byte><rx_byte>34</rx_byte><conn_days>1</conn_days><conn_hours>2</conn_hours><conn_minutes>3</conn_minutes><conn_seconds>4</conn_seconds></WanStatistics></statistics><lan><ip>192.168.21.1</ip><mac>secret-lan-mac</mac></lan><message><content>secret-sms</content></message></RGW>';
const wanXml='<RGW><wan><SIM_status>0</SIM_status><NW_register_status>5</NW_register_status><roaming>1</roaming><ConnType>3</ConnType><network_name>Carrier &amp; Co</network_name><connect_disconnect>1</connect_disconnect><pdp_type>2</pdp_type><cellular><active_apn>private.apn</active_apn><ip_address>10.0.0.9</ip_address><v4dns1>1.1.1.1</v4dns1><v4gateway>10.0.0.1</v4gateway><password>secret-password</password><imsi>secret-imsi</imsi></cellular></wan><HA1>secret-ha1</HA1></RGW>';
const engineerXml='<RGW><Engineer_parameter><LTE_band>3</LTE_band><EARFCN>1300</EARFCN><PCI>77</PCI><Cell_ID>secret-cell</Cell_ID><TAC>secret-tac</TAC><RSRP>-94</RSRP><RSRQ>-10</RSRQ><SINR>14</SINR><RSSI>-66</RSSI></Engineer_parameter></RGW>';

function fixture(options={}){
  const {window}=parseHTML('<html><body><div id="Content"></div></body></html>');
  const document=window.document,calls=[];let responses={status1:statusXml,wan:wanXml,Engineer_parameter:engineerXml};
  function jquery(){return {}}jquery.fn={};
  jquery.ajax=config=>{
    const name=(config.url.match(/file=([^&]+)/)||[])[1],headers={};calls.push({name,config,headers});config.beforeSend({setRequestHeader:(key,value)=>{headers[key]=value}});
    const reply=responses[name];if(reply&&reply.error){config.error({status:reply.status||0},reply.state||'error')}else config.success(new window.DOMParser().parseFromString(reply,'text/xml'));
  };
  window.jQuery=jquery;window.location={protocol:'http:',host:'192.168.21.1'};window.callProductHTML=()=>html;window.getAuthHeader=method=>'Digest '+method;
  window.document.execCommand=()=>false;
  const context={window,document,console,Date,JSON,Array,Object,String,Number,Boolean,RegExp,Error,Promise,Map,Set};vm.createContext(context);vm.runInContext(source,context);
  const controller=jquery.fn.objDiagnostics.call({});controller.setXMLName('status1');if(options.auto!==false)controller.onLoad();
  return {window,document,calls,controller,setResponses(next){responses=next}};
}

test('R2.1 diagnostics reads only the three fixed GET endpoints in order and renders useful safe fields',{skip:!parseHTML},()=>{
  const value=fixture();assert.deepEqual(value.calls.map(call=>call.name),['status1','wan','Engineer_parameter']);
  for(const call of value.calls){assert.equal(call.config.type,'GET');assert.equal(call.config.timeout,10000);assert.equal(call.config.cache,false);assert.equal(call.headers.Authorization,'Digest GET')}
  const visible=value.document.getElementById('mfDiagValues').textContent;
  for(const expected of ['0.2.1-community-r2','MF96 Ver.D','Carrier & Co','4G · LTE','10.0.0.9','1d 02h 03m 04s','1234','5678','250','90','-94','secret-cell','secret-tac'])assert.match(visible,new RegExp(expected.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')));
  assert.doesNotMatch(visible,/192\.168\.21\.1|secret-password|secret-imei/);
  assert.match(value.document.getElementById('mfDiagStatus').textContent,/three fixed endpoints/);
});

test('R2.1 safe copy is allowlisted and excludes private network and cell values',{skip:!parseHTML},()=>{
  const value=fixture();value.document.getElementById('mfDiagCopy').click();
  const report=value.document.getElementById('mfDiagReport').value,parsed=JSON.parse(report);
  assert.equal(parsed.schema,'mf885-community-safe-diagnostics/v1');assert.deepEqual(parsed.community,{value:'0.2.1-community-r2',stale:false});assert.equal(parsed.identity.model.value,'MF885');
  assert.equal(parsed.wan.connectionTime.value,'1d 02h 03m 04s');assert.equal(parsed.battery.outputCurrent.value,'90');
  for(const secret of ['private.apn','10.0.0.9','1.1.1.1','10.0.0.1','192.168.21.1','secret-cell','secret-tac','1300','77','secret-password','secret-ha1','secret-imsi','secret-imei','secret-iccid','secret-msisdn','secret-mac','secret-lan-mac','secret-sms'])assert.doesNotMatch(report,new RegExp(secret.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')));
  assert.equal(value.document.getElementById('mfDiagCopyFallback').hidden,false);
});

test('R2.1 identity mismatch warns but still performs all three fixed reads',{skip:!parseHTML},()=>{
  const bad=statusXml.replace('MF96 Ver.D','MF96 Ver.C'),value=fixture({auto:false});value.setResponses({status1:bad,wan:wanXml,Engineer_parameter:engineerXml});value.controller.onLoad();
  assert.deepEqual(value.calls.map(call=>call.name),['status1','wan','Engineer_parameter']);assert.equal(value.document.getElementById('mfDiagCopy').disabled,false);
  assert.match(value.document.getElementById('mfDiagStatus').textContent,/identity was not proven/i);
});

test('R2.1 later partial failure preserves previous WAN values as visibly stale and never retries',{skip:!parseHTML},()=>{
  const value=fixture();value.setResponses({status1:statusXml,wan:{error:true,state:'timeout'},Engineer_parameter:engineerXml});value.document.getElementById('mfDiagRefresh').click();
  assert.deepEqual(value.calls.map(call=>call.name),['status1','wan','Engineer_parameter','status1','wan','Engineer_parameter']);
  assert.match(value.document.getElementById('mfDiagStatus').textContent,/Partial diagnostics: 1 endpoint failed/);
  const rows=Array.from(value.document.getElementById('mfDiagValues').children),operator=rows.find(row=>/Operator/.test(row.textContent));
  assert.match(operator.textContent,/previous/);assert.match(operator.textContent,/Carrier & Co/);assert.match(operator.getAttribute('style'),/opacity/);
  value.document.getElementById('mfDiagCopy').click();const snapshot=JSON.parse(value.document.getElementById('mfDiagReport').value);
  assert.deepEqual(snapshot.cellular.operator,{value:'Carrier & Co',stale:true});assert.deepEqual(snapshot.cellular.rsrp,{value:'-94',stale:false});
});

test('R2.1 preserves prior display after a later status1 failure and still reads all endpoints',{skip:!parseHTML},()=>{
  const value=fixture();value.setResponses({status1:{error:true,status:401,state:'error'},wan:wanXml,Engineer_parameter:engineerXml});value.document.getElementById('mfDiagRefresh').click();
  assert.equal(value.calls.length,6);assert.deepEqual(value.calls.slice(-3).map(call=>call.name),['status1','wan','Engineer_parameter']);assert.equal(value.document.getElementById('mfDiagCopy').disabled,false);
  assert.match(value.document.getElementById('mfDiagValues').textContent,/Carrier & Co/);assert.match(value.document.getElementById('mfDiagValues').textContent,/previous/);
  assert.match(value.document.getElementById('mfDiagStatus').textContent,/identity was not proven/i);
});

test('R2.1 diagnostics sources contain no detailed-log, background-polling, or browser-storage path',()=>{
  const combined=source+'\n'+html;
  assert.doesNotMatch(combined,/detailed_log|setInterval|localStorage|sessionStorage|XMLHttpRequest\.prototype|fetch\s*=|event log/i);
});

test('R2.1 preserves unknown enums verbatim with the explicit raw marker',{skip:!parseHTML},()=>{
  const value=fixture({auto:false}),xml=new value.window.DOMParser().parseFromString('<RGW><wan><sim_status>9</sim_status></wan><batteryinfo><Charger_status>88</Charger_status></batteryinfo></RGW>','text/xml');
  const normalized=value.window.MF885CommunityDiagnostics.normalize({status1:value.window.MF885CommunityDiagnostics.extract('status1',xml)});
  assert.equal(normalized.sim.value,'Unknown (raw: 9)');
  assert.equal(normalized.chargerStatus.value,'Unknown (raw: 88)');
});

test('R2.1 diagnostics controller implements the production layout-manager lifecycle',{skip:!parseHTML},()=>{
  const value=fixture({auto:false});assert.equal(typeof value.controller.setXMLName,'function');
  assert.doesNotThrow(()=>value.controller.setXMLName('status1'));value.controller.onLoad(true);
  assert.deepEqual(value.calls.map(call=>call.name),['status1','wan','Engineer_parameter']);
  assert.equal(value.document.getElementById('mfDiagCopy').textContent,'Copy safe snapshot');
});

test('R2.1 parses the checked-in 2.5.94 endpoint fixtures without flattening scope',{skip:!parseHTML},()=>{
  const directory=path.join(__dirname,'fixtures/mf885-2.5.94'),value=fixture({auto:false});
  value.setResponses(Object.fromEntries(['status1','wan','Engineer_parameter'].map(name=>[
    name,fs.readFileSync(path.join(directory,`${name}.xml`),'utf8')
  ])));
  value.controller.onLoad();
  assert.deepEqual(value.calls.map(call=>call.name),['status1','wan','Engineer_parameter']);
  const visible=value.document.getElementById('mfDiagValues').textContent;
  for(const expected of ['MF885','2.5.94','Example Operator','4G · LTE','192.0.2.10','Band3','1300','42','-97','-11','18'])
    assert.match(visible.replace(/\s+/g,''),new RegExp(expected.replace(/\s+/g,'').replace(/[.*+?^${}()|[\]\\]/g,'\\$&')));
  assert.match(value.document.getElementById('mfDiagStatus').textContent,/identity was not proven/i);
});
