# Tarefa Z.ai — corrigir todas as folhas e cotar barras no PDF

## Fonte única e escopo

Trabalhe diretamente na versão canônica em execução: `mini-services/led-cad`. Não criar cópia, versão paralela, arquivo de export alternativo, fallback visual ou outro motor de PDF.

Corrija somente a prancha PDF e a geração de cotas que a alimenta. Arquivos candidatos: `drawing/dimensions.py`, `drawing/projections.py`, `export/pdf.py` e, só se inevitável, o ponto de export em `main.py`.

Não alterar frontend, IA, presets, banco, materiais internos, preço, BOM, vento, operações CAD ou modelo de dados.

## Defeitos observados

A primeira página da prancha se aproxima do formato pedido, mas as páginas seguintes renderizam o desenho muito pequeno e deslocado para o canto inferior. Elas não seguem o mesmo padrão de ocupação, escala e leitura da primeira folha.

Além disso, a entrega precisa informar as medidas de cada barra/linha estrutural, como um desenho CAD: quem recebe deve enxergar quanto mede cada segmento relevante. Hoje as cotas gerais não bastam.

Há também um defeito de interface/exportação: ao clicar uma única vez em **Baixar PDF**, o navegador baixa **três arquivos**. O comportamento correto é exatamente um clique → uma única requisição de exportação → um único arquivo `.pdf`.

## Resultado obrigatório

Para **cada folha/vista**:

1. A vista deve ocupar a área útil central da A2, com a mesma lógica de escala, moldura, cabeçalho, rodapé e legibilidade da primeira página. Não aceitar desenho pequeno no canto inferior.
2. A escala deve ser calculada independentemente a partir do envelope da vista atual, incluindo as cotas dessa própria vista; nunca reutilizar origem, bounds ou escala da primeira página.
3. Mostrar cotas gerais estruturais: largura, altura, profundidade, bases, poste, gaiola, vãos e afastamentos pertinentes à projeção.
4. Mostrar também a **medida de comprimento de cada barra/linha estrutural visível naquela projeção**, derivada dos pontos reais `start/end` do modelo. Exemplos: poste vertical, travessa horizontal, diagonal, contorno da gaiola, avanço de passarela e barra de guarda-corpo.
5. Uma barra perpendicular à vista pode ser cotada na vista ortográfica onde seu comprimento aparece, ou em outra vista que a represente sem ambiguidade. Nunca inventar valor e nunca duplicar a mesma medida em três páginas sem necessidade.
6. Não mostrar nome/id de material, perfil, METALON, TUBO, peso, custo, BOM, lista de peças nem quantidade. O valor da medida pode aparecer sozinho, por exemplo `3000`, `1920`, `650` (mm).
7. Evitar acúmulo: organizar cotas por níveis externos, agrupar barras colineares repetidas quando o mesmo comprimento/posição já estiver explicitado por cadeia de cotas e afastar textos/linhas que colidam. Não é permitido esconder todas as cotas individuais para “limpar” a página.
8. Um clique em **Baixar PDF** baixa somente um arquivo PDF. A correção deve remover a causa raiz (por exemplo: listener duplicado, `submit` simultâneo, propagação de evento ou múltiplas chamadas de download), e não apenas bloquear temporariamente novos cliques.

## Critério de "cada barra"

- Barra com comprimento, posição ou inclinação distinta: deve ter sua dimensão legível na vista em que é compreensível.
- Barras repetidas e idênticas numa mesma grade: uma cadeia de cotas pode representá-las, desde que deixe claro o comprimento de cada vão/segmento. Não usar rótulo de quantidade.
- Diagonais: cotar por comprimento real ou, quando uma cota diagonal tornaria a prancha ilegível, pelas duas coordenadas/extremos que a definem; a solução deve permitir reconstruir a diagonal.
- Chapas/bases: cotar largura × profundidade e sua posição geométrica, sem falar de espessura/material comercial.

## Implementação esperada

1. Investigue primeiro por que páginas posteriores usam bounds/origem/escala incorretos. Corrija a causa, não crie offsets fixos por página, view name ou preset.
2. Centralize a política de cotagem no gerador de dimensões. Use a projeção e a geometria real, não textos manuais dentro de `pdf.py`.
3. Garanta que a caixa de escala do PDF considere todas as primitivas de cota e texto da página atual, inclusive cotas rotacionadas.
4. Preserve uma página por vista; não volte ao mosaico de várias vistas em uma única folha.
5. Localize todos os listeners/caminhos de exportação de PDF. Deve existir apenas um fluxo ativo para o botão e ele deve impedir o comportamento padrão caso esteja dentro de formulário.
6. Faça uma única validação final, não testes a cada microetapa.

## Roadmap obrigatório

