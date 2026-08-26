/* MF885 Community R2.1 safe manual diagnostics 0.2.1-community-r2 */
(function(w){
  'use strict';
  var VERSION='0.2.1-community-r2',ENDPOINTS=['status1','wan','Engineer_parameter'];
  var PATHS={
    status1:{
      hardware:[['sysinfo','hardware_version'],['hardware_version']],baseVersion:[['sysinfo','version_num'],['version_num']],model:[['sysinfo','model_name'],['model'],['model_name']],
      sim:[['wan','cellular','sim_status'],['wan','sim_status']],registration:[['wan','NW_register_status'],['wan','cellular','NW_register_status']],roaming:[['wan','cellular','roaming'],['wan','roaming']],
      ratSysMode:[['wan','sys_mode'],['wan','cellular','sys_mode']],ratConnType:[['wan','ConnType'],['wan','cellular','ConnType']],ratProto:[['wan','proto'],['wan','cellular','proto']],
      operator:[['wan','network_name'],['wan','cellular','network_name'],['wan','ISP_name'],['wan','cellular','ISP_name']],pdp:[['wan','connect_disconnect'],['wan','cellular','connect_disconnect']],pdpType:[['wan','pdp_type'],['wan','cellular','pdp_type']],
      apn:[['wan','cellular','active_apn'],['wan','cellular','pdp_context_list','Item','lte_apn'],['wan','cellular','pdp_context_list','Item','apn']],
      ipv4:[['wan','ip'],['wan','cellular','pdp_context_list','Item','ipv4']],ipv6:[['wan','cellular','pdp_context_list','Item','ipv6']],
      dns1:[['wan','dns1'],['wan','cellular','pdp_context_list','Item','v4dns1']],dns2:[['wan','dns2'],['wan','cellular','pdp_context_list','Item','v4dns2']],gateway:[['wan','gateway'],['wan','cellular','pdp_context_list','Item','v4gateway']],
      txTotal:[['statistics','WanStatistics','tx_byte_all'],['WanStatistics','tx_byte_all']],rxTotal:[['statistics','WanStatistics','rx_byte_all'],['WanStatistics','rx_byte_all']],txSession:[['statistics','WanStatistics','tx_byte'],['WanStatistics','tx_byte']],rxSession:[['statistics','WanStatistics','rx_byte'],['WanStatistics','rx_byte']],
      connDays:[['statistics','WanStatistics','conn_days'],['WanStatistics','conn_days']],connHours:[['statistics','WanStatistics','conn_hours'],['WanStatistics','conn_hours']],connMinutes:[['statistics','WanStatistics','conn_minutes'],['WanStatistics','conn_minutes']],connSeconds:[['statistics','WanStatistics','conn_seconds'],['WanStatistics','conn_seconds']],
      battery:[['batteryinfo','Battery_percent']],batteryState:[['batteryinfo','Battery_status']],chargerStatus:[['batteryinfo','Charger_status']],chargerCurrent:[['batteryinfo','Charger_current']],outputCurrent:[['batteryinfo','Output_current']]
    },
    wan:{
      sim:[['wan','cellular','sim_status'],['wan','sim_status']],registration:[['wan','NW_register_status'],['wan','cellular','NW_register_status']],roaming:[['wan','cellular','roaming'],['wan','roaming']],
      ratSysMode:[['wan','sys_mode'],['wan','cellular','sys_mode']],ratConnType:[['wan','ConnType'],['wan','cellular','ConnType']],ratProto:[['wan','proto'],['wan','cellular','proto']],
      operator:[['wan','network_name'],['wan','cellular','network_name'],['wan','ISP_name'],['wan','cellular','ISP_name']],pdp:[['wan','connect_disconnect'],['wan','cellular','connect_disconnect']],pdpType:[['wan','pdp_type'],['wan','cellular','pdp_type']],
      apn:[['wan','cellular','active_apn'],['wan','cellular','lte_apn'],['wan','cellular','apn'],['wan','cellular','pdp_context_list','Item','lte_apn'],['wan','cellular','pdp_context_list','Item','apn']],
      ipv4:[['wan','ip'],['wan','cellular','ip'],['wan','cellular','ip_address'],['wan','cellular','pdp_context_list','Item','ipv4']],ipv6:[['wan','ipv6'],['wan','cellular','ipv6'],['wan','cellular','ipv6_address'],['wan','cellular','pdp_context_list','Item','ipv6']],
      dns1:[['wan','dns1'],['wan','cellular','dns1'],['wan','cellular','v4dns1'],['wan','cellular','pdp_context_list','Item','v4dns1']],dns2:[['wan','dns2'],['wan','cellular','dns2'],['wan','cellular','v4dns2'],['wan','cellular','pdp_context_list','Item','v4dns2']],gateway:[['wan','gateway'],['wan','cellular','gateway'],['wan','cellular','v4gateway'],['wan','cellular','pdp_context_list','Item','v4gateway']]
    },
    Engineer_parameter:{
      band:[['Engineer_parameter','LTE_band'],['Engineer_parameter','lte_band'],['Engineer_parameter','band']],earfcn:[['Engineer_parameter','EARFCN'],['Engineer_parameter','earfcn']],pci:[['Engineer_parameter','PCI'],['Engineer_parameter','pci']],
      cell:[['Engineer_parameter','Cell_ID'],['Engineer_parameter','cell_id'],['Engineer_parameter','cellid']],tac:[['Engineer_parameter','TAC'],['Engineer_parameter','tac'],['Engineer_parameter','LAC'],['Engineer_parameter','lac']],
      rsrp:[['Engineer_parameter','RSRP'],['Engineer_parameter','rsrp']],rsrq:[['Engineer_parameter','RSRQ'],['Engineer_parameter','rsrq']],sinr:[['Engineer_parameter','SINR'],['Engineer_parameter','sinr']],rssi:[['Engineer_parameter','RSSI'],['Engineer_parameter','rssi']]
    }
  };
  var MAPS={sim:{'0':'Ready','1':'Absent'},registration:{'0':'Not registered','1':'Registered (home)','2':'Searching','5':'Registered (roaming)'},roaming:{'0':'Home network','1':'Roaming'},pdp:{'0':'Disconnected','1':'Connected','2':'Connecting','cellular':'Connected','disabled':'Disconnected'},pdpType:{'0':'IPv4','1':'IPv6','2':'IPv4/IPv6','IP':'IPv4','IPV6':'IPv6','IPV4V6':'IPv4/IPv6'},ratSysMode:{'0':'No service','3':'2G · GSM/GPRS','4':'3G · WCDMA','5':'3G · WCDMA','6':'4G · LTE','17':'4G · LTE'},ratConnType:{'0':'No service','1':'2G · GSM','2':'3G · WCDMA','3':'4G · LTE','LTE':'4G · LTE','WCDMA':'3G · WCDMA','GSM':'2G · GSM'},ratProto:{'LTE':'4G · LTE','WCDMA':'3G · WCDMA','HSPA':'3G · HSPA','GSM':'2G · GSM','cellular':'Cellular'},batteryState:{'1':'Charging input','2':'Powering USB-A','3':'On battery'},chargerStatus:{'0':'Normal charging','4':'Full','5':'Abnormal charging'}};
  function endpoint(name){return ENDPOINTS.indexOf(name)>=0}
  function unavailable(value){return /^(?:NA|N\/A|NONE|NULL|UNKNOWN|--?|0\.0\.0\.0|::|::0)$/i.test(String(value||'').trim())}
  function direct(nodes,name){var result=[],wanted=String(name).toLowerCase();for(var i=0;i<nodes.length;i++){var children=nodes[i].childNodes||[];for(var j=0;j<children.length;j++)if(children[j].nodeType===1&&String(children[j].nodeName||'').toLowerCase()===wanted)result.push(children[j])}return result}
  function pathValue(name,xml,path){
    var root=xml&&xml.documentElement;if(!root)return null;var nodes=[root],status=name==='status1'?direct(nodes,'status'):[];if(status.length===1)nodes=status;
    var start=0;if(String(nodes[0].nodeName||'').toLowerCase()===String(path[0]).toLowerCase())start=1;
    for(var i=start;i<path.length&&nodes.length;i++)nodes=direct(nodes,path[i]);
    for(var j=0;j<nodes.length;j++){var value=String(nodes[j].textContent||'').trim();if(value&&!unavailable(value))return value}return null;
  }
  function extract(name,xml){var result={},fields=PATHS[name]||{};Object.keys(fields).forEach(function(field){var paths=fields[field];for(var i=0;i<paths.length;i++){var value=pathValue(name,xml,paths[i]);if(value!==null){result[field]=value;break}}});return result}
  function first(models,name){for(var i=0;i<ENDPOINTS.length;i++){var values=models[ENDPOINTS[i]]||{};if(values[name]!==undefined)return values[name]}return null}
  function mapped(name,raw){var table=MAPS[name];return raw===null?null:table&&table[raw]!==undefined?table[raw]:table?'Unknown (raw: '+raw+')':raw}
  function normalized(models){
    var names=['hardware','baseVersion','model','sim','registration','roaming','operator','pdp','pdpType','apn','ipv4','ipv6','dns1','dns2','gateway','band','earfcn','pci','cell','tac','rsrp','rsrq','sinr','rssi','txTotal','rxTotal','txSession','rxSession','connDays','connHours','connMinutes','connSeconds','battery','batteryState','chargerStatus','chargerCurrent','outputCurrent'];
    var output={community:{raw:VERSION,value:VERSION,stale:false}};for(var i=0;i<names.length;i++){var raw=first(models,names[i]);output[names[i]]={raw:raw,value:mapped(names[i],raw),stale:false}}
    var ratNames=['ratSysMode','ratConnType','ratProto'],ratRaw=null,ratValue=null;for(var r=0;r<ratNames.length;r++){ratRaw=first(models,ratNames[r]);if(ratRaw!==null){ratValue=mapped(ratNames[r],ratRaw);break}}output.rat={raw:ratRaw,value:ratValue,stale:false};
    var duration=['connDays','connHours','connMinutes','connSeconds'].map(function(name){var value=output[name].raw;return value!==null&&/^\d+$/.test(value)?parseInt(value,10):0}),hasDuration=['connDays','connHours','connMinutes','connSeconds'].some(function(name){return output[name].raw!==null});
    function two(value){return ('0'+String(value)).slice(-2)}output.connectionTime={raw:hasDuration?duration.join(':'):null,value:hasDuration?(duration[0]+'d '+two(duration[1])+'h '+two(duration[2])+'m '+two(duration[3])+'s'):null,stale:false};return output;
  }
  function exactIdentity(values){return !values.model.stale&&!values.hardware.stale&&!values.baseVersion.stale&&/^(?:MF885|LV01)$/i.test(String(values.model.raw||''))&&values.hardware.raw==='MF96 Ver.D'&&values.baseVersion.raw==='2.5.94_release_MF855_NZ_CP_2.129.003'}
  function requestModel($,name,done){
    if(!endpoint(name)){done('unsupported');return}
    try{$.ajax({type:'GET',url:(w.location.protocol+'//'+w.location.host+'/xml_action.cgi?method=get&module=duster&file='+name),dataType:'xml',async:true,cache:false,timeout:10000,
      beforeSend:function(xhr){xhr.setRequestHeader('Authorization',w.getAuthHeader('GET'));xhr.setRequestHeader('Cache-Control','no-store, no-cache, must-revalidate')},
      success:function(xml){if(!xml||!xml.documentElement||String(xml.documentElement.nodeName).toUpperCase()!=='RGW'){done('parse');return}if(xml.getElementsByTagName('login_status').length&&String(xml.getElementsByTagName('login_status')[0].textContent||'').trim()){done('authentication');return}done(null,extract(name,xml))},
      error:function(xhr,state){var category=state==='timeout'?'timeout':xhr&&xhr.status===401?'authentication':xhr&&xhr.status?'http':'error';done(category)}
    })}catch(_){done('error')}
  }
  function install($){
    if(!$||!$.fn)return;
    $.fn.objDiagnostics=function(){
      var root=w.document.getElementById('Content');if(!root)throw new Error('Diagnostics content root is missing');root.innerHTML=w.callProductHTML('html/Diagnostics/Diagnostics.html');
      var refresh=w.document.getElementById('mfDiagRefresh'),copy=w.document.getElementById('mfDiagCopy'),status=w.document.getElementById('mfDiagStatus'),valuesRoot=w.document.getElementById('mfDiagValues');
      var fallback=w.document.getElementById('mfDiagCopyFallback'),reportBox=w.document.getElementById('mfDiagReport');
      var models={},values={},endpointStates={},busy=false,hasSuccess=false,xmlName='status1';
      var labels=[['community','Community version'],['model','Model'],['hardware','Hardware'],['baseVersion','Base firmware'],['sim','SIM'],['registration','Registration'],['roaming','Roaming'],['rat','Radio'],['operator','Operator'],['pdp','PDP'],['pdpType','PDP type'],['apn','APN'],['ipv4','IPv4'],['ipv6','IPv6'],['dns1','DNS 1'],['dns2','DNS 2'],['gateway','Gateway'],['band','Band'],['earfcn','EARFCN'],['pci','PCI'],['cell','Cell ID'],['tac','TAC / LAC'],['rsrp','RSRP'],['rsrq','RSRQ'],['sinr','SINR'],['rssi','RSSI'],['txTotal','WAN uploaded (total bytes)'],['rxTotal','WAN downloaded (total bytes)'],['txSession','WAN uploaded (session bytes)'],['rxSession','WAN downloaded (session bytes)'],['connectionTime','Connection time'],['battery','Battery %'],['batteryState','Battery state'],['chargerStatus','Charger status'],['chargerCurrent','Charge input current'],['outputCurrent','USB output current']];
      function setStatus(value,error){status.textContent=value;status.style.color=error?'#b42318':'#344054'}
      function renderValues(){
        valuesRoot.textContent='';for(var i=0;i<labels.length;i++){var key=labels[i][0],row=w.document.createElement('div'),title=w.document.createElement('span'),value=w.document.createElement('strong');
          row.style.cssText='border-bottom:1px solid #eaecf0;padding:5px 0;min-width:0';title.style.cssText='display:block;color:#667085;font-size:12px';title.textContent=labels[i][1];
          value.style.cssText='display:block;overflow-wrap:anywhere';value.textContent=values[key]&&values[key].value!==null?values[key].value:'Not returned';row.appendChild(title);row.appendChild(value);if(values[key]&&values[key].stale){row.style.opacity='.65';title.textContent+=' (previous)'}valuesRoot.appendChild(row)}
      }
      function mergePrevious(next){Object.keys(values).forEach(function(name){if((!next[name]||next[name].value===null)&&values[name]&&values[name].value!==null)next[name]={raw:values[name].raw,value:values[name].value,stale:true}});return next}
      function finishRead(failures){
        busy=false;refresh.disabled=false;copy.disabled=!hasSuccess;var failed=Object.keys(failures).length,identity=exactIdentity(values);renderValues();
        if(!hasSuccess){setStatus('Diagnostics unavailable. No previous values were replaced.',true);return}
        if(!identity){setStatus('Diagnostics read completed, but exact MF885 / Ver.D / 2.5.94 identity was not proven.'+(failed?' '+failed+' endpoint'+(failed===1?'':'s')+' failed.':''),true);return}
        setStatus(failed?'Partial diagnostics: '+failed+' endpoint'+(failed===1?'':'s')+' failed.':'Diagnostics updated from three fixed endpoints.',failed>0);
      }
      function run(){
        if(busy)return;busy=true;refresh.disabled=true;copy.disabled=true;fallback.hidden=true;models={};endpointStates={};var failures={},index=0;setStatus('Reading status1 (1 of 3)…');
        function next(){
          if(index>=ENDPOINTS.length){values=mergePrevious(normalized(models));hasSuccess=Object.keys(models).length>0;finishRead(failures);return}
          var name=ENDPOINTS[index++];setStatus('Reading '+name+' ('+index+' of 3)…');requestModel($,name,function(error,data){endpointStates[name]=error||'ok';if(error)failures[name]=error;else models[name]=data;next()})
        }
        next();
      }
      function safeItem(name){var item=values[name];return {value:item&&item.value!==null?item.value:null,stale:!!(item&&item.stale)}}
      function safeReport(){
        return JSON.stringify({schema:'mf885-community-safe-diagnostics/v1',community:safeItem('community'),identity:{model:safeItem('model'),hardware:safeItem('hardware'),baseFirmware:safeItem('baseVersion')},
          cellular:{sim:safeItem('sim'),registration:safeItem('registration'),roaming:safeItem('roaming'),rat:safeItem('rat'),operator:safeItem('operator'),pdp:safeItem('pdp'),pdpType:safeItem('pdpType'),band:safeItem('band'),rsrp:safeItem('rsrp'),rsrq:safeItem('rsrq'),sinr:safeItem('sinr'),rssi:safeItem('rssi')},
          wan:{txTotal:safeItem('txTotal'),rxTotal:safeItem('rxTotal'),txSession:safeItem('txSession'),rxSession:safeItem('rxSession'),connectionTime:safeItem('connectionTime')},battery:{percent:safeItem('battery'),state:safeItem('batteryState'),chargerStatus:safeItem('chargerStatus'),chargerCurrent:safeItem('chargerCurrent'),outputCurrent:safeItem('outputCurrent')},endpoints:endpointStates,privacy:{omitted:['raw XML','credentials','identifiers','addresses','APN','cell location','SMS and phone data']}},null,2);
      }
      function copyReport(){
        var report=safeReport();reportBox.value=report;fallback.hidden=true;
        function manual(){fallback.hidden=false;try{reportBox.focus();reportBox.select()}catch(_){}setStatus('Clipboard access failed. Select and copy the safe snapshot manually.',true)}
        if(w.navigator&&w.navigator.clipboard&&typeof w.navigator.clipboard.writeText==='function'){try{var promise=w.navigator.clipboard.writeText(report);if(promise&&typeof promise.then==='function'){promise.then(function(){setStatus('Safe snapshot copied.')},manual);return}}catch(_){}}
        try{fallback.hidden=false;reportBox.focus();reportBox.select();if(w.document.execCommand&&w.document.execCommand('copy')){fallback.hidden=true;setStatus('Safe snapshot copied.');return}}catch(_){}manual();
      }
      refresh.addEventListener('click',run);copy.addEventListener('click',copyReport);this.onLoad=function(){run()};this.onPost=function(){};this.onPostSuccess=function(){};this.setXMLName=function(value){xmlName=value||'status1'};return this;
    };
  }
  var api={id:VERSION,normalize:normalized,extract:extract,install:install};w.MF885CommunityDiagnostics=api;install(w.jQuery);
})(window);
