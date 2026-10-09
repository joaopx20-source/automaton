// Grava o site do KAVIX como se fosse um celular e um computador, gerando
// promo/kavix/gameplay/celular.webm e promo/kavix/gameplay/pc.webm, que o
// gerar_videos.py usa automaticamente.
//
// Uso:
//   NODE_PATH="$(npm root -g)" node promo/kavix/gravar_gameplay.cjs [segundos]
//
// Variáveis opcionais:
//   KAVIX_URL      endereço a gravar (padrão: https://kavixbrasil.com.br/)
//   KAVIX_HEADED=1 abre o navegador na tela para você mesmo jogar enquanto grava
//
// Requer o pacote "playwright" (npm i -g playwright) e o Chromium dele.
const fs = require('fs');
const os = require('os');
const path = require('path');
const { chromium, devices } = require('playwright');

const URL = process.env.KAVIX_URL || 'https://kavixbrasil.com.br/';
const HEADED = process.env.KAVIX_HEADED === '1';
const SECS = Number(process.argv[2] || 25);
const OUT = path.join(__dirname, 'gameplay');

const PLAY_TEXT = /jogar|play|come[cç]ar|iniciar|start|entrar/i;

async function tryEnterGame(page) {
  for (const role of ['button', 'link']) {
    const el = page.getByRole(role, { name: PLAY_TEXT }).first();
    if (await el.isVisible().catch(() => false)) {
      await el.click({ timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(2500);
      return true;
    }
  }
  return false;
}

// Interação genérica: toques/cliques no meio da tela, setas e rolagem,
// para a gravação não ficar parada. Com KAVIX_HEADED=1 é melhor jogar você.
async function wander(page, viewport, secs, touch) {
  const end = Date.now() + secs * 1000;
  let i = 0;
  while (Date.now() < end) {
    const x = viewport.width * (0.3 + Math.random() * 0.4);
    const y = viewport.height * (0.35 + Math.random() * 0.4);
    if (!HEADED) {
      if (i % 3 === 0) {
        if (touch) await page.touchscreen.tap(x, y).catch(() => {});
        else await page.mouse.click(x, y).catch(() => {});
      } else if (i % 3 === 1) {
        const k = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'Space'][i % 4];
        await page.keyboard.press(k).catch(() => {});
      } else {
        await page.mouse.wheel(0, i % 2 ? 300 : -300).catch(() => {});
      }
    }
    await page.waitForTimeout(800);
    i++;
  }
}

async function record(name, contextOpts, touch) {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kavix-rec-'));
  const browser = await chromium.launch({
    headless: !HEADED,
    args: ['--autoplay-policy=no-user-gesture-required'],
  });
  const vp = contextOpts.viewport;
  const scale = contextOpts.deviceScaleFactor || 1;
  const context = await browser.newContext({
    ...contextOpts,
    recordVideo: {
      dir: tmp,
      size: { width: Math.round(vp.width * Math.min(scale, 2)),
              height: Math.round(vp.height * Math.min(scale, 2)) },
    },
  });
  const page = await context.newPage();
  console.log(`[${name}] abrindo ${URL}`);
  await page.goto(URL, { waitUntil: 'networkidle', timeout: 60000 })
    .catch((e) => console.log(`[${name}] aviso: ${e.message.split('\n')[0]}`));
  await page.waitForTimeout(2000);
  if (await tryEnterGame(page)) console.log(`[${name}] cliquei em "jogar"`);
  await wander(page, vp, SECS, touch);
  const video = page.video();
  await context.close();
  fs.mkdirSync(OUT, { recursive: true });
  const dest = path.join(OUT, `${name}.webm`);
  await video.saveAs(dest);
  await browser.close();
  fs.rmSync(tmp, { recursive: true, force: true });
  console.log(`[${name}] salvo em ${dest}`);
}

(async () => {
  const { defaultBrowserType, ...phone } = devices['iPhone 13'];
  await record('celular', phone, true);
  await record('pc', { viewport: { width: 1920, height: 1080 } }, false);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
