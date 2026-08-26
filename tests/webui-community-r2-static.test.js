const test=require('node:test');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');

const root=path.resolve(__dirname,'..');
const directory=path.join(root,'firmware/community-r2');
const manifest=JSON.parse(fs.readFileSync(path.join(directory,'manifest.json'),'utf8'));
const auth=fs.readFileSync(path.join(directory,'community_auth.js'));
const authText=auth.toString('utf8');
const readme=fs.readFileSync(path.join(directory,'README.md'),'utf8');
const digest=value=>crypto.createHash('sha256').update(value).digest('hex');

test('Community R2 publishes source only and pins the exact tab auth source',()=>{
  assert.deepEqual(fs.readdirSync(directory).sort(),['README.md','community_auth.js','manifest.json']);
  const source=manifest.sources.find(item=>item.target==='www\\js\\community_auth.js');
  assert.ok(source);
  assert.equal(auth.length,source.size);
  assert.equal(digest(auth),source.sha256);
  assert.match(authText,/mf885\.community\.r2\.tab-auth\.v1/);
  assert.match(authText,/sessionStorage/);
  assert.doesNotMatch(authText,/localStorage/);
});

test('Community R2 manifest records the exact bounded scope and risk state',()=>{
  assert.equal(manifest.logical_id,'0.2-community-r2');
  assert.deepEqual(manifest.logical_change_counts,{replaced:10,added:1,removed:18});
  assert.deepEqual(manifest.removed_locales,['cn','hk','jp']);
  assert.equal(manifest.removed_archive_bytes,263312);
  assert.equal(manifest.webi_padding_bytes_remaining,306308);
  assert.equal(manifest.artifact.size,8323644);
  assert.deepEqual(manifest.capabilities.languages,['en']);
  assert.equal(manifest.capabilities.sms_send_request,false);
  assert.equal(manifest.capabilities.remember_tab_plaintext_password,false);
  assert.equal(manifest.capabilities.remember_tab_password_equivalent_ha1,true);
  for(const field of ['live_tested','flash_qualified','restore_allowlisted','stable'])
    assert.equal(manifest[field],false);
  assert.match(readme,/permanently brick/i);
  assert.match(readme,/password-equivalent/i);
});
