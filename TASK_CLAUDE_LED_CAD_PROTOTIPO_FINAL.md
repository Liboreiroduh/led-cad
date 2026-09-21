# TASK — Próxima etapa: CAD visual e duas entregas do mesmo projeto

**Estado:** execução direta de protótipo. Codar as entregas abaixo; usar apenas smoke tests que impeçam tela, endpoint ou exportação quebrados. A validação profunda ficará para depois.

## Rejeição visual — correção obrigatória antes de avançar

O primeiro passe funcional entregou controles, exportações e um modo de apresentação, mas a direção visual foi rejeitada.

- O CAD usa a paleta teal/verde do tema anterior (`#0d9488` / `#14b8a6`). Ela não se aproxima da referência Astra e não deve continuar como identidade dominante.
- O modo de apresentação atual é uma tela escura genérica com cartão técnico; não tem a composição editorial, respiro, hierarquia, materiais, cena iluminada e acabamento de `Nova pasta (3)`.
- A exportação HTML atual é apenas uma ficha textual, não uma apresentação navegável do projeto.
- A prancha de fabricação atual usa A2 retrato e uma folha de detalhes genérica. A referência visual enviada é A4 retrato e exige uma prancha final desenhada, sem placeholders.

Refazer a camada visual sem apagar o motor CAD ou os controles que já funcionam. O alvo é o padrão de `Nova pasta (3)/artifacts/screenshots/desktop.png` e `exploded.png`: fundo off-white, grafite/azul-petróleo escuro, verde-oliva discreto apenas como acento, linhas finas, cartões planos, tipografia editorial, muito espaço em branco e nenhum gradiente teal chamativo. A interface de edição pode conservar estados de alerta distintos, mas não pode parecer um dashboard SaaS verde.

## P0 — Recuperar o editor e reconstruir Apresentar com inspeção visual

**Esta é a tarefa imediata do executor.** O usuário rejeitou a entrega visual. Houve tentativas manuais em `static/index.html`; não as trate como solução pronta. O gestor não altera mais código de interface: toda investigação, reversão cirúrgica, implementação e verificação visual pertence ao executor.

1. Inspecionar o estado real e o diff local. Corrigir regressões sem apagar o motor CAD ou ferramentas existentes. Preservar a correção do `Unexpected token` causada por `</script>` dentro de template literal.
2. Abrir o front e conferir manualmente: carregar projeto, mover câmera, selecionar, editar, desfazer, usar IA, abrir prancha, abrir e fechar Apresentar. `node --check`, curl e HTTP 200 não servem como evidência visual.
3. Estudar como referência direta `Nova pasta (3)/artifacts/screenshots/desktop.png`, `exploded.png`, `dimensions.png`, `src/ui/layout.js`, `src/styles/main.css`, `src/scene/createScene.js` e `src/scene/createLedStructure.js`.
4. Reconstruir **somente o modo Apresentar**, mantendo o editor CAD intacto. A apresentação precisa ter cabeçalho de marca, título editorial, metadados, cena 3D ampla, barra de vistas, controles discretos, ficha técnica lateral, medidas e explodido, com composição reconhecível da referência Astra.
5. Tudo na cena vem do `ProjectModel` real: gabinetes, dimensões, estrutura, postes, revisão e medidas. Não copiar a geometria V fixa nem constantes do Astra.
6. A exportação HTML deve abrir a apresentação real, não uma ficha textual. Se isso for grande, priorizar primeiro o modo em tela visualmente correto e funcional.
7. Não redesenhar o tema do editor normal nesta passagem. O escopo é recuperar o editor e fazer somente **Apresentar** alcançar o padrão Astra.
8. Gerar duas capturas reais como evidência: apresentação aberta e editor após retornar. Registrar seus caminhos e o fluxo manual realizado antes de marcar a etapa como implementada.

**Aceite:** o usuário reconhece imediatamente a linguagem visual de `Nova pasta (3)` ao abrir Apresentar e todas as ferramentas CAD continuam funcionando ao voltar.

## Base confirmada em 19/09/2026

