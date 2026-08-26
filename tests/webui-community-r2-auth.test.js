const test=require('node:test');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

const source=fs.readFileSync(path.join(__dirname,'../firmware/community-r2/community_auth.js'),'utf8');

function harness(options={}){
  const values=new Map(Object.entries(options.storage||{}));
  const calls={challenge:0,login:0,status:0,clear:0,reset:0,timeout:0};
  const events={};
  const timers=new Map();
  let nextTimer=1;
  let timerCalls=0;
  let now=options.now||1700000000000;
  function FakeDate(){this.getTime=()=>now;}
  const xml=options.xml||{
    documentElement:{nodeName:'RGW'},
    values:{login_status:'', 'sysinfo hardware_version':'MF96 Ver.D','sysinfo version_num':'2.5.94_release_MF855_NZ_CP_2.129.003'}
  };
  const sessionStorage={
    getItem:key=>values.has(key)?values.get(key):null,
    setItem:(key,value)=>{
      if(options.setItemThrows)throw new Error('storage write failed');
      values.set(key,String(value));
    },
    removeItem:key=>values.delete(key)
  };
  function jQuery(value){
    return {find(selector){return {text(){return (value&&value.values&&value.values[selector])||'';}};}};
  }
  jQuery.ajax=function(request){
    calls.status++;
    const headers={};
    if(request.beforeSend)request.beforeSend({setRequestHeader:(key,value)=>{headers[key]=value;}});
    assert.equal(request.type,'GET');
    assert.match(request.url,/file=status1$/);
    assert.match(headers.Authorization||'',/^Digest /);
    return {responseXML:xml};
  };
  const context={
    console,
    JSON,
    Math,
    Date:FakeDate,
    location:{protocol:'http:',host:'192.0.2.1'},
    sessionStorage:options.noStorage?null:sessionStorage,
    jQuery,
    $:jQuery,
    username:'admin',
    passwd:'secret',
    Authrealm:'Highwmg',
    nonce:'manual-nonce',
    Gnonce:'manual-nonce',
    AuthQop:'auth',
    GnCount:1,
    _zstimeSettingsIntervalID:0,
    clearInterval(){},
    setTimeout(callback,delay){
      timerCalls++;
      if(options.setTimeoutThrowsAt===timerCalls)throw new Error('timer creation failed');
      const id=nextTimer++;
      timers.set(id,{callback,delay});
      return id;
    },
    clearTimeout(id){timers.delete(id);},
    hex_md5:value=>crypto.createHash('md5').update(String(value)).digest('hex'),
    getValue(value){const parts=value.split('=');return parts[1].substring(1,parts[1].indexOf('"',2));},
    getAuthType(){calls.challenge++;if(options.challengeThrows)throw new Error('challenge failed');return `Digest realm="${options.realm||'Highwmg'}", nonce="fresh-nonce", qop="auth"`;},
    login_done:value=>String(value).includes('200 OK'),
    authentication(url){calls.login++;calls.loginUrl=url;return options.loginFails?'': '200 OK';},
    getAuthHeader(){return `Digest ${context.MF885CommunityAuth?context.MF885CommunityAuth.ha1():''}`;},
    clearAuthheader(){calls.clear++;},
    resetInterval(){calls.reset++;},
    AuthTimeout(){calls.timeout++;},
    AuthKickoff(){},
    AuthUnAuth(){},
    document:{addEventListener(name,callback){events[name]=callback;}},
    callProductHTML(){return '';},
    getHardware_Version(){return 'Ver.D';},
    initAPP(){}
  };
  context.window=context;
  vm.runInNewContext(source,context,{filename:'community_auth.js'});
  return {context,calls,values,events,timers,advance:value=>{now+=value;},key:'mf885.community.r2.tab-auth.v1'};
}

test('manual opt-in stores only a tab-scoped password-equivalent HA1 after exact status proof',()=>{
  const h=harness();
  assert.equal(h.context.MF885CommunityAuth.afterManualLogin(true),true);
  assert.equal(h.calls.status,1);
  assert.equal(h.context.passwd,'');
  const raw=h.values.get(h.key);
  assert.ok(raw);
  const saved=JSON.parse(raw);
  assert.deepEqual(Object.keys(saved).sort(),['expires','ha1','origin','realm','username','v']);
  assert.equal(saved.username,'admin');
  assert.equal(saved.realm,'Highwmg');
  assert.match(saved.ha1,/^[0-9a-f]{32}$/);
  assert.doesNotMatch(raw,/secret|manual-nonce|fresh-nonce|cnonce|response|password/i);
});

