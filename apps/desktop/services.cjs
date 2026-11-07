const fs = require('node:fs/promises');
const path = require('node:path');
const { spawn } = require('node:child_process');

function validLocalURL(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' && url.hostname === '127.0.0.1' && !url.username && !url.password;
  } catch { return false; }
}

async function serviceReady(base, fetcher = fetch) {
  if (!validLocalURL(base)) return false;
  try {
    const response = await fetcher(`${base}/api/health`, { signal: AbortSignal.timeout(2500), redirect: 'error' });
    const status = await response.json();
    return response.ok && status.service === 'CreatorOS' && status.database === 'connected' && status.status === 'ok';
  } catch { return false; }
}

async function readAddress(root) {
  try {
    const state = JSON.parse((await fs.readFile(path.join(root, 'data', 'processes.json'), 'utf8')).replace(/^\uFEFF/, ''));
    return validLocalURL(state.web_url) ? new URL(state.web_url).origin : null;
  } catch { return null; }
}

function runScript(root, name) {
  const powershell = path.join(process.env.SystemRoot, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe');
  return new Promise((resolve, reject) => {
    const child = spawn(powershell, ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', path.join(root, 'scripts', name)], {cwd:root, windowsHide:true, stdio:['ignore','pipe','pipe']});
    child.stdout.resume();
    child.stderr.resume();
    child.on('error', reject);
    child.on('exit', code => code === 0 ? resolve() : reject(Error(`本地服务启动失败（${code}），请查看项目 data/logs 或先运行 scripts/setup.ps1。`)));
  });
}

async function ensureServices(root) {
  let address = await readAddress(root);
  if (address && await serviceReady(address)) return address;
  await runScript(root, 'start.ps1');
  const deadline = Date.now() + 90000;
  while (Date.now() < deadline) {
    address = await readAddress(root);
    if (address && await serviceReady(address)) return address;
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  throw Error('本地服务未就绪。请查看 data/logs；若只有部分服务运行，可在项目中执行 stop.ps1 后重新打开。');
}
module.exports = { validLocalURL, serviceReady, ensureServices, runScript };