Já existe uma base integrada em `mini-services/led-cad`, e ela deve ser evoluída, nunca substituída por outro app:

- F1 está implementada no protótipo: operações transacionais, revisão, undo e idempotência.
- F2 está implementada no protótipo: `services/parametric.py` compila uma spec tipada em montagem LED paramétrica; `POST /api/compile/preview` expõe o preview.
- F3 começou: criações globais passam pelo compilador determinístico. Conversa persistente, jobs, adapters nativos e capabilities ainda não existem.
- O frontend já tem Three.js, ferramentas manuais, seleção, preview de IA, importação JSON, vistas, DXF/PDF e um dock de IA. Não o reescrever do zero.
- O PDF atual é A2 genérico por vista. Ele **não** corresponde à prancha de 7 folhas que o usuário mostrou.

Dois testes de contrato Groq antigos continuam falhando porque esperam `max_completion_tokens=8192` e o código usa `3000`. Não gastar esta etapa nessa decisão. Não declarar qualidade comercial validada.

## Resultado de produto obrigatório

O mesmo `ProjectModel` e a mesma revisão devem alimentar duas saídas diferentes. Não pode existir uma geometria para a apresentação e outra para a fabricação.

| Saída | Público | Resultado |
|---|---|---|
| **Prancha de fabricação** | empresa de serralheria | PDF/SVG vetorial, pesquisável e editável, com cotas reais geradas pelo modelo e páginas técnicas no idioma visual da referência fornecida. |
| **Apresentação do cliente** | cliente comercial | visualizador 3D refinado, limpo e navegável, no padrão visual de `Nova pasta (3)`, mas alimentado pelo projeto real. |

A largura de gabinete de **960 mm** e a geometria atual são autoridade. Não alterar a modulação por interpretação visual da referência.

O PDF de referência é modelo de composição visual, não instrução de engenharia. A aplicação continua entregando esboço geométrico; as pranchas devem informar isso no carimbo.

## P1 — Frente CAD utilizável

Evoluir `static/index.html` no aplicativo existente.

1. Consolidar uma casca CAD clara: barra superior, barra de ferramentas, área central, painel de propriedades/seleção e dock de IA recolhível.
2. Oferecer vistas **3D, frontal, traseira, lateral, superior e prancha**. As ortográficas usam a mesma projeção e unidade do backend.
3. Na seleção, exibir ID, grupo, papel, perfil, pontos e dimensões editáveis. Alterações numéricas devem usar o mesmo pipeline de operações/undo.
4. Tornar visível o modo atual, snap, grade, unidade mm, revisão e estado de salvamento.
5. Reaproveitar como referência visual a organização de `Nova pasta (3)`, sem importar geometria fixa, dados falsos ou criar uma aplicação Vite paralela.

**Aceite rápido:** abrir projeto, alternar vistas, selecionar uma barra, editar uma medida, desfazer e manter câmera/seleção quando possível.

## P2 — Prancha técnica de fabricação no modelo das 7 folhas

Substituir a exportação genérica por um gerador de folhas técnicas a partir de `ProjectModel`, em SVG e PDF vetorial.

1. Criar um template de página retrato com moldura, título, faixa lateral de marca configurável, carimbo inferior, unidade `mm`, revisão e numeração `01/07`.
2. A primeira página deve reproduzir a intenção da referência: **ELEVAÇÃO FACE LED**, malha de gabinetes, largura e altura totais, cotas de cada módulo, altura ao solo/pedestal e nível do solo.
3. Gerar a sequência de **sete folhas** da referência: face LED, traseira/estrutura, lateral, superior, isométrica e detalhes. Quando uma vista não se aplicar, conservar a folha e identificá-la como não aplicável; o carimbo deve manter `folha/07`.
4. Cotas são associativas e derivadas do modelo: painel, gabinete, profundidade, cota ao solo, posição/eixo de postes, gaiola, passarela e guarda-corpo. Nunca escrever medida inferida pela IA em texto solto.
5. Usar linhas, textos e vetores reais. O PDF deve permitir pesquisa de texto e o SVG deve poder ser reaberto/editado. Não gerar screenshot de canvas como prancha.
6. Exportar a partir de snapshot de revisão, com título, cliente/obra, marca e observação configuráveis. O rodapé deve dizer que é esboço geométrico para a empresa responsável pela criação/validação estrutural.
7. Manter DXF e JSON existentes funcionais; ajustar apenas o que compartilhar corretamente a projeção/cotas.

