# Contexto canônico — LED Structure CAD

> A tarefa ativa é exclusivamente a indicada pelo usuário na sessão, conforme
> [AGENTS.md](../../AGENTS.md). `TASK_*.md` são históricos por padrão;
> este contexto não ativa tarefas nem autoriza implementação.
> A [auditoria de 19/09/2026](../../docs/AUDITORIA_LED_CAD_2026-09-19.md)
> é uma referência histórica, não um backlog obrigatório.
> Este documento descreve a base existente e suas intenções históricas.
> Garantias abaixo sobre preview, atomicidade e undo têm divergências no código
> constatadas na auditoria; não tratá-las como testes já aprovados.
> Novos contratos da task só serão disponíveis após implementação.

Este arquivo é o ponto de partida para qualquer IA externa (ChatGPT, GPT, Claude etc.) que vá analisar, corrigir ou evoluir o projeto. Leia este arquivo antes de sugerir mudanças. O código atual deste repositório é a autoridade; não inventar uma arquitetura paralela.

## Produto e limite do escopo

LED Structure CAD é um protótipo local em Python/FastAPI para desenhar **esboços geométricos editáveis** de estruturas para painéis LED. Não é um sistema de orçamento, lista de corte, preços, peso, material escolhido, memória de cálculo ou projeto estrutural executivo.

- Unidade interna: milímetros.
- Eixos: X = largura; Y = profundidade; Z = altura; solo = Z 0.
- Painel LED é referência visual. Gaiola, postes, barras, passarela e guarda-corpo são a geometria estrutural de esboço.
- O usuário/engenheiro pode editar no canvas. A IA é copiloto: propõe operações geométricas, nunca toma controle silenciosamente.

## Como executar

Modo direto: executar a partir de `mini-services/led-cad`. No Windows com o
launcher disponível, usar `py -3.10 -m uvicorn main:app --host 127.0.0.1 --port 3000`.
No modo shell Next.js, o shell ocupa 3000 e encaminha ao FastAPI em 3100,
conforme `next.config.ts` e o `package.json` do serviço. Não executar ambos
na porta 3000. A consolidação da instalação está prevista na fase F0 da task.

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 3000
```

Aplicação: `http://localhost:3000`.

## Fonte de verdade e arquitetura

```text
static/index.html
  → FastAPI (main.py)
  → ProjectStore / ProjectModel
  → core/operations.py + core/ai_ops.py
  → desenho/projeções/exportação

Copiloto:
usuário → ai_intent → ai_prompts → ai_llm → provider
→ JSON { explain, ops } → validação/dry-run → preview
→ Apply explícito → apply_batch + undo
```

| Área | Arquivos canônicos |
|---|---|
| API e fluxo do Copiloto | `main.py` (`ai_plan`, `ai_command`) |
| Modelo persistido | `models/element.py` (`ProjectModel`, `Element`, `Vec3`) |
| Operações e undo | `core/operations.py`, `core/ai_ops.py` |
| Normalização/dry-run | `core/ai_ops.py` (`normalize_op`, `dry_run_diff`, `apply_batch`) |
| Intenção | `services/ai_intent.py` |
| Prompt CAD | `services/ai_prompts.py` |
| Conexão OpenAI-compatible | `services/ai_llm.py` |
| Contrato estruturado da IA | `services/ai_contract.py` |
| Interface | `static/index.html` |

## Contrato obrigatório do Copiloto

A resposta da IA precisa ser somente:

```json
{
  "explain": "Resumo curto",
  "ops": [
    {"operation": "set_panel", "width": 1920, "height": 960}
  ]
}
```

- O campo canônico é `operation`; não usar `op`.
- `type` existe apenas como compatibilidade de entrada em `normalize_op`; não deve ser ensinado como formato novo.
- `ops: []` só é válida para pergunta legítima ou ambiguidade geométrica real.
- Para NEW, GLOBAL_RESIZE ou LOCAL_EDIT com informações suficientes, as operações devem alterar efetivamente o modelo.
- `ai_plan` simula e devolve preview; não pode modificar o projeto. O usuário confirma em Apply.
- `apply_batch` é atômico e cria uma única entrada de undo.

