import {defineConfig} from '@playwright/test';
import path from 'node:path';
const python=process.platform==='win32'?path.resolve('../.venv/Scripts/python.exe'):path.resolve('../.venv/bin/python');
const port=8010;
export default defineConfig({
 testDir:'./tests',timeout:120_000,expect:{timeout:15_000},fullyParallel:false,workers:1,
 reporter:[['list'],['html',{open:'never'}]],
 use:{baseURL:`http://127.0.0.1:${port}`,viewport:{width:1440,height:1000},trace:'retain-on-failure',screenshot:'only-on-failure',launchOptions:{args:['--enable-unsafe-swiftshader']}},
 webServer:{command:`"${python}" -m uvicorn backend.app:app --app-dir .. --host 127.0.0.1 --port ${port}`,url:`http://127.0.0.1:${port}/api/health`,reuseExistingServer:false,timeout:60_000,env:{DATABASE_URL:`sqlite:///${path.resolve('../runtime/browser-tests.db').replaceAll('\\','/')}`}},
});
