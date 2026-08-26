const test=require('node:test');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');

const root=path.resolve(__dirname,'..');
const directory=path.join(root,'firmware/community-r2.1');
const manifest=JSON.parse(fs.readFileSync(path.join(directory,'manifest.json'),'utf8'));
const readme=fs.readFileSync(path.join(directory,'README.md'),'utf8');
const digest=value=>crypto.createHash('sha256').update(value).digest('hex');

test('Community R2.1 source manifest pins every custom source byte',()=>{
  assert.deepEqual(fs.readdirSync(directory).sort(),[
    'Diagnostics.html','README.md','SMS.html','SMS.js','community_diagnostics.js','manifest.json'
  ]);
  for(const source of manifest.sources){
    const file=path.resolve(directory,source.file);
    const bytes=fs.readFileSync(file);
    assert.equal(bytes.length,source.size,source.target);
    assert.equal(digest(bytes),source.sha256,source.target);
  }
});

test('Community R2.1 is immutable, English-only, live-static-qualified and not allowlisted',()=>{
  assert.equal(manifest.logical_id,'0.2.1-community-r2');
  assert.equal(manifest.artifact.file,'MF885_Community_0.2.1-community-r2-cafe-r2.bin');
  assert.deepEqual(manifest.logical_change_counts,{replaced:10,added:3,removed:18});
  assert.deepEqual(manifest.removed_locales,['cn','hk','jp']);
  assert.equal(manifest.webi_padding_bytes_remaining,278636);
  assert.equal(manifest.artifact.size,8323644);
  assert.equal(manifest.capabilities.sms_send_request,true);
  assert.equal(manifest.capabilities.sms_send_max_ucs2_segments,4);
  assert.deepEqual(manifest.capabilities.diagnostics_manual_reads,['status1','wan','Engineer_parameter']);
  assert.equal(manifest.capabilities.native_detailed_log,false);
  assert.equal(manifest.capabilities.background_diagnostics_polling,false);
  assert.equal(manifest.live_tested,true);
  assert.equal(manifest.release_status,'experimental-live-qualified-canary');
  assert.equal(manifest.capabilities.static_assets_live_verified,true);
  assert.equal(manifest.capabilities.exact_served_assets_live_verified,13);
  assert.equal(manifest.capabilities.removed_locale_routes_live_verified,18);
  assert.equal(manifest.capabilities.same_unit_postboot_live_verified,true);
  for(const field of ['sms_send_live_tested','inbox_delete_live_tested','flash_qualified','restore_allowlisted','stable'])
    assert.equal(manifest[field],false,field);
  assert.match(readme,/permanently brick/i);
  assert.match(readme,/password-equivalent/i);
  assert.match(readme,/delivery receipt/i);
});

test('Community R2.1 production sources exclude old logs and firmware-control routes',()=>{
  const source=fs.readFileSync(path.join(directory,'SMS.js'),'utf8')+'\n'+
    fs.readFileSync(path.join(directory,'community_diagnostics.js'),'utf8')+'\n'+
    fs.readFileSync(path.join(directory,'Diagnostics.html'),'utf8');
  assert.doesNotMatch(source,/detailed_log|canary_logs|RestoreFw|file=reset|file=poweroff|debugmodeon/i);
  assert.doesNotMatch(source,/setInterval|XMLHttpRequest\.prototype|console\.(?:log|warn|error)\s*=/i);
});
