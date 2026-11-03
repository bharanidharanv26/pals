import {test,expect} from '@playwright/test';

test('national overview loads offline geography without JavaScript errors',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('https://**/*',route=>route.abort());
 await page.goto('/');
 await expect(page.getByRole('heading',{name:'National response overview'})).toBeVisible();
 await expect(page.locator('.maplibregl-canvas')).toBeVisible();
 await expect(page.locator('.incident-marker')).toHaveCount(12);
 expect(await page.locator('.incident-marker').first().evaluate(el=>getComputedStyle(el).position)).toBe('absolute');
 await page.waitForTimeout(1200);
 await page.screenshot({path:'test-results/overview-desktop.png',fullPage:true});
 expect(errors).toEqual([]);
 await page.getByRole('combobox',{name:'Disaster type',exact:true}).selectOption('flood');
 await expect(page.locator('.incident-marker')).toHaveCount(2);
 await expect(page.locator('.metric').nth(2).locator('.metric-value')).toHaveText('5');
});

test('create incident, explain dispatch, reserve resources and advance simulation',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Report incident',exact:true}).click();
 const dialog=page.getByRole('dialog');
 await dialog.getByRole('combobox',{name:'Region',exact:true}).selectOption('RJ');
 await dialog.getByRole('combobox',{name:'Disaster type',exact:true}).selectOption('heatwave');
 await dialog.getByLabel('Incident title',{exact:true}).fill('Browser test · heat exposure');
 await dialog.getByLabel('Patients',{exact:true}).fill('2');
 await dialog.getByRole('button',{name:'Create incident',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Incident operations',exact:true})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Browser test · heat exposure',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Calculate response plan',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Response recommendation',exact:true})).toBeVisible({timeout:30_000});
 await page.getByRole('button',{name:'Apply dispatch plan',exact:true}).click();
 await expect(page.getByRole('dialog')).not.toBeVisible();
 await page.getByRole('button',{name:'Step +5m',exact:true}).click();
 await expect(page.locator('.clock-label strong')).toHaveText('00:05:00');
 const state=await page.evaluate(async()=>fetch('/api/state',{headers:{'X-Session-ID':localStorage.getItem('rescuegrid-workspace-v1')!}}).then(r=>r.json()));
 expect(state.missions.length).toBeGreaterThan(0);
 const busy=state.resources.filter((r:{assignment:string|null})=>r.assignment);
 expect(new Set(busy.map((r:{id:string})=>r.id)).size).toBe(busy.length);
});

test('regional map and imported roads load after changing exercise',async({page})=>{
 const warnings:string[]=[];page.on('console',msg=>{if(msg.type()==='warning'||msg.type()==='error')warnings.push(msg.text());});
 await page.goto('/');await page.getByRole('button',{name:'Load exercise',exact:true}).first().click();
 const dialog=page.getByRole('dialog');
 await dialog.getByRole('button',{name:/Chennai · highway collision/}).click();
 await dialog.getByLabel('Incidents to generate').fill('1');
 await dialog.getByRole('button',{name:'Start exercise',exact:true}).click();
 await expect(page.getByRole('dialog')).not.toBeVisible();
 await expect(page.getByText('Imported roads · Simulated operations',{exact:true})).toBeVisible();
 await expect(page.locator('.incident-marker')).toHaveCount(1);
 await expect(page.locator('.map-wrap')).toHaveAttribute('data-roads-ready','true');
 expect(warnings.filter(w=>w.includes('Map source:')||w.includes('Regional roads could not load'))).toEqual([]);
 await page.waitForTimeout(1400);
 await page.screenshot({path:'test-results/chennai-roads.png',fullPage:true});
});

test('resource availability and hospital admissions can be changed',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Resources',exact:true}).first().click();
 await page.getByLabel('Region',{exact:true}).selectOption('RJ');
 const first=page.getByRole('row').filter({hasText:'RJ-ALS-01'});
 await first.getByRole('button',{name:'Take offline',exact:true}).click();
 await expect(first.getByRole('button',{name:'Restore',exact:true})).toBeVisible();
 await first.getByRole('button',{name:'Restore',exact:true}).click();
 await page.getByRole('button',{name:'Facilities',exact:true}).click();
 const card=page.locator('.facility-card').first();
 await card.getByRole('button',{name:'Close admissions',exact:true}).click();
 await expect(card.getByRole('button',{name:'Open admissions',exact:true})).toBeVisible();
 await card.getByRole('button',{name:'Add capacity',exact:true}).click();
 await expect(card.locator('.capacity-heading strong')).toContainText('/ 5');
});

test('controlled experiment completes and recorded trace can be replayed',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:/Simulation lab/}).click();
 await page.getByRole('combobox',{name:'Scenario',exact:true}).selectOption('heatwave');
 await page.getByRole('combobox',{name:'Horizon (minutes)',exact:true}).selectOption('120');
 await page.getByRole('button',{name:'Run comparison',exact:true}).click();
 await expect(page.getByText('Computed results',{exact:true})).toBeVisible({timeout:90_000});
 await expect(page.locator('.comparison-card')).toHaveCount(3);
 await page.getByRole('button',{name:'Load optimised trace',exact:true}).click();
 await expect(page.locator('.replay-controls')).toBeVisible();
 await page.locator('.replay-controls input').fill('120');
 await expect(page.locator('.replay-events .timeline-row').first()).toBeVisible();
 await page.locator('.main-content').evaluate(el=>{el.scrollTop=0;});
 await page.screenshot({path:'test-results/simulation-results.png',fullPage:true});
});

test('pre-positioning creates real timed cross-region transfers',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Mutual aid',exact:true}).click();
 await page.getByRole('button',{name:'Calculate placement',exact:true}).click();
 await expect(page.locator('.placement-results')).toBeVisible();
 await page.getByRole('button',{name:'Mobilise placement',exact:true}).click();
 await expect(page.getByText('No transfers scheduled',{exact:true})).not.toBeVisible();
 await expect(page.locator('table tbody tr')).toHaveCount(2);
});

test('Hindi and Tamil navigation and responsive phone layout',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 await page.goto('/');await expect(page.getByRole('heading',{name:'National response overview'})).toBeVisible();
 await page.getByLabel('Interface language').selectOption('hi');
 await expect(page.getByRole('heading',{name:'राष्ट्रीय प्रतिक्रिया अवलोकन'})).toBeVisible();
 await page.getByLabel('Interface language').selectOption('ta');
 await expect(page.getByRole('heading',{name:'தேசிய மீட்பு மேலோட்டம்'})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 await page.getByLabel('Interface language').selectOption('en');
 await page.screenshot({path:'test-results/overview-mobile.png',fullPage:true});
 await page.getByRole('button',{name:'Navigation',exact:true}).click();
 await page.getByRole('button',{name:'Data & model',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Source transparency'})).toBeVisible();
});
