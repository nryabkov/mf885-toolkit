/* MF885 Community R2.4 read-only modem monitor 0.2.4-community-r2 */
(function(w){
  'use strict';
  var VERSION='0.2.4-community-r2',ENDPOINTS=['status1','wan','Engineer_parameter'];
  var WATCH_KEY='mf885.community.r24.modem-watch.v1',WATCH_MS=30000,FAILURE_LIMIT=3,MAX_SAMPLES=60,MAX_CHANGES=20;
  var PATHS={
    status1:{
      model:[['sysinfo','model_name']],hardware:[['sysinfo','hardware_version']],baseVersion:[['sysinfo','version_num']],
      sim:[['wan','cellular','sim_status'],['wan','sim_status']],registration:[['wan','cellular','NW_register_status'],['wan','NW_register_status']],roaming:[['wan','cellular','roaming'],['wan','roaming']],
      ratMode:[['wan','cellular','sys_mode'],['wan','sys_mode']],ratType:[['wan','cellular','ConnType'],['wan','ConnType']],operator:[['wan','cellular','network_name'],['wan','network_name']],
      pdp:[['wan','cellular','connect_disconnect'],['wan','connect_disconnect']],pdpType:[['wan','cellular','pdp_type'],['wan','pdp_type']],wanProto:[['wan','proto']],wanLink:[['wan','wan_link_status']],wanConn:[['wan','wan_conn_status']],wifiSsid:[['wan','wifi','ssid']],wifiSignal:[['wan','wifi','signal']],
      apEnabled:[['wlan_settings','wlan_enable']],apChannel:[['wlan_settings','current_channel'],['wlan_settings','channel']],
      battery:[['batteryinfo','Battery_percent']],batteryState:[['batteryinfo','Battery_status']],
      connDays:[['statistics','WanStatistics','conn_days']],connHours:[['statistics','WanStatistics','conn_hours']],connMinutes:[['statistics','WanStatistics','conn_minutes']],connSeconds:[['statistics','WanStatistics','conn_seconds']]
    },
    wan:{
      sim:[['wan','cellular','sim_status'],['wan','sim_status']],registration:[['wan','cellular','NW_register_status'],['wan','NW_register_status']],roaming:[['wan','cellular','roaming'],['wan','roaming']],
      ratMode:[['wan','cellular','sys_mode'],['wan','sys_mode']],ratType:[['wan','cellular','ConnType'],['wan','ConnType']],operator:[['wan','cellular','network_name'],['wan','network_name']],
      pdp:[['wan','cellular','connect_disconnect'],['wan','connect_disconnect']],pdpType:[['wan','cellular','pdp_type'],['wan','pdp_type']],wanProto:[['wan','proto']],wanLink:[['wan','wan_link_status']],wanConn:[['wan','wan_conn_status']],wifiSsid:[['wan','wifi','ssid']],wifiSignal:[['wan','wifi','signal']]
    },
    Engineer_parameter:{
      band:[['Engineer_parameter','LTE_band'],['Engineer_parameter','lte_band'],['Engi','LTE','band']],earfcn:[['Engineer_parameter','EARFCN'],['Engineer_parameter','earfcn'],['Engi','LTE','dlEuArfcn']],ulEarfcn:[['Engi','LTE','ulEuArfcn']],pci:[['Engineer_parameter','PCI'],['Engineer_parameter','pci'],['Engi','LTE','phyCellId']],
      bandwidth:[['Engi','LTE','dlBandwidth']],cqi:[['Engi','LTE','cqi']],rsrp:[['Engineer_parameter','RSRP'],['Engineer_parameter','rsrp'],['Engi','LTE','rsrp']],rsrq:[['Engineer_parameter','RSRQ'],['Engineer_parameter','rsrq'],['Engi','LTE','rsrq']],sinr:[['Engineer_parameter','SINR'],['Engineer_parameter','sinr'],['Engi','LTE','sinr']],rssi:[['Engineer_parameter','RSSI'],['Engineer_parameter','rssi'],['Engi','LTE','rssi']],
      mainRsrp:[['Engi','LTE','mainRsrp']],diversityRsrp:[['Engi','LTE','diversityRsrp']],mainRsrq:[['Engi','LTE','mainRsrq']],diversityRsrq:[['Engi','LTE','diversityRsrq']],
      umtsPsc:[['Engi','UMTS','psc_cellParameterId']],umtsArfcn:[['Engi','UMTS','arfcn']],rscp:[['Engi','UMTS','rscp']],ecno:[['Engi','UMTS','cpichEcN0']],txPower:[['Engi','UMTS','txPower']],
      gsmArfcn:[['Engi','GSM','arfcn']],gsmSignal:[['Engi','GSM','rxSigLevel']],gsmQuality:[['Engi','GSM','rxQualityFull']],timingAdvance:[['Engi','GSM','timingAdv']],gprsUl:[['Engi','GPRS','ULThroughput']],gprsDl:[['Engi','GPRS','DLThroughput']]
    }
  };
  var MAPS={
    sim:{'0':'Ready','1':'Absent'},registration:{'0':'Not registered','1':'Registered · home','2':'Searching','5':'Registered · roaming'},roaming:{'0':'Home network','1':'Roaming'},
    pdp:{'0':'Disconnected','1':'Connected','2':'Connecting','cellular':'Connected','disabled':'Disconnected'},pdpType:{'0':'IPv4','1':'IPv6','2':'IPv4 / IPv6','IP':'IPv4','IPV6':'IPv6','IPV4V6':'IPv4 / IPv6'},
    ratMode:{'0':'No service','3':'2G · GSM / GPRS','4':'3G · WCDMA','5':'3G · WCDMA','6':'4G · LTE','17':'4G · LTE'},ratType:{'0':'No service','1':'2G · GSM','2':'3G · WCDMA','3':'4G · LTE','LTE':'4G · LTE','WCDMA':'3G · WCDMA','GSM':'2G · GSM'},
    batteryState:{'1':'Charging input','2':'Powering USB-A','3':'On battery'},wanProto:{'cellular':'Cellular','wifi':'Wi-Fi uplink','disabled':'Disabled'},apEnabled:{'0':'Off','1':'On'}
  };
  function direct(nodes,name){
    var result=[],wanted=String(name).toLowerCase();
    for(var i=0;i<nodes.length;i++){var items=nodes[i]&&nodes[i].childNodes?nodes[i].childNodes:[];for(var j=0;j<items.length;j++)if(items[j].nodeType===1&&String(items[j].nodeName||'').toLowerCase()===wanted)result.push(items[j])}
    return result;
  }
  function unavailable(value){return /^(?:NA|N\/A|NONE|NULL|UNKNOWN|--?|0\.0\.0\.0|::|::0)$/i.test(String(value||'').trim())}
  function pathValue(xml,path){
    var root=xml&&xml.documentElement;if(!root)return null;var nodes=[root],start=String(root.nodeName||'').toLowerCase()===String(path[0]).toLowerCase()?1:0;
    for(var i=start;i<path.length&&nodes.length;i++)nodes=direct(nodes,path[i]);
    if(nodes.length!==1)return null;var value=String(nodes[0].textContent||'').trim();return value&&!unavailable(value)?value:null;
  }
  function extract(name,xml){
    var result={},fields=PATHS[name]||{};
    Object.keys(fields).forEach(function(field){for(var i=0;i<fields[field].length;i++){var value=pathValue(xml,fields[field][i]);if(value!==null){result[field]=value;break}}});
    return result;
  }
  function findNonEmpty(node,name){
    var wanted=String(name).toLowerCase(),pending=[node];
    while(pending.length){var current=pending.pop(),items=current&&current.childNodes?current.childNodes:[];for(var i=0;i<items.length;i++)if(items[i].nodeType===1){if(String(items[i].nodeName||'').toLowerCase()===wanted&&String(items[i].textContent||'').trim())return true;pending.push(items[i])}}
    return false;
  }
  function requestModel($,name,done){
    if(ENDPOINTS.indexOf(name)<0){done('unsupported');return null}
    try{return $.ajax({type:'GET',url:(w.location.protocol+'//'+w.location.host+'/xml_action.cgi?method=get&module=duster&file='+name),dataType:'xml',async:true,cache:false,timeout:10000,
      beforeSend:function(xhr){xhr.setRequestHeader('Authorization',w.getAuthHeader('GET'));xhr.setRequestHeader('Cache-Control','no-store, no-cache, must-revalidate')},
      success:function(xml){
        if(!xml||!xml.documentElement||String(xml.documentElement.nodeName||'').toUpperCase()!=='RGW'){done('parse');return}
        if(findNonEmpty(xml.documentElement,'login_status')){done('authentication');return}
        done(null,extract(name,xml),xml);
      },
      error:function(xhr,state){done(state==='timeout'?'timeout':xhr&&xhr.status===401?'authentication':xhr&&xhr.status?'http':'error')}
    })}catch(_){done('error');return null}
  }
  function first(models,name){for(var i=0;i<ENDPOINTS.length;i++){var item=models[ENDPOINTS[i]]||{};if(item[name]!==undefined)return item[name]}return null}
  function mapped(name,raw){var map=MAPS[name];return raw===null?'Not returned':map&&map[raw]!==undefined?map[raw]:map?'Unknown (raw: '+raw+')':raw}
  function radio(models){var raw=first(models,'ratMode');if(raw!==null)return mapped('ratMode',raw);raw=first(models,'ratType');return mapped('ratType',raw)}
  function duration(models){
    var names=['connDays','connHours','connMinutes','connSeconds'],parts=[],found=false;
    for(var i=0;i<names.length;i++){var raw=first(models,names[i]);if(raw!==null&&/^\d+$/.test(raw)){parts.push(parseInt(raw,10));found=true}else parts.push(0)}
    function two(v){return ('0'+String(v)).slice(-2)}return found?parts[0]+'d '+two(parts[1])+'h '+two(parts[2])+'m '+two(parts[3])+'s':'Not returned';
  }
  function snapshot(models,identity){
    return {identity:identity,model:mapped('model',first(models,'model')),hardware:mapped('hardware',first(models,'hardware')),baseVersion:mapped('baseVersion',first(models,'baseVersion')),
      sim:mapped('sim',first(models,'sim')),registration:mapped('registration',first(models,'registration')),roaming:mapped('roaming',first(models,'roaming')),operator:mapped('operator',first(models,'operator')),
      rat:radio(models),pdp:mapped('pdp',first(models,'pdp')),pdpType:mapped('pdpType',first(models,'pdpType')),band:mapped('band',first(models,'band')),earfcn:mapped('earfcn',first(models,'earfcn')),ulEarfcn:mapped('ulEarfcn',first(models,'ulEarfcn')),pci:mapped('pci',first(models,'pci')),bandwidth:mapped('bandwidth',first(models,'bandwidth')),cqi:mapped('cqi',first(models,'cqi')),
      rsrp:mapped('rsrp',first(models,'rsrp')),rsrq:mapped('rsrq',first(models,'rsrq')),sinr:mapped('sinr',first(models,'sinr')),rssi:mapped('rssi',first(models,'rssi')),mainRsrp:mapped('mainRsrp',first(models,'mainRsrp')),diversityRsrp:mapped('diversityRsrp',first(models,'diversityRsrp')),mainRsrq:mapped('mainRsrq',first(models,'mainRsrq')),diversityRsrq:mapped('diversityRsrq',first(models,'diversityRsrq')),
      umtsPsc:mapped('umtsPsc',first(models,'umtsPsc')),umtsArfcn:mapped('umtsArfcn',first(models,'umtsArfcn')),rscp:mapped('rscp',first(models,'rscp')),ecno:mapped('ecno',first(models,'ecno')),txPower:mapped('txPower',first(models,'txPower')),gsmArfcn:mapped('gsmArfcn',first(models,'gsmArfcn')),gsmSignal:mapped('gsmSignal',first(models,'gsmSignal')),gsmQuality:mapped('gsmQuality',first(models,'gsmQuality')),timingAdvance:mapped('timingAdvance',first(models,'timingAdvance')),gprsUl:mapped('gprsUl',first(models,'gprsUl')),gprsDl:mapped('gprsDl',first(models,'gprsDl')),
      battery:mapped('battery',first(models,'battery')),batteryState:mapped('batteryState',first(models,'batteryState')),connectionTime:duration(models),wanProto:mapped('wanProto',first(models,'wanProto')),wanLink:mapped('wanLink',first(models,'wanLink')),wanConn:mapped('wanConn',first(models,'wanConn')),wifiSsid:first(models,'wifiSsid'),wifiSignal:mapped('wifiSignal',first(models,'wifiSignal')),apEnabled:mapped('apEnabled',first(models,'apEnabled')),apChannel:mapped('apChannel',first(models,'apChannel'))};
  }
  function number(value){var match=String(value||'').match(/-?\d+(?:\.\d+)?/);return match?Number(match[0]):null}
  function safeState(value,allowed){return allowed.indexOf(String(value||''))>=0?String(value):'Unknown'}
  function safeNumeric(value,minimum,maximum){
    value=String(value||'').trim();if(!/^-?\d+(?:\.\d+)?$/.test(value))return null;
    var numeric=Number(value);return isFinite(numeric)&&numeric>=minimum&&numeric<=maximum?value:null;
  }
  function safeSample(item){
    return {elapsedSeconds:typeof item.elapsedSeconds==='number'&&item.elapsedSeconds>=0&&item.elapsedSeconds<=86400?item.elapsedSeconds:null,
      registration:safeState(item.registration,['Not registered','Registered · home','Searching','Registered · roaming']),
      roaming:safeState(item.roaming,['Home network','Roaming']),rat:safeState(item.rat,['No service','2G · GSM / GPRS','2G · GSM','3G · WCDMA','4G · LTE']),
      pdp:safeState(item.pdp,['Disconnected','Connected','Connecting']),wanMode:safeState(item.wanProto,['Cellular','Wi-Fi uplink','Disabled']),
      band:safeNumeric(item.band,0,255),bandwidth:safeNumeric(item.bandwidth,0,100),cqi:safeNumeric(item.cqi,0,30),
      rsrp:safeNumeric(item.rsrp,-200,0),rsrq:safeNumeric(item.rsrq,-60,60),sinr:safeNumeric(item.sinr,-100,100),rssi:safeNumeric(item.rssi,-200,0),
      mainRsrp:safeNumeric(item.mainRsrp,-200,0),diversityRsrp:safeNumeric(item.diversityRsrp,-200,0),mainRsrq:safeNumeric(item.mainRsrq,-60,60),diversityRsrq:safeNumeric(item.diversityRsrq,-60,60),battery:safeNumeric(item.battery,0,100)};
  }
  function mutationBusy(){var value=w.MF885_COMMUNITY_R24_MUTATION_SESSION;return !!(value&&value.document===w.document&&value.busy)}
  function notifyMutationUi(){var value=w.MF885_COMMUNITY_R24_MUTATION_SESSION;if(value&&value.document===w.document&&typeof value.update==='function')try{value.update()}catch(_){}}
  function monitorSession(){
    var state=w.MF885_COMMUNITY_R24_MODEM_SESSION;
    if(state&&state.version===1&&state.document===w.document)return state;
    state={version:1,document:w.document,enabled:false,timer:null,request:null,generation:0,busy:false,failures:0,started:Date.now(),latest:null,samples:[],changes:[],controller:null};
    try{state.enabled=!!(w.sessionStorage&&w.sessionStorage.getItem(WATCH_KEY)==='1')}catch(_){state.enabled=false}
    w.MF885_COMMUNITY_R24_MODEM_SESSION=state;return state;
  }
  function install($){
    if(!$||!$.fn)return;
    $.fn.objModemMonitor=function(){
      var root=w.document.getElementById('Content');if(!root)throw new Error('Modem content root is missing');
      root.innerHTML=w.callProductHTML('html/Community/r24modem.html');if(w.MF885CommunityR24&&typeof w.MF885CommunityR24.markRoot==='function')w.MF885CommunityR24.markRoot();
      var page=w.document.getElementById('mfCommunityR24Modem'),refresh=w.document.getElementById('mfModemRefresh'),copy=w.document.getElementById('mfModemCopy'),watch=w.document.getElementById('mfModemWatch');
      var status=w.document.getElementById('mfModemStatus'),summary=w.document.getElementById('mfModemSummary'),changes=w.document.getElementById('mfModemChanges'),uplink=w.document.getElementById('mfUplinkState');
      var chart=w.document.getElementById('mfSignalChart'),line=w.document.getElementById('mfSignalLine'),signalNow=w.document.getElementById('mfSignalNow'),fallback=w.document.getElementById('mfSignalFallback');
      var reportBox=w.document.getElementById('mfModemReport'),copyFallback=w.document.getElementById('mfModemCopyFallback'),session=monitorSession(),xmlName='status1';
      session.generation++;if(session.request&&typeof session.request.abort==='function')try{session.request.abort()}catch(_){}session.request=null;session.busy=false;if(session.timer!==null&&typeof w.clearTimeout==='function')w.clearTimeout(session.timer);session.timer=null;session.controller=page;watch.checked=session.enabled;notifyMutationUi();
      function current(){return session.controller===page&&w.document.getElementById('mfCommunityR24Modem')===page}
      function releaseDetached(token){
        if(token!==session.generation||current()||(!session.controller&&!session.request&&!session.busy))return false;
        session.generation++;var request=session.request;session.request=null;session.busy=false;session.controller=null;cancelTimer();notifyMutationUi();
        if(request&&typeof request.abort==='function')try{request.abort()}catch(_){}return true;
      }
      function active(token){if(token===session.generation&&current())return true;releaseDetached(token);return false}
      function setStatus(value,error){if(!current())return;status.textContent=value;status.style.color=error?'#b42318':'#344054'}
      function persist(value){try{if(!w.sessionStorage)return false;if(value)w.sessionStorage.setItem(WATCH_KEY,'1');else w.sessionStorage.removeItem(WATCH_KEY);return true}catch(_){return false}}
      function cancelTimer(){if(session.timer!==null&&typeof w.clearTimeout==='function')w.clearTimeout(session.timer);session.timer=null}
      function schedule(){
        cancelTimer();if(!session.enabled||!current()||w.document.hidden)return;var generation=session.generation;
        session.timer=w.setTimeout(function(){session.timer=null;if(generation===session.generation&&current())run(true)},WATCH_MS);
      }
      session.schedule=schedule;session.cancel=cancelTimer;session.releaseDetached=function(){return releaseDetached(session.generation)};
      function metric(label,value){var box=w.document.createElement('div'),key=w.document.createElement('span'),text=w.document.createElement('strong');box.className='mfModemMetric';key.className='mfModemMetricLabel';text.className='mfModemMetricValue';key.textContent=label;text.textContent=value;box.appendChild(key);box.appendChild(text);summary.appendChild(box)}
      function renderSummary(value){
        summary.textContent='';var rows=[['SIM',value.sim],['Registration',value.registration],['Radio',value.rat],['Operator',value.operator],['PDP',value.pdp],['Band',value.band],['RSRP',value.rsrp],['RSRQ',value.rsrq],['SINR',value.sinr],['Battery',value.battery==='Not returned'?value.battery:value.battery+'%'],['Uplink',value.wanProto],['Connection time',value.connectionTime]];
        var optional=[['DL EARFCN',value.earfcn],['UL EARFCN',value.ulEarfcn],['PCI',value.pci],['DL bandwidth',value.bandwidth],['CQI',value.cqi],['Main RSRP',value.mainRsrp],['Diversity RSRP',value.diversityRsrp],['Main RSRQ',value.mainRsrq],['Diversity RSRQ',value.diversityRsrq],['UMTS PSC',value.umtsPsc],['UMTS ARFCN',value.umtsArfcn],['RSCP',value.rscp],['Ec/N0',value.ecno],['UMTS Tx power',value.txPower],['GSM ARFCN',value.gsmArfcn],['GSM signal',value.gsmSignal],['GSM quality',value.gsmQuality],['GSM timing advance',value.timingAdvance],['GPRS UL throughput',value.gprsUl],['GPRS DL throughput',value.gprsDl]];
        for(var o=0;o<optional.length;o++)if(optional[o][1]!=='Not returned')rows.push(optional[o]);
        for(var i=0;i<rows.length;i++)metric(rows[i][0],rows[i][1]);
        var detail='Link '+value.wanLink+' · connection '+value.wanConn+' · local AP '+value.apEnabled+(value.apChannel!=='Not returned'?' · channel '+value.apChannel:'');
        uplink.textContent=(value.wanProto==='Wi-Fi uplink'?(value.wifiSsid?'Configured network: '+value.wifiSsid+'. ':'Wi-Fi uplink selected; network name was not returned. '):value.wanProto==='Cellular'?'Cellular is the selected uplink. ':'Uplink mode: '+value.wanProto+'. ')+detail;
      }
      function addChanges(next){
        var prior=session.latest,keys=[['sim','SIM'],['registration','Registration'],['roaming','Roaming'],['rat','Radio'],['pdp','PDP'],['wanProto','Uplink']];
        if(prior)for(var i=0;i<keys.length;i++){var key=keys[i][0];if(prior[key]!==next[key]){var elapsed=Math.max(0,Math.round((Date.now()-session.started)/1000));session.changes.unshift('+'+elapsed+'s · '+keys[i][1]+': '+prior[key]+' → '+next[key]);if(session.changes.length>MAX_CHANGES)session.changes.pop()}}
      }
      function renderChanges(){changes.textContent='';if(!session.changes.length){var empty=w.document.createElement('li');empty.textContent='No changes observed.';changes.appendChild(empty);return}for(var i=0;i<session.changes.length;i++){var item=w.document.createElement('li');item.textContent=session.changes[i];changes.appendChild(item)}}
      function renderChart(){
        var points=[],valid=[];for(var i=0;i<session.samples.length;i++){var value=number(session.samples[i].rsrp);if(value!==null)valid.push(value)}
        if(!valid.length){line.setAttribute('points','');signalNow.textContent='No samples';fallback.textContent='No valid RSRP samples yet.';return}
        for(var j=0;j<valid.length;j++){var clamped=Math.max(-130,Math.min(-70,valid[j])),x=valid.length===1?300:j*(600/(valid.length-1)),y=20+((-70-clamped)/60)*96;points.push(x.toFixed(1)+','+y.toFixed(1))}
        line.setAttribute('points',points.join(' '));signalNow.textContent=valid[valid.length-1]+' dBm · '+valid.length+' sample'+(valid.length===1?'':'s');fallback.textContent='Scale: −70 dBm strong · −130 dBm weak.';
      }
      function safeReport(){
        var safeSamples=session.samples.map(safeSample);
        return JSON.stringify({schema:'mf885-community-safe-modem-trace/v1',community:VERSION,current:session.latest?safeSamples[safeSamples.length-1]||null:null,samples:safeSamples,changeCount:session.changes.length,privacy:{omitted:['raw XML','credentials','identifiers','addresses','APN','SSID','cell location','raw unknown values','SMS and phone data']}},null,2);
      }
      function copyTrace(){
        var value=safeReport();reportBox.value=value;copyFallback.hidden=true;
        function manual(){copyFallback.hidden=false;try{reportBox.focus();reportBox.select()}catch(_){}setStatus('Clipboard unavailable. Select and copy the safe trace manually.',true)}
        if(w.navigator&&w.navigator.clipboard&&typeof w.navigator.clipboard.writeText==='function')try{var promise=w.navigator.clipboard.writeText(value);if(promise&&typeof promise.then==='function'){promise.then(function(){setStatus('Safe trace copied.')},manual);return}}catch(_){}
        try{copyFallback.hidden=false;reportBox.focus();reportBox.select();if(w.document.execCommand&&w.document.execCommand('copy')){copyFallback.hidden=true;setStatus('Safe trace copied.');return}}catch(_){}manual();
      }
      function complete(models,states,statusXml,token){
        if(!active(token))return;
        var identity=!!(w.MF885CommunityR24&&typeof w.MF885CommunityR24.exactStatus1Identity==='function'&&w.MF885CommunityR24.exactStatus1Identity(statusXml)),value=snapshot(models,identity),failed=0;
        Object.keys(states).forEach(function(name){if(states[name]!=='ok')failed++});addChanges(value);session.latest=value;session.samples.push({elapsedSeconds:Math.max(0,Math.round((Date.now()-session.started)/1000)),registration:value.registration,roaming:value.roaming,rat:value.rat,pdp:value.pdp,band:value.band,bandwidth:value.bandwidth,cqi:value.cqi,rsrp:value.rsrp,rsrq:value.rsrq,sinr:value.sinr,rssi:value.rssi,mainRsrp:value.mainRsrp,diversityRsrp:value.diversityRsrp,mainRsrq:value.mainRsrq,diversityRsrq:value.diversityRsrq,battery:value.battery,wanProto:value.wanProto});if(session.samples.length>MAX_SAMPLES)session.samples.shift();
        session.request=null;session.busy=false;notifyMutationUi();refresh.disabled=false;copy.disabled=false;renderSummary(value);renderChanges();renderChart();
        if(!identity)setStatus('Read completed, but exact MF885 / Ver.D / 2.5.94 identity was not proven.',true);else if(failed)setStatus('Partial read: '+failed+' source'+(failed===1?'':'s')+' failed. Previous samples were kept.',true);else setStatus(session.enabled?'Watching · next read in 30 seconds.':'Modem status updated.');
        session.failures=failed?session.failures+1:0;if(session.enabled&&session.failures>=FAILURE_LIMIT){session.enabled=false;persist(false);watch.checked=false;setStatus('Watch paused after repeated incomplete reads. Manual Refresh remains available.',true)}schedule();
      }
      function run(fromWatch){
        if(session.busy||!current())return;if(mutationBusy()){setStatus('Waiting for the current Messages operation.');if(fromWatch)schedule();return}
        var token=++session.generation;session.busy=true;notifyMutationUi();refresh.disabled=true;copy.disabled=true;var models={},states={},index=0,statusXml=null;setStatus('Reading status1 (1 of 3)…');
        function next(){
          if(!active(token))return;if(index>=ENDPOINTS.length){complete(models,states,statusXml,token);return}
          var name=ENDPOINTS[index++],completed=false;setStatus('Reading '+name+' ('+index+' of 3)…');var request=requestModel($,name,function(error,data,xml){completed=true;if(!active(token))return;session.request=null;states[name]=error||'ok';if(!error){models[name]=data;if(name==='status1')statusXml=xml}next()});if(!completed)session.request=request;
        }
        next();
      }
      refresh.addEventListener('click',function(){run(false)});copy.addEventListener('click',copyTrace);watch.addEventListener('change',function(){
        if(watch.checked){if(!persist(true)){watch.checked=false;setStatus('Watch preference is unavailable in this browser.',true);return}session.enabled=true;session.failures=0;setStatus('Watch enabled.');run(true)}else{session.enabled=false;persist(false);cancelTimer();setStatus('Watch off. Manual Refresh remains available.')}
      });
      if(typeof w.addEventListener==='function'&&!w.MF885_COMMUNITY_R24_MODEM_LIFECYCLE){
        w.MF885_COMMUNITY_R24_MODEM_LIFECYCLE=true;
        w.addEventListener('pagehide',function(){var s=monitorSession();s.generation++;if(s.request&&typeof s.request.abort==='function')try{s.request.abort()}catch(_){}s.request=null;if(typeof s.cancel==='function')s.cancel();s.busy=false;notifyMutationUi()});
        w.addEventListener('pageshow',function(){var s=monitorSession();if(s.enabled&&typeof s.schedule==='function')s.schedule()});
        w.document.addEventListener('visibilitychange',function(){var s=monitorSession();if(w.document.hidden){if(typeof s.cancel==='function')s.cancel()}else if(s.enabled&&typeof s.schedule==='function')s.schedule()});
      }
      this.onLoad=function(){run(false)};this.onPost=function(){};this.onPostSuccess=function(){};this.setXMLName=function(value){xmlName=value||'status1'};
      w.MF885_COMMUNITY_R24_MODEM={id:VERSION,watchMs:WATCH_MS,isWatching:function(){return session.enabled},safeReport:safeReport,refresh:function(){run(false)}};return this;
    };
  }
  var api={id:VERSION,extract:extract,install:install,watchMs:WATCH_MS};w.MF885_COMMUNITY_R24_MODEM_CORE=api;install(w.jQuery);
})(window);
