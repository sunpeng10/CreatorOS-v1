/** Edge and Chrome acceptance using isolated contexts and labeled TEST records. */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { randomUUID } = require('node:crypto');

let playwright;
try { playwright = require('playwright'); }
catch {
  playwright = require(path.join(process.env.USERPROFILE, '.cache', 'codex-runtimes', 'codex-primary-runtime', 'dependencies', 'node', 'node_modules', 'playwright'));
}

const root = path.resolve(__dirname, '..');
const screenshotDir = path.join(root, 'docs', 'screenshots');
const testAssets = path.join(root, 'data', 'test-fixtures');
const results = [];

async function body(response, expected = 200) {
  assert.equal(response.status(), expected, `${response.url()} returned ${response.status()}: ${await response.text()}`);
  return response.json();
}

async function post(context, route, data, expected = 200) {
  return body(await context.request.post(`/api${route}`, { data }), expected);
}

async function get(context, route) {
  return body(await context.request.get(`/api${route}`));
}

async function visit(page, route, text) {
  const response = await page.goto(route, { waitUntil: 'domcontentloaded' });
  assert.equal(response.status(), 200, route);
  await page.getByText(text, { exact: false }).first().waitFor({ timeout: 20000 });
}

async function screenshot(page, browser, name) {
  await page.screenshot({ path: path.join(screenshotDir, `${browser}-${name}.png`), animations: 'disabled', fullPage: false });
}

async function waitAnalysis(context, id, timeoutMs = 20000) {
  const until = Date.now() + timeoutMs;
  while (Date.now() < until) {
    const result = await get(context, `/analyses/${id}`);
    if (['SUCCEEDED', 'FAILED', 'CANCELED', 'WAITING_APPROVAL'].includes(result.status)) return result;
    await new Promise(resolve => setTimeout(resolve, 350));
  }
  throw new Error(`Analysis ${id} exceeded acceptance timeout`);
}

