const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');

let parseHTML=null;
for(const candidate of ['linkedom','/opt/openclaw-runtime/releases/2026.7.1-2/lib/node_modules/openclaw/node_modules/linkedom']){try{({parseHTML}=require(candidate));break}catch(_){}}

const source=fs.readFileSync(path.join(__dirname,'../firmware/community-r2.1/SMS.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../firmware/community-r2.1/SMS.html'),'utf8');
const command=(number,status)=>`<RGW><message><sms_cmd>${number}</sms_cmd><sms_cmd_status_result>${status}</sms_cmd_status_result></message></RGW>`;

function fixture(options={}){
  const {window}=parseHTML('<html><body><div id="Content"></div></body></html>');
  const document=window.document,posts=[],reads=[];
  let currentPage=1,currentFlag='',pendingCallback=null,statusQueue=[],deleted=false,sendCompleted=false,timerId=0,watchdog=null;
  function jquery(){return {}}jquery.fn={};
  const escape=value=>String(value).replace(/[&<>]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[ch]));
  window.jQuery=jquery;
  window.setTimeout=(fn,ms)=>{const id=++timerId;if(ms>=30000)watchdog={id,fn};else fn();return id};
  window.clearTimeout=id=>{if(watchdog&&watchdog.id===id)watchdog=null};
  window.callProductHTML=()=>html;
  window.callProductXML=()=>`<RGW><status><model>${options.model||'MF885'}</model><version_num>${options.version||'2.5.94_release_MF855_NZ_CP_2.129.003'}</version_num></status></RGW>`;
  window.getHardware_Version=()=>options.hardware||'MF96 Ver.D';
  window.putMapElement=(map,key,value)=>map.push({key,value:String(value)});
  window.g_objXML={createXML:map=>map,getXMLDocToString:map=>'<RGW><message>'+map.map(item=>`<${item.key.split('/').at(-1)}>${escape(item.value)}</${item.key.split('/').at(-1)}>`).join('')+'</message></RGW>'};
  window.PostSyncXML=(_name,body)=>{currentPage=Number((body.match(/<page_number>(\d+)<\/page_number>/)||[])[1]||1);currentFlag=(body.match(/<message_flag>([^<]+)<\/message_flag>/)||[])[1]||'';reads.push({page:currentPage,flag:currentFlag})};
  function item(id,recipient,body){return `<Item><index>${id}</index><from>${escape(recipient)}</from><contacts>${escape(recipient)}</contacts><subject>${escape(body)}</subject><received>8,26,2026,10,00,00,+0</received><status>1</status></Item>`}
  window.GetSmsXML=()=>{
    if(currentFlag==='GET_SENT_SMS_LOCAL'){
      if(options.incompleteSent||options.incompleteAfter&&sendCompleted)return `<RGW><message><get_message><total_number>3</total_number><message_list>${currentPage===1?item('old','+15550000000','old'):''}</message_list></get_message></message></RGW>`;
      const items=[item('old','+15550000000','old')];if(sendCompleted&&options.recordSent!==false)items.unshift(item('new','+15551234567','hello <b>'));
      return `<RGW><message><get_message><total_number>1</total_number><message_list>${items.join('')}</message_list></get_message></message></RGW>`;
    }
    const items=deleted?'':item('1','+15550000001','inbox <img id="pwn">');
    return `<RGW><message><get_message><total_number>${items?1:0}</total_number><message_list>${items}</message_list></get_message></message></RGW>`;
  };
  window.PostXMLWithResponse=(_name,body,callback)=>{posts.push(body);pendingCallback=callback};
  window.getData=()=>{const value=statusQueue.length?statusQueue.shift():command('4','1');if(/<sms_cmd>4<\/sms_cmd>/.test(value)&&/<sms_cmd_status_result>3<\/sms_cmd_status_result>/.test(value))sendCompleted=true;return value};
  window.UniDecode=value=>String(value);
  window.UniEncode=value=>String(value).split('').map(ch=>ch.charCodeAt(0).toString(16).padStart(4,'0')).join('').toUpperCase();
  window.GetSmsTime=()=> '8,26,2026,10,00,00,+0';window.confirm=()=>options.confirm!==false;
  const context={window,document,console,Date,JSON,Array,Object,String,Number,Boolean,RegExp,Error,Promise,Map,Set};
  vm.createContext(context);vm.runInContext(source,context);
  function openController(){const controller=jquery.fn.objSms.call({},'mDeviceInbox');controller.setXMLName('message');controller.onLoad();return controller}
  const controller=openController();
  return {window,document,posts,reads,controller,reopen:openController,setStatus(values){statusQueue=values.slice()},finish(){assert.ok(pendingCallback);pendingCallback()},timeout(){assert.ok(watchdog);const timer=watchdog;watchdog=null;timer.fn()},markDeleted(){deleted=true}};
}

