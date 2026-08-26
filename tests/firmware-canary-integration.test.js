const test = require("node:test");
const assert = require("node:assert/strict");
const app = require("../scriptable.js");
const stage0 = require("../modules/firmware-stage0.js");

const NOW = 1_000_000;
const STATUS = `<?xml version="1.0"?><RGW>
  <model>LV01</model>
  <imei>TEST-IMEI-NOT-A-DEVICE</imei>
  <revision>Ver.D</revision>
  <version_num>${stage0.REQUIRED_FIRMWARE}</version_num>
  <batteryinfo><Battery_percent>80</Battery_percent><Battery_status>1</Battery_status><Charger_status>0</Charger_status></batteryinfo>
</RGW>`;

function acceptedStage0(image = stage0.WEBUI_CANARY_LOGS_R1) {
  return {
    ...stage0,
    createImageEvidence() {
      return Object.freeze({
        size: image.size,
        sha256: image.sha256,
        byteLength: image.size,
        computedSha256: image.sha256,
        verification: "computed-from-bytes",
        verifiedAt: NOW
      });
    },
    validateAuditImageEvidence() {
      return { ok: true, image, errors: [] };
    }
  };
}

test("Scriptable canary validation reads the selected bytes and one fresh status without a flash POST", async () => {
  let downloads = 0;
  let reads = 0;
  let statusReads = 0;
  const result = await app.validateFirmwareCanary({}, {
    stage0: acceptedStage0(),
    now: () => NOW,
    documentPicker: { openFile: async () => "/private/mobile/Documents/MF885_Community_0.0-logs-r1-auth-r4-cafe-r2.bin" },
    fileManager: {
      async downloadFileFromiCloud() { downloads++; },
      read() { reads++; return [1, 2, 3]; }
    },
    getStatus: async () => { statusReads++; return STATUS; }
  });

  assert.equal(result.ok, true);
  assert.equal(result.readyForTransportCapture, true);
  assert.equal(result.flashAllowed, false);
  assert.equal(result.report.selectedFile.name, stage0.WEBUI_CANARY_LOGS_R1.file);
  assert.equal(result.report.image.match, true);
  assert.equal(result.report.device.model, "LV01");
  assert.equal(result.report.device.ok, true);
  assert.equal(result.report.power.chargerConnected, true);
  assert.equal(result.report.power.ok, true);
  assert.equal(result.report.restoreTransport.allowlistedContracts, 0);
  assert.deepEqual(result.report.safety, {
    routerReadsAttempted: 1,
    routerWritesAttempted: 0,
    firmwarePostsAttempted: 0,
    automaticRetries: 0,
    flashAllowed: false
  });
  assert.equal(downloads, 1);
  assert.equal(reads, 1);
  assert.equal(statusReads, 1);
  assert.doesNotMatch(result.text, /private\/mobile/);
});

test("Scriptable audit recognizes Logs r2 without making it restorable", async () => {
  let statusReads=0;
  const result=await app.validateFirmwareCanary({}, {
    stage0:acceptedStage0(stage0.WEBUI_CANARY_LOGS_R2),
    now:()=>NOW,
    documentPicker:{openFile:async()=>"/private/mobile/Documents/MF885_Community_0.0-logs-r2-auth-r4-cafe-r2.bin"},
    fileManager:{read(){return [4,5,6];}},
    getStatus:async()=>{statusReads++;return STATUS;}
  });
  assert.equal(result.ok,true);
  assert.equal(result.report.image.id,"0.0-logs-r2-auth-r4-cafe2");
  assert.equal(result.report.expectedCanary.sha256,stage0.WEBUI_CANARY_LOGS_R2.sha256);
  assert.equal(result.report.expectedCanary.restorable,false);
  assert.equal(result.flashAllowed,false);
  assert.equal(result.report.safety.firmwarePostsAttempted,0);
  assert.equal(statusReads,1);
});

