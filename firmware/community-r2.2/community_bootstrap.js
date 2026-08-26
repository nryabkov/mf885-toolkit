/* MF885 Community R2.2 cache-safe labels and exact identity */
(function(w){
  'use strict';
  var MODEL=/^(?:LV01|MF885)$/i;
  var HARDWARE='MF96 Ver.D';
  var VERSION='2.5.94_release_MF855_NZ_CP_2.129.003';
  function children(node,name){
    var result=[],wanted=String(name).toLowerCase(),items=node&&node.childNodes?node.childNodes:[];
    for(var i=0;i<items.length;i++)if(items[i].nodeType===1&&String(items[i].nodeName||'').toLowerCase()===wanted)result.push(items[i]);
    return result;
  }
  function one(node,name){
    var items=children(node,name);
    return items.length===1?String(items[0].textContent||'').trim():null;
  }
  function hasNonEmpty(node,name){
    var wanted=String(name).toLowerCase(),pending=[node];
    while(pending.length){
      var current=pending.pop(),items=current&&current.childNodes?current.childNodes:[];
      for(var i=0;i<items.length;i++)if(items[i].nodeType===1){
        if(String(items[i].nodeName||'').toLowerCase()===wanted&&String(items[i].textContent||'').trim())return true;
        pending.push(items[i]);
      }
    }
    return false;
  }
  function documentOf(value){
    var doc=value&&value.documentElement?value:null;
    try{doc=doc||new w.DOMParser().parseFromString(String(value||''),'text/xml')}catch(_){return null}
    return doc&&doc.documentElement&&doc.getElementsByTagName('parsererror').length===0?doc:null;
  }
  function exactStatus1Identity(value){
    var doc=documentOf(value),root=doc&&doc.documentElement;
    if(!root||String(root.nodeName||'').toUpperCase()!=='RGW')return false;
    if(hasNonEmpty(root,'login_status'))return false;
    if(children(root,'status').length)return false;
    var sysinfo=children(root,'sysinfo');
    if(sysinfo.length!==1)return false;
    var model=one(sysinfo[0],'model_name'),hardware=one(sysinfo[0],'hardware_version'),version=one(sysinfo[0],'version_num');
    return model!==null&&MODEL.test(model)&&hardware===HARDWARE&&version===VERSION;
  }
  function seedLabels(){
    var jq=w.jQuery;if(!jq||!jq.i18n)return false;
    jq.i18n.map=jq.i18n.map||{};
    jq.i18n.map.tDiagnostics='Diagnostics';
    jq.i18n.map.mDiagnostics='Diagnostics';
    return true;
  }
  w.MF885CommunityR22={id:'0.2.2-community-r2',seedLabels:seedLabels,exactStatus1Identity:exactStatus1Identity};
  seedLabels();
})(window);
