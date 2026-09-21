# Tarefa Z.ai — substituir catálogo automático por conectores universais manuais

## Modo de execução

Leia e siga `ZAI_MODO_EDICAO_DIRETA.md`. Execute somente esta mudança na versão canônica `mini-services/led-cad`; não rode testes, build, servidor, navegador, catálogo online ou validação automática. Ao terminar, marque o roadmap e pare.

## Decisão de produto fechada

Desfazer a arquitetura de provedores especiais e catálogos automáticos (OpenRouter, Groq e Gemini). Ela acrescentou erro, complexidade e gasto sem trazer valor.

A configuração de IA passa a ser um **modo universal manual**, para APIs compatíveis com OpenAI. O usuário mesmo informa e guarda vários conectores. O programa não pesquisa modelos, não impõe lista de gratuitos, não escolhe modelo e não usa atualização de catálogo.

## Resultado visual obrigatório

No modal ⚙ Conector de IA, substituir a interface atual por:

1. Área `Conexões salvas` no topo: lista simples de cartões/botões com o **nome** de cada conexão. Um clique carrega a conexão no formulário e a torna ativa para o copiloto.
2. Botão `+ Nova conexão` que limpa o formulário sem apagar conexões existentes.
3. Formulário universal com exatamente estes campos:
   - `Nome da conexão` — exemplo: `Groq Qwen`, `OpenRouter Free`, `Gemini Flash`.
   - `URL base da API` — exemplo: `https://api.groq.com/openai/v1`.
   - `Chave de API` — vazia significa manter a chave já salva ao editar uma conexão existente.
   - `Modelo` — texto livre, exemplo: `qwen/qwen3.8-27b`.
4. Botões nesta ordem: `Testar conexão` e `Salvar conexão`.
5. Botão `Excluir conexão` apenas para conexão salva, com confirmação explícita. Nunca apagar a conexão selecionada sem confirmação.
6. Texto curto abaixo: “API compatível com OpenAI. Informe URL base e modelo fornecidos pelo provedor.”

Não exibir: provider fixo, Base URL condicionada, lista de modelos, “Atualizar modelos”, catálogo, cache, OpenRouter/Groq/Gemini predefinidos, modelos recomendados, `openrouter/free`, migração de modelo ou promessa de gratuidade.

## Comportamento obrigatório

1. **Teste antes de salvar:** `Testar conexão` deve usar os quatro valores preenchidos no formulário somente em memória e fazer um `chat/completions` mínimo. Não salvar arquivo, não alterar conexão ativa e não trocar chave existente.
2. **Salvar depois:** `Salvar conexão` cria ou atualiza uma conexão manual após o usuário decidir salvar. Salvar também a torna a conexão ativa.
3. **Múltiplas conexões:** permitir criar e manter várias conexões com IDs estáveis. A conexão ativa persiste entre recargas e é a única usada pelo copiloto até o usuário selecionar outra.
4. **Segurança:** chave fica somente no backend local. Resposta pública devolve `has_key` e chave mascarada para cada conexão, nunca chave inteira. Não gravar/mostrar chave em console, toast, log, histórico ou HTML.
5. **Chamada de IA:** todas as conexões usam `POST {base_url}/chat/completions` com Bearer token, `model`, `messages` e o formato atual do copiloto. Não criar SDK, gateway, adaptador por provedor ou fallback automático.
6. **Erros:** mostrar o erro devolvido pelo provedor de forma curta. Não trocar conexão, modelo ou URL automaticamente.

## Copiloto: seletor e resposta visível

Também corrigir o painel do Copiloto IA no front, sem criar outra tela:

1. Logo abaixo dos botões de ação do Copiloto, inserir uma faixa compacta `IA ativa` com os nomes das conexões salvas.
   - A conexão ativa deve ficar visualmente marcada.
   - Um clique em outra conexão salva deve ativá-la imediatamente para o próximo pedido e persistir essa escolha.
   - Não mostrar URL completa, chave, máscara de chave ou detalhes técnicos nessa faixa.
   - O botão ⚙ continua sendo apenas para criar/editar/excluir conexões.

