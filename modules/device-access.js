// Experimental diagnostic/device-access probes isolated from the dashboard.
// Safe detection only uses GET requests. State-changing commands are exposed
// only after one exact endpoint contract is proved. Until then execute() is a
// hard lock and performs no router request.

const CAPABILITIES = [
  {
    id: "tryEnableAdb",
    title: "Try to enable ADB",
    description: "Attempt to enable the firmware ADB/debug bridge, if this build exposes it.",
    probes: ["adb", "adb_enable", "debug", "debug_adb", "device_debug"],
    attempts: [
      { type: "routerCall", path: "debug", method: "enable_adb" },
      { type: "xml", file: "adb", root: "adb", field: "enable", value: "1" },
      { type: "xml", file: "debug", root: "debug", field: "adb", value: "1" }
    ]
  },
  {
    id: "tryOpenShell",
    title: "Try to enable vendor shell",
    description: "Attempt to enable a vendor shell/debug service, if present.",
    probes: ["shell", "open_shell", "debug_shell", "device_debug"],
    attempts: [
      { type: "routerCall", path: "debug", method: "open_shell" },
      { type: "xml", file: "shell", root: "shell", field: "open", value: "1" },
      { type: "xml", file: "debug", root: "debug", field: "shell", value: "1" }
    ]
  }
];

const TELNET_METADATA = Object.freeze({ id: "tryEnableTelnet", title: "Telnet", description: "Enable Telnet only when a universal command contract is fully confirmed.", telnet: true });
function capabilities() {
  return CAPABILITIES.map(({ id, title, description }) => ({ id, title, description })).concat([{ ...TELNET_METADATA }]);
}

async function detect(api) {
  const diagnostics = [];
  for (const file of uniqueProbeFiles()) {
    try {
      const xml = await api.xmlRequest("GET", file, null, true, 5);
      diagnostics.push({ file, status: classify(xml), detail: compact(xml) });
    } catch (error) {
      diagnostics.push({ file, status: "error", detail: api.cleanError(error) });
    }
  }
  return {
    supported: diagnostics.some(item => item.status === "responded") ? true : null,
    detail: "Safe GET diagnostics completed. Execution actions are experimental and require a separate confirmation.",
    capabilities: capabilities().map(item => {
      const definition=CAPABILITIES.find(candidate=>candidate.id===item.id);
      return { ...item, supported:!!definition && definition.probes.some(file=>diagnostics.some(probe=>probe.file===file&&probe.status==="responded")) };
    }),
    diagnostics
  };
}

async function execute(api, capability, action) {
  const item = CAPABILITIES.find(entry => entry.id === capability || entry.id === action);
  if (!item) throw new Error("Unknown device-access capability");
  throw new Error("Device-access mutation is locked until one exact endpoint is proven.");
}
function uniqueProbeFiles() { return Array.from(new Set(CAPABILITIES.flatMap(item => item.probes))); }
function classify(xml) { const text = String(xml || ""); return isUnsupported(text) ? "rejected" : "responded"; }
function isUnsupported(xml) { return /not.?found|unknown.?file|not.?support|unsupported|invalid.?file|unauthorized/i.test(String(xml || "")); }
function compact(value) { return String(value || "").replace(/\s+/g, " ").trim().slice(0, 300); }

module.exports = { capabilities, detect, execute };
