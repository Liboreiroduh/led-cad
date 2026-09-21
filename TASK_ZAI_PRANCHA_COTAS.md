# Tarefa Z.ai — prancha dimensional completa, sem materiais

## Papel e limite

Você é o executor. Corrija somente a geração de vistas/cotas e do PDF do serviço Python em `mini-services/led-cad`. Não redesenhe o frontend, não altere IA, presets, modelo de dados, banco, materiais internos, orçamento, vento ou o motor 3D.

Objetivo: a prancha é um **esboço geométrico para a empresa de estrutura**. Ela deve mostrar todas as cotas necessárias para reproduzir a posição e as dimensões da estrutura, mas nunca especificação de material, perfil, peso, custo, lista de corte ou quantidade de peças.

## Problema atual

O PDF já passou para uma vista por página e removeu textos de material. Porém ele está cotando pouco: em especial só a primeira folha/vista recebe parte das cotas. A pessoa que recebe a prancha precisa enxergar claramente largura da estrutura, altura, profundidade, dimensões e posição das bases, altura de postes, gaiola e espaçamentos — em cada vista pertinente.

## Regra de produto (não negociar)

- Mostrar: **Barra**, **Poste**, **Chapa geométrica**, **Base**, **Gaiola**, linhas, contornos e valores em mm.
- Não mostrar em nenhum PDF/prancha: `METALON`, `TUBO`, códigos de perfil, espessura/tipo comercial, kg, peso, custo, BOM, orçamento, lista de materiais, corte ou quantidade de peças.
- A estrutura é a referência principal. O painel LED pode aparecer apenas como referência visual tracejada; suas medidas não podem substituir as cotas da gaiola/estrutura/base.
- Nenhuma cota pode ser hardcoded para um preset. Todas devem ser derivadas do `ProjectModel` e das coordenadas reais após edições manuais ou da IA.

## Escopo técnico esperado

Arquivos candidatos principais:

- `drawing/dimensions.py`: política única para gerar cotas geométricas por vista.
- `drawing/projections.py`: somente se for necessário expor geometria projetada correta às cotas.
- `export/pdf.py`: renderização, zona útil, escala, colisão e legibilidade no A2.
- `main.py`: somente se uma vista não estiver chegando à exportação.

Não eliminar a operação existente `set_post_height` nem alterar a semântica do editor.

### Matriz mínima de cotas

Para cada vista exportada, gerar somente cotas visíveis/pertinentes à projeção; não repetir uma dimensão que fique em zero ou seja visualmente idêntica na mesma folha.

| Vista | Cotas obrigatórias quando existirem |
|---|---|
| Frontal e traseira | largura total da **estrutura**, altura total, cota do solo até apoio/painel, altura dos postes, distância entre postes/colunas, largura/altura da gaiola, cadeia dos vãos ou módulos que definam o quadro. |
| Lateral | profundidade total da estrutura, profundidade da gaiola/passarela/base, alturas principais e afastamentos em Y. |
| Superior e inferior | largura × profundidade do envelope estrutural, dimensões em planta das bases/chapas, posições e espaçamento dos postes e travessas relevantes. |
| Isométrica | manter leitura limpa; usar apenas chamadas dimensionais que acrescentem informação e não colidam. As cotas completas pertencem às ortográficas. |

Além da matriz, cotar geometrias que mudem o desenho de forma relevante: balanços, avanços de passarela, degraus de altura, diagonais definidas por pontos extremos, chapas/base e suportes fora do envelope principal. Não cotar cada barra repetida se ela tiver a mesma posição explicada pela cadeia de cotas; não gerar uma nuvem ilegível.

### Política de legibilidade

1. Uma vista por folha A2, retrato ou paisagem conforme o envelope projetado.
2. As linhas de extensão e textos devem ficar dentro da área útil da folha, sem cair no rodapé/cabeçalho.
3. Separar níveis de cotas: dimensão local mais próxima do desenho, cadeia depois, total mais externa. Usar offsets calculados, não números mágicos dependentes de 4×2.
4. Detectar/evitar sobreposição simples de textos e linhas de cota: caso uma dimensão esteja muito próxima da próxima, afastar para o próximo nível externo.
5. Fonte de cotas legível impressa em A2; nunca reduzir para caber. Se a geometria for alta/estreita, usar A2 retrato e aproveitar a folha.
6. A caixa usada para escala da vista deve incluir as cotas, chamadas e textos. Não pode haver dimensão cortada.
7. Não remover as cotas existentes apenas para "limpar" a página; corrigir a política para organizar e ampliar.

