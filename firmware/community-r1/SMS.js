/* MF885 Community R1 SMS read-delete 0.1-community-r1 */
(function(w){
  'use strict';
  var PROFILES={
    mDeviceInbox:{flag:'GET_RCV_SMS_LOCAL',tags:'12',store:'1',label:'Device inbox',deletable:true},
    mDeviceOutbox:{flag:'GET_SENT_SMS_LOCAL',tags:'2',store:'1',label:'Sent messages',deletable:false},
    mSimSms:{flag:'GET_SIM_SMS',tags:'',store:'0',label:'SIM messages',deletable:false},
    mDrafts:{flag:'GET_DRAFT_SMS',tags:'2',store:'2',label:'Drafts',deletable:false}
  };
  var MAX_PAGES=20,MAX_MESSAGES=200,PAGE_SIZE=10,STATUS_POLLS=10,POST_CALLBACK_TIMEOUT_MS=30000;

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
    for(var i=0;i<items.length;i++)messages.push({
      id:text(items[i],'index'),
      from:String(decode(text(items[i],'from'))||'').replace(/^;/,'').replace(/;.*$/,''),
      content:String(decode(text(items[i],'subject')||text(items[i],'content'))||''),
      received:text(items[i],'received'),status:text(items[i],'status')
    });
    var pages=parseInt(text(containers[0],'total_number'),10);
    return {messages:messages,totalPages:Number.isFinite(pages)&&pages>0?pages:null};
  }
  function install($){
    if(!$||!$.fn)return;
    $.fn.objSms=function(menuName){
      var root=w.document.getElementById('Content'),xmlName='message',profile=PROFILES[menuName]||PROFILES.mDeviceInbox;
      if(!root)throw new Error('SMS content root is missing');
      root.innerHTML=w.callProductHTML('html/SMS/SMS.html');
      var list=w.document.getElementById('mfSmsList'),status=w.document.getElementById('mfSmsStatus');
      var refresh=w.document.getElementById('mfSmsRefresh'),folder=w.document.getElementById('mfSmsFolder');
      var busy=false,unknown=false,identityMatched=false;
      folder.textContent=profile.label;

      function setStatus(value,error){status.textContent=value;status.style.color=error?'#b42318':'#344054'}
      function updateButtons(){
        refresh.disabled=busy;
        var deletes=list.querySelectorAll('button[data-sms-delete]');
        for(var i=0;i<deletes.length;i++)deletes[i].disabled=busy||unknown||!identityMatched||!profile.deletable||deletes[i].getAttribute('data-sms-safe')!=='1';
      }
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
        var map=[],index=0;
        for(var i=0;i<fields.length;i++)w.putMapElement(map,fields[i][0],fields[i][1],index++);
        return w.g_objXML.getXMLDocToString(w.g_objXML.createXML(map));
      }
      function readPage(page){
        var xml=mapXml([['RGW/message/flag/message_flag',profile.flag],['RGW/message/get_message/page_number',String(page)]]);
        w.PostSyncXML(xmlName,xml);return parsePage(w.GetSmsXML(xmlName));
      }
      function render(messages){
        var idCounts={};for(var count=0;count<messages.length;count++)if(messages[count].id)idCounts[messages[count].id]=(idCounts[messages[count].id]||0)+1;
        list.textContent='';
        if(!messages.length){var empty=w.document.createElement('p');empty.textContent='No messages found.';list.appendChild(empty);return}
        for(var i=0;i<messages.length;i++)(function(message){
          var card=w.document.createElement('details');card.style.cssText='border:1px solid #d0d5dd;border-radius:10px;padding:10px;margin:8px 0';
          var summary=w.document.createElement('summary');summary.style.cursor='pointer';
          var sender=w.document.createElement('strong');sender.textContent=message.from||'Unknown sender';
          var received=w.document.createElement('span');received.style.cssText='font-size:12px;color:#667085;margin-left:8px';received.textContent=message.received;
          summary.appendChild(sender);summary.appendChild(received);
          var content=w.document.createElement('div');content.style.cssText='white-space:pre-wrap;margin-top:10px';content.textContent=message.content;
          card.appendChild(summary);card.appendChild(content);
          if(profile.deletable){
            var del=w.document.createElement('button');del.type='button';del.textContent='Delete';del.style.marginTop='10px';del.setAttribute('data-sms-delete','');
            var safe=/^[A-Za-z0-9_-]{1,64}$/.test(String(message.id||''))&&idCounts[message.id]===1;
            del.setAttribute('data-sms-safe',safe?'1':'0');del.disabled=busy||unknown||!identityMatched||!safe;
            del.addEventListener('click',function(event){event.preventDefault();if(w.confirm('Delete this SMS from MF885? This cannot be undone.'))deleteOne(message.id)});
            card.appendChild(del);
          }
          list.appendChild(card);
        })(messages[i]);
      }
      function loadAll(expectedDeletedId){
        if(busy)return;busy=true;updateButtons();setStatus('Loading messages…');
        try{
          var all=[],seenIds={},pageFingerprints={},reportedPages=null,complete=false,incomplete='',historySafe=true;
          for(var page=1;page<=MAX_PAGES;page++){
            var current=readPage(page),fingerprint=current.messages.map(function(message){return [message.id,message.from,message.received,message.content].join('\u001f')}).join('\u001e');
            if(page===1)reportedPages=current.totalPages;
            else if(current.totalPages!==null&&reportedPages!==current.totalPages){incomplete='the router changed its page count';break}
            if(!current.messages.length){
              if((page===1&&reportedPages===null)||(reportedPages!==null&&page>=reportedPages)||(reportedPages===null&&page>1))complete=true;
              else incomplete='an expected page was empty';
              break;
            }
            if(pageFingerprints[fingerprint]){incomplete='the router repeated a page';break}
            pageFingerprints[fingerprint]=true;
            for(var item=0;item<current.messages.length&&all.length<MAX_MESSAGES;item++){
              var message=current.messages[item],safeId=/^[A-Za-z0-9_-]{1,64}$/.test(String(message.id||''));
              if(!safeId||seenIds[message.id])historySafe=false;
              if(safeId)seenIds[message.id]=true;
              all.push(message);
            }
            if(all.length>=MAX_MESSAGES){incomplete='the message limit was reached';break}
            if(reportedPages!==null&&page>=reportedPages){complete=true;break}
            if(reportedPages===null&&current.messages.length<PAGE_SIZE){complete=true;break}
            if(page===MAX_PAGES)incomplete='the page limit was reached';
          }
          if(!historySafe){complete=false;incomplete=incomplete||'message identifiers were missing, unsafe, or repeated'}
          render(all);
          if(expectedDeletedId&&!complete){
            unknown=true;setStatus('Deletion readback was incomplete. Reload the page before any retry.',true);
          }else if(expectedDeletedId&&all.some(function(message){return message.id===expectedDeletedId})){
            unknown=true;setStatus('The router reported completion, but deletion could not be verified. Reload the page before any retry.',true);
          }else{
            var summary='Loaded '+all.length+' message'+(all.length===1?'':'s')+'.';
            if(expectedDeletedId)summary='Message deletion verified. '+summary;
            if(!complete)summary+=' History may be incomplete; deletion is disabled.';
            if(!profile.deletable)summary+=' This folder is read-only.';
            if(!identityMatched)summary+=' Deletion remains locked: exact device identity was not proven.';
            setStatus(summary,!complete||!identityMatched);if(!complete)unknown=true;
          }
        }catch(_){
          if(expectedDeletedId){unknown=true;setStatus('Deletion readback failed. Reload the page before any retry.',true)}
          else{unknown=true;list.textContent='';setStatus('Message history could not be read. Reload the page to restore deletion.',true)}
        }
        busy=false;updateButtons();
      }
      function lockUnknown(){unknown=true;busy=false;setStatus('Deletion outcome unknown. Reload the page before any retry.',true);updateButtons()}
      function poll(attempt,onSuccess){
        var parsed;
        try{parsed=commandStatus(w.getData(xmlName))}catch(_){parsed={pending:true}}
        if(parsed.command==='6'&&parsed.complete){busy=false;updateButtons();onSuccess();return}
        if(parsed.command==='6'&&!parsed.pending){busy=false;setStatus('The router rejected the deletion command.',true);updateButtons();return}
        if(attempt>=STATUS_POLLS){lockUnknown();return}
        w.setTimeout(function(){poll(attempt+1,onSuccess)},1000);
      }
      function deleteOne(id){
        if(busy||unknown||!identityMatched||!profile.deletable)return;
        if(!/^[A-Za-z0-9_-]{1,64}$/.test(String(id||''))){setStatus('The selected message ID is not safe to submit.',true);return}
        busy=true;updateButtons();setStatus('Deletion submitted once; waiting for final status…');
        var fields=[
          ['RGW/message/flag/message_flag','DELETE_SMS'],['RGW/message/flag/sms_cmd','6'],
          ['RGW/message/get_message/tags',profile.tags],['RGW/message/get_message/mem_store',profile.store],
          ['RGW/message/set_message/delete_message_id',String(id)+',']
        ];
        var waiting=true,timer=w.setTimeout(function(){if(waiting){waiting=false;lockUnknown()}},POST_CALLBACK_TIMEOUT_MS);
        try{w.PostXMLWithResponse(xmlName,mapXml(fields),function(){if(!waiting)return;waiting=false;if(typeof w.clearTimeout==='function')w.clearTimeout(timer);poll(0,function(){loadAll(String(id))})})}catch(_){waiting=false;if(typeof w.clearTimeout==='function')w.clearTimeout(timer);lockUnknown()}
      }
      refresh.addEventListener('click',function(){loadAll()});
      this.onLoad=function(){checkIdentity();loadAll()};this.onPost=function(){};this.onPostSuccess=function(){};this.setXMLName=function(value){xmlName=value||'message'};
      w.MF885_COMMUNITY_R1_SMS={id:'0.1-community-r1',parsePage:parsePage,commandStatus:commandStatus};
      return this;
    };
  }
  w.MF885_COMMUNITY_R1_SMS_CORE={id:'0.1-community-r1',parsePage:parsePage,commandStatus:commandStatus,install:install};
  install(w.jQuery);
})(window);
