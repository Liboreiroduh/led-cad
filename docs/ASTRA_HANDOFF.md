# Handoff — prancha final LED Collor

## Escopo e precedência
- Task indicada para o Claude: `TASK_CLAUDE_PRANCHA_FINAL_LEDCOLLOR.md` (raiz).
- Esta passagem é somente preparação; implementação fica para a sessão do Claude.
- AGENTS.md, CLAUDE.md e contexto canônico já tratam outras TASK_*.md como históricas.
- Somente a instrução explícita da sessão ativa uma task; status antigo não vale.
- PROTOTIPAGEM DESKTOP: preservar alterações locais, inclusive exclusões de tasks.
- Não fazer commit/push/branch/PR nem reset/restore/clean/stash.

## Objetivo essencial
O PDF de referência é PADRÃO VISUAL DA SAÍDA, não geometria padrão.
Geometria real → projeções/cotas → planejador de folhas → template → PDF.
Não fixar V, duas faces, medidas, poste ou sete folhas.
O número de folhas e seus conteúdos devem acompanhar o projeto.

## Arquivos e fluxo atuais
Todos os caminhos abaixo são relativos a `mini-services/led-cad/`.
- Entrypoint FastAPI: `main.py`, objeto `app`.
- Modelo: `models/element.py`, `ProjectModel` e `Element`.
- Projeções: `drawing/projections.py`, `project_view()` e `View2D`.
- Cotas: `drawing/dimensions.py`, `add_dimensions()`.
- PDF técnico: `export/pdf.py`, `build_pdf()` e `render_view_pdf()`.
- Fluxo técnico: STORE → modelo → project_view → add_dimensions → build_pdf.
- Endpoint técnico existente: `GET /api/export/pdf`; preservar.
- Apresentação legada: `GET /api/export/presentation.pdf`, em `main.py`.
- Prancha existente: `export/sheetpack.py`, atualmente com sete folhas fixas.
- Frontend CAD: `static/index.html`; Next em `src/app/page.tsx` é apenas shell.
- Alterações prováveis: novo planejador/template em `export/`, main.py e botão no HTML.
- Estender projeções/cotas somente onde necessário; não reconstruir IA/presets.

## Alterações parciais da execução interrompida
- Já foi adicionada em main.py a rota `GET /api/export/pdf/presentation`.
- Ela chama `export.ledcollor.build_presentation_pdf(model, meta={...})`.
- O arquivo `export/ledcollor.py` NÃO existe: essa rota ainda não funciona.
- Já existem botões PDF LED Collor em Prancha e Apresentar no HTML.
- Eles apontam para a rota acima. Completar a integração, não duplicá-la.
- Não houve geração de PDF nem teste dessa implementação parcial.

## Assets e referência
- Existe `public/logo.svg` na raiz; identidade LED Collor não confirmada.
- A busca por nomes de assets não encontrou logo oficial LED Collor identificável.
- Procurar também assets das referências; não tratar logo genérico como oficial.
- PDF informado pelo usuário: `C:/Users/Duh/Desktop/Painel_LED_V_LedCollor_7_paginas (1).pdf`.
- Disponibilidade atual desse PDF não conferida nesta preparação.
- Sem asset oficial utilizável, usar placeholder identificado, conforme a task.

## Limitações relevantes
- Element aceita beam/plate/bolt/panel; não há face curva/rotação de painel explícita.
- project_view usa o Panel global para elementos panel; revisar múltiplas faces.
- Chapas usam envelope projetado; isometria exige atenção para não deformar contorno.
- Curvas existentes como segmentos devem manter suas coordenadas, sem retangularizar.
- Não inventar modulação de gabinete nem medidas ausentes.
- Não alterar export técnico ao adaptar escala, cotas ou layout da apresentação.
- Próxima execução: implementar, gerar um PDF real e conferir visualmente; testes mínimos.
