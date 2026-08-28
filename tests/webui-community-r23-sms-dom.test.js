const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

let parseHTML=null;
for(const candidate of ['linkedom','/opt/openclaw-runtime/releases/2026.7.1-2/lib/node_modules/openclaw/node_modules/linkedom']){try{({parseHTML}=require(candidate));break}catch(_){}}

const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'firmware/community-r2.3/SMS.html'),'utf8');
const source=fs.readFileSync(path.join(root,'firmware/community-r2.3/SMS.js'),'utf8');
const bootstrap=fs.readFileSync(path.join(root,'firmware/community-r2.3/community_bootstrap.js'),'utf8');

function xmlEscape(value){return String(value).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function messageXml(items,total){
  return '<RGW><message><get_message><total_number>'+total+'</total_number><message_list>'+items.map(item=>
    '<Item><index>'+xmlEscape(item.id)+'</index><from>'+xmlEscape(item.from)+'</from><subject>'+xmlEscape(item.body)+'</subject><received>'+xmlEscape(item.date)+'</received></Item>'
  ).join('')+'</message_list></get_message></message></RGW>';
}

function harness(options={}){
  const {window}=parseHTML('<html><body><div id="Content"></div></body></html>');
  function jquery(){}jquery.fn={};jquery.i18n={map:{}};
  let inbox=options.inbox||Array.from({length:12},(_,index)=>({id:String(index+1),from:'+700000000'+String(index).padStart(2,'0'),body:'Body '+(index+1),date:'2026-08-27 21:'+String(index).padStart(2,'0')}));
  let lastMap=[],reads=0,sentReads=0,recorded=false,confirmResult=false,lastCommand='4',lastTarget='',lastBody='',statusReads=0,permissionCalls=0;const posts=[],postCallbacks=[],timers=[],notifications=[],stored=options.storedEnabled?{'mf885.community.r23.sms-watch.v1':'1'}:{};
  function FakeNotification(title){notifications.push(String(title))}
  FakeNotification.permission=options.notificationPermission||'default';
  FakeNotification.requestPermission=()=>{permissionCalls++;return Promise.resolve(FakeNotification.permission)};
  const exact='<RGW><sysinfo><model_name>LV01</model_name><hardware_version>MF96 Ver.D</hardware_version><version_num>2.5.94_release_MF855_NZ_CP_2.129.003</version_num></sysinfo></RGW>';
  Object.assign(window,{jQuery:jquery,$:jquery,console,confirm:()=>confirmResult,callProductHTML:()=>html,callProductXML:()=>exact,
    putMapElement:(map,key,value)=>map.push({key,value}),g_objXML:{createXML:value=>value,getXMLDocToString:value=>value},
    PostSyncXML:(name,map)=>{lastMap=map;reads++},GetSmsXML:()=>{
      const flag=(lastMap.find(item=>/message_flag$/.test(item.key))||{}).value;
      const page=Number((lastMap.find(item=>/page_number$/.test(item.key))||{}).value||1);
      if(flag==='GET_SENT_SMS_LOCAL'){
        if(options.sentBaselineIncomplete&&!recorded)return '<RGW><message><get_message><total_number>2</total_number><message_list/></get_message></message></RGW>';
        sentReads++;return recorded&&!options.sentMismatch?messageXml([{id:'sent-1',from:lastTarget,body:lastBody,date:'now'}],1):messageXml([],0);
      }
      return page===1?messageXml(inbox.slice(0,10),2):messageXml(inbox.slice(10),2);
    },
    PostXMLWithResponse:(name,map,callback)=>{
      posts.push(map);postCallbacks.push(callback);lastCommand=(map.find(item=>/sms_cmd$/.test(item.key))||{}).value||'';
      lastTarget=(map.find(item=>/contacts$/.test(item.key))||{}).value||'';
      const encoded=(map.find(item=>/content$/.test(item.key))||{}).value||'';lastBody=encoded.replace(/[0-9A-F]{4}/g,unit=>String.fromCharCode(parseInt(unit,16)));
      if(lastCommand==='4')recorded=true;if(!options.deferCallback)callback();
    },getData:()=>{statusReads++;const command=options.statusCommand||lastCommand,status=options.statusValue||'3';return '<RGW><sms_cmd>'+command+'</sms_cmd><sms_cmd_status_result>'+status+'</sms_cmd_status_result></RGW>'},
    isSecureContext:options.secureContext===true,Notification:FakeNotification,
    sessionStorage:{getItem:key=>Object.prototype.hasOwnProperty.call(stored,key)?stored[key]:null,setItem:(key,value)=>{if(options.storageThrows)throw new Error('storage');stored[key]=String(value)},removeItem:key=>{delete stored[key]}},
    setTimeout:(fn,delay)=>{if(delay===1000){fn();return 0}const timer={fn,delay,cancelled:false};timers.push(timer);return timers.length},clearTimeout:id=>{if(id&&timers[id-1])timers[id-1].cancelled=true},UniDecode:value=>value,UniEncode:value=>Array.from(value).map(character=>character.charCodeAt(0).toString(16).padStart(4,'0')).join(''),GetSmsTime:()=> 'fixture'
  });
  const context=window;vm.createContext(context);vm.runInContext(bootstrap,context);vm.runInContext(source,context);
  const controller=jquery.fn.objSms.call({},'mDeviceInbox');controller.setXMLName('message');controller.onLoad();
  function fireTimer(delay){const timer=timers.find(item=>!item.cancelled&&item.delay===delay);if(!timer)return false;timer.cancelled=true;timer.fn();return true}
  return {window,document:window.document,jquery,posts,postCallbacks,notifications,stored,
    fireWatchdog(){return fireTimer(30000)},fireWatchCycle(){return fireTimer(60000)},setConfirm(value){confirmResult=value},setInbox(value){inbox=value},
    get reads(){return reads},get sentReads(){return sentReads},get statusReads(){return statusReads},get permissionCalls(){return permissionCalls},get watchTimers(){return timers.filter(item=>!item.cancelled&&item.delay===60000).length}};
}

test('R2.3 renders bodies immediately and paginates the complete local history without I/O',{skip:!parseHTML},()=>{
  const value=harness();
  assert.equal(value.document.querySelectorAll('#mfSmsList article').length,10);
  assert.match(value.document.getElementById('mfSmsList').textContent,/Body 1/);
  assert.doesNotMatch(value.document.getElementById('mfSmsList').textContent,/Body 11/);
  assert.equal(value.document.getElementById('mfSmsPage').textContent,'Page 1 of 2');
  const reads=value.reads;value.document.getElementById('mfSmsNext').click();
  assert.equal(value.reads,reads);
  assert.equal(value.document.querySelectorAll('#mfSmsList article').length,2);
  assert.match(value.document.getElementById('mfSmsList').textContent,/Body 11/);
  assert.equal(value.document.getElementById('mfSmsPage').textContent,'Page 2 of 2');
});

test('R2.3 direct Send captures one draft and issues one exact mutation without a review panel',{skip:!parseHTML},()=>{
  const value=harness();
  value.document.getElementById('mfSmsNew').click();
  value.document.getElementById('mfSmsNumber').value='+79991234567';
  value.document.getElementById('mfSmsBody').value='Hello';
  value.document.getElementById('mfSmsSend').click();
  assert.equal(value.posts.length,1);
  const fields=Object.fromEntries(value.posts[0].map(item=>[item.key,item.value]));
  assert.equal(fields['RGW/message/flag/message_flag'],'SEND_SMS');
  assert.equal(fields['RGW/message/flag/sms_cmd'],'4');
  assert.equal(fields['RGW/message/send_save_message/contacts'],'+79991234567');
  assert.equal(fields['RGW/message/send_save_message/encode_type'],'UNICODE');
  assert.deepEqual(Array.from(value.posts[0],item=>item.key),[
    'RGW/message/flag/message_flag','RGW/message/flag/sms_cmd','RGW/message/send_save_message/contacts',
    'RGW/message/send_save_message/content','RGW/message/send_save_message/encode_type','RGW/message/send_save_message/sms_time'
  ]);
  assert.equal(value.document.getElementById('mfSmsConfirm'),null);
  assert.match(value.document.getElementById('mfSmsStatus').textContent,/Recorded in Sent\. Delivery is not proven/);
});

test('R2.3 validates locally, supports exactly four UCS-2 segments, and sends the exact encoded body once',{skip:!parseHTML},()=>{
  const value=harness();value.document.getElementById('mfSmsNew').click();
  value.document.getElementById('mfSmsNumber').value='12';value.document.getElementById('mfSmsBody').value='ok';value.document.getElementById('mfSmsSend').click();assert.equal(value.posts.length,0);
  const body='A'.repeat(268);value.document.getElementById('mfSmsNumber').value='+79991234567';value.document.getElementById('mfSmsBody').value=body;value.document.getElementById('mfSmsSend').click();
  assert.equal(value.posts.length,1);const fields=Object.fromEntries(value.posts[0].map(item=>[item.key,item.value]));
  assert.equal(fields['RGW/message/send_save_message/content'],'0041'.repeat(268));
  assert.equal(value.window.MF885_COMMUNITY_R23_SMS.segments(body),4);
  assert.equal(value.window.MF885_COMMUNITY_R23_SMS.validBody(body),true);
  assert.equal(value.window.MF885_COMMUNITY_R23_SMS.validBody('A\u0085B'),false);
  assert.equal(value.window.MF885_COMMUNITY_R23_SMS.validBody('A\ud83d\ude00B'),false);
});

test('R2.3 suppresses a double click while the sole POST callback is pending',{skip:!parseHTML},()=>{
  const value=harness({deferCallback:true});value.document.getElementById('mfSmsNew').click();value.document.getElementById('mfSmsNumber').value='+79991234567';value.document.getElementById('mfSmsBody').value='One click';
  const send=value.document.getElementById('mfSmsSend');send.click();send.click();
  assert.equal(value.posts.length,1);assert.equal(value.window.MF885_COMMUNITY_R23_SMS.isMutationBusy(),true);
});

test('R2.3 callback loss locks the page session and a late callback cannot submit or unlock',{skip:!parseHTML},()=>{
  const value=harness({deferCallback:true});value.document.getElementById('mfSmsNew').click();value.document.getElementById('mfSmsNumber').value='+79991234567';value.document.getElementById('mfSmsBody').value='Callback loss';value.document.getElementById('mfSmsSend').click();
  assert.equal(value.posts.length,1);value.fireWatchdog();assert.equal(value.window.MF885_COMMUNITY_R23_SMS.isMutationLocked(),true);
  value.postCallbacks[0]();assert.equal(value.posts.length,1);assert.equal(value.statusReads,0);assert.equal(value.window.MF885_COMMUNITY_R23_SMS.isMutationLocked(),true);
});

test('R2.3 incomplete Sent baseline submits zero POST and locks writes fail-closed',{skip:!parseHTML},()=>{
  const value=harness({sentBaselineIncomplete:true});value.document.getElementById('mfSmsNew').click();value.document.getElementById('mfSmsNumber').value='+79991234567';value.document.getElementById('mfSmsBody').value='No baseline';value.document.getElementById('mfSmsSend').click();
  assert.equal(value.posts.length,0);assert.equal(value.window.MF885_COMMUNITY_R23_SMS.isMutationLocked(),true);assert.match(value.document.getElementById('mfSmsStatus').textContent,/baseline was incomplete/i);
});

test('R2.3 definitive matched rejection is shown once and is never retried',{skip:!parseHTML},()=>{
  const value=harness({statusValue:'5'});value.document.getElementById('mfSmsNew').click();value.document.getElementById('mfSmsNumber').value='+79991234567';value.document.getElementById('mfSmsBody').value='Rejected';value.document.getElementById('mfSmsSend').click();
  assert.equal(value.posts.length,1);assert.equal(value.statusReads,1);assert.equal(value.window.MF885_COMMUNITY_R23_SMS.isMutationLocked(),false);assert.match(value.document.getElementById('mfSmsStatus').textContent,/Send rejected \(status 5\)\. No retry\./);
});

test('R2.3 locks Send and Delete across controller recreation after command mismatch',{skip:!parseHTML},()=>{
  const value=harness({statusCommand:'6'});value.document.getElementById('mfSmsNew').click();value.document.getElementById('mfSmsNumber').value='+79991234567';value.document.getElementById('mfSmsBody').value='Mismatch';value.document.getElementById('mfSmsSend').click();
  assert.equal(value.posts.length,1);assert.equal(value.window.MF885_COMMUNITY_R23_SMS.isMutationLocked(),true);assert.equal(value.statusReads,11);
  const next=value.jquery.fn.objSms.call({},'mDeviceInbox');next.setXMLName('message');next.onLoad();
  assert.equal(value.document.getElementById('mfSmsNew').disabled,true);assert.equal(value.document.querySelector('button[data-sms-delete]').disabled,true);
});

test('R2.3 locks after accepted status when no matching new Sent record exists',{skip:!parseHTML},()=>{
  const value=harness({sentMismatch:true});value.document.getElementById('mfSmsNew').click();value.document.getElementById('mfSmsNumber').value='+79991234567';value.document.getElementById('mfSmsBody').value='No readback';value.document.getElementById('mfSmsSend').click();
  assert.equal(value.posts.length,1);assert.equal(value.window.MF885_COMMUNITY_R23_SMS.isMutationLocked(),true);assert.match(value.document.getElementById('mfSmsStatus').textContent,/no matching new Sent record/i);
});

test('R2.3 renders hostile SMS text literally and disables Delete for duplicate ids',{skip:!parseHTML},()=>{
  const inbox=[{id:'dup',from:'<img src=x onerror=alert(1)>',body:'<script>PRIVATE</script>',date:'now'},{id:'dup',from:'+70000000000',body:'second',date:'later'}];
  const value=harness({inbox});const list=value.document.getElementById('mfSmsList');
  assert.match(list.textContent,/<script>PRIVATE<\/script>/);assert.equal(list.querySelectorAll('script,img').length,0);
  for(const button of list.querySelectorAll('button[data-sms-delete]'))assert.equal(button.disabled,true);
  assert.equal(value.posts.length,0);
});

test('R2.3 Delete keeps one native confirmation and one POST plus full readback',{skip:!parseHTML},()=>{
  const value=harness(),button=value.document.querySelector('button[data-sms-delete]');
  const initialReads=value.reads;button.click();assert.equal(value.posts.length,0);assert.equal(value.reads,initialReads);
  value.setConfirm(true);button.click();
  assert.equal(value.posts.length,1);
  const fields=Object.fromEntries(value.posts[0].map(item=>[item.key,item.value]));
  assert.equal(fields['RGW/message/flag/message_flag'],'DELETE_SMS');
  assert.equal(fields['RGW/message/flag/sms_cmd'],'6');
  assert.equal(fields['RGW/message/set_message/delete_message_id'],'1,');
  assert.equal(value.reads,initialReads+2);
  assert.match(value.document.getElementById('mfSmsStatus').textContent,/Deletion was not verified|Outcome unknown/);
});

test('R2.3 SMS checking is opt-in, stores only one boolean, and stays browser-safe on HTTP',{skip:!parseHTML},()=>{
  const value=harness();
  assert.equal(value.window.MF885_COMMUNITY_R23_SMS.isWatchEnabled(),false);
  assert.equal(value.watchTimers,0);assert.equal(value.permissionCalls,0);assert.deepEqual(value.stored,{});
  const input=value.document.getElementById('mfSmsAutoCheck');input.checked=true;input.dispatchEvent(new value.window.Event('change'));
  assert.equal(value.window.MF885_COMMUNITY_R23_SMS.isWatchEnabled(),true);
  assert.equal(value.watchTimers,1);assert.equal(value.permissionCalls,0);
  assert.deepEqual(value.stored,{'mf885.community.r23.sms-watch.v1':'1'});
  assert.match(value.document.getElementById('mfSmsWatchHint').textContent,/HTTP address/);
});

test('R2.3 unchanged polling reads one first page and never announces content',{skip:!parseHTML},()=>{
  const value=harness();const input=value.document.getElementById('mfSmsAutoCheck');input.checked=true;input.dispatchEvent(new value.window.Event('change'));
  const reads=value.reads;assert.equal(value.fireWatchCycle(),true);
  assert.equal(value.reads,reads+1);assert.deepEqual(value.notifications,[]);assert.equal(value.document.getElementById('mfSmsWatchToast'),null);
  assert.equal(value.watchTimers,1);
});

test('R2.3 changed first page triggers one complete read and a generic notification only',{skip:!parseHTML},()=>{
  const value=harness({secureContext:true,notificationPermission:'granted'});const input=value.document.getElementById('mfSmsAutoCheck');input.checked=true;input.dispatchEvent(new value.window.Event('change'));
  const added={id:'new-13',from:'+79990000000',body:'PRIVATE BODY',date:'now'};
  value.setInbox([added,...Array.from({length:12},(_,index)=>({id:String(index+1),from:'+700000000'+String(index).padStart(2,'0'),body:'Body '+(index+1),date:'2026-08-27 21:'+String(index).padStart(2,'0')}))]);
  const reads=value.reads;value.fireWatchCycle();
  assert.equal(value.reads,reads+3);assert.deepEqual(value.notifications,['New router messages: 1']);
  const visible=value.document.getElementById('mfSmsWatchToast').textContent;
  assert.match(visible,/1 new router message/);assert.doesNotMatch(visible,/PRIVATE|7999|new-13/);
  assert.match(value.document.title,/^\(1\)/);assert.deepEqual(value.stored,{'mf885.community.r23.sms-watch.v1':'1'});
});

test('R2.3 watcher detects a new record when the router reuses the same SMS id',{skip:!parseHTML},()=>{
  const original=[{id:'slot-1',from:'+70000000000',body:'Old text',date:'old'}];
  const value=harness({inbox:original,secureContext:true,notificationPermission:'granted'});const input=value.document.getElementById('mfSmsAutoCheck');input.checked=true;input.dispatchEvent(new value.window.Event('change'));
  value.setInbox([{id:'slot-1',from:'+79999999999',body:'NEW PRIVATE TEXT',date:'new'}]);value.fireWatchCycle();
  assert.deepEqual(value.notifications,['New router messages: 1']);assert.doesNotMatch(value.document.getElementById('mfSmsWatchToast').textContent,/PRIVATE|7999|slot-1/);
  assert.deepEqual(value.stored,{'mf885.community.r23.sms-watch.v1':'1'});
});

test('R2.3 watcher never overlaps a pending SMS mutation',{skip:!parseHTML},()=>{
  const value=harness({deferCallback:true});const input=value.document.getElementById('mfSmsAutoCheck');input.checked=true;input.dispatchEvent(new value.window.Event('change'));
  value.document.getElementById('mfSmsNew').click();value.document.getElementById('mfSmsNumber').value='+79991234567';value.document.getElementById('mfSmsBody').value='Pending';value.document.getElementById('mfSmsSend').click();
  const reads=value.reads;value.fireWatchCycle();assert.equal(value.reads,reads);assert.equal(value.posts.length,1);assert.equal(value.watchTimers,1);
});

test('R2.3 page lifecycle suspends polling while preserving only its boolean tab preference',{skip:!parseHTML},()=>{
  const value=harness();const input=value.document.getElementById('mfSmsAutoCheck');input.checked=true;input.dispatchEvent(new value.window.Event('change'));
  value.window.dispatchEvent(new value.window.Event('pagehide'));
  assert.equal(value.window.MF885_COMMUNITY_R23_SMS.isWatchEnabled(),true);assert.equal(value.watchTimers,0);assert.deepEqual(value.stored,{'mf885.community.r23.sms-watch.v1':'1'});
  value.window.dispatchEvent(new value.window.Event('pageshow'));assert.equal(value.watchTimers,1);
});

test('R2.3 restored opt-in re-baselines silently and never re-prompts for permission',{skip:!parseHTML},()=>{
  const value=harness({storedEnabled:true,secureContext:true,notificationPermission:'default'});
  assert.equal(value.window.MF885_COMMUNITY_R23_SMS.isWatchEnabled(),true);assert.equal(value.permissionCalls,0);assert.deepEqual(value.notifications,[]);assert.equal(value.watchTimers,1);
});

test('R2.3 notification permission is requested once only from an explicit secure-context gesture',{skip:!parseHTML},()=>{
  const value=harness({secureContext:true,notificationPermission:'default'});const input=value.document.getElementById('mfSmsAutoCheck');input.checked=true;input.dispatchEvent(new value.window.Event('change'));
  assert.equal(value.permissionCalls,1);input.checked=false;input.dispatchEvent(new value.window.Event('change'));input.checked=true;input.dispatchEvent(new value.window.Event('change'));
  assert.equal(value.permissionCalls,1);
  const denied=harness({secureContext:true,notificationPermission:'denied'});const deniedInput=denied.document.getElementById('mfSmsAutoCheck');deniedInput.checked=true;deniedInput.dispatchEvent(new denied.window.Event('change'));
  assert.equal(denied.permissionCalls,0);assert.match(denied.document.getElementById('mfSmsWatchHint').textContent,/blocked/);
});

test('R2.3 watcher pauses after three unsafe reads without advancing or announcing',{skip:!parseHTML},()=>{
  const value=harness();const input=value.document.getElementById('mfSmsAutoCheck');input.checked=true;input.dispatchEvent(new value.window.Event('change'));
  value.setInbox([{id:'dup',from:'a',body:'one',date:'x'},{id:'dup',from:'b',body:'two',date:'y'}]);
  value.fireWatchCycle();value.fireWatchCycle();value.fireWatchCycle();
  assert.equal(value.window.MF885_COMMUNITY_R23_SMS.isWatchEnabled(),false);assert.equal(value.watchTimers,0);assert.deepEqual(value.notifications,[]);assert.deepEqual(value.stored,{});
  assert.match(value.document.getElementById('mfSmsWatchHint').textContent,/Paused/);
});