test("Scriptable audit recognizes SMS r1 with one read and zero firmware posts",async()=>{
  let statusReads=0;
  const result=await app.validateFirmwareCanary({}, {
    stage0:acceptedStage0(stage0.WEBUI_SMS_R1),
    now:()=>NOW,
    documentPicker:{openFile:async()=>"/private/mobile/Documents/MF885_Community_0.0-sms-r1-cafe-r2.bin"},
    fileManager:{read(){return [7,8,9];}},
    getStatus:async()=>{statusReads++;return STATUS;}
  });
  assert.equal(result.ok,true);
  assert.equal(result.report.image.id,"0.0-sms-r1-cafe2");
  assert.equal(result.report.expectedCanary.sha256,stage0.WEBUI_SMS_R1.sha256);
  assert.equal(result.report.expectedCanary.restorable,false);
  assert.equal(result.readyForTransportCapture,true);
  assert.equal(result.flashAllowed,false);
  assert.equal(result.report.safety.routerReadsAttempted,1);
  assert.equal(result.report.safety.routerWritesAttempted,0);
  assert.equal(result.report.safety.firmwarePostsAttempted,0);
  assert.equal(statusReads,1);
});

test("a non-canary file fails before contacting the router", async () => {
  let statusReads = 0;
  const rejectedStage0 = {
    ...acceptedStage0(),
    validateAuditImageEvidence() { return { ok: false, image: null, errors: ["Image SHA-256 is not a recognized audited MF885 artifact."] }; }
  };
  const result = await app.validateFirmwareCanary({}, {
    stage0: rejectedStage0,
    now: () => NOW,
    documentPicker: { openFile: async () => "/tmp/not-the-canary.bin" },
    fileManager: { read() { return [9]; } },
    getStatus: async () => { statusReads++; return STATUS; }
  });

  assert.equal(result.ok, false);
  assert.equal(result.readyForTransportCapture, false);
  assert.equal(result.flashAllowed, false);
  assert.equal(result.report.safety.routerReadsAttempted, 0);
  assert.equal(result.report.safety.firmwarePostsAttempted, 0);
  assert.equal(statusReads, 0);
});

test("cancelling the native file picker does not read files or contact the router", async () => {
  let reads = 0;
  const result = await app.validateFirmwareCanary({}, {
    stage0: acceptedStage0(),
    documentPicker: { openFile: async () => "" },
    fileManager: { read() { reads++; return []; } },
    getStatus: async () => { throw new Error("must not be called"); }
  });
  assert.deepEqual(result, { cancelled: true, ok: false, flashAllowed: false });
  assert.equal(reads, 0);
});

test("RestoreFw dry-run hashes twice, round-trips multipart locally, and uses GET only",async()=>{
  let getBytesCalls=0;
  const bytes=[1,2,3,4],sha=stage0.sha256Hex(bytes),data={getBytes:()=>{getBytesCalls++;return bytes.slice();}};
  const image={id:stage0.GOLDEN_IMAGE.id,file:stage0.GOLDEN_IMAGE.file,size:bytes.length,sha256:sha};
  let evidenceCalls=0,sessionCalls=0,statusCalls=0,routeCalls=0,journalCalls=0;
  const fakeStage0={
    ...stage0,
    createImageEvidence(value){assert.ok(value instanceof Uint8Array);assert.deepEqual(Array.from(value),bytes);evidenceCalls++;return Object.freeze({size:bytes.length,sha256:sha,byteLength:bytes.length,computedSha256:sha,verification:"computed-from-bytes",verifiedAt:NOW});},
    validateImageEvidence(){return {ok:true,image,errors:[]};},
    createKeychainJournal(){journalCalls++;throw new Error("live journal must not be touched");}
  };
  const routes=[
    {id:"restore-status-direct",model:"GetRestoreStatus",method:"GET",query:"method=get&file=GetRestoreStatus",schema:"restore"},
    {id:"upgrade-status-direct",model:"upgrade_firmware",method:"GET",query:"method=get&file=upgrade_firmware",schema:"upgrade"}
  ];
  const result=await app.runFirmwareRestoreDryRun({
    stage0:fakeStage0,now:()=>NOW,routes,
    documentPicker:{async openFile(){return "/private/mobile/Documents/stock-golden.bin";}},
    fileManager:{read(){return data;}},
    async createAppSession(){sessionCalls++;return {appLogin:{authHeaderPersisted:true,sessionCookieReceived:true}};},
    async getAppStatus(){statusCalls++;return STATUS;},
    async readRoute(_session,route){routeCalls++;return route.schema==="restore"?{statusCode:200,redirectCount:0,text:"<process><status>0</status><progress>0</progress><cause>No Error!</cause></process>"}:{statusCode:200,redirectCount:0,text:"<RGW><upgrade_firmware><support_32m_flash>1</support_32m_flash><restore_status>0</restore_status></upgrade_firmware></RGW>"};}
  });
  assert.equal(result.ok,true);
  assert.equal(result.dryRunReady,true);
  assert.equal(result.flashAllowed,false);
  assert.equal(evidenceCalls,2);
  assert.equal(getBytesCalls,1);
  assert.equal(sessionCalls,1);
  assert.equal(statusCalls,1);
  assert.equal(routeCalls,2);
  assert.equal(journalCalls,0);
  assert.equal(result.report.wireManifest.payloadRoundTripVerified,true);
  assert.equal(result.report.wireManifest.networkRequestConstructed,false);
  assert.equal(result.report.safety.routerGetsAttempted,5);
  assert.equal(result.report.safety.routerWritesAttempted,0);
  assert.equal(result.report.safety.firmwarePostsAttempted,0);
  assert.equal(result.report.safety.multipartNetworkRequestsConstructed,0);
  assert.equal(result.report.safety.liveJournalTouched,false);
  assert.equal(result.report.productionAvailability.available,false);
  assert.doesNotMatch(result.text,/private\/mobile/);
});

