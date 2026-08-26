const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');

let parseHTML=null;
for(const candidate of ['linkedom','/opt/openclaw-runtime/releases/2026.7.1-2/lib/node_modules/openclaw/node_modules/linkedom']){try{({parseHTML}=require(candidate));break}catch(_){}}

const source=fs.readFileSync(path.join(__dirname,'../firmware/community-r1/SMS.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../firmware/community-r1/SMS.html'),'utf8');

function fixture(options={}){
  const {window}=parseHTML('<html><body><div id="Content"></div></body></html>');
  const document=window.document,posts=[],reads=[];
  let currentPage=1,pendingCallback=null,statusQueue=[],deletedId='',repeatPages=false,timerId=0,postWatchdog=null;
  function jquery(){return {}}jquery.fn={};
  const escape=value=>String(value).replace(/[&<>]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[ch]));
  const total=options.totalMessages===undefined?42:options.totalMessages;
  window.jQuery=jquery;window.DOMParser=window.DOMParser;
  window.setTimeout=(fn,ms)=>{const id=++timerId;if(ms>=30000)postWatchdog={id,fn};else fn();return id};
  window.clearTimeout=id=>{if(postWatchdog&&postWatchdog.id===id)postWatchdog=null};window.Date=Date;
  window.callProductHTML=()=>html;
  window.callProductXML=()=>`<RGW><status><model>${options.model||'MF885'}</model><version_num>${options.version||'2.5.94_release_MF855_NZ_CP_2.129.003'}</version_num></status></RGW>`;
  window.getHardware_Version=()=>options.hardware||'Ver.D';
  window.putMapElement=(map,key,value)=>map.push({key,value:String(value)});
  window.g_objXML={createXML:map=>map,getXMLDocToString:map=>'<RGW><message>'+map.map(item=>{const name=item.key.split('/').at(-1);return `<${name}>${escape(item.value)}</${name}>`}).join('')+'</message></RGW>'};
  window.PostSyncXML=(_name,body)=>{currentPage=Number((body.match(/<page_number>(\d+)<\/page_number>/)||[])[1]||1);reads.push(body)};
  function pageXml(page){
    if(repeatPages&&page>1)page=1;
    const totalPages=total?Math.ceil(total/10):0,start=(page-1)*10+1,end=Math.min(total,start+9),items=[];
    for(let id=start;id<=end;id++){
      const value=options.unsafeId&&id===1?'bad,id':String(id);
      if(value!==deletedId)items.push(`<Item><index>${value}</index><from>+1555000${String(id).padStart(2,'0')}</from><subject>${id===1?'&lt;img id="pwn"&gt;':'message '+id}</subject><received>8,24,2026,10,00,00,+0</received><status>1</status></Item>`);
    }
    const reported=options.inconsistentPages&&page>1?totalPages+1:totalPages;
    if(options.duplicateId&&page===1&&items.length>1)items[1]=items[1].replace(/<index>2<\/index>/,'<index>1</index>');
    return `<RGW><message><get_message><total_number>${reported}</total_number><message_list>${items.join('')}</message_list></get_message></message></RGW>`;
  }
  window.GetSmsXML=()=>pageXml(currentPage);
  window.PostXMLWithResponse=(_name,body,callback)=>{posts.push(body);pendingCallback=callback};
  window.getData=()=>statusQueue.length?statusQueue.shift():'<RGW><message><sms_cmd>6</sms_cmd><sms_cmd_status_result>1</sms_cmd_status_result></message></RGW>';
  window.UniDecode=value=>String(value);window.confirm=()=>options.confirm!==false;
  const context={window,document,console,Date,JSON,Array,Object,String,Number,Boolean,RegExp,Error,Promise,Map,Set};
  vm.createContext(context);vm.runInContext(source,context);
  const controller=jquery.fn.objSms.call({},options.menu||'mDeviceInbox');controller.setXMLName('message');controller.onLoad();
  return {window,document,controller,posts,reads,setStatusQueue(values){statusQueue=values.slice()},finish(){assert.ok(pendingCallback);pendingCallback()},firePostWatchdog(){assert.ok(postWatchdog);const timer=postWatchdog;postWatchdog=null;timer.fn()},markDeleted(id){deletedId=String(id)},repeatReadbackPages(){repeatPages=true}};
}

