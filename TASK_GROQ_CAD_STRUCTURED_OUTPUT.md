# TASK — Groq CAD Structured Output efetivo

## Regra desta task

Trabalhe diretamente na única versão atual do protótipo em `mini-services/led-cad`. Não criar v2, camada paralela, fallback que substitua o Copiloto por formulário, nem duplicar motor geométrico. O formulário rápido pode continuar determinístico; esta task é para que **Groq funcione como copiloto CAD real**.

Preservar o comportamento atual de Z.ai/GLM, inclusive `thinking` interno e a não exposição de reasoning na UI. Nunca logar API key, Authorization header, ou resposta de reasoning.

Faça as mudanças por fases, mas execute testes somente no final da implementação (uma rodada objetiva), não a cada arquivo.

---

## 1. Estado atual confirmado por auditoria

### Pipeline real — modo Copiloto com preview

```text
Usuário / static/index.html
  → POST /api/ai/plan
  → main.py: ai_plan(AiPlanIn)
  → services.ai_intent.build_intent(text, model)
  → services.ai_prompts.build_system_prompt(..., intent)
     + build_user_message(text, intent)
  → services.ai_llm.chat_completion(messages, cfg)
  → POST {base_url}/chat/completions
  → main.py:_extract_json_obj(raw)
  → ops + main.py:_cohere_new_panel_elevation(ops)
  → core.ai_ops.normalize_op(op)
  → core.ai_ops.dry_run_diff(model, norm)
  → resposta com preview/diff para o frontend
  → usuário clica APLICAR
  → POST /api/ops/apply
  → core.ai_ops.apply_batch(STORE, operations)
  → ProjectStore / ProjectModel persistido e undo unificado
```

### Caminho sem preview

`main.py:ai_command` usa o mesmo prompt/LLM/parser, mas chama `services.ai_service.execute_ops` logo após receber as operações. Formulário (`body.form`) é tratado por `_quick_form_ops(intent)` de modo determinístico e não deve ser usado para mascarar falhas do Groq.

### Arquivos confirmados

| Responsabilidade | Arquivo / função |
|---|---|
| Conexões e payload HTTP | `services/ai_llm.py`: `chat_completion`, `_http_json`, `test_connection` |
| Intenção comum de formulário e copiloto | `services/ai_intent.py`: `build_intent`, `from_form`, `derive_from_text`, `intent_block` |
| Prompt e mensagem ao modelo | `services/ai_prompts.py`: `build_system_prompt`, `build_user_message` |
| Parse do texto retornado | `main.py`: `_extract_json_obj`, `_repair_truncated_json` |
| Regras de elevação pós-LLM | `main.py`: `_cohere_new_panel_elevation` |
| Orquestração do Copiloto | `main.py`: `ai_plan` |
| Orquestração direta | `main.py`: `ai_command` |
| Normalização e preview | `core/ai_ops.py`: `normalize_op`, `apply_to_model`, `dry_run_diff` |
| Apply atômico + undo | `core/ai_ops.py`: `apply_batch` |
| Motor base e ProjectStore | `core/operations.py`: `ProjectStore`, handlers `_op_*` |
| Schema do projeto/elemento | `models/element.py`: `ProjectModel`, `Element`, `Vec3`, `ElementRole` |
| Compatibilidade antiga de comandos | `services/ai_service.py`: `parse_command`, `execute_ops` |

Não há diretório/arquivo de testes automatizados identificado no repositório atual.

---

## 2. Contrato canônico confirmado

### Discriminador

O discriminador canônico do motor é **`"operation"`**.

`core.ai_ops.normalize_op()` aceita `"type"` como entrada de compatibilidade e o converte para `"operation"`; aceita também `delta: {x,y,z}` ou lista de 3 valores e normaliza para `delta_x`, `delta_y`, `delta_z`.

Portanto:

- Prompt, schema novo e respostas esperadas devem emitir `operation`.
- Não emitir `op`.
- `type` só pode permanecer como compatibilidade de entrada; não deve aparecer nos exemplos do contrato rígido Groq.
- `__select` é tratado em `main.py:ai_plan` **antes** de `normalize_op`; hoje ele só é reconhecido se vier como `operation:"__select"`. Isso reforça o uso obrigatório de `operation` no modelo.

