import { test } from "node:test";
import assert from "node:assert/strict";
import { aplicarComentarios, distribuirEmPedacos, montarResumo, linhasParaComentarios, chaveSegura } from "../lib/contagem.js";

const base = () => ({ vistos: new Set(), autores: new Set(), votos: { lula: 0, flavio: 0, ignorados: 0 }, rede: "instagram", postagemId: "p1" });

test("conta cada comentário uma vez, inclusive repetido no mesmo lote", () => {
  const e = base();
  const r = aplicarComentarios(e, [{ id: "a", texto: "13" }, { id: "a", texto: "13" }, { id: "b", texto: "Fora PT" }, { id: "c", texto: "oi" }]);
  assert.equal(r.novos, 2);
  assert.deepEqual(r.votos, { lula: 1, flavio: 1, ignorados: 1 });
  assert.deepEqual(r.novasChaves, [["a", "lula"], ["b", "flavio"], ["c", 0]]);
  for (const [k] of r.novasChaves) e.vistos.add(k);
  const r2 = aplicarComentarios({ ...e, votos: r.votos }, [{ id: "a", texto: "13" }, { id: "d", texto: "22" }]);
  assert.deepEqual(r2.votos, { lula: 1, flavio: 2, ignorados: 1 });
  assert.equal(r2.feedNovo.length, 1);
});

test("um voto por pessoa", () => {
  const r = aplicarComentarios(base(), [{ id: "1", texto: "13", autor: "ana" }, { id: "2", texto: "22", autor: "ana" }], { umVotoPorPessoa: true });
  assert.deepEqual(r.votos, { lula: 1, flavio: 0, ignorados: 1 });
  assert.deepEqual(r.novosAutores, ["ana"]);
});

test("pedaços: completa o último e cria novos", () => {
  const novas = Array.from({ length: 7 }, (_, i) => [`k${i}`, 0]);
  const g = distribuirEmPedacos([{ id: "0000", tamanho: 3 }], novas, 5);
  assert.deepEqual(g.map((x) => [x.id, x.entradas.length]), [["0000", 2], ["0001", 5]]);
  assert.deepEqual(distribuirEmPedacos([], [["a", 0]], 5).map((x) => x.id), ["0000"]);
  assert.deepEqual(distribuirEmPedacos([{ id: "0000", tamanho: 5 }], [], 5), []);
});

test("resumo soma e fecha 100%", () => {
  const r = montarResumo([
    { rede: "instagram", votos: { lula: 2, flavio: 1, ignorados: 4 } },
    { rede: "facebook", votos: { lula: 0, flavio: 3, ignorados: 0 } },
  ], []);
  assert.deepEqual([r.totais.lula, r.totais.flavio, r.totais.total], [2, 4, 6]);
  assert.equal(r.totais.pctLula + r.totais.pctFlavio, 100);
  assert.equal(r.porRede.facebook.flavio, 3);
});

test("importação manual gera IDs estáveis", async () => {
  const a = await linhasParaComentarios("13\n13\n22");
  const b = await linhasParaComentarios("13\n13\n22\n22");
  assert.deepEqual(a.map((c) => c.id), b.slice(0, 3).map((c) => c.id));
  assert.equal(new Set(b.map((c) => c.id)).size, 4);
});

test("chaves seguras para o Firestore", () => {
  assert.equal(chaveSegura("a.b/c"), "a_b_c");
  assert.equal(chaveSegura(""), "_vazio");
});
