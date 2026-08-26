/* MF885 Community R2.1 SMS read-delete-send 0.2.1-community-r2 */
(function(w){
  'use strict';
  var PROFILES={
    mDeviceInbox:{flag:'GET_RCV_SMS_LOCAL',tags:'12',store:'1',label:'Device inbox',deletable:true},
    mDeviceOutbox:{flag:'GET_SENT_SMS_LOCAL',tags:'2',store:'1',label:'Sent messages',deletable:false},
    mSimSms:{flag:'GET_SIM_SMS',tags:'',store:'0',label:'SIM messages',deletable:false},
    mDrafts:{flag:'GET_DRAFT_SMS',tags:'2',store:'2',label:'Drafts',deletable:false}
  };
  var MAX_PAGES=20,MAX_MESSAGES=200,PAGE_SIZE=10,STATUS_POLLS=10,POST_CALLBACK_TIMEOUT_MS=30000,MAX_UCS2_UNITS=268;
  function mutationSession(){
    var state=w.MF885_COMMUNITY_R21_MUTATION_SESSION;
    if(!state||state.version!==1||state.document!==w.document){state={version:1,document:w.document,busy:false,locked:false,message:'',update:null};w.MF885_COMMUNITY_R21_MUTATION_SESSION=state}
    return state;
  }

  function text(node,name){var list=node&&node.getElementsByTagName?node.getElementsByTagName(name):[];return list.length?String(list[0].textContent||'').trim():''}
  function asDocument(value){
    var doc=value&&value.getElementsByTagName?value:null;
    try{doc=doc||new w.DOMParser().parseFromString(String(value||''),'text/xml')}catch(_){return null}
    return doc&&doc.getElementsByTagName('parsererror').length===0?doc:null;
  }
  function decode(value){try{return typeof w.UniDecode==='function'?w.UniDecode(value):value}catch(_){return value}}
  function commandStatus(value){
    var doc=asDocument(value),cmd=text(doc,'sms_cmd'),status=text(doc,'sms_cmd_status_result');
    return {command:cmd,status:status,complete:status==='3',pending:status===''||status==='0'||status==='1'};
  }
  function parsePage(value){
    var doc=asDocument(value);if(!doc)throw new Error('invalid SMS XML');
    var containers=doc.getElementsByTagName('get_message');
    if(containers.length!==1||containers[0].getElementsByTagName('message_list').length!==1)throw new Error('unexpected SMS XML schema');
    var items=containers[0].getElementsByTagName('Item'),messages=[];
    for(var i=0;i<items.length;i++){var from=String(decode(text(items[i],'from'))||'').replace(/^;/,'').replace(/;.*$/,''),recipient=String(decode(text(items[i],'contacts')||text(items[i],'to')||text(items[i],'from'))||'').replace(/^;/,'').replace(/;.*$/,'');messages.push({
      id:text(items[i],'index'),from:from,recipient:recipient,
      content:String(decode(text(items[i],'subject')||text(items[i],'content'))||''),
      received:text(items[i],'received'),status:text(items[i],'status')
    })}
    var pages=parseInt(text(containers[0],'total_number'),10);
    return {messages:messages,totalPages:Number.isFinite(pages)&&pages>0?pages:null};
  }
  function segments(value){var units=String(value||'').length;return units===0?0:(units<=70?1:Math.ceil(units/67))}
  function validBody(value){
    value=String(value||'');
    if(!value.length||value.length>MAX_UCS2_UNITS||segments(value)>4)return false;
    for(var i=0;i<value.length;i++){var code=value.charCodeAt(i);if((code>=0xd800&&code<=0xdfff)||code===0||(code>=0x7f&&code<=0x9f)||(code<0x20&&code!==10&&code!==13))return false}
    return true;
  }
  function validPhone(value){return /^\+?[0-9]{3,15}$/.test(String(value||''))}
  function install($){
    if(!$||!$.fn)return;
    $.fn.objSms=function(menuName){
      var root=w.document.getElementById('Content'),xmlName='message',profile=PROFILES[menuName]||PROFILES.mDeviceInbox;
      if(!root)throw new Error('SMS content root is missing');
      root.innerHTML=w.callProductHTML('html/SMS/SMS.html');
      var list=w.document.getElementById('mfSmsList'),status=w.document.getElementById('mfSmsStatus'),refresh=w.document.getElementById('mfSmsRefresh');
      var folder=w.document.getElementById('mfSmsFolder'),newButton=w.document.getElementById('mfSmsNew'),composer=w.document.getElementById('mfSmsComposer');
      var number=w.document.getElementById('mfSmsNumber'),body=w.document.getElementById('mfSmsBody'),count=w.document.getElementById('mfSmsCount');
      var review=w.document.getElementById('mfSmsReview'),cancel=w.document.getElementById('mfSmsCancel'),confirmBox=w.document.getElementById('mfSmsConfirm');
      var send=w.document.getElementById('mfSmsSend'),back=w.document.getElementById('mfSmsBack'),reviewNumber=w.document.getElementById('mfSmsReviewNumber');
      var reviewBody=w.document.getElementById('mfSmsReviewBody'),reviewSegments=w.document.getElementById('mfSmsReviewSegments');
      var session=mutationSession(),busy=false,identityMatched=false,historyComplete=false,currentMessages=[],reviewedTarget=null,reviewedBody=null;
      folder.textContent=profile.label;

      function setStatus(value,error){status.textContent=value;status.style.color=error?'#b42318':'#344054'}
      function notifySession(){if(typeof session.update==='function')try{session.update()}catch(_){}}
      function releaseMutation(){session.busy=false;notifySession()}
      function updateButtons(){
        var writeBusy=busy||session.busy;refresh.disabled=writeBusy;newButton.disabled=writeBusy||session.locked||!identityMatched;review.disabled=writeBusy||session.locked||!identityMatched;
        send.disabled=writeBusy||session.locked||!identityMatched;cancel.disabled=writeBusy;back.disabled=writeBusy;
        var deletes=list.querySelectorAll('button[data-sms-delete]');
        for(var i=0;i<deletes.length;i++)deletes[i].disabled=writeBusy||session.locked||!identityMatched||!historyComplete||!profile.deletable||deletes[i].getAttribute('data-sms-safe')!=='1';
        if(session.locked&&session.message&&!busy)setStatus(session.message,true);
      }
      session.update=updateButtons;
      function checkIdentity(){
        try{
          var doc=asDocument(w.callProductXML('status1')),model=text(doc,'model'),version=text(doc,'version_num');
          var hardware=typeof w.getHardware_Version==='function'?String(w.getHardware_Version()||''):'';
          identityMatched=/^(?:LV01|MF885)$/i.test(model)&&/^2\.5\.94(?:_|$)/.test(version)&&/(?:^|\s)Ver\.?\s*D(?:$|\s)/i.test(hardware);
        }catch(_){identityMatched=false}
        if(!identityMatched)setStatus('Read-only mode: exact MF885 / Ver.D / 2.5.94 identity was not proven.',true);
        updateButtons();return identityMatched;
      }
      function mapXml(fields){
        var map=[],index=0;for(var i=0;i<fields.length;i++)w.putMapElement(map,fields[i][0],fields[i][1],index++);
        return w.g_objXML.getXMLDocToString(w.g_objXML.createXML(map));
      }
      function readPage(targetProfile,page){
        var xml=mapXml([['RGW/message/flag/message_flag',targetProfile.flag],['RGW/message/get_message/page_number',String(page)]]);
        w.PostSyncXML(xmlName,xml);return parsePage(w.GetSmsXML(xmlName));
      }
      function readHistory(targetProfile){
        var all=[],seenIds={},pageFingerprints={},reportedPages=null,complete=false,incomplete='',safe=true;
        for(var page=1;page<=MAX_PAGES;page++){
          var current=readPage(targetProfile,page),fingerprint=current.messages.map(function(message){return [message.id,message.from,message.received,message.content].join('\u001f')}).join('\u001e');
          if(page===1)reportedPages=current.totalPages;else if(current.totalPages!==null&&reportedPages!==current.totalPages){incomplete='the router changed its page count';break}
          if(!current.messages.length){if((page===1&&reportedPages===null)||(reportedPages!==null&&page>=reportedPages)||(reportedPages===null&&page>1))complete=true;else incomplete='an expected page was empty';break}
          if(pageFingerprints[fingerprint]){incomplete='the router repeated a page';break}pageFingerprints[fingerprint]=true;
          for(var item=0;item<current.messages.length&&all.length<MAX_MESSAGES;item++){
            var message=current.messages[item],safeId=/^[A-Za-z0-9_-]{1,64}$/.test(String(message.id||''));
            if(!safeId||seenIds[message.id])safe=false;if(safeId)seenIds[message.id]=true;all.push(message);
          }
          if(all.length>=MAX_MESSAGES){incomplete='the message limit was reached';break}
          if(reportedPages!==null&&page>=reportedPages){complete=true;break}
          if(reportedPages===null&&current.messages.length<PAGE_SIZE){complete=true;break}
          if(page===MAX_PAGES)incomplete='the page limit was reached';
        }
        if(!safe){complete=false;incomplete=incomplete||'message identifiers were missing, unsafe, or repeated'}
        return {messages:all,complete:complete,warning:incomplete};
      }
      function render(messages){
        var idCounts={};currentMessages=messages.slice();for(var n=0;n<messages.length;n++)if(messages[n].id)idCounts[messages[n].id]=(idCounts[messages[n].id]||0)+1;
        list.textContent='';if(!messages.length){var empty=w.document.createElement('p');empty.textContent='No messages found.';list.appendChild(empty);return}
        for(var i=0;i<messages.length;i++)(function(message){
          var card=w.document.createElement('details');card.style.cssText='border:1px solid #d0d5dd;border-radius:10px;padding:10px;margin:8px 0';
          var summary=w.document.createElement('summary');summary.style.cursor='pointer';var sender=w.document.createElement('strong');sender.textContent=message.from||'Unknown sender';
          var received=w.document.createElement('span');received.style.cssText='font-size:12px;color:#667085;margin-left:8px';received.textContent=message.received;
          var content=w.document.createElement('div');content.style.cssText='white-space:pre-wrap;margin-top:10px';content.textContent=message.content;
          summary.appendChild(sender);summary.appendChild(received);card.appendChild(summary);card.appendChild(content);
          if(profile.deletable){
            var del=w.document.createElement('button');del.type='button';del.textContent='Delete';del.style.marginTop='10px';del.setAttribute('data-sms-delete','');
            var safe=/^[A-Za-z0-9_-]{1,64}$/.test(String(message.id||''))&&idCounts[message.id]===1;del.setAttribute('data-sms-safe',safe?'1':'0');
            del.addEventListener('click',function(event){event.preventDefault();if(w.confirm('Delete this SMS from MF885? This cannot be undone.'))deleteOne(message.id)});card.appendChild(del);
          }
          list.appendChild(card);
        })(messages[i]);
      }
      function loadAll(expectedDeletedId,releaseAfterReadback){
        if(busy||(session.busy&&!releaseAfterReadback)){updateButtons();return}busy=true;historyComplete=false;updateButtons();setStatus('Loading messages…');
        try{
          var result=readHistory(profile);historyComplete=result.complete;render(result.messages);
          if(expectedDeletedId&&!result.complete){lockUnknown('Deletion readback was incomplete. The outcome is unknown; reload this page before any SMS write.');return}
          if(expectedDeletedId&&result.messages.some(function(message){return message.id===expectedDeletedId})){lockUnknown('Deletion could not be verified. The outcome is unknown; reload this page before any SMS write.');return}
          var summary='Loaded '+result.messages.length+' message'+(result.messages.length===1?'':'s')+'.';
          if(expectedDeletedId)summary='Message deletion verified. '+summary;if(!result.complete)summary+=' History may be incomplete; deletion is disabled.';
          if(!profile.deletable)summary+=' This folder is read-only.';if(!identityMatched)summary+=' Mutations remain locked: exact device identity was not proven.';
          setStatus(summary,!result.complete||!identityMatched);
        }catch(_){historyComplete=false;render([]);if(expectedDeletedId){lockUnknown('Deletion readback failed. The outcome is unknown; reload this page before any SMS write is attempted again.');return}setStatus('Message history could not be read. Read-only refresh remains available.',true)}
        busy=false;if(releaseAfterReadback)releaseMutation();updateButtons();
      }
      function lockUnknown(message){session.locked=true;session.busy=false;busy=false;session.message=message||'Outcome unknown. Reload this page before any SMS write is attempted again.';setStatus(session.message,true);notifySession();updateButtons()}
      function poll(command,attempt,onComplete,onReject){
        var parsed;try{parsed=commandStatus(w.getData(xmlName))}catch(_){parsed={pending:true,command:'',status:''}}
        if(parsed.command===String(command)&&parsed.complete){busy=false;updateButtons();onComplete();return}
        if(parsed.command===String(command)&&parsed.status&&parsed.status!=='1'&&parsed.status!=='0'){busy=false;releaseMutation();updateButtons();onReject(parsed.status);return}
        if(attempt>=STATUS_POLLS){lockUnknown();return}
        w.setTimeout(function(){poll(command,attempt+1,onComplete,onReject)},1000);
      }
      function postOnce(fields,command,onComplete,onReject){
        if(busy||session.busy||session.locked||!identityMatched)return;busy=true;session.busy=true;notifySession();updateButtons();
        var waiting=true,timer=w.setTimeout(function(){if(waiting){waiting=false;lockUnknown()}},POST_CALLBACK_TIMEOUT_MS);
        try{w.PostXMLWithResponse(xmlName,mapXml(fields),function(){if(!waiting)return;waiting=false;if(typeof w.clearTimeout==='function')w.clearTimeout(timer);poll(command,0,onComplete,onReject)})}
        catch(_){waiting=false;if(typeof w.clearTimeout==='function')w.clearTimeout(timer);lockUnknown()}
      }
      function deleteOne(id){
        if(busy||session.busy||session.locked||!identityMatched||!profile.deletable||!historyComplete)return;
        if(!/^[A-Za-z0-9_-]{1,64}$/.test(String(id||''))){setStatus('The selected message ID is not safe to submit.',true);return}
        setStatus('Deletion submitted once; waiting for final status…');postOnce([
          ['RGW/message/flag/message_flag','DELETE_SMS'],['RGW/message/flag/sms_cmd','6'],['RGW/message/get_message/tags',profile.tags],
          ['RGW/message/get_message/mem_store',profile.store],['RGW/message/set_message/delete_message_id',String(id)+',']
        ],6,function(){loadAll(String(id),true)},function(value){setStatus('The router rejected deletion (status '+value+'). No retry was sent.',true)});
      }
      function updateCount(){var value=String(body.value||''),parts=segments(value);count.textContent=value.length+' / '+MAX_UCS2_UNITS+' · '+parts+' of 4 UCS-2 segment'+(parts===1?'':'s')}
      function openComposer(){if(busy||session.busy||session.locked||!identityMatched)return;reviewedTarget=null;reviewedBody=null;confirmBox.hidden=true;composer.hidden=false;number.focus();updateCount()}
      function reviewMessage(){
        var target=String(number.value||'').trim(),message=String(body.value||'');
        if(!validPhone(target)){setStatus('Use 3–15 digits with an optional leading +. Only one recipient is allowed.',true);return}
        if(!validBody(message)){setStatus('Use 1–268 UCS-2 characters (maximum four segments); control characters and emoji are not accepted.',true);return}
        reviewedTarget=target;reviewedBody=message;reviewNumber.textContent=target;reviewBody.textContent=message;reviewSegments.textContent=segments(message)+' UCS-2 segment'+(segments(message)===1?'':'s');
        composer.hidden=true;confirmBox.hidden=false;setStatus('Review the exact recipient and text. Nothing has been sent yet.');
      }
      function sendOne(){
        if(busy||session.busy||session.locked||!identityMatched||confirmBox.hidden)return;
        var target=String(number.value||'').trim(),message=String(body.value||'');if(target!==reviewedTarget||message!==reviewedBody||!validPhone(target)||!validBody(message)){reviewedTarget=null;reviewedBody=null;confirmBox.hidden=true;composer.hidden=false;setStatus('The draft changed and must be reviewed again.',true);return}
        var encoded;try{encoded=String(w.UniEncode(message)||'').toUpperCase()}catch(_){setStatus('Message encoding failed before submission.',true);return}
        if(!/^(?:[0-9A-F]{4})+$/.test(encoded)||encoded.length!==message.length*4){setStatus('Message encoding failed before submission.',true);return}
        var before=null;try{before=readHistory(PROFILES.mDeviceOutbox)}catch(_){lockUnknown('Sent-folder baseline could not be read. No SMS was submitted; reload this page before any SMS write is attempted.');return}
        if(!before.complete){lockUnknown('Sent-folder baseline was incomplete. No SMS was submitted; reload this page before any SMS write is attempted.');return}
        setStatus('Send submitted once; waiting for the router command status…');
        postOnce([
          ['RGW/message/flag/message_flag','SEND_SMS'],['RGW/message/flag/sms_cmd','4'],['RGW/message/send_save_message/contacts',target],
          ['RGW/message/send_save_message/content',encoded],['RGW/message/send_save_message/encode_type','UNICODE'],['RGW/message/send_save_message/sms_time',w.GetSmsTime()]
        ],4,function(){
          var recorded=false,after=null;try{after=readHistory(PROFILES.mDeviceOutbox)}catch(_){lockUnknown('The router accepted the send command, but Sent-folder verification failed. Delivery is not proven. Reload before any SMS write.');return}
          if(!after.complete){lockUnknown('The router accepted the send command, but Sent-folder verification was incomplete. Delivery is not proven. Reload before any SMS write.');return}
          var known={};for(var i=0;i<before.messages.length;i++)known[before.messages[i].id]=true;
          for(var j=0;j<after.messages.length;j++){var item=after.messages[j];if(item.id&&!known[item.id]&&item.recipient===target&&item.content===message){recorded=true;break}}
          if(!recorded){lockUnknown('The router accepted the send command, but no matching new Sent record was found. Delivery is not proven. Reload before any SMS write.');return}
          releaseMutation();reviewedTarget=null;reviewedBody=null;
          confirmBox.hidden=true;composer.hidden=true;number.value='';body.value='';updateCount();
          setStatus('Recorded in Sent messages; delivery is not proven.');
        },function(value){setStatus('The router rejected sending (status '+value+'). No retry was sent.',true)});
      }

      refresh.addEventListener('click',function(){loadAll()});newButton.addEventListener('click',openComposer);review.addEventListener('click',reviewMessage);
      cancel.addEventListener('click',function(){reviewedTarget=null;reviewedBody=null;composer.hidden=true});back.addEventListener('click',function(){reviewedTarget=null;reviewedBody=null;confirmBox.hidden=true;composer.hidden=false});
      send.addEventListener('click',sendOne);body.addEventListener('input',updateCount);
      this.onLoad=function(){checkIdentity();loadAll()};this.onPost=function(){};this.onPostSuccess=function(){};this.setXMLName=function(value){xmlName=value||'message'};
      w.MF885_COMMUNITY_R21_SMS={id:'0.2.1-community-r2',parsePage:parsePage,commandStatus:commandStatus,segments:segments,validBody:validBody,validPhone:validPhone,isMutationLocked:function(){return session.locked},isMutationBusy:function(){return session.busy}};
      return this;
    };
  }
  w.MF885_COMMUNITY_R21_SMS_CORE={id:'0.2.1-community-r2',parsePage:parsePage,commandStatus:commandStatus,segments:segments,validBody:validBody,validPhone:validPhone,install:install};
  install(w.jQuery);
})(window);