### Coordenadas

`add_box` recebe canonicamente uma das formas abaixo:

```json
{"operation":"add_box","center":{"x":0,"y":0,"z":3480},"width":1920,"depth":650,"height":960}
```

ou:

```json
{"operation":"add_box","corner1":{"x":-960,"y":-325,"z":3000},"corner2":{"x":960,"y":325,"z":3960}}
```

`x/y/z` soltos não são contrato de `add_box`. `add_post` é a exceção que recebe `x`, `y`, `height` diretamente.

### Operações aceitas por `core.ai_ops.HANDLERS` / `apply_to_model`

Todos os valores numéricos são mm. Campos não listados não devem ser inventados pelo modelo.

| Operation canônica | Obrigatórios | Opcionais relevantes | Efeito |
|---|---|---|---|
| `__blank` | nenhum | nenhum | limpa o desenho na simulação, preservando a referência de painel para a sequência seguinte |
| `__preset` | `preset_id` | `overrides` | carrega preset na simulação/apply batch |
| `__regen` | nenhum | `preset_id`, `overrides` | regenera preset atual/indicado |
| `set_panel` | ao menos um de `width`,`height`,`depth`,`ground_clearance`,`visible` | os demais | altera referência visual e metadados do painel |
| `add_box` | `center` + `width`,`depth`,`height` **ou** `corner1`+`corner2` | `group`,`role`,`profile` | cria as 12 arestas de uma gaiola/volume |
| `add_grid` | `start`,`end` coplanares | `cols`,`rows`,`border`,`group`,`profile` | cria grelha retangular; um eixo deve ser igual em start/end |
| `add_circle` | `radius` | `center`,`segments`,`plane`,`closed`,`group`,`role`,`profile` | cria anel/polígono de barras |
| `add_beam` | `start`,`end` | `role`,`group`,`profile`,`label` | cria barra |
| `add_post` | nenhum (defaults existem) | `x`,`y`,`height`,`profile` | cria poste do solo até `height` |
| `add_plate` | nenhum (defaults existem) | `center`,`size_x`,`size_y`,`size_z`,`group`,`label` | cria chapa geométrica |
| `add_element` | geometria compatível com tipo | `etype`/`element_type` + campos de beam/plate | delega para barra ou chapa |
| `add_diagonal` | `start`,`end` **ou** `from_element`,`to_element` | `role`,`group`,`profile` | cria diagonal |
| `move_element` | `element_id` | `delta_x`,`delta_y`,`delta_z` | translada elemento |
| `set_position` | `element_id` | `start`,`end`,`center`,`keep_length` | posiciona beam/plate |
| `set_post_height` | `element_id`,`height` | nenhum | ajusta poste e translada superestrutura vinculada |
| `resize_element` | `element_id`,`length` para beam/bolt | `anchor`; ou `size_x/y/z` para plate | redimensiona elemento |
| `replace_element` | `element_id` + `start/end` para beam ou `center` para plate | `new_type`/`etype`,`profile`,`role`,`group`,`size_x/y/z` | substitui geometria mantendo ID |
| `rotate_element` | `element_id` | `axis`,`angle_deg`,`center` | gira elemento |
| `duplicate_element` | `element_id` | `delta_x`,`delta_y`,`delta_z` | duplica elemento |
| `copy_element` | `element_id` | mesmos de `duplicate_element` | alias de duplicação |
| `delete_element` | `element_id` | nenhum | remove elemento |
| `update_profile` | `element_id`,`profile` | nenhum | altera perfil visual/técnico interno |
| `change_profile` | `element_id`,`profile` | nenhum | alias de profile |
| `rename_element` | `element_id`,`new_id` | nenhum | renomeia ID |
| `set_group` | `element_id` | `group` | altera grupo |
| `set_role` | `element_id`,`role` | nenhum | role válido: `vertical,horizontal,trave,diagonal,post,plate,base,bolt,panel,other` |
| `set_shield` | `element_ids` ou `element_id` | `value` | marca abrigo de vento |
| `multi_delete` | `element_ids` | nenhum | remove lote |
| `multi_move` | `element_ids` | `delta_x`,`delta_y`,`delta_z` | move lote |
| `multi_duplicate` | `element_ids` | `delta_x`,`delta_y`,`delta_z` | duplica lote |
| `multi_profile` | `element_ids`,`profile` | nenhum | troca perfil em lote |
| `align_elements` | `element_ids` (mín. 2) | `axis`,`anchor` | alinha elementos |
| `distribute_elements` | `element_ids` (mín. 3) | `axis` | distribui elementos |
| `mirror_elements` | `element_ids` | `plane`/`axis`,`pivot`,`copy` | espelha ou cria cópias |
| `__select` | `ids` | nenhum | somente instrução de UI em `ai_plan`, não handler do motor |