2. Toda chamada do Copiloto deve terminar em um estado visível, nunca apenas “pensando”:
   - enquanto aguarda: `Enviando para <nome da IA>…`;
   - sucesso: nome da IA/modelo e resposta/plano recebido;
   - limite/quota: mensagem curta `Limite do provedor atingido` com código HTTP e `retry_after` quando o provedor o informar;
   - erro de chave/permissão: `Chave ou permissão recusada pelo provedor`;
   - falha de rede/timeout: mensagem correspondente;
   - resposta inválida da IA: explicar que o plano foi recusado pelo CAD e mostrar o motivo curto.
   Sempre desligar loading/botões no `finally`, inclusive quando houver erro.

3. Não esconder a resposta textual da IA. Quando ela devolver um plano válido, manter a prévia e o resumo; quando não devolver operação válida, manter a mensagem no chat e preservar o desenho anterior.

## Correção geral de geração/preview de estrutura

O erro mostrado pelo usuário (`Element role`: recebeu `guarda corpo`, mas o schema aceita apenas `vertical`, `horizontal`, `trave`, `diagonal`, `post`, `plate`, `base`, `bolt`, `panel`, `other`) não pode mais bloquear a geração.

1. No ponto central que normaliza operações da IA antes de validar/aplicar (`core/ai_ops.py` ou o único ponto equivalente), normalizar **qualquer** papel semântico não-canônico para um papel canônico, sem depender de um caso de projeto específico.
2. Regra geral:
   - manter papéis já válidos;
   - reconhecer sinônimos de poste/base/chapa/painel;
   - para descrições funcionais que não são papéis geométricos — `guarda corpo`, `corrimão`, `suporte`, `reforço`, etc. — preservar a descrição em `group`/label e deduzir o papel geométrico pela direção real `start/end`: predominantemente Z = `vertical`; predominantemente X/Y = `horizontal` ou `trave`; eixos mistos = `diagonal`; sem geometria = `other`.
3. Nunca deixar texto livre chegar ao campo Pydantic `role`.
4. Corrigir o preview e a aplicação para que um plano normalizado apareça como desenho de estrutura consistente, não painel deformado ou erro genérico. O desenho anterior só é preservado quando a resposta for realmente impossível de normalizar.
5. Esta é uma proteção geral da ferramenta, não uma regra especial para guarda-corpo, painel 2×1 ou um preset.

## Simplificação obrigatória do código

1. Remover da execução e da UI tudo que foi adicionado para catálogo automático: endpoints de catálogo OpenRouter/Groq, cache de catálogos, filtros, botões/estado de atualização e seleção dinâmica de modelos.
2. Remover enum/dicionário de provedores especiais e lógica de Gemini/OpenRouter/Groq/z.ai/compat como caminhos distintos.
3. Manter uma única implementação genérica de conexão OpenAI-compatível.
4. Substituir a configuração em `data/ai_config.json` por uma estrutura simples, por exemplo:

```json
{
  "active_connection_id": "conn_xxx",
  "connections": [
    {
      "id": "conn_xxx",
      "name": "Groq Qwen",
      "base_url": "https://api.groq.com/openai/v1",
      "model": "qwen/qwen3.8-27b",
      "api_key": "<somente no backend>"
    }
  ]
}
```

5. Não apagar as chaves/configuração legadas existentes durante a migração. Elas podem permanecer no arquivo como dados não usados até o usuário recriar manualmente as conexões; não as copie para respostas públicas nem as exponha.

## Arquivos permitidos

- `mini-services/led-cad/services/ai_llm.py`
- `mini-services/led-cad/main.py`
- `mini-services/led-cad/static/index.html`
- `mini-services/led-cad/core/ai_ops.py`

Não alterar nenhum outro arquivo do programa.

## Roadmap

