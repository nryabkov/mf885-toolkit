/* MF885 Community 0.4.7-dev.6: explicit one-shot stock power operations. */
(function(w){
  'use strict';
  var app=w.MF885Community047Dev6,b=app.powerBridge,busy=false,consumed=false,appNonce=2;
  function el(id){return w.document.getElementById(id)}
  function syncControls(){var blocked=busy||b.busy()||!b.sessionPresent()||typeof w.fetch!=='function'||typeof w.AbortController!=='function';el('routerReboot').disabled=blocked;el('routerPowerOff').disabled=blocked}
  function parse(reply){if(!reply.body||reply.body.length>32768||/<!DOCTYPE|<!ENTITY/i.test(reply.body))throw Error('Invalid router response.');return b.parseXml(reply.body)}
  function get(url,authorization,challenge){
    var controller=new w.AbortController(),timer=w.setTimeout(function(){controller.abort()},10000);
    var headers={'Cache-Control':'no-store','Pragma':'no-cache'};if(authorization)headers.Authorization=authorization;
    return w.fetch(url,{method:'GET',headers:headers,credentials:'same-origin',cache:'no-store',redirect:'error',signal:controller.signal}).then(function(reply){
      if(reply.status!==200&&!(challenge&&reply.status===401))throw Error('Router rejected the request (HTTP '+reply.status+').');
      return reply.text().then(function(body){if(body.length>32768)throw Error('Oversized router response.');return {body:body,auth:reply.headers.get('WWW-Authenticate')||''}});
    }).finally(function(){w.clearTimeout(timer)});
  }
  function apply(action){
    if(action!=='reboot'&&action!=='poweroff')return Promise.reject(Error('Unknown power action.'));
    if(busy||!b.sessionPresent()||b.busy())return Promise.resolve(false);
    if(typeof w.fetch!=='function'||typeof w.AbortController!=='function')return Promise.reject(Error('This browser does not support power controls.'));
    var warning=action==='reboot'?'Restart this MF885 now? Connections will drop and RAM TTL settings will reset.':'Power off this MF885 now? Connections will drop. You must use its physical power button to turn it on again.';
    if(!w.confirm(warning))return Promise.resolve(false);
    if(!b.begin('power','powerStatus'))return Promise.resolve(false);
    busy=true;consumed=false;b.stopLive();syncControls();
    var auth=b.credentials(),header='',finalMessage='',accepted=false;
    el('powerStatus').textContent='Verifying the router before '+(action==='reboot'?'restart':'power off')+'…';
    return get('/login.cgi','',true).then(function(reply){
      if(reply.body.trim())throw Error('Unexpected login challenge body.');
      var c=b.parseChallenge(reply.auth);
      if(c.realm!==auth.realm)throw Error('Router authentication realm changed. Sign in again.');
      var pair=appNonce;appNonce+=2;var q=b.proof(c,auth.ha1,'GET','/cgi/protected.cgi',pair),h=b.proof(c,auth.ha1,'GET','/cgi/xml_action.cgi',pair+1);
      if(/["\\\r\n]/.test(c.realm+c.nonce))throw Error('Invalid authentication challenge.');
      header='Digest username="admin", realm="'+c.realm+'", nonce="'+c.nonce+'", uri="'+h.uri+'", response="'+h.response+'", qop=auth, nc='+h.nc+', cnonce="'+h.cnonce+'", client=APP';
      var query='Action=Digest&username=admin&realm='+encodeURIComponent(c.realm)+'&nonce='+encodeURIComponent(c.nonce)+'&response='+q.response+'&qop=auth&cnonce='+q.cnonce+'&temp=marvell&client=APP';
      return get('/login.cgi?'+query,header);
    }).then(function(reply){
      if(reply.body.trim()&&!/^HTTP\/1\.1 200 OK\r?\nContent-Type: text\/html\r?\nServer: Mongoose\/3\.0\r?\n\r?\n?$/.test(reply.body)){var doc=parse(reply);if(doc.getElementsByTagName('login_status').length)throw Error('APP sign-in was not confirmed.');}
      return get('/xml_action.cgi?method=get&module=duster&file=status1',header);
    }).then(function(reply){
      if(!b.exactIdentity(parse(reply)))throw Error('The exact MF885 / Ver.D / 2.5.94 identity was not confirmed.');
      consumed=true;
      return get('/xml_action.cgi?method=get&module=duster&file='+(action==='reboot'?'reset':'poweroff'),header);
    }).then(function(reply){
      if(reply.body.trim()){
        var doc=parse(reply),root=doc.documentElement,tag=action==='reboot'?'reboot':'shutdown';
        if(root.children.length!==1||root.children[0].nodeName!==tag||root.children[0].children.length||root.children[0].textContent.trim())throw Error('Unexpected power response.');
      }
      accepted=true;finalMessage='The router accepted the '+(action==='reboot'?'restart':'power-off')+' request. Its physical effect is not yet confirmed. '+(action==='reboot'?'Wait for the router to return, then sign in.':'Use the physical power button when you want to turn it on again.');
      return true;
    }).catch(function(){
      finalMessage=consumed?'The power request was attempted once; its result is unknown. Check the router before attempting another action.':'Power action stopped before sending the command. Sign in again and check the router.';
      return false;
    }).finally(function(){
      auth=null;header='';busy=false;b.end('power');b.finish(finalMessage,!accepted);syncControls();
    });
  }
  el('routerReboot').addEventListener('click',function(){apply('reboot')});
  el('routerPowerOff').addEventListener('click',function(){apply('poweroff')});
  w.MF885Community047Dev6Power={apply:apply,syncControls:syncControls};syncControls();
})(window);
