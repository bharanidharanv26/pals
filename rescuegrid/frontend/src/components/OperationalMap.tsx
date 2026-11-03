import { useEffect,useRef,useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import type {GeoJSONSource,Map as MapType} from 'maplibre-gl';
import type {Feature,FeatureCollection,LineString} from 'geojson';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import { LocateFixed,Minus,Plus,Map as MapIcon,Layers,Maximize2,RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type {Catalog,World,Plan} from '../types';
import {api,requestJson,reconnectedEvent} from '../api';

// MapLibre 6 ships a separate module worker. Bundle it locally for offline demos.
maplibregl.setWorkerUrl(workerUrl);
maplibregl.setWorkerCount(1);

type Props={world:World;catalog:Catalog;region:string;selected:string|null;onSelect:(id:string)=>void;onRegion:(id:string)=>void;plan?:Plan|null;large?:boolean;hazard?:string};
export default function OperationalMap({world,catalog,region,selected,onSelect,onRegion,plan,large,hazard='all'}:Props){
 const{t}=useTranslation();const container=useRef<HTMLDivElement>(null);const map=useRef<MapType|null>(null);const markers=useRef<maplibregl.Marker[]>([]);const callbacks=useRef({onSelect,onRegion});callbacks.current={onSelect,onRegion};
 const [loaded,setLoaded]=useState(false);const[streets,setStreets]=useState(false);const[showAssets,setShowAssets]=useState(true);const[mapError,setMapError]=useState(false);const[roadsReady,setRoadsReady]=useState(false);
 const regionBounds=useRef<maplibregl.LngLatBounds|null>(null);
 const currentRegion=useRef(region);currentRegion.current=region;
 const currentWorld=useRef(world);currentWorld.current=world;
 const roadRequest=useRef(0);
 const requestedRoadRegion=useRef<string|null>(null);
 const [retry,setRetry]=useState(0);
 const [referenceError,setReferenceError]=useState(false);
 const [roadError,setRoadError]=useState(false);
 useEffect(()=>{const recover=()=>setRetry(n=>n+1);window.addEventListener(reconnectedEvent,recover);return()=>window.removeEventListener(reconnectedEvent,recover);},[]);
 useEffect(()=>{
  if(!container.current)return;
  try{
   const m=new maplibregl.Map({container:container.current,center:[80,23],zoom:3.55,minZoom:2.7,maxZoom:16,scrollZoom:false,attributionControl:false,style:{version:8,sources:{states:{type:'geojson',data:{type:'FeatureCollection',features:[]}}},layers:[{id:'background',type:'background',paint:{'background-color':'#131d21'}},{id:'states',type:'fill',source:'states',paint:{'fill-color':'#26312e','fill-opacity':.92}},{id:'borders',type:'line',source:'states',paint:{'line-color':'#506052','line-opacity':.55,'line-width':.8}},{id:'selected-state',type:'fill',source:'states',filter:['==','region','_'],paint:{'fill-color':'#b8cf7d','fill-opacity':.13}}]}});
   map.current=m;
   m.on('load',()=>{if(map.current===m){setLoaded(true);m.resize();}});
   m.on('sourcedata',e=>{if(map.current===m&&e.sourceId==='roads'&&e.isSourceLoaded&&requestedRoadRegion.current===currentRegion.current)setRoadsReady(true);});
   m.on('error',e=>console.warn('Map source:',e.error.message));
   m.on('click','states',e=>{const id=e.features?.[0]?.properties?.region;if(id)callbacks.current.onRegion(id);});
   m.on('mouseenter','states',()=>{m.getCanvas().style.cursor='pointer';});m.on('mouseleave','states',()=>{m.getCanvas().style.cursor='';});
   m.addControl(new maplibregl.AttributionControl({compact:true,customAttribution:'Reference geography: geoBoundaries / DataMeet · Synthetic operations'}),'bottom-right');
   const observer=new ResizeObserver(()=>m.resize());observer.observe(container.current);
   return()=>{observer.disconnect();markers.current.forEach(m=>m.remove());m.remove();map.current=null;setLoaded(false);};
  }catch{setMapError(true);}
 },[]);
 useEffect(()=>{
  const m=map.current;if(!m||!loaded)return;
  const controller=new AbortController();setReferenceError(false);
  requestJson<FeatureCollection>('/geography/states.geojson',{signal:controller.signal,timeoutMs:15_000}).then(data=>{
   if(!controller.signal.aborted&&map.current===m)(m.getSource('states') as GeoJSONSource).setData(data);
  }).catch(()=>{if(!controller.signal.aborted)setReferenceError(true);});
  return()=>controller.abort();
 },[loaded,retry]);
 useEffect(()=>{
  const m=map.current;if(!m||!loaded)return;
  m.setFilter('selected-state',['==','region',region]);
  if(region==='ALL'){m.fitBounds([[67,6],[98,37]],{padding:{top:42,bottom:28,left:20,right:20},duration:0});}
  else{const r=catalog.regions.find(r=>r.id===region);if(r)m.jumpTo({center:[r.lon,r.lat],zoom:10.05});}
  const controller=new AbortController();
  const generation=++roadRequest.current;
  regionBounds.current=null;
  requestedRoadRegion.current=null;
  setRoadsReady(false);
  setRoadError(false);
  if(region!=='ALL')api<FeatureCollection<LineString>>(`/networks/${region}`,'GET',undefined,{signal:controller.signal,timeoutMs:30_000}).then(data=>{
   // A slow previous region must never pan the current map back to its old bounds.
   if(controller.signal.aborted||generation!==roadRequest.current||currentRegion.current!==region||map.current!==m)return;
   requestedRoadRegion.current=region;
   if(m.getSource('roads'))(m.getSource('roads') as GeoJSONSource).setData(data);
   else{m.addSource('roads',{type:'geojson',data});m.addLayer({id:'roads',type:'line',source:'roads',paint:{'line-color':'#5d7467','line-width':1.2,'line-opacity':.65}});}
   const closed=currentWorld.current.conditions.closed_edges[region]||[];
   m.setPaintProperty('roads','line-color',['case',['in',['get','id'],['literal',closed]],'#ef8277','#5d7467']);
   const bounds=new maplibregl.LngLatBounds();
   for(const feature of data.features)for(const coord of feature.geometry.coordinates)bounds.extend([coord[0],coord[1]]);
   if(!bounds.isEmpty()){regionBounds.current=bounds;m.fitBounds(bounds,{padding:65,maxZoom:13.5,duration:0});}
  }).catch(()=>{if(!controller.signal.aborted&&currentRegion.current===region)setRoadError(true);});
  else if(m.getSource('roads'))(m.getSource('roads') as GeoJSONSource).setData({type:'FeatureCollection',features:[]});
  return()=>controller.abort();
 },[region,loaded,catalog,retry]);
 useEffect(()=>{
  const m=map.current;if(!m||!loaded)return;
  markers.current.forEach(marker=>marker.remove());markers.current=[];
  function marker(el:HTMLElement,pos:number[]){const mark=new maplibregl.Marker({element:el}).setLngLat([pos[0],pos[1]]).addTo(m!);markers.current.push(mark);}
  if(region==='ALL')catalog.regions.filter(r=>['TN','DL','AS','MH','WB','GJ','OD','UK','RJ','AN'].includes(r.id)).forEach(r=>{const el=document.createElement('div');el.className='city-label';el.textContent=r.city;marker(el,[r.lon,r.lat-.5]);});
  if(region!=='ALL'&&showAssets){
   world.facilities.filter(f=>f.region===region).forEach(f=>{const el=document.createElement('div');el.className=`facility-marker ${f.closed?'closed':''}`;el.textContent=f.kind==='shelter'?'S':'H';el.title=`${f.name} · ${f.occupied}/${f.capacity}`;marker(el,f.position);});
   world.resources.filter(r=>r.region===region&&r.status!=='offline').forEach(r=>{const el=document.createElement('div');el.className=`resource-marker ${r.type==='als'||r.type==='bls'?'ambulance-marker':''}`;el.title=`${r.id} · ${r.status}`;el.textContent=r.type==='als'||r.type==='bls'?'+':'·';marker(el,r.position);});
  }
  world.incidents.filter(i=>i.status!=='scheduled'&&(region==='ALL'||i.region===region)&&(hazard==='all'||i.hazard===hazard)).forEach(i=>{
   const el=document.createElement('button');el.className=`incident-marker ${i.severity} ${i.id===selected?'selected':''} ${i.status==='resolved'?'resolved':''}`;el.setAttribute('aria-label',`${i.title} · ${i.severity}`);el.title=`${i.id} · ${i.title}`;
   const dot=document.createElement('span');dot.className='marker-core';el.appendChild(dot);
   if(i.id===selected){const tag=document.createElement('span');tag.className='marker-tag';tag.textContent=`${i.id} · ${i.patients.length} ${t('patients')}`;el.appendChild(tag);}
   el.addEventListener('click',e=>{e.stopPropagation();callbacks.current.onSelect(i.id);});marker(el,i.position);
  });
  const features:Feature[]=[];
  const visibleIds=new Set(world.incidents.filter(i=>(region==='ALL'||i.region===region)&&(hazard==='all'||i.hazard===hazard)).map(i=>i.id));
  const focus=selected&&visibleIds.has(selected)?selected:null;
  const paths=plan?.assignments.filter(a=>visibleIds.has(a.incident_id)).flatMap(a=>[a.response_route,a.transport_route])||world.missions.filter(mi=>visibleIds.has(mi.incident_id)&&!mi.completed&&(!focus||mi.incident_id===focus)).flatMap(mi=>[mi.route,mi.response_route,mi.transport_route,mi.transfer_route].filter(Boolean));
  paths.forEach((p)=>{if(p&&p.coordinates.length>1)features.push({type:'Feature',properties:{mode:p.mode},geometry:{type:'LineString',coordinates:p.coordinates}});});
  const geo:FeatureCollection={type:'FeatureCollection',features};
  if(m.getSource('routes'))(m.getSource('routes') as GeoJSONSource).setData(geo);
  else{m.addSource('routes',{type:'geojson',data:geo});m.addLayer({id:'routes-glow',type:'line',source:'routes',paint:{'line-color':'#d2ed8a','line-width':8,'line-opacity':.1}});m.addLayer({id:'routes',type:'line',source:'routes',paint:{'line-color':['match',['get','mode'],'water','#6bbbdc','#d2ed8a'],'line-width':2.8,'line-opacity':.95}});}
  const closed=world.conditions.closed_edges[region]||[];
  if(m.getLayer('roads'))m.setPaintProperty('roads','line-color',['case',['in',['get','id'],['literal',closed]],'#ef8277','#5d7467']);
 },[loaded,world,region,selected,showAssets,plan,catalog,t,hazard]);
 useEffect(()=>{
  const m=map.current;if(!m||!loaded)return;
  if(streets&&!m.getSource('osm')){m.addSource('osm',{type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],tileSize:256,attribution:'© OpenStreetMap contributors'});m.addLayer({id:'osm',type:'raster',source:'osm',paint:{'raster-opacity':.6,'raster-saturation':-.8}},'states');}
  if(m.getLayer('osm'))m.setLayoutProperty('osm','visibility',streets?'visible':'none');
  m.setPaintProperty('states','fill-opacity',streets?.1:.92);
 },[streets,loaded]);
 return <div className={`map-wrap ${large?'map-large':''}`} data-roads-ready={roadsReady}>
  <div ref={container} className="map-canvas"/>
  {mapError&&<div className="map-fallback">Your browser could not start WebGL. Incident lists and all simulation controls remain available.</div>}
  {(referenceError||roadError)&&<div className="map-source-warning" role="status"><span>{referenceError?'Reference geography could not load.':'The selected road package could not load.'}</span><button onClick={()=>setRetry(n=>n+1)}><RefreshCw size={12}/>{t('Retry connection')}</button></div>}
  <div className="map-top"><div className="map-label"><span className="online-dot"/>{t('Operational map')}<span className="map-mode">{region==='ALL'?'INDIA':catalog.regions.find(r=>r.id===region)?.name}</span></div><button className="map-tool" onClick={()=>setStreets(v=>!v)} aria-pressed={streets}><MapIcon size={14}/>{t('Street map')}</button></div>
  {region==='ALL'&&<><span className="sea-label sea-west">ARABIAN<br/>SEA</span><span className="sea-label sea-east">BAY OF<br/>BENGAL</span></>}
   <div className="map-controls">
    <button title={t('Fit view')} aria-label={t('Fit view')} onClick={()=>{
     if(region==='ALL')map.current?.fitBounds([[67,6],[98,37]],{padding:30,duration:0});
     else if(regionBounds.current)map.current?.fitBounds(regionBounds.current,{padding:65,maxZoom:13.5,duration:0});
     else{const r=catalog.regions.find(r=>r.id===region)!;map.current?.jumpTo({center:[r.lon,r.lat],zoom:10.05});}
    }}><LocateFixed size={17}/></button>
    <button aria-label="Zoom in" onClick={()=>map.current?.zoomIn({duration:160})}><Plus size={17}/></button>
    <button aria-label="Zoom out" onClick={()=>map.current?.zoomOut({duration:160})}><Minus size={17}/></button>
    <button title={t('Resources')} aria-label={t('Resources')} aria-pressed={showAssets} onClick={()=>setShowAssets(v=>!v)}><Layers size={17}/></button>
    <button aria-label="Fullscreen map" onClick={()=>{if(document.fullscreenElement)document.exitFullscreen();else container.current?.parentElement?.requestFullscreen();}}><Maximize2 size={16}/></button>
   </div>
  <div className="map-legend"><span><i className="legend-dot critical"/>{t('critical')}</span><span><i className="legend-dot serious"/>{t('serious')}</span><span><i className="legend-dot minor"/>{t('minor')}</span></div>
  {region!=='ALL'&&<div className="map-data-note">{t(catalog.networks.find(n=>n.region===region)?.mode==='osm'?'Imported roads':'Generated network')} · {t('Simulated operations')}</div>}
 </div>;
}
