const { test } = require('node:test');
const assert = require('node:assert/strict');
const { validLocalURL, serviceReady } = require('./services.cjs');
test('only explicit HTTP loopback URLs are loaded in the desktop', () => {
  assert.equal(validLocalURL('http://127.0.0.1:3004'), true);
  for (const url of ['https://example.com', 'file:///C:/secret', 'http://127.0.0.1.evil:3000', 'http://u:p@127.0.0.1:3000']) assert.equal(validLocalURL(url), false);
});
test('ready requires CreatorOS identity and a connected database', async () => {
  assert.equal(await serviceReady('http://127.0.0.1:3000', async () => ({ok:true,json:async()=>({service:'Other',database:'connected'})})), false);
  assert.equal(await serviceReady('http://127.0.0.1:3000', async () => ({ok:true,json:async()=>({service:'CreatorOS',database:'connected',status:'ok'})})), true);
  assert.equal(await serviceReady('http://127.0.0.1:3000', async () => { throw Error('offline'); }), false);
});
