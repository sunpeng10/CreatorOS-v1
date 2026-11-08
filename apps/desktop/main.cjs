const { app, BrowserWindow, Menu, dialog, shell, session } = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const { ensureServices } = require('./services.cjs');

app.setName('CreatorOS');
app.setAppUserModelId('com.creatoros.desktop');
let window;
let origin;
let cookieStore;
let flushingCookiesOnQuit = false;
let quitAfterCookieFlush = false;
const configFile = path.join(__dirname, 'runtime.json');
let root = fs.existsSync(configFile) ? JSON.parse(fs.readFileSync(configFile, 'utf8')).projectRoot : path.resolve(__dirname, '../..');
if (process.env.CREATOROS_DESKTOP_TEST === '1') {
  const profile = path.join(root, 'data', 'desktop-test-profile');
  fs.mkdirSync(profile, {recursive:true});
  app.setPath('userData', profile);
}
let booting = false;
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) app.quit();
else {
  app.on('second-instance', () => {
    if (!window) return;
    if (window.isMinimized()) window.restore();
    window.show();
    window.focus();
  });
  app.whenReady().then(async () => {
    try {
      if (!fs.existsSync(path.join(root, 'services', 'api', 'app', 'main.py'))) throw Error('项目目录已移动。请在新位置运行 scripts/install-desktop.ps1 重新建立入口。');
      session.defaultSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
      cookieStore = session.defaultSession.cookies;
      // Electron batches cookie writes; save login and logout changes immediately.
      cookieStore.on('changed', () => { void flushCookies(); });
      window = new BrowserWindow({
        title:'CreatorOS · 爆款实验室', width:1440, height:960, minWidth:900, minHeight:650,
        backgroundColor:'#f7f9f4', icon:path.join(__dirname, 'assets', 'creatoros.ico'),
        webPreferences:{nodeIntegration:false, contextIsolation:true, sandbox:true, webSecurity:true, spellcheck:false},
      });
      window.on('closed', () => { window = null; });
      window.webContents.on('page-title-updated', event => { event.preventDefault(); if(window) window.setTitle('CreatorOS · 爆款实验室'); });
      window.webContents.setWindowOpenHandler(({ url }) => {
        if (safeExternal(url)) void shell.openExternal(url);
        return {action:'deny'};
      });
      window.webContents.on('will-navigate', (event, url) => {
        if (origin && new URL(url).origin === origin) return;
        event.preventDefault();
        if (safeExternal(url)) void shell.openExternal(url);
      });
      Menu.setApplicationMenu(Menu.buildFromTemplate([
        {label:'CreatorOS',submenu:[
          {label:'工作台',click:()=>{if(origin)void window.loadURL(origin+'/dashboard');}},
          {label:'人工审批',click:()=>{if(origin)void window.loadURL(origin+'/admin/approvals');}},
          {type:'separator'}, {label:'退出桌面窗口',role:'quit'},
        ]},
        {label:'编辑',submenu:[{role:'undo'},{role:'redo'},{type:'separator'},{role:'cut'},{role:'copy'},{role:'paste'},{role:'selectAll'}]},
        {label:'视图',submenu:[{role:'reload'},{role:'resetZoom'},{role:'zoomIn'},{role:'zoomOut'},{role:'togglefullscreen'}]},
        {label:'帮助',submenu:[
          {label:'重新连接本地服务',click:()=>void boot()},
          {label:'打开运行日志',click:()=>void shell.openPath(path.join(root,'data','logs'))},
          {label:'关于 CreatorOS',click:()=>void dialog.showMessageBox(window,{type:'info',title:'CreatorOS',message:'CreatorOS · 爆款实验室',detail:'让每一次创作都有数据依据\n关闭窗口后，本地分析服务继续运行。\n账号与业务数据保存在当前项目中。'})},
        ]},
      ]));
      await boot();
    } catch (error) {
      dialog.showErrorBox('CreatorOS 启动失败', error.message);
      app.quit();
    }
  });
}

function safeExternal(value) {
  try { const url=new URL(value); return ['http:','https:'].includes(url.protocol)&&!url.username&&!url.password; } catch{return false;}
}
function flushCookies() {
  return cookieStore.flushStore().catch(error => console.error('CreatorOS 登录状态保存失败：', error.message));
}
async function boot() {
  if (booting || !window) return;
  booting=true;
  try {
    await window.loadFile(path.join(__dirname,'splash.html'));
    origin=await ensureServices(root);
    if(window) await window.loadURL(origin+'/dashboard');
  } catch(error) {
    if(window) await dialog.showMessageBox(window,{type:'error',title:'本地服务暂不可用',message:error.message,detail:'修复后可从“帮助 → 重新连接本地服务”重试。'});
  } finally { booting=false; }
}
app.on('window-all-closed',()=>app.quit());
app.on('will-quit', event => {
  if (!cookieStore || quitAfterCookieFlush) return;
  event.preventDefault();
  if (flushingCookiesOnQuit) return;
  flushingCookiesOnQuit = true;
  void flushCookies().then(() => {
    quitAfterCookieFlush = true;
    app.quit();
  });
});
