import {useCallback,useEffect,useRef,useState} from 'react';
import {Activity,LayoutDashboard,MapPin,Ambulance,Building2,FlaskConical,ArrowLeftRight,Database,Search,ChevronDown,ArrowUpRight,LoaderCircle,Menu,Globe2,Radio,FolderOpen,Play,Pause,StepForward,Download,WifiOff,RefreshCw} from 'lucide-react';
import{useTranslation}from 'react-i18next';
import{Toaster,toast}from 'sonner';
import{api,ApiError,NetworkError,connectionLostEvent,reconnectedEvent,sessionKey,clock,download}from './api';
import type{World,Catalog,View,Plan}from './types';
import{AppContext}from './context';
import Overview from './pages/Overview';
import{Incidents,Resources,Facilities,Coordination,Model}from './pages/Operations';
import Simulation from './pages/Simulation';
import AppDialogs from './components/AppDialogs';

const NAV:{id:View;label:string;icon:typeof Activity;group:string}[]=[{id:'overview',label:'Overview',icon:LayoutDashboard,group:'OPERATIONS'},{id:'incidents',label:'Incidents',icon:MapPin,group:'OPERATIONS'},{id:'resources',label:'Resources',icon:Ambulance,group:'OPERATIONS'},{id:'facilities',label:'Facilities',icon:Building2,group:'OPERATIONS'},{id:'simulation',label:'Simulation lab',icon:FlaskConical,group:'RESEARCH'},{id:'coordination',label:'Mutual aid',icon:ArrowLeftRight,group:'RESEARCH'},{id:'model',label:'Data & model',icon:Database,group:'RESEARCH'}];
let startup:Promise<[Catalog,World]>|null=null;
function initialise(){if(!startup)startup=(async()=>{const cat=await api<Catalog>('/catalog');let world:World;const sid=localStorage.getItem(sessionKey);if(sid){try{world=await api<World>('/state');}catch(e){if(!(e instanceof ApiError)||e.status!==401)throw e;world=await api<World>('/sessions','POST',{});}}else world=await api<World>('/sessions','POST',{});localStorage.setItem(sessionKey,world.id);return [cat,world] as [Catalog,World];})();return startup;}
export default function App(){
 const{t,i18n}=useTranslation();const[world,setWorld]=useState<World|null>(null);const[catalog,setCatalog]=useState<Catalog|null>(null);const[error,setError]=useState('');
 const[view,setView]=useState<View>('overview');const[region,setRegion]=useState('ALL');const[selected,setSelected]=useState<string|null>(null);const[modal,setModal]=useState<string|null>(null);const[plan,setPlan]=useState<Plan|null>(null);const[busy,setBusy]=useState(false);const[playing,setPlaying]=useState(false);const[speed,setSpeed]=useState(5);const[mobileNav,setMobileNav]=useState(false);const busyRef=useRef(false);const revision=useRef(-1);
 const [connected,setConnected]=useState(true);
 const [connectionMessage,setConnectionMessage]=useState('');
 const [reconnecting,setReconnecting]=useState(false);
 const connectedRef=useRef(true);
 const currentWorld=useRef<World|null>(null);
 const refreshTask=useRef<Promise<boolean>|null>(null);
 const receive=useCallback((s:World)=>{
  if(s.id!==localStorage.getItem(sessionKey))return;
  const current=currentWorld.current;
  if(current&&current.id===s.id&&s.revision<current.revision)return;
  currentWorld.current=s;revision.current=s.revision;setWorld(s);
 },[]);
 const markConnected=useCallback(()=>{
  const recovered=!connectedRef.current;
  connectedRef.current=true;setConnected(true);setConnectionMessage('');
  if(recovered)window.dispatchEvent(new Event(reconnectedEvent));
 },[]);
 const markDisconnected=useCallback((message:string)=>{
  connectedRef.current=false;setConnected(false);setPlaying(false);setConnectionMessage(message);
 },[]);
 useEffect(()=>{
  const handle=(event:Event)=>markDisconnected((event as CustomEvent<string>).detail);
  window.addEventListener(connectionLostEvent,handle);
  return()=>window.removeEventListener(connectionLostEvent,handle);
 },[markDisconnected]);
 const boot=useCallback(()=>{setError('');initialise().then(([cat,s])=>{setCatalog(cat);receive(s);setRegion(s.region);markConnected();}).catch(e=>setError(e.message));},[receive,markConnected]);
 useEffect(boot,[boot]);
 const refresh=useCallback(()=>{
  if(refreshTask.current)return refreshTask.current;
  refreshTask.current=(async()=>{
   try{const s=await api<World>('/state','GET',undefined,{timeoutMs:10_000});receive(s);markConnected();return true;}
   catch(e){markDisconnected((e as Error).message);return false;}
   finally{refreshTask.current=null;}
  })();
  return refreshTask.current;
 },[receive,markConnected,markDisconnected]);
 useEffect(()=>{
  if(connected||!world?.id)return;
  const timer=window.setInterval(()=>{void refresh();},4000);
  return()=>clearInterval(timer);
 },[connected,world?.id,refresh]);
 const mutate=useCallback(async(path:string,body?:unknown,method='POST',message?:string)=>{
  if(busyRef.current)return null;
  if(!connectedRef.current){toast.error(t('The local server is unavailable. Start START_RESCUEGRID.bat, then reconnect.'));return null;}
  busyRef.current=true;setBusy(true);
  try{
   const payload=path==='/advance'?{...(body as Record<string,unknown>),expected_revision:revision.current}:body;
   const s=await api<World>(path,method,payload);receive(s);if(message)toast.success(t(message));return s;
  }catch(e){
   toast.error(t((e as Error).message));setPlaying(false);
   if(e instanceof ApiError&&e.status===409)await refresh();
   return null;
  }finally{busyRef.current=false;setBusy(false);}
 },[receive,t,refresh]);
 const calculate=useCallback(async()=>{
  if(busyRef.current)return;
  if(!connectedRef.current){toast.error(t('The local server is unavailable. Start START_RESCUEGRID.bat, then reconnect.'));return;}
  setPlaying(false);busyRef.current=true;setBusy(true);
  try{setPlan(await api<Plan>('/plans','POST',{policy:'optimized'}));setModal('plan');}
  catch(e){toast.error(t((e as Error).message));}
  finally{busyRef.current=false;setBusy(false);}
 },[t]);
 useEffect(()=>{
  if(!playing||!connected)return;
  let stopped=false;
  let timer:number|undefined;
  const tick=async()=>{
   if(stopped||!connectedRef.current)return;
   if(busyRef.current){timer=window.setTimeout(()=>void tick(),200);return;}
   const remaining=1440-(currentWorld.current?.now??0);
   if(remaining<=0){setPlaying(false);toast.info(t('Simulation horizon reached'));return;}
   const s=await mutate('/advance',{minutes:Math.min(speed,remaining),auto:true,policy:'optimized'});
   if(stopped||!s)return;
   const finished=s.incidents.length>0&&s.incidents.every(i=>i.status==='resolved')&&s.missions.every(m=>m.completed)&&s.transfers.every(tr=>tr.status==='arrived');
   if(finished||s.now>=1440){setPlaying(false);toast.success(t(finished?'Exercise complete':'Simulation horizon reached'));return;}
   timer=window.setTimeout(()=>void tick(),1800);
  };
  void tick();
  return()=>{stopped=true;window.clearTimeout(timer);};
 },[playing,connected,speed,mutate,t]);
 useEffect(()=>{
  if(!world?.id)return;
  const source=new EventSource(`/api/stream?session_id=${world.id}`);
  source.onopen=()=>{if(!busyRef.current)void refresh();};
  source.onerror=()=>{void refresh();};
  source.onmessage=e=>{const data=JSON.parse(e.data);if(data.revision>revision.current&&!busyRef.current)void refresh();};
  return()=>source.close();
 },[world?.id,refresh]);
 useEffect(()=>{const handler=(e:KeyboardEvent)=>{document.documentElement.dataset.keyboard='true';if((e.ctrlKey||e.metaKey)&&e.key==='k'){e.preventDefault();setModal('search');}};const pointer=()=>{delete document.documentElement.dataset.keyboard;};window.addEventListener('keydown',handler);window.addEventListener('pointerdown',pointer);return()=>{window.removeEventListener('keydown',handler);window.removeEventListener('pointerdown',pointer);};},[]);
 const navigate=(v:View)=>{setView(v);setMobileNav(false);};
 if(!world||!catalog)return <div className="boot-screen"><div className="brand-mark"><Activity size={30}/></div><h1>RescueGrid <span>Chennai</span></h1>{error?<><p>{error}</p><button className="button primary" onClick={()=>{startup=null;boot();}}>{t('Retry connection')}</button></>:<p><LoaderCircle size={16} className="spinner"/>{t('Loading workspace')}</p>}<small>Emergency response · Research & simulation</small></div>;
 const context={world,catalog,view,setView:navigate,region,setRegion,selected,setSelected,busy,connected,playing,setPlaying,speed,setSpeed,modal,setModal,plan,calculate,mutate,refresh};
 const active=world.incidents.filter(i=>i.status!=='scheduled'&&i.status!=='resolved').length;
 return <AppContext.Provider value={context}><div className="app-shell">
  {mobileNav&&<button className="nav-scrim" aria-label="Close navigation" onClick={()=>setMobileNav(false)}/>}
  <aside className={`sidebar ${mobileNav?'sidebar-open':''}`}>
   <a className="brand" href="#overview" onClick={e=>{e.preventDefault();navigate('overview');}}><span className="brand-mark"><Activity size={24} strokeWidth={2}/></span><span>RescueGrid<small>CHENNAI</small></span></a>
   <div className="workspace-selector"><span className="workspace-icon"><MapPin size={18}/></span><div>{t('Chennai command')}<small>Think2Impact workspace</small></div><ChevronDown size={13}/></div>
   <nav>{['OPERATIONS','RESEARCH'].map(group=><div className="nav-group" key={group}><div className="nav-group-label">{t(group)}</div>{NAV.filter(n=>n.group===group).map(n=><button key={n.id} className={`nav-item ${view===n.id?'active':''}`} onClick={()=>navigate(n.id)} aria-current={view===n.id?'page':undefined}><n.icon size={18} strokeWidth={1.7}/><span>{t(n.label)}</span>{n.id==='incidents'&&<span className="nav-count">{active}</span>}{n.id==='simulation'&&<span className="nav-new">LAB</span>}</button>)}</div>)}</nav>
   <div className="sidebar-bottom"><div className="prototype-card"><span><FlaskConical size={15}/>{t('Research prototype')}</span><p>Explore decisions.<br/>Measure the response.</p><button onClick={()=>navigate('model')}>{t('Model assumptions')}<ArrowUpRight size={13}/></button></div><div className="workspace-profile"><span className="avatar">RG</span><div>Response analyst<small>PALS · Think2Impact</small></div><span className="online-dot"/></div></div>
  </aside>
  <div className="main-shell">
   <header className="topbar"><button className="icon-button mobile-menu" aria-label="Navigation" onClick={()=>setMobileNav(v=>!v)}><Menu size={20}/></button><div className="breadcrumbs"><span>{t(NAV.find(n=>n.id===view)?.group||'OPERATIONS')}</span><span>/</span><strong>{t(NAV.find(n=>n.id===view)?.label||'Overview')}</strong></div><div className="topbar-right"><button className="search-trigger" onClick={()=>setModal('search')}><Search size={15}/><span>{t('Search')}</span><kbd>⌘ K</kbd></button><select aria-label="Interface language" className="language-select" value={i18n.language} onChange={e=>i18n.changeLanguage(e.target.value)}><option value="en">EN</option><option value="hi">हिन्दी</option><option value="ta">தமிழ்</option></select><span className="data-badge"><span className="online-dot"/>{t('Simulated operations')}</span><span className="avatar small">RA</span></div></header>
    {!connected&&<div className="connection-banner" role="alert"><WifiOff size={20}/><div><strong>{t('Connection lost — playback paused')}</strong><p>{t(connectionMessage)} {t('Your saved workspace will reload when the server returns.')}</p></div><button className="button" disabled={reconnecting} onClick={async()=>{setReconnecting(true);try{await refresh();}finally{setReconnecting(false);}}}>{reconnecting?<LoaderCircle className="spinner" size={15}/>:<RefreshCw size={15}/>} {t(reconnecting?'Reconnecting…':'Reconnect')}</button></div>}
    <main className="main-content" id="main-content">
    {view==='overview'&&<Overview/>}{view==='incidents'&&<Incidents/>}{view==='resources'&&<Resources/>}{view==='facilities'&&<Facilities/>}{view==='simulation'&&<Simulation/>}{view==='coordination'&&<Coordination/>}{view==='model'&&<Model/>}
   </main>
    <footer className="simulation-bar"><div className="clock-label"><Radio size={15}/><span>{t('Simulation clock')}</span><strong>{clock(world.now)}</strong><span className="clock-rule"/></div><div className="playback-controls"><button className={`play-button ${playing?'playing':''}`} aria-label={t(playing?'Pause':'Play')} onClick={()=>setPlaying(!playing)} disabled={!connected||(busy&&!playing)}>{playing?<Pause size={14}/>:<Play size={14} fill="currentColor"/>}{t(playing?'Pause':'Play')}</button><button className="step-button" disabled={busy||!connected} onClick={()=>void mutate('/advance',{minutes:Math.min(5,1440-world.now),auto:true,policy:'optimized'})}><StepForward size={15}/>{t('Step')} +5m</button><select aria-label="Simulation speed" value={speed} onChange={e=>setSpeed(Number(e.target.value))}><option value={1}>1m / tick</option><option value={5}>5m / tick</option><option value={15}>15m / tick</option></select></div><div className="bar-right"><span className={`compute-status ${!connected?'text-red':''}`}>{!connected?<><WifiOff size={13}/>{t('Server unavailable')}</>:busy?<><LoaderCircle size={13} className="spinner"/>{t('Working…')}</>:<><span className="online-dot"/>{t('Ready')}</>}</span><button onClick={()=>{setPlaying(false);setModal('exercise');}}><FolderOpen size={15}/>{t('Load exercise')}</button><button onClick={()=>download().catch(e=>toast.error(t(e.message)))}><Download size={15}/>{t('Export')}</button></div></footer>
  </div><AppDialogs/><Toaster theme="dark" position="bottom-right" offset={76} closeButton toastOptions={{style:{background:'#222927',border:'1px solid #414940',color:'#f1f3eb'}}}/>
 </div></AppContext.Provider>;
}
