#!/usr/bin/env node
/** Dependency-free Chromium smoke checks over a private CDP pipe.
 * Usage: node tests/check_browser_cdp.mjs [--browser path/to/chrome] [--screenshots directory]
 * Checks a local, self-contained document. Clipboard APIs are mocked.
 */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as pause } from 'node:timers/promises';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const locales = JSON.parse(await fs.readFile(path.join(ROOT, 'src/locales.json'), 'utf8'));
const languages = locales.map(locale => locale.code);
const options = {};
for (let i = 2; i < process.argv.length; i += 2) {
  assert.ok(['--browser', '--screenshots'].includes(process.argv[i]), 'Unknown command-line option');
  assert.ok(process.argv[i + 1], 'Missing command-line option value');
  options[process.argv[i].slice(2)] = process.argv[i + 1];
}
const artifacts = path.resolve(options.screenshots || path.join(ROOT, 'tests/artifacts/cdp'));
await fs.mkdir(artifacts, { recursive: true });
const translations = Object.fromEntries(await Promise.all(languages.filter(language => language !== 'ja').map(async language => [language,
  JSON.parse(await fs.readFile(path.join(ROOT, `src/translations/${language}.json`), 'utf8'))])));
const prompts = Object.fromEntries(await Promise.all(languages.map(async language => [language,
  (await fs.readFile(path.join(ROOT, `prompts/led_solder_review_${language}.txt`), 'utf8')).replace(/\r\n?/g, '\n').trim()])));
const html = await fs.readFile(path.join(ROOT, 'index.html'), 'utf8');
const tr = (key, language) => language === 'ja' ? key : translations[language][key];
const contextData = text => JSON.parse('{' + text.split('\n{').at(-1));
const brightness = color => color.match(/[\d.]+/g).slice(0, 3).map(Number).reduce((sum, n, i) => sum + n * [.2126, .7152, .0722][i], 0);

async function findBrowser() {
  if (options.browser) return path.resolve(options.browser);
  const cache = path.join(process.env.LOCALAPPDATA || '', 'ms-playwright');
  const dirs = (await fs.readdir(cache).catch(() => [])).filter(name => /^chromium-\d+$/.test(name))
    .sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1]));
  const candidates = dirs.map(dir => path.join(cache, dir, 'chrome-win64/chrome.exe'));
  candidates.push(path.join(process.env.PROGRAMFILES || '', 'Google/Chrome/Application/chrome.exe'));
  for (const candidate of candidates) if (await fs.stat(candidate).then(s => s.isFile()).catch(() => false)) return candidate;
  throw new Error('Chromium was not found. Pass --browser with an installed Chromium executable.');
}

class CdpBrowser {
  constructor(executable, profile) {
    this.events = [];
    this.pending = new Map();
    this.sequence = 0;
    this.buffer = '';
    this.process = spawn(executable, ['--headless=new', '--remote-debugging-pipe', '--no-sandbox', '--disable-gpu',
      '--no-first-run', '--no-default-browser-check', `--user-data-dir=${profile}`],
    { cwd: ROOT, stdio: ['ignore', 'ignore', 'pipe', 'pipe', 'pipe'], windowsHide: true });
    this.process.stderr.on('data', () => {});
    this.process.on('error', error => { for (const request of this.pending.values()) request.reject(error); });
    this.process.stdio[4].setEncoding('utf8');
    this.process.stdio[4].on('data', bytes => {
      this.buffer += bytes.toString();
      let end;
      while ((end = this.buffer.indexOf('\0')) >= 0) {
        const text = this.buffer.slice(0, end);
        this.buffer = this.buffer.slice(end + 1);
        if (!text) continue;
        const message = JSON.parse(text);
        const request = this.pending.get(message.id);
        if (!request) { this.events.push(message); continue; }
        this.pending.delete(message.id);
        clearTimeout(request.timer);
        if (message.error) request.reject(new Error(JSON.stringify(message.error)));
        else request.resolve(message.result);
      }
    });
  }
  send(method, params = {}, sessionId) {
    return new Promise((resolve, reject) => {
      const id = ++this.sequence;
      const timer = setTimeout(() => { this.pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 10000);
      this.pending.set(id, { resolve, reject, timer });
      this.process.stdio[3].write(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }) + '\0');
    });
  }
  async evaluate(expression, session) {
    const result = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true }, session);
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    return result.result.value;
  }
  async createPage(nojs = false) {
    const { targetId } = await this.send('Target.createTarget', { url: 'about:blank' });
    const { sessionId } = await this.send('Target.attachToTarget', { targetId, flatten: true });
    await this.send('Page.enable', {}, sessionId);
    await this.send('Runtime.enable', {}, sessionId);
    await this.send('Network.enable', {}, sessionId);
    if (nojs) await this.send('Emulation.setScriptExecutionDisabled', { value: true }, sessionId);
    return sessionId;
  }
  async load(session) {
    const frame = (await this.send('Page.getFrameTree', {}, session)).frameTree.frame.id;
    await this.send('Page.setDocumentContent', { frameId: frame, html }, session);
  }
  async close() {
    await this.send('Browser.close').catch(() => {});
    if (this.process.exitCode === null) this.process.kill();
  }
}

