const test=require('node:test');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

let parseHTML=null;
for(const candidate of ['linkedom','/opt/openclaw-runtime/releases/2026.7.1-2/lib/node_modules/openclaw/node_modules/linkedom']){try{({parseHTML}=require(candidate));break}catch(_){}}

const root=path.resolve(__dirname,'..');
const directory=path.join(root,'firmware/community-r2.2');
const manifest=JSON.parse(fs.readFileSync(path.join(directory,'manifest.json'),'utf8'));
const readme=fs.readFileSync(path.join(directory,'README.md'),'utf8');
const transformer=fs.readFileSync(path.join(root,'tools/mf885_community_r22.py'),'utf8');
const bootstrap=fs.readFileSync(path.join(directory,'community_bootstrap.js'),'utf8');
const css=fs.readFileSync(path.join(directory,'community_ui.css'),'utf8');
const digest=value=>crypto.createHash('sha256').update(value).digest('hex');

test('Community R2.2 manifest pins every source and records bounded live qualification',()=>{
  assert.deepEqual(fs.readdirSync(directory).sort(),[
    'Diagnostics.html','README.md','SMS.html','community_bootstrap.js','community_ui.css','manifest.json'
  ]);
  for(const source of manifest.sources){
    const bytes=fs.readFileSync(path.resolve(directory,source.file));
    assert.equal(bytes.length,source.size,source.target);
    assert.equal(digest(bytes),source.sha256,source.target);
  }
  assert.equal(manifest.logical_id,'0.2.2-community-r2');
  assert.equal(manifest.artifact.file,'MF885_Community_0.2.2-community-r2-cafe-r2.bin');
  assert.equal(manifest.artifact.size,8323644);
  assert.equal(manifest.artifact.sha256,'80e94750bf820e1fdbf6f51b8b2462cad633e28d19571610ce744bac7e6e04d5');
  assert.equal(manifest.artifact.portable_plaintext_sha256,'c712f4774d8d4dc05e1a70ddd34cb8f508e705705b9cb16e3174bbb991d612ec');
  assert.deepEqual(manifest.logical_change_counts,{replaced:10,added:11,removed:18});
  assert.equal(manifest.webi_padding_bytes_remaining,162428);
  assert.equal(manifest.live_tested,true);
  assert.equal(manifest.release_status,'experimental-live-qualified-canary');
  assert.equal(manifest.capabilities.static_assets_live_verified,true);
  assert.equal(manifest.capabilities.exact_served_assets_live_verified,21);
  assert.equal(manifest.capabilities.removed_locale_routes_live_verified,18);
  assert.equal(manifest.capabilities.same_unit_postboot_live_verified,true);
  assert.equal(manifest.capabilities.authenticated_ui_live_verified,false);
  assert.equal(manifest.capabilities.semantic_ui_live_verified,false);
  for(const field of ['sms_send_live_tested','inbox_delete_live_tested','flash_qualified','restore_allowlisted','stable'])assert.equal(manifest[field],false,field);
  assert.match(readme,/permanently\s+brick/i);
  assert.match(readme,/installed\s+once/i);
  assert.match(readme,/rollback\s+remain(?:s)?\s+unproved/i);
});

test('Community R2.2 uses unique cache-safe assets and seeds labels before both menu builds',()=>{
  for(const route of ['js/r22boot.js','js/r22auth.js','js/r22diag.js','js/panel/SMS/r22sms.js','js/panel/r22dash.js','html/Community/r22dash.html','css/r22ui.css'])assert.equal((transformer.match(new RegExp(route.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'g'))||[]).length>=1,true,route);
  assert.match(transformer,/R2\.2 cache-safe diagnostics loaders/);
  assert.match(transformer,/R2\.2 cache-safe auth loader/);
  assert.match(transformer,/strict auth identity gate/);
  assert.match(transformer,/R2\.2 cache-safe SMS loader/);
  assert.match(transformer,/cache-safe Diagnostics labels/);
  assert.match(transformer,/createMenuFromXML\(\)/);
  assert.doesNotMatch(transformer,/r22(?:boot|auth|diag|sms|dash)\.js\?/);
});

