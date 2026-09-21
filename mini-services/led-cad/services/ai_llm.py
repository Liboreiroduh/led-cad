"""Conector UNIVERSAL de IA (modo manual) para o LED STRUCTURE CAD.

Decisão de produto (TASK_ZAI_CONECTORES_UNIVERSAIS): nada de provedores
especiais nem catálogo automático. O usuário cadastra CONEXÕES manuais para
qualquer API compatível com OpenAI (Groq, OpenRouter, Gemini em modo
OpenAI-compatível, DeepSeek, Ollama local…): nome, URL base, chave e modelo.

- data/ai_config.json guarda `active_connection_id` + `connections`
  [{id, name, base_url, model, api_key}]. A chave NUNCA sai do backend
  (a API pública devolve apenas `has_key` + máscara). Chaves/config legadas
  que existam no arquivo permanecem como dados não usados (não são apagadas
  nem expostas em respostas públicas).
- Toda chamada é `POST {base_url}/chat/completions` com Bearer token.
- Somente biblioteca padrão (urllib) — sem dependências novas.
"""
from __future__ import annotations

import json
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

CONFIG_FILE = Path(__file__).resolve().parent.parent / "data" / "ai_config.json"
# Uma operação de desenho precisa responder rápido. Sem teto, uma chamada
# síncrona pode ficar invisivelmente pendurada por dois minutos no navegador.
TIMEOUT_S = 75.0
# User-Agent estável de aplicação: o Cloudflare do Groq bloqueia a assinatura
# padrão Python-urllib com 403/1010 antes de processar a autenticação.
HTTP_USER_AGENT = "LED-Structure-CAD/1.0"


class AiError(RuntimeError):
    """Erro de conexão/configuração com o provedor de IA.

    `status`/`retry_after` (quando o provedor informa) viajam para a UI e
    alimentam os estados de limite/erro do Copiloto — sem expor headers."""

    def __init__(self, msg: str, status: Optional[int] = None,
                 retry_after: Optional[int] = None):
        super().__init__(msg)
        self.status = status
        self.retry_after = retry_after


def _mask(key: Optional[str]) -> str:
    k = str(key or "")
    if not k:
        return ""
    if len(k) <= 10:
        return k[:2] + "…" + k[-2:]
    return k[:6] + "…" + k[-4:]


# ------------------------------------------------------------------ config
def _read_doc() -> Dict[str, Any]:
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _write_doc(doc: Dict[str, Any]) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                           encoding="utf-8")


