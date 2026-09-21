# LED COLLOR — Visualizador 3D

Apresentação técnica interativa de um painel LED em V. Aplicação estática em JavaScript, Vite e Three.js, com geometria procedural, sem backend ou modelos 3D externos.

## Executar

Requer Node.js 22.12 ou superior e npm.

```bash
npm install
npm run dev
```

Abra o endereço local informado pelo Vite. Para conferir a versão de produção:

```bash
npm run build
npm run preview
```

A build gera a pasta `dist/`. O servidor de desenvolvimento aceita conexões pela rede local; use o endereço de rede informado pelo Vite para abrir em um celular conectado à mesma rede.

## Publicar no Netlify

Envie o projeto a um repositório GitHub e conecte-o ao Netlify. O arquivo `netlify.toml` já define:

| Configuração | Valor |
| --- | --- |
| Build command | `npm run build` |
| Publish directory | `dist` |
| Node.js | `22` |

Também é possível enviar a pasta `dist/` gerada para um deploy manual. Não há variáveis de ambiente ou serviços externos obrigatórios.

## Interação

- Arraste com o mouse ou um dedo para girar o modelo.
- Use a roda do mouse ou a pinça com dois dedos para aproximar e afastar.
- Use o botão direito do mouse ou dois dedos para deslocar o enquadramento.
- Os atalhos de câmera oferecem perspectiva, frontal, lateral, superior e reset, com transição suave.
- Alterne entre painel completo, somente estrutura e wireframe; ative as medidas e a vista explodida para inspecionar os componentes.

## Dimensões e cálculo do V

As dimensões principais estão centralizadas em `src/scene/project.js`. A escala é **1 unidade Three.js = 1000 mm**.

| Elemento | Dimensão |
| --- | --- |
| Faces | 2 |
| Cada face | 2880 × 3840 mm |
| Gabinetes por face | 3 colunas × 4 linhas = 12 |
| Cada gabinete | 960 × 960 mm |
| Total de gabinetes | 24 |
| Abertura traseira | 2000 mm |
| Altura livre desde o solo | 2500 mm |
| Altura total | 6340 mm |
| Poste | Ø150 mm |
| Placa de base | Ø600 × 25 mm |
| Chumbadores | 4, em disposição simétrica |

A planta é um triângulo isósceles, com lados de 2880 mm e base de 2000 mm. A profundidade e o ângulo são derivados dessas dimensões:

```text
meia abertura = 2000 / 2 = 1000 mm
profundidade = √(2880² − 1000²) = 2700,8147 mm
meio ângulo = arcsen(1000 / 2880) = 20,3175°
ângulo interno do V = 40,6350°
```

A profundidade resultante arredonda para os 2701 mm da referência. O vértice indica a frente; a abertura entre as pontas opostas indica a traseira. As juntas visuais entre gabinetes preservam a modulação de 960 mm.

As espessuras de gabinetes, molduras, perfis e detalhes de fixação sem cota específica são representativas. A base mantém a espessura definida de 25 mm. A vista explodida apenas afasta as peças para explicar sua montagem; as dimensões nominais se referem ao modelo montado.

As carcaças e os trilhos junto ao vértice possuem cortes em mitra, derivados do ângulo do V, para não atravessar a face oposta. O recuo dos montantes e das diagonais também respeita esse espaço interno.

## Referência técnica

Foi feita a leitura visual das seis páginas de `Esboco_LED_3x4m_LedCollor.pdf`:

1. Elevação de uma face: dimensões, gabinetes, altura livre e poste.
2. Elevação traseira: abertura máxima de 2000 mm e indicação de lona.
3. Vista lateral esquemática do V.
4. Perspectiva: faces, molduras, poste e base.
5. Planta: lados de 2880 mm, abertura de 2000 mm e profundidade aproximada de 2701 mm.
6. Base circular de Ø600 × 25 mm, poste Ø150 mm e quatro chumbadores simétricos.

A posição do poste na planta da página 5 difere da perspectiva da página 4. O modelo segue o pedido explícito e a perspectiva: poste próximo ao encontro frontal das duas faces. Os ângulos são calculados pelas cotas, pois as ilustrações do PDF são esquemáticas.

A lona traseira ilustrada na página 2 não integra o modelo: o escopo implementado contempla as duas faces LED e os componentes de montagem solicitados no prompt, mantendo a abertura traseira visível.

As renderizações usadas para revisar o PDF ficam em `artifacts/reference/` durante o desenvolvimento e não integram a build.

**Essa é apenas uma referência técnica para montagem, não serve como desenho estrutural final.** Não foram realizados cálculos de resistência, vento, fundações ou dimensionamento estrutural.

## Verificação

```bash
npm test
npm run build
```

Os testes de geometria verificam as dimensões e as relações do V. A compilação de produção verifica a integração dos módulos e gera os arquivos prontos para hospedagem.

Para a verificação automática no navegador, instale o Chromium uma vez e execute:

```bash
npx playwright install chromium
npm run test:browser
```

O script inicia e encerra seu próprio servidor Vite em `http://127.0.0.1:5180`; deixe essa porta livre. Ele verifica câmeras, modos, cotas, vista explodida, reset, mouse, toque, pinça, tela cheia e cinco tamanhos de tela, incluindo 320 px de largura. As capturas ficam em `artifacts/screenshots/` e não são publicadas.

## Organização

```text
src/
  main.js                      Inicialização e tratamento de falhas
  scene/
    project.js                 Constantes e trigonometria do V
    createLedStructure.js      Geometria, materiais, modos e explosão
    createScene.js             Iluminação, renderização e interação
    cameraViews.js             Enquadramento e transições
    createDimensions.js        Linhas de cota e rótulos
  ui/
    layout.js                  Apresentação e ficha técnica
    controls.js                Eventos e estados da interface
    icons.js                   Ícones vetoriais
  styles/main.css              Layout responsivo
tests/                         Geometria, câmeras e navegador
```

A renderização pausa quando a cena está parada ou a aba está oculta. Texturas e geometria são geradas localmente; a aplicação publicada não depende de fontes, modelos ou APIs externas. É necessário um navegador com WebGL 2 habilitado. Os testes mobile usam emulação no Chromium; não substituem uma verificação em cada aparelho físico.
