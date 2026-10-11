// Grava o modo automático do KAVIX Arcade (um bot joga sozinho) como celular
// e como PC, apertando "N" para pular de jogo em jogo.
//
// No Linux com Xvfb + ffmpeg (como no ambiente do Claude), o navegador roda
// numa tela virtual e o ffmpeg grava essa tela em H.264 de alta qualidade.
// Sem Xvfb, usa a gravação embutida do Playwright (.webm, qualidade menor).
//
// Gera em promo/kavix/gameplay/:
//   celular.mp4 + celular.json   e   pc.mp4 + pc.json
// O .json guarda em que segundo começa cada jogo e o nome dele (lido da
// página). O gerar_videos.py usa isso para montar os vídeos.
//
// Uso:
//   NODE_PATH="$(npm root -g)" node promo/kavix/gravar_auto.cjs [jogos] [segundos_por_jogo]
//   (padrão: 24 jogos, 25 segundos cada — grave bastante jogabilidade)
//
// Variáveis opcionais:
//   KAVIX_AUTO_URL  página do bot (padrão: https://kavix-arcade.web.app/auto.html)
//   KAVIX_ONLY=pc   grava só um aparelho (celular ou pc)
//   KAVIX_KEY=n     tecla que pula para o próximo jogo
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn, spawnSync } = require('child_process');
const { chromium, devices } = require('playwright');

const URL = process.env.KAVIX_AUTO_URL || 'https://kavix-arcade.web.app/auto.html';
const MODES = Number(process.argv[2] || 24);
const PER_MODE = Number(process.argv[3] || 25);
const KEY = process.env.KAVIX_KEY || 'n';
const OUT = path.join(__dirname, 'gameplay');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const has = (bin) => spawnSync('which', [bin]).status === 0;
const HD = process.platform === 'linux' && has('Xvfb') && has('ffmpeg');

// Tenta descobrir o nome do jogo que está na tela: título da aba, depois o
// maior texto curto no topo da página.
async function gameName(page) {
  return page.evaluate(() => {
    const vh = window.innerHeight;
    let best = null;
    for (const el of document.querySelectorAll('h1,h2,h3,header *,[class*=title],[class*=nome],[class*=name]')) {
      const txt = (el.innerText || '').trim();
      const r = el.getBoundingClientRect();
      if (!txt || txt.length > 24 || txt.includes('\n') || r.top > vh * 0.25 || r.height === 0) continue;
      const fs = parseFloat(getComputedStyle(el).fontSize) || 0;
      if (!best || fs > best.fs) best = { txt, fs };
    }
    return best ? best.txt : document.title;
  }).catch(() => '');
}

async function playModes(page, name, now) {
  const segments = [];
  for (let i = 0; i < MODES; i++) {
    if (i > 0) {
      await page.keyboard.press(KEY);
      await sleep(400);
    }
    const start = now();
    await sleep(1500);
    const nome = await gameName(page);
    await sleep(Math.max(0, PER_MODE * 1000 - 1500));
    segments.push({ modo: i + 1, nome, inicio: +start.toFixed(2), fim: +now().toFixed(2) });
    console.log(`[${name}] ${i + 1}/${MODES} "${nome}": ${start.toFixed(1)}s → ${now().toFixed(1)}s`);
  }
  return segments;
}

async function recordHD(name, ctxOpts, display) {
  const vp = ctxOpts.viewport;
  const xvfb = spawn('Xvfb', [display, '-screen', '0', `${vp.width}x${vp.height}x24`, '-nolisten', 'tcp'],
                     { stdio: 'ignore' });
  await sleep(800);
  const browser = await chromium.launch({
    headless: false,
    env: { ...process.env, DISPLAY: display },
    args: [`--window-size=${vp.width},${vp.height}`, '--window-position=0,0',
           '--autoplay-policy=no-user-gesture-required', '--ignore-gpu-blocklist',
           '--disable-infobars', '--hide-scrollbars'],
  });
  const context = await browser.newContext(ctxOpts);
  const page = await context.newPage();
  // tela cheia (como o F11): some com abas e barra de endereço
  const cdp = await context.newCDPSession(page);
  const { windowId } = await cdp.send('Browser.getWindowForTarget');
  await cdp.send('Browser.setWindowBounds', { windowId, bounds: { windowState: 'fullscreen' } });
  console.log(`[${name}] abrindo ${URL}`);
  await page.goto(URL, { waitUntil: 'load', timeout: 90000 });
  await sleep(2500);
  await page.mouse.click(vp.width / 2, vp.height / 2).catch(() => {});

  fs.mkdirSync(OUT, { recursive: true });
  const file = path.join(OUT, `${name}.mp4`);
  const ff = spawn('ffmpeg', ['-loglevel', 'error', '-y', '-f', 'x11grab', '-framerate', '30',
                              '-video_size', `${vp.width}x${vp.height}`, '-draw_mouse', '0',
                              '-i', `${display}.0`, '-c:v', 'libx264', '-preset', 'veryfast',
                              '-crf', '16', '-pix_fmt', 'yuv420p', file],
                   { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  const now = () => (Date.now() - t0) / 1000;
  await sleep(500);

  const segments = await playModes(page, name, now);
  const realDuration = now();
  ff.stdin.write('q');
  await new Promise((r) => ff.on('close', r));
  await browser.close();
  xvfb.kill();
  return { file, realDuration, segments };
}

async function recordPlaywright(name, ctxOpts) {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kavix-auto-'));
  const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  const vp = ctxOpts.viewport;
  const context = await browser.newContext({
    ...ctxOpts, recordVideo: { dir: tmp, size: { width: vp.width, height: vp.height } },
  });
  const page = await context.newPage();
  const t0 = Date.now();
  const now = () => (Date.now() - t0) / 1000;
  console.log(`[${name}] abrindo ${URL}`);
  await page.goto(URL, { waitUntil: 'load', timeout: 90000 });
  await sleep(2500);
  await page.mouse.click(vp.width / 2, vp.height / 2).catch(() => {});
  const segments = await playModes(page, name, now);
  // o .webm do Playwright sai um pouco mais longo que o tempo real; guardamos
  // a duração real para o gerar_videos.py corrigir os cortes
  const realDuration = now();
  const video = page.video();
  await context.close();
  fs.mkdirSync(OUT, { recursive: true });
  const file = path.join(OUT, `${name}.webm`);
  await video.saveAs(file);
  await browser.close();
  fs.rmSync(tmp, { recursive: true, force: true });
  return { file, realDuration, segments };
}

async function record(name, ctxOpts, display) {
  const r = HD ? await recordHD(name, ctxOpts, display) : await recordPlaywright(name, ctxOpts);
  fs.writeFileSync(path.join(OUT, `${name}.json`),
                   JSON.stringify({ url: URL, hd: HD, duracao_real: +r.realDuration.toFixed(2),
                                    segmentos: r.segments }, null, 2));
  console.log(`[${name}] salvo em ${r.file}`);
}

(async () => {
  console.log(HD ? 'modo HD: Xvfb + ffmpeg' : 'modo simples: gravação do Playwright');
  const only = process.env.KAVIX_ONLY;
  if (!only || only === 'celular') {
    // tela de celular em pé (9:19,5), com toque e user agent de iPhone
    const { defaultBrowserType, ...iphone } = devices['iPhone 13'];
    await record('celular', { ...iphone, viewport: { width: 540, height: 1170 },
                              screen: { width: 540, height: 1170 }, deviceScaleFactor: 1 }, ':91');
  }
  if (!only || only === 'pc') {
    await record('pc', { viewport: { width: 1920, height: 1080 } }, ':92');
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