- [x] 1. Substituir backend de provedores/catálogos por conexões manuais múltiplas e uma chamada OpenAI-compatível única.
  - Registro: `services/ai_llm.py` reescrito como modo universal manual — config nova em `data/ai_config.json`: `{"active_connection_id", "connections":[{id, name, base_url, model, api_key}]}` (IDs estáveis `conn_<hex>`; chaves/config legadas que existam no arquivo são PRESERVADAS em disco como dados não usados, nunca expostas). Funções: `load_config`, `public_config` (só `id/name/base_url/model/has_key/masked` — nunca a chave), `save_connection` (cria/atualiza e torna ativa; `api_key` vazio preserva a salva), `delete_connection`, `activate_connection`, `_active_conn`, `test_connection` (efêmero), `test_provider` (ativa) e `chat_completion(messages, cfg)` — assinatura mantida para `main.ai_command`/`ai_plan`. Chamada ÚNICA: `POST {base_url}/chat/completions` com Bearer/model/messages (sem SDK, gateway, adaptador ou fallback). `AiError` ganhou `status`/`retry_after`; User-Agent `LED-Structure-CAD/1.0` e tratamento 403/1010 preservados. `main.py`: `AiConnIn`/`AiConnIdIn` substituem `AiConfigIn`; `POST /api/ai/config` salva+ativa, novos `POST /api/ai/config/activate` e `/delete`; `/api/ai/test-dry` usa `test_connection`; `/api/ai/test` testa a ativa; erros devolvem `error/status/retry_after`; `ai_command`/`ai_plan` incluem `ai_status`/`ai_retry_after` nas falhas de provedor (estados do Copiloto).

- [x] 2. Substituir o modal pelo formulário manual + lista de conexões + fluxo testar antes de salvar.
  - Registro: `static/index.html` — modal ⚙ refeito: área `Conexões salvas` (cartões com o nome; clique carrega no formulário E ativa), `+ Nova conexão` (limpa o formulário sem apagar nada), formulário universal com exatamente `Nome da conexão`, `URL base da API`, `Chave de API` (vazia = manter a salva, exibindo máscara) e `Modelo` (texto livre), botões na ordem `Testar conexão` → `Salvar conexão` (+ `Excluir conexão` só para conexão carregada, com `confirm()` explícito) e o texto "API compatível com OpenAI. Informe URL base e modelo fornecidos pelo provedor.". `Testar` usa `POST /api/ai/test-dry` (só memória); `Salvar` usa `POST /api/ai/config` e torna a conexão ativa. Nada de provider fixo, lista de modelos, catálogo, cache, recomendados, `openrouter/free` ou promessa de gratuidade.

- [x] 3. Adicionar seletor compacto de conexão ativa e estados claros de resposta/limite/erro no Copiloto.
  - Registro: faixa `IA ativa` (`#aiConnStrip`) logo abaixo da linha de ação do Copiloto: chips com o NOME de cada conexão salva, ativa marcada (borda/preenchimento + ●); clique ativa imediatamente (`POST /api/ai/config/activate`, persistente) com toast `IA ativa: <nome>`; nada de URL/chave/máscara na faixa; atualiza no boot (`refreshActiveAI()`), após salvar/ativar/excluir. `sendAi` mostra "Enviando para <nome>…" e mapeia estados: 429 → "⏳ Limite do provedor atingido (HTTP 429) — tente novamente em Xs", 402 → créditos/quota, 401/403 → chave/permissão recusada; `applyPlan` confirma com toast `Conexão ativa: <nome>`, avisa "⚠ Plano aplicado com resalvas — confira o desenho." quando o plano altera painel existente e, em recusa do CAD, "O desenho recusou a proposta (elemento inválido). Revise o pedido." — sem trocar conexão/modelo/URL automaticamente.

