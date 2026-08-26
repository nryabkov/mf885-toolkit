const test = require("node:test");
const assert = require("node:assert/strict");
const ussd = require("../modules/ussd.js");

test("USSD detection is transport-free while the exact HTTP/XML bridge is unresolved",async()=>{
  let calls=0;
  const result=await ussd.detect({xmlRequest:async()=>{calls++;throw new Error("must not run");}});
  assert.equal(result.supported,false);
  assert.equal(result.confirmed,false);
  assert.equal(result.state,"unavailable");
  assert.deepEqual(result.candidates,[]);
  assert.deepEqual(result.probes,[]);
  assert.equal(result.safety.routerRequestsAttempted,0);
  assert.equal(result.safety.routerWritesAttempted,0);
  assert.equal(result.safety.carrierCommandsAttempted,0);
  assert.equal(calls,0);
});

test("USSD execution rejects even a stale forged capability without a router call",async()=>{
  let calls=0;
  const result=await ussd.execute({xmlRequest:async()=>{calls++;return "unexpected";}},{
    supported:true,
    confirmed:true,
    candidates:[{file:"stale",root:"stale",field:"stale"}]
  },"*#21#");
  assert.equal(result.ok,false);
  assert.equal(result.title,"USSD locked");
  assert.match(result.message,/no exact WebUI\/Duster endpoint/i);
  assert.match(result.diagnostics,/Router requests attempted: 0/);
  assert.doesNotMatch(result.diagnostics,/\*#21#/);
  assert.equal(calls,0);
});
