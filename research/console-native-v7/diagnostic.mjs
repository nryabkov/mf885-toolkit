/* Read-only decoder of the last borrowed-parser observation. */
export function decodeQueueDiagnostic(value){
 if(typeof value!=='string'||!(/^(?:q1:[0-9a-f]{208}|q2:[0-9a-f]{240})$/.test(value)))throw Error('Invalid AT queue snapshot');
 const hasContext=value.startsWith('q2:');const bytes=new Uint8Array(hasContext?120:104);for(let i=0;i<bytes.length;i++)bytes[i]=parseInt(value.slice(3+2*i,5+2*i),16);
 const view=new DataView(bytes.buffer),words=Array.from({length:20},(_,i)=>view.getUint32(i*4,true));
 const [flags,samples,foreignCalls,ownedCalls,busyRejections,pendingCount,pendingMask,responseTag,responseCode,responseError,responses,callbackClass]=words;
 const tags=words.slice(12);let bits=0;for(let m=pendingMask;m;m>>>=1)bits+=m&1;
 if(flags>31||pendingCount>8||pendingMask>255||bits!==pendingCount||callbackClass>2||tags.slice(pendingCount).some(x=>x!==0))throw Error('Invalid AT queue bounds');
 if((flags===0&&(samples||pendingCount))||((flags&2)&&flags!==3))throw Error('Invalid AT queue flags');
 const tail=bytes.slice(80,104),zero=tail.indexOf(0);if(zero<0||tail.slice(zero).some(x=>x!==0))throw Error('Invalid AT command label');
 const verb=String.fromCharCode(...tail.slice(0,zero));if(verb!==''&&!/^AT[A-Za-z+]{0,21}$/.test(verb))throw Error('Invalid AT command label');
 const context=hasContext?{parserAddress:view.getUint32(104,true),callbackAddress:view.getUint32(108,true),pendingAddress:view.getUint32(112,true),callerAddress:view.getUint32(116,true)}:null;
 if(context&&flags===0&&Object.values(context).some(x=>x!==0))throw Error('Unobserved AT context');
 return {context,flags,samples,foreignCalls,ownedCalls,busyRejections,pendingCount,pendingMask,tags:tags.slice(0,pendingCount),responseTag,responseCode,responseError,responses,callbackClass,verb,sampled:Boolean(flags&1),valid:Boolean(flags&2),liveQueue:false};
}
