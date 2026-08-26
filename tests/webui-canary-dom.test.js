const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const path=require("node:path");

let parseHTML=null;
for(const candidate of ["linkedom","/opt/openclaw-runtime/releases/2026.7.1-2/lib/node_modules/openclaw/node_modules/linkedom"]){try{({parseHTML}=require(candidate));break}catch(_){}}

class FakeXHR{
  constructor(){this.listeners={};this.readyState=0;this.status=0;this.responseText="";FakeXHR.instances.push(this)}
  open(method,url){this.method=method;this.url=url;this.readyState=1}
  setRequestHeader(name,value){(this.headers||(this.headers={}))[name]=value}
  addEventListener(name,handler){(this.listeners[name]||(this.listeners[name]=[])).push(handler)}
  send(body){this.body=body;this.status=/timeout_probe/.test(this.url)?0:200;this.readyState=4;this.responseText=/file=message/.test(this.url)?'<RGW><message><sender>+15551234567</sender><content>PRIVATE SMS WORDS</content></message></RGW>':/file=status1/.test(this.url)?'<RGW><status><content>MODEM TRACE CONTENT at 12:34:56</content><pdp_name>internet.apn</pdp_name></status></RGW>':/credential_probe/.test(this.url)?'{"password":"JSON_SECRET","token":"JSON_TOKEN","access_token":"ACCESS_SECRET","session_id":"SESSION_SECRET","imsi":"001010123456789","iccid":"8901000000000000001","serial_number":"PRIVATE_SERIAL","username":"PRIVATE_WAN_USER","untyped_network":"2001:db8::2","loopback":"::1","link_local":"fe80::","mapped":"::ffff:192.0.2.1"}\n{"set-cookie":"ALT_COOKIE","proxy-authorization":"ALT_AUTH","serial-number":"ALT_SERIAL","x-api-key":"ALT_API_KEY"}\n{"password":"prefix\\\"SECRET_SUFFIX"}\n{"Authorization":"Bearer JSON_AUTH_SECRET"}\n{"Cookie":"sid=JSON_COOKIE_SECRET"}\nCookie: sid=FIRST; session=SECOND\nSet-Cookie: sid=THIRD; session=FOURTH\n<password value="ATTR_SECRET"/><IMEI>123456789012345</IMEI><ssid>PRIVATE_SSID</ssid><username>XML_PRIVATE_USER</username><untyped_ipv6>2001:db8::3</untyped_ipv6>':'<RGW><detailed_log><pdp_name>internet.apn</pdp_name><ip_addr>10.0.0.2</ip_addr><wifimac>aa:bb:cc:dd:ee:ff</wifimac></detailed_log></RGW>';if(this.onreadystatechange)this.onreadystatechange();if(/timeout_probe/.test(this.url))for(const handler of this.listeners.timeout||[])handler.call(this);for(const handler of this.listeners.loadend||[])handler.call(this)}
}
FakeXHR.instances=[];
const fakeOpen=FakeXHR.prototype.open,fakeSend=FakeXHR.prototype.send;
function resetFakeXHR(){FakeXHR.prototype.open=fakeOpen;FakeXHR.prototype.send=fakeSend;FakeXHR.instances=[]}