## Roadmap de execução e registro

Atualize esta seção durante o trabalho. Marque `[x]` somente após a etapa estar concluída e escreva, abaixo dela, os arquivos e decisões reais. Não criar relatório separado.

- [x] 1. Mapear o fluxo atual `ProjectModel → projeção → dimensions → View2D → PDF` e registrar abaixo por que as cotas somem nas demais vistas.
  - Registro: Fluxo real: `main.py::build_views` → `project_view` (projeção) → `add_dimensions` → `build_pdf` (`export/pdf.py`, 1 vista/folha). Causas das cotas sumirem: (a) `add_dimensions` retorna cedo para `INFERIOR` e `ISOMETRICA` — folhas sem nenhuma cota; (b) `TRASEIRA` projeta u=-x, mas as cotas usavam xs positivos → cadeia/total espelhados fora do desenho; (c) `LATERAL` coletava só `start.y` das travessas (todas na mesma borda) → lista com 1 elemento → cadeia e total nunca desenhados, sobrando 1–2 cotas; (d) sem cotas de chapas de base, altura de postes, profundidade da gaiola e envelopes; (e) `View2D.add_text` não expandia `box` → textos fora da caixa de escala (corte no PDF); (f) níveis fixos 160/140 colidindo com o título a -170.
  - Registro:

- [x] 2. Implementar a política paramétrica de cotas por vista, cobrindo a matriz mínima e geometria especial sem material/perfil.
  - Registro: `drawing/dimensions.py` reescrito como política única paramétrica. Classe `_V`: dedupe de valor por folha/orientação (dimensão visualmente idêntica não repete) + alocação de níveis sem colisão (afasta para o nível externo em passos derivados de `TXT_H`; sem números mágicos 160/140). Matriz: FRONTAL/TRASEIRA — cadeia de vãos do quadro (força segmentos, `_MAX_CHAIN=8` acima vira só total), vão total, gaiola (barras) e envelope (com chapas) + alturas gaiola/vão livre/total à esquerda e altura de postes à direita (degraus viram níveis); LATERAL — cadeia em Y de TODOS os pontos das barras (antes só `start.y` das travessas, que estavam na mesma borda), profundidades gaiola/envelope, alturas e profundidade em planta das bases; SUPERIOR/INFERIOR — cadeia de postes em X, afastamentos em Y, profundidades e bases em planta (largura no topo × profundidade à esquerda, um cota por tamanho distinto); ISOMETRICA limpa por design. Correções de geometria: espelhamento de TRASEIRA (u=-x) e INFERIOR (v=-y) respeitado via tabela `_SIGNS` (antes as cotas da traseira eram desenhadas fora do desenho); `_vertical_zs` agora usa start E end dos verticais (antes só start → altura da gaiola zerada); filtro do quadro por `role=="vertical"`; fallback para desenho livre (IA) mantido; chumbadores ficam fora dos envelopes (descem abaixo do solo). Nenhum perfil/material/peso: só coordenadas do `ProjectModel`.
  - Registro:

- [x] 3. Ajustar a composição da página A2 para garantir escala, fonte legível, afastamento de cotas e ausência de corte/sobreposição.
  - Registro: `drawing/projections.py`: `View2D.add_text` agora expande `box` com a extensão estimada do texto (largura ≈ 0,62·s por caractere, respeitando `anchor` e rotação) — a caixa de escala da folha passa a incluir cotas/rótulos/títulos, acabando o corte na borda. `view_title` ganhou offset padrão derivado dos níveis de cota (não colide mais com a cadeia). `export/pdf.py`: piso de fonte de cotas elevado para 5,0 (demais textos 4,2) — a fonte nunca encolhe para caber; A2 retrato automático para geometria alta mantido. `main.py` não precisou de mudança (todas as vistas já chegam ao PDF). Auditoria numérica de folha (retângulos de cada texto projetados no papel com o piso de fonte): 0 cortados e 0 sobrepostos nas 12 folhas dos 2 cenários; `build_views` do SVG (frontend) segue funcionando.
  - Registro:

