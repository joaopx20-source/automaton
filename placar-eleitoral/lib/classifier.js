import { TERMOS, REJEICAO, EMOJIS } from "./keywords.js";

const LADOS = ["lula", "flavio"];
const ADVERSARIO = { lula: "flavio", flavio: "lula" };

/**
 * Normaliza um comentário para comparação:
 * - minúsculas, sem acentos
 * - emojis de número (1️⃣3️⃣) viram dígitos
 * - # e @ removidos (#Lula13 -> lula 13)
 * - letras repetidas 3+ vezes colapsadas (lulaaaa -> lula, mitoooo -> mito)
 * - separa letras de números (lula13 -> lula 13, b22 continua casando como termo)
 */
export function normalizar(texto) {
  return String(texto ?? "")
    .replace(/️/g, "")
    .replace(/([0-9])⃣/g, "$1")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[#@]/g, " ")
    .replace(/([a-z])\1{2,}/g, "$1")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

// Versão com letras e números separados para casar "lula13" e "flavio22".
function separarNumeros(texto) {
  return texto.replace(/([a-z])([0-9])/g, "$1 $2").replace(/([0-9])([a-z])/g, "$1 $2");
}

function escapar(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function compilar(lista) {
  const termos = [...new Set(lista.map(normalizar).filter(Boolean))]
    .sort((a, b) => b.length - a.length)
    .map(escapar);
  // Fronteira: não pode haver letra/número colado antes ou depois (13 não casa em 2013).
  return new RegExp(`(?<![a-z0-9])(?:${termos.join("|")})(?![a-z0-9])`, "g");
}

const REGEX_TERMOS = Object.fromEntries(LADOS.map((l) => [l, compilar(TERMOS[l])]));
const REGEX_REJEICAO = Object.fromEntries(LADOS.map((l) => [l, compilar(REJEICAO[l])]));

function contarEmojis(textoOriginal, lado) {
  const t = String(textoOriginal ?? "").replace(/️/g, "");
  let n = 0;
  for (const e of EMOJIS[lado]) {
    const alvo = e.replace(/️/g, "");
    if (alvo) n += t.split(alvo).length - 1;
  }
  return n;
}

/**
 * Classifica um comentário.
 * Retorna { voto: "lula" | "flavio" | null, motivo, pontos: {lula, flavio}, termos: [...] }
 *
 * Regras:
 *  1. Expressões de rejeição ("fora Lula") contam para o adversário e são retiradas do texto.
 *  2. Cada termo associado (13, PT, mito, 22, PL...) soma 1 ponto ao lado dele.
 *  3. Emojis associados somam 1 ponto.
 *  4. Quem tiver mais pontos leva o voto. Empate (inclusive 0 x 0) = comentário ignorado.
 *  Um comentário vale no máximo 1 voto.
 */
export function classificar(texto) {
  const pontos = { lula: 0, flavio: 0 };
  const termos = [];
  let t = separarNumeros(normalizar(texto));

  for (const lado of LADOS) {
    const achados = t.match(REGEX_REJEICAO[lado]) || [];
    pontos[ADVERSARIO[lado]] += achados.length;
    termos.push(...achados.map((a) => `contra ${lado}: "${a}"`));
    t = t.replace(REGEX_REJEICAO[lado], " ");
  }

  for (const lado of LADOS) {
    const achados = t.match(REGEX_TERMOS[lado]) || [];
    pontos[lado] += achados.length;
    termos.push(...achados.map((a) => `${lado}: "${a}"`));
    const emojis = contarEmojis(texto, lado);
    if (emojis) {
      pontos[lado] += emojis;
      termos.push(`${lado}: ${emojis} emoji(s)`);
    }
  }

  let voto = null;
  let motivo;
  if (pontos.lula === 0 && pontos.flavio === 0) motivo = "sem termos associados";
  else if (pontos.lula === pontos.flavio) motivo = "empate (ambíguo)";
  else {
    voto = pontos.lula > pontos.flavio ? "lula" : "flavio";
    motivo = "ok";
  }
  return { voto, motivo, pontos, termos };
}
