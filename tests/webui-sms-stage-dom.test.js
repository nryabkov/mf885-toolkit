const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');

let parseHTML=null;
for(const candidate of ['linkedom','/opt/openclaw-runtime/releases/2026.7.1-2/lib/node_modules/openclaw/node_modules/linkedom']){try{({parseHTML}=require(candidate));break}catch(_){}}

const source=fs.readFileSync(path.join(__dirname,'../firmware/webui-sms-r1/SMS.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../firmware/webui-sms-r1/SMS.html'),'utf8');

function fixture(options={}){
  const {window}=parseHTML('<html><body><div id="Content"></div></body></html>');
  const document=window.document,posts=[],reads=[];
  let currentPage=1,pendingCallback=null,statusQueue=[],deletedId='',repeatPages=false;
  function jquery(){return {}}jquery.fn={};
  const escape=value=>String(value).replace(/[&<>]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[ch]));
  window.jQuery=jquery;window.DOMParser=window.DOMParser;window.setTimeout=fn=>{fn();return 1};window.Date=Date;
  window.callProductHTML=()=>html;
  window.callProductXML=()=>`<RGW><status><model>${options.model||'MF885'}</model><version_num>${options.version||'2.5.94_release_MF855_NZ_CP_2.129.003'}</version_num></status></RGW>`;
  window.getHardware_Version=()=>options.hardware||'Ver.D';
  window.putMapElement=(map,key,value)=>map.push({key,value:String(value)});
  window.g_objXML={createXML:map=>map,getXMLDocToString:map=>'<RGW><message>'+map.map(item=>{const name=item.key.split('/').at(-1);return `<${name}>${escape(item.value)}</${name}>`}).join('')+'</message></RGW>'};
  window.PostSyncXML=(_name,body)=>{currentPage=Number((body.match(/<page_number>(\d+)<\/page_number>/)||[])[1]||1);reads.push(body)};
  function pageXml(page){
    if(repeatPages&&page>1)page=1;
    const start=(page-1)*10+1,end=Math.min(42,start+9),items=[];
    for(let id=start;id<=end;id++)if(String(id)!==deletedId)items.push(`<Item><index>${id}</index><from>+1555000${String(id).padStart(2,'0')}</from><subject>${id===1?'&lt;img id="pwn"&gt;':'message '+id}</subject><received>8,24,2026,10,00,00,+0</received><status>1</status></Item>`);
    return `<RGW><message><get_message><total_number>5</total_number><message_list>${items.join('')}</message_list></get_message></message></RGW>`;
  }
  window.GetSmsXML=()=>pageXml(currentPage);
  window.PostXMLWithResponse=(_name,body,callback)=>{posts.push(body);pendingCallback=callback};
  window.getData=()=>statusQueue.length?statusQueue.shift():'<RGW><message><sms_cmd>4</sms_cmd><sms_cmd_status_result>1</sms_cmd_status_result></message></RGW>';
  window.UniDecode=value=>String(value);window.UniEncode=value=>Array.from(String(value),ch=>ch.charCodeAt(0).toString(16).padStart(4,'0')).join('').toUpperCase();
  window.GetSmsTime=()=> '8,24,2026,10,00,00,+0';window.IsGSM7Code=value=>/^[\x00-\x7f]*$/.test(value);window.confirm=()=>options.confirm!==false;
  const context={window,document,console,Date,JSON,Array,Object,String,Number,Boolean,RegExp,Error,Promise,Map,Set};
  vm.createContext(context);vm.runInContext(source,context);
  const controller=jquery.fn.objSms.call({},'mDeviceInbox');controller.setXMLName('message');controller.onLoad();
  return {window,document,controller,posts,reads,setStatusQueue(values){statusQueue=values.slice()},finish(){pendingCallback()},markDeleted(id){deletedId=String(id)},repeatReadbackPages(){repeatPages=true}};
}

