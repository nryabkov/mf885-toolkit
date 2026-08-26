const test=require('node:test');
const assert=require('node:assert/strict');
const child=require('node:child_process');
const crypto=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

let parseHTML=null;
for(const candidate of ['linkedom','/opt/openclaw-runtime/releases/2026.7.1-2/lib/node_modules/openclaw/node_modules/linkedom']){try{({parseHTML}=require(candidate));break}catch(_){}}
const root=path.resolve(__dirname,'..');
const generated=child.spawnSync('python3',['-c',"from pathlib import Path; import mf885_community_r22 as r; print(r._derive_auth(Path('.')).decode())"],{cwd:root,encoding:'utf8',env:{...process.env,PYTHONPATH:path.join(root,'tools')}});
if(generated.status!==0)throw new Error(generated.stderr);
const source=generated.stdout;
const bootstrap=fs.readFileSync(path.join(root,'firmware/community-r2.2/community_bootstrap.js'),'utf8');
const KEY='mf885.community.r2.tab-auth.v1';
const NOW=1700000000000;

function identity(model='LV01',hardware='MF96 Ver.D',version='2.5.94_release_MF855_NZ_CP_2.129.003'){
  return `<RGW><sysinfo><model_name>${model}</model_name><hardware_version>${hardware}</hardware_version><version_num>${version}</version_num></sysinfo></RGW>`;
}

function harness(options={}){
  const {window}=parseHTML('<html><body></body></html>');
  const values=new Map(Object.entries(options.storage||{}));
  const calls={challenge:0,login:0,status:0,clear:0};
  const timers=new Map();let nextTimer=1,now=NOW;
  function FakeDate(){this.getTime=()=>now}
  const sessionStorage={
    getItem:key=>values.has(key)?values.get(key):null,
    setItem:(key,value)=>{if(options.setItemThrows)throw new Error('storage write failed');values.set(key,String(value))},
    removeItem:key=>values.delete(key)
  };
  function jQuery(value){return {find(selector){return {text(){const nodes=value&&value.getElementsByTagName?value.getElementsByTagName(selector):[];let text='';for(let i=0;i<nodes.length;i++)text+=nodes[i].textContent||'';return text}}}}}
  jQuery.i18n={map:{}};
  jQuery.ajax=request=>{
    calls.status++;
    const headers={};
    if(request.beforeSend)request.beforeSend({setRequestHeader:(key,value)=>{headers[key]=value}});
    assert.equal(request.type,'GET');assert.match(request.url,/file=status1$/);assert.match(headers.Authorization||'',/^Digest /);
    return {responseXML:new window.DOMParser().parseFromString(options.xml||identity(),'text/xml')};
  };
  Object.assign(window,{
    console,JSON,Math,Date:FakeDate,location:{protocol:'http:',host:'192.0.2.1'},sessionStorage,jQuery,$:jQuery,
    username:'admin',passwd:'secret',Authrealm:'Highwmg',nonce:'manual-nonce',Gnonce:'manual-nonce',AuthQop:'auth',GnCount:1,_zstimeSettingsIntervalID:0,
    clearInterval(){},setTimeout(callback,delay){const id=nextTimer++;timers.set(id,{callback,delay});return id},clearTimeout(id){timers.delete(id)},
    hex_md5:value=>crypto.createHash('md5').update(String(value)).digest('hex'),
    getValue(value){const parts=value.split('=');return parts[1].substring(1,parts[1].indexOf('"',2))},
    getAuthType(){calls.challenge++;return 'Digest realm="Highwmg", nonce="fresh-nonce", qop="auth"'},
    login_done:value=>String(value).includes('200 OK'),authentication(){calls.login++;return '200 OK'},
    getAuthHeader(){return `Digest ${window.MF885CommunityAuth?window.MF885CommunityAuth.ha1():''}`},
    clearAuthheader(){calls.clear++},resetInterval(){},AuthTimeout(){},AuthKickoff(){},AuthUnAuth(){},
    callProductHTML(){return ''},getHardware_Version(){return 'Ver.D'},initAPP(){}
  });
  window.document.addEventListener=()=>{};
  const context=window;vm.createContext(context);vm.runInContext(bootstrap,context,{filename:'r22boot.js'});vm.runInContext(source,context,{filename:'r22auth.js'});
  if(options.noHelper)delete window.MF885CommunityR22;
  if(options.throwingHelper)window.MF885CommunityR22.exactStatus1Identity=()=>{throw new Error('identity helper failed')};
  return {window,calls,values,timers,key:KEY};
}

