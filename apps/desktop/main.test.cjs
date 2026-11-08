const { test } = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const nextTurn = () => new Promise(resolve => setImmediate(resolve));

async function loadMain(flushStore = async () => {}) {
  const app = new EventEmitter();
  const cookies = new EventEmitter();
  const result = { app, cookies, flushes: 0, quitRequests: 0, quitCompletions: 0, errors: [] };
  cookies.flushStore = () => { result.flushes++; return flushStore(); };
  Object.assign(app, {
    setName() {}, setAppUserModelId() {}, requestSingleInstanceLock: () => true,
    whenReady: () => Promise.resolve(),
    quit() {
      result.quitRequests++;
      const event = { defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
      app.emit('will-quit', event);
      if (!event.defaultPrevented) result.quitCompletions++;
    },
  });
  class BrowserWindow extends EventEmitter {
    constructor() {
      super();
      this.webContents = new EventEmitter();
      this.webContents.setWindowOpenHandler = () => {};
    }
    async loadFile() {}
    async loadURL() {}
  }
  const electron = {
    app, BrowserWindow,
    session: { defaultSession: { cookies, setPermissionRequestHandler() {} } },
    Menu: { buildFromTemplate: template => template, setApplicationMenu() {} },
    dialog: { showErrorBox: (...args) => result.errors.push(args), showMessageBox: async () => {} },
    shell: {},
  };
  const mainPath = path.join(__dirname, 'main.cjs');
  vm.runInNewContext(fs.readFileSync(mainPath, 'utf8'), {
    require(name) {
      if (name === 'electron') return electron;
      if (name === './services.cjs') return { ensureServices: async () => 'http://127.0.0.1:3000' };
      if (name === 'node:fs') return { existsSync: file => file.endsWith('main.py') };
      return require(name);
    },
    __dirname, process: { env: {} }, URL,
    console: { error: (...args) => result.errors.push(args) },
  }, { filename: mainPath });
  await nextTurn();
  return result;
}

test('login cookie changes are flushed without waiting for the periodic disk write', async () => {
  const client = await loadMain();
  client.cookies.emit('changed', {}, { name: 'creatoros_session' }, 'explicit', false);
  await nextTurn();
  assert.equal(client.flushes, 1);
  assert.equal(client.errors.length, 0);
});

test('logout cookie removal is flushed to prevent a stale login on reopening', async () => {
  const client = await loadMain();
  client.cookies.emit('changed', {}, { name: 'creatoros_session' }, 'explicit', true);
  await nextTurn();
  assert.equal(client.flushes, 1);
  assert.equal(client.errors.length, 0);
});

test('normal quit waits for cookie storage once and completes without recursive flushing', async () => {
  let finishFlush;
  const pendingFlush = new Promise(resolve => { finishFlush = resolve; });
  const client = await loadMain(() => pendingFlush);
  client.app.emit('window-all-closed');
  assert.equal(client.flushes, 1);
  assert.equal(client.quitCompletions, 0);
  client.app.quit();
  assert.equal(client.flushes, 1);
  assert.equal(client.quitCompletions, 0);
  finishFlush();
  await nextTurn();
  assert.equal(client.quitCompletions, 1);
  assert.equal(client.quitRequests, 3);
  assert.equal(client.flushes, 1);
});

test('cookie save failure is handled and does not prevent normal quit', async () => {
  const client = await loadMain(async () => { throw Error('disk unavailable'); });
  client.app.emit('window-all-closed');
  assert.equal(client.quitCompletions, 0);
  await nextTurn();
  assert.equal(client.quitCompletions, 1);
  assert.equal(client.flushes, 1);
  assert.equal(client.errors.length, 1);
});

test('cookie-change save rejection is handled without quitting the app', async () => {
  const client = await loadMain(async () => { throw Error('disk unavailable'); });
  client.cookies.emit('changed', {}, { name: 'creatoros_session' }, 'explicit', true);
  await nextTurn();
  assert.equal(client.flushes, 1);
  assert.equal(client.errors.length, 1);
  assert.equal(client.quitRequests, 0);
});
