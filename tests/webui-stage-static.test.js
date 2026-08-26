const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');

const root=path.join(__dirname,'..');
const sms=fs.readFileSync(path.join(root,'firmware/webui-sms-r1/SMS.js'),'utf8');
const smsHtml=fs.readFileSync(path.join(root,'firmware/webui-sms-r1/SMS.html'),'utf8');
const smsManifest=JSON.parse(fs.readFileSync(path.join(root,'firmware/webui-sms-r1/manifest.json'),'utf8'));
const community=fs.readFileSync(path.join(root,'firmware/community-r1/SMS.js'),'utf8');
const communityHtml=fs.readFileSync(path.join(root,'firmware/community-r1/SMS.html'),'utf8');
const communityManifest=JSON.parse(fs.readFileSync(path.join(root,'firmware/community-r1/manifest.json'),'utf8'));
const ussd=fs.readFileSync(path.join(root,'firmware/webui-ussd-r1/custom_fw.js'),'utf8');
const ussdHtml=fs.readFileSync(path.join(root,'firmware/webui-ussd-r1/custom_fw_rules.html'),'utf8');
const ussdContract=JSON.parse(fs.readFileSync(path.join(root,'firmware/webui-ussd-r1/contract.json'),'utf8'));
const builder=fs.readFileSync(path.join(root,'tools/mf885_webui_stage_builder.py'),'utf8');

test('SMS r1 is a bounded exact-stock message client with no firmware or power route',()=>{
  assert.doesNotThrow(()=>new Function(sms));
  assert.match(sms,/MF885 Community WebUI SMS 0\.0-sms-r1/);
  assert.match(sms,/GET_RCV_SMS_LOCAL/);
  assert.match(sms,/SEND_SMS/);
  assert.match(sms,/DELETE_SMS/);
  assert.match(sms,/STATUS_POLLS=10/);
  assert.match(sms,/MAX_PAGES=20/);
  assert.match(sms,/Outcome unknown\. Reload this page before any retry/);
  assert.match(sms,/callProductXML\('status1'\)/);
  assert.match(sms,/\^2\\\.5\\\.94/);
  assert.equal((sms.match(/PostXMLWithResponse/g)||[]).length,1);
  assert.ok(Buffer.byteLength(sms)<13000);
  for(const forbidden of ['RestoreFw','file=reset','file=poweroff','restore_defaults','debugmodeon','ussd_status','ussd_setting'])assert.doesNotMatch(sms,new RegExp(forbidden,'i'));
  assert.match(smsHtml,/Nothing is sent automatically/);
  assert.match(smsHtml,/Technical log \(SMS text is never recorded\)/);
  const sourceByFile=new Map(smsManifest.sources.map(item=>[item.file,item]));
  for(const [file,data] of [['SMS.js',Buffer.from(sms)],['SMS.html',Buffer.from(smsHtml)]]){
    const expected=sourceByFile.get(file);assert.ok(expected);assert.equal(data.length,expected.size);assert.equal(crypto.createHash('sha256').update(data).digest('hex'),expected.sha256);
  }
  assert.equal(smsManifest.artifact.sha256,'c27b5f7989ac4e4ac6ff1ebdd603685f6f1fe777918458059b620b1c36ec73ce');
  assert.equal(smsManifest.container_revision,2);
  assert.equal(smsManifest.stable,false);
  assert.equal(smsManifest.flash_qualified,false);
  assert.equal(smsManifest.restore_allowlisted,false);
});

test('community r1 is the exact read-delete product profile with logs and sending absent',()=>{
  assert.doesNotThrow(()=>new Function(community));
  assert.match(community,/MF885 Community R1 SMS read-delete 0\.1-community-r1/);
  assert.match(community,/GET_RCV_SMS_LOCAL/);
  assert.match(community,/DELETE_SMS/);
  assert.match(community,/STATUS_POLLS=10/);
  assert.match(community,/MAX_PAGES=20,MAX_MESSAGES=200/);
  assert.match(community,/Deletion outcome unknown\. Reload the page before any retry/);
  assert.equal((community.match(/PostXMLWithResponse/g)||[]).length,1);
  for(const forbidden of ['SEND_SMS','detailed_log','canary_logs','mfSmsLog','RestoreFw','file=reset','file=poweroff','debugmodeon'])assert.doesNotMatch(community,new RegExp(forbidden,'i'));
  assert.doesNotMatch(communityHtml,/send|composer|technical log/i);
  assert.match(communityHtml,/Nothing is sent automatically/);
  const sourceByFile=new Map(communityManifest.sources.map(item=>[item.file,item]));
  for(const [file,data] of [['SMS.js',Buffer.from(community)],['SMS.html',Buffer.from(communityHtml)]]){
    const expected=sourceByFile.get(file);assert.ok(expected);assert.equal(data.length,expected.size);assert.equal(crypto.createHash('sha256').update(data).digest('hex'),expected.sha256);
  }
  assert.equal(communityManifest.artifact.sha256,'d42a912e31aafed4e57c6c98d94932444a0b2cf1fe0f8e223c95b3df22dae676');
  assert.equal(communityManifest.capabilities.sms_send_request,false);
  assert.equal(communityManifest.capabilities.sms_page_log,false);
  assert.equal(communityManifest.capabilities.custom_logs_panel_added,false);
  assert.equal(communityManifest.live_tested,false);
  assert.equal(communityManifest.stable,false);
});

test('USSD r1 remains an unbuildable zero-transport audit scaffold',()=>{
  assert.doesNotThrow(()=>new Function(ussd));
  assert.equal(ussdContract.status,'unresolved');
  assert.equal(ussdContract.build_enabled,false);
  assert.equal(ussdContract.router_requests_possible,false);
  assert.equal(ussdContract.transport.file,null);
  assert.equal(ussdContract.native_evidence.handler_address,'0x062d1b88');
  assert.equal(ussdContract.native_evidence.argument_count,3);
  assert.equal(ussdContract.native_evidence.supplementary_service_api_bridge,'0x066e1484');
  assert.equal(ussdContract.native_evidence.supplementary_service_api_bridge_proven,true);
  assert.equal(ussdContract.native_evidence.hardcoded_special_branch_safe_to_test,false);
  assert.equal(ussdContract.native_evidence.webui_to_modem_bridge_proven,false);
  assert.equal(ussdContract.qualification.artifact_built,false);
  assert.match(ussdHtml,/Dialing is locked/);
  assert.match(ussdHtml,/id="mfUssdDial" disabled/);
  for(const forbidden of ['XMLHttpRequest','fetch(','ajax(','PostXML','PostSyncXML','file=ussd','ussd_status','ussd_setting','RestoreFw','file=reset','file=poweroff'])assert.doesNotMatch(ussd,new RegExp(forbidden.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'i'));
  assert.doesNotMatch(builder,/"0\.0-ussd-r1"\s*:/);
});