test("firmware Canary panel polls authenticated detailed_log and masks private values",{skip:!parseHTML},async()=>{
  resetFakeXHR();
  const {window}=parseHTML('<html><head></head><body></body></html>'),document=window.document,script=fs.readFileSync(path.join(__dirname,"../firmware/webui-canary-logs/canary_logs.js"),"utf8");
  let copied="";
  const context={window,document,console,XMLHttpRequest:FakeXHR,getAuthHeader:method=>"Digest TEST_AUTH_"+method,navigator:{clipboard:{writeText:async value=>{copied=value}}},location:{href:"http://192.168.21.1/"},setInterval:()=>1,setTimeout,clearTimeout,Date,JSON,Array,Object,String,Number,Boolean,RegExp,Error,Promise,Map,Set,Blob,URL:{createObjectURL:()=>"blob:test",revokeObjectURL:()=>{}},XMLSerializer:window.XMLSerializer};
  window.window=window;window.document=document;window.XMLHttpRequest=FakeXHR;window.fetch=null;
  vm.createContext(context);vm.runInContext(script,context);
  assert.equal(window.MF885_COMMUNITY_CANARY.id,"0.0-logs-r1");
  assert.ok(document.getElementById("zmiDbgToggle"));assert.ok(document.getElementById("zmiDbgPanel"));
  document.getElementById("zmiDbgToggle").click();
  const poll=FakeXHR.instances.at(-1);assert.equal(poll.method,"GET");assert.equal(poll.url,"xml_action.cgi?method=get&module=duster&file=detailed_log");assert.equal(poll.headers.Authorization,"Digest TEST_AUTH_GET");
  const technical=new FakeXHR();technical.open("GET","xml_action.cgi?method=get&module=duster&file=status1");technical.send(null);
  const sms=new FakeXHR();sms.open("POST","xml_action.cgi?method=set&module=duster&file=message");sms.send('<content>PRIVATE REQUEST</content><phone_number>+15557654321</phone_number>');
  const credentials=new FakeXHR();credentials.open("GET","xml_action.cgi?method=get&module=duster&file=credential_probe");credentials.send(null);
  window.console.warn("call +15559876543 failed");
  const visible=document.getElementById("zmiDbgList").textContent;
  assert.match(visible,/MODEM TRACE CONTENT/);
  for(const smsValue of ["PRIVATE SMS WORDS","PRIVATE REQUEST","+15551234567","+15557654321","+15559876543","JSON_SECRET","JSON_TOKEN","ACCESS_SECRET","SESSION_SECRET","ALT_COOKIE","ALT_AUTH","ALT_SERIAL","ALT_API_KEY","SECRET_SUFFIX","JSON_AUTH_SECRET","JSON_COOKIE_SECRET","FIRST","SECOND","THIRD","FOURTH","ATTR_SECRET","123456789012345","001010123456789","8901000000000000001","PRIVATE_SERIAL","PRIVATE_SSID","PRIVATE_WAN_USER","XML_PRIVATE_USER","2001:db8::2","2001:db8::3","::1","fe80::","::ffff:192.0.2.1","internet.apn","10.0.0.2","aa:bb:cc:dd:ee:ff"])assert.doesNotMatch(visible,new RegExp(smsValue.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")));
  assert.match(visible,/12:34:56/);
  assert.match(visible,/SMS payload hidden/);
  document.getElementById("zmiDbgCopy").click();await Promise.resolve();
  assert.match(copied,/MODEM TRACE CONTENT.*12:34:56/);assert.doesNotMatch(copied,/PRIVATE SMS WORDS|JSON_SECRET|ALT_COOKIE|ALT_AUTH|ALT_SERIAL|ALT_API_KEY|SECRET_SUFFIX|001010123456789|8901000000000000001|PRIVATE_SERIAL|PRIVATE_WAN_USER|XML_PRIVATE_USER|2001:db8::[23]|::1|fe80::|::ffff:192\.0\.2\.1|internet\.apn|10\.0\.0\.2|aa:bb:cc:dd:ee:ff/);
});

test("firmware Canary r2 correlates bounded phases and does not mistake generic content for SMS",{skip:!parseHTML},async()=>{
  resetFakeXHR();
  const {window}=parseHTML('<html><head></head><body></body></html>'),document=window.document,script=fs.readFileSync(path.join(__dirname,"../firmware/webui-canary-logs-r2/canary_logs.js"),"utf8");
  let copied="";
  const fetchCalls=[],nativeFetch=(input,init)=>{fetchCalls.push({input,method:init&&init.method||"GET"});return Promise.resolve({status:200,clone:()=>({text:()=>Promise.resolve('{"Authorization":"Bearer FETCH_AUTH_SECRET"}\n<status>FETCH TRACE</status>')})})};
  const quiet={error:()=>{},warn:()=>{},log:()=>{},info:()=>{}};
  window.console=quiet;
  const context={window,document,console:quiet,XMLHttpRequest:FakeXHR,getAuthHeader:method=>"Digest TEST_AUTH_"+method,navigator:{clipboard:{writeText:async value=>{copied=value}}},location:{href:"http://192.168.21.1/",pathname:"/"},setInterval:()=>1,setTimeout,clearTimeout,Date,JSON,Array,Object,String,Number,Boolean,RegExp,Error,Promise,Map,Set,XMLSerializer:window.XMLSerializer};
  window.window=window;window.document=document;window.XMLHttpRequest=FakeXHR;window.fetch=nativeFetch;delete window.MF885_COMMUNITY_CANARY;
  vm.createContext(context);vm.runInContext(script,context);
  assert.equal(window.MF885_COMMUNITY_CANARY.id,"0.0-logs-r2");
  document.getElementById("zmiDbgToggle").click();
  const poll=FakeXHR.instances.at(-1);assert.equal(poll.headers.Authorization,"Digest TEST_AUTH_GET");
  const reused=new FakeXHR();reused.open("GET","xml_action.cgi?method=get&module=duster&file=status1");reused.send(null);
  reused.open("POST","xml_action.cgi?method=set&module=duster&file=message");reused.send('<content>PRIVATE REQUEST</content><phone_number>+15557654321</phone_number>');
  const credentials=new FakeXHR();credentials.open("GET","xml_action.cgi?method=get&module=duster&file=credential_probe");credentials.send(null);
  const malformed=new FakeXHR();assert.doesNotThrow(()=>{malformed.open("GET","xml_action.cgi?file=%E0%A4%A");malformed.send(null)});
  await window.fetch("xml_action.cgi?method=get&module=duster&file=fetch_probe",{method:"GET"});await new Promise(resolve=>setTimeout(resolve,0));
  const timeout=new FakeXHR();timeout.open("GET","xml_action.cgi?method=get&module=duster&file=timeout_probe");timeout.send(null);
  window.console.warn("Authorization: Digest response=deadbeef");
  const visible=document.getElementById("zmiDbgList").textContent;
  for(const technicalValue of ["MODEM TRACE CONTENT","FETCH TRACE","timeout","req "])assert.match(visible,new RegExp(technicalValue));
  assert.equal(fetchCalls.length,1);assert.equal(fetchCalls[0].method,"GET");
  for(const secret of ["PRIVATE SMS WORDS","PRIVATE REQUEST","+15551234567","+15557654321","deadbeef","JSON_SECRET","JSON_TOKEN","ACCESS_SECRET","SESSION_SECRET","ALT_COOKIE","ALT_AUTH","ALT_SERIAL","ALT_API_KEY","SECRET_SUFFIX","JSON_AUTH_SECRET","JSON_COOKIE_SECRET","FETCH_AUTH_SECRET","FIRST","SECOND","THIRD","FOURTH","ATTR_SECRET","123456789012345","001010123456789","8901000000000000001","PRIVATE_SERIAL","PRIVATE_SSID","PRIVATE_WAN_USER","XML_PRIVATE_USER","2001:db8::2","2001:db8::3","::1","fe80::","::ffff:192.0.2.1","internet.apn","10.0.0.2","aa:bb:cc:dd:ee:ff"])assert.doesNotMatch(visible,new RegExp(secret.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")));
  assert.match(visible,/12:34:56/);
  assert.match(visible,/SMS hidden/);
  document.getElementById("zmiDbgPause").click();
  for(let i=0;i<250;i++)window.console.info("bounded event "+i);
  assert.match(document.getElementById("zmiDbgMeta").textContent,/dropped [1-9]/);
  document.getElementById("zmiDbgCopy").click();await Promise.resolve();
  assert.match(copied,/schema=2/);assert.match(copied,/dropped=/);assert.doesNotMatch(copied,/deadbeef|PRIVATE SMS WORDS|JSON_SECRET|JSON_TOKEN|ACCESS_SECRET|SESSION_SECRET|ALT_COOKIE|ALT_AUTH|ALT_SERIAL|ALT_API_KEY|SECRET_SUFFIX|JSON_AUTH_SECRET|JSON_COOKIE_SECRET|FETCH_AUTH_SECRET|FIRST|SECOND|THIRD|FOURTH|ATTR_SECRET|123456789012345|001010123456789|8901000000000000001|PRIVATE_SERIAL|PRIVATE_SSID|PRIVATE_WAN_USER|XML_PRIVATE_USER|2001:db8::[23]|::1|fe80::|::ffff:192\.0\.2\.1|internet\.apn|10\.0\.0\.2|aa:bb:cc:dd:ee:ff/);
});
