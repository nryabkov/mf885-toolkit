/* Private c1 command session successor v2. Explicit sends, GET-only recovery, bounded RAM history. */
import {decodeSessionSnapshot} from '../ussd-observer-v19/snapshot.mjs';
const wordHex = n => n.toString(16).padStart(8,'0');
export function encodeConsoleCommand(kind,command) {
  if(!['a','u'].includes(kind)||typeof command!=='string'||!command.length||command.length>224||/[^\x20-\x7e]/.test(command))throw Error('Enter 1–224 printable ASCII characters.');
  if(kind==='a'&&(!/^at/i.test(command)||command.includes(';')))throw Error('Enter one AT command, without a command batch.');
  if(kind==='u'&&/[$@\[\]\\^_`{|}~]/.test(command))throw Error('This USSD sender accepts codes and ASCII characters shared with the GSM alphabet.');
  return Array.from(command,c=>c.charCodeAt(0).toString(16).padStart(2,'0')).join('');
}
export function decodeConsoleSnapshot(wire) {
  if(typeof wire!=='string'||wire.length!==1995||!/^c1:[0-9a-f]+$/.test(wire))throw Error('Invalid console snapshot');
  const raw=Uint8Array.from(wire.slice(3).match(/../g),x=>parseInt(x,16)),v=new DataView(raw.buffer);
  const w=Array.from({length:9},(_,i)=>v.getUint32(i*4,true));
  const [low,high,sequence,phase,kind,,tag,count,flags]=w,status=v.getInt32(20,true);
  if(phase>7||![0,97,117].includes(kind)||count>960||flags&~3||(!sequence&&(phase||kind||status||tag||count||flags))||(!(low||high)&&sequence)||((phase>=1&&phase<=4)!==(status===-2147483648)))throw Error('Inconsistent console snapshot');
  for(let i=36+count;i<raw.length;i++)if(raw[i])throw Error('Nonzero output padding');
  const outputBytes=raw.slice(36,36+count);let output=null;
  try {output=new TextDecoder('utf-8',{fatal:true}).decode(outputBytes);}catch{}
  return {nonce:wordHex(low)+':'+wordHex(high),initialized:!!(low||high),sequence,phase,kind:String.fromCharCode(kind),status,tag,
    pending:phase>=1&&phase<=4,quarantined:!!(flags&2),truncated:!!(flags&1),output,
    outputHex:wire.slice(75,75+2*count)};
}
export function createConsoleSession({read,post,readNetwork,random=words=>globalThis.crypto.getRandomValues(words)}) {
  let busy=false,phase='unavailable',joined=null,current=null,action=null,history=[],network=null;
  const copy=a=>a?{...a,reply:a.reply?{...a.reply}:null}:null;
  const state=()=>({busy,phase,canSubmit:!busy&&phase==='ready',snapshot:current,network:network?{...network}:null,action:copy(action),history:history.map(copy)});
  async function readState(){
    const wire=await read(),c=decodeConsoleSnapshot(wire.console),u=decodeSessionSnapshot(wire.ussd);
    if(c.nonce!==u.submission.nonceRaw||c.sequence!==u.submission.sequence||c.status!==u.submission.status)throw Error('Snapshot changed while being read');
    current={console:c,ussd:u};return c;
  }
  function reconcile(c){
    if(action){
      if(!c.initialized||c.nonce!==action.nonce){action.outcome='session-lost';action.reply=null;}
      else {
        if(action.kind==='u'){
          const matches=current.ussd.events.filter(e=>e.requestSequence===action.sequence);
          if(matches.length){action.reply={...matches[matches.length-1]};action.outcome=classifyUssdEvent(action.reply);}
        }
        if(c.sequence===action.sequence){
          action.status=c.status;
          if(action.kind==='a'){action.output=c.output;action.outputHex=c.outputHex;action.truncated=c.truncated;}
          if(!action.reply)action.outcome=c.pending?'pending':c.phase===5?(action.kind==='u'?'accepted-awaiting-reply':'success'):c.phase===6?'error':'unknown';
        } else if(!action.reply)action.outcome=c.sequence>action.sequence?'superseded':'not-observed';
      }
    }
    phase=c.initialized&&c.nonce===joined?(c.quarantined?'quarantined':c.pending?'pending':c.sequence<0xffffffff?'ready':'unavailable'):'session-changed';
  }
  async function run(fn){if(busy)throw Error('Command operation in progress');busy=true;try{await fn();}finally{busy=false;}return state();}
  async function refresh(){try{reconcile(await readState());}catch{current=null;phase='unavailable';}}
  return {state,
    prepare:()=>run(async()=>{
      joined=null;phase='preparing';
      try{
        let c=await readState();
        if(!c.initialized){
          let words=new Uint32Array(2);for(let i=0;i<8&&!words.some(Boolean);i++)random(words);
          if(!words.some(Boolean))throw Error('No random session identity');
          try{await post(wordHex(words[0])+':'+wordHex(words[1])+':00000000:s:');}catch{}
          c=await readState();
        }
        if(!c.initialized){phase='unavailable';return;}
        joined=c.nonce;reconcile(c);
      }catch{current=null;phase='unavailable';}
    }),
    submit:(kind,command)=>run(async()=>{
      const payload=encodeConsoleCommand(kind,command);
      if(phase!=='ready'||!joined)throw Error('Connect the command session first');
      await refresh();if(phase!=='ready')return;
      if(kind==='u'){
        try{network=networkReadiness(await readNetwork());}
        catch{network={ready:false,reason:'Network readiness could not be read. Nothing was sent.'};}
        if(!network.ready)return;
        // Network I/O may span a restart or another producer. Recheck ownership.
        await refresh();if(phase!=='ready')return;
      }
      const c=current.console;
      if(action){history.unshift(copy(action));history=history.slice(0,20);}
      action={nonce:c.nonce,sequence:c.sequence+1,kind,command,outcome:'unknown',status:null,output:'',outputHex:'',truncated:false,reply:null};
      phase='sending';
      try{await post(c.nonce+':'+wordHex(action.sequence)+':'+kind+':'+payload);}catch{}
      await refresh();
    }),
    refresh:()=>run(refresh)
  };
}

// Path values come from observer.h, not from the carrier status byte.
export function classifyUssdEvent(event){
  if(event.pathRaw===2)return 'ussd-error';
  if(![1,3].includes(event.pathRaw))return 'ussd-event';
  if(!event.payloadBytes)return 'ussd-empty';
  return typeof event.text==='string'&&event.text.length?'ussd-reply':'ussd-raw';
}
export function networkReadiness(fields){
  if(!fields||!['1','5'].includes(fields.registration)||fields.sim!=='0')return {
    ready:false,reason:'SIM and network registration are not ready or could not be verified. Nothing was sent.'};
  return {ready:true,registration:fields.registration,sim:fields.sim,
    reason:'Registered. USSD availability still depends on the modem and network.'};
}
// Stock status1 direct paths only. Missing, duplicate or structured fields fail closed.
export function decodeConsoleNetwork(doc){
  const children=n=>Array.from(n?.childNodes||[]).filter(c=>c.nodeType===1);
  const child=(n,name)=>{const all=children(n).filter(c=>c.nodeName===name);if(all.length!==1||all[0].attributes.length)throw Error('Invalid network field');return all[0];};
  const leaf=(n,name)=>{const v=child(n,name);if(Array.from(v.childNodes).some(c=>c.nodeType!==3)||!/^\d+$/.test(v.textContent))throw Error('Invalid network value');return v.textContent;};
  const root=doc?.documentElement;if(!root||root.nodeName!=='RGW'||root.attributes.length)throw Error('Invalid network root');
  const wan=child(root,'wan');return {registration:leaf(wan,'NW_register_status'),sim:leaf(child(wan,'cellular'),'sim_status')};
}
