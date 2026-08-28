/* MF885 Community R2.3 SMS read-delete-send 0.2.3-community-r2 */
(function(w){
  'use strict';
  var PROFILES={
    mDeviceInbox:{flag:'GET_RCV_SMS_LOCAL',tags:'12',store:'1',label:'Device inbox',deletable:true},
    mDeviceOutbox:{flag:'GET_SENT_SMS_LOCAL',tags:'2',store:'1',label:'Sent messages',deletable:false},
    mSimSms:{flag:'GET_SIM_SMS',tags:'',store:'0',label:'SIM messages',deletable:false},
    mDrafts:{flag:'GET_DRAFT_SMS',tags:'2',store:'2',label:'Drafts',deletable:false}
  };
  var MAX_PAGES=20,MAX_MESSAGES=200,ROUTER_PAGE_SIZE=10,DISPLAY_PAGE_SIZE=10,STATUS_POLLS=10,POST_CALLBACK_TIMEOUT_MS=30000,MAX_UCS2_UNITS=268;
  var WATCH_KEY='mf885.community.r23.sms-watch.v1',WATCH_INTERVAL_MS=60000,WATCH_FAILURE_LIMIT=3;
  function mutationSession(){
    var state=w.MF885_COMMUNITY_R23_MUTATION_SESSION;
    if(!state||state.version!==1||state.document!==w.document){state={version:1,document:w.document,busy:false,locked:false,message:'',update:null};w.MF885_COMMUNITY_R23_MUTATION_SESSION=state}
    return state;
  }

  function opaqueRecordHash(value){
    value=String(value||'');var first=2166136261,second=5381;
    for(var index=0;index<value.length;index++){
      var code=value.charCodeAt(index);first^=code;first+=(first<<1)+(first<<4)+(first<<7)+(first<<8)+(first<<24);second=((second<<5)+second)^code;
    }
    return ('00000000'+(first>>>0).toString(16)).slice(-8)+('00000000'+(second>>>0).toString(16)).slice(-8);
  }
  function safeWatchTokens(messages){
    var ids={},tokens={},list=[];
    for(var i=0;i<messages.length;i++){
      var id=String(messages[i]&&messages[i].id||'');
      if(!/^[A-Za-z0-9_-]{1,64}$/.test(id)||ids[id])return null;
      ids[id]=true;
      var token=opaqueRecordHash([id,messages[i].from,messages[i].received,messages[i].content].join('\u001f'));
      if(tokens[token])return null;tokens[token]=true;list.push(token);
    }
    return {map:tokens,list:list};
  }
  function pageFingerprint(page){
    var tokens=safeWatchTokens(page&&page.messages||[]);
    if(!tokens)return null;
    return String(page.totalPages===null?'?':page.totalPages)+'|'+tokens.list.join(',');
  }
  function watchSession(){
    var existing=w.MF885_COMMUNITY_R23_SMS_WATCH_SESSION;
    if(existing&&existing.version===1&&existing.document===w.document)return existing;
    var state={version:1,document:w.document,enabled:false,timer:null,generation:0,inFlight:false,failures:0,baseline:null,firstFingerprint:null,reader:null,input:null,hint:null,panel:null,noticeCount:0,permissionRequested:false,baseTitle:String(w.document.title||'MF885')};
    try{state.enabled=!!(w.sessionStorage&&w.sessionStorage.getItem(WATCH_KEY)==='1')}catch(_){state.enabled=false}
    function setHint(value,error){
      if(state.hint){state.hint.textContent=value;state.hint.style.color=error?'#b42318':'#667085'}
    }
    function activeHint(){
      if(w.isSecureContext!==true||!w.Notification)return 'On · checks once a minute. Browser alerts are unavailable on this HTTP address; the in-page badge still works.';
      if(w.Notification.permission==='denied')return 'On · checks once a minute. Browser alerts are blocked; the in-page badge still works.';
      return 'On · checks once a minute while this tab stays open.';
    }
    function syncUi(){if(state.input)state.input.checked=state.enabled}
    function cancelTimer(){if(state.timer!==null&&typeof w.clearTimeout==='function')w.clearTimeout(state.timer);state.timer=null}
    function persist(value){
      try{
        if(!w.sessionStorage)return false;
        if(value)w.sessionStorage.setItem(WATCH_KEY,'1');else w.sessionStorage.removeItem(WATCH_KEY);
        return true;
      }catch(_){return false}
    }
    function clearNotice(){
      state.noticeCount=0;w.document.title=state.baseTitle;
      var prior=w.document.getElementById('mfSmsWatchToast');if(prior&&prior.parentNode)prior.parentNode.removeChild(prior);
    }
    function showNotice(count){
      state.noticeCount=count;w.document.title='('+count+') '+state.baseTitle;
      var toast=w.document.getElementById('mfSmsWatchToast');
      if(!toast){toast=w.document.createElement('div');toast.id='mfSmsWatchToast';toast.className='mfSmsWatchToast';w.document.body.appendChild(toast)}
      toast.textContent=count+' new router message'+(count===1?'':'s')+'. Open Messages and press Refresh.';
      if(w.isSecureContext===true&&w.Notification&&w.Notification.permission==='granted'){
        try{new w.Notification('New router messages: '+count)}catch(_){}
      }
    }
    function requestPermissionFromGesture(){
      if(w.isSecureContext!==true||!w.Notification){setHint('Browser alerts are unavailable on this HTTP address; the in-page badge still works.');return}
      if(w.Notification.permission==='denied'){setHint('Browser alerts are blocked; the in-page badge still works.');return}
      if(state.permissionRequested||w.Notification.permission!=='default'||typeof w.Notification.requestPermission!=='function')return;
      state.permissionRequested=true;
      try{
        var answer=w.Notification.requestPermission();
        if(answer&&typeof answer.then==='function')answer.then(function(value){if(value==='denied')setHint('Browser alerts are blocked; the in-page badge still works.')},function(){});
      }catch(_){}
    }
    function acceptBaseline(result){
      if(!result||!result.complete)return false;
      var tokens=safeWatchTokens(result.messages||[]);if(!tokens||!result.firstFingerprint)return false;
      state.baseline=tokens.map;state.firstFingerprint=result.firstFingerprint;state.failures=0;return true;
    }
    function schedule(){
      cancelTimer();if(!state.enabled||!state.reader)return;
      var generation=state.generation;
      state.timer=w.setTimeout(function(){state.timer=null;if(generation!==state.generation)return;runCycle()},WATCH_INTERVAL_MS);
    }
    function failCycle(message){
      state.failures++;
      if(state.failures>=WATCH_FAILURE_LIMIT){state.enabled=false;state.generation++;cancelTimer();persist(false);syncUi();setHint('Paused after repeated incomplete reads. Turn it on to try again.',true);return}
      setHint(message||'Check incomplete; the baseline was not changed.',true);
    }
    function foregroundBlocked(){
      var mutation=mutationSession();
      return mutation.busy||mutation.locked||!state.reader||state.reader.busy();
    }
    function runCycle(){
      if(!state.enabled||state.inFlight||!state.reader)return;
      if(foregroundBlocked()){setHint('Waiting for the current Messages operation to finish.');schedule();return}
      state.inFlight=true;
      try{
        var first=state.reader.readFirst(),fingerprint=pageFingerprint(first);
        if(!fingerprint)throw new Error('unsafe first page');
        if(state.baseline===null||fingerprint!==state.firstFingerprint){
          var full=state.reader.readFull(),tokens=full&&full.complete?safeWatchTokens(full.messages||[]):null;
          if(!tokens||!full.firstFingerprint)throw new Error('incomplete history');
          var count=0;if(state.baseline!==null)for(var token in tokens.map)if(Object.prototype.hasOwnProperty.call(tokens.map,token)&&!state.baseline[token])count++;
          state.baseline=tokens.map;state.firstFingerprint=full.firstFingerprint;
          if(count>0)showNotice(count);
        }
        state.failures=0;setHint(activeHint());
      }catch(_){failCycle('Check incomplete; the baseline was not changed.')}
      state.inFlight=false;schedule();
    }
    function enable(fromGesture){
      if(!persist(true)){state.enabled=false;syncUi();setHint('Automatic checks are unavailable in this browser.',true);return}
      state.enabled=true;state.generation++;state.failures=0;syncUi();
      if(fromGesture)requestPermissionFromGesture();
      if(foregroundBlocked()){setHint('Waiting for the current Messages operation to finish.');schedule();return}
      state.inFlight=true;
      try{
        var current=state.reader.current();
        if(!acceptBaseline(current)&&!acceptBaseline(state.reader.readFull()))throw new Error('baseline incomplete');
        setHint(activeHint());
      }catch(_){state.inFlight=false;failCycle('Baseline incomplete; nothing was announced.');schedule();return}
      state.inFlight=false;schedule();
    }
    function disable(clearPreference){
      state.enabled=false;state.generation++;state.inFlight=false;cancelTimer();state.baseline=null;state.firstFingerprint=null;state.failures=0;
      if(clearPreference!==false)persist(false);syncUi();setHint('Off');
    }
    function attach(reader,input,hint,panel){
      state.reader=reader;state.input=input;state.hint=hint;state.panel=panel;syncUi();
      if(state.enabled){
        var current=reader.current();
        if(current&&current.complete)acceptBaseline(current);
        setHint(activeHint());schedule();
      }else setHint('Off');
    }
    function observeVisible(result){
      if(!state.enabled||!acceptBaseline(result))return;
      clearNotice();setHint(activeHint());schedule();
    }
    state.attach=attach;state.observeVisible=observeVisible;state.enable=enable;state.disable=disable;state.runCycle=runCycle;state.clearNotice=clearNotice;state.syncUi=syncUi;
    w.MF885_COMMUNITY_R23_SMS_WATCH_SESSION=state;
    if(typeof w.addEventListener==='function'){
      w.addEventListener('pagehide',function(){state.generation++;state.inFlight=false;cancelTimer()});
      w.addEventListener('pageshow',function(){if(state.enabled)schedule()});
    }
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
    for(var i=0;i<items.length;i++){
      var from=String(decode(text(items[i],'from'))||'').replace(/^;/,'').replace(/;.*$/,'');
      var recipient=String(decode(text(items[i],'contacts')||text(items[i],'to')||text(items[i],'from'))||'').replace(/^;/,'').replace(/;.*$/,'');
      messages.push({id:text(items[i],'index'),from:from,recipient:recipient,content:String(decode(text(items[i],'subject')||text(items[i],'content'))||''),received:text(items[i],'received'),status:text(items[i],'status')});
    }
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
      root.innerHTML=w.callProductHTML('html/Community/r23sms.html');
      if(w.MF885CommunityR23&&typeof w.MF885CommunityR23.markRoot==='function')w.MF885CommunityR23.markRoot();
      var list=w.document.getElementById('mfSmsList'),status=w.document.getElementById('mfSmsStatus'),refresh=w.document.getElementById('mfSmsRefresh');
      var folder=w.document.getElementById('mfSmsFolder'),newButton=w.document.getElementById('mfSmsNew'),composer=w.document.getElementById('mfSmsComposer');
      var number=w.document.getElementById('mfSmsNumber'),body=w.document.getElementById('mfSmsBody'),count=w.document.getElementById('mfSmsCount');
      var send=w.document.getElementById('mfSmsSend'),cancel=w.document.getElementById('mfSmsCancel'),pager=w.document.getElementById('mfSmsPager');
      var previous=w.document.getElementById('mfSmsPrevious'),next=w.document.getElementById('mfSmsNext'),pageLabel=w.document.getElementById('mfSmsPage');
      var watchPanel=w.document.getElementById('mfSmsWatchPanel'),watchInput=w.document.getElementById('mfSmsAutoCheck'),watchHint=w.document.getElementById('mfSmsWatchHint');
      var session=mutationSession(),watcher=watchSession(),busy=false,identityMatched=false,historyComplete=false,currentMessages=[],idCounts={},displayPage=1,lastHistoryResult=null;
      folder.textContent=profile.label;
      if(!profile.deletable)watchPanel.hidden=true;

      function setStatus(value,error){status.textContent=value;status.style.color=error?'#b42318':'#344054'}
      function notifySession(){if(typeof session.update==='function')try{session.update()}catch(_){} }
      function releaseMutation(){session.busy=false;notifySession()}
      function updateButtons(){
        var writeBusy=busy||session.busy;
        refresh.disabled=writeBusy;
        newButton.disabled=writeBusy||session.locked||!identityMatched;
        send.disabled=writeBusy||session.locked||!identityMatched;
        cancel.disabled=writeBusy;
        number.disabled=writeBusy;body.disabled=writeBusy;
        previous.disabled=displayPage<=1;
        next.disabled=displayPage>=Math.max(1,Math.ceil(currentMessages.length/DISPLAY_PAGE_SIZE));
        var deletes=list.querySelectorAll('button[data-sms-delete]');
        for(var i=0;i<deletes.length;i++)deletes[i].disabled=writeBusy||session.locked||!identityMatched||!historyComplete||!profile.deletable||deletes[i].getAttribute('data-sms-safe')!=='1';
        if(session.locked&&session.message&&!busy)setStatus(session.message,true);
      }
      session.update=updateButtons;
      function checkIdentity(){
        try{identityMatched=!!(w.MF885CommunityR23&&w.MF885CommunityR23.exactStatus1Identity(w.callProductXML('status1')))}catch(_){identityMatched=false}
        if(!identityMatched)setStatus('Read-only: exact device identity was not proven.',true);
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
          if(reportedPages===null&&current.messages.length<ROUTER_PAGE_SIZE){complete=true;break}
          if(page===MAX_PAGES)incomplete='the page limit was reached';
        }
        if(!safe){complete=false;incomplete=incomplete||'message identifiers were missing, unsafe, or repeated'}
        return {messages:all,complete:complete,warning:incomplete,firstFingerprint:all.length||complete?pageFingerprint({messages:all.slice(0,ROUTER_PAGE_SIZE),totalPages:reportedPages}):null};
      }
      function renderPage(){
        var pages=Math.max(1,Math.ceil(currentMessages.length/DISPLAY_PAGE_SIZE));
        if(displayPage>pages)displayPage=pages;if(displayPage<1)displayPage=1;
        list.textContent='';pager.hidden=currentMessages.length<=DISPLAY_PAGE_SIZE;pageLabel.textContent='Page '+displayPage+' of '+pages;
        if(!currentMessages.length){var empty=w.document.createElement('p');empty.textContent='No messages.';list.appendChild(empty);updateButtons();return}
        var start=(displayPage-1)*DISPLAY_PAGE_SIZE,end=Math.min(start+DISPLAY_PAGE_SIZE,currentMessages.length);
        for(var i=start;i<end;i++)(function(message){
          var card=w.document.createElement('article');card.className='mfCommunityMessage';
          var header=w.document.createElement('div');header.className='mfCommunityMessageHeader';
          var sender=w.document.createElement('strong');sender.className='mfCommunityMessageSender';sender.textContent=message.from||'Unknown sender';
          var received=w.document.createElement('span');received.className='mfCommunityMessageDate';received.textContent=message.received||'Date not returned';
          var content=w.document.createElement('div');content.className='mfCommunityMessageBody';content.textContent=message.content;
          header.appendChild(sender);header.appendChild(received);card.appendChild(header);card.appendChild(content);
          if(profile.deletable){
            var del=w.document.createElement('button');del.type='button';del.textContent='Delete';del.className='mfCommunityButton mfCommunityButtonDanger';del.setAttribute('data-sms-delete','');
            var safe=/^[A-Za-z0-9_-]{1,64}$/.test(String(message.id||''))&&idCounts[message.id]===1;del.setAttribute('data-sms-safe',safe?'1':'0');
            del.addEventListener('click',function(){if(w.confirm('Delete this SMS? This cannot be undone.'))deleteOne(message.id)});card.appendChild(del);
          }
          list.appendChild(card);
        })(currentMessages[i]);
        updateButtons();
      }
      function render(messages){
        currentMessages=messages.slice();idCounts={};
        for(var n=0;n<currentMessages.length;n++)if(currentMessages[n].id)idCounts[currentMessages[n].id]=(idCounts[currentMessages[n].id]||0)+1;
        renderPage();
      }
      function loadAll(expectedDeletedId,releaseAfterReadback){
        if(busy||(session.busy&&!releaseAfterReadback)){updateButtons();return}
        busy=true;historyComplete=false;updateButtons();setStatus('Loading…');
        try{
          var result=readHistory(profile);lastHistoryResult=result;historyComplete=result.complete;render(result.messages);
          if(expectedDeletedId&&!result.complete){lockUnknown('Deletion readback was incomplete. Outcome unknown; reload before another SMS write.');return}
          if(expectedDeletedId&&result.messages.some(function(message){return message.id===expectedDeletedId})){lockUnknown('Deletion was not verified. Outcome unknown; reload before another SMS write.');return}
          var summary=result.messages.length+' message'+(result.messages.length===1?'':'s')+'.';
          if(expectedDeletedId)summary='Deleted. '+summary;
          if(!result.complete)summary+=' History incomplete; deletion disabled.';
          if(!profile.deletable)summary+=' Read-only folder.';
          if(!identityMatched)summary+=' Writes locked.';
          setStatus(summary,!result.complete||!identityMatched);
          if(profile.deletable)watcher.observeVisible(result);
        }catch(_){
          lastHistoryResult=null;historyComplete=false;render([]);
          if(expectedDeletedId){lockUnknown('Deletion readback failed. Outcome unknown; reload before another SMS write.');return}
          setStatus('Messages unavailable. Refresh remains available.',true);
        }
        busy=false;if(releaseAfterReadback)releaseMutation();updateButtons();
      }
      function lockUnknown(message){
        session.locked=true;session.busy=false;busy=false;session.message=message||'Outcome unknown. Reload before another SMS write.';
        setStatus(session.message,true);notifySession();updateButtons();
      }
      function poll(command,attempt,onComplete,onReject){
        var parsed;try{parsed=commandStatus(w.getData(xmlName))}catch(_){parsed={pending:true,command:'',status:''}}
        if(parsed.command===String(command)&&parsed.complete){busy=false;updateButtons();onComplete();return}
        if(parsed.command===String(command)&&parsed.status&&parsed.status!=='1'&&parsed.status!=='0'){busy=false;releaseMutation();updateButtons();onReject(parsed.status);return}
        if(attempt>=STATUS_POLLS){lockUnknown();return}
        w.setTimeout(function(){poll(command,attempt+1,onComplete,onReject)},1000);
      }
      function postOnce(fields,command,onComplete,onReject){
        if(busy||session.busy||session.locked||!identityMatched)return;
        busy=true;session.busy=true;notifySession();updateButtons();
        var waiting=true,timer=w.setTimeout(function(){if(waiting){waiting=false;lockUnknown()}},POST_CALLBACK_TIMEOUT_MS);
        try{w.PostXMLWithResponse(xmlName,mapXml(fields),function(){if(!waiting)return;waiting=false;if(typeof w.clearTimeout==='function')w.clearTimeout(timer);poll(command,0,onComplete,onReject)})}
        catch(_){waiting=false;if(typeof w.clearTimeout==='function')w.clearTimeout(timer);lockUnknown()}
      }
      function deleteOne(id){
        if(busy||session.busy||session.locked||!identityMatched||!profile.deletable||!historyComplete)return;
        if(!/^[A-Za-z0-9_-]{1,64}$/.test(String(id||''))||idCounts[id]!==1){setStatus('This message cannot be deleted safely.',true);return}
        setStatus('Deleting once…');
        postOnce([
          ['RGW/message/flag/message_flag','DELETE_SMS'],['RGW/message/flag/sms_cmd','6'],['RGW/message/get_message/tags',profile.tags],
          ['RGW/message/get_message/mem_store',profile.store],['RGW/message/set_message/delete_message_id',String(id)+',']
        ],6,function(){loadAll(String(id),true)},function(value){setStatus('Delete rejected (status '+value+'). No retry.',true)});
      }
      function updateCount(){
        var value=String(body.value||''),parts=segments(value);
        count.textContent=value.length+' / '+MAX_UCS2_UNITS+' · '+parts+' of 4 UCS-2 segment'+(parts===1?'':'s');
      }
      function openComposer(){
        if(busy||session.busy||session.locked||!identityMatched)return;
        composer.hidden=false;number.focus();updateCount();
      }
      function sendOne(){
        if(busy||session.busy||session.locked||!identityMatched||composer.hidden)return;
        var target=String(number.value||'').trim(),message=String(body.value||'');
        if(!validPhone(target)){setStatus('Use 3–15 digits and an optional leading +.',true);return}
        if(!validBody(message)){setStatus('Use 1–268 BMP characters; controls and emoji are not supported.',true);return}
        var encoded;try{encoded=String(w.UniEncode(message)||'').toUpperCase()}catch(_){setStatus('Encoding failed. Nothing sent.',true);return}
        if(!/^(?:[0-9A-F]{4})+$/.test(encoded)||encoded.length!==message.length*4){setStatus('Encoding failed. Nothing sent.',true);return}
        var before=null;
        try{before=readHistory(PROFILES.mDeviceOutbox)}catch(_){lockUnknown('Sent baseline failed. Nothing was submitted; reload before an SMS write.');return}
        if(!before.complete){lockUnknown('Sent baseline was incomplete. Nothing was submitted; reload before an SMS write.');return}
        setStatus('Sending once…');
        postOnce([
          ['RGW/message/flag/message_flag','SEND_SMS'],['RGW/message/flag/sms_cmd','4'],['RGW/message/send_save_message/contacts',target],
          ['RGW/message/send_save_message/content',encoded],['RGW/message/send_save_message/encode_type','UNICODE'],['RGW/message/send_save_message/sms_time',w.GetSmsTime()]
        ],4,function(){
          var recorded=false,after=null;
          try{after=readHistory(PROFILES.mDeviceOutbox)}catch(_){lockUnknown('Router accepted the command, but Sent verification failed. Delivery is not proven. Reload before another SMS write.');return}
          if(!after.complete){lockUnknown('Router accepted the command, but Sent verification was incomplete. Delivery is not proven. Reload before another SMS write.');return}
          var known={};for(var i=0;i<before.messages.length;i++)known[before.messages[i].id]=true;
          for(var j=0;j<after.messages.length;j++){var item=after.messages[j];if(item.id&&!known[item.id]&&item.recipient===target&&item.content===message){recorded=true;break}}
          if(!recorded){lockUnknown('Router accepted the command, but no matching new Sent record was found. Delivery is not proven. Reload before another SMS write.');return}
          releaseMutation();composer.hidden=true;number.value='';body.value='';updateCount();setStatus('Recorded in Sent. Delivery is not proven.');
        },function(value){setStatus('Send rejected (status '+value+'). No retry.',true)});
      }

      refresh.addEventListener('click',function(){loadAll()});
      newButton.addEventListener('click',openComposer);
      cancel.addEventListener('click',function(){if(!busy&&!session.busy)composer.hidden=true});
      send.addEventListener('click',sendOne);body.addEventListener('input',updateCount);
      previous.addEventListener('click',function(){if(displayPage>1){displayPage--;renderPage()}});
      next.addEventListener('click',function(){if(displayPage<Math.ceil(currentMessages.length/DISPLAY_PAGE_SIZE)){displayPage++;renderPage()}});
      if(profile.deletable){
        watcher.attach({readFirst:function(){return readPage(PROFILES.mDeviceInbox,1)},readFull:function(){return readHistory(PROFILES.mDeviceInbox)},current:function(){return lastHistoryResult},busy:function(){return busy||session.busy}},watchInput,watchHint,watchPanel);
        watchInput.addEventListener('change',function(){if(watchInput.checked)watcher.enable(true);else watcher.disable(true)});
      }
      this.onLoad=function(){displayPage=1;checkIdentity();loadAll()};this.onPost=function(){};this.onPostSuccess=function(){};this.setXMLName=function(value){xmlName=value||'message'};
      w.MF885_COMMUNITY_R23_SMS={id:'0.2.3-community-r2',parsePage:parsePage,commandStatus:commandStatus,segments:segments,validBody:validBody,validPhone:validPhone,isMutationLocked:function(){return session.locked},isMutationBusy:function(){return session.busy},isWatchEnabled:function(){return watcher.enabled},watchIntervalMs:WATCH_INTERVAL_MS,displayPageSize:DISPLAY_PAGE_SIZE};
      return this;
    };
  }
  w.MF885_COMMUNITY_R23_SMS_CORE={id:'0.2.3-community-r2',parsePage:parsePage,commandStatus:commandStatus,segments:segments,validBody:validBody,validPhone:validPhone,install:install,watchIntervalMs:WATCH_INTERVAL_MS,watchKey:WATCH_KEY,displayPageSize:DISPLAY_PAGE_SIZE};
  install(w.jQuery);
})(window);