function draft(value,phone='+15551234567',body='hello <b>'){
  value.document.getElementById('mfSmsNew').click();
  value.document.getElementById('mfSmsNumber').value=phone;
  value.document.getElementById('mfSmsBody').value=body;
  value.document.getElementById('mfSmsReview').click();
}

test('R2.1 review writes nothing, escapes content, then sends exactly one stock POST and verifies a new Sent entry',{skip:!parseHTML},()=>{
  const value=fixture();draft(value);
  assert.equal(value.posts.length,0);
  assert.equal(value.document.querySelector('#mfSmsReviewBody b'),null);
  assert.equal(value.document.getElementById('mfSmsReviewBody').textContent,'hello <b>');
  value.document.getElementById('mfSmsSend').click();value.document.getElementById('mfSmsSend').click();
  assert.equal(value.posts.length,1);
  assert.match(value.posts[0],/<message_flag>SEND_SMS<\/message_flag><sms_cmd>4<\/sms_cmd>/);
  assert.match(value.posts[0],/<contacts>\+15551234567<\/contacts>/);
  assert.match(value.posts[0],/<content>00680065006C006C006F0020003C0062003E<\/content>/);
  assert.match(value.posts[0],/<encode_type>UNICODE<\/encode_type>/);
  value.setStatus([command('4','1'),command('4','3')]);value.finish();
  assert.equal(value.posts.length,1);
  assert.match(value.document.getElementById('mfSmsStatus').textContent,/Recorded in Sent messages; delivery is not proven/);
});

test('R2.1 accepts at most four UCS-2 segments and rejects unsafe input before POST',{skip:!parseHTML},()=>{
  const core=fixture().window.MF885_COMMUNITY_R21_SMS_CORE;
  assert.equal(core.segments('я'.repeat(268)),4);assert.equal(core.validBody('я'.repeat(268)),true);
  for(const body of ['я'.repeat(269),'x\ud800y','x\ty','x\0y','x\u0085y','x\u009fy','😀'])assert.equal(core.validBody(body),false);
  for(const phone of ['1,2','+12','+1234567890123456','+1+2'])assert.equal(core.validPhone(phone),false);
});

test('R2.1 submits an exact 268-unit four-segment UCS-2 payload once',{skip:!parseHTML},()=>{
  const body='я'.repeat(268),value=fixture();draft(value,'+15551234567',body);
  assert.match(value.document.getElementById('mfSmsReviewSegments').textContent,/4 UCS-2 segments/);
  value.document.getElementById('mfSmsSend').click();value.document.getElementById('mfSmsSend').click();
  assert.equal(value.posts.length,1);
  const encoded=(value.posts[0].match(/<content>([0-9A-F]+)<\/content>/)||[])[1]||'';
  assert.equal(encoded.length,268*4);assert.equal(encoded,'044F'.repeat(268));
});

test('R2.1 incomplete Sent baseline locks send and delete with zero mutation POSTs',{skip:!parseHTML},()=>{
  const value=fixture({incompleteSent:true});draft(value);value.document.getElementById('mfSmsSend').click();
  assert.equal(value.posts.length,0);assert.match(value.document.getElementById('mfSmsStatus').textContent,/No SMS was submitted/i);
  assert.equal(value.document.getElementById('mfSmsNew').disabled,true);
  assert.equal(value.document.querySelector('button[data-sms-delete]').disabled,true);
  assert.equal(value.document.getElementById('mfSmsRefresh').disabled,false);
});

test('R2.1 unknown send callback locks both mutations and ignores a late callback',{skip:!parseHTML},()=>{
  const value=fixture();draft(value);value.document.getElementById('mfSmsSend').click();assert.equal(value.posts.length,1);
  value.timeout();assert.match(value.document.getElementById('mfSmsStatus').textContent,/Outcome unknown/i);
  assert.equal(value.document.getElementById('mfSmsNew').disabled,true);assert.equal(value.document.querySelector('button[data-sms-delete]').disabled,true);
  value.finish();assert.equal(value.posts.length,1);assert.match(value.document.getElementById('mfSmsStatus').textContent,/Outcome unknown/i);
});