- [x] 4. Normalizar papéis semânticos inválidos da IA antes da validação e preservar preview/desenho anterior em falhas reais.
  - Registro: `core/ai_ops.py` — `normalize_op()` (ponto único por onde TODO plano passa: `dry_run_diff` e `apply_batch`) chama `_norm_role()`: `ROLE_CANON` (válidos passam intactos), `ROLE_SYNONYMS` (poste/pilar/coluna→post; chapa→plate; base/fundação→base; chumbador/pino→bolt; painel→panel; travessa/viga→trave; diagonal/escora→diagonal…) e `_deduce_role_by_direction()` para descrições funcionais (`guarda corpo`, `corrimão`, `suporte`, `reforço`…): preserva a descrição em `group` e deduz pela direção real start/end — Z predominante = `vertical`; X = `horizontal`; Y = `trave`; eixos mistos (≥50% em outro eixo) = `diagonal`; sem geometria = `other`. Aceita também `element_role`. Nenhum texto livre chega ao campo Pydantic `role` — o erro `Element role: 'guarda corpo'` não bloqueia mais a geração; em falha real de normalização o desenho anterior é preservado (all-or-nothing já existente em `apply_batch`).

- [x] 5. Remover fluxo de catálogo automático e marcar concluído. Não testar nem executar nada.
  - Registro: removidos de `services/ai_llm.py`: `PROVIDERS`, constantes Gemini/Groq, `_defaults`, `_migrate`/`_LAST_NOTICE`, `save_config`, `_gateway_key`/`GATEWAY_*`/rota z.ai, `_resolve`, `_CAT_CACHE`/`_http_get_json`/`_saved_key`/`_filter_openrouter`/`openrouter_free_models`/`_normalize_groq`/`groq_models`/`test_config_dry`. Removidos de `main.py`: endpoints `GET /api/ai/openrouter/free-models` e `GET /api/ai/groq/models`. Removidos de `index.html`: select de provedor, Base URL condicionada, select/`Atualizar modelos`/estados de catálogo e toda a lógica JS associada (`AI_CAT`, `GEMINI_FALLBACK`, `aiFillModelSelect`, `aiSyncProvUI`, `aiRefreshCatalog`, `aiEffectiveModel`…). Conforme o modo de edição direta: NADA foi executado/testado; inspeção estática confirmou ausência de referências órfãs aos nomes removidos nos quatro arquivos.

## Resumo final

- Arquivos alterados: `mini-services/led-cad/services/ai_llm.py` (reescrito: conexões manuais universais, chamada OpenAI-compatível única), `mini-services/led-cad/main.py` (endpoints de conexões + estados de erro), `mini-services/led-cad/static/index.html` (modal universal + faixa IA ativa + estados do Copiloto), `mini-services/led-cad/core/ai_ops.py` (normalização geral de papéis).
- Estrutura da configuração manual: `data/ai_config.json` → `{"active_connection_id": "conn_xxx", "connections": [{"id","name","base_url","model","api_key"}]}`; chaves/config legadas permanecem no arquivo como dados não usados (não apagadas, não expostas em respostas públicas).
- Fluxo testar/salvar: `Testar conexão` → `POST /api/ai/test-dry` (quatro valores do formulário, só memória, `chat/completions` mínimo); `Salvar conexão` → `POST /api/ai/config` (cria/atualiza e torna ativa; api_key vazio preserva a salva); `Excluir conexão` só em conexão carregada, com confirmação explícita.
- Seletor e estados do Copiloto: faixa `IA ativa` com chips das conexões (nome apenas), ativa marcada, clique ativa e persiste; "Enviando para <nome>…"; 429/402/401/403 com mensagens curtas e `retry_after` quando informado; `applyPlan` com toast `Conexão ativa`, resalvas de painel e recusa do CAD com mensagem curta.
- Normalização geral de operações IA: `_norm_role` em `normalize_op` — canônicos intactos, sinônimos mapeados, funcionais preservados em `group` com papel deduzido pela direção start/end (Z→vertical, X→horizontal, Y→trave, mistos→diagonal, sem geometria→other).
- O que foi removido: provedores especiais e catálogos automáticos (OpenRouter/Groq/Gemini/z.ai/compat como caminhos distintos), endpoints de catálogo, cache, filtros, botões/estado de atualização e seleção dinâmica de modelos (backend + UI).
- Pendências reais: conferência visual/funcional pelo usuário (nada foi executado, conforme o modo de edição direta).