test('reload uses one fresh challenge, one Digest login and one protected read with no retry',()=>{
  const ha1=crypto.createHash('md5').update('admin:Highwmg:secret').digest('hex');
  const seed=JSON.stringify({v:1,origin:'http://192.0.2.1',username:'admin',realm:'Highwmg',ha1,expires:Date.now()+600000});
  const h=harness({storage:{'mf885.community.r2.tab-auth.v1':seed}});
  assert.equal(h.context.MF885CommunityAuth.resume(),true);
  assert.equal(h.context.MF885CommunityAuth.resume(),false);
  assert.deepEqual({challenge:h.calls.challenge,login:h.calls.login,status:h.calls.status},{challenge:1,login:1,status:1});
  assert.equal(h.context.nonce,'fresh-nonce');
  assert.equal(h.context.passwd,'');
  const loginUrl=new URL(h.calls.loginUrl);
  const cnonce=loginUrl.searchParams.get('cnonce');
  const ha2=crypto.createHash('md5').update('GET:/cgi/protected.cgi').digest('hex');
  const expected=crypto.createHash('md5').update(`${ha1}:fresh-nonce:00000001:${cnonce}:auth:${ha2}`).digest('hex');
  assert.equal(loginUrl.searchParams.get('response'),expected);
});

test('realm mismatch or failed login clears the record and never retries',()=>{
  const record=JSON.stringify({v:1,origin:'http://192.0.2.1',username:'admin',realm:'Highwmg',ha1:'a'.repeat(32),expires:Date.now()+600000});
  const mismatch=harness({realm:'OtherRealm',storage:{'mf885.community.r2.tab-auth.v1':record}});
  assert.equal(mismatch.context.MF885CommunityAuth.resume(),false);
  assert.equal(mismatch.values.has(mismatch.key),false);
  assert.deepEqual({challenge:mismatch.calls.challenge,login:mismatch.calls.login,status:mismatch.calls.status},{challenge:1,login:0,status:0});

  const failed=harness({loginFails:true,storage:{'mf885.community.r2.tab-auth.v1':record}});
  assert.equal(failed.context.MF885CommunityAuth.resume(),false);
  assert.equal(failed.values.has(failed.key),false);
  assert.deepEqual({challenge:failed.calls.challenge,login:failed.calls.login,status:failed.calls.status},{challenge:1,login:1,status:0});

  const thrown=harness({challengeThrows:true,storage:{'mf885.community.r2.tab-auth.v1':record}});
  assert.equal(thrown.context.MF885CommunityAuth.resume(),false);
  assert.equal(thrown.values.has(thrown.key),false);
  assert.deepEqual({challenge:thrown.calls.challenge,login:thrown.calls.login,status:thrown.calls.status},{challenge:1,login:0,status:0});
});

test('failed storage renewal after auto-login clears HA1 and keeps the login page',()=>{
  const record=JSON.stringify({v:1,origin:'http://192.0.2.1',username:'admin',realm:'Highwmg',ha1:'a'.repeat(32),expires:Date.now()+600000});
  const h=harness({setItemThrows:true,storage:{'mf885.community.r2.tab-auth.v1':record}});
  assert.equal(h.context.MF885CommunityAuth.resume(),false);
  assert.deepEqual({challenge:h.calls.challenge,login:h.calls.login,status:h.calls.status},{challenge:1,login:1,status:1});
  assert.equal(h.values.has(h.key),false);
  assert.equal(h.context.MF885CommunityAuth.ha1(),'');
  assert.equal(h.timers.size,0);
  assert.equal(h.calls.clear,0);
  assert.equal(h.context.MF885CommunityAuth.resume(),false);
  assert.deepEqual({challenge:h.calls.challenge,login:h.calls.login,status:h.calls.status},{challenge:1,login:1,status:1});
});

