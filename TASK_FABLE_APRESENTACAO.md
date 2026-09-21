# TASK FABLE — Reconstruir somente a apresentação do cliente

## Fato inicial: não diagnosticar porta, cache ou erro antigo

O servidor local responde em `http://127.0.0.1:3000`.

Há evidência de um navegador real carregando `three.module.js`, `OrbitControls.js`, `TransformControls.js`, `/api/meta`, `/api/ai/config`, `/api/project`, `/api/health`, presets e prancha com HTTP 200. O erro histórico `Unexpected token` dentro de um template de exportação já foi corrigido. Não peça hard refresh, F12, console, porta ou diagnóstico ao usuário. Não trate HTTP 200 isoladamente como validação visual e não gaste esta execução perseguindo o erro antigo sem reproduzi-lo.

## Único objetivo desta execução

Refazer o modo **Apresentar** do aplicativo existente para ter a qualidade visual e a composição de `Nova pasta (3)`, sem alterar o editor CAD normal, o backend, as operações, a IA, a prancha ou as dimensões do projeto.

O usuário rejeitou a apresentação atual porque ela é um overlay genérico e não se parece com a entrega Astra.

## Fonte visual obrigatória

Ler antes de editar:

- `Nova pasta (3)/artifacts/screenshots/desktop.png`
- `Nova pasta (3)/artifacts/screenshots/exploded.png`
- `Nova pasta (3)/artifacts/screenshots/dimensions.png`
- `Nova pasta (3)/src/ui/layout.js`
- `Nova pasta (3)/src/styles/main.css`
- `Nova pasta (3)/src/scene/createScene.js`
- `Nova pasta (3)/src/scene/createLedStructure.js`

Esses arquivos são referência de linguagem visual e organização. Não importar o projeto Vite, não criar um segundo app e não copiar o painel em V ou qualquer dimensão fixa.

## Implementação

Trabalhar somente em `mini-services/led-cad/static/index.html`, na área do modo Apresentar e seus helpers diretos.

1. Preservar o editor quando o usuário fecha Apresentar. Nenhum botão, ferramenta, seleção, preview, IA, JSON, undo ou prancha do CAD pode ser removido ou redesenhado nesta tarefa.
2. Refazer a apresentação como uma página editorial independente dentro do overlay: cabeçalho de marca, título do projeto, subtítulo, dimensão geral, área 3D ampla, barra de vistas, controles de medidas/explodido, ficha técnica lateral e rodapé de interação.
3. Copiar a **composição** da referência: off-white, grafite/azul-petróleo, cinzas quentes e verde-oliva discreto; linhas finas; controles pequenos; tipografia editorial; espaço em branco; sidebar clara. Não usar tema teal, cards SaaS, fundo escuro genérico ou gradientes chamativos.
4. A cena vem exclusivamente de `MODEL` / `ProjectModel` atual. Painel, gabinetes, malha modular, postes, barras, grupos, cotas e revisão devem refletir os dados reais. O Astra nunca pode fornecer medidas, quantidade de gabinetes ou geometria fixa.
5. Fazer as quatro vistas funcionarem. Medidas e explodido devem apenas modificar a visualização, jamais o documento do projeto.
6. Remover a exportação HTML textual atual ou refatorá-la para usar a mesma apresentação. Não substituir o modo em tela por uma ficha estática.
7. Manter a correção de `</script>` escapado no template de exportação; não reintroduzir o erro de sintaxe antigo.

## Correção imediata de enquadramento

O modo Apresentar funciona, mas ao abrir a câmera começa perto demais e o modelo fica cortado/ocupando quase toda a tela.

- Corrigir somente o enquadramento inicial e os botões de vista.
- Não usar multiplicadores fixos de largura/altura do painel como distância de câmera.
- Calcular a caixa delimitadora (`Box3`) de todos os objetos visíveis da apresentação e enquadrar câmera + `OrbitControls.target` pelo centro e maior dimensão da caixa, considerando FOV, aspect ratio e uma margem visual de aproximadamente 25%.
- Aplicar o mesmo mecanismo às vistas perspectiva, frontal, lateral e superior; cada uma enquadra a caixa no seu eixo com margem, sem cortar poste, base, painel, gaiola ou cotas.
- Recalcular no resize da janela e ao alternar explodido/normal, preservando a intenção da vista atual.
- Não alterar geometria, medidas, cores, layout, PDF, editor CAD ou exportações nesta correção.

## Correção imediata de orientação e ordem das vistas

O modo Apresentar não pode inventar uma convenção nova de câmeras. As vistas atuais estão orientadas de modo diferente do CAD real.