test('SMS r1 renders 42 bounded messages as text and enables mutations only on exact identity',{skip:!parseHTML},()=>{
  const value=fixture();
  assert.equal(value.reads.length,5);
  assert.match(value.document.getElementById('mfSmsStatus').textContent,/Loaded 42 messages/);
  assert.equal(value.document.querySelectorAll('article').length,42);
  assert.equal(value.document.getElementById('pwn'),null);
  assert.match(value.document.getElementById('mfSmsList').textContent,/<img id="pwn">/);

  value.document.getElementById('mfSmsNew').click();
  value.document.getElementById('mfSmsNumber').value='+15551234567';
  value.document.getElementById('mfSmsBody').value='hello';
  value.document.getElementById('mfSmsSend').click();
  value.document.getElementById('mfSmsSend').click();
  assert.equal(value.posts.length,1);
  assert.match(value.posts[0],/<message_flag>SEND_SMS<\/message_flag><sms_cmd>4<\/sms_cmd>/);
  assert.match(value.posts[0],/<contacts>\+15551234567<\/contacts>/);
  assert.match(value.posts[0],/<content>00680065006C006C006F<\/content>/);
  assert.match(value.posts[0],/<encode_type>UNICODE<\/encode_type>/);
  value.setStatusQueue(['<RGW><message><sms_cmd>4</sms_cmd><sms_cmd_status_result>1</sms_cmd_status_result></message></RGW>','<RGW><message><sms_cmd>4</sms_cmd><sms_cmd_status_result>3</sms_cmd_status_result></message></RGW>']);
  value.finish();
  assert.equal(value.posts.length,1);
  assert.doesNotMatch(value.document.getElementById('mfSmsLog').textContent,/15551234567|hello|00680065/);
});

test('SMS r1 mismatch and ambiguous completion both fail closed with no replay',{skip:!parseHTML},()=>{
  const mismatch=fixture({model:'OTHER'});
  assert.equal(mismatch.document.getElementById('mfSmsNew').disabled,true);
  mismatch.document.getElementById('mfSmsNew').click();
  assert.equal(mismatch.posts.length,0);

  const unknown=fixture();
  unknown.document.getElementById('mfSmsNew').click();
  unknown.document.getElementById('mfSmsNumber').value='+15551234567';
  unknown.document.getElementById('mfSmsBody').value='hello';
  unknown.document.getElementById('mfSmsSend').click();
  unknown.setStatusQueue(Array(12).fill('<RGW><message><sms_cmd>4</sms_cmd><sms_cmd_status_result>1</sms_cmd_status_result></message></RGW>'));
  unknown.finish();
  assert.equal(unknown.posts.length,1);
  assert.match(unknown.document.getElementById('mfSmsStatus').textContent,/Outcome unknown/);
  assert.equal(unknown.document.getElementById('mfSmsNew').disabled,true);
});

test('SMS r1 delete uses one exact stock command and verifies disappearance',{skip:!parseHTML},()=>{
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
  assert.equal(value.document.querySelectorAll('article').length,41);
});

test('SMS r1 never claims deletion when the success reply is not confirmed by readback',{skip:!parseHTML},()=>{
  const value=fixture();
  value.document.querySelector('button[data-sms-delete]').click();
  value.setStatusQueue(['<RGW><message><sms_cmd>6</sms_cmd><sms_cmd_status_result>3</sms_cmd_status_result></message></RGW>']);
  value.finish();
  assert.equal(value.posts.length,1);
  assert.match(value.document.getElementById('mfSmsStatus').textContent,/deletion could not be verified/i);
  assert.equal(value.document.getElementById('mfSmsNew').disabled,true);
  assert.equal(value.document.querySelectorAll('article').length,42);
});

test('SMS r1 locks deletion after an incomplete repeated-page readback',{skip:!parseHTML},()=>{
  const value=fixture();
  value.document.querySelector('button[data-sms-delete]').click();
  value.markDeleted('1');value.repeatReadbackPages();
  value.setStatusQueue(['<RGW><message><sms_cmd>6</sms_cmd><sms_cmd_status_result>3</sms_cmd_status_result></message></RGW>']);
  value.finish();
  assert.equal(value.posts.length,1);
  assert.match(value.document.getElementById('mfSmsStatus').textContent,/readback was incomplete/i);
  assert.equal(value.document.getElementById('mfSmsNew').disabled,true);
});

test('SMS r1 rejects unsafe recipient, any 71-code-unit body and lone surrogates before POST',{skip:!parseHTML},()=>{
  for(const [phone,body] of [['1,2','ok'],['+15551234567','я'.repeat(71)],['+15551234567','a'.repeat(71)],['+15551234567','x\ud800y']]){
    const value=fixture();value.document.getElementById('mfSmsNew').click();value.document.getElementById('mfSmsNumber').value=phone;value.document.getElementById('mfSmsBody').value=body;value.document.getElementById('mfSmsSend').click();assert.equal(value.posts.length,0);
  }
});
