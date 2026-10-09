import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Store } from "../lib/store.js";

const novoStore = (op) => new Store(join(mkdtempSync(join(tmpdir(), "placar-")), "db.json"), op);

test("cada comentário conta uma vez e porcentagens fecham 100%", () => {
  const s = novoStore();
  const p = s.adicionarPostagem({ url: "https://x.com/a/status/1", rede: "x", idPostagem: "1" });
  s.registrarComentarios(p, [{ id: "a", texto: "13" }, { id: "b", texto: "22" }, { id: "c", texto: "Faz o L" }, { id: "d", texto: "oi" }]);
  s.registrarComentarios(p, [{ id: "a", texto: "13" }, { id: "e", texto: "mito" }]);
  const r = s.resumo();
  assert.deepEqual([r.totais.lula, r.totais.flavio, r.totais.ignorados, r.totais.total], [2, 2, 1, 4]);
  assert.equal(r.totais.pctLula + r.totais.pctFlavio, 100);
  assert.equal(r.porRede.x.lula, 2);
});

test("importação manual não duplica ao colar a mesma lista", () => {
  const s = novoStore();
  const p = s.adicionarPostagem({ url: "https://tiktok.com/@a/video/1", rede: "tiktok", idPostagem: "1" });
  assert.equal(s.importarTexto(p, "13\n13\n22\n").novos, 3);
  assert.equal(s.importarTexto(p, "13\n13\n22\n22\n").novos, 1);
  assert.deepEqual(p.votos, { lula: 2, flavio: 2, ignorados: 0 });
});

test("um voto por pessoa (opcional)", () => {
  const s = novoStore({ umVotoPorPessoa: true });
  const p = s.adicionarPostagem({ url: "https://x.com/a/status/2", rede: "x", idPostagem: "2" });
  s.registrarComentarios(p, [{ id: "1", texto: "13", autor: "ana" }, { id: "2", texto: "13", autor: "ana" }, { id: "3", texto: "22", autor: "bia" }]);
  assert.deepEqual(p.votos, { lula: 1, flavio: 1, ignorados: 1 });
});

test("remover postagem tira os votos dela", () => {
  const s = novoStore();
  const p = s.adicionarPostagem({ url: "https://x.com/a/status/3", rede: "x", idPostagem: "3" });
  s.registrarComentarios(p, [{ id: "1", texto: "22" }]);
  s.removerPostagem(p.id);
  assert.equal(s.resumo().totais.total, 0);
});
