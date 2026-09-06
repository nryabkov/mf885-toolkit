/* MF885 Community R4.6: explicit native-state reads; no timers or write retries. */
(function(w){
  'use strict';
  var core=w.MF885CommunityR46,bridge=core&&core.ttlBridge;
  var state={current:null,locked:true,busy:false,dirty:false,epoch:0,bound:false};
  function node(id){return w.document.getElementById(id)}
  function valueInfo(value){var canonical=typeof value==='string'&&/^[1-9][0-9]{0,2}$/.test(value);return {accepted:value==='off'||canonical&&Number(value)<=255,value:value==='off'?0:canonical?Number(value):null}}
  function label(value){return value===0?'Off · подмена выключена':String(value)}
  function status(phase,text){node('ttlStatus').textContent=text;node('ttlStatus').setAttribute('data-phase',phase);node('ttlStatus').classList.toggle('error',phase==='unknown'||phase==='unavailable'||phase==='rejected')}
  function problem(code){var e=new Error(code);e.mfCode=code;return e}
  function elements(parent){return Array.prototype.filter.call(parent&&parent.childNodes||[],function(n){return n.nodeType===1})}
  function plain(parent){return Array.prototype.every.call(parent&&parent.childNodes||[],function(n){return n.nodeType===1||n.nodeType===3&&!/\S/.test(n.nodeValue)||n.nodeType===8})}
  function strictState(doc){
    var root=doc&&doc.documentElement,models=elements(root),model=models[0],fields=elements(model);
    if(!root||root.nodeName!=='RGW'||root.attributes.length||models.length!==1||model.nodeName!=='diagnostic'||model.attributes.length||fields.length!==3||!plain(root)||!plain(model))throw problem('E_TTL_RESPONSE');
    var names={},output=null;
    fields.forEach(function(field){var name=field.nodeName;if(['command','arg','output'].indexOf(name)<0||names[name]||field.attributes.length||elements(field).length)throw problem('E_TTL_RESPONSE');names[name]=true;if(name==='output')output=field.textContent});
    var match=/^r46:([0-9a-f]{8}):([0-9a-f]{2})$/.exec(output||'');
    if(!match)throw problem('E_TTL_RESPONSE');
    return {generation:parseInt(match[1],16),value:parseInt(match[2],16)};
  }
  function advancing(before,after){var delta=(after.generation-before.generation)>>>0;return delta>0&&delta<0x80000000}
  function checkEpoch(epoch){if(state.epoch!==epoch||!bridge.sessionPresent())throw problem('E_TTL_SESSION')}
  function get(owner,epoch){checkEpoch(epoch);return bridge.get(owner).then(function(doc){checkEpoch(epoch);return strictState(doc)})}
  function fresh(before,after){if(!advancing(before,after))throw problem('E_TTL_STALE');return after}
  function render(current){state.current=current;node('ttlCurrent').textContent=label(current.value);node('ttlFreshness').textContent='Подтверждено чтением в '+new Date().toLocaleTimeString()+'. Это последнее прочитанное состояние.'}
  function inputHint(){var raw=node('ttlValue').value,valid=valueInfo(raw).accepted&&raw!=='off';node('ttlValue').setAttribute('aria-invalid',raw!==''&&!valid?'true':'false');node('ttlInputHint').classList.toggle('error',raw!==''&&!valid);node('ttlInputHint').textContent=raw!==''&&!valid?'Введите целое число от 1 до 255 без пробелов, знака и ведущих нулей.':valid&&Number(raw)<32?'Малое значение TTL может помешать доставке пакетов.':'Значение изменится только после нажатия «Применить».'}
  function syncControls(){
    if(!node('ttlRead'))return;
    var signed=!!bridge&&bridge.sessionPresent(),busy=state.busy||!bridge||bridge.routerBusy(),ready=signed&&!busy&&!state.locked&&state.current!==null;
    node('ttlRead').disabled=!signed||busy;node('ttlValue').disabled=!signed||busy;
    node('ttlApply').disabled=!ready;node('ttlOff').disabled=!ready;
  }
  function begin(owner){if(!bridge||!bridge.sessionPresent()||state.busy)return false;if(!bridge.begin(owner,'ttlStatus'))return false;state.busy=true;syncControls();return true}
  function end(owner){state.busy=false;bridge.end(owner);syncControls()}
  function read(){
    var owner='ttl-read',epoch=state.epoch;if(!begin(owner))return Promise.resolve(null);
    status('pending','Читаю состояние и проверяю свежесть второго ответа…');
    return get(owner,epoch).then(function(first){return get(owner,epoch).then(function(second){return fresh(first,second)})}).then(function(current){state.locked=false;render(current);status('ready','Состояние подтверждено. Можно применить новое значение или выключить подмену.');return current}).catch(function(error){if(state.epoch===epoch){state.locked=true;status('unavailable','Не удалось подтвердить свежее состояние. Изменения заблокированы; повторите чтение вручную. ['+(error.mfCode||'E_TTL_READ')+']')}return null}).finally(function(){end(owner)});
  }
  function setValue(value){
    var parsed=valueInfo(value);
    if(!parsed.accepted){status('rejected','Допустимо целое число от 1 до 255. Для отключения используйте отдельную кнопку Off.');inputHint();return Promise.resolve(null)}
    if(state.locked||!state.current){status('unavailable','Сначала прочитайте свежее состояние TTL.');return Promise.resolve(null)}
    var owner='ttl-write',epoch=state.epoch,submitted=false,baseline=null;
    if(!begin(owner))return Promise.resolve(null);
    status('pending','Проверяю текущее состояние перед изменением…');
    return get(owner,epoch).then(function(current){
      baseline=fresh(state.current,current);render(baseline);
      if(baseline.value===parsed.value){status('ready','Уже установлено '+label(baseline.value)+'. Запись не отправлялась.');return null}
      checkEpoch(epoch);submitted=true;status('pending','Отправляю одно изменение и читаю результат…');
      return bridge.post(value,owner).then(function(){return get(owner,epoch)}).then(function(after){
        fresh(baseline,after);render(after);
        if(after.value!==parsed.value){state.locked=true;status('rejected','После записи прочитано другое значение: '+label(after.value)+'. Изменение не подтверждено. Для следующей попытки прочитайте состояние заново.');return after}
        state.locked=false;if(node('ttlValue').value===value)state.dirty=false;
        status('applied','Применено: '+label(after.value)+'. Состояние обработчика подтверждено свежим чтением.');return after;
      });
    }).catch(function(error){if(state.epoch===epoch){state.locked=true;status(submitted?'unknown':'unavailable',submitted?'Исход изменения неизвестен: связь или проверка ответа прервалась. Повторная запись не отправлялась. Прочитайте состояние вручную.':'Свежее состояние перед записью не подтверждено. Изменение не отправлялось; прочитайте состояние вручную.')}return null}).finally(function(){end(owner)});
  }
  function reset(){state.epoch++;state.current=null;state.locked=true;state.dirty=false;node('ttlValue').value='';node('ttlCurrent').textContent='Не прочитано';node('ttlFreshness').textContent='Прочитайте состояние, чтобы открыть управление.';status('unavailable','Войдите в интерфейс и прочитайте состояние TTL.');inputHint();syncControls()}
  function bind(){if(state.bound)return;state.bound=true;node('ttlRead').addEventListener('click',read);node('ttlForm').addEventListener('submit',function(event){event.preventDefault();var value=node('ttlValue').value;if(value==='off'){status('rejected','Для отключения используйте отдельную кнопку Off.');return}setValue(value)});node('ttlOff').addEventListener('click',function(){setValue('off')});node('ttlValue').addEventListener('input',function(){state.dirty=true;inputHint()});inputHint();syncControls()}
  w.MF885CommunityR46TTL={version:'0.4.6-community-r2',state:state,valueInfo:valueInfo,strictState:strictState,advancing:advancing,read:read,setValue:setValue,reset:reset,syncControls:syncControls,bind:bind};
  if(w.document.readyState==='loading')w.document.addEventListener('DOMContentLoaded',bind);else bind();
})(window);
