// Conectores das redes sociais. Cada um recebe a postagem salva e devolve
// { comentarios: [{ id, texto, autor }], estado } onde `estado` é guardado e
// reenviado na próxima sincronização (cursor, since_id etc.).
//
// As credenciais vêm de variáveis de ambiente (veja o README / .env.example).
// Sem credencial, a postagem continua aceitando importação manual de comentários.

import { lerCrescente, lerDecrescente, dataEmMs } from "./leitura.js";

const MAX_PAGINAS = 50;
const GRAPH = `https://graph.facebook.com/${process.env.META_GRAPH_VERSION || "v21.0"}`;

async function getJson(url, opcoes = {}) {
  const resp = await fetch(url, opcoes);
  const corpo = await resp.text();
  let json;
  try {
    json = JSON.parse(corpo);
  } catch {
    throw new Error(`Resposta inválida (${resp.status}): ${corpo.slice(0, 200)}`);
  }
  if (!resp.ok || json.error) {
    const msg = json.error?.message || json.detail || json.title || json.errors?.[0]?.message || corpo.slice(0, 200);
    throw new Error(`HTTP ${resp.status}: ${msg}`);
  }
  return json;
}

function semCredencial(variaveis) {
  const err = new Error(`Credencial ausente: defina ${variaveis.join(", ")} ou use a importação manual.`);
  err.semCredencial = true;
  return err;
}

// ---------- Facebook (Graph API: comentários de posts da sua Página) ----------
// Ordem cronológica + cursor salvo: cada sincronização continua de onde parou,
// e os comentários novos aparecem no fim da lista.
async function facebook(post) {
  const token = process.env.FACEBOOK_PAGE_TOKEN;
  if (!token) throw semCredencial(["FACEBOOK_PAGE_TOKEN"]);
  let id = post.idApi || post.idPostagem;
  if (!id) throw new Error("Não foi possível extrair o ID do post. Informe o 'ID na API' manualmente (formato PAGINA_POST).");
  if (!id.includes("_") && process.env.FACEBOOK_PAGE_ID) id = `${process.env.FACEBOOK_PAGE_ID}_${id}`;

  const base = `${GRAPH}/${id}/comments?filter=stream&order=chronological&fields=id,message,created_time,from{id,name}&limit=100&access_token=${encodeURIComponent(token)}`;
  return lerCrescente(post.estado, async (cursor) => {
    const json = await getJson(cursor ? `${base}&after=${encodeURIComponent(cursor)}` : base);
    return {
      itens: (json.data || []).map((c) => ({ id: c.id, texto: c.message || "", autor: c.from?.id || c.from?.name || null, quando: dataEmMs(c.created_time) })),
      proximo: json.paging?.next ? json.paging.cursors?.after : null,
      depois: json.paging?.cursors?.after || null,
    };
  }, { maxPaginas: MAX_PAGINAS });
}
// ---------- Instagram (Graph API: mídia da sua conta profissional) ----------
async function instagram(post) {
  const token = process.env.INSTAGRAM_TOKEN || process.env.FACEBOOK_PAGE_TOKEN;
  const contaId = process.env.INSTAGRAM_BUSINESS_ID;
  if (!token || !contaId) throw semCredencial(["INSTAGRAM_TOKEN", "INSTAGRAM_BUSINESS_ID"]);
  const tk = encodeURIComponent(token);

  // O link traz o "shortcode"; a API precisa do ID da mídia. Procuramos na lista de mídias da conta.
  let mediaId = post.idApi || post.estado?.mediaId;
  if (!mediaId) {
    let url = `${GRAPH}/${contaId}/media?fields=id,shortcode,permalink&limit=100&access_token=${tk}`;
    for (let i = 0; url && i < 20 && !mediaId; i++) {
      const json = await getJson(url);
      mediaId = (json.data || []).find((m) => m.shortcode === post.idPostagem || m.permalink?.includes(`/${post.idPostagem}`))?.id;
      url = json.paging?.next;
    }
    if (!mediaId) throw new Error("Mídia não encontrada na conta configurada. A API do Instagram só lê comentários de posts da sua própria conta profissional.");
  }

  // A ordem da lista é detectada pelas datas e guardada no estado.
  let ordem = post.estado?.ordem;
  const base = `${GRAPH}/${mediaId}/comments?fields=id,text,username,timestamp,replies{id,text,username,timestamp}&limit=50&access_token=${tk}`;
  const buscarPagina = async (cursor) => {
    const json = await getJson(cursor ? `${base}&after=${encodeURIComponent(cursor)}` : base);
    const dados = json.data || [];
    if (!ordem && dados.length > 1) {
      const [a, b] = [dataEmMs(dados[0].timestamp), dataEmMs(dados.at(-1).timestamp)];
      if (a !== b) ordem = a > b ? "desc" : "asc";
    }
    const itens = [];
    for (const c of dados) {
      itens.push({ id: c.id, texto: c.text || "", autor: c.username || null, quando: dataEmMs(c.timestamp) });
      for (const r of c.replies?.data || []) itens.push({ id: r.id, texto: r.text || "", autor: r.username || null, quando: dataEmMs(r.timestamp) });
    }
    return { itens, proximo: json.paging?.next ? json.paging.cursors?.after : null, depois: json.paging?.cursors?.after || null };
  };
  const res = (post.estado?.ordem === "asc")
    ? await lerCrescente(post.estado, buscarPagina, { maxPaginas: MAX_PAGINAS })
    : await lerDecrescente(post.estado, buscarPagina, { maxNovas: MAX_PAGINAS, maxAntigas: 20 });
  return { comentarios: res.comentarios, estado: { ...res.estado, mediaId, ...(ordem ? { ordem } : {}) } };
}
// ---------- X / Twitter (API v2: respostas via conversation_id) ----------
async function x(post) {
  const bearer = process.env.X_BEARER_TOKEN;
  if (!bearer) throw semCredencial(["X_BEARER_TOKEN"]);
  if (!post.idPostagem) throw new Error("Link do X sem ID de status.");
  const headers = { authorization: `Bearer ${bearer}` };
  // search/recent cobre os últimos 7 dias; para posts antigos é preciso o plano com search/all.
  const endpoint = process.env.X_FULL_ARCHIVE ? "search/all" : "search/recent";

  // Se a última leitura parou no meio (muitas respostas novas), retoma da página pendente
  // mantendo o since_id antigo; só avança o since_id quando todas as páginas foram lidas.
  const comentarios = [];
  const sinceId = post.estado?.sinceId;
  let maiorId = post.estado?.maiorPendente || sinceId;
  let proxima = post.estado?.pendente || undefined;
  for (let i = 0; i < MAX_PAGINAS; i++) {
    const p = new URLSearchParams({
      query: `conversation_id:${post.idPostagem}`,
      max_results: "100",
      "tweet.fields": "author_id,created_at",
    });
    if (sinceId) p.set("since_id", sinceId);
    if (proxima) p.set("next_token", proxima);
    const json = await getJson(`https://api.x.com/2/tweets/${endpoint}?${p}`, { headers });
    for (const t of json.data || []) {
      comentarios.push({ id: t.id, texto: t.text || "", autor: t.author_id || null });
      if (!maiorId || BigInt(t.id) > BigInt(maiorId)) maiorId = t.id;
    }
    proxima = json.meta?.next_token;
    if (!proxima) break;
  }
  if (proxima) return { comentarios, estado: { sinceId: sinceId || null, pendente: proxima, maiorPendente: maiorId || null } };
  return { comentarios, estado: { sinceId: maiorId || null, pendente: null, maiorPendente: null } };
}