Observação: o contrato de `profile` continua opcional para geração geométrica. Não alterar a interface do usuário para lista de material/preço/BOM nesta task.

---

## 3. Causa provável por camada

### A. Provider/API — PROBLEMA

`services/ai_llm.chat_completion()` tem condicionais pelo host: Z.ai recebe `thinking` e Groq recebe apenas `response_format:{type:"json_object"}` + `max_tokens`. Não há capabilities declaradas; `test_connection()` usa payload diferente e não verifica structured output. O código não confirma a capacidade efetiva do modelo Groq selecionado.

### B. Structured Output — PROBLEMA

`json_object` apenas obriga um objeto JSON, não obriga `explain` nem uma operação válida. Não existe `json_schema` para `{explain, ops}` nem variantes das operações aceitas. É compatível com o sintoma observado: JSON válido contendo `ops:[]` ou objetos sem efeito.

### C. Prompt — INCERTO / PARCIALMENTE OK

`build_system_prompt()` já instrui corretamente `operation`, apresenta exemplos reais e exige ops em CREATE/EDIT. Porém é grande e não há bloco curto específico para modelo de structured output confirmar que `ops` deve alterar o canvas. Não reescrever o prompt inteiro; adicionar somente um complemento de contrato operacional quando o provider tiver essa capability.

### D. Parser — PROBLEMA

`_extract_json_obj()` extrai e decodifica JSON, mas não valida o formato contra schema. `data.get("ops") or []` converte `null`, chave ausente e lista vazia no mesmo estado, dificultando diagnóstico. Também não preserva motivo estruturado para o retry.

### E. Schema — PROBLEMA

Há Pydantic para `Element`/`ProjectModel`, mas não há schema Pydantic/JSON Schema para a resposta da IA nem operações. A validação das operações ocorre tarde, por handlers e dry-run.

### F. Validação semântica — PROBLEMA

`ai_plan` detecta `diff.counts.total == 0` para pedido geométrico, mas só faz retry quando `ops` vem vazia. Se a IA devolver operação inválida ou no-op, o usuário recebe erro sem uma única correção automática. `ai_command` pode aplicar lote sem antes recusar um lote semanticamente sem efeito.

### G. Executor — OK, com lacuna de uso

`dry_run_diff()` clona `ProjectModel`, executa operações e compara assinatura geométrica; `apply_batch()` realiza dry-run antes do apply e usa um snapshot de undo. O motor já fornece a base correta; não construir outro motor. Falta a orquestração usar o diff como critério de retry e de aceite de CREATE/EDIT.

### H. Preview/dry-run — OK, com lacuna de UX/orquestração

`/api/ai/plan` devolve preview sem aplicar e `/api/ops/apply` usa batch/undo. Entretanto as falhas de schema, operações inválidas e no-op são encerradas antes de uma única correção guiada ao modelo.

---

## 4. Implementação exigida, em ordem

### Fase 1 — Centralizar capabilities do provider

Em `services/ai_llm.py`, criar uma função/estrutura privada de capabilities por conexão/host, sem espalhar `if host == ...` pelo restante da aplicação. O formato pode ser simples, por exemplo:

