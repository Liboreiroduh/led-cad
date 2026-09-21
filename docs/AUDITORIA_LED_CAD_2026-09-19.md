# Auditoria de preparação — 19/09/2026

## Escopo e método

Leitura do backend, modelo, operações, prompts, transporte de IA, frontend, exportação, catálogo, documentos e scripts. Execução da suíte existente e sondagens em modelos sintéticos, com persistência desabilitada. Não houve chamada externa a modelos de IA, teste de carga do navegador ou modificação do código do aplicativo. Não foram extraídas nem validadas medidas dos PDFs/DWGs; o acervo foi inventariado por caminhos e o catálogo JSON foi lido.

O workspace já continha muitas alterações e arquivos não rastreados antes desta auditoria. Nenhuma limpeza, restauração de Git ou migração de sessão foi realizada.

## Base a aproveitar

- `models/element.py`: documento Pydantic, coordenadas em mm, barras, chapas, pinos e referência do painel.
- `core/operations.py`, `core/ai_ops.py`: operações úteis, cópia para simulação, diff e histórico inicial.
- `services/ai_intent.py`, `ai_prompts.py`, `ai_contract.py`, `ai_llm.py`: preparação contextual, contrato de resposta e conexões manuais.
- `static/index.html`: editor Three.js, seleção, snaps, desenho livre, propriedades, plano e aplicação.
- `drawing/` e `export/`: vistas, cotas, SVG, PDF, DXF e outros formatos existentes.
- `presets/referencias/catalogo.json` e `referencias/`: ponto de partida para receitas e conhecimento rastreável. Catálogo deduplicado por dimensão não prova que todas as tipologias e revisões estejam representadas.

## Resultados reproduzidos

Comando executado na raiz:

```powershell
py -3.10 -B mini-services/led-cad/tests/test_groq_contract.py
```

**21 testes: 19 passaram, 2 falharam.** Os testes `test_groq_oss_structured_output` e `test_groq_outro_modelo_json_object` esperam `max_completion_tokens=8192`; o código envia 3000. Isso comprova divergência de contrato/teste, não comprova que 8192 seja o valor correto para qualquer modelo. Definir orçamento de saída com evidência e tratar truncamento.

Sondagens adicionais importaram as funções reais com dados sintéticos; para `ai_plan`, o `STORE` foi substituído por um `ProjectStore` temporário com `_persist=lambda:None` e o carregamento da conexão bloqueado por mock.

| ID | Entrada/ação | Resultado observado | Localização |
|---|---|---|---|
| A01 | `crie um painel novo 4x2 sem passarela e sem guarda-corpo` | `walkway=true`, `guardrail=true` | `services/ai_intent.py:derive_from_text`, `_has` procura presença sem negação |
| A02 | `base do painel em 20 mm` | `ground_clearance=20000.0` | `derive_from_text`, `_to_mm` |
| A03 | `crie um painel novo 4x2 gabinetes de 960x960 mm` | painel 4000×2000; esperado pela contagem 3840×1920 | `derive_from_text`, `_WXH` |
| A04 | `dry_run_diff` com 121 movimentos válidos | retorna 120 operações, sem erro | `core/ai_ops.py:dry_run_diff`, fatia `[:120]`; Apply rejeita >120 |
| A05 | construir `Vec3(x=float('nan'))` | aceito pelo modelo | `models/element.py:Vec3` |
| A06 | `ProjectModel` com dois elementos do mesmo ID | aceito; `index()` pode ocultar um deles | `models/element.py:ProjectModel` |
| A07 | `apply_operation` com operação inexistente | lança erro, mas deixa uma entrada de undo | `core/operations.py:apply_operation` empilha antes de validar |
| A08 | pedido de painel novo com passarela e guarda-corpo; resposta contém só uma barra | `evaluate_cad_response` retorna `ok=true`, diff total 1 | `services/ai_contract.py:evaluate_cad_response` |
| A09 | `ai_plan(text='desfaca')` com painel e poste no modelo sintético | `mode='executed'`, largura volta de 5000 para 4000, undo é consumido | `main.py:ai_plan` → `execute_ops` |

A08 é a principal lacuna de qualidade geométrica: alteração efetiva não significa proposta completa. O teste existente de criação também pede passarela, porém verifica principalmente diff e dimensão do painel, sem comprovar a passarela.

## Achados por leitura, ainda sem benchmark ou teste de falha completo