const profile = await fs.mkdtemp(path.join(artifacts, 'profile-'));
const browser = new CdpBrowser(await findBrowser(), profile);
const checks = [];
try {
  const version = await browser.send('Browser.getVersion');
  const page = await browser.createPage();
  const evaluate = expression => browser.evaluate(expression, page);
  const select = (id, value) => evaluate(`(()=>{const e=document.getElementById(${JSON.stringify(id)});e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));})()`);
  const viewport = (width, height = 900, session = page) => browser.send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false }, session);
  const media = (scheme, type = 'screen', session = page) => browser.send('Emulation.setEmulatedMedia', { media: type, features: [{ name: 'prefers-color-scheme', value: scheme }] }, session);
  const output = () => evaluate("document.getElementById('prompt-output').value");
  const bodyColor = () => evaluate('getComputedStyle(document.body).backgroundColor');
  const screenshot = async name => {
    const { data } = await browser.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }, page);
    await fs.writeFile(path.join(artifacts, name), Buffer.from(data, 'base64'));
  };
  await viewport(1440, 1000);
  await media('light');
  await browser.load(page);
  assert.deepEqual(await evaluate("[document.getElementById('language-select').value,document.getElementById('theme-select').value]"), ['ja', 'auto']);
  assert.deepEqual(await evaluate("Array.from(document.getElementById('language-select').options, option => ({code:option.value,name:option.textContent}))"), locales);
  assert.equal(await evaluate("document.querySelector('.brand').textContent"), 'フルカラーLEDテープ はんだ付けサポート');
  const initial = await output();
  assert.ok(initial.length > 7000 && initial.includes('未記入。実際の作業状況は未確認') && initial.includes('このWebページでは確認していません'));
  assert.equal(await evaluate("document.getElementById('prompt-preview').open"), false);
  const original = await evaluate("({description:document.querySelector('meta[name=description]').content,placeholder:document.getElementById('product').placeholder})");
  await screenshot('desktop-ja-light.png');
  checks.push('Text site title, Japanese/auto defaults, full prompt and unverified initial state');
  for (const language of languages) {
    await select('language-select', language);
    const state = await evaluate("({lang:document.documentElement.lang,title:document.title,description:document.querySelector('meta[name=description]').content,placeholder:document.getElementById('product').placeholder,label:document.querySelector('label[for=led-type]').textContent,scope:document.querySelector('.scope-note').textContent})");
    assert.equal(state.lang, language);
    assert.equal(await evaluate("document.querySelector('.brand').textContent"), tr('フルカラーLEDテープ はんだ付けサポート', language));
    assert.equal(await evaluate("document.getElementById('prompt-language').textContent"), locales.find(locale => locale.code === language).name);
    assert.equal(state.title, tr('LEDテープ はんだ付けサポート | EdelWorks', language));
    assert.equal(state.description, tr(original.description, language));
    assert.equal(state.placeholder, tr(original.placeholder, language));
    assert.equal(state.label, tr('使うもの', language));
    assert.ok((await output()).startsWith(prompts[language]));
    for (const voltage of [5, 12, 24]) assert.ok(new RegExp(`(?<!\\d)${voltage}\\s*V(?![A-Za-z0-9])`).test(state.scope));
    for (const theme of ['auto', 'light', 'dark']) {
      await select('theme-select', theme);
      assert.equal(await evaluate('document.documentElement.dataset.theme'), theme);
      for (const width of [320, 375, 390, 650, 768, 1024, 1440]) {
        await viewport(width);
        assert.equal(await evaluate('document.documentElement.scrollWidth>innerWidth'), false, `${language}/${theme}/${width}`);
      }
    }
    await evaluate("window.scrollTo({top:0,behavior:'instant'})");
    await screenshot(`desktop-${language}-dark.png`);
    await viewport(390, 844);
    await screenshot(`mobile-${language}-dark.png`);
  }
  checks.push(`All ${languages.length} localized titles, metadata, labels, placeholders, voltage scopes and prompts; ${languages.length * 3 * 7} locale/theme/viewport combinations without overflow`);
  await select('theme-select', 'auto');
  await media('light');
  const light = await bodyColor();
  await media('dark');
  const dark = await bodyColor();
  assert.ok(brightness(light) > 180 && brightness(dark) < 90);
  await select('theme-select', 'light');
  assert.equal(await bodyColor(), light);
  await media('light');
  await select('theme-select', 'dark');
  assert.equal(await bodyColor(), dark);
  await media('dark', 'print');
  assert.ok(brightness(await bodyColor()) > 180);
  await media('light');
  await select('language-select', 'en');
  await viewport(1440, 1000);
  await evaluate("window.scrollTo({top:0,behavior:'instant'})");
  await screenshot('desktop-en-dark.png');
  await select('language-select', 'zh');
  await viewport(390, 844);
  await screenshot('mobile-zh-dark.png');
  await select('language-select', 'ja');
  await select('theme-select', 'light');
  await screenshot('mobile-ja-light.png');
  await evaluate("document.getElementById('optional-fields').open=true;document.querySelector('.prompt-panel').scrollIntoView({block:'start',behavior:'instant'})");
  await screenshot('mobile-ja-optional.png');
  checks.push('OS automatic theme, manual overrides, print light background, desktop/mobile screenshots for every locale');
  for (const type of ['strip', 'ring', 'both', 'unknown']) {
    await select('led-type', type);
    for (const stage of ['unspecified', 'uncovered', 'repaired', 'covered', 'before']) {
      await select('work-stage', stage);
      assert.ok(contextData(await output())['対象']);
      assert.equal(await evaluate("!document.getElementById('stage-notice').hidden"), ['covered', 'before'].includes(stage));
    }
  }
  const malicious = '</textarea><script>window.__xss=true</script>\n中央の端子が気になります。';
  await evaluate(`document.getElementById('product').value='WS2812B、5V（製品表示）';document.getElementById('concern').value=${JSON.stringify(malicious)};document.getElementById('concern').dispatchEvent(new Event('input',{bubbles:true}));`);
  const downloadDir = path.join(artifacts, 'downloads');
  await fs.mkdir(downloadDir, { recursive: true });
  await browser.send('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: downloadDir, eventsEnabled: true });
  for (const language of languages) {
    await select('language-select', language);
    assert.deepEqual(await evaluate("[document.getElementById('product').value,document.getElementById('concern').value,document.getElementById('led-type').value,document.getElementById('work-stage').value]"), ['WS2812B、5V（製品表示）', malicious, 'unknown', 'before']);
    assert.equal(await evaluate('window.__xss===undefined'), true);
    const data = contextData(await output());
    assert.equal(data[tr('気になる点・使用予定（利用者の自由記入）', language)], malicious);
    assert.equal(data[tr('電源切断・測定・動作確認の実施状況', language)], tr('このWebページでは確認していません', language));
    for (const [stage, key] of [
      ['covered', '隠れた接合部は判断できません。覆う前の写真があれば使い、撮影のためだけに無理に剥がさないでください。'],
      ['before', '写真レビューは、はんだ付けして接合部が冷めてから。電源を外し、覆う前の状態で撮影してください。'],
    ]) { await select('work-stage', stage); assert.equal(await evaluate("document.getElementById('stage-notice').textContent"), tr(key, language)); }
    const text = await output();
    const filename = `led-solder-review-${language}.txt`;
    const saved = path.join(downloadDir, filename);
    await fs.rm(saved, { force: true });
    const eventIndex = browser.events.length;
    await evaluate("document.getElementById('download-btn').click()");
    let bytes;
    for (let attempt = 0; attempt < 40; attempt++) {
      bytes = await fs.readFile(saved).catch(() => null);
      if (bytes) break;
      await pause(100);
    }
    assert.ok(bytes, `Missing ${language} download`);
    assert.ok(bytes.subarray(0, 3).equals(Buffer.from([0xef, 0xbb, 0xbf])));
    assert.equal(bytes.toString('utf8').slice(1), text);
    assert.equal(browser.events.slice(eventIndex).find(e => e.method === 'Browser.downloadWillBegin')?.params.suggestedFilename, filename);
  }
  checks.push(`20 LED type/stage combinations, input/selection retention, translated context and notices, safe HTML-like input, ${languages.length} exact real downloads with UTF-8 BOM`);
  await evaluate("Object.defineProperty(window,'isSecureContext',{value:true,configurable:true});Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{window.__copiedText=text}}});");
  for (const language of languages) {
    await select('language-select', language);
    await evaluate("(async()=>{document.getElementById('copy-btn').click();await new Promise(r=>setTimeout(r,10))})()");
    assert.equal(await evaluate('window.__copiedText'), await output());
    assert.equal(await evaluate("document.getElementById('status').textContent"), tr('コピーしました。画像対応AIのチャットに貼り付けて送信し、続けて写真を送ってください。', language));
    assert.equal(await evaluate("document.getElementById('copy-label').textContent"), tr('コピーしました', language));
  }
  await select('language-select', 'ja');
  for (const change of ['language', 'input']) {
    await evaluate("navigator.clipboard.writeText=text=>new Promise(resolve=>{window.__completeCopy=()=>{window.__copiedText=text;resolve()}})");
    const oldText = await output();
    await evaluate("document.getElementById('copy-btn').click()");
    const language = change === 'language' ? 'en' : 'ja';
    if (change === 'language') await select('language-select', language);
    else await evaluate(`document.getElementById('concern').value=${JSON.stringify(malicious + '\n追記')};document.getElementById('concern').dispatchEvent(new Event('input',{bubbles:true}));`);
    assert.notEqual(await output(), oldText);
    await evaluate('(async()=>{window.__completeCopy();await new Promise(r=>setTimeout(r,10))})()');
    assert.equal(await evaluate('window.__copiedText'), oldText);
    assert.equal(await evaluate("document.getElementById('status').dataset.type"), 'warning');
    assert.equal(await evaluate("document.getElementById('status').textContent"), tr('変更前の内容がコピーされました。現在の内容をもう一度コピーしてください。', language));
    await select('language-select', 'ja');
    await evaluate(`document.getElementById('concern').value=${JSON.stringify(malicious)};document.getElementById('concern').dispatchEvent(new Event('input',{bubbles:true}));`);
  }
  await evaluate("navigator.clipboard.writeText=async()=>{throw new Error('Permission denied')};document.execCommand=()=>{window.__legacyText=document.activeElement.value;return true};document.getElementById('copy-btn').click()");
  await pause(20);
  assert.equal(await evaluate('window.__legacyText'), await output());
  await evaluate("document.execCommand=()=>false;document.getElementById('copy-btn').click()");
  await pause(20);
  assert.equal(await evaluate("document.getElementById('status').dataset.type"), 'warning');
  assert.ok(await evaluate("document.getElementById('status').textContent.includes('自動コピーが使えませんでした')"));
  assert.equal(await evaluate("document.getElementById('prompt-preview').open&&document.getElementById('prompt-output').selectionStart===0&&document.getElementById('prompt-output').selectionEnd===document.getElementById('prompt-output').value.length"), true);
  await evaluate("location.hash='source-6'");
  await pause(30);
  assert.equal(await evaluate("document.getElementById('sources').open"), true);
  checks.push('Mocked clipboard success/localized labels, delayed language/input change warning, compatibility fallback, manual-copy selection, source disclosure navigation');
  const nojs = await browser.createPage(true);
  await viewport(390, 844, nojs);
  await media('dark', 'screen', nojs);
  await browser.load(nojs);
  assert.ok(await browser.evaluate("document.getElementById('prompt-output').value.includes('最優先：はんだ付けの確認が先')", nojs));
  assert.ok(await browser.evaluate("document.querySelector('noscript').getBoundingClientRect().height>0", nojs));
  assert.equal(await browser.evaluate('getComputedStyle(document.body).backgroundColor', nojs), dark);
  assert.equal(await browser.evaluate('document.documentElement.scrollWidth>innerWidth', nojs), false);
  assert.equal(await browser.evaluate("document.querySelector('.brand').textContent", nojs), 'フルカラーLEDテープ はんだ付けサポート');
  assert.deepEqual(browser.events.filter(e => e.method === 'Runtime.exceptionThrown'), []);
  assert.deepEqual(browser.events.filter(e => e.method === 'Network.requestWillBeSent' && /^https?:/.test(e.params.request.url)), []);
  checks.push('No-JS Japanese prompt, text site title, dark OS theme and no overflow; no uncaught JavaScript errors or HTTP(S) requests');
  const report = { status: 'PASS', browser: version.product, load_mode: 'direct document over CDP pipe', checks,
    limitations: ['Python Playwright test not executed by this script', 'Clipboard APIs mocked; OS clipboard not tested', 'Physical mobile devices not tested', 'AI photo-assessment quality not tested', 'Hosted deployment not tested'] };
  await fs.writeFile(path.join(artifacts, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
