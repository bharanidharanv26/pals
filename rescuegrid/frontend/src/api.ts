export const sessionKey='rescuegrid-workspace-v1';
export const connectionLostEvent='rescuegrid:connection-lost';
export const reconnectedEvent='rescuegrid:reconnected';
export class ApiError extends Error {constructor(message:string,public status:number){super(message);}}
export class NetworkError extends Error {}
type RequestOptions={signal?:AbortSignal;timeoutMs?:number};

async function send<T>(url:string,init:RequestInit,read:(response:Response)=>Promise<T>,options:RequestOptions={}):Promise<T>{
 const controller=new AbortController();
 let timedOut=false;
 const abort=()=>controller.abort();
 options.signal?.addEventListener('abort',abort,{once:true});
 if(options.signal?.aborted)controller.abort();
 const timer=window.setTimeout(()=>{timedOut=true;controller.abort();},options.timeoutMs??60_000);
 try{
  const response=await fetch(url,{...init,signal:controller.signal});
  if(!response.ok){
   let message=`Request failed (${response.status})`;
   try{const data=await response.json();message=typeof data.detail==='string'?data.detail:data.detail?.map((x:{msg:string})=>x.msg).join('; ')||message;}catch{/* Preserve the HTTP status for non-JSON error pages. */}
   throw new ApiError(message,response.status);
  }
  return await read(response);
 }catch(error){
  if(error instanceof ApiError)throw error;
  if(options.signal?.aborted)throw new DOMException('Request cancelled','AbortError');
  const message=timedOut
   ?'The request timed out. Reconnect to check the saved state before retrying.'
   :'The local server is unavailable. Start START_RESCUEGRID.bat, then reconnect.';
  window.dispatchEvent(new CustomEvent(connectionLostEvent,{detail:message}));
  throw new NetworkError(message);
 }finally{
  window.clearTimeout(timer);
  options.signal?.removeEventListener('abort',abort);
 }
}

export function requestJson<T>(url:string,options:RequestOptions={},init:RequestInit={}):Promise<T>{
 return send(url,init,async response=>{
  try{return await response.json();}
  catch(error){if(error instanceof SyntaxError)throw new ApiError('The server returned an unreadable response. Reload the application.',response.status);throw error;}
 },options);
}

export function api<T>(path:string,method='GET',body?:unknown,options:RequestOptions={}):Promise<T>{
 // Mutations are never retried automatically: a dropped response may already be committed.
 return requestJson<T>(`/api${path}`,options,{method,headers:{'Content-Type':'application/json','X-Session-ID':localStorage.getItem(sessionKey)||''},body:body===undefined?undefined:JSON.stringify(body)});
}
export async function download(kind='snapshot',job?:string){
 const blob=await send(`/api/export?kind=${encodeURIComponent(kind)}${job?`&job_id=${encodeURIComponent(job)}`:''}`,{headers:{'X-Session-ID':localStorage.getItem(sessionKey)||''}},response=>response.blob());
 const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`rescuegrid-${kind}.${kind==='events'?'csv':'json'}`;a.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000);
}
export const number=(n:number|null|undefined,digits=0)=>n==null?'—':n.toLocaleString('en-IN',{maximumFractionDigits:digits});
export const minutes=(n:number|null|undefined)=>n==null?'—':`${number(n,1)} min`;
export const clock=(n:number)=>`${Math.floor(n/60).toString().padStart(2,'0')}:${Math.floor(n%60).toString().padStart(2,'0')}:${Math.floor((n%1)*60).toString().padStart(2,'0')}`;
