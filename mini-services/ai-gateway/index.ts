// ai-gateway — wrapper HTTP do z-ai-web-dev-sdk (GLM gratuito) para o led-cad.
// Porta fixa 3101 (server-to-server, chamado pelo serviço Python na 3100).
//
// PROXY LED CAD (desde o incidente da borda): a borda do sandbox só diala
// portas REGISTRADAS (3000 e 3101) — a 3100 do led-cad ficou 502 no domínio
// público. Como a 3101 continua alcançável, este gateway também encaminha
// (reverse proxy) o app do CAD para 127.0.0.1:3100. Assim o acesso público
// passa a ser  ?XTransformPort=3101  (ou /cad?XTransformPort=3101) e o app
// inteiro (HTML, vendors e /api) flui pela porta registrada.
// Rotas próprias (/health, /chat) continuam locais — sem loop: o Python chama
// /chat aqui direto e /chat nunca é proxyada.
import ZAI from 'z-ai-web-dev-sdk';

const PORT = 3101;
const UPSTREAM = 'http://127.0.0.1:3100';
const STARTED_AT = Date.now();

type ZAIClient = Awaited<ReturnType<typeof ZAI.create>>;

// Cliente ZAI único, criado sob demanda. Um ZAI.create() que falha NÃO é
// cacheado (zaiClient permanece null → a próxima requisição tenta de novo).
let zaiClient: ZAIClient | null = null;

async function getClient(): Promise<ZAIClient> {
  if (zaiClient) return zaiClient;
  zaiClient = await ZAI.create();
  return zaiClient;
}

const CORS_HEADERS: Record<string, string> = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
  });
}

interface IncomingChatMessage {
  role: string;
  content: string;
}

type NormalizedMessage = { role: 'user' | 'assistant'; content: string };

function validateMessages(
  raw: unknown,
): { ok: true; messages: NormalizedMessage[] } | { ok: false; error: string } {
  if (!Array.isArray(raw) || raw.length === 0) {
    return { ok: false, error: "'messages' must be a non-empty array" };
  }
  const messages: NormalizedMessage[] = [];
  for (let i = 0; i < raw.length; i++) {
    const item = raw[i] as Partial<IncomingChatMessage> | null;
    if (typeof item !== 'object' || item === null) {
      return { ok: false, error: `messages[${i}] must be an object with role and content` };
    }
    const { role, content } = item;
    if (typeof role !== 'string' || !['user', 'assistant', 'system'].includes(role)) {
      return {
        ok: false,
        error: `messages[${i}].role must be "user", "assistant" or "system"`,
      };
    }
    if (typeof content !== 'string') {
      return { ok: false, error: `messages[${i}].content must be a string` };
    }
    // O z-ai SDK usa role "assistant" para prompts de sistema →
    // qualquer "system" recebido é mapeado para "assistant" antes da chamada.
    messages.push({
      role: role === 'system' ? 'assistant' : (role as 'user' | 'assistant'),
      content,
    });
  }
  return { ok: true, messages };
}

async function handleChat(req: Request): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return json({ ok: false, error: 'invalid JSON body' }, 400);
  }
  if (typeof body !== 'object' || body === null) {
    return json({ ok: false, error: 'body must be a JSON object' }, 400);
  }

  const input = body as { messages?: unknown; model?: unknown };
  const parsed = validateMessages(input.messages);
  if (!parsed.ok) {
    return json({ ok: false, error: parsed.error }, 400);
  }

  // Nota: `temperature` do request é intencionalmente IGNORADO (caminho mais
  // seguro — o gateway não repassa parâmetros opcionais de sampling ao SDK).
  // max_tokens: geracões de desenho livre (gaiolas, círculos, casas) produzem
  // JSON longo — sem isto o GLM cortava no padrão (~1k) e o JSON quebrava.
  try {
    const client = await getClient();
    const completion = await client.chat.completions.create({
      // O CAD controla o modelo; o gateway jamais deve cair silenciosamente
      // no default do SDK, que pode mudar entre ambientes.
      model: typeof input.model === 'string' && input.model.trim()
        ? input.model.trim()
        : 'glm-4.5-flash',
      messages: parsed.messages,
      thinking: { type: 'disabled' },
      max_tokens: 8192,
    });
    const choices = (completion as { choices?: Array<{ message?: { content?: string }; finish_reason?: string | null }> })
      ?.choices;
    const content = choices?.[0]?.message?.content ?? '';
    return json({
      ok: true,
      content,
      finish_reason: choices?.[0]?.finish_reason ?? null,
    });
  } catch (err) {
    const e = err as { message?: string } | undefined;
    return json({ ok: false, error: String(e?.message || err) }, 502);
  }
}

// ---------------------------------------------------------------- proxy CAD
// /cad e /cad/* → 3100/ e 3100/*  (o app também é servido sob o prefixo /cad)
// qualquer outro caminho (/, /api/*, /js/*, /presets/*, /export/*) → 3100 igual
function mapPath(pathname: string): string {
  if (pathname === '/cad' || pathname === '/cad/') return '/';
  if (pathname.startsWith('/cad/')) return pathname.slice('/cad'.length);
  return pathname;
}

async function proxyToCad(req: Request, pathname: string): Promise<Response> {
  const url = new URL(req.url);
  const target = `${UPSTREAM}${mapPath(pathname)}${url.search}`;
  const init: RequestInit = {
    method: req.method,
    headers: req.headers,
    redirect: 'manual',
  };
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    init.body = await req.arrayBuffer();
  }
  try {
    const upstream = await fetch(target, init);
    const headers = new Headers(upstream.headers);
    headers.set('x-led-cad-proxy', 'ai-gateway:3101');
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers,
    });
  } catch (err) {
    const e = err as { message?: string } | undefined;
    console.error('[ai-gateway] proxy erro:', target, err);
    return json(
      { ok: false, error: `led-cad indisponível: ${String(e?.message || err)}` },
      502,
    );
  }
}

const server = Bun.serve({
  port: PORT,
  async fetch(req): Promise<Response> {
    const url = new URL(req.url);
    const path = url.pathname;

    try {
      if (req.method === 'OPTIONS') {
        return new Response(null, { status: 204, headers: { ...CORS_HEADERS } });
      }

      if (path === '/health' && req.method === 'GET') {
        const uptimeS = Math.round(((Date.now() - STARTED_AT) / 1000) * 10) / 10;
        return json({ ok: true, service: 'ai-gateway', model: 'glm', uptime_s: uptimeS });
      }

      if (path === '/chat' && req.method === 'POST') {
        return await handleChat(req);
      }

      // Tudo o mais → app LED STRUCTURE CAD (:3100) — proxy transparente.
      return await proxyToCad(req, path);
    } catch (err) {
      const e = err as { message?: string } | undefined;
      console.error('[ai-gateway] unhandled error:', err);
      return json({ ok: false, error: String(e?.message || err) }, 500);
    }
  },
});

console.log(`[ai-gateway] listening on http://localhost:${server.port}`);