test('Community R2.2 bootstrap repairs a stale i18n map and strictly matches the live status1 identity',{skip:!parseHTML},()=>{
  const {window}=parseHTML('<html><body></body></html>');
  window.jQuery={i18n:{map:{tDashboard:'Dashboard'}}};
  const context={window,document:window.document,console,String,RegExp,Array,Object,Boolean,Error};vm.createContext(context);vm.runInContext(bootstrap,context);
  assert.equal(window.jQuery.i18n.map.tDiagnostics,'Diagnostics');
  assert.equal(window.jQuery.i18n.map.mDiagnostics,'Diagnostics');
  const exact='<RGW><sysinfo><model_name>LV01</model_name><hardware_version>MF96 Ver.D</hardware_version><version_num>2.5.94_release_MF855_NZ_CP_2.129.003</version_num></sysinfo></RGW>';
  assert.equal(window.MF885CommunityR22.exactStatus1Identity(exact),true);
  assert.equal(window.MF885CommunityR22.exactStatus1Identity(exact.replace('LV01','MF885')),true);
  assert.equal(window.MF885CommunityR22.exactStatus1Identity(exact.replace('<RGW><sysinfo>','<RGW><status><sysinfo>').replace('</sysinfo></RGW>','</sysinfo></status></RGW>')),false);
  for(const invalid of [
    exact.replace('LV01','LV02'),
    exact.replace('MF96 Ver.D','MF96 Ver.C'),
    exact.replace('2.5.94_release_MF855_NZ_CP_2.129.003','2.5.94'),
    exact.replace('</RGW>','<login_status>UNAUTHORIZED</login_status></RGW>'),
    exact.replace('</sysinfo>','<decoy><login_status>TIMEOUT</login_status></decoy></sysinfo>'),
    exact.replace('</sysinfo>','<model_name>LV01</model_name></sysinfo>'),
    exact.replace('</RGW>','<sysinfo><model_name>LV01</model_name><hardware_version>MF96 Ver.D</hardware_version><version_num>2.5.94_release_MF855_NZ_CP_2.129.003</version_num></sysinfo></RGW>'),
    '<RGW><decoy>'+exact+'</decoy></RGW>',
    '<RGW><sysinfo><model_name>LV01</model_name></sysinfo></RGW>'
  ])assert.equal(window.MF885CommunityR22.exactStatus1Identity(invalid),false,invalid);
});

test('Community R2.2 visual system fixes the checkbox and stays legacy-browser scoped',()=>{
  assert.match(css,/#mfRememberTab\s*\{[^}]*width:16px !important;[^}]*height:16px !important;/s);
  assert.match(css,/\.mfRememberRow/);assert.match(css,/#mfCommunityDashboard/);assert.match(css,/\.mfCommunityShell/);
  assert.doesNotMatch(css,/display\s*:\s*(?:grid|flex)|position\s*:\s*(?:fixed|sticky)|var\s*\(|--[a-z]|calc\s*\(/i);
  assert.doesNotMatch(css,/(?:^|})\s*(?:input|button|a|body|\.content|\.homeBox|\.header|\.navigation)\s*\{/m);
  const sms=fs.readFileSync(path.join(directory,'SMS.html'),'utf8'),diag=fs.readFileSync(path.join(directory,'Diagnostics.html'),'utf8');
  for(const value of [sms,diag]){assert.match(value,/mfCommunityShell/);assert.match(value,/mfCommunityToolbar/);assert.match(value,/mfCommunityStatus/);assert.doesNotMatch(value,/style=/i)}
});

test('Community R2.2 sources exclude old logs, global interception and firmware controls',()=>{
  const combined=[bootstrap,css,transformer,fs.readFileSync(path.join(directory,'SMS.html'),'utf8'),fs.readFileSync(path.join(directory,'Diagnostics.html'),'utf8')].join('\n');
  assert.doesNotMatch(combined,/detailed_log|canary_logs|RestoreFw|file=reset|file=poweroff|debugmodeon/i);
  assert.doesNotMatch(combined,/XMLHttpRequest\.prototype|console\.(?:log|warn|error)\s*=|setInterval/i);
});