Operações reais aceitas estão centralizadas em `core/ai_ops.py:HANDLERS`, incluindo `__blank`, `set_panel`, `add_box`, `add_grid`, `add_beam`, `add_post`, `add_plate`, `add_circle`, operações de mover/redimensionar/duplicar/remover e operações de lote.

## Regras geométricas importantes

- `ground_clearance` é a cota da base do painel/gaiola; em painel com poste, topo do poste e base da gaiola devem coincidir.
- Para mudar altura de poste ancorado, usar `set_post_height`; isso move a superestrutura junto. Não esticar o poste de forma isolada.
- `add_grid` exige retângulo coplanar: exatamente um eixo deve ter a mesma coordenada em `start` e `end`.
- `add_box` recebe `center + width/depth/height` ou `corner1 + corner2`; não recebe `x/y/z` soltos.
- Redimensionamento integral, por exemplo 2×1 para 4×2 gabinetes, substitui o conjunto de forma controlada; não sobrepor uma segunda gaiola.
- Edição local altera apenas o elemento/grupo pedido; não usar `__blank` para ajuste pontual.

## Estado funcional atual

- Backend canônico: FastAPI em `mini-services/led-cad`, porta 3000.
- Formulário rápido: criação determinística por `_quick_form_ops`; não deve ser usado como desvio quando o Copiloto falhar.
- Copiloto: usa `/api/ai/plan` e preview antes de Apply.
- Conexões de IA: manuais, OpenAI-compatible, guardadas somente no backend local.
- Z.ai/GLM: mantém thinking interno, mas reasoning não pode aparecer na UI.
- Groq GPT-OSS (20b/120b): JSON Schema strict (`response_format json_schema`),
  `reasoning_effort: medium` com `include_reasoning: false` (reasoning nunca
  aparece na UI, em logs ou no disco) e `max_completion_tokens`. Instruções
  vão no conteúdo da primeira mensagem de usuário (sem depender de system).
  Campos opcionais que o strict output devolve como `null` são sanitizados
  na borda (`services/ai_contract.py:_sanitize_strict_nulls`) antes do motor:
  opcional null → chave removida; obrigatório null → erro; `False`/`0`/`[]`
  permanecem. `mirror_elements.pivot` é escalar numérico (mm).

## Snapshot ativo consultado em 14/09/2026

O servidor local respondeu em `/api/project` com:

```json
{
  "project": {"name": "Projeto em branco", "units": "mm"},
  "panel": {"width": 1920, "height": 960, "depth": 650},
  "installation": {"type": "wall", "posts": 0, "ground_clearance": 3000, "environment": "outdoor"},
  "element_count": 34
}
```

Este snapshot é apenas referência de sessão, não preset de produto. Para uma IA externa revisar um desenho específico, exporte o projeto em JSON pela interface e envie esse JSON junto deste arquivo; não publique `data/_session*.json` automaticamente.

## Segurança e Git

Nunca incluir no repositório público:

- `data/ai_config.json` ou qualquer API key;
- `data/_session*.json` sem revisão explícita;
- banco local, PID, log, cache Python ou exportações privadas.

Esses itens são intencionalmente ignorados por `.gitignore`. O repositório contém código, testes, presets de referência e documentação, não credenciais nem sessão privada.

## Como uma IA externa deve trabalhar

1. Ler este arquivo e os arquivos da tabela de arquitetura.
2. Conferir o executor antes de mudar prompt/schema.
3. Não criar um novo motor CAD, frontend paralelo ou versão v2.
4. Não reduzir o contexto do Copiloto a material/orçamento: o foco é geometria editável.
5. Para mudanças no Copiloto, preservar o pipeline `JSON → normalização → dry-run → preview → Apply → undo`.
6. Para uma correção grande, criar uma task curta com critérios de aceite antes de alterar código.
