// Experimental MF885 USSD support. The exact 2.5.94 image proves +CUSD through
// its local supplementary-service API call, but no WebUI/Duster transport
// contract. Keep both detection and execution transport-free until that HTTP/
// XML bridge is recovered.

const CONTRACT_STATUS = Object.freeze({
  id: "mf885-2.5.94-ussd-unresolved-v2",
  supported: false,
  confirmed: false,
  state: "unavailable",
  candidates: Object.freeze([]),
  detail: "USSD is locked: the modem handler reaches the local supplementary-service API, but no exact WebUI/Duster endpoint or XML contract is confirmed. No router probe or command was sent."
});

async function detect() {
  return {
    ...CONTRACT_STATUS,
    candidates: [],
    probes: [],
    safety: {
      routerRequestsAttempted: 0,
      routerWritesAttempted: 0,
      carrierCommandsAttempted: 0
    }
  };
}

async function execute() {
  return {
    ok: false,
    title: "USSD locked",
    message: CONTRACT_STATUS.detail,
    diagnostics: "Exact 2.5.94 +CUSD and its modem-service bridge are statically identified; HTTP/XML delivery remains unresolved. Router requests attempted: 0."
  };
}

module.exports = { CONTRACT_STATUS, detect, execute };