test('community r1 renders a bounded collapsed inbox as text with no send or log UI',{skip:!parseHTML},()=>{
  const value=fixture();
  assert.equal(value.reads.length,5);
  assert.match(value.document.getElementById('mfSmsStatus').textContent,/Loaded 42 messages/);
  assert.equal(value.document.querySelectorAll('details').length,42);
  assert.equal(value.document.querySelectorAll('details[open]').length,0);
  assert.equal(value.document.getElementById('pwn'),null);
  assert.match(value.document.getElementById('mfSmsList').textContent,/<img id="pwn">/);
  assert.equal(value.document.getElementById('mfSmsNew'),null);
  assert.equal(value.document.getElementById('mfSmsLog'),null);
});

test('community r1 keeps reads available but locks deletion on identity mismatch',{skip:!parseHTML},()=>{
  const value=fixture({model:'OTHER'});
  assert.equal(value.reads.length,5);
  assert.equal(value.document.querySelector('button[data-sms-delete]').disabled,true);
  value.document.querySelector('button[data-sms-delete]').click();
  assert.equal(value.posts.length,0);
  assert.match(value.document.getElementById('mfSmsStatus').textContent,/Deletion remains locked|Read-only mode/);
});

test('community r1 cancellation sends zero writes and double click sends one exact inbox delete',{skip:!parseHTML},()=>{
  const cancelled=fixture({confirm:false});
  cancelled.document.querySelector('button[data-sms-delete]').click();
  assert.equal(cancelled.posts.length,0);

  const value=fixture();
  const first=value.document.querySelector('button[data-sms-delete]');
  first.click();first.click();
  assert.equal(value.posts.length,1);
  assert.match(value.posts[0],/<message_flag>DELETE_SMS<\/message_flag><sms_cmd>6<\/sms_cmd>/);
  assert.match(value.posts[0],/<tags>12<\/tags><mem_store>1<\/mem_store>/);
  assert.match(value.posts[0],/<delete_message_id>1,<\/delete_message_id>/);
  value.markDeleted('1');
  value.setStatusQueue(['<RGW><message><sms_cmd>6</sms_cmd><sms_cmd_status_result>3</sms_cmd_status_result></message></RGW>']);
  value.finish();
  assert.equal(value.posts.length,1);
  assert.match(value.document.getElementById('mfSmsStatus').textContent,/Message deletion verified/);
  assert.equal(value.document.querySelectorAll('details').length,41);
});

test('community r1 never claims deletion without complete absence readback',{skip:!parseHTML},()=>{
  const present=fixture();
  present.document.querySelector('button[data-sms-delete]').click();
  present.setStatusQueue(['<RGW><message><sms_cmd>6</sms_cmd><sms_cmd_status_result>3</sms_cmd_status_result></message></RGW>']);
  present.finish();
  assert.equal(present.posts.length,1);
  assert.match(present.document.getElementById('mfSmsStatus').textContent,/could not be verified/);
  assert.equal(present.document.querySelector('button[data-sms-delete]').disabled,true);

  const incomplete=fixture();
  incomplete.document.querySelector('button[data-sms-delete]').click();
  incomplete.markDeleted('1');incomplete.repeatReadbackPages();
  incomplete.setStatusQueue(['<RGW><message><sms_cmd>6</sms_cmd><sms_cmd_status_result>3</sms_cmd_status_result></message></RGW>']);
  incomplete.finish();
  assert.match(incomplete.document.getElementById('mfSmsStatus').textContent,/readback was incomplete/i);
  assert.equal(incomplete.posts.length,1);
});

