# Tarefa Z.ai — configurar provedores gratuitos decididos

## Fonte única e escopo

Trabalhe somente na versão canônica: `mini-services/led-cad`.

Leia `AI_FREE_PROVIDERS_DECIDED.md` como decisão fechada de produto. Não pesquise, não acrescente nem troque provedores/modelos por conta própria; sua tarefa é somente implementar a matriz já decidida.

Objetivo: configurar no front os três provedores gratuitos já decididos — Gemini, OpenRouter e Groq — com suas chaves guardadas uma vez no servidor local e seus modelos selecionáveis de forma correta.

Arquivos candidatos: `services/ai_llm.py`, `main.py`, `static/index.html`. Não criar outro frontend, outro gateway, banco paralelo ou configuração alternativa. Não alterar CAD, PDF, presets, IA prompts, geometria, operações ou exportação.

## Requisitos funcionais

1. Adicionar o provedor `openrouter` separado de `compat`.
   - Label: `OpenRouter — modelos gratuitos`.
   - Base URL fixa: `https://openrouter.ai/api/v1`.
   - Chat pelo endpoint OpenAI-compatível `/chat/completions` já usado pelos demais provedores.
   - A chave é exigida para usar/testar o provedor.

2. No modal **⚙ Conector IA**:
   - Ao selecionar OpenRouter, exibir campo de chave e um **select de modelos gratuitos**, não apenas input livre.
   - Exibir botão `Atualizar modelos gratuitos` e estado de carregamento/erro claro.
   - Exibir nome legível e ID exato do modelo; o valor salvo/enviado deve ser o `id` oficial do OpenRouter.
   - Deixar uma opção explícita `Modelo manual…` para o usuário digitar um ID se quiser usar um modelo pago depois; não escolher modelo pago automaticamente.
   - Ocultar/desabilitar a Base URL manual para OpenRouter, pois ela é fixa.

3. A lista deve ser dinâmica e segura:
   - Criar endpoint local autenticado apenas pelo serviço, por exemplo `GET /api/ai/openrouter/free-models`.
   - O backend chama `https://openrouter.ai/api/v1/models` com a chave já salva no servidor. O navegador nunca chama OpenRouter diretamente e nunca recebe a chave completa.
   - Filtrar o retorno oficial por modelos de chat/texto cujo preço de `prompt`, `completion` e `request` seja numérico e igual a `0`.
   - Preservar somente campos seguros para o browser: `id`, `name`, `context_length`, modalidades/parâmetros úteis e preço público. Nunca devolver token/chave/cabeçalhos.
   - Ordenar de forma estável por nome; remover duplicados por `id`.
   - Fazer cache local em memória por no máximo 10 minutos, com botão de atualização forçada. Não gravar a lista nem a chave em arquivos extras desnecessários.
   - Se a consulta falhar, mostrar erro e manter a seleção anteriormente salva; não trocar silenciosamente para outro provedor/modelo.

4. Persistência e segurança:
   - Estender o mesmo `data/ai_config.json` já existente: `keys.openrouter`, `models.openrouter`; não criar outro mecanismo de segredo.
   - A API pública de configuração deve continuar devolvendo apenas chave mascarada e `has_key`; nunca a chave em claro.
   - Não registrar chave, Authorization header ou resposta integral do OpenRouter no console, toast, histórico ou arquivo de tarefa.
   - Ao salvar outra configuração sem digitar a chave OpenRouter, preservar a chave existente, exatamente como os demais provedores.

5. Adicionar Groq como provedor próprio:
   - Label: `Groq — quota gratuita (sujeita a limites)`.
   - Base URL fixa: `https://api.groq.com/openai/v1`.
   - Chave obrigatória, salva em `keys.groq`; modelo em `models.groq`.
   - Modelo padrão inicial definido pelo produto: **`qwen/qwen3.8-27b`**. Exibi-lo como primeira opção/recomendado quando estiver ativo no catálogo da conta; se o catálogo informar que ele não está disponível, manter o ID salvo e mostrar aviso claro para o usuário escolher outro, sem substituição silenciosa.
   - Criar endpoint local para consultar `GET https://api.groq.com/openai/v1/models` com a chave no backend e entregar ao front somente `id`/campos públicos dos modelos ativos.
   - O front usa select atualizado sob demanda, com botão `Atualizar modelos Groq`; modelo manual continua disponível.
   - Não classificar modelos Groq como “grátis para sempre”; mostrar na UI que a conta possui quota gratuita e pode atingir limite.