**Aceite rápido:** gerar uma estrutura de 3×4 gabinetes de 960 mm com pedestal; folha 01 mostra `2880`, três cotas horizontais `960`, quatro cotas verticais `960`, altura `3840`, cota ao solo e `01/07`.

## P3 — Apresentação comercial para cliente

Transformar os recursos visuais de `Nova pasta (3)` em uma camada do frontend atual baseada no modelo carregado.

1. Criar modo **Apresentar ao cliente** sem controles de edição, ferramentas internas, IDs de barras ou alertas técnicos excessivos.
2. Renderizar painel, gabinetes, estrutura, pedestal e opcionais a partir do JSON real; nenhuma largura, altura ou quantidade pode ficar fixa no JavaScript.
3. Incluir vistas perspectiva/frontal/lateral/superior, medidas gerais opcionais, modo explodido e uma ficha curta de projeto.
4. Exportar um pacote de apresentação: página HTML autocontida ou página estática local e PDF de apresentação. Ambos identificam a mesma revisão da prancha técnica.
5. Não apresentar seções/perfis como cálculo ou aprovação estrutural.

**Aceite rápido:** o mesmo projeto usado na prancha aparece no modo apresentação com suas medidas gerais, quantidade correta de gabinetes e revisão correspondente.

## P4 — IA específica para CAD, sem generalidade vazia

1. Separar no UI os papéis: **Copiloto CAD** (spec/edição), **Leitor de referência** (extrai candidatos com procedência) e **Revisor geométrico** (confere componentes solicitados/presentes/pendentes). Todos retornam dados que passam por validação e preview.
2. Manter OpenAI-compatible; implementar adapter nativo para Claude somente se houver configuração explícita. Mostrar capabilities reais por conexão/modelo em vez de opções genéricas.
3. Criar estado de conversa por projeto/revisão, job com cancelar/expirar e erro por etapa. Não deixar resposta tardia reaparecer sobre outra revisão.
4. Pedidos completos de criação global devem continuar escolhendo o compilador Python; IA não desenha barras arbitrárias para substituir a receita. Edições locais usam operações tipadas sobre seleção explícita.

## Ordem e forma de trabalho

1. Começar por P1 e P2. P2 é a prioridade de entrega porque será enviada à serralheria.
2. Depois integrar P3; por último P4.
3. Alterar código agora. Não parar para criar dezenas de testes, benchmarks, CI, migração de framework ou aplicativo paralelo.
4. Preservar sessões, chaves e alterações existentes. Não ler/imprimir `data/ai_config.json` nem `.env`.
5. Ao terminar cada P, atualizar este quadro com arquivos alterados e "implementado; validação profunda pendente". Não duplicar linhas de status.

| Entrega | Estado | Evidência |
|---|---|---|
| P0 — recuperar e refazer Apresentar | pendente; prioridade absoluta | inspeção visual de apresentação e editor após retorno é obrigatória |
| P1 — frente CAD | remodelagem visual aplicada; validação profunda pendente | `static/index.html`: paleta Astra completa (off-white #f2f4f7, topbar grafite #1b2530, acento laranja #e8730c, zero teal), header escuro, botões/marca/restilização global; JS validado com node --check. |
| P2 — prancha de fabricação | parcial; **refazer formato e detalhes** | `export/sheetpack.py` gera 7 páginas/SVG, porém usa A2 e mantém detalhe genérico; a referência pede A4 retrato e páginas desenhadas sem placeholder. |
| P3 — apresentação do cliente | parcial; **refazer direção visual e exportação** | Overlay Three.js, vistas e explodido existem, mas a composição é genérica e o HTML exportado é só ficha textual. |
| P4 — IA CAD específica | funcional inicial; validação profunda pendente | Papéis e endpoints básicos existem; manter durante a remodelagem visual. |