- [x] 4. Fazer uma única validação final (não testar a cada microedição): gerar PDF de um preset com poste/base/gaiola e um projeto de geometria diferente; confirmar visualmente todas as folhas e buscar no texto extraído que não há termos de material/peso/custo.
  - Registro: Validação única com script temporário (removido após; não tocou em `data/_session.json` nem instanciou `ProjectStore`). Cenário A: `REF_4000X2000` (outdoor, 2 postes/bases/gaiola) editado com a operação real `set_post_height` em POSTE-01 → 3600 mm (53 elementos transladados, POSTE-02 linkado) — as cotas FRONTAL/TRASEIRA passaram a conter 3600/3625/5625 automaticamente (critério 2 OK). Cenário B: `REF_2000X2000` (rental, geometria diferente). 2 PDFs × 6 folhas; cotas de cota-texto presentes em TODAS as ortográficas dos dois cenários (isométrica limpa por design); busca no texto extraído (pymupdf) de METALON/TUBO/PERFIL/KG/PESO/CUSTO/R$/BOM/QUANT/LISTA DE MATERIAIS: zero ocorrências nas 12 folhas. Conferência visual das folhas feita por auditoria geométrica no papel (renderização em PNG não é suportada neste ambiente): 0 textos cortados, 0 sobreposições, fonte de cota ≥ 5 no papel.
  - Registro:

- [x] 5. Preencher o resumo final abaixo e parar. Não iniciar melhorias fora deste escopo.
  - Registro: Resumo preenchido abaixo. Nenhum trabalho fora do escopo foi iniciado.

## Critérios de aceite

1. Em um painel com poste e base, a prancha deixa inequívocos: largura e altura da estrutura, altura do poste, vão ao solo, largura/profundidade da base e profundidade da gaiola.
2. Ao editar a altura do poste, as cotas do PDF refletem a nova geometria automaticamente.
3. Toda vista aplicável contém suas próprias cotas estruturais legíveis, sem depender da primeira página.
4. Não há corte, textos empilhados ou cotas fora da moldura.
5. O PDF não contém material/perfil/peso/custo/BOM em texto visível.
6. O frontend e a IA não foram alterados.

## Resumo final do executor

Preencha ao terminar:

- Arquivos alterados: `mini-services/led-cad/drawing/dimensions.py` (política de cotagem reescrita: matriz por vista, dedupe, níveis sem colisão, sinais de projeção, correção de `_vertical_zs`); `mini-services/led-cad/drawing/projections.py` (apenas `View2D.add_text` expande a caixa de escala; `view_title` com offset derivado); `mini-services/led-cad/export/pdf.py` (apenas piso de fonte das cotas = 5,0). Frontend, IA, presets, modelo de dados, operações (`set_post_height` intacto), BOM/orçamento e motor 3D: intocados.
- Política de cotagem implementada: única e paramétrica em `add_dimensions` — por vista ortográfica: cadeia local de vãos/afastamentos no nível mais próximo, totais de quadro/gaiola/envelope nos níveis externos; alturas (gaiola → vão livre → total) à esquerda e alturas de poste (com degraus) à direita nas elevações; nas plantas, cadeias de postes (X) e travessas (Y) + bases em planta (largura×profundidade, um cota por tamanho distinto); isométrica limpa. Níveis derivados de `TXT_H` (sem números mágicos), afastamento automático em colisão, dedupe de valores por folha, cadeia limitada a 8 pontos. Tudo derivado das coordenadas reais do `ProjectModel` (preset, edição manual ou IA) — nada hardcoded por preset.
- Cenários validados: (A) `REF_4000X2000` + `set_post_height` POSTE-01→3600 — cotas 3600/3625/5625 refletem a edição; (B) `REF_2000X2000` (rental). 6 folhas por PDF, todas as ortográficas com as próprias cotas; auditoria de papel: 0 cortes, 0 sobreposições; SVG do editor (`build_views`) segue OK; `main.py` importa sem erros.
- Resultado da busca de termos proibidos: 0 ocorrências de METALON, TUBO, PERFIL, KG, PESO, CUSTO, R$, BOM, QUANT e LISTA DE MATERIAIS no texto extraído das 12 folhas (rótulos de perfil/ID continuam visíveis só no editor/SVG, como antes).
- Pendências reais (se houver): a conferência "visual" das folhas foi feita por auditoria geométrica (este ambiente não renderiza imagem para inspeção humana) — recomenda-se uma olhada humana em um PDF real antes de uso produtivo. A isométrica continua sem cotas por decisão da matriz (leitura limpa). Nada mais pendente dentro do escopo.