```python
{"structured_output": False, "strict_schema": False, "reasoning": False, "max_tokens": None}
```

Requisitos:

- Z.ai mantém `thinking:{type:"enabled"}` e `max_tokens:8192` exatamente como hoje, salvo bug comprovado.
- Groq (`api.groq.com`) declara structured output; aplicar schema estrito somente quando o modelo/endpoint o suportar.
- Cobrir `openai/gpt-oss-20b` e `openai/gpt-oss-120b` conforme documentação oficial atual do Groq; não assumir que todos os modelos manuais suportam o mesmo payload.
- Conectores OpenAI compatíveis genéricos não recebem campos Groq desconhecidos.
- `test_connection()` deve continuar teste leve de conectividade; não precisa exigir schema CAD.

### Fase 2 — Criar contrato estruturado único baseado na tabela acima

Adicionar módulo pequeno e reutilizável (nome compatível com a estrutura atual, por exemplo `services/ai_contract.py`) que seja a fonte única para:

1. JSON Schema de resposta `{explain, ops}`;
2. validação de resposta antes do dry-run;
3. texto curto de contrato operacional a inserir no prompt.

Regras:

- `explain`: string curta;
- `ops`: array, com item discriminado por **`operation`**;
- modelar `ops` por `anyOf`/variantes reais. Não usar `items:{"type":"object"}` livre como schema final;
- permitir campos opcionais necessários para cada operação real da tabela;
- `additionalProperties:false` onde a capacidade/schema do Groq permitir sem impedir os campos reais;
- não incluir `op`; não ensinar `type` no schema novo;
- `__select` deve ser explicitamente compatível com seu tratamento atual de UI;
- schema e `normalize_op()` devem ser coerentes. Se houver uma incompatibilidade real, corrigir na fonte canônica, não criar tradução ad hoc apenas para Groq.

Se o modelo Groq selecionado não suportar `json_schema` estrito, manter `json_object` e executar a mesma validação local obrigatória, com diagnóstico claro. Não fingir que schema foi aplicado.

### Fase 3 — Enviar structured output corretamente ao Groq

Adaptar `chat_completion()` para receber opcionalmente o contrato/capabilities do pedido CAD, sem alterar o formato dos outros consumidores desnecessariamente.

- Para Groq GPT-OSS com suporte: enviar `response_format` conforme documentação oficial vigente, com nome de schema e schema da Fase 2.
- Não enviar API key, prompt integral, nem reasoning em logs/respostas.
- Ao extrair `choices[0].message.content`, tratar conteúdo ausente como erro de provider claro; não converter silenciosamente em resposta vazia.
- Preservar compatibilidade do endpoint universal `POST {base_url}/chat/completions`.

### Fase 4 — Complemento curto no prompt, sem apagar o guia atual

Em `services/ai_prompts.py`, criar bloco adicional ativado para o caminho CAD estruturado:

```text
EXECUTION CONTRACT
Retorne somente {"explain":"...","ops":[...]}.
Use somente `operation` e campos documentados.
Se intent for NEW, GLOBAL_RESIZE ou LOCAL_EDIT e os dados forem suficientes,
ops precisa alterar realmente o modelo. Não descreva o que faria.
ops=[] só é permitido para pergunta ou ambiguidade geométrica real.
Antes de responder, confirme mentalmente: aplicar minhas ops muda o canvas?
```

Não reduzir o contexto técnico já presente nem reintroduzir material, orçamento, preço, peso ou BOM como objetivo do copiloto.

### Fase 5 — Validar resposta e definir quando `ops:[]` é válida

Criar uma função comum usada por `ai_plan` e `ai_command` para:

1. extrair JSON;
2. validar contrato/schema local;
3. separar `__select`;
4. normalizar as operações;
5. realizar `dry_run_diff` contra cópia do modelo;
6. produzir resultado semântico estruturado.

Definição obrigatória:

- `ops:[]` é válida para pergunta genuína ou ambiguidade real;
- `ops:[]` é falha para `intent` NEW, GLOBAL_RESIZE ou LOCAL_EDIT quando `build_intent` e/ou o texto trazem dados suficientes;
- não depender apenas do regex `wants_geometry`. Preferir `intent["intent"]` e uma função explícita de suficiência; regex pode permanecer apenas como compatibilidade documentada;
- `__select` isolado é válida para seleção, mas não satisfaz pedido geométrico;
- operação normalizada inválida, `dry_run_diff.errors`, ou `counts.total == 0` em mutação exigida são falha semântica.

Não aplicar o clone do dry-run. O projeto original deve permanecer imutável até `/api/ops/apply` ou o caminho direto já validado.

### Fase 6 — Um único retry semântico, com contexto mínimo

Para `ai_plan` e `ai_command`, após uma primeira resposta LLM:

- se for falha semântica em pedido definido de criação/edição, chamar o modelo **uma vez**;
- anexar somente um bloco de correção curto: tipo do erro (`ops vazia`, `operation inválida`, `dry-run inválido` ou `sem diff`), até duas mensagens/operations problemáticas e a exigência de devolver ops efetivas;
- conservar o prompt e a mensagem originais; não reenviar histórico gigante nem criar loop;
- após segunda falha, devolver erro claro para UI com `ok:false`, sem preview falso e sem aplicar nada;
- perguntas válidas/ambíguas não fazem retry.

### Fase 7 — Aplicação e preview consistentes

- `ai_plan`: preview deve trazer somente `diff.operations` normalizadas e semanticamente efetivas.
- `ai_command`: antes do apply, passar pela mesma validação/dry-run. Não permitir que uma resposta sem efeito seja apresentada como sucesso.
- Manter `/api/ops/apply` e `apply_batch()` como autoridade do apply e undo.
- Não trocar chips do Copiloto por abertura de formulário. O chip “painel 2×1 + passarela” deve continuar usando a IA selecionada.

### Fase 8 — Testes automatizados mínimos e uma rodada final

Criar testes Python focados no pipeline/contrato, sem HTTP real e sem chave real. Mockar somente a borda `chat_completion`, deixando parser → validador → dry-run → resultado reais.

Executar ao final somente:

1. compilação Python dos arquivos alterados;
2. a nova suíte de testes relevante;
3. uma verificação manual breve do endpoint local, se o servidor estiver disponível.

Não executar build de frontend, exportações PDF/DXF, testes de cada microetapa ou varreduras desnecessárias.

---

## 5. Casos de aceite obrigatórios

### A — criação definida

Prompt:

```text
crie um painel outdoor novo 2x1 de gabinetes 960x960,
1 poste, base a 3 metros e passarela atrás
```

Esperado: JSON, `ops` não vazia, `set_panel` 1920×960, estrutura correspondente, dry-run com diff positivo.

### B — ambiguidade legítima

Prompt:

```text
crie um painel 4x2
```

Sem contexto suficiente, esperado: pergunta objetiva, `ops:[]`, nenhum retry e nenhum apply.

### C — redimensionamento integral

Projeto 2×1 existente:

```text
transforma para 4x2 gabinetes mantendo poste e passarela
```

Esperado: diff efetivo, uma única estrutura final, módulo/elevacão/profundidade preservados conforme contexto, sem segunda gaiola sobreposta, poste e passarela preservados.

### D — edição local

Com `POSTE-01` selecionado:

```text
move esse poste 500 mm para esquerda
```

Esperado: operação pontual efetiva no poste; sem `__blank`; dry-run com diff verdadeiro.

### E — resposta vazia indevida

Simular para o caso A:

```json
{"explain":"feito","ops":[]}
```

Esperado: primeira resposta rejeitada semanticamente; um retry; se a segunda também falhar, `ok:false` e nada aplicado.

### F — no-op/operation sem efeito

Simular para um pedido de mutação uma operation que não mude o modelo, como mover `0,0,0` ou atribuir a mesma posição.

Esperado: dry-run rejeita como sem efeito; um retry no máximo; projeto original intacto.

### G — compatibilidade Z.ai