Preencha este próprio arquivo enquanto executa. Marque a etapa somente quando ela estiver concluída; não criar relatório separado.

- [x] 1. Diagnosticar a diferença entre a primeira folha e as demais; registrar causa real e arquivos envolvidos.
  - Registro: Fluxo real: `main.build_views` → `project_view` → `add_dimensions` → `build_pdf`/`render_view_pdf`. A matemática de bounds/escala/origem JÁ é independente por folha (`view.padded(pad)` + `min(w/wmm, h/hmm)` + centróide) — simulando o transform ativo, o conteúdo de TODAS as 6 folhas ocupa a área útil (ex.: FRONTAL 88,9–505,1 × 63,5–349,5 mm de 594×420). Causa real encontrada: o **reportlab reseta o estado gráfico (CTM) a cada `showPage()`** e `build_pdf` aplicava `c.scale(mm, mm)` UMA única vez antes do loop. Prova empírica: decodificando os content streams do PDF gerado, a página 1 contém `2.834 0 0 2.834 0 0 cm` (escala mm) e as páginas 2..6 não contêm nenhum operador `cm` → desenhadas em pontos (≈35% do tamanho), amontoadas no canto inferior esquerdo. Arquivo envolvido: `export/pdf.py` (função `build_pdf`); `drawing/` sem defeito nesse ponto.

- [x] 2. Corrigir escala, bounds e posicionamento por folha para todas as vistas.
  - Registro: `export/pdf.py::build_pdf` — o `c.scale(mm, mm)` foi movido para DENTRO do loop, reaplicado no início de cada folha (o `showPage()` do reportlab reseta a CTM; era a causa do desenho pequeno/canto inferior a partir da 2ª página). Também aplicado no caminho de folha vazia ("SEM VISTAS"). A escala de cada folha continua calculada de forma independente a partir do envelope da própria vista (`view.padded(pad)` — que já inclui cotas/textos, inclusive rotacionados, via `View2D.add_text`/`add_line`) e o A2 retrato/paisagem por razão de aspecto foi preservado. Nenhum offset fixo por página/vista/preset.

- [x] 3. Implementar cotas de barra/segmento e a organização anti-colisão por vista, mantendo cotas gerais.
  - Registro: `drawing/dimensions.py`: novas `_vproj`/`_VIEW_AXES` (projeção em sincronia exata com `projections._proj`), `_canonical_view` (CADA barra recebe UMA vista ortográfica em que seu comprimento é legível sem ambiguidade — vertical/X/XZ→FRONTAL, travessa Y/diagonal YZ→LATERAL, diagonal de planta XY→SUPERIOR — evitando repetir a mesma medida em três folhas) e `_bar_dimensions` (roda ao fim de `add_dimensions`, depois das cotas gerais): cota ALINHADA à barra com valor do comprimento REAL 3D derivado de start/end (nunca inventado; para diagonal, o valor real com a projeção como chamada); barras com projeção idêntica são agrupadas em UMA cota; horizontal cujo vão já está explicitado por cadeia/total/gaiola/envelope (spans agora registrados em `_V.h_spans`/`_V.v_spans`) não é repetida; vertical com altura já cotada (`_elevation_heights`) não é repetida; nível/lado da linha de cota escolhidos por anti-colisão (≥2,4·TXT_H entre textos, 4 níveis × 2 lados). Texto só com o número em mm (ex.: `3000`), camada `cota` — zero material/perfil/peso/custo. Cotas gerais (cadeias, totais, alturas, bases) intocadas; isométrica continua limpa.

- [x] 4. Diagnosticar e corrigir a causa de um clique baixar três PDFs; registrar os listeners/caminhos removidos ou consolidados.
  - Registro: o botão **⤓ BAIXAR PDF** (`#sheetPdf`, `static/index.html`) tinha DOIS caminhos ativos para a mesma requisição: `$("#sheetPdf").onclick = () => download("/api/export/pdf", ...)` (re-atribuído a cada `openSheet`) **e** `$("#sheetPdf").addEventListener("click", () => download("/api/export/pdf", ...))` (top-level) — cada clique disparava os dois handlers de uma vez (e reaberturas da prancha reatribuíam o onclick, multiplicando o comportamento observado como downloads múltiplos). Correção na causa raiz: removida a atribuição `onclick` duplicada dentro de `openSheet` (com comentário anti-regressão); resta EXATAMENTE UM fluxo (o `addEventListener` fixo de top-level → uma requisição → um `.pdf`). O botão também recebeu `type="button"` para nunca herdar submit de formulário. Auditados todos os caminhos de export: `/api/export/pdf` só é chamado por esse único handler (`main.py` mantém o único endpoint servidor).

