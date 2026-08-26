/* MF885 Community WebUI SMS 0.0-sms-r1 */
(function(w){
  'use strict';
  var PROFILE={mDeviceInbox:['GET_RCV_SMS_LOCAL','12','1'],mDeviceOutbox:['GET_SENT_SMS_LOCAL','2','1'],mSimSms:['GET_SIM_SMS','','0'],mDrafts:['GET_DRAFT_SMS','2','2']};
  var MAX_PAGES=20,MAX_MESSAGES=200,PAGE_SIZE=10,MAX_LOGS=80,STATUS_POLLS=10;

  function text(node,name){var list=node&&node.getElementsByTagName?node.getElementsByTagName(name):[];return list.length?String(list[0].textContent||'').trim():''}
  function asDocument(value){
    if(value&&value.getElementsByTagName)return value;
    try{return new w.DOMParser().parseFromString(String(value||''),'text/xml')}catch(_){return null}
  }
  function escapeText(value){return String(value==null?'':value)}
  function coreDecode(value){try{return typeof w.UniDecode==='function'?w.UniDecode(value):value}catch(_){return value}}
  function validatePhone(value){return /^\+?[0-9][0-9 ()-]{2,30}$/.test(String(value||'').trim())}
  function hasLoneSurrogate(value){
    for(var i=0;i<value.length;i++){var code=value.charCodeAt(i);if(code>=0xd800&&code<=0xdbff){if(i+1>=value.length||value.charCodeAt(++i)<0xdc00||value.charCodeAt(i)>0xdfff)return true}else if(code>=0xdc00&&code<=0xdfff)return true}return false;
  }
  function commandStatus(value){
    var doc=asDocument(value),cmd=text(doc,'sms_cmd'),status=text(doc,'sms_cmd_status_result');
    return {command:cmd,status:status,complete:status==='3',pending:status===''||status==='0'||status==='1'};
  }
  function parsePage(value){
    var doc=asDocument(value),items=doc?doc.getElementsByTagName('Item'):[],messages=[];
    for(var i=0;i<items.length;i++)messages.push({
      id:text(items[i],'index'),from:coreDecode(text(items[i],'from')).replace(/^;/,'').replace(/;.*$/,''),
      content:coreDecode(text(items[i],'subject')||text(items[i],'content')),received:text(items[i],'received'),status:text(items[i],'status')
    });
    var pages=parseInt(text(doc,'total_number'),10);
    return {messages:messages,totalPages:Number.isFinite(pages)&&pages>0?pages:null};
  }
  function install($){
    if(!$||!$.fn)return;
    $.fn.objSms=function(menuName){
      var root=w.document.getElementById('Content'),xmlName='message',profile=PROFILE[menuName]||PROFILE.mDeviceInbox;
      if(!root)throw new Error('SMS content root is missing');
      root.innerHTML=w.callProductHTML('html/SMS/SMS.html');
      var list=w.document.getElementById('mfSmsList'),status=w.document.getElementById('mfSmsStatus'),composer=w.document.getElementById('mfSmsComposer');
      var refresh=w.document.getElementById('mfSmsRefresh'),newButton=w.document.getElementById('mfSmsNew'),send=w.document.getElementById('mfSmsSend');
      var cancel=w.document.getElementById('mfSmsCancel'),number=w.document.getElementById('mfSmsNumber'),body=w.document.getElementById('mfSmsBody');
      var count=w.document.getElementById('mfSmsCount'),logBox=w.document.getElementById('mfSmsLog'),busy=false,unknown=false,identityMatched=false,logs=[];
      function log(event,detail){
        logs.push(new Date().toISOString()+' '+event+(detail?' '+detail:''));if(logs.length>MAX_LOGS)logs.shift();logBox.textContent=logs.join('\n');
      }
      function setStatus(value,error){status.textContent=value;status.style.color=error?'#b42318':'#344054'}
      function updateButtons(){
        refresh.disabled=busy;newButton.disabled=busy||unknown||!identityMatched;send.disabled=busy||unknown||!identityMatched;cancel.disabled=busy;
        var deletes=list.querySelectorAll('button[data-sms-delete]');for(var i=0;i<deletes.length;i++)deletes[i].disabled=busy||unknown||!identityMatched;
      }
      function checkIdentity(){
        try{
          var doc=asDocument(w.callProductXML('status1')),model=text(doc,'model'),version=text(doc,'version_num');
          var hardware=typeof w.getHardware_Version==='function'?String(w.getHardware_Version()||''):'';
          identityMatched=/^(?:LV01|MF885)$/i.test(model)&&/^2\.5\.94(?:_|$)/.test(version)&&/(?:^|\s)Ver\.?\s*D(?:$|\s)/i.test(hardware);
          log('identity',identityMatched?'exact MF885/Ver.D/2.5.94':'mismatch');
        }catch(_){identityMatched=false;log('identity:error','mutation locked')}
        if(!identityMatched)setStatus('Read-only mode: exact MF885 / Ver.D / 2.5.94 identity was not proven.',true);
        updateButtons();return identityMatched;
      }
      function mapXml(fields){
        var map=[],index=0;
        for(var i=0;i<fields.length;i++)w.putMapElement(map,fields[i][0],fields[i][1],index++);
        return w.g_objXML.getXMLDocToString(w.g_objXML.createXML(map));
      }
      function readPage(page){
        var xml=mapXml([['RGW/message/flag/message_flag',profile[0]],['RGW/message/get_message/page_number',String(page)]]);
        w.PostSyncXML(xmlName,xml);return parsePage(w.GetSmsXML(xmlName));
      }
      function render(messages){
        list.textContent='';
        if(!messages.length){var empty=w.document.createElement('p');empty.textContent='No messages found.';list.appendChild(empty);return}
        for(var i=0;i<messages.length;i++)(function(message){
          var card=w.document.createElement('article');card.style.cssText='border:1px solid #d0d5dd;border-radius:10px;padding:10px;margin:8px 0';
          var meta=w.document.createElement('div');meta.style.cssText='font-size:12px;color:#667085;margin-bottom:5px';meta.textContent=escapeText(message.from)+' · '+escapeText(message.received);
          var content=w.document.createElement('div');content.style.whiteSpace='pre-wrap';content.textContent=escapeText(message.content);
          var del=w.document.createElement('button');del.type='button';del.textContent='Delete';del.style.marginTop='8px';del.setAttribute('data-sms-delete','');del.disabled=busy||unknown||!identityMatched||!message.id;
          del.addEventListener('click',function(){if(w.confirm('Delete this message?'))deleteOne(message.id)});
          card.appendChild(meta);card.appendChild(content);card.appendChild(del);list.appendChild(card);
        })(messages[i]);
      }
      function loadAll(expectedDeletedId){
        if(busy)return;busy=true;updateButtons();setStatus('Loading messages…');log('read:start',profile[0]);
        try{
          var all=[],seen={},pageFingerprints={},pagesRead=0,reportedPages=null,complete=false,incomplete='';
          for(var page=1;page<=MAX_PAGES;page++){
            var current=readPage(page),fingerprint=current.messages.map(function(message){return [message.id,message.from,message.received,message.content].join('\u001f')}).join('\u001e');
            pagesRead++;if(page===1)reportedPages=current.totalPages;
            if(!current.messages.length){if(reportedPages!==null?page>=reportedPages:page>1)complete=true;else incomplete='an expected page was empty';break}
            if(pageFingerprints[fingerprint]){incomplete='the router repeated a page';break}
            pageFingerprints[fingerprint]=true;
            for(var item=0;item<current.messages.length&&all.length<MAX_MESSAGES;item++){
              var message=current.messages[item],key=message.id||fingerprint+'#'+item;
              if(!seen[key]){seen[key]=true;all.push(message)}
            }
            if(all.length>=MAX_MESSAGES){incomplete='the message limit was reached';break}
            if(reportedPages!==null&&page>=reportedPages){complete=true;break}
            if(reportedPages===null&&current.messages.length<PAGE_SIZE){complete=true;break}
            if(page===MAX_PAGES)incomplete='the page limit was reached';
          }
          render(all);
          if(expectedDeletedId&&!complete){
            unknown=true;setStatus('Deletion readback was incomplete. Reload before any retry.',true);log('delete:unknown',incomplete||'complete history not proven');
          }else if(expectedDeletedId&&all.some(function(message){return message.id===expectedDeletedId})){
            unknown=true;setStatus('The router reported success, but deletion could not be verified. Reload before any retry.',true);log('delete:unknown','message still present');
          }else{
            var summary='Loaded '+all.length+' message'+(all.length===1?'':'s')+'.';
            if(expectedDeletedId)summary='Message deletion verified. '+summary;
            if(!complete)summary+=' History may be incomplete.';
            if(!identityMatched)summary+=' Mutations remain locked: exact device identity was not proven.';
            setStatus(summary,!complete||!identityMatched);log('read:end','pages='+pagesRead+' items='+all.length+' complete='+(complete?'yes':'no'));
          }
        }catch(_){if(expectedDeletedId){unknown=true;setStatus('Deletion readback failed. Reload before any retry.',true);log('delete:unknown','readback failed')}else{setStatus('Message history could not be read.',true);log('read:error','body omitted')}}
        busy=false;updateButtons();
      }
      function lockUnknown(command){unknown=true;busy=false;setStatus('Outcome unknown. Reload this page before any retry.',true);log('mutation:unknown','command='+command+' no replay');updateButtons()}
      function poll(command,attempt,onSuccess){
        var parsed;
        try{parsed=commandStatus(w.getData(xmlName))}catch(_){parsed={pending:true}}
        if(parsed.command===String(command)&&parsed.complete){busy=false;log('mutation:complete','command='+command+' polls='+attempt);updateButtons();onSuccess();return}
        if(parsed.command===String(command)&&!parsed.pending){busy=false;setStatus('The router rejected the command.',true);log('mutation:rejected','command='+command+' status='+parsed.status);updateButtons();return}
        if(attempt>=STATUS_POLLS){lockUnknown(command);return}
        w.setTimeout(function(){poll(command,attempt+1,onSuccess)},1000);
      }
      function postOnce(fields,command,onSuccess){
        if(busy||unknown||!identityMatched)return;busy=true;updateButtons();setStatus('Command '+command+' submitted once; waiting for final status…');log('mutation:post','command='+command+' attempt=1');
        try{w.PostXMLWithResponse(xmlName,mapXml(fields),function(){poll(command,0,onSuccess)})}catch(_){lockUnknown(command)}
      }
      function deleteOne(id){
        if(!/^[A-Za-z0-9_-]{1,64}$/.test(String(id||''))){setStatus('The selected message ID is not safe to submit.',true);return}
        postOnce([
          ['RGW/message/flag/message_flag','DELETE_SMS'],['RGW/message/flag/sms_cmd','6'],
          ['RGW/message/get_message/tags',profile[1]],['RGW/message/get_message/mem_store',profile[2]],
          ['RGW/message/set_message/delete_message_id',String(id)+',']
        ],6,function(){loadAll(String(id))});
      }
      function sendOne(){
        var target=number.value.trim(),message=body.value;
        if(!validatePhone(target)){setStatus('Enter one valid phone number.',true);return}
        var limit=70;
        if(!message||message.length>limit||hasLoneSurrogate(message)){setStatus('Message must contain 1–'+limit+' valid characters.',true);return}
        var encoded;
        try{encoded=String(w.UniEncode(message)||'').toUpperCase()}catch(_){setStatus('Message encoding failed before submission.',true);return}
        if(!/^(?:[0-9A-F]{4})+$/.test(encoded)){setStatus('Message encoding failed before submission.',true);return}
        postOnce([
          ['RGW/message/flag/message_flag','SEND_SMS'],['RGW/message/flag/sms_cmd','4'],
          ['RGW/message/send_save_message/contacts',target],['RGW/message/send_save_message/content',encoded],
          ['RGW/message/send_save_message/encode_type','UNICODE'],['RGW/message/send_save_message/sms_time',w.GetSmsTime()]
        ],4,function(){composer.hidden=true;number.value='';body.value='';count.textContent='0 / 70';setStatus('Message sent.');loadAll()});
      }
      refresh.addEventListener('click',loadAll);newButton.addEventListener('click',function(){if(!busy&&!unknown){composer.hidden=false;number.focus()}});
      cancel.addEventListener('click',function(){composer.hidden=true});send.addEventListener('click',sendOne);
      body.addEventListener('input',function(){body.maxLength=70;count.textContent=body.value.length+' / 70'});
      this.onLoad=function(){checkIdentity();loadAll()};this.onPost=function(){};this.onPostSuccess=function(){};this.setXMLName=function(value){xmlName=value||'message'};
      w.MF885_SMS_R1={id:'0.0-sms-r1',parsePage:parsePage,commandStatus:commandStatus,validatePhone:validatePhone,hasLoneSurrogate:hasLoneSurrogate};
      return this;
    };
  }
  w.MF885_SMS_R1_CORE={id:'0.0-sms-r1',parsePage:parsePage,commandStatus:commandStatus,validatePhone:validatePhone,hasLoneSurrogate:hasLoneSurrogate,install:install};
  install(w.jQuery);
})(window);