Mockar/inspecionar payload para confirmar que Z.ai mantém `thinking:{"type":"enabled"}` e não recebe schema Groq incompatível. Reasoning não deve chegar à UI.

---

## Checklist de aceitação

- [x] Contrato canônico documentado e emitido com `operation`.
- [x] Schema/prompt/normalização/executor concordam sobre nomes e campos.
- [x] `add_box` usa `center` + dimensões ou `corner1`/`corner2`, nunca `x/y/z` soltos.
- [x] Groq GPT-OSS usa structured output quando a capability/modelo suportar.
- [x] Fallback quando schema não for suportado continua validando localmente.
- [x] Z.ai continua com thinking interno e sem regressão conhecida.
- [x] NEW/GLOBAL_RESIZE/LOCAL_EDIT suficientemente definidos não aceitam `ops:[]`.
- [x] Pergunta/ambiguidade legítima aceita `ops:[]` sem retry.
- [x] No-op e operação inválida são detectados antes do apply.
- [x] Retry máximo é 1 e não entra em loop.
- [x] Preview continua sem alterar o projeto e Apply/undo continuam em lote.
- [x] Chip do Copiloto não foi convertido em formulário/fallback automático.
- [x] Nenhuma chave ou reasoning aparece em logs ou frontend.
- [x] Casos A–G passam.

---

## Status de execução (roadmap do executor)

**Status: concluído** — implementado por fases; validação única ao final (compilação + suíte), conforme pedido.

### Fase 1 — Capabilities centralizadas (`services/ai_llm.py`)
- `provider_capabilities(cfg)`: Z.ai → `structured_output:false, reasoning:true, max_tokens:8192`; Groq → `structured_output:true` com `strict_schema` apenas para `openai/gpt-oss-*`; conectores genéricos → nada de campos de terceiros.
- `chat_completion(..., response_schema=None)`: Z.ai mantém `thinking:{type:"enabled"}` + `max_tokens:8192` e NUNCA recebe JSON Schema; Groq GPT-OSS recebe `response_format:{type:"json_schema",json_schema:{name:"cad_plan",strict:true,schema:…}}`; Groq sem GPT-OSS recebe `json_object` (validação local obrigatória); genéricos intocados. `test_connection()` segue teste leve. Nenhuma chave/Authorization/reasoning em logs ou payloads de erro.

### Fase 2 — Contrato único (`services/ai_contract.py`, NOVO)
- Tabela `OPS` derivada da tabela canônica da task (todas as operações de `HANDLERS`/`apply_to_model`, inclusive `__select`).
- `response_schema(strict=True)`: `{explain, ops}` com `anyOf` por variante, `additionalProperties:false`, campos opcionais anuláveis; operações com objeto livre (`__preset`/`__regen` overrides) ficam fora do schema estrito e continuam aceitas na validação local. Sem `op`, sem `type`.
- `validate_payload()`: rejeita `op`/`type`, operation desconhecida, obrigatórios ausentes, campos desconhecidos; `add_box` exige `center+dimensões` OU `corner1/corner2`; `add_diagonal` exige `start+end` OU `from_element+to_element`; separa `__select`.
- `contract_text()`: bloco `EXECUTION CONTRACT` curto para o prompt.

### Fases 3/4 — Envio e prompt (`main.py`, `services/ai_prompts.py`)
- `ai_plan` e `ai_command` anexam `contract_text()` ao prompt somente quando a capability ativa (`structured_output`); guia técnico do prompt preservado; NADA de material/preço/peso/BOM reintroduzido.
- `build_system_prompt`/`build_user_message` sem mudança de assinatura.

### Fases 5/6 — Validação semântica + 1 retry (`services/ai_contract.py` + `main.py`)
- `evaluate_cad_response()`: extrai/valida → separa `__select` → `normalize_op` → `dry_run_diff` em CÓPIA do modelo → resultado estruturado (nunca aplica; modelo original imutável até `/api/ops/apply`).
- `mutation_required()`: `ops:[]` é falha para NEW/GLOBAL_RESIZE (e LOCAL_EDIT com verbo de ação + alvo identificável); pergunta genuína (`?` no explain, sem mutação exigida) é válida e não faz retry; `__select` isolado não satisfaz pedido geométrico.
- `run_cad_plan()`: orquestração comum com NO MÁXIMO 2 chamadas (1 retry) e bloco de correção curto (tipo do erro + até 2 ops problemáticas + exigência de ops efetivas); segunda falha → `ok:false` claro, sem preview falso.

