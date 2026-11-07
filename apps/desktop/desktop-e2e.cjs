const path = require('node:path');
const fs = require('node:fs/promises');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { _electron } = require(path.join(process.env.USERPROFILE,'.cache','codex-runtimes','codex-primary-runtime','dependencies','node','node_modules','playwright'));
async function main(){
  const root=path.resolve(__dirname,'../..');
  const exe=JSON.parse(await fs.readFile(path.join(root,'data','desktop','current.json'),'utf8')).executable;
  const testEnv={...process.env,CREATOROS_DESKTOP_TEST:'1'};
  const client=await _electron.launch({executablePath:exe,env:testEnv,timeout:30000});
  try{
    const page=await client.firstWindow();
    await page.waitForURL(url=>url.protocol==='http:',{timeout:150000});
    await page.getByRole('heading',{name:'欢迎回到实验室'}).waitFor({timeout:30000});
    assert.equal(await page.evaluate(()=>typeof window.require),'undefined');
    const settings=await client.evaluate(({BrowserWindow})=>{const win=BrowserWindow.getAllWindows()[0]; const p=win.webContents.getLastWebPreferences();return {sandbox:p.sandbox,nodeIntegration:p.nodeIntegration,contextIsolation:p.contextIsolation};});
    assert.deepEqual(settings,{sandbox:true,nodeIntegration:false,contextIsolation:true});
    await new Promise((resolve,reject)=>{const second=spawn(exe,[],{windowsHide:true,env:testEnv});second.on('error',reject);second.on('exit',code=>code===0?resolve():reject(Error('Second instance failed')));});
    assert.equal(await client.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows().length),1);
    await fs.mkdir(path.join(root,'docs','screenshots'),{recursive:true});
    await page.screenshot({path:path.join(root,'docs','screenshots','desktop-login.png')});
    console.log('Desktop verified: automatic service connection, login screen, isolated renderer, single instance.');
  }finally{
    // Force the test-owned process to exit; Electron's inspector can otherwise hold shutdown open.
    await client.evaluate(({app})=>app.exit(0)).catch(()=>{});
    await client.close().catch(()=>{});
  }
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