6. Compatibilidade:
   - Não quebrar z.ai, Gemini, OpenAI e `compat`.
   - `compat` continua disponível para provedores manuais; OpenRouter não deve ser escondido dentro dele.
   - O teste de conexão deve informar `OpenRouter — modelos gratuitos` e o ID efetivamente selecionado.

## Correção obrigatória do Gemini

O modelo atualmente salvo no projeto, `gemini-2.0-flash`, foi oficialmente descontinuado/desligado pelo Google. Corrija isso no mesmo fluxo de configuração antes de considerar a tarefa concluída.

1. Trocar o padrão Gemini do sistema para **`gemini-2.5-flash`**. É o recomendado para este CAD: tem camada gratuita e melhor capacidade de raciocínio/saída estruturada do que Lite.
2. No seletor Gemini do front, oferecer opções oficiais de camada gratuita:
   - `gemini-2.5-flash` — recomendado, raciocínio e contexto amplo.
   - `gemini-2.5-flash-lite` — econômico/rápido para pedidos simples.
   - `gemini-2.5-pro` — opcional, sujeito a limites gratuitos mais restritos; não selecionar automaticamente.
3. Ao carregar uma configuração antiga com `gemini-2.0-flash` ou `gemini-2.0-flash-lite`, migrar automaticamente para `gemini-2.5-flash` antes de testar/chamar a API. Mostrar no modal um aviso curto de que o modelo anterior foi aposentado e foi atualizado.
4. Não usar preview desligado, aliases vagos ou modelos de imagem/áudio para o copiloto textual. Não alegar uso ilimitado: deixar claro na UI que há limites da camada gratuita do Google.

7. Ordem correta do modal (obrigatória):
   - Ação principal ao preencher chave/modelo: **Testar conexão**.
   - O teste deve enviar os valores atualmente digitados ao backend apenas para uma chamada efêmera; não pode gravar `ai_config.json`, nem alterar o provedor ativo, nem substituir a chave salva antes de retornar sucesso.
   - Só depois do teste bem-sucedido o usuário clica em **Salvar configuração**.
   - Se o teste falhar, mostrar o motivo e não salvar nada.
   - A tela pode avisar quando há alterações ainda não salvas. Nunca exigir que o usuário salve uma chave inválida apenas para poder testá-la.

## Modelos gratuitos — regra importante

Não hardcode uma lista como verdade. O catálogo do OpenRouter é mutável. A fonte de verdade deve ser o endpoint oficial `/api/v1/models`, filtrado pelos preços zero acima.

Como referência de UX apenas, a página pública lista atualmente alguns modelos marcados como free, por exemplo Ling 3.0 Flash VL, Nex-N2.5-Mini e Nex-N2.5-Pro; eles podem desaparecer ou mudar. A tela deve refletir o retorno atual da API, não esses nomes fixos. Incluir a opção `openrouter/free` como “Automático — melhor modelo gratuito disponível”, mas não selecionar automaticamente se o usuário já escolheu um ID específico.

## Roadmap obrigatório

Atualize este arquivo durante o trabalho. Marque uma etapa somente após concluí-la e registre decisões/arquivos reais abaixo. Não criar relatório separado e não testar a cada microedição.