| ID | Evidência no código | Consequência/risco a verificar |
|---|---|---|
| A10 | `adopt()` chama `buildScene()`, que chama `clearScene()` e reconstrói todos os meshes | custo de edição cresce com o desenho; candidato a travamentos |
| A11 | `clearScene()` descarta geometria; `buildBeam`, `buildPlate`, `buildPanel` criam novos materiais | descarte de materiais ausente nesse caminho; medir retenção de recursos após muitos ciclos |
| A12 | loop `animate()` reescreve `vpStats.innerHTML` em cada frame | trabalho de DOM independente de mudança no projeto |
| A13 | helper `api()` sem timeout/cancelamento; `sendAi()` mantém `aiBusy` até a promise terminar | usuário sem mecanismo de cancelamento; não há prazo total percebido pela UI |
| A14 | `TIMEOUT_S=75`, até duas chamadas semânticas; resposta HTTP expõe apenas content | espera acumulada e perda de `finish_reason`, uso e identificação de truncamento; timeout de socket não é prazo total do fluxo |
| A15 | `STORE` global, endpoints recebem modelo ativo sem revisão-base e sem isolamento de projeto | concorrência entre abas/usuários, preview desatualizado e resultado tardio |
| A16 | `apply_batch` simula e depois executa de novo sobre estado vivo; resets chamam `new_from_preset(...keep_undo=True)` | atomicidade/uma entrada de undo não garantidas para todo caminho; ausência de swap único do candidato |
| A17 | `_persist()` usa `write_text` direto e ignora qualquer exceção; versões também têm gravação best-effort | perda ou corrupção sem estado visível de salvamento |
| A18 | undo no Python; `opsStack`/`redoStack` no browser; redo de lote chama função que limpa redo | duas autoridades e inconsistências em sequência, recarga e múltiplas abas |
| A19 | `next_id()` reconstrói conjunto de IDs e começa a busca em 1; `add_grid` sem teto de linhas/colunas; remoções do diff recalculam conjuntos | trabalho que cresce com expansão; 120 operações não limitam elementos gerados |
| A20 | `_elements_digest` limita contexto, `_selection_digest` limita IDs; prompt manual e tabela de operações separados | seleção/conjunto pode ficar incompleto; risco de divergência de contrato |
| A21 | `bom_full` calcula BOM/vento em caminhos de edição; tipos trazem perfis fixos e painel singular | acoplamento desnecessário ao fluxo geométrico; dupla face e montagem semântica precisam evolução |
| A22 | ausência de `schema_version`/revisão transacional e montagem explícita no `ProjectModel` | difícil migrar, relacionar componentes e regenerar preservando edição |
| A23 | `buildBeam` usa largura `prof.w` nos dois lados de seção retangular; chapas são alinhadas aos eixos | representação perde altura do perfil e orientação de chapas; avaliar transformações comuns a render/export |
| A24 | há rotas GET que carregam versão/projeto e alteram STORE; CORS `*` e persistência local compartilhada | contrato HTTP inadequado e isolamento insuficiente para disponibilização em rede |
| A25 | README descreve backend direto em 3000, package do serviço usa 3100 e Next usa 3000 | modos legítimos, porém mal diferenciados; scripts da raiz usam comandos de shell Unix |

Não afirmar que A10–A20 são a causa única dos travamentos. Capturar tempos por etapa, draw calls, memória e respostas concorrentes na fase F0/F1.

Um ensaio também mostrou que importar `main` da raiz falha porque `static` é resolvido pelo diretório atual. Em outro ensaio, mensagem de erro com símbolo Unicode falhou na saída CP1252 do Python/Windows. Consolidar paths baseados em `__file__` e logs compatíveis com UTF-8. A reprodução final de A09 foi executada no diretório do serviço e não usou API externa.

## Conclusão de arquitetura

O ganho principal virá de especificação geométrica tipada + compilador paramétrico + validação de atendimento, apoiados em transações e revisão. Prompt melhor é parte da solução; trocar o modelo de IA não corrige contrato incompleto, unidade ambígua, estado concorrente ou reconstrução da cena.

## Fontes externas consultadas

Consultadas em 19/09/2026; reconferir capacidades no momento de implementar.

- [Groq: Structured Outputs](https://console.groq.com/docs/structured-outputs): suporte depende de modelo/modo; schema não substitui validação geométrica do aplicativo.
- [Anthropic: Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs): usar adapter de protocolo e formatos suportados ao integrar API nativa Claude.
- [Three.js: Material](https://threejs.org/docs/pages/Material.html): descarte explícito dos recursos de material.
- [Three.js: InstancedMesh](https://threejs.org/docs/pages/InstancedMesh.html): possibilidade de reduzir draw calls para elementos repetidos; medir antes de adotar.
- [FastAPI: concorrência](https://fastapi.tiangolo.com/async/): funções de rota `def` são executadas em threadpool. O diagnóstico de estado compartilhado é distinto de bloqueio do event loop.

O plano de implementação e seus critérios de conclusão estão em [TASK_CLAUDE_LED_CAD_COMERCIAL.md](../TASK_CLAUDE_LED_CAD_COMERCIAL.md).
