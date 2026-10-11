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
//   (padrão: todos os jogos da página, 25 segundos cada)
//
// Variáveis opcionais:
//   KAVIX_AUTO_URL  página do bot (padrão: https://kavix-arcade.web.app/auto.html)
//   KAVIX_ONLY=pc   grava só um aparelho (celular ou pc)
//   KAVIX_KEY=n     tecla que pula para o próximo jogo
//   KAVIX_VISUAL    kit (padrão: kit sorteado a cada jogo), roupa ou meu
//   KAVIX_FAIXA=1   mantém a faixa de cima com o nome do jogo
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn, spawnSync } = require('child_process');
const { chromium, devices } = require('playwright');

const URL = process.env.KAVIX_AUTO_URL || 'https://kavix-arcade.web.app/auto.html';
const MODES_ARG = Number(process.argv[2] || 0);  // 0 = todos os jogos da página
const PER_MODE = Number(process.argv[3] || 25);
const KEY = process.env.KAVIX_KEY || 'n';
const OUT = path.join(__dirname, 'gameplay');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const has = (bin) => spawnSync('which', [bin]).status === 0;
const HD = process.platform === 'linux' && has('Xvfb') && has('ffmpeg');

// Abre a vitrine: clica em "Começar" e esconde a faixa de cima (tecla H),
// para a imagem sair limpa. Devolve quantos jogos a página tem ("1 de N").
async function startShowcase(page) {
  // como a bolinha se veste: "kit" = kit sorteado a cada jogo (padrão),
  // "roupa" = uma roupa nova a cada jogo, "meu" = visual do Inventário
  const visual = process.env.KAVIX_VISUAL || 'kit';
  const modo = page.locator(`#modosVitrine .modo[data-modo="${visual}"]`);
  if (await modo.count()) {
    await modo.click();
    console.log(`  visual: ${visual}`);
  }
  const vai = page.locator('#vai');
  if (await vai.count()) await vai.click();
  else await page.mouse.click(10, 10).catch(() => {});
  await sleep(1200);
  if (process.env.KAVIX_FAIXA !== '1') await page.keyboard.press('h');
  const total = await page.evaluate(() => {
    const m = /de\s+(\d+)/.exec((document.querySelector('#conta') || {}).textContent || '');
    return m ? Number(m[1]) : 0;
  }).catch(() => 0);
  return total;
}

// Nome do jogo que está na tela: #nome da vitrine; senão, o maior texto
// curto no topo da página.
async function gameName(page) {
  return page.evaluate(() => {
    const el = document.querySelector('#nome');
    if (el && el.textContent.trim()) return el.textContent.trim();
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

async function playModes(page, name, now, total) {
  const MODES = MODES_ARG || total || 24;
  console.log(`[${name}] ${total || '?'} jogos na página; gravando ${MODES}, ${PER_MODE}s cada`);
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
  const total = await startShowcase(page);

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

  const segments = await playModes(page, name, now, total);
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
  const total = await startShowcase(page);
  const segments = await playModes(page, name, now, total);
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
    // tela em pé 9:16 em resolução cheia (o formato dos Reels), com toque e
    // user agent de iPhone
    const { defaultBrowserType, ...iphone } = devices['iPhone 13'];
    await record('celular', { ...iphone, viewport: { width: 1080, height: 1920 },
                              screen: { width: 1080, height: 1920 }, deviceScaleFactor: 1 }, ':91');
  }
  if (!only || only === 'pc') {
    await record('pc', { viewport: { width: 1920, height: 1080 } }, ':92');
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