test('community r1 locks writes after status timeout but keeps refresh read-only',{skip:!parseHTML},()=>{
  const value=fixture();
  value.document.querySelector('button[data-sms-delete]').click();
  value.setStatusQueue(Array(12).fill('<RGW><message><sms_cmd>6</sms_cmd><sms_cmd_status_result>1</sms_cmd_status_result></message></RGW>'));
  value.finish();
  assert.equal(value.posts.length,1);
  assert.match(value.document.getElementById('mfSmsStatus').textContent,/outcome unknown/i);
  assert.equal(value.document.getElementById('mfSmsRefresh').disabled,false);
  value.document.getElementById('mfSmsRefresh').click();
  value.document.querySelector('button[data-sms-delete]').click();
  assert.equal(value.posts.length,1);
});

test('community r1 treats a missing async callback as unknown and ignores a late callback',{skip:!parseHTML},()=>{
  const value=fixture();
  value.document.querySelector('button[data-sms-delete]').click();
  assert.equal(value.posts.length,1);value.firePostWatchdog();
  assert.match(value.document.getElementById('mfSmsStatus').textContent,/outcome unknown/i);
  assert.equal(value.document.getElementById('mfSmsRefresh').disabled,false);
  value.finish();
  assert.equal(value.posts.length,1);
  assert.match(value.document.getElementById('mfSmsStatus').textContent,/outcome unknown/i);
});

test('community r1 rejects well-formed non-message XML during delete readback',{skip:!parseHTML},()=>{
  const value=fixture();
  value.document.querySelector('button[data-sms-delete]').click();
  value.markDeleted('1');value.window.GetSmsXML=()=>'<RGW><error>session expired</error></RGW>';
  value.setStatusQueue(['<RGW><message><sms_cmd>6</sms_cmd><sms_cmd_status_result>3</sms_cmd_status_result></message></RGW>']);
  value.finish();
  assert.equal(value.posts.length,1);
  assert.match(value.document.getElementById('mfSmsStatus').textContent,/readback failed/i);
  assert.doesNotMatch(value.document.getElementById('mfSmsStatus').textContent,/deletion verified/i);
});

test('community r1 clears stale delete controls after an ordinary refresh failure',{skip:!parseHTML},()=>{
  const value=fixture();
  assert.equal(value.document.querySelector('button[data-sms-delete]').disabled,false);
  value.window.GetSmsXML=()=>'<RGW><error>session expired</error></RGW>';
  value.document.getElementById('mfSmsRefresh').click();
  assert.equal(value.document.querySelector('button[data-sms-delete]'),null);
  assert.match(value.document.getElementById('mfSmsStatus').textContent,/could not be read/i);
  assert.equal(value.posts.length,0);
});

test('community r1 makes non-inbox folders read-only and handles an empty inbox as complete',{skip:!parseHTML},()=>{
  const outbox=fixture({menu:'mDeviceOutbox'});
  assert.match(outbox.reads[0],/<message_flag>GET_SENT_SMS_LOCAL<\/message_flag>/);
  assert.equal(outbox.document.querySelector('button[data-sms-delete]'),null);
  assert.match(outbox.document.getElementById('mfSmsStatus').textContent,/read-only/);

  const empty=fixture({totalMessages:0});
  assert.equal(empty.reads.length,1);
  assert.match(empty.document.getElementById('mfSmsStatus').textContent,/Loaded 0 messages/);
  assert.doesNotMatch(empty.document.getElementById('mfSmsStatus').textContent,/incomplete/i);
});

test('community r1 rejects an unsafe message id before a POST',{skip:!parseHTML},()=>{
  const value=fixture({unsafeId:true});
  const button=value.document.querySelector('button[data-sms-delete]');
  assert.equal(button.disabled,true);button.click();
  assert.equal(value.posts.length,0);
  assert.match(value.document.getElementById('mfSmsStatus').textContent,/incomplete/i);
});

test('community r1 locks deletion for duplicate ids and inconsistent pagination',{skip:!parseHTML},()=>{
  for(const options of [{duplicateId:true},{inconsistentPages:true}]){
    const value=fixture(options);
    assert.match(value.document.getElementById('mfSmsStatus').textContent,/incomplete/i);
    for(const button of value.document.querySelectorAll('button[data-sms-delete]'))assert.equal(button.disabled,true);
    assert.equal(value.posts.length,0);
  }
});
