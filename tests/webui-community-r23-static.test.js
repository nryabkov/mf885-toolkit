const test=require('node:test');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');

const root=path.resolve(__dirname,'..');
const directory=path.join(root,'firmware/community-r2.3');
const manifest=JSON.parse(fs.readFileSync(path.join(directory,'manifest.json'),'utf8'));
const transformer=fs.readFileSync(path.join(root,'tools/mf885_community_r23.py'),'utf8');
const css=fs.readFileSync(path.join(directory,'community_ui.css'),'utf8');
const sms=fs.readFileSync(path.join(directory,'SMS.html'),'utf8');
const smsJs=fs.readFileSync(path.join(directory,'SMS.js'),'utf8');
const diagnostics=fs.readFileSync(path.join(directory,'Diagnostics.html'),'utf8');
const digest=value=>crypto.createHash('sha256').update(value).digest('hex');

test('Community R2.3 is a separate fail-closed immutable source profile',()=>{
  assert.deepEqual(fs.readdirSync(directory).sort(),[
    'Diagnostics.html','README.md','SMS.html','SMS.js','community_bootstrap.js','community_ui.css','manifest.json'
  ]);
  assert.equal(manifest.logical_id,'0.2.3-community-r2');
  assert.ok(['prebuild-unpinned','offline-pinned'].includes(manifest.pin_state));
  if(manifest.pin_state==='prebuild-unpinned'){
    assert.equal(manifest.artifact.sha256,null);
    assert.equal(manifest.structurally_verified,false);
  }else{
    assert.match(manifest.artifact.sha256,/^[0-9a-f]{64}$/);
  }
  assert.equal(manifest.live_tested,false);
  assert.equal(manifest.flash_qualified,false);
  assert.equal(manifest.restore_allowlisted,false);
  assert.equal(manifest.stable,false);
  assert.equal(manifest.design_review_gate.required_before_flash_authorization,true);
  assert.deepEqual(manifest.design_review_gate.pages,['Canonical Login','Modern Login','Dashboard','Internet','Wireless','Settings','Messages','Diagnostics']);
  for(const source of manifest.sources){
    const bytes=fs.readFileSync(path.join(directory,source.file));
    assert.equal(bytes.length,source.size,source.target);
    assert.equal(digest(bytes),source.sha256,source.target);
  }
  assert.match(transformer,/derived output records are not pinned/);
  assert.match(transformer,/r22\.build_patch_set/);
  assert.doesNotMatch(transformer,/community-r2\.2\/.*(?:write|unlink|rename)/i);
});

test('R2.3 keeps the canonical login plain and scopes the modern visual system',()=>{
  assert.match(transformer,/Remember this tab/);
  assert.match(transformer,/Keeps refreshes signed in with a password-equivalent key\. Sign out or close the tab to clear it\./);
  assert.match(transformer,/Open updated interface<\/a>/);
  assert.match(transformer,/href="\/r23\.html"/);
  assert.match(transformer,/name="viewport" content="width=device-width, initial-scale=1"/);
  assert.match(transformer,/Cache-Control" content="no-cache, no-store, must-revalidate"/);
  assert.match(transformer,/ENTRY_PATH = "www\\\\r23\.html"/);
  assert.match(transformer,/UTILS_PATH = "www\\\\js\\\\r23utils\.js"/);
  assert.match(transformer,/LAYOUT_PATH = "www\\\\js\\\\r23layout\.js"/);
  assert.match(transformer,/MENU_PATH = "www\\\\xml\\\\r23ui\.xml"/);
  assert.match(transformer,/window\.location="\/r23\.html"/);
  assert.match(transformer,/legacy entry loads Community functionality/);
  assert.match(transformer,/R2\.3 private menu route/);
  assert.match(css,/#mfRememberTab\s*\{[^}]*width:16px !important;[^}]*height:16px !important;/s);
  assert.match(css,/html\.mfCommunityR23Entry \.mfFreshUiLink \{ display:none; \}/);
  assert.match(css,/@media screen and \(max-width:720px\)/);
  assert.doesNotMatch(css,/overflow-x\s*:\s*hidden/i);
  assert.match(css,/\.navigation ul li\s*\{[^}]*width:33\.333% !important;/s);
  assert.match(css,/\.leftBar\s*\{[^}]*float:none !important;[^}]*width:100% !important;/s);
  assert.match(css,/html\.mfCommunityR23Root #Content/);
  assert.doesNotMatch(css,/display\s*:\s*(?:grid|flex)|position\s*:\s*(?:fixed|sticky)|var\s*\(|--[a-z]|calc\s*\(/i);
  for(const page of [sms,diagnostics]){
    assert.match(page,/mfCommunityShell/);
    assert.match(page,/mfCommunityHeading/);
    assert.match(page,/mfCommunityToolbar/);
    assert.doesNotMatch(page,/style=/i);
  }
});

test('R2.3 Messages is direct, expanded and display-paginated without weakening history safety',()=>{
  assert.ok(!sms.includes('mfSmsConfirm'));
  assert.ok(!sms.includes('mfSmsReview'));
  assert.match(sms,/id="mfSmsSend"[^>]*>Send</);
  assert.match(sms,/operator may charge per segment/i);
  assert.match(sms,/id="mfSmsPrevious"/);
  assert.match(sms,/id="mfSmsPage"/);
  assert.match(sms,/id="mfSmsNext"/);
  assert.match(sms,/id="mfSmsAutoCheck"/);
  assert.match(sms,/Check for new messages while this tab is open/);
  assert.match(smsJs,/DISPLAY_PAGE_SIZE=10/);
  assert.match(smsJs,/createElement\('article'\)/);
  assert.match(smsJs,/content\.textContent=message\.content/);
  assert.match(smsJs,/var target=String\(number\.value/);
  assert.match(smsJs,/var before=null;[\s\S]*readHistory\(PROFILES\.mDeviceOutbox\)/);
  assert.match(smsJs,/PostXMLWithResponse/);
  assert.match(smsJs,/DELETE_SMS/);
  assert.match(smsJs,/w\.confirm\('Delete this SMS\?/);
  assert.equal((smsJs.match(/SEND_SMS/g)||[]).length,1);
  assert.equal((smsJs.match(/PostXMLWithResponse/g)||[]).length,1);
  assert.match(smsJs,/WATCH_INTERVAL_MS=60000/);
  assert.match(smsJs,/Browser alerts are unavailable on this HTTP address/);
  assert.match(smsJs,/New router messages:/);
  assert.doesNotMatch(smsJs,/setInterval|automatic retry|mfSmsReview|mfSmsConfirm/i);
});

test('R2.3 keeps active USSD and firmware controls out of every owned source',()=>{
  const combined=['community_bootstrap.js','community_ui.css','SMS.html','SMS.js','Diagnostics.html'].map(name=>fs.readFileSync(path.join(directory,name),'utf8')).join('\n');
  assert.doesNotMatch(combined,/SEND_USSD|\+CUSD|AT\+|RestoreFw|file=reset|file=poweroff|debugmodeon|detailed_log|canary_logs/i);
  assert.equal(manifest.capabilities.ussd_active,false);
  assert.equal(manifest.capabilities.ussd_webui_transport_proven,false);
  assert.equal(manifest.capabilities.custom_detailed_log_panel,false);
  assert.equal(manifest.capabilities.inherited_stock_detailed_log_route_present,true);
});
