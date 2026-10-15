// Busca páginas com cabeçalhos de navegador e detecção de bloqueio anti-robô.

const HEADERS = {
  "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
  accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  "accept-language": "pt-BR,pt;q=0.9,en;q=0.7",
  "cache-control": "no-cache",
};

export class FetchError extends Error {}

export async function fetchPage(url, { timeoutMs = 20_000, fetchImpl = fetch } = {}) {
  const res = await fetchImpl(url, { headers: HEADERS, redirect: "follow", signal: AbortSignal.timeout(timeoutMs) });
  const html = await res.text();
  if (!res.ok) throw new FetchError(`HTTP ${res.status} ao acessar ${new URL(url).hostname}`);
  if (/captcha|api-services-support@amazon|are you a robot|verifique que você não é um robô|cf-chl-bypass/i.test(html.slice(0, 50_000)) && html.length < 60_000) {
    throw new FetchError("A loja bloqueou a consulta automática (captcha). Tente mais tarde ou registre o preço manualmente.");
  }
  return html;
}
