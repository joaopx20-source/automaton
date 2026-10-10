import { test } from "node:test";
import assert from "node:assert/strict";
import { lerDecrescente, lerCrescente, dataEmMs } from "../lib/connectors/leitura.js";

// Simula uma API paginada; "lista" pode crescer entre as sincronizações.
function apiFalsa(lista, porPagina, ordem) {
  return async (cursor) => {
    const ordenada = [...lista].sort((a, b) => (ordem === "desc" ? b.quando - a.quando : a.quando - b.quando));
    // cursor = id do último item lido (estável mesmo com itens novos chegando)
    const ini = cursor ? ordenada.findIndex((c) => c.id === cursor) + 1 : 0;
    const itens = ordenada.slice(ini, ini + porPagina);
    const temMais = ini + porPagina < ordenada.length;
    const ultimo = itens.at(-1)?.id ?? cursor;
    return { itens, proximo: temMais ? ultimo : null, depois: ultimo };
  };
}
const gerar = (de, ate) => Array.from({ length: ate - de }, (_, i) => ({ id: `c${de + i}`, texto: "13", quando: (de + i) * 1000 }));

test("decrescente: cobre um post grande ao longo de várias sincronizações e pega os novos", async () => {
  const lista = gerar(0, 1000);
  const vistos = new Set();
  let estado = {};
  for (let s = 0; s < 6; s++) {
    if (s === 3) lista.push(...gerar(1000, 1150)); // 150 comentários novos no meio do caminho
    const r = await lerDecrescente(estado, apiFalsa(lista, 50, "desc"), { maxNovas: 50, maxAntigas: 5 });
    r.comentarios.forEach((c) => vistos.add(c.id));
    estado = r.estado;
  }
  assert.equal(vistos.size, 1150);
  assert.equal(estado.completo, true);
  // Depois de completo, só lê as novidades.
  lista.push(...gerar(1150, 1160));
  const r = await lerDecrescente(estado, apiFalsa(lista, 50, "desc"), { maxNovas: 50, maxAntigas: 5 });
  assert.ok(r.comentarios.some((c) => c.id === "c1159"));
  assert.ok(r.comentarios.length <= 50);
});

test("crescente: continua do ponto salvo e pega os novos no fim", async () => {
  const lista = gerar(0, 230);
  const vistos = new Set();
  let estado = {};
  for (let s = 0; s < 4; s++) {
    if (s === 2) lista.push(...gerar(230, 260));
    const r = await lerCrescente(estado, apiFalsa(lista, 20, "asc"), { maxPaginas: 5 });
    r.comentarios.forEach((c) => vistos.add(c.id));
    estado = r.estado;
  }
  assert.equal(vistos.size, 260);
  const r = await lerCrescente(estado, apiFalsa(lista, 20, "asc"), { maxPaginas: 5 });
  assert.equal(r.comentarios.length, 0); // nada novo: não relê tudo
});

test("cursor inválido (HTTP 400) recomeça em vez de travar", async () => {
  const api = apiFalsa(gerar(0, 30), 10, "desc");
  const comErro = async (cursor) => { if (cursor === "velho") throw new Error("HTTP 400: invalid page token"); return api(cursor); };
  const r = await lerDecrescente({ topo: 1, cursorAntigo: "velho" }, comErro, { maxNovas: 1, maxAntigas: 5 });
  assert.ok(r.comentarios.length > 0);
});

test("datas das APIs", () => {
  assert.equal(dataEmMs("2024-05-01T12:00:00+0000"), Date.UTC(2024, 4, 1, 12));
  assert.equal(dataEmMs("2024-05-01T12:00:00Z"), Date.UTC(2024, 4, 1, 12));
  assert.equal(dataEmMs(1714564800), 1714564800000);
  assert.equal(dataEmMs(null), 0);
});