test('failed optional save after manual login keeps only the current authenticated page',()=>{
  const h=harness({setItemThrows:true});
  assert.equal(h.context.MF885CommunityAuth.afterManualLogin(true),true);
  assert.equal(h.calls.status,1);
  assert.equal(h.context.passwd,'');
  assert.match(h.context.MF885CommunityAuth.ha1(),/^[0-9a-f]{32}$/);
  assert.equal(h.values.has(h.key),false);
  assert.equal(h.timers.size,0);
});

test('wrong protected status, logout, timeout and missing sessionStorage fail closed',()=>{
  const wrong=harness({xml:{documentElement:{nodeName:'RGW'},values:{login_status:'','sysinfo hardware_version':'Other','sysinfo version_num':'2.5.94'}}});
  assert.equal(wrong.context.MF885CommunityAuth.afterManualLogin(true),false);
  assert.equal(wrong.values.has(wrong.key),false);

  const wrongPatch=harness({xml:{documentElement:{nodeName:'RGW'},values:{login_status:'','sysinfo hardware_version':'MF96 Ver.D','sysinfo version_num':'2.5.94_unreviewed'}}});
  assert.equal(wrongPatch.context.MF885CommunityAuth.afterManualLogin(true),false);
  assert.equal(wrongPatch.values.has(wrongPatch.key),false);

  const logout=harness();
  assert.equal(logout.context.MF885CommunityAuth.afterManualLogin(true),true);
  logout.context.clearAuthheader();
  assert.equal(logout.values.has(logout.key),false);
  assert.equal(logout.calls.clear,1);

  const timeout=harness();
  assert.equal(timeout.context.MF885CommunityAuth.afterManualLogin(true),true);
  timeout.context.AuthTimeout();
  assert.equal(timeout.values.has(timeout.key),false);
  assert.equal(timeout.calls.timeout,1);

  const unsupported=harness({noStorage:true});
  assert.equal(unsupported.context.MF885CommunityAuth.supported(),false);
  assert.equal(unsupported.context.MF885CommunityAuth.resume(),false);
  assert.equal(unsupported.calls.challenge,0);
});

test('only keyboard, touch or mouse activity extends the ten-minute tab lease',()=>{
  const h=harness();
  assert.equal(h.context.MF885CommunityAuth.afterManualLogin(true),true);
  const first=JSON.parse(h.values.get(h.key));
  assert.deepEqual(Object.keys(h.events).sort(),['keydown','mousedown','touchstart']);
  assert.equal(h.timers.size,1);
  h.context.resetInterval();
  assert.equal(JSON.parse(h.values.get(h.key)).expires,first.expires);
  h.advance(1234);
  h.events.keydown();
  const second=JSON.parse(h.values.get(h.key));
  assert.equal(second.expires,first.expires+1234);
  assert.equal(h.timers.size,1);
  const expiry=[...h.timers.values()][0].callback;
  expiry();
  assert.equal(h.values.has(h.key),false);
  assert.equal(h.calls.clear,1);
});

test('an overdue browser timer cannot extend the stored or in-memory HA1 lease',()=>{
  const read=harness();
  assert.equal(read.context.MF885CommunityAuth.afterManualLogin(true),true);
  read.advance(600001);
  assert.equal(read.context.MF885CommunityAuth.ha1(),'');
  assert.equal(read.values.has(read.key),false);
  assert.equal(read.timers.size,0);

  const activity=harness();
  assert.equal(activity.context.MF885CommunityAuth.afterManualLogin(true),true);
  activity.advance(600001);
  activity.events.keydown();
  assert.equal(activity.context.MF885CommunityAuth.ha1(),'');
  assert.equal(activity.values.has(activity.key),false);
  assert.equal(activity.timers.size,0);
  assert.equal(activity.calls.clear,1);
});

test('failed activity renewal preserves the earlier expiry timer',()=>{
  const h=harness({setTimeoutThrowsAt:2});
  assert.equal(h.context.MF885CommunityAuth.afterManualLogin(true),true);
  assert.equal(h.timers.size,1);
  const originalExpiry=[...h.timers.values()][0].callback;
  h.advance(1234);
  h.events.keydown();
  assert.equal(h.values.has(h.key),false);
  assert.match(h.context.MF885CommunityAuth.ha1(),/^[0-9a-f]{32}$/);
  assert.equal(h.timers.size,1);
  originalExpiry();
  assert.equal(h.context.MF885CommunityAuth.ha1(),'');
  assert.equal(h.calls.clear,1);
});
