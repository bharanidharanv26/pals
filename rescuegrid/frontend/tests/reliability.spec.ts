import {test,expect,type Page} from '@playwright/test';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import net from 'node:net';
import path from 'node:path';

const execute=promisify(execFile);
const root=path.resolve('..');
const python=path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
const sessionKey='rescuegrid-workspace-v1';

async function freePort(){
 const server=net.createServer();
 await new Promise<void>((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',()=>resolve());});
 const port=(server.address() as net.AddressInfo).port;
 await new Promise<void>((resolve,reject)=>server.close(e=>e?reject(e):resolve()));
 return port;
}
async function state(page:Page){
 return page.evaluate(async key=>fetch('/api/state',{headers:{'X-Session-ID':localStorage.getItem(key)!}}).then(response=>response.json()),sessionKey);
}

test('background launch survives 30 seconds, Play advances, restart restores the same workspace',async({page,request},info)=>{
 test.setTimeout(150_000);
 const port=await freePort();
 const base=`http://127.0.0.1:${port}`;
 const env={...process.env,DATABASE_URL:`sqlite:///${info.outputPath('restart.db').replaceAll('\\','/')}`};
 const run=(...args:string[])=>execute(python,[path.join(root,'scripts/launch.py'),...args,'--port',String(port),'--no-browser'],{cwd:root,env,timeout:50_000,windowsHide:true});
 const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
 try{
  await run('--background'); // The launcher command exits before the browser starts.
  const firstHealth=await (await request.get(`${base}/api/health`)).json();
  await run('--background'); // Repeated starts reuse the service instead of binding twice.
  expect((await (await request.get(`${base}/api/health`)).json()).pid).toBe(firstHealth.pid);
  await page.goto(base);
  await expect(page.getByRole('heading',{name:'National response overview'})).toBeVisible();
  const original=await state(page);
  await page.getByLabel('Simulation speed').selectOption('1');
  await page.getByRole('button',{name:'Play',exact:true}).click();
  await expect.poll(async()=>(await state(page)).now,{timeout:25_000}).toBeGreaterThan(1);
  // The reported regression killed the process at 30 seconds. This is an intentional soak.
  await page.waitForTimeout(35_000);
  await expect(page.locator('.connection-banner')).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Pause',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Pause',exact:true}).click();
  await expect(page.locator('.compute-status')).toHaveText('Ready');
  const paused=await state(page);
  expect(paused.now).toBeGreaterThan(8);
  expect(paused.missions.length).toBeGreaterThan(0);
  await page.waitForTimeout(2200);
  expect((await state(page)).now).toBe(paused.now);
  await run('--stop');
  await expect(page.locator('.connection-banner')).toBeVisible({timeout:15_000});
  await expect(page.getByRole('button',{name:'Play',exact:true})).toBeDisabled();
  await page.screenshot({path:info.outputPath('backend-disconnected.png')});
  await run('--background');
  await expect(page.locator('.connection-banner')).toHaveCount(0,{timeout:20_000});
  await expect(page.getByRole('button',{name:'Play',exact:true})).toBeEnabled();
  const restored=await state(page);
  expect(restored.id).toBe(original.id);
  expect(restored.now).toBe(paused.now);
  expect(restored.missions).toEqual(paused.missions);
  await page.getByRole('button',{name:'Step +5m',exact:true}).click();
  await expect.poll(async()=>(await state(page)).now).toBe(paused.now+5);
  expect(errors).toEqual([]);
 }finally{
  await page.goto('about:blank');
  await run('--stop');
 }
});

test('lost response pauses playback and reconnect reads committed state without replaying the action',async({page,request})=>{
 await page.goto('/');
 await expect(page.getByRole('heading',{name:'National response overview'})).toBeVisible();
 const before=await state(page);
 let blockState=false;let advanceCalls=0;
 await page.route('**/api/state',route=>blockState?route.abort('failed'):route.continue());
 await page.route('**/api/advance',async route=>{
  advanceCalls++;
  if(advanceCalls===1){
   blockState=true;
   const committed=await route.fetch();
   expect(committed.ok()).toBe(true);
   await route.abort('failed'); // Server committed; client never received the result.
  }else await route.continue();
 });
 await page.getByRole('button',{name:'Play',exact:true}).click();
 await expect(page.locator('.connection-banner')).toBeVisible();
 await expect(page.getByRole('button',{name:'Play',exact:true})).toBeDisabled();
 const committed=await (await request.get('/api/state',{headers:{'X-Session-ID':before.id}})).json();
 expect(committed.now).toBe(before.now+5);
 expect(advanceCalls).toBe(1);
 blockState=false;
 await expect(page.locator('.connection-banner')).toHaveCount(0,{timeout:15_000});
 await expect(page.locator('.clock-label strong')).toHaveText('00:05:00');
 await expect(page.getByRole('button',{name:'Play',exact:true})).toBeEnabled();
 await page.waitForTimeout(2200);
 expect(advanceCalls).toBe(1);
 expect((await state(page)).id).toBe(before.id);
 await page.getByRole('button',{name:'Step +5m',exact:true}).click();
 await expect(page.locator('.clock-label strong')).toHaveText('00:10:00');
});

test('late regional geometry cannot replace All India and wheel scrolling does not zoom the map',async({page})=>{
 await page.goto('/');
 await expect(page.locator('.incident-marker')).toHaveCount(12);
 let release!:()=>void;
 const delayed=new Promise<void>(resolve=>{release=resolve;});
 let requested!:()=>void;
 const incoming=new Promise<void>(resolve=>{requested=resolve;});
 await page.route('**/api/networks/TN',async route=>{
  requested();await delayed;
  try{await route.continue();}catch{/* This obsolete request is deliberately aborted by the component. */}
 });
 await page.getByRole('combobox',{name:'Region',exact:true}).selectOption('TN');
 await incoming;
 await page.getByRole('combobox',{name:'Region',exact:true}).selectOption('ALL');
 await expect(page.locator('.incident-marker')).toHaveCount(12);
 const offset=()=>page.locator('.incident-marker').first().evaluate(el=>{
  const map=el.closest('.map-wrap')!.getBoundingClientRect();const pin=el.getBoundingClientRect();
  return {x:pin.x-map.x,y:pin.y-map.y};
 });
 const before=await offset();release();
 await page.waitForTimeout(350);
 expect((await offset()).y).toBeCloseTo(before.y,0);
 await page.locator('.map-canvas').hover();
 await page.mouse.wheel(0,240);
 await page.waitForTimeout(250);
 const after=await offset();
 expect(after.x).toBeCloseTo(before.x,0);expect(after.y).toBeCloseTo(before.y,0);
 await expect(page.locator('.connection-banner')).toHaveCount(0);
});