- [x] 1. Mapear o fluxo atual de configuração e chamada de provedores; registrar como Gemini, OpenRouter e Groq serão integrados sem duplicar `compat`.
  - Registro: Fluxo atual — `PROVIDERS` (dict) em `services/ai_llm.py` define zai/gemini/openai/compat; configuração única em `data/ai_config.json` (`provider`, `keys`, `models`, `base_urls`), com `load_config` (valida provider + migração pontual `glm`→`glm-4.5-flash`), `save_config` (chave vazia NÃO apaga a salva), `public_config` (só `masked` + `has_key` + metadados), `_resolve` → `chat_completion` (zai via gateway :3101; demais OpenAI-compatíveis `/chat/completions`) e `test_provider(cfg)`. Endpoints em `main.py`: GET/POST `/api/ai/config`, POST `/api/ai/test`. UI: modal `#aiCfgModal` (select de provedor, chave, input de modelo livre, base URL só p/ compat, testar/salvar). Integração SEM duplicar `compat`: `openrouter` e `groq` entram como novos registros de `PROVIDERS` (base URL fixa no meta, `needs_key`) reaproveitando `_resolve`/`chat_completion`/`test_provider`; catálogos novos buscados por urllib GET **no backend** com a chave salva, cache em memória 10 min no mesmo módulo; persistência continua só em `data/ai_config.json` (`keys.openrouter/groq`, `models.openrouter/groq`); novo `POST /api/ai/test-dry` para testar valores digitados sem persistir nada; Gemini ganha migração 2.0→2.5 e opções fixas decididas; UI reusa o mesmo modal com select de modelos + botão de atualização.

- [x] 2. Implementar backend: providers, persistência mascarada, catálogo seguro/cached do OpenRouter (preço zero) e catálogo seguro/cached do Groq (modelos ativos).
  - Registro: `services/ai_llm.py` — `PROVIDERS` ganhou `openrouter` (label `OpenRouter — modelos gratuitos`, base fixa `https://openrouter.ai/api/v1`, `needs_key`, default `openrouter/free`) e `groq` (label `Groq — quota gratuita (sujeita a limites)`, base fixa `https://api.groq.com/openai/v1`, default do produto `qwen/qwen3.8-27b`); ambos reutilizam `_resolve`/`chat_completion`/`test_provider` (endpoint OpenAI-compat `/chat/completions`) — nada de gateway duplicado. Persistência continua SÓ em `data/ai_config.json` (`keys.openrouter/groq`, `models.openrouter/groq`); `public_config` devolve apenas `masked` + `has_key` (+ `notice` de migração) — verificado que nenhuma chave em claro aparece. Catálogos: `_http_get_json` (urllib, Authorization NUNCA logado); `openrouter_free_models()` chama `GET https://openrouter.ai/api/v1/models` com a chave salva e `_filter_openrouter` mantém só chat/texto (modality terminando em `->text`) com `pricing.prompt/completion/request` numéricos `= 0`, campos públicos (`id`, `name`, `context_length`, `modality`, `pricing`), dedupe por `id`, ordem estável por nome; `groq_models()` chama `GET https://api.groq.com/openai/v1/models` e `_normalize_groq` entrega id/owned_by/context_window dos ativos, dedupe e `qwen/qwen3.8-27b` primeiro com flag `recommended`. Cache em memória de 10 min (`_CAT_CACHE`, TTL 600 s) com `force=True` para o botão de atualização; nenhum arquivo novo de segredos. Endpoints em `main.py`: `GET /api/ai/openrouter/free-models?force=`, `GET /api/ai/groq/models?force=`, `POST /api/ai/test-dry` (`/api/ai/test` mantido p/ retrocompatibilidade). O navegador nunca chama OpenRouter/Groq diretamente e nunca recebe a chave.

- [x] 3. Implementar UI: Gemini com opções decididas; OpenRouter e Groq com selects dinâmicos, atualização, carregamento/erro e modelo manual opcional; preservar os outros provedores.
  - Registro: `static/index.html` (modal `#aiCfgModal` + JS) — para `openrouter`/`groq` o input de modelo dá lugar a **select dinâmico** (`#aiModelSel`) com botão `↻ Atualizar modelos` (`?force=true`), estado de carregamento (`⏳ atualizando modelos…`), contagem e erro claro (`#aiCatState` + `#aiNotice`) SEM trocar a seleção salva; OpenRouter exibe `openrouter/free` como "Automático — melhor modelo gratuito disponível" (não força troca se já há ID específico salvo); Groq mostra o recomendado primeiro (`qwen/qwen3.8-27b — recomendado`) e, se o modelo salvo não estiver no catálogo, mantém o ID salvo em "Modelo manual…" com aviso explícito (sem substituição silenciosa); todo provedor com catálogo tem `Modelo manual…` para digitar ID (ex.: modelo pago) — nunca escolhido automaticamente; Base URL manual oculta/desabilitada para OpenRouter/Groq (base fixa) e só aparece para `compat`; z.ai/OpenAI/compat idênticos; hints deixam claro que Groq tem quota sujeita a limites e Gemini tem limites da camada gratuita (nada de "ilimitado").

