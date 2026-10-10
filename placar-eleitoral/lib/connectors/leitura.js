// Leitura contínua de comentários, página por página, guardando até onde já leu.
// Assim posts grandes entram aos poucos (um pedaço por sincronização) e os
// comentários novos continuam chegando, sem recomeçar do zero a cada vez.
//
// buscarPagina(cursor) deve devolver { itens: [{ id, texto, autor, quando }], proximo, depois }
//   - quando:  data do comentário em milissegundos
//   - proximo: cursor da página seguinte (ou null se acabou)
//   - depois:  (só listas crescentes) cursor que aponta para o fim desta página

/**
 * Lista do mais novo para o mais antigo (YouTube, Instagram).
 * 1) Lê do topo até alcançar o comentário mais novo já visto (novidades).
 * 2) Continua descendo pelos antigos a partir do cursor salvo, até chegar ao fim.
 */
export async function lerDecrescente(estado = {}, buscarPagina, { maxNovas = 50, maxAntigas = 20 } = {}) {
  const e = { ...estado };
  const comentarios = [];
  let maior = e.topo || 0;
  const anotar = (itens) => {
    comentarios.push(...itens);
    for (const c of itens) if (c.quando > maior) maior = c.quando;
  };

  if (e.topo) {
    let cursor = null;
    for (let i = 0; i < maxNovas; i++) {
      const { itens, proximo } = await buscarPagina(cursor);
      anotar(itens);
      if (!proximo || itens.some((c) => c.quando <= e.topo)) break;
      cursor = proximo;
    }
  }

  if (!e.completo) {
    let cursor = e.cursorAntigo || null;
    for (let i = 0; i < maxAntigas; i++) {
      let pagina;
      try {
        pagina = await buscarPagina(cursor);
      } catch (err) {
        // Cursor vencido ou inválido: recomeça a descida pelo topo (duplicados são ignorados na contagem).
        if (cursor && /^HTTP 400/.test(err.message)) { cursor = null; continue; }
        throw err;
      }
      anotar(pagina.itens);
      if (!pagina.proximo) { e.completo = true; cursor = null; break; }
      cursor = pagina.proximo;
    }
    e.cursorAntigo = cursor;
  }

  e.topo = maior || e.topo || null;
  return { comentarios, estado: e };
}

/**
 * Lista do mais antigo para o mais novo (Facebook em ordem cronológica).
 * Continua sempre do último ponto lido; os comentários novos aparecem no fim da lista.
 */
export async function lerCrescente(estado = {}, buscarPagina, { maxPaginas = 50 } = {}) {
  const e = { ...estado };
  const comentarios = [];
  let cursor = e.cursor || null;
  for (let i = 0; i < maxPaginas; i++) {
    let pagina;
    try {
      pagina = await buscarPagina(cursor);
    } catch (err) {
      if (cursor && /^HTTP 400/.test(err.message)) { cursor = null; continue; }
      throw err;
    }
    comentarios.push(...pagina.itens);
    if (pagina.depois) cursor = pagina.depois;
    if (!pagina.proximo) break;
  }
  e.cursor = cursor;
  return { comentarios, estado: e };
}

/** Converte datas das APIs ("2024-05-01T12:00:00+0000", ISO etc.) em milissegundos. */
export function dataEmMs(valor) {
  if (!valor) return 0;
  if (typeof valor === "number") return valor < 1e12 ? valor * 1000 : valor;
  const t = Date.parse(String(valor).replace(/([+-]\d\d)(\d\d)$/, "$1:$2"));
  return Number.isNaN(t) ? 0 : t;
}