def _norm_conn(c: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(c, dict):
        return None
    cid = str(c.get("id") or "").strip()
    if not cid:
        return None
    return {
        "id": cid,
        "name": str(c.get("name") or "").strip() or f"Conexão {cid[:8]}",
        "base_url": str(c.get("base_url") or "").strip().rstrip("/"),
        "model": str(c.get("model") or "").strip(),
        "api_key": str(c.get("api_key") or ""),
    }


def load_config() -> Dict[str, Any]:
    """Config normalizada das conexões manuais: `active_connection_id` +
    `connections`. Chaves legadas no arquivo são preservadas em disco, mas
    NÃO entram nesta estrutura nem em respostas públicas."""
    doc = _read_doc()
    conns = [c for c in (_norm_conn(x) for x in doc.get("connections") or [])
             if c]
    active = str(doc.get("active_connection_id") or "").strip()
    if active and not any(c["id"] == active for c in conns):
        active = conns[0]["id"] if conns else ""
    return {"active_connection_id": active, "connections": conns}


def _persist(doc: Dict[str, Any], cfg: Dict[str, Any]) -> None:
    # preserva chaves/config legadas que existam no arquivo (dados não usados)
    doc.update({"active_connection_id": cfg["active_connection_id"],
                "connections": cfg["connections"]})
    _write_doc(doc)


def _conn_public(c: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": c["id"], "name": c["name"], "base_url": c["base_url"],
            "model": c["model"], "has_key": bool(c["api_key"]),
            "masked": _mask(c["api_key"]) if c["api_key"] else ""}


def public_config(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Config devolvida para a UI — NUNCA inclui a chave em claro."""
    cfg = cfg or load_config()
    return {
        "active_connection_id": cfg["active_connection_id"],
        "connections": [_conn_public(c) for c in cfg["connections"]],
    }


# ------------------------------------------------------------------ config
def save_connection(patch: Dict[str, Any]) -> Dict[str, Any]:
    """Cria ou atualiza uma conexão manual e a torna ativa.

    `api_key` vazio/ausente em uma conexão existente PRESERVA a chave salva."""
    cfg = load_config()
    doc = _read_doc()
    cid = str(patch.get("id") or "").strip()
    name = str(patch.get("name") or "").strip()
    base = str(patch.get("base_url") or "").strip().rstrip("/")
    model = str(patch.get("model") or "").strip()
    key = patch.get("api_key")
    key = "" if key is None else str(key).strip()
    if not base:
        raise AiError("Informe a URL base da API (ex.: https://api.groq.com/openai/v1).")
    if not re.match(r"^https?://", base):
        raise AiError("URL base inválida — deve começar com http:// ou https://.")
    if not model:
        raise AiError("Informe o modelo (ex.: qwen/qwen3.8-27b).")
    target = next((c for c in cfg["connections"] if c["id"] == cid), None) \
        if cid else None
    if target is None:
        target = {"id": "conn_" + secrets.token_hex(4)}
        cfg["connections"].append(target)
    target["name"] = name or _host_of(base)
    target["base_url"] = base
    target["model"] = model
    if key:
        target["api_key"] = key
    target.setdefault("api_key", "")
    cfg["active_connection_id"] = target["id"]
    _persist(doc, cfg)
    return public_config(cfg)


def _host_of(base: str) -> str:
    m = re.match(r"^https?://([^/]+)", base)
    return (m.group(1) if m else base)[:32]


def delete_connection(conn_id: str) -> Dict[str, Any]:
    cfg = load_config()
    before = len(cfg["connections"])
    cfg["connections"] = [c for c in cfg["connections"] if c["id"] != conn_id]
    if len(cfg["connections"]) == before:
        raise AiError("Conexão não encontrada.")
    if cfg["active_connection_id"] == conn_id:
        cfg["active_connection_id"] = cfg["connections"][0]["id"] \
            if cfg["connections"] else ""
    _persist(_read_doc(), cfg)
    return public_config(cfg)


def activate_connection(conn_id: str) -> Dict[str, Any]:
    cfg = load_config()
    if not any(c["id"] == conn_id for c in cfg["connections"]):
        raise AiError("Conexão não encontrada.")
    cfg["active_connection_id"] = conn_id
    _persist(_read_doc(), cfg)
    return public_config(cfg)


def provider_capabilities(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Capabilities do provedor da conexão ATIVA — fonte única para payload
    HTTP (structured output, reasoning, limite de saída). Evita espalhar
    `if host == ...` pela aplicação.

    - Z.ai (api.z.ai): raciocínio interno habilitado (thinking enabled,
      max_tokens 8192) — NUNCA recebe JSON Schema do Groq.
    - Groq (api.groq.com): structured output declarado; schema estrito
      (json_schema) somente para modelos GPT-OSS confirmados na doc oficial.
      GPT-OSS (20b/120b) é reasoning-capable.
    - Conectores OpenAI-compatíveis genéricos: nada de campos Groq/Z.ai."""
    conn = _conn_of(cfg)
    m = re.match(r"^https?://([^/]+)", conn.get("base_url") or "")
    host = (m.group(1) if m else "").lower()
    model = (conn.get("model") or "").lower()
    if host == "api.z.ai":
        return {"structured_output": False, "strict_schema": False,
                "reasoning": True, "max_tokens": 8192}
    if host == "api.groq.com":
        oss = model.startswith("openai/gpt-oss")
        # O tier gratuito do Groq tem orçamento de tokens por minuto. GPT-OSS
        # recebe um prompt CAD relativamente grande; 8192 tokens de saída
        # fariam prompt + completion ultrapassar 8k TPM antes de o modelo
        # processar a requisição. 3000 preserva espaço para o JSON de operações
        # sem afetar a Z.ai, que continua com 8192.
        return {"structured_output": True, "strict_schema": oss,
                "reasoning": oss, "max_tokens": 3000}
    return {"structured_output": False, "strict_schema": False,
            "reasoning": False, "max_tokens": None}


def _conn_of(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = cfg or load_config()
    cid = cfg.get("active_connection_id")
    conn = next((c for c in cfg.get("connections") or []
                 if c["id"] == cid), None)
    if conn is None:
        raise AiError("Nenhuma conexão de IA ativa. Abra ⚙ Conector IA, "
                      "cadastre/selecione uma conexão e teste antes de usar.")
    if not conn.get("base_url") or not conn.get("model"):
        raise AiError(f"Conexão '{conn.get('name')}' incompleta: informe URL "
                      "base e modelo no ⚙ Conector IA.")
    return conn


def _active_conn(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return _conn_of(cfg)


# ------------------------------------------------------------------- chat
def _http_json(url: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None,
               timeout: float = TIMEOUT_S) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    merged = {"Content-Type": "application/json", "User-Agent": HTTP_USER_AGENT,
              **(headers or {})}
    req = urllib.request.Request(url, data=body, method="POST", headers=merged)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")[:400]
        except Exception:
            detail = ""
        retry = None
        try:
            retry = int(e.headers.get("Retry-After", "") or "") or None
        except (ValueError, TypeError):
            retry = None
        if e.code == 403 and "1010" in detail:
            raise AiError(
                "HTTP 403 (Cloudflare 1010): bloqueio da assinatura HTTP do "
                "cliente — NÃO é chave inválida. Atualize o LED-Structure-CAD "
                "ou contate o suporte do provedor.", status=403) from e
        if e.code == 403:
            detail = f"recusado pelo provedor. {detail}"
        raise AiError(f"HTTP {e.code} do provedor: {detail or e.reason}",
                      status=e.code, retry_after=retry) from e
    except urllib.error.URLError as e:
        raise AiError(f"Falha de conexão com o provedor ({e.reason})") from e
    except TimeoutError:
        raise AiError("Tempo esgotado esperando a resposta da IA.",
                      status=408) from None


def _gpt_oss_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Preparação provider-aware APENAS para GPT-OSS (Groq, reasoning): a doc
    do Groq recomenda NÃO depender de system prompt — as instruções vão no
    conteúdo da PRIMEIRA mensagem de usuário. A ordem dos turnos (inclusive
    os do retry guiado: user/assistant/user) é preservada. Z.ai continua
    recebendo `system`, que já funciona bem com GLM."""
    sys_txt = "\n\n".join(m.get("content") or "" for m in messages
                          if m.get("role") == "system")
    out: List[Dict[str, str]] = []
    injected = False
    for m in messages:
        role = m.get("role") or "user"
        if role == "system":
            continue
        if role == "user" and not injected:
            content = m.get("content") or ""
            if sys_txt:
                content = (f"[INSTRUÇÕES CAD]\n{sys_txt}\n\n"
                           f"[PEDIDO / CONTEXTO]\n{content}")
            out.append({"role": "user", "content": content})
            injected = True
        else:
            out.append({"role": role, "content": m.get("content") or ""})
    return out


def chat_completion(messages: List[Dict[str, str]],
                    cfg: Optional[Dict[str, Any]] = None,
                    response_schema: Optional[Dict[str, Any]] = None) -> str:
    """Uma completion na conexão ATIVA — única implementação, universal:
    POST {base_url}/chat/completions com Bearer token, model e messages.

    `response_schema` (JSON Schema do contrato CAD) é enviado SOMENTE quando
    as capabilities confirmarem structured output estrito (Groq GPT-OSS).
    Z.ai segue com thinking interno habilitado e sem schema; conectores
    genéricos não recebem campos de terceiros."""
    conn = _active_conn(cfg)
    caps = provider_capabilities(cfg)
    payload: Dict[str, Any] = {
        "model": conn["model"], "temperature": 0.2,
    }
    # GLM-4.5 na Z.ai: o raciocínio INTERNO precisa estar HABILITADO —
    # `thinking: disabled` degradava a capacidade de interpretar/criar/editar.
    # A cadeia de pensamento fica no provedor: o app lê somente
    # choices[0].message.content e nada de reasoning_content é exposto,
    # logado ou persistido. NUNCA enviar JSON Schema do Groq à Z.ai.
    host = (urllib.parse.urlparse(conn["base_url"]).hostname or "").lower()
    if host == "api.z.ai":
        payload["messages"] = messages
        payload["thinking"] = {"type": "enabled"}
        payload["max_tokens"] = caps.get("max_tokens") or 8192
    elif host == "api.groq.com":
        # Groq substituiu o `max_tokens` legado por `max_completion_tokens`.
        payload["max_completion_tokens"] = caps.get("max_tokens") or 8192
        if caps.get("reasoning"):
            # GPT-OSS (20b/120b) é reasoning-capable: esforço MÉDIO; a cadeia
            # de raciocínio NUNCA é exposta na UI, logada ou persistida —
            # o app lê somente choices[0].message.content.
            payload["reasoning_effort"] = "medium"
            payload["include_reasoning"] = False
            payload["messages"] = _gpt_oss_messages(messages)
        else:
            payload["messages"] = messages
        if caps.get("strict_schema") and response_schema:
            # Structured Output EFETIVO (Groq GPT-OSS): json_schema estrito.
            # Opcionais do schema são anuláveis → podem chegar `null`; a
            # tradução para operations esparsas acontece em
            # services.ai_contract.validate_payload (_sanitize_strict_nulls).
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "cad_plan", "strict": True,
                                "schema": response_schema},
            }
        else:
            # Groq sem GPT-OSS confirmado: json_object + validação local
            payload["response_format"] = {"type": "json_object"}
    else:
        payload["messages"] = messages
    out = _http_json(
        f"{conn['base_url']}/chat/completions", payload,
        headers={"Authorization": f"Bearer {conn['api_key']}"} if conn["api_key"] else None,
    )
    try:
        return str(out["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError) as e:
        raise AiError(f"Resposta inesperada do provedor: {json.dumps(out)[:300]}") from e


def test_provider(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Teste da conexão ativa: pergunta trivial via chat/completions."""
    conn = _active_conn(cfg)
    t0 = time.time()
    reply = chat_completion(
        [{"role": "system", "content": "Responda apenas: PONG"},
         {"role": "user", "content": "ping"}], cfg)
    return {"ok": True, "name": conn["name"], "model": conn["model"],
            "reply": (reply or "").strip()[:120],
            "elapsed_s": round(time.time() - t0, 2)}


def test_connection(patch: Dict[str, Any]) -> Dict[str, Any]:
    """Teste EFÊMERO com os valores do formulário — SOMENTE em memória.

    Não salva arquivo, não altera a conexão ativa e não troca chave existente
    (chave vazia em uma conexão já salva usa a chave guardada só para o
    teste). Faz um `chat/completions` mínimo."""
    cfg = load_config()
    conn: Dict[str, Any] = {"id": "", "name": "", "base_url": "", "model": "",
                            "api_key": ""}
    cid = str(patch.get("id") or "").strip()
    if cid:
        saved = next((c for c in cfg["connections"] if c["id"] == cid), None)
        if saved:
            conn.update(saved)
    conn["base_url"] = str(patch.get("base_url") or "").strip().rstrip("/") \
        or conn["base_url"]
    conn["model"] = str(patch.get("model") or "").strip() or conn["model"]
    key = patch.get("api_key")
    if key is not None and str(key).strip():
        conn["api_key"] = str(key).strip()
    if not conn["base_url"] or not conn["model"]:
        raise AiError("Preencha URL base e modelo para testar a conexão.")
    if not re.match(r"^https?://", conn["base_url"]):
        raise AiError("URL base inválida — deve começar com http:// ou https://.")
    name = str(patch.get("name") or "").strip() or conn["name"] \
        or _host_of(conn["base_url"])
    t0 = time.time()
    out = _http_json(
        f"{conn['base_url']}/chat/completions",
        {"model": conn["model"],
         "messages": [{"role": "system", "content": "Responda apenas: PONG"},
                      {"role": "user", "content": "ping"}],
         "temperature": 0.2},
        headers={"Authorization": f"Bearer {conn['api_key']}"} if conn["api_key"] else None,
    )
    try:
        reply = str(out["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError) as e:
        raise AiError(f"Resposta inesperada do provedor: {json.dumps(out)[:300]}") from e
    return {"ok": True, "name": name, "model": conn["model"],
            "reply": reply.strip()[:120],
            "elapsed_s": round(time.time() - t0, 2)}
