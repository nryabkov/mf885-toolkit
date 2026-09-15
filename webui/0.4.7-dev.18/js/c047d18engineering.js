/* Community 0.4.7-dev.18: explicit Engineering control, serialized with other router actions. */
(function(w){
  'use strict';
  var core=w.MF885Community047Dev18, bridge=core&&core.engineeringBridge;
  var state={current:null,locked:true,busy:false,epoch:0,bound:false};
  function node(id){return w.document.getElementById(id)}
  function fail(code){var e=new Error(code);e.mfCode=code;return e}
  function elements(parent,name){return Array.prototype.filter.call(parent&&parent.childNodes||[],function(n){return n.nodeType===1&&n.nodeName===name})}
  function parseState(doc){
    var root=doc&&doc.documentElement,wan=elements(root,'wan');
    if(!root||root.nodeName!=='RGW'||wan.length!==1||doc.getElementsByTagName('login_status').length)throw fail('E_ENGINEERING_RESPONSE');
    function one(name){var n=elements(wan[0],name);if(n.length!==1||Array.prototype.some.call(n[0].childNodes,function(c){return c.nodeType!==3}))throw fail('E_ENGINEERING_RESPONSE');return n[0].textContent.trim()}
    var mode=one('Engineering_mode'),interval=one('query_time_interval'),reg=elements(wan[0],'NW_register_status');
    if(!/^[01]$/.test(mode)||!/^[0-9]{1,4}$/.test(interval))throw fail('E_ENGINEERING_RESPONSE');
    return {mode:mode,interval:interval,registration:reg.length===1?reg[0].textContent.trim():null};
  }
  function same(a,b){return a.mode===b.mode&&a.interval===b.interval}
  function message(text,error){node('engineeringStatus').textContent=text;node('engineeringStatus').className='status'+(error?' error':'')}
  function check(epoch){if(epoch!==state.epoch||!bridge.sessionPresent())throw fail('E_ENGINEERING_SESSION')}
  function syncControls(){if(!node('engineeringRead'))return;var unavailable=!bridge||!bridge.sessionPresent(),busy=state.busy||!bridge||bridge.routerBusy();node('engineeringRead').disabled=unavailable||busy;node('engineeringMode').disabled=unavailable||busy;node('engineeringApply').disabled=unavailable||busy||state.locked||!state.current;node('engineeringForm').setAttribute('aria-busy',String(state.busy))}
  function show(current){state.current=current;node('engineeringCurrent').textContent=(current.mode==='1'?'Enabled':'Disabled')+' · interval '+current.interval+' minute(s)';node('engineeringMode').value=current.mode}
  function invalidate(){state.current=null;state.locked=true;node('engineeringCurrent').textContent='Not confirmed'}
  function begin(owner){if(!bridge||!bridge.sessionPresent()||state.busy)return false;var token=bridge.begin(owner,'engineeringStatus');if(!token)return false;state.busy=true;syncControls();return token}
  function end(owner,token){state.busy=false;bridge.end(owner,token);syncControls()}
  function get(owner,epoch){check(epoch);return bridge.get(owner).then(function(doc){check(epoch);return parseState(doc)})}
  function read(){
    var owner='engineering-read',epoch=state.epoch;var token=begin(owner);if(!token)return Promise.resolve(null);
    message('Reading the setting…');
    return get(owner,epoch).then(function(current){show(current);state.locked=false;message('Setting read. Choose Enabled or Disabled, then Apply.');return current}).catch(function(e){if(epoch===state.epoch){invalidate();message('The setting could not be read. Read again when the connection is available. ['+(e.mfCode||'E_ENGINEERING_READ')+']',true)}return null}).finally(function(){end(owner,token)});
  }
  function apply(value){
    if(value!=='0'&&value!=='1'){message('Choose Enabled or Disabled.',true);return Promise.resolve(null)}
    if(state.locked||!state.current){message('Read the current setting first.',true);return Promise.resolve(null)}
    var owner='engineering-write',epoch=state.epoch,previous=state.current,submitted=false,postFailure=null;
    var token=begin(owner);if(!token)return Promise.resolve(null);message('Checking the current setting…');
    return get(owner,epoch).then(function(current){
      if(!same(previous,current)){show(current);state.locked=true;message('The setting changed in another session. Read it again before applying.',true);return null}
      if(current.mode===value){show(current);message('Already '+(value==='1'?'Enabled.':'Disabled.'));return current}
      if(value==='1'&&current.interval!=='1'){show(current);state.locked=true;message('This version supports the 1 minute interval. Review the interval in Router settings first.',true);return null}
      check(epoch);submitted=true;message(value==='1'?'Enabling collection…':'Disabling collection… The modem may briefly reconnect.');
      return bridge.post(value,owner).catch(function(e){postFailure=e;return null}).then(function(){
        check(epoch);return get(owner,epoch);
      }).then(function(after){
        if(after.mode!==value||after.interval!==current.interval)throw fail('E_ENGINEERING_READBACK');
        show(after);state.locked=false;
        var text=value==='1'?'Enabled and confirmed. Allow about a minute for readings, then Refresh all.':'Disabled and confirmed.';
        if(value==='0'&&after.registration!=='1'&&after.registration!=='5')text+=' Network registration is not confirmed; refresh device status shortly.';
        if(postFailure)text+=' The initial reply was not confirmed; a separate read confirmed the setting.';
        message(text);return after;
      });
    }).catch(function(e){if(epoch===state.epoch){invalidate();message((submitted?'The result is not confirmed. No change was sent again. Read the setting to check it.':'The setting could not be checked; nothing was applied.')+' ['+(e.mfCode||'E_ENGINEERING_CHECK')+']',true)}return null}).finally(function(){end(owner,token)});
  }
  function reset(){state.epoch++;state.current=null;state.locked=true;node('engineeringCurrent').textContent='Not read';node('engineeringMode').value='0';message('Sign in and read the setting before applying a change.');syncControls()}
  function bind(){if(state.bound)return;state.bound=true;node('engineeringRead').addEventListener('click',read);node('engineeringForm').addEventListener('submit',function(event){event.preventDefault();apply(node('engineeringMode').value)});syncControls()}
  w.MF885Community047Dev18Engineering={version:'0.4.7-dev.18',state:state,parseState:parseState,read:read,apply:apply,reset:reset,syncControls:syncControls,bind:bind};
  if(w.document.readyState==='loading')w.document.addEventListener('DOMContentLoaded',bind);else bind();
})(window);
