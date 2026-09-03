  var ttlRuntime={current:null,locked:false,nextAt:0,sequence:0};
  function nextTtlId(){ttlRuntime.sequence++;return serial('TTL30',ttlRuntime.sequence)}
  function ttlLog(id,kind,values){if(w.console&&typeof w.console.debug==='function')w.console.debug('[MF885]['+(id||'TTL30-NOT-STARTED')+'] '+kind,values||{})}
  function ttlCondition(id,name,expected,observed,passed){ttlLog(id,'condition '+name,{id:name,expected:expected,observed:observed,passed:passed})}
  function ttlValueInfo(value){value=String(value===null||value===undefined?'':value);var off=value==='off',canonical=/^[1-9][0-9]{0,2}$/.test(value),numeric=canonical?Number(value):null,inRange=canonical&&numeric>=1&&numeric<=255,accepted=off||inRange;return {raw:value,off:off,canonical:canonical,numeric:numeric,inRange:inRange,accepted:accepted}}
  function ttlLabel(value){var parsed=ttlValueInfo(value);return parsed.off?'Off':!parsed.accepted?'Unknown':value==='64'?'64 · Recommended':value==='65'?'65 · Compatibility':'TTL '+value}
  function syncTtlControls(){
    var refresh=node('ttlRefresh');if(!refresh)return;var busy=routerOwner!==null;
    refresh.disabled=busy;var buttons=w.document.querySelectorAll('button[data-ttl-value]');
    for(var i=0;i<buttons.length;i++)buttons[i].disabled=busy||ttlRuntime.locked||ttlRuntime.current===null;
    var custom=node('ttlCustom'),customApply=node('ttlCustomApply');if(custom)custom.disabled=busy||ttlRuntime.locked||ttlRuntime.current===null;if(customApply)customApply.disabled=busy||ttlRuntime.locked||ttlRuntime.current===null;
  }
  function renderTtl(value){
    ttlRuntime.current=value;node('ttlCurrent').textContent=ttlLabel(value);node('ttlCurrentDetail').textContent=value==='off'?'The extension is not rewriting forwarded IPv4 TTL.':'Forwarded IPv4 packets leave with TTL '+value+'. This resets to Off after restart.';
    var cardValue=value==='off'||value==='64'||value==='65'?value:'custom',cards=w.document.querySelectorAll('[data-ttl-card]');for(var i=0;i<cards.length;i++){var active=cards[i].getAttribute('data-ttl-card')===cardValue;cards[i].classList.toggle('active',active);cards[i].setAttribute('aria-current',active?'true':'false')}if(cardValue==='custom')node('ttlCustom').value=value;
    syncTtlControls();
  }
  function ttlState(doc){
    var id=doc&&doc.mfRequestId||nextTtlId(),root=doc&&doc.documentElement,models=children(root,'diagnostic'),model=models.length===1?models[0]:null,command=model?one(model,'command'):null,arg=model?one(model,'arg'):null,output=model?one(model,'output'):null,parsed=ttlValueInfo(arg),expectedOutput=parsed.off?'TTL_OFF':parsed.accepted?'TTL_VALUE':null,modelCount=models.length,commandExact=command==='ttl',outputExact=expectedOutput!==null&&output===expectedOutput,passed=modelCount===1&&commandExact&&parsed.accepted&&outputExact;
    ttlLog(id,'state variables',{modelCount:modelCount,command:command,arg:arg,output:output,argOff:parsed.off,argCanonicalDecimal:parsed.canonical,argNumeric:parsed.numeric,argInRange:parsed.inRange,argAccepted:parsed.accepted,acceptedMinimum:1,acceptedMaximum:255,expectedOutput:expectedOutput,automaticRetryCeiling:0});
    ttlCondition(id,'diagnostic_model_count',1,modelCount,modelCount===1);ttlCondition(id,'command_exact','ttl',command,commandExact);ttlCondition(id,'arg_is_off_or_canonical_decimal',true,parsed.off||parsed.canonical,parsed.off||parsed.canonical);ttlCondition(id,'numeric_arg_in_range_or_off','off|1..255',arg,parsed.accepted);ttlCondition(id,'output_matches_state',expectedOutput===null?'no accepted state':expectedOutput,output,outputExact);
    if(!passed)throw fault('E_TTL_RESPONSE','The router returned an invalid TTL state.',id,{modelCount:modelCount,command:command,arg:arg,output:output});
    return {value:arg,output:output,requestId:id};
  }
  function ttlXml(value){var parsed=ttlValueInfo(value);if(!parsed.accepted)throw fault('E_TTL_VALUE','TTL must be Off or an integer from 1 to 255.');return xmlDocument('<RGW><diagnostic><command>ttl</command><arg>'+parsed.raw+'</arg><output></output></diagnostic></RGW>')}
  function ttlGet(owner,trigger){
    var id=nextTtlId();ttlLog(id,'read variables',{trigger:trigger||'manual',owner:owner,model:'diagnostic',method:'GET',automaticRetryCeiling:0});
    return modelGet('diagnostic',owner).then(function(doc){var state=ttlState(doc);ttlRuntime.locked=false;ttlRuntime.nextAt=Date.now()+SNAPSHOT_POLL_MS;renderTtl(state.value);status('ttlStatus','TTL state '+ttlLabel(state.value)+' · '+state.requestId+' · automatic refresh in 30 seconds.');ttlLog(id,'terminal',{terminal_reason:'TTL_STATE_PROVEN',state:state.value,requestCount:1,retryCount:0});return state});
  }
  function readTtlState(trigger){
    if(!session)return Promise.resolve(null);if(!beginRouterOperation('ttl-read','ttlStatus'))return Promise.resolve(null);status('ttlStatus','Reading current TTL state…');
    return ttlGet('ttl-read',trigger).catch(function(error){showError('ttlStatus',error,'TTL state read failed.');throw error}).finally(function(){endRouterOperation('ttl-read')});
  }
  function setTtl(value){
    value=String(value===null||value===undefined?'':value);var id=nextTtlId(),parsed=ttlValueInfo(value),allowed=parsed.accepted,unlocked=!ttlRuntime.locked,currentKnown=ttlRuntime.current!==null,different=value!==ttlRuntime.current;
    ttlLog(id,'set variables',{requested:value,requestedOff:parsed.off,requestedCanonicalDecimal:parsed.canonical,requestedNumeric:parsed.numeric,requestedInRange:parsed.inRange,current:ttlRuntime.current,allowed:allowed,minimum:1,maximum:255,mutationLocked:ttlRuntime.locked,currentKnown:currentKnown,different:different,postCeiling:1,readbackGetCeiling:1,retryCeiling:0});
    ttlCondition(id,'requested_value_canonical',true,parsed.off||parsed.canonical,parsed.off||parsed.canonical);ttlCondition(id,'requested_value_in_range_or_off',true,allowed,allowed);ttlCondition(id,'mutation_unlocked',true,unlocked,unlocked);ttlCondition(id,'current_state_known',true,currentKnown,currentKnown);ttlCondition(id,'requested_value_differs',true,different,different);
    if(!allowed){showError('ttlStatus',fault('E_TTL_VALUE','TTL must be Off or an integer from 1 to 255.',id),'TTL was not changed.');return}
    if(!unlocked){showError('ttlStatus',fault('E_TTL_LOCKED','A previous TTL outcome is not proven. Read the current state first.',id),'TTL was not changed.');return}
    if(!currentKnown){showError('ttlStatus',fault('E_TTL_STATE_UNKNOWN','Read the current TTL state before changing it.',id),'TTL was not changed.');return}
    if(!different){status('ttlStatus','TTL is already '+ttlLabel(value)+'. No request was sent.');ttlLog(id,'terminal',{terminal_reason:'TTL_ALREADY_SET',requestCount:0,retryCount:0});return}
    if(value!=='off'&&!w.confirm('Set forwarded IPv4 TTL to '+value+' until the router restarts?')){ttlLog(id,'terminal',{terminal_reason:'TTL_OPERATOR_CANCELLED',requestCount:0,retryCount:0});return}
    if(!beginRouterOperation('ttl-set','ttlStatus'))return;var submitted=false,body=ttlXml(value);status('ttlStatus','Applying '+ttlLabel(value)+' once, then reading it back…');
    submitted=true;request({method:'POST',url:'/xml_action.cgi?method=set&module=duster&file=diagnostic',authorization:nextHeader('POST'),body:body,owner:'ttl-set'}).then(function(){return ttlGet('ttl-set','readback:'+id)}).then(function(state){var matches=state.value===value;ttlCondition(id,'readback_matches_request',value,state.value,matches);if(!matches)throw fault('E_TTL_READBACK','TTL readback does not match the requested value.',state.requestId,{requested:value,observed:state.value});status('ttlStatus','TTL is now '+ttlLabel(value)+'. One change and one readback completed; no retry was sent.');ttlLog(id,'terminal',{terminal_reason:'TTL_SET_VERIFIED',state:value,requestCount:2,postCount:1,getCount:1,retryCount:0})}).catch(function(error){if(submitted){ttlRuntime.locked=true;syncTtlControls();showError('ttlStatus',error,'TTL change outcome is unknown.',' Change outcome is unknown. No retry was sent. Use Read current state before another change.')}else showError('ttlStatus',error,'TTL was not changed.');ttlLog(id,'terminal',{terminal_reason:submitted?'TTL_SET_OUTCOME_UNKNOWN':'TTL_SET_NOT_SUBMITTED',postCount:submitted?1:0,retryCount:0})}).finally(function(){endRouterOperation('ttl-set')});
  }