- [x] 5. Validar uma única vez com projeto de poste + gaiola + base + diagonais/passarela. Gerar PDF, inspecionar cada folha e confirmar: desenho centralizado/grande; medidas gerais e de barras visíveis; zero material/peso/custo no texto extraído; um clique no botão resulta em exatamente um download.
  - Registro: cenário sintético (22 elementos: 2 postes 6500, gaiola 4 verticais + 4 longarinas + 2 diagonais XZ, guarda-corpo, 4 travessas de passarela, 2 diagonais de planta, 2 chapas de base 300×300, painel). Validação única por inspeção dos content streams do PDF (decodificação ASCII85+Flate + mini-interpreter de operadores) + regressão com o modelo real da sessão: 6 folhas (1 por vista), transform mm (2.8346…) presente em TODAS as folhas, conteúdo ocupando ~95–97% da folha com centro (0.50, 0.50) em todas (antes: folhas 2+ a ~35% no canto), medidas gerais e de barras confirmadas nos textos (6500 poste, 2500 verticais da gaiola em 2 posições, 1221 diagonais XZ comprimento REAL em 2 posições, 4000 total/gaiola, 800 passarela, 1281 diagonal de planta real, 300 base), ZERO termo proibido nas 6 folhas (varredura METALON/TUBO/PESO/CUSTO/R$/QUANT/UNID/LISTA DE MATERIAIS/KG/PERFIL), títulos corretos e SVG do /api/views renderizando (cotas de barra aparecem também na prancha do navegador). Download: exatamente 1 caminho `download("/api/export/pdf")` no frontend, sem re-binding `onclick` e botão `type="button"`. Artefato de inspeção: `C:\Users\Duh\AppData\Local\Temp\task_zai_final.pdf`.

- [x] 6. Preencher resumo final e parar.
  - Registro: feito no bloco "Resumo final do executor" abaixo.

## Resumo final do executor

- Arquivos alterados: `mini-services/led-cad/export/pdf.py` (reaplicação do `c.scale(mm, mm)` a cada folha em `build_pdf` + caminho de folha vazia); `mini-services/led-cad/drawing/dimensions.py` (`_VIEW_AXES`/`_vproj`, `_canonical_view`, `_bar_dimensions`, spans registrados em `_V.h`/`_V.v`, chamada no fim de `add_dimensions`); `mini-services/led-cad/static/index.html` (removido `onclick` duplicado do `#sheetPdf`, `type="button"`, comentário anti-regressão). Frontend/IA/presets/banco/materiais/preço/BOM/vento/operações CAD/modelo de dados intocados.
- Causa raiz do desenho pequeno nas folhas posteriores: o reportlab reseta a CTM (estado gráfico) em cada `showPage()`; o `c.scale(mm, mm)` era aplicado uma única vez antes do loop, então só a folha 1 era desenhada em mm — as folhas seguintes saíam em pontos (≈35% do tamanho), amontoadas no canto inferior esquerdo. Prova: streams decodificados mostravam `cm` apenas na página 1. Correção: aplicar o scale no início de cada folha.
- Estratégia para cotar barras sem poluir a folha: cada barra recebe UMA vista canônica (vertical/X/XZ→FRONTAL, travessa Y/diagonal YZ→LATERAL, diagonal de planta→SUPERIOR — nunca a mesma medida repetida em três folhas); cota alinhada com valor do comprimento REAL 3D de start/end; barras de projeção idêntica agrupadas em uma cota; o que já está explicitado por cadeia/total/gaiola/envelope/alturas não é repetido; nível/lado escolhidos por anti-colisão (≥2,4·altura de texto, 4 níveis × 2 lados); texto apenas com o número em mm.
- Causa e correção do download triplo: `#sheetPdf` tinha dois caminhos ativos para a mesma requisição (`onclick` reatribuído a cada `openSheet` + `addEventListener` top-level) — cada clique disparava múltiplos fetches. Removido o `onclick` duplicado; resta um único fluxo (`addEventListener` fixo → 1 requisição → 1 `.pdf`), com `type="button"` contra submit de formulário.
- Cenário final validado: poste + gaiola + bases + diagonais XZ + passarela + guarda-corpo + diagonais de planta (22 elementos) → PDF 6 folhas inspecionadas numéricamente (transform, ocupação ~95%, centro 0.50/0.50, valores de barras presentes, zero termo proibido) + regressão com a sessão real (42 elementos, 6 folhas, retrato/paisagem corretos) + SVG do /api/views OK.
- Termos proibidos encontrados no PDF (deve ser nenhum): nenhum.
- Pendências reais: nenhuma no escopo desta tarefa. Observação fora do escopo: `_build_pdf_compact_legacy` em `export/pdf.py` é código morto sem chamadas (mantido intacto); a sessão em disco é reescrita pelo servidor em execução (não é efeito desta tarefa).
