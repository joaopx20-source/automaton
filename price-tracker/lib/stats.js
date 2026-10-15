// Análise do histórico: mínimo/máximo, quedas e veredito "é uma boa hora para comprar?".

const DAY = 86_400_000;

/** @param {{t:string,price:number}[]} history ordenado por data */
export function analyze(history, now = Date.now()) {
  const pts = history.filter((h) => typeof h.price === "number");
  if (!pts.length) return null;
  const prices = pts.map((p) => p.price);
  const current = prices.at(-1);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const minPoint = pts.findLast((p) => p.price === min);

  // Média ponderada pelo tempo em que cada preço vigorou.
  let weighted = 0, total = 0;
  for (let i = 0; i < pts.length; i++) {
    const start = Date.parse(pts[i].t);
    const end = i + 1 < pts.length ? Date.parse(pts[i + 1].t) : now;
    const dur = Math.max(end - start, 1);
    weighted += pts[i].price * dur;
    total += dur;
  }
  const avg = weighted / total;

  const drops = [];
  for (let i = 1; i < pts.length; i++) {
    if (pts[i].price < pts[i - 1].price) {
      drops.push({ at: pts[i].t, from: pts[i - 1].price, to: pts[i].price, percent: pct(pts[i - 1].price, pts[i].price) });
    }
  }

  const priceAt = (ts) => pts.findLast((p) => Date.parse(p.t) <= ts)?.price ?? pts[0].price;
  const change30d = pct(priceAt(now - 30 * DAY), current);

  return {
    current, min, max, avg: Math.round(avg * 100) / 100,
    minAt: minPoint.t,
    aboveMinPercent: Math.round(((current - min) / min) * 1000) / 10,
    vsAvgPercent: Math.round(((current - avg) / avg) * 1000) / 10,
    change30d,
    drops: drops.reverse(),
    verdict: verdict({ current, min, max, avg, samples: pts.length }),
  };
}

const pct = (from, to) => Math.round(((from - to) / from) * 1000) / 10;

function verdict({ current, min, max, avg, samples }) {
  if (samples < 3 || max === min) return { level: "neutral", label: "Coletando histórico" };
  if (current <= min) return { level: "good", label: "Menor preço já registrado" };
  if (current <= min * 1.03) return { level: "good", label: "Perto do menor preço" };
  if (current < avg * 0.97) return { level: "ok", label: "Abaixo da média" };
  if (current > avg * 1.05) return { level: "bad", label: "Acima da média — espere" };
  return { level: "neutral", label: "Na média" };
}
