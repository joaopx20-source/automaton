// Identifica a rede social e o ID da postagem a partir do link colado no painel.
// O placar trabalha só com Instagram e Facebook.

export const REDES = {
  facebook: "Facebook",
  instagram: "Instagram",
};

export function analisarLink(link) {
  let url;
  try {
    url = new URL(String(link).trim());
  } catch {
    throw new Error("Link inválido. Cole o endereço completo da postagem (https://...).");
  }
  const host = url.hostname.replace(/^(www|m|mobile|web)\./, "");
  const caminho = url.pathname;
  let m;

  if (/(^|\.)instagram\.com$/.test(host)) {
    m = caminho.match(/\/(?:p|reel|reels|tv)\/([A-Za-z0-9_-]+)/);
    return { rede: "instagram", idPostagem: m?.[1] ?? null, url: url.href };
  }

  if (/(^|\.)(facebook\.com|fb\.com|fb\.watch)$/.test(host)) {
    // facebook.com/permalink.php?story_fbid=X&id=PAGINA
    const story = url.searchParams.get("story_fbid");
    const dono = url.searchParams.get("id");
    if (story && dono && /^\d+$/.test(story)) return { rede: "facebook", idPostagem: `${dono}_${story}`, url: url.href };
    // facebook.com/PAGINA/posts/123 ou /videos/123 ou /photo?fbid=123
    m = caminho.match(/\/(?:posts|videos|reel)\/(\d+)/);
    const fbid = m?.[1] ?? url.searchParams.get("fbid") ?? url.searchParams.get("v");
    return { rede: "facebook", idPostagem: fbid && /^\d+$/.test(fbid) ? fbid : null, url: url.href, curto: !fbid };
  }

  throw new Error("Rede social não suportada. Use links do Instagram ou do Facebook.");
}

// Links curtos (fb.watch, facebook.com/share/...) precisam seguir o redirecionamento.
export async function resolverLinkCurto(link) {
  const resp = await fetch(link, { redirect: "follow", headers: { "user-agent": "Mozilla/5.0" } });
  return resp.url || link;
}