async function runBrowser(browserLabel, executablePath, baseURL, owner) {
  const browser = await playwright.chromium.launch({ executablePath, headless: true });
  try {
    const suffix = randomUUID().slice(0, 8);
    const email = `test-${browserLabel}-${suffix}@example.test`;
    const password = `Test-${randomUUID()}!`;
    const client = await browser.newContext({ baseURL, viewport: { width: 1440, height: 1050 } });
    const admin = await browser.newContext({ baseURL, viewport: { width: 1440, height: 1050 } });
    const customerPage = await client.newPage();
    const adminPage = await admin.newPage();
    const errors = [];
    for (const page of [customerPage, adminPage]) {
      page.on('pageerror', error => errors.push(error.message));
      page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    }

    assert.equal((await get(client, '/health')).database, 'connected');
    await visit(customerPage, '/', 'CreatorOS');
    await screenshot(customerPage, browserLabel, '01-home');
    await visit(customerPage, '/register', '建立你的创作工作区');
    await customerPage.locator('[name=name]').fill(`TEST ${browserLabel} 创作者`);
    await customerPage.locator('[name=email]').fill(email);
    await customerPage.locator('[name=password]').fill(password);
    await customerPage.getByRole('checkbox').check();
    await customerPage.getByRole('button', { name: '创建工作区' }).click();
    await customerPage.waitForURL('**/dashboard');
    assert.equal((await get(client, '/auth/me')).role, 'CLIENT_USER');
    assert.equal((await client.request.get('/api/admin/overview')).status(), 403);

    const account = await post(client, '/accounts', { name: 'TEST 编程实验账号', platform: '测试平台', niche: '编程教育' });
    await visit(customerPage, '/analyze', '每一份作品');
    await customerPage.locator('input[type=file]').setInputFiles([path.join(testAssets, 'TEST-creatoros.mp4'), path.join(root, 'fixtures', 'TEST_字幕.srt')]);
    await customerPage.locator('[name=title]').fill(`TEST Python 函数视频 ${suffix}`);
    await customerPage.locator('[name=category]').fill('编程教育');
    await customerPage.locator('[name=text]').fill('TEST 本地验收。开场提出重复代码的问题，再用 Python 函数演示输入与输出。');
    await customerPage.getByRole('button', { name: '开始本地分析' }).click();
    await customerPage.waitForURL('**/analyses/*', { timeout: 35000 });
    const id = customerPage.url().split('/').pop();
    const analysis = await waitAnalysis(client, id);
    assert.equal(analysis.status, 'SUCCEEDED', JSON.stringify(analysis.task?.error));
    assert.equal(analysis.report.source, 'local');
    assert.equal(analysis.steps.length, 7);
    const content = await get(client, `/contents/${analysis.content_id}`);
    assert.ok(content.metadata.duration >= 3.9);
    assert.ok(content.keyframes.length >= 2);
    assert.ok(content.scenes.length >= 1);
    assert.equal((await client.request.get(`/api/assets/${content.keyframes[0].asset_id}`)).status(), 200);
    await customerPage.getByText('发现与证据', { exact: true }).waitFor();
    await customerPage.getByRole('button', { name: '保存为新版本' }).click();
    await customerPage.getByText('新版本已保存。').waitFor();
    assert.equal((await client.request.get(`/api/analyses/${id}/export?format=markdown`)).status(), 200);
    await screenshot(customerPage, browserLabel, '02-report');

    await visit(customerPage, '/library', '添加 Demo 样本');
    await customerPage.getByRole('button', { name: '添加 Demo 样本' }).click();
    let library;
    for (let i = 0; i < 20; i++) {
      library = await get(client, '/library');
      if (library.total >= 3) break;
      await new Promise(resolve => setTimeout(resolve, 250));
    }
    assert.ok(library.total >= 3);
    assert.ok(library.items.every(item => item.is_demo));
    await visit(customerPage, '/recommendations', '查找相关作品');
    await customerPage.locator('[name=query]').fill('Python 编程函数教学');
    await customerPage.locator('[name=include_demo]').check();
    const searchPromise = customerPage.waitForResponse(response => response.url().endsWith('/api/recommendations/search') && response.request().method() === 'POST');
    await customerPage.getByRole('button', { name: '查找相关作品' }).click();
    assert.ok((await body(await searchPromise)).items.length >= 3);

    await visit(customerPage, '/analytics', '预览与验证');
    await customerPage.locator('input[type=file]').setInputFiles(path.join(root, 'fixtures', 'TEST_指标.csv'));
    await customerPage.getByRole('button', { name: '预览与验证' }).click();
    const importPromise = customerPage.waitForResponse(response => response.url().endsWith('/api/metrics/import') && response.request().method() === 'POST');
    await customerPage.getByRole('button', { name: '确认导入' }).click();
    assert.equal((await body(await importPromise)).imported, 3);
    await customerPage.getByText('播放表现趋势', { exact: true }).waitFor();
    await customerPage.locator('.recharts-surface').first().waitFor();
    await customerPage.getByText('内容表现', { exact: true }).scrollIntoViewIfNeeded();
    await screenshot(customerPage, browserLabel, '03-analytics');
    const experiment = await post(client, '/experiments', { title: 'TEST 更快展示函数输出', content_id: content.id, analysis_id: id, hypothesis: '更早展示输出，检验观众互动是否变化', plan: '仅修改开头 3 秒', metric: 'views', window_days: 7 });
    assert.ok(experiment.id);
    const lead = await post(client, '/leads', { contact: email, need: 'TEST 验收编程内容诊断与改进报告', campaign: `TEST-${browserLabel}` });

    await visit(adminPage, '/login', '欢迎回到实验室');
    await adminPage.locator('[name=email]').fill(owner.email);
    await adminPage.locator('[name=password]').fill(owner.password);
    await adminPage.getByRole('button', { name: '登录工作区' }).click();
    await adminPage.waitForURL('**/dashboard');
    assert.equal((await get(admin, '/auth/me')).role, 'OWNER_ADMIN');
    assert.equal((await admin.request.get(`/api/contents/${content.id}`)).status(), 404);
    const services = await get(admin, '/admin/services');
    const quote = await post(admin, '/admin/quotes', { lead_id: lead.id, service_id: services.items[0].id, amount: 99, notes: 'TEST / DEMO' });
    await post(admin, '/admin/orders', { quote_id: quote.id }, 409);
    await visit(adminPage, '/admin/approvals', '审批记录');
    await adminPage.locator('.record').filter({ hasText: quote.id }).getByRole('button', { name: '批准', exact: true }).click();
    await adminPage.locator('[name=reason]').fill('TEST 人工审批与留痕验收');
    const approvalPromise = adminPage.waitForResponse(response => response.url().endsWith(`/api/approvals/${quote.approval_id}/decision`));
    await adminPage.getByRole('button', { name: '确认批准' }).click();
    assert.equal((await body(await approvalPromise)).status, 'APPROVED');
    const order = await post(admin, '/admin/orders', { quote_id: quote.id, is_demo: true });
    await adminPage.goto('/admin/orders', { waitUntil: 'domcontentloaded' });
    const payPromise = adminPage.waitForResponse(response => response.url().endsWith(`/api/admin/orders/${order.id}/simulate-payment`));
    await adminPage.locator('.order-record').filter({ hasText: order.id.slice(0, 8) }).getByRole('button', { name: 'DEMO 模拟支付' }).click();
    assert.equal((await body(await payPromise)).payment.status, 'DEMO_PAID');
    const currentOrder = adminPage.locator('.order-record').filter({ hasText: order.id.slice(0, 8) });
    await currentOrder.getByRole('button', { name: '交付分析报告' }).click();
    await adminPage.locator('[name=customer_analysis_id]').fill(id);
    const deliveryPromise = adminPage.waitForResponse(response => response.url().endsWith(`/api/admin/orders/${order.id}/deliver`));
    await adminPage.getByRole('button', { name: '确认交付' }).click();
    const delivery = await body(await deliveryPromise);
    assert.equal(delivery.status, 'DELIVERED');
    assert.ok((await get(client, '/orders')).items.some(item => item.id === order.id));
    await visit(customerPage, '/orders', '我的订单');
    const acceptPromise = customerPage.waitForResponse(response => response.url().endsWith(`/api/orders/${order.id}/accept`));
    await customerPage.locator('.order-record').filter({ hasText: order.id.slice(0, 8) }).getByRole('button', { name: '确认验收' }).click();
    const accepted = await body(await acceptPromise);
    assert.equal(accepted.status, 'COMPLETED');
    await post(client, '/tickets', { order_id: order.id, subject: 'TEST 创作建议反馈', message: '仅用于本地流程验收', kind: 'QUESTION' });
    await adminPage.reload();
    await adminPage.getByText('DEMO', { exact: false }).first().waitFor();
    await screenshot(adminPage, browserLabel, '04-orders');
    const weekly = await get(admin, '/admin/weekly-report');
    assert.ok(weekly.markdown.includes('CreatorOS 经营周报'));
    assert.ok(weekly.summary.demo_revenue >= 99);
    assert.equal(weekly.summary.real_revenue, 0);
    await visit(adminPage, '/admin/finance', '经营');
    await screenshot(adminPage, browserLabel, '05-finance');

    for (const [page, routes] of [
      [customerPage, ['/accounts', '/experiments', '/settings', '/tickets']],
      [adminPage, ['/admin', '/admin/leads', '/admin/services', '/admin/tickets', '/admin/agents', '/admin/data']],
    ]) {
      for (const route of routes) {
        const response = await page.goto(route, { waitUntil: 'domcontentloaded' });
        assert.equal(response.status(), 200, route);
        await page.getByRole('heading', { level: 1 }).first().waitFor();
        if (route === '/admin') await screenshot(page, browserLabel, '08-admin');
      }
    }

    await customerPage.setViewportSize({ width: 390, height: 844 });
    await visit(customerPage, '/dashboard', '工作台');
    assert.ok(await customerPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'mobile page overflows');
    await screenshot(customerPage, browserLabel, '06-mobile');

    let mimo = null;
    if (browserLabel === 'chrome' && process.env.CREATOROS_E2E_MIMO === '1') {
      const state = await get(client, '/system/ai-status');
      if (state.connectivity === 'connected') {
        await customerPage.setViewportSize({ width: 1440, height: 1050 });
        await visit(customerPage, '/analyze', '每一份作品');
        await customerPage.locator('input[type=file]').setInputFiles(path.join(testAssets, 'TEST-creatoros.mp4'));
        await customerPage.locator('[name=title]').fill(`TEST MiMo 视频理解 ${suffix}`);
        await customerPage.locator('[name=text]').fill('TEST 本机生成的双色片段，分析两次场景的视觉变化；没有播放或互动数据。');
        await customerPage.getByText('MiMo 深度分析', { exact: true }).click();
        await customerPage.locator('[name=budget]').fill('0.25');
        await customerPage.getByRole('checkbox').check();
        await customerPage.getByRole('button', { name: '开始 AI 分析' }).click();
        await customerPage.waitForURL('**/analyses/*', { timeout: 35000 });
        const ai = await waitAnalysis(client, customerPage.url().split('/').pop(), 540000);
        mimo = { id: ai.id, status: ai.status, source: ai.report?.source, cost: ai.task?.cost, error: ai.task?.error, events: ai.task?.cost_events?.map(event => ({ model: event.model, input_tokens: event.input_tokens, output_tokens: event.output_tokens, estimated_cost: event.estimated_cost })) };
        if (ai.status === 'SUCCEEDED') {
          assert.equal(ai.report.source, 'mimo');
          await customerPage.getByText('发现与证据', { exact: true }).waitFor();
          await screenshot(customerPage, browserLabel, '07-mimo');
        }
      } else mimo = { status: state.connectivity };
    }

    assert.deepEqual(errors.filter(error => !/favicon/i.test(error)), [], 'browser console errors');
    const saved = { browser: browserLabel, browser_version: browser.version(), account_id: account.id, analysis_id: id, content_id: content.id, keyframes: content.keyframes.length, scenes: content.scenes.length, experiment_id: experiment.id, lead_id: lead.id, quote_id: quote.id, order_id: order.id, order_status: accepted.status, demo_revenue: weekly.summary.demo_revenue, real_revenue: weekly.summary.real_revenue, mimo };
    results.push(saved);
    await fs.writeFile(path.join(root, 'data', `browser-${browserLabel}-credentials.txt`), `仅用于本地 TEST 工作区。\n邮箱: ${email}\n密码: ${password}\n`, 'utf8');
    console.log(JSON.stringify(saved));
  } finally { await browser.close(); }
}

