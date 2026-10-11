// Exporta as skins do inventário do KAVIX ARCADE (página auto.html) como
// PNG em alta resolução, usando o próprio desenho do site (Arcade.itemPreview).
// Gera promo/kavix/gameplay/skins/<id>.png e skins.json (nome, tipo, raridade).
//
// Uso: NODE_PATH="$(npm root -g)" node promo/kavix/exportar_skins.cjs
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const URL = process.env.KAVIX_AUTO_URL || 'https://kavix-arcade.web.app/auto.html';
const OUT = path.join(__dirname, 'gameplay', 'skins');
const SIZE = 480;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto(URL, { waitUntil: 'load', timeout: 90000 });
  await page.click('.aba[data-painel="inv"]');
  await page.waitForTimeout(2500);
  const items = await page.evaluate((size) => {
    const out = [];
    Skins.SLOTS.forEach((sl) => {
      Skins.doSlot(sl.id).forEach((it) => {
        const cv = document.createElement('canvas');
        cv.width = cv.height = size;
        cv.style.width = cv.style.height = size + 'px';
        document.body.appendChild(cv);
        try { Arcade.itemPreview(cv, it.id); } catch (e) { cv.remove(); return; }
        const r = Skins.RAR[it.rar] || {};
        out.push({ id: it.id, nome: it.name, tipo: sl.id, tipo_nome: sl.label,
                   raridade: it.rar, raridade_nome: r.nome || '', cor: r.cor || '',
                   png: cv.toDataURL('image/png') });
        cv.remove();
      });
    });
    return out;
  }, SIZE);
  fs.mkdirSync(OUT, { recursive: true });
  const meta = items.map(({ png, ...it }) => {
    fs.writeFileSync(path.join(OUT, `${it.id}.png`), Buffer.from(png.split(',')[1], 'base64'));
    return { ...it, arquivo: `skins/${it.id}.png` };
  });
  fs.writeFileSync(path.join(OUT, '..', 'skins.json'), JSON.stringify(meta, null, 2));
  console.log(`${meta.length} skins salvas em ${OUT}`);
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