- [x] 4. Corrigir Gemini: migrar 2.0 desligado para 2.5 Flash e oferecer as opções gratuitas oficiais no modal.
  - Registro: default do sistema agora é `gemini-2.5-flash`; `_migrate()` (chamada em `load_config()`) converte `gemini-2.0-flash` e `gemini-2.0-flash-lite` → `gemini-2.5-flash` antes de qualquer teste/chamada (em memória; `save_config` persiste quando o usuário salva) e gera aviso curto exibido no modal (`#aiNotice`: "modelo anterior foi aposentado pelo Google e foi atualizado"). Seletor Gemini recebe as 3 opções oficiais decididas (2.5 Flash recomendado / 2.5 Flash-lite econômico / 2.5 Pro opcional, não-selecionado automaticamente) via `choices` no `public_config` — sem preview desligado, sem modelo de imagem/áudio, hint deixa claro que a camada gratuita tem limites.

- [x] 5. Inverter o fluxo do modal: testar com valores não salvos primeiro; salvar somente após sucesso. Implementar teste efêmero no backend sem persistir chave/configuração.
  - Registro: backend — `test_config_dry(patch)` em `ai_llm.py` mescla o patch na config EM MEMÓRIA (mesmas regras do save: chave vazia preserva a salva) e chama `test_provider`; NÃO grava `ai_config.json`, NÃO altera o provedor ativo e NÃO substitui chave salva (para z.ai, não escreve o arquivo do gateway — o teste usa o gateway instalado e a resposta traz `note` explicando que a nova chave entra ao salvar). Frontend — botão principal **🔌 Testar conexão** envia os valores digitados a `POST /api/ai/test-dry` (mostra `label` do provedor — ex. `OpenRouter — modelos gratuitos` — e o ID efetivo selecionado); falha mostra o motivo e NÃO salva nada; **Salvar configuração** é o passo seguinte. Validado por bytes do arquivo: test-dry não altera `ai_config.json` nem o provedor ativo.

- [x] 6. Fazer uma única validação final: sem chave, com chave já salva (sem expô-la), catálogo OpenRouter filtrado, catálogo Groq, teste de uma seleção não salva e salvamento posterior. Confirmar que z.ai/Gemini/OpenAI/compat ainda carregam no modal e que configuração Gemini 2.0 é migrada para 2.5 Flash.
  - Registro: validação única in-process (`py -3.10` + `node --check`), 24/24 checks OK: matriz decidida (bases/labels/defaults, incluindo Groq `qwen/qwen3.8-27b`); migrações 2.0-flash e 2.0-flash-lite → 2.5-flash com aviso (2.5-pro intocado); config pública sem NENHUMA chave em claro (1 chave salva existente conferida por substring — nunca impressa) com `has_key`/`masked`; filtro OpenRouter aceita só preço zero/texto (rejeitou pago, saída de imagem, preço não numérico; dedupe + ordem) com campos públicos; Groq com recomendado primeiro/inativos fora/dedupe; cache (2ª chamada sem refetch + `force` refetch); sem chave → erro claro sem fallback silencioso; test-dry usa os valores digitados e NÃO persistiu nada (bytes do arquivo idênticos, provedor ativo inalterado, chave vazia preserva a salva); rotas `/api/ai/openrouter/free-models` e `/api/ai/groq/models` respondem ok; 6 provedores no modal; `node --check` do JS limpo; modal usa `/api/ai/test-dry` antes de salvar. Chamadas REAIS aos provedores ficam pendentes de chave do usuário (não existem chaves OpenRouter/Groq salvas; o fluxo de erro sem chave foi o validado — nenhuma credencial foi inventada).

- [x] 7. Preencher resumo final e parar.
  - Registro: feito no bloco "Resumo final do executor" abaixo.

## Critérios de aceite