test("RestoreFw dry-run rejects an unknown image before APP session or router GET",async()=>{
  let sessions=0,statusReads=0;
  const fakeStage0={
    ...stage0,
    createImageEvidence:()=>Object.freeze({size:1,sha256:"0".repeat(64)}),
    validateImageEvidence:()=>({ok:false,image:null,errors:["Unknown firmware image."]})
  };
  await assert.rejects(app.runFirmwareRestoreDryRun({
    stage0:fakeStage0,now:()=>NOW,
    documentPicker:{async openFile(){return "/private/mobile/Documents/unknown.bin";}},
    fileManager:{read(){return {getBytes:()=>[9]};}},
    async createAppSession(){sessions++;throw new Error("must not run");},
    async getAppStatus(){statusReads++;throw new Error("must not run");}
  }),error=>{
    assert.match(error.message,/Unknown firmware image/i);
    assert.match(error.diagnostics,/"firmwarePostsAttempted": 0/);
    assert.doesNotMatch(error.diagnostics,/private\/mobile/);
    return true;
  });
  assert.equal(sessions,0);
  assert.equal(statusReads,0);
});

test("RestoreFw dry-run cancellation performs no file or router work",async()=>{
  let reads=0,sessions=0;
  const result=await app.runFirmwareRestoreDryRun({
    stage0,
    documentPicker:{async openFile(){return "";}},
    fileManager:{read(){reads++;return null;}},
    async createAppSession(){sessions++;return {};}
  });
  assert.deepEqual(result,{cancelled:true,ok:false,flashAllowed:false});
  assert.equal(reads,0);
  assert.equal(sessions,0);
});

test("dashboard dispatcher rejects a concurrent dry-run and releases firmware-exclusive mode",async()=>{
  const guard=()=>app.createInFlightGuard();
  const web={async evaluateJavaScript(){return null;}};
  let calls=0,powerCalls=0,releaseFirst,signalFirst;
  const firstEntered=new Promise(resolve=>{signalFirst=resolve;});
  const firstHeld=new Promise(resolve=>{releaseFirst=resolve;});
  const dispatcher=app.createDashboardDispatcher({}, {sms:{messages:[]}}, web, {smsGuard:guard(),refreshGuard:guard(),powerGuard:guard(),firmwareGuard:guard()}, {
    runFirmwareRestoreDryRun:async()=>{calls++;if(calls===1){signalFirst();await firstHeld;}return {ok:true,dryRunReady:true,flashAllowed:false};},
    executePowerCommand:async()=>{powerCalls++;return {ok:true};}
  });
  const firstPending=dispatcher({id:"dry-1",action:"firmwareRestoreDryRun",params:{}});
  await firstEntered;
  const second=await dispatcher({id:"dry-2",action:"firmwareRestoreDryRun",params:{}});
  const refresh=await dispatcher({id:"dry-refresh",action:"refresh",params:{}});
  const reboot=await dispatcher({id:"dry-reboot",action:"reboot",params:{confirmed:true}});
  releaseFirst();
  const first=await firstPending;
  const third=await dispatcher({id:"dry-3",action:"firmwareRestoreDryRun",params:{}});
  assert.equal(second.ok,false);
  assert.match(second.error,/exclusive mode.*active|operation.*active|not started/i);
  assert.equal(refresh.ok,false);
  assert.match(refresh.error,/Firmware-exclusive mode/i);
  assert.equal(reboot.ok,false);
  assert.match(reboot.error,/Firmware-exclusive mode/i);
  assert.equal(powerCalls,0);
  assert.equal(first.ok,true);
  assert.equal(third.ok,true);
  assert.equal(calls,2);
  assert.equal(first.result.flashAllowed,false);
});

