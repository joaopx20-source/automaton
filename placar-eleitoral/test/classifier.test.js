import { test } from "node:test";
import assert from "node:assert/strict";
import { classificar, normalizar } from "../lib/classifier.js";

const casos = [
  ["13", "lula"], ["22", "flavio"], ["Lula", "lula"], ["lulinha", "lula"], ["PT", "lula"],
  ["Faz o L!!", "lula"], ["#Lula13", "lula"], ["1️⃣3️⃣", "lula"], ["LULAAAA", "lula"],
  ["mito", "flavio"], ["PL", "flavio"], ["Flávio Bolsonaro", "flavio"], ["#Flavio22", "flavio"],
  ["Bolsonaro 2026", "flavio"], ["2️⃣2️⃣", "flavio"],
  ["Fora Lula", "flavio"], ["fora PT", "flavio"], ["Fora Bolsonaro", "lula"], ["Ele não", "lula"],
  ["22 > 13, vote 22", "flavio"],
  ["olá, bom dia", null], ["2013 foi um ano bom", null], ["mitologia grega", null],
  ["13 ou 22?", null], ["telefone 11 98722-1313", null],
];

for (const [texto, esperado] of casos) {
  test(`"${texto}" => ${esperado}`, () => {
    assert.equal(classificar(texto).voto, esperado);
  });
}

test("normalizar remove acentos, # e repetições", () => {
  assert.equal(normalizar("#FLÁVIOOOO é o Mito!!"), "flavio e o mito");
});
