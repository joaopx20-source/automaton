// Grava o modo automático do KAVIX Arcade (um bot joga sozinho) como celular
// e como PC, apertando "N" para pular de modo em modo.
//
// Gera em promo/kavix/gameplay/:
//   celular.webm + celular.json   e   pc.webm + pc.json
// O .json guarda em que segundo começa cada modo; o gerar_videos.py usa isso
// para editar a montagem ("kavix_modos_*.mp4").
//
// Uso:
//   NODE_PATH="$(npm root -g)" node promo/kavix/gravar_auto.cjs [modos] [segundos_por_modo]
//   (padrão: 8 modos, 20 segundos cada — grave bastante jogabilidade)
//
// Variáveis opcionais:
//   KAVIX_AUTO_URL  página do bot (padrão: https://kavix-arcade.web.app/auto.html)
//   KAVIX_HEADED=1  mostra o navegador enquanto grava
//   KAVIX_ONLY=pc   grava só um aparelho (celular ou pc)
const fs = require('fs');
const os = require('os');
const path = require('path');
const { chromium, devices } = require('playwright');

const URL = process.env.KAVIX_AUTO_URL || 'https://kavix-arcade.web.app/auto.html';
const MODES = Number(process.argv[2] || 8);
const PER_MODE = Number(process.argv[3] || 20);
const OUT = path.join(__dirname, 'gameplay');

async function record(name, contextOpts) {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kavix-auto-'));
  const browser = await chromium.launch({
    headless: process.env.KAVIX_HEADED !== '1',
    args: ['--autoplay-policy=no-user-gesture-required',
           '--enable-gpu-rasterization', '--ignore-gpu-blocklist'],
  });
  const vp = contextOpts.viewport;
  const context = await browser.newContext({
    ...contextOpts,
    recordVideo: { dir: tmp, size: { width: vp.width, height: vp.height } },
  });
  const page = await context.newPage();
  const t0 = Date.now(); // a gravação começa junto com a página
  const now = () => (Date.now() - t0) / 1000;

  console.log(`[${name}] abrindo ${URL}`);
  await page.goto(URL, { waitUntil: 'load', timeout: 90000 });
  await page.waitForTimeout(2500);
  // um clique para dar foco (teclas) e liberar áudio/animações
  await page.mouse.click(vp.width / 2, vp.height / 2).catch(() => {});
  await page.waitForTimeout(500);

  const segments = [];
  for (let i = 0; i < MODES; i++) {
    if (i > 0) {
      await page.keyboard.press('n');
      await page.waitForTimeout(150);
    }
    const start = now();
    const title = await page.title().catch(() => '');
    await page.waitForTimeout(PER_MODE * 1000);
    segments.push({ modo: i + 1, inicio: +start.toFixed(2),
                    fim: +now().toFixed(2), titulo: title });
    console.log(`[${name}] modo ${i + 1}: ${start.toFixed(1)}s → ${now().toFixed(1)}s`);
  }

  // O .webm do Playwright costuma sair um pouco mais longo que o tempo real;
  // guardamos a duração real para o gerar_videos.py corrigir os cortes.
  const realDuration = now();
  const video = page.video();
  await context.close();
  fs.mkdirSync(OUT, { recursive: true });
  await video.saveAs(path.join(OUT, `${name}.webm`));
  fs.writeFileSync(path.join(OUT, `${name}.json`),
                   JSON.stringify({ url: URL, duracao_real: +realDuration.toFixed(2),
                                   segmentos: segments }, null, 2));
  await browser.close();
  fs.rmSync(tmp, { recursive: true, force: true });
  console.log(`[${name}] salvo em ${OUT}/${name}.webm`);
}

(async () => {
  const only = process.env.KAVIX_ONLY;
  if (!only || only === 'celular') {
    // viewport maior e escala 1: o vídeo do Playwright grava em pixels CSS,
    // então a escala 3 do iPhone só deixaria bordas cinzas na gravação.
    const { defaultBrowserType, ...iphone } = devices['iPhone 13'];
    const phone = { ...iphone, viewport: { width: 540, height: 1170 },
                    screen: { width: 540, height: 1170 }, deviceScaleFactor: 1 };
    await record('celular', phone);
  }
  if (!only || only === 'pc') {
    await record('pc', { viewport: { width: 1920, height: 1080 } });
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