test("default dry-run transport constructs GET Requests only and never touches RestoreFw",async()=>{
  const originalRequest=global.Request;
  const requests=[];
  class GetOnlyRequest {
    constructor(url){this.url=url;this.method="GET";this.headers={};this.body=null;this.response=null;requests.push(this);}
    async loadString(){
      assert.equal(this.method,"GET");
      assert.equal(this.body==null,true);
      assert.doesNotMatch(this.url,/Action=RestoreFw/i);
      if(/\/login\.cgi$/.test(this.url)){
        this.response={statusCode:401,headers:{"WWW-Authenticate":'Digest realm="router", nonce="nonce-1", qop="auth"'}};
        return "";
      }
      if(/\/login\.cgi\?/.test(this.url)){
        this.response={statusCode:200,headers:{},cookies:[{name:"session",value:"fixture",domain:"192.168.21.1",path:"/"}]};
        return "<?xml version=\"1.0\"?><RGW><login_status>OK</login_status></RGW>";
      }
      this.response={statusCode:200,headers:{"Content-Type":"text/xml"}};
      if(/file=status1/.test(this.url))return STATUS;
      if(/file=GetRestoreStatus/.test(this.url))return "<process><status>0</status><progress>0</progress><cause>No Error!</cause></process>";
      if(/file=upgrade_firmware/.test(this.url))return "<RGW><upgrade_firmware><support_32m_flash>1</support_32m_flash><restore_status>0</restore_status></upgrade_firmware></RGW>";
      throw new Error(`Unexpected GET fixture URL: ${this.url}`);
    }
  }
  const bytes=[1,2,3,4],sha=stage0.sha256Hex(bytes),image={id:stage0.GOLDEN_IMAGE.id,file:stage0.GOLDEN_IMAGE.file,size:bytes.length,sha256:sha};
  const fakeStage0={
    ...stage0,
    createImageEvidence(value){assert.ok(value instanceof Uint8Array);return Object.freeze({size:bytes.length,sha256:sha,byteLength:bytes.length,computedSha256:sha,verification:"computed-from-bytes",verifiedAt:NOW});},
    validateImageEvidence(){return {ok:true,image,errors:[]};}
  };
  global.Request=GetOnlyRequest;
  try{
    const result=await app.runFirmwareRestoreDryRun({
      stage0:fakeStage0,now:()=>NOW,
      documentPicker:{async openFile(){return "/private/mobile/Documents/stock-golden.bin";}},
      fileManager:{read(){return {getBytes:()=>bytes.slice()};}}
    });
    assert.equal(result.ok,true);
    assert.equal(result.report.safety.routerGetsAttempted,7);
    assert.equal(result.report.safety.firmwarePostsAttempted,0);
    assert.equal(result.report.safety.multipartNetworkRequestsConstructed,0);
    assert.equal(requests.length,7);
    assert.ok(requests.every(request=>request.method==="GET"&&request.body==null));
  }finally{
    if(originalRequest===undefined)delete global.Request;
    else global.Request=originalRequest;
  }
});

test("the distributed dashboard has no live firmware restore sender seam",()=>{
  assert.equal(app.runFirmwareRestore,undefined);
  assert.equal(app.firmwareRestoreAvailability,undefined);
  assert.equal(app.confirmFirmwareRestore,undefined);
  assert.equal(app.readFirmwareJournalStatus,undefined);
  assert.equal(app.acknowledgeFirmwareJournal,undefined);
  assert.equal(stage0.executeArmedRestoreOnce,undefined);
  assert.equal(stage0.executePersistentRestoreOnce,undefined);
});
