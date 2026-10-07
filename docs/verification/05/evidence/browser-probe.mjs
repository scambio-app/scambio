// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Fermich srl
// Capture only the local preview in a disposable browser profile.
import {spawn} from 'node:child_process';
import {mkdtemp, readFile, writeFile, rm, mkdir} from 'node:fs/promises';
import {watch} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

const profile = await mkdtemp(join(tmpdir(), 'scambio-site-browser-'));
const output = process.argv[2] || '/tmp/scambio-spec05-screenshots';
await mkdir(output, {recursive: true});
const browser = spawn('/usr/bin/google-chrome', ['--headless=new',
  '--user-data-dir=' + profile, '--remote-debugging-port=0',
  '--hide-scrollbars', 'about:blank'],
  {stdio: ['ignore', 'ignore', 'ignore']});
let socket;
try {
  const port = await new Promise((resolve, reject) => {
    const watcher = watch(profile, async (_, name) => {
      if (name !== 'DevToolsActivePort') return;
      try {
        const value = await readFile(join(profile, name), 'utf8');
        if (value.includes('\n')) { watcher.close(); resolve(value.split('\n')[0]); }
      } catch {}
    });
    browser.once('exit', () => { watcher.close(); reject(new Error('Browser exited')); });
  });
  const page = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`,
    {method: 'PUT'}).then(r => r.json());
  socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise(resolve => socket.addEventListener('open', resolve, {once: true}));
  let id = 0;
  const pending = new Map(), requests = [], errors = [];
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.id) {
      const {resolve, reject} = pending.get(message.id);
      pending.delete(message.id);
      message.error ? reject(message.error) : resolve(message.result);
    }
    if (message.method === 'Network.requestWillBeSent') requests.push(message.params.request.url);
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params);
    if (message.method === 'Log.entryAdded' && message.params.entry.level === 'error') errors.push(message.params);
  });
  function command(method, params = {}) {
    return new Promise((resolve, reject) => {
      pending.set(++id, {resolve, reject}); socket.send(JSON.stringify({id, method, params}));
    });
  }
  async function evaluate(expression) {
    const result = await command('Runtime.evaluate', {expression, awaitPromise: true, returnByValue: true});
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  }
  await command('Page.enable'); await command('Runtime.enable');
  await command('Network.enable'); await command('Log.enable');
  await command('Emulation.setDeviceMetricsOverride', {width:1440,height:1100,deviceScaleFactor:1,mobile:false});
  await command('Page.navigate', {url:'http://127.0.0.1:8787/'});
  await evaluate(`new Promise(resolve => {
    function ready() { if (document.querySelector('#download h2')?.textContent) {
      document.fonts.ready.then(resolve); return true; } return false; }
    if (!ready()) { const observer = new MutationObserver(() => {
      if (ready()) observer.disconnect(); }); observer.observe(document,{childList:true,subtree:true}); }
  })`);
  const captures = [];
  for (const lang of ['en','it','de']) {
    const info = await evaluate(`(() => {
      document.querySelector('[data-lang="${lang}"]').click();
      document.getElementById('download').scrollIntoView();
      return {lang:document.documentElement.lang,download:document.getElementById('download').innerText};
    })()`);
    const shot = await command('Page.captureScreenshot', {format:'png'});
    await writeFile(join(output, `download-${lang}.png`), Buffer.from(shot.data,'base64'));
    captures.push(info);
  }
  await evaluate(`document.querySelector('[data-lang="en"]').click(); window.scrollTo(0,0)`);
  const shot = await command('Page.captureScreenshot', {format:'png'});
  await writeFile(join(output,'home-after.png'),Buffer.from(shot.data,'base64'));
  const copy = JSON.parse(await readFile('~/development/scambio-site/public/copy.json','utf8'));
  const payload = '<img src=x onerror="window.scambioXss=true">';
  for (const value of Object.values(copy)) { value.form.consent_text = payload; value.headline = payload; }
  const source = await readFile('~/development/scambio-site/public/app.js','utf8');
  const modified = source.replace(/var COPY = await fetch[^\n]+/, 'var COPY = ' + JSON.stringify(copy) + ';');
  await evaluate(modified);
  const safe = await evaluate(`({text:document.querySelector('#consent-label').textContent,
    injected:!!document.querySelector('#consent-label img'),executed:!!window.scambioXss})`);
  if (!safe.text.includes(payload) || safe.injected || safe.executed) throw new Error('Copy injection');
  console.log('PASS malicious copy rendered as literal text');
  const external = requests.filter(url => !url.startsWith('http://127.0.0.1:8787/') && !url.startsWith('data:'));
  const report = {captures,requests:[...new Set(requests)],external,errors};
  await writeFile(join(output,'browser.json'),JSON.stringify(report,null,2)+'\n');
  if (external.length || errors.length) throw new Error('Unexpected external request or browser error');
  console.log(JSON.stringify({captures:captures.length,external:external.length,errors:errors.length}));
} finally {
  if (socket) socket.close();
  browser.kill('SIGTERM');
  await new Promise(resolve => browser.once('exit',resolve));
  await rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:100});
}