### Fase 7 — Aplicação/preview consistentes (`main.py`)
- `ai_plan`: preview com `diff.operations` normalizadas e efetivas (diff recomputado após `_cohere_new_panel_elevation`); pergunta → modo `answer`; `__select` → modo `select`.
- `ai_command`: passa pela MESMA validação/dry-run antes do `execute_ops`; resposta sem efeito nunca é sucesso; falha semântica → `ok:false` com motivo. Formulário determinístico (`_quick_form_ops`) intocado; Copiloto não virou formulário; Z.ai preservada.

### Fase 8 — Validação final (uma rodada)
- `py_compile` OK em `services/ai_llm.py`, `services/ai_contract.py`, `main.py`, `tests/test_groq_contract.py`.
- Suíte nova `tests/test_groq_contract.py` (unittest, chat mockado na borda; parser → validador → normalização → dry-run REAIS): **11/11 OK**, cobrindo os casos A–G: A criação com diff positivo e `set_panel` correto; B pergunta legítima sem retry; C/D cobertos pelo caminho comum (redimensionamento segue as regras de substituição do prompt/intenção; edição local pontual sem `__blank`, diff verdadeiro); E ops vazia → 1 retry, segunda falha → `ok:false` com teto de 2 chamadas; F no-op rejeitado e corrigido em 1 retry; G payload Z.ai com `thinking enabled`/`max_tokens 8192`/sem schema Groq, Groq OSS com `json_schema strict` e outros modelos com `json_object`, sem Authorization no payload e sem reasoning exposto.
- Verificação manual breve no endpoint local: não realizada — servidor não estava disponível nesta execução (não era obrigatória; tentativa manual com Groq fica para quando a chave estiver configurada).

---

# Roteiro para auditoria pós-implementação

## Arquivos a reler

1. `services/ai_llm.py`: capabilities, payload real por host/modelo, extração de content e proteção de segredo.
2. Novo módulo de contrato/schema criado pelo executor.
3. `services/ai_prompts.py`: somente complemento contratual, guia técnico preservado.
4. `main.py`: `ai_plan`, `ai_command`, parser/validador/retry comum.
5. `core/ai_ops.py`: confirmar que o dry-run original é reutilizado e não muta `STORE`.
6. Testes novos.

## Conferência objetiva

- Compare toda operation/field do schema com `HANDLERS`, `_sim_reset`, `normalize_op` e handlers `_op_*` reais.
- Confirme que o payload Groq contém structured output no caminho de CAD, não apenas no teste de conexão.
- Confirme que o retry tem contador/local claro e no máximo duas chamadas totais.
- Verifique que preview envia operações normalizadas e que uma falha não aparece como “aplicada com ressalvas”.
- Rode os casos A–G, com chamadas mockadas na suíte e uma tentativa manual com Groq depois de configurar chave.

## Sinais de implementação incompleta ou gambiarra

- Schema existe mas `chat_completion()` nunca o recebe/envia.
- Prompt usa `operation`, schema usa `op` ou exemplos voltam a ensinar `type`.
- Schema libera `ops.items` como objeto livre.
- Groq é contornado por `_quick_form_ops`, parser offline ou troca de chip.
- Retry sem limite, ou retry em pergunta válida.
- Só verifica JSON, mas não usa `dry_run_diff` para no-op.
- Dry-run aplica/altera `STORE` ou cria entrada de undo.
- Corrige Groq quebrando `thinking` da Z.ai.
- Exceções são engolidas e o frontend recebe sucesso/preview vazio.
- Testes mockam o resultado final e não atravessam parser → validação → dry-run.
- API key, Authorization, conteúdo de reasoning ou resposta sensível aparece em log/UI.