// ---------- TikTok (Research API: exige acesso aprovado pelo TikTok) ----------
let tokenTikTok = null;
async function tokenTiktok() {
  if (tokenTikTok && tokenTikTok.expira > Date.now()) return tokenTikTok.valor;
  const { TIKTOK_CLIENT_KEY: chave, TIKTOK_CLIENT_SECRET: segredo } = process.env;
  if (!chave || !segredo) throw semCredencial(["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"]);
  const json = await getJson("https://open.tiktokapis.com/v2/oauth/token/", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ client_key: chave, client_secret: segredo, grant_type: "client_credentials" }),
  });
  tokenTikTok = { valor: json.access_token, expira: Date.now() + (json.expires_in - 60) * 1000 };
  return tokenTikTok.valor;
}

async function tiktok(post) {
  if (!post.idPostagem) throw new Error("Link do TikTok sem ID do vídeo.");
  const token = await tokenTiktok();
  const comentarios = [];
  let cursor = 0;
  for (let i = 0; i < MAX_PAGINAS; i++) {
    const json = await getJson("https://open.tiktokapis.com/v2/research/video/comment/list/?fields=id,text,create_time,parent_comment_id", {
      method: "POST",
      headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
      body: JSON.stringify({ video_id: Number(post.idPostagem), max_count: 100, cursor }),
    });
    for (const c of json.data?.comments || []) comentarios.push({ id: String(c.id), texto: c.text || "", autor: null });
    if (!json.data?.has_more) break;
    cursor = json.data.cursor;
  }
  return { comentarios, estado: {} };
}

// ---------- YouTube (Data API v3) ----------
// Lista do mais novo para o mais antigo: lê as novidades e depois continua descendo
// pelos antigos de onde parou. Cada página gasta 1 unidade da cota diária (10 mil grátis).
async function youtube(post) {
  const chave = process.env.YOUTUBE_API_KEY;
  if (!chave) throw semCredencial(["YOUTUBE_API_KEY"]);
  if (!post.idPostagem) throw new Error("Link do YouTube sem ID do vídeo.");
  return lerDecrescente(post.estado, async (cursor) => {
    const p = new URLSearchParams({ part: "snippet", videoId: post.idPostagem, maxResults: "100", order: "time", textFormat: "plainText", key: chave });
    if (cursor) p.set("pageToken", cursor);
    const json = await getJson(`https://www.googleapis.com/youtube/v3/commentThreads?${p}`);
    return {
      itens: (json.items || []).map((item) => {
        const s = item.snippet.topLevelComment.snippet;
        return { id: item.id, texto: s.textOriginal || "", autor: s.authorChannelId?.value || s.authorDisplayName || null, quando: dataEmMs(s.publishedAt) };
      }),
      proximo: json.nextPageToken || null,
    };
  }, { maxNovas: 20, maxAntigas: Number(process.env.YOUTUBE_PAGINAS_POR_SYNC || 15) });
}
export const CONECTORES = { facebook, instagram, x, tiktok, youtube };

export function credenciaisConfiguradas() {
  const e = process.env;
  return {
    facebook: !!e.FACEBOOK_PAGE_TOKEN,
    instagram: !!((e.INSTAGRAM_TOKEN || e.FACEBOOK_PAGE_TOKEN) && e.INSTAGRAM_BUSINESS_ID),
    x: !!e.X_BEARER_TOKEN,
    tiktok: !!(e.TIKTOK_CLIENT_KEY && e.TIKTOK_CLIENT_SECRET),
    youtube: !!e.YOUTUBE_API_KEY,
  };
}
