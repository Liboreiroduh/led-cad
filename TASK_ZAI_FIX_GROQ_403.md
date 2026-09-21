# Microtarefa Z.ai — corrigir Groq 403 / Cloudflare 1010

## Modo de execução

Leia e siga `ZAI_MODO_EDICAO_DIRETA.md`. Esta é uma edição direta: não execute validação, testes, build, servidor ou browser.

## Diagnóstico confirmado

O endpoint local `GET /api/ai/groq/models` responde:

`HTTP 403 do provedor: error code: 1010`

Não é erro da chave. O backend usa `urllib` e envia o User-Agent padrão `Python-urllib/<versão>`. O Cloudflare da API Groq bloqueia essa assinatura com 403/1010 antes de processar autenticação.

## Escopo único

Trabalhe só em `mini-services/led-cad/services/ai_llm.py`, versão canônica. Não alterar frontend, PDF, CAD, modelos, chaves, configurações, provedores, endpoints ou arquivos de tarefa.

## Correção obrigatória

1. Definir um User-Agent estável de aplicação, por exemplo `LED-Structure-CAD/1.0`.
2. Aplicá-lo por padrão em **ambos** os helpers HTTP:
   - `_http_get_json` — necessário para `GET /openai/v1/models` do Groq.
   - `_http_json` — necessário para `POST /chat/completions` do Groq, evitando que a lista funcione e o chat ainda dê 403.
3. Preservar headers já enviados, especialmente `Authorization` e `Content-Type`. Nenhum header de autorização pode ser logado ou retornado.
4. Não usar user-agent de navegador falso, não desabilitar SSL, não criar retry infinito e não alterar a chave do usuário.
5. Melhorar a mensagem do erro somente se útil: `403/1010` deve informar que é bloqueio de assinatura HTTP, não “chave inválida”.

## Roadmap

- [x] 1. Aplicar User-Agent nos dois helpers sem remover Authorization/Content-Type.
  - Registro: `services/ai_llm.py` — constante `HTTP_USER_AGENT = "LED-Structure-CAD/1.0"` (com comentário do motivo: Cloudflare do Groq bloqueia `Python-urllib` com 403/1010 antes da autenticação). `_http_get_json`: headers mesclados `{"User-Agent": …, **(headers or {})}`; `_http_json`: `{"Content-Type": "application/json", "User-Agent": …, **(headers or {})}` — os headers do chamador (Authorization, Content-Type) continuam passando e têm precedência; nenhum header é logado ou retornado. Mensagem de erro melhorada nos DOIS helpers: `403` com `1010` no corpo agora informa "bloqueio da assinatura HTTP do cliente — NÃO é chave inválida". Sem UA de navegador falso, sem mexer em SSL/retry/chave.

- [x] 2. Marcar concluído e parar. Não validar nem executar nada.
  - Registro: concluído — nenhuma validação/execução rodada (edição direta).

## Resumo final

- Arquivo alterado: `mini-services/led-cad/services/ai_llm.py` (apenas).
- Header aplicado em: `_http_get_json` (GET `/openai/v1/models` do Groq) e `_http_json` (POST `/chat/completions` do Groq), via `HTTP_USER_AGENT = "LED-Structure-CAD/1.0"`, preservando Authorization/Content-Type do chamador.
- Pendências reais: conferência visual/funcional pelo usuário (reexecutar `GET /api/ai/groq/models` e um chat Groq para confirmar o fim do 403/1010).
