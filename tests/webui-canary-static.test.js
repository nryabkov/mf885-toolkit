const test=require("node:test");
const assert=require("node:assert/strict");
const crypto=require("node:crypto");
const fs=require("node:fs");
const path=require("node:path");

const root=path.join(__dirname,"..");
const script=fs.readFileSync(path.join(root,"firmware/webui-canary-logs/canary_logs.js"),"utf8");
const scriptR2=fs.readFileSync(path.join(root,"firmware/webui-canary-logs-r2/canary_logs.js"),"utf8");
const builder=fs.readFileSync(path.join(root,"tools/mf885_webi_builder.py"),"utf8");
const manifestR1=JSON.parse(fs.readFileSync(path.join(root,"firmware/webui-canary-logs/manifest.json"),"utf8"));
const manifestR2=JSON.parse(fs.readFileSync(path.join(root,"firmware/webui-canary-logs-r2/manifest.json"),"utf8"));

test("WEBI log Canary is syntactically valid and observer-only",()=>{
  assert.doesNotThrow(()=>new Function(script));
  assert.match(script,/MF885 Community Canary Logs 0\.0-logs-r1/);
  for(const hook of ["XMLHttpRequest.prototype.open","XMLHttpRequest.prototype.send","window.fetch","addEventListener('submit'","addEventListener('click'","console.'+name","unhandledrejection"]){
    assert.match(script,new RegExp(hook.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")));
  }
  assert.match(script,/file=detailed_log/);
  assert.match(script,/setRequestHeader\('Authorization',getAuthHeader\('GET'\)\)/);
  assert.match(script,/SMS payload hidden/);
  assert.doesNotMatch(script,/RestoreFw|file=reset|file=poweroff|restore_defaults|debugmodeon/i);
  assert.equal(manifestR1.script.size,Buffer.byteLength(script));
  assert.equal(manifestR1.script.sha256,crypto.createHash("sha256").update(script).digest("hex"));
  assert.equal(manifestR1.live_tested,false);
  assert.equal(manifestR1.flash_qualified,false);
  assert.equal(manifestR1.restore_allowlisted,false);
  assert.equal(manifestR1.stable,false);
  assert.equal(manifestR1.release_status,"experimental-unflashed");
  assert.equal(manifestR1.detailed_log_authentication,"stock getAuthHeader(GET) Digest header");
});

test("WEBI log Canary r2 is separate, bounded and stays inside the WEBI budget",()=>{
  assert.doesNotThrow(()=>new Function(scriptR2));
  assert.match(scriptR2,/MF885 Community Canary Logs 0\.0-logs-r2/);
  assert.ok(Buffer.byteLength(scriptR2)<=13420);
  for(const feature of ["maxUnits=96000","dropped=0","requestId","timeout","visibilitychange","detailed_log_items","'error','warn','log','info'"]){
    assert.match(scriptR2,new RegExp(feature.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")));
  }
  assert.match(scriptR2,/file=message/);
  assert.match(scriptR2,/setRequestHeader\('Authorization',getAuthHeader\('GET'\)\)/);
  assert.match(scriptR2,/message_content\|sms_content\|sms_message/);
  assert.doesNotMatch(scriptR2,/RestoreFw|file=reset|file=poweroff|restore_defaults|debugmodeon/i);
  assert.equal(manifestR2.script.size,Buffer.byteLength(scriptR2));
  assert.equal(manifestR2.script.sha256,crypto.createHash("sha256").update(scriptR2).digest("hex"));
  assert.equal(manifestR2.webi_padding_bytes_remaining,16);
  assert.equal(manifestR2.cafe_record.padding_bytes,2);
  assert.equal(manifestR2.cafe_record.stored_size,13404);
  assert.equal(manifestR2.identity_and_network_values_redacted_before_event_storage,true);
  assert.equal(manifestR2.stable,false);
  assert.equal(manifestR2.flash_qualified,false);
});

test("local r2 artifact matches its exact manifest when present",()=>{
  const artifact=path.join(root,"build",manifestR2.artifact.file);
  if(!fs.existsSync(artifact))return;
  const raw=fs.readFileSync(artifact);
  assert.equal(raw.length,manifestR2.artifact.size);
  assert.equal(crypto.createHash("sha256").update(raw).digest("hex"),manifestR2.artifact.sha256);
});

test("WEBI builder is exact-golden, fixed-size-index and fail-closed",()=>{
  assert.match(builder,/2b5880fc26805918bb574d07341ea9b863f8261be34c3bf9766fac0929204531/);
  assert.match(builder,/INDEX_LOADER = b'<script src="js\/canary_logs\.js"><\/script>'/);
  assert.match(builder,/len\(match\.group\(1\)\) != len\(INDEX_LOADER\)/);
  assert.match(builder,/0xCAFE1000/);
  assert.match(builder,/padding_bytes = \(-len\(logical_data\)\) % 4/);
  assert.match(builder,/\(padding_bytes << 24\) \| len\(stored_data\)/);
  assert.doesNotMatch(builder,/0x03000000 \| len\(data\)/);
  assert.match(builder,/zlib\.adler32/);
  assert.match(builder,/inspector\.byte_sum/);
  assert.match(builder,/non-WEBI partition changed/);
  assert.match(builder,/"flash_qualified": False/);
  assert.match(builder,/"restore_allowlisted": False/);
  assert.match(builder,/"0\.0-logs-r2"/);
  assert.match(builder,/--profile/);
});