- OpenRouter aparece como opção própria no front.
- A chave é salva apenas no backend/local e reaparece exclusivamente mascarada.
- A lista é obtida no servidor e contém somente preços zero conforme resposta oficial atual.
- Um modelo é selecionável e salvo por ID; há atualização manual da lista.
- Nenhuma chave aparece em HTML, resposta pública, console, log ou documentação.
- Os quatro provedores existentes continuam funcionais.

## Resumo final do executor

- Arquivos alterados: `mini-services/led-cad/services/ai_llm.py` (provedores `openrouter` e `groq` em `PROVIDERS` com bases fixas; Gemini padrão `gemini-2.5-flash` + `_migrate()` com aviso; `_http_get_json`, `_filter_openrouter`, `openrouter_free_models`, `_normalize_groq`, `groq_models` com cache de 10 min; `test_config_dry` efêmero; `public_config` com `notice`); `mini-services/led-cad/main.py` (endpoints `POST /api/ai/test-dry`, `GET /api/ai/openrouter/free-models?force=`, `GET /api/ai/groq/models?force=`); `mini-services/led-cad/static/index.html` (modal: select de modelos com atualização/carregamento/erro, `Modelo manual…`, `openrouter/free` automático, opções Gemini 2.5, fluxo Testar→Salvar via test-dry, avisos de quota/limites). CAD, PDF, presets, IA prompts, geometria, operações e exportação intocados; sem novo frontend/gateway/banco.
- Endpoint e regra de filtragem: `GET /api/ai/openrouter/free-models` (backend chama `https://openrouter.ai/api/v1/models` com a chave salva; mantém SOMENTE modelos de chat/texto com `pricing.prompt`, `pricing.completion` e `pricing.request` numéricos e `= 0`; devolve apenas `id/name/context_length/modality/pricing`; dedupe por `id`; ordem estável por nome) e `GET /api/ai/groq/models` (backend chama `https://api.groq.com/openai/v1/models`; só ativos, campos públicos, recomendado `qwen/qwen3.8-27b` primeiro).
- Cache implementado: `_CAT_CACHE` em memória por processo, TTL 600 s (10 min), com `force=True` no botão de atualização; nada gravado em arquivos além do `data/ai_config.json` já existente.
- Comportamento da UI: OpenRouter com select de gratuitos + `openrouter/free` (Automático) + `Modelo manual…`; Groq com select de ativos (recomendado primeiro) + manual; estado de carregamento/erro sem trocar a seleção salva; Base URL oculta (fixa) para ambos; chave com máscara/`has_key`; aviso explícito quando o modelo salvo não está no catálogo; hints de quota/limites (nada de "ilimitado").
- Migração e opções Gemini: `gemini-2.0-flash`/`gemini-2.0-flash-lite` → `gemini-2.5-flash` automaticamente antes de testar/chamar, com aviso no modal; opções oficiais 2.5 Flash (recomendado), 2.5 Flash-lite (econômico) e 2.5 Pro (opcional).
- Fluxo testar antes de salvar: `POST /api/ai/test-dry` testa os valores digitados em memória (chave vazia preserva a salva; z.ai usa o gateway instalado com `note`); nada é gravado nem o provedor ativo alterado; salvar só depois de teste bem-sucedido, com motivo visível em caso de falha.
- Validação final: 24/24 checks (matriz decidida, migrações, mascaramento sem vazamento — chave real existente conferida por substring sem ser impressa, filtros de preço zero/modality, cache+force, erro sem chave, test-dry sem persistir, rotas, 6 provedores no modal, `node --check` do JS, wiring testar→salvar). Chamadas reais aos provedores dependem de chave do usuário (nenhuma inventada).
- Garantias de segredo: chaves só em `data/ai_config.json` (e gateway z.ai como já existia); API pública devolve só `masked`/`has_key`; navegador nunca chama OpenRouter/Groq nem recebe a chave; Authorization nunca logado; erros expõem apenas corpo público curto do provedor; nenhuma chave em HTML/console/log/documentação.
- Pendências reais: teste E2E com chaves OpenRouter/Groq reais do usuário (inserir via modal ⚙ → Testar → Salvar); nenhum bloqueio de código conhecido.