test('R2.1 mutation fence survives controller recreation and keeps Refresh available',{skip:!parseHTML},()=>{
  const value=fixture();draft(value);value.document.getElementById('mfSmsSend').click();value.timeout();
  value.reopen();assert.equal(value.document.getElementById('mfSmsNew').disabled,true);
  assert.equal(value.document.querySelector('button[data-sms-delete]').disabled,true);assert.equal(value.document.getElementById('mfSmsRefresh').disabled,false);
  assert.equal(value.window.MF885_COMMUNITY_R21_SMS.isMutationLocked(),true);
  assert.match(value.document.getElementById('mfSmsStatus').textContent,/Outcome unknown/i);
});

test('R2.1 accepted send with incomplete Sent readback is not called verified and locks later writes',{skip:!parseHTML},()=>{
  const value=fixture({incompleteAfter:true});draft(value);value.document.getElementById('mfSmsSend').click();
  value.setStatus([command('4','3')]);value.finish();assert.equal(value.posts.length,1);
  assert.match(value.document.getElementById('mfSmsStatus').textContent,/accepted.*verification was incomplete/i);
  assert.match(value.document.getElementById('mfSmsStatus').textContent,/Delivery is not proven/i);
  assert.equal(value.document.getElementById('mfSmsNew').disabled,true);assert.equal(value.document.querySelector('button[data-sms-delete]').disabled,true);
});

test('R2.1 accepted send without an exact new Sent match locks all later writes',{skip:!parseHTML},()=>{
  const value=fixture({recordSent:false});draft(value);value.document.getElementById('mfSmsSend').click();value.setStatus([command('4','3')]);value.finish();
  assert.equal(value.posts.length,1);assert.match(value.document.getElementById('mfSmsStatus').textContent,/no matching new Sent record/i);
  assert.equal(value.document.getElementById('mfSmsNew').disabled,true);assert.equal(value.document.querySelector('button[data-sms-delete]').disabled,true);
});

test('R2.1 command mismatch exhausts bounded reads and locks without another POST',{skip:!parseHTML},()=>{
  const value=fixture();draft(value);value.document.getElementById('mfSmsSend').click();value.setStatus(Array(11).fill(command('6','3')));value.finish();
  assert.equal(value.posts.length,1);assert.equal(value.window.MF885_COMMUNITY_R21_SMS.isMutationLocked(),true);assert.match(value.document.getElementById('mfSmsStatus').textContent,/Outcome unknown/i);
});

test('R2.1 matching rejection is reported without retry',{skip:!parseHTML},()=>{
  const value=fixture();draft(value);value.document.getElementById('mfSmsSend').click();value.setStatus([command('4','2')]);value.finish();
  assert.equal(value.posts.length,1);assert.match(value.document.getElementById('mfSmsStatus').textContent,/rejected sending \(status 2\).*No retry/i);assert.equal(value.window.MF885_COMMUNITY_R21_SMS.isMutationBusy(),false);
});

test('R2.1 binds the exact reviewed target and body before allowing Send once',{skip:!parseHTML},()=>{
  const value=fixture();draft(value);value.document.getElementById('mfSmsBody').value='changed after review';value.document.getElementById('mfSmsSend').click();
  assert.equal(value.posts.length,0);assert.equal(value.document.getElementById('mfSmsComposer').hidden,false);assert.match(value.document.getElementById('mfSmsStatus').textContent,/must be reviewed again/i);
});

test('R2.1 deletion stays one-POST and locks writes when its readback throws',{skip:!parseHTML},()=>{
  const value=fixture();value.document.querySelector('button[data-sms-delete]').click();assert.equal(value.posts.length,1);
  assert.match(value.posts[0],/<message_flag>DELETE_SMS<\/message_flag><sms_cmd>6<\/sms_cmd>/);
  assert.match(value.posts[0],/<tags>12<\/tags><mem_store>1<\/mem_store><delete_message_id>1,<\/delete_message_id>/);
  value.window.GetSmsXML=()=>{throw new Error('read failed')};value.setStatus([command('6','3')]);value.finish();
  assert.equal(value.posts.length,1);assert.match(value.document.getElementById('mfSmsStatus').textContent,/Deletion readback failed/i);
  assert.equal(value.document.getElementById('mfSmsNew').disabled,true);
});
