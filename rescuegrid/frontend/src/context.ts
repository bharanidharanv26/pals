import {createContext,useContext} from 'react';
import type{Catalog,World,View,Plan}from './types';
type Context={world:World;catalog:Catalog;view:View;setView:(v:View)=>void;region:string;setRegion:(r:string)=>void;selected:string|null;setSelected:(s:string|null)=>void;busy:boolean;connected:boolean;playing:boolean;setPlaying:(v:boolean)=>void;speed:number;setSpeed:(n:number)=>void;modal:string|null;setModal:(m:string|null)=>void;plan:Plan|null;calculate:()=>Promise<void>;mutate:(path:string,body?:unknown,method?:string,message?:string)=>Promise<World|null>;refresh:()=>Promise<boolean>};
export const AppContext=createContext<Context|null>(null);
export function useApp(){const c=useContext(AppContext);if(!c)throw new Error('App context missing');return c;}