async function retryMiMo(executablePath, baseURL) {
  const input = JSON.parse(await fs.readFile(path.join(root, 'data', 'browser-chrome-retry.json'), 'utf8'));
  const browser = await playwright.chromium.launch({ executablePath, headless: true });
  try {
    const client = await browser.newContext({ baseURL, viewport: { width: 1440, height: 1050 } });
    const page = await client.newPage();
    await visit(page, '/login', '欢迎回到实验室');
    await page.locator('[name=email]').fill(input.email);
    await page.locator('[name=password]').fill(input.password);
    await page.getByRole('button', { name: '登录工作区' }).click();
    await page.waitForURL('**/dashboard');
    const before = await get(client, `/analyses/${input.id}`);
    assert.equal(before.status, 'FAILED');
    assert.equal(before.steps.find(step => step.name === 'content').status, 'SUCCEEDED');
    await visit(page, `/analyses/${input.id}`, '从失败步骤重试');
    const response = page.waitForResponse(r => r.url().endsWith(`/api/tasks/${before.task_id}/retry`));
    await page.getByRole('button', { name: '从失败步骤重试' }).click();
    await body(await response);
    const ai = await waitAnalysis(client, input.id, 320000);
    const result = { id: ai.id, browser_version: browser.version(), status: ai.status, source: ai.report?.source, cost: ai.task?.cost, error: ai.task?.error,
      steps: ai.steps.map(({name, status, attempts, model, tokens}) => ({name, status, attempts, model, tokens})),
      events: ai.task?.cost_events?.map(({model, input_tokens, output_tokens, estimated_cost, status, step}) => ({model, input_tokens, output_tokens, estimated_cost, status, step})) };
    await fs.writeFile(path.join(root, 'data', 'browser-chrome-mimo.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
    assert.equal(ai.steps.find(step => step.name === 'content').attempts, before.steps.find(step => step.name === 'content').attempts);
    assert.equal(ai.status, 'SUCCEEDED');
    assert.equal(ai.report.source, 'mimo');
    await page.getByText('发现与证据', { exact: true }).waitFor();
    await screenshot(page, 'chrome', '07-mimo');
  } finally { await browser.close(); }
}

async function main() {
  const state = JSON.parse((await fs.readFile(path.join(root, 'data', 'processes.json'), 'utf8')).replace(/^\uFEFF/, ''));
  const raw = await fs.readFile(path.join(root, 'data', 'admin-credentials.txt'), 'utf8');
  const owner = { email: raw.match(/^邮箱: (.+)$/m)[1].trim(), password: raw.match(/^密码: (.+)$/m)[1].trim() };
  await fs.mkdir(screenshotDir, { recursive: true });
  const browsers = [
    ['edge', process.env.CREATOROS_EDGE || path.join(process.env['ProgramFiles(x86)'], 'Microsoft', 'Edge', 'Application', 'msedge.exe')],
    ['chrome', process.env.CREATOROS_CHROME || path.join(process.env.LOCALAPPDATA, 'Google', 'Chrome', 'Application', 'chrome.exe')],
  ];
  if (process.env.CREATOROS_E2E_RETRY_MIMO === '1') {
    await retryMiMo(browsers[1][1], state.web_url);
    return;
  }
  for (const [label, executable] of browsers) {
    if (process.env.CREATOROS_BROWSER && process.env.CREATOROS_BROWSER !== label) continue;
    await runBrowser(label, executable, state.web_url, owner);
    await fs.writeFile(path.join(root, 'data', `browser-${label}.json`), JSON.stringify(results.at(-1), null, 2));
  }
}

main().catch(error => {
  console.error(error.message.replace(/([?&]password=)[^&\s]+/gi, '$1[REDACTED]'));
  process.exitCode = 1;
});