function savedRecord(){
  const ha1=crypto.createHash('md5').update('admin:Highwmg:secret').digest('hex');
  return JSON.stringify({v:1,origin:'http://192.0.2.1',username:'admin',realm:'Highwmg',ha1,expires:NOW+600000});
}

test('R2.2 auth stores the same tab-scoped schema only after the shared exact identity proof',{skip:!parseHTML},()=>{
  const h=harness();
  assert.equal(h.window.MF885CommunityAuth.id,'0.2.2-community-r2');
  assert.equal(h.window.MF885CommunityAuth.afterManualLogin(true),true);
  assert.equal(h.calls.status,1);assert.equal(h.window.passwd,'');
  const stored=JSON.parse(h.values.get(KEY));
  assert.deepEqual(Object.keys(stored).sort(),['expires','ha1','origin','realm','username','v']);
  assert.match(stored.ha1,/^[0-9a-f]{32}$/);assert.doesNotMatch(h.values.get(KEY),/secret|nonce|password/i);
});

test('R2.2 auth rejects wrong, missing, ambiguous, nested and unauthenticated status identity forms',{skip:!parseHTML},()=>{
  const exact=identity();
  const invalid=[
    identity('LV02'),identity('','MF96 Ver.D'),identity('LV01','MF96 Ver.C'),identity('LV01','MF96 Ver.D','2.5.94'),
    '<RGW><decoy><sysinfo><model_name>LV01</model_name><hardware_version>MF96 Ver.D</hardware_version><version_num>2.5.94_release_MF855_NZ_CP_2.129.003</version_num></sysinfo></decoy></RGW>',
    exact.replace('</RGW>','<status><sysinfo><model_name>LV01</model_name><hardware_version>MF96 Ver.D</hardware_version><version_num>2.5.94_release_MF855_NZ_CP_2.129.003</version_num></sysinfo></status></RGW>'),
    exact.replace('</sysinfo>','</sysinfo><sysinfo><model_name>LV01</model_name><hardware_version>MF96 Ver.D</hardware_version><version_num>2.5.94_release_MF855_NZ_CP_2.129.003</version_num></sysinfo>'),
    exact.replace('</sysinfo>','<model_name>LV01</model_name></sysinfo>'),
    exact.replace('</RGW>','<login_status>UNAUTHORIZED</login_status></RGW>'),
    '<OTHER>'+exact+'</OTHER>','<RGW><sysinfo>'
  ];
  for(const xml of invalid){
    const h=harness({xml});assert.equal(h.window.MF885CommunityAuth.afterManualLogin(true),false,xml);
    assert.equal(h.calls.status,1);assert.equal(h.values.has(KEY),false);assert.equal(h.window.MF885CommunityAuth.ha1(),'');
  }
  for(const option of [{noHelper:true},{throwingHelper:true}]){
    const h=harness(option);assert.equal(h.window.MF885CommunityAuth.afterManualLogin(true),false);assert.equal(h.values.has(KEY),false);
  }
});

test('R2.2 auth resumes an existing R2 tab record once, but clears it on strict identity failure',{skip:!parseHTML},()=>{
  const exact=harness({storage:{[KEY]:savedRecord()}});
  assert.equal(exact.window.MF885CommunityAuth.resume(),true);assert.equal(exact.window.MF885CommunityAuth.resume(),false);
  assert.deepEqual({challenge:exact.calls.challenge,login:exact.calls.login,status:exact.calls.status},{challenge:1,login:1,status:1});
  assert.equal(exact.values.has(KEY),true);assert.equal(exact.timers.size,1);

  const rejected=harness({xml:identity('LV02'),storage:{[KEY]:savedRecord()}});
  assert.equal(rejected.window.MF885CommunityAuth.resume(),false);assert.equal(rejected.values.has(KEY),false);assert.equal(rejected.window.MF885CommunityAuth.ha1(),'');
  assert.deepEqual({challenge:rejected.calls.challenge,login:rejected.calls.login,status:rejected.calls.status},{challenge:1,login:1,status:1});
  assert.equal(rejected.window.MF885CommunityAuth.resume(),false);
  assert.deepEqual({challenge:rejected.calls.challenge,login:rejected.calls.login,status:rejected.calls.status},{challenge:1,login:1,status:1});
});

test('R2.2 auth source keeps the no-retry lifecycle and delegates identity to the bootstrap',()=>{
  assert.equal((source.match(/jQuery\.ajax/g)||[]).length,1);
  assert.equal((source.match(/authentication\(url\)/g)||[]).length,1);
  assert.match(source,/MF885CommunityR22\.exactStatus1Identity\(xml\) === true/);
  assert.doesNotMatch(source,/find\("sysinfo hardware_version"\)|find\("sysinfo version_num"\)/);
});