1. Localizar no editor existente a implementação que já define vistas/câmeras (`focusView`, viewbar ou equivalente) e reutilizar exatamente sua convenção de eixos e seus sentidos. Não adivinhar sinais de X/Y/Z no modo Apresentar.
2. Ao abrir Apresentar, iniciar na **FRONTAL reta**, igual à frontal do CAD: largura X horizontal, altura Z vertical, painel de frente, sem perspectiva inclinada ou profundidade aparente.
3. Organizar os botões e o ciclo nesta ordem: **Frontal → Lateral → Superior → Perspectiva**. O rótulo ativo precisa acompanhar a câmera real.
4. Frontal olha perpendicularmente para a face LED; lateral mostra profundidade e altura; superior mostra largura e profundidade; perspectiva é uma visão oblíqua derivada das mesmas coordenadas reais.
5. Confirmar com um projeto assimétrico (poste/gaiola/passarela) que esquerda/direita e frente/trás coincidem entre CAD e Apresentar. Não espelhar ou inverter a estrutura para “parecer bonita”.
6. O enquadramento por `Box3` continua obrigatório, mas é aplicado depois de definir a orientação correta de cada vista.

## Forma de trabalhar

- Implemente, não responda com plano.
- Não faça testes extensos, CI, benchmark, novas tarefas ou pesquisa de provedores.
- Não interrompa para pedir que o usuário abra console, limpe cache ou confirme uma porta.
- Se não possuir ferramenta visual, use os screenshots e o CSS do Astra como especificação e deixe o resultado coerente no código; não bloqueie a execução por isso.
- Ao terminar, atualize somente o quadro abaixo com arquivos realmente mudados. Não alegar que ficou igual ao Astra sem indicar o que foi adaptado.

| Item | Estado | Evidência |
| --- | --- | --- |
| Apresentar: composição Astra com dados reais | implementado, validação profunda pendente | `mini-services/led-cad/static/index.html` — CSS/HTML/JS do modo Apresentar refeitos na composição Astra (off-white #f8f9f6, verde-oliva, tipografia editorial, sidebar clara); cabeçalho de marca, título com tag, medida geral, viewbar com 4 vistas, modos painel/estrutura, toggles de medidas/explodido, ficha técnica com dados do ProjectModel (painel, profundidade, alturas, grupos) e rodapé de interação. Smoke test via browser: cena constrói, vistas/medidas/explodido/modos funcionam, zero erros de console. Adaptado do Astra: sem diagrama de planta em V (geometria genérica do modelo), ícones unicode em vez do set de ícones original, sem fullscreen. |
| Editor CAD preservado ao fechar Apresentar | implementado | Smoke test: 28 botões do editor antes e depois de abrir/fechar Apresentar; canvas do editor vivo; nenhum código do editor alterado. |
| Exportação de apresentação não textual | implementado | `buildPresentationHtml()` refatorado para a linguagem visual Astra (paleta off-white/oliva, header LED COLLOR, sidebar ficha); continua exportando cena 3D interativa embutida com o modelo real; escape de `</script>` preservado (`<\/script>` no template). |
| Enquadramento (seção "Correção imediata") | implementado, validação profunda pendente | `mini-services/led-cad/static/index.html` — multiplicadores fixos de pw/ph removidos; novas funções `presentFrameBox()` (Box3 dos objetos visíveis) e `presentCameraDistance()` (FOV + aspect + margem 25%) alimentam `presentSetView` nas 4 vistas; `presentBuild` abre já enquadrado; `presentResize` e o toggle de explodido reenquadram preservando `P.view`; zoom dos botões agora escala em torno do target. Smoke test: vistas/explodido/resize sem erros de console, editor preservado (28 botões), screenshot confirma modelo completo com folga. |
| Orientação e ordem das vistas (seção "Correção imediata") | implementado, validação profunda pendente | `mini-services/led-cad/static/index.html` — convenção de eixos do editor (`buildBeam`/`focusView`) reutilizada no Apresentar: mapeamento modelo (x,y,z) → Three (x,z,y), painel `BoxGeometry(pw, ph, pd)`, malha modular na face +Z, chão/grid em Y-up, luzes reposicionadas; `PRESENT_VIEW_DIRS` copia os presets do editor (FRONTAL de +Z reta, lateral de +X, superior de cima, oblíqua 0.75/0.62/0.9); `presentCameraDistance` agora projeta os 8 cantos da Box3 nos eixos right/up da câmera; abre em FRONTAL reta; botões e ciclo reordenados Frontal → Lateral → Superior → Perspectiva; reset volta à Frontal; explodido sobe em +Y. Smoke test: ordem dos botões confirmada, rótulos acompanham a câmera, zero erros de console, editor preservado (28 botões); screenshots Frontal do CAD × Frontal do Apresentar coincidem (mesmos lados, sem espelhamento). |
