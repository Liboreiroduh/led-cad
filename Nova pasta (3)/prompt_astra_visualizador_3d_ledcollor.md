# PROMPT PARA ASTRA — VISUALIZADOR 3D LED COLLOR (NETLIFY)

Quero que você atue como arquiteto de software + desenvolvedor front-end 3D e CONSTRUA o projeto completo no workspace atual do VS Code.

## OBJETIVO

Criar uma página única, pronta para deploy no Netlify, que apresente em 3D um projeto de painel de LED em formato "V".

A página deve funcionar como uma apresentação técnica interativa para o cliente abrir por link no navegador, tanto no desktop quanto no celular.

Não quero apenas um mockup ou uma imagem 3D. Quero um modelo tridimensional real, manipulável pelo usuário no navegador.

## REFERÊNCIA

Use como referência principal o arquivo:

`Esboco_LED_3x4m_LedCollor.pdf`

Se o PDF estiver disponível no workspace, leia-o e use as páginas como referência visual.

O PDF é apenas referência técnica de montagem e NÃO é um desenho estrutural final.

## GEOMETRIA PRINCIPAL DO PROJETO

Todas as medidas abaixo estão em milímetros.

### Faces de LED

O projeto possui DUAS faces de LED formando um "V".

Cada face:

- largura: 2880 mm
- altura: 3840 mm
- composta por 12 gabinetes
- distribuição: 3 colunas x 4 linhas
- cada gabinete: 960 x 960 mm

As duas faces se encontram no vértice frontal central.

### Geometria superior

Na vista superior:

- comprimento de cada face: 2880 mm
- abertura máxima traseira entre as extremidades das duas faces: 2000 mm
- profundidade aproximada frente-fundo: 2701 mm
- vértice do "V" voltado para a frente

Não invente um ângulo arbitrário.

Calcule geometricamente a posição e o ângulo das duas faces a partir destas dimensões, priorizando:
- lado de cada face = 2880 mm
- abertura traseira = 2000 mm

A profundidade resultante deve ficar aproximadamente compatível com 2701 mm.

### Altura

- parte inferior do painel: 2500 mm acima do nível do solo
- altura do painel: 3840 mm
- altura total aproximada até o topo: 6340 mm

### Poste

- poste tubular central
- diâmetro: 150 mm
- altura visível até a parte inferior do painel: 2500 mm

O poste deve ficar centralizado aproximadamente na região do encontro das duas faces.

### Base

- placa circular
- diâmetro: 600 mm
- espessura: 25 mm
- 4 chumbadores distribuídos simetricamente
- tubo central de 150 mm

Não é necessário modelar rosca real dos parafusos; geometria visual simples é suficiente.

## TECNOLOGIA

Use preferencialmente:

- Vite
- JavaScript ou TypeScript
- Three.js
- OrbitControls

Evite frameworks pesados se não forem necessários.

O projeto deve ser completamente estático e não deve depender de backend, banco de dados ou API.

Preciso conseguir publicar diretamente no Netlify.

## ESTRUTURA DE ENTREGA

Crie os arquivos necessários, incluindo no mínimo:

- `package.json`
- `index.html`
- `src/main.js` ou equivalente
- arquivos CSS necessários
- `netlify.toml`
- `.gitignore`
- `README.md`

O comando deve funcionar:

```bash
npm install
npm run dev
npm run build
```

A build de produção deve sair em:

```text
dist/
```

## EXPERIÊNCIA VISUAL

A página deve parecer uma apresentação técnica premium, limpa e moderna.

Layout sugerido:

```text
┌────────────────────────────────────────────────────┐
│ LED COLLOR                                         │
│ ESBOÇO LED 3X4M — VISUALIZAÇÃO 3D                 │
│ Painel em V • 2880 x 3840 mm por face             │
├────────────────────────────────────────────────────┤
│                                                    │
│                                                    │
│                 MODELO 3D                          │
│                                                    │
│                                                    │
├────────────────────────────────────────────────────┤
│ Arraste para girar • Scroll/pinça para zoom        │
└────────────────────────────────────────────────────┘
```

A área 3D deve ocupar a maior parte da tela.

Fundo claro ou cinza muito suave.

Interface elegante, industrial e técnica.

## MODELO 3D

Quero visualizar claramente:

1. as duas faces em V;
2. os 12 gabinetes de cada face;
3. separação visual entre gabinetes;
4. estrutura/perfil externo das faces;
5. poste central;
6. placa de base;
7. quatro chumbadores;
8. piso/plano de referência;
9. indicação clara de frente e traseira.

### Aparência dos painéis

As faces podem utilizar:
- preto/grafite escuro;
- leve aspecto de painel LED;
- grid sutil dos gabinetes;
- moldura metálica discreta.

Evite aparência de desenho infantil ou low-poly exagerado.

### Estrutura

O modelo deve ter volume real.

Não faça apenas planos sem espessura.

Use espessuras visuais coerentes para:
- gabinetes;
- molduras;
- perfis;
- base.

Essas espessuras são apenas representativas quando não estiverem definidas no PDF.

## CÂMERA E INTERAÇÃO

Implementar:

- rotação por mouse;
- rotação por toque;
- zoom;
- pan moderado;
- damping/suavização;
- câmera com perspectiva;
- limites para evitar que o usuário se perca completamente.

Adicionar botões:

- Perspectiva
- Frontal
- Lateral
- Superior
- Reset

Ao clicar, animar suavemente a câmera para a posição correspondente.

## MODO DE VISUALIZAÇÃO

Adicionar controles discretos para:

- Painel completo
- Somente estrutura
- Wireframe

Se possível sem comprometer estabilidade, incluir também:

- botão "Explodir modelo"

Nesse modo, afastar levemente:
- faces;
- estrutura;
- poste;
- base

para o cliente perceber os componentes.

Não transforme isso em um CAD completo. É uma apresentação interativa de página única.

## COTAS

Mostrar algumas cotas principais no ambiente 3D ou como overlay:

- 2880 mm
- 3840 mm
- 2500 mm
- abertura traseira 2000 mm
- poste Ø150 mm
- base Ø600 mm

As cotas podem ser ativadas/desativadas por um botão:

`Mostrar medidas`

Priorize legibilidade.

## PAINEL DE INFORMAÇÕES

Adicionar uma pequena ficha técnica lateral ou inferior:

```text
PAINEL LED EM V

Faces: 2
Dimensão por face: 2880 x 3840 mm
Gabinetes por face: 12
Gabinete: 960 x 960 mm
Altura livre: 2500 mm
Abertura traseira: até 2000 mm
Poste: Ø150 mm
Base: Ø600 x 25 mm
```

No mobile ela deve recolher ou ir para baixo do viewer.

## AVISO OBRIGATÓRIO

Na parte inferior da apresentação colocar em vermelho:

"Essa é apenas uma referência técnica para montagem, não serve como desenho estrutural final."

## RESPONSIVIDADE

O site precisa funcionar corretamente em:

- desktop
- notebook
- tablet
- celular

No celular:

- interação touch deve funcionar;
- o canvas não pode estourar a tela;
- botões precisam ser fáceis de tocar;
- painel de informações não pode bloquear o modelo.

## PERFORMANCE

O site deve abrir rápido.

Não use modelos externos gigantes.

Preferencialmente toda a geometria deve ser gerada proceduralmente em Three.js.

Não depender de Blender.

Não depender de arquivos GLB externos, salvo se você realmente gerar um e justificar.

## ARQUITETURA DO CÓDIGO

Não coloque tudo em um único arquivo gigantesco.

Separe de forma razoável, por exemplo:

```text
src/
  main.js
  scene/
    createScene.js
    createLedStructure.js
    cameraViews.js
  ui/
    controls.js
  styles/
    main.css
```

Pode adaptar essa estrutura se encontrar uma organização melhor.

## REGRA IMPORTANTE SOBRE GEOMETRIA

O modelo deve ser construído a partir de constantes dimensionais.

Crie algo conceitualmente semelhante a:

```js
const PROJECT = {
  faceWidth: 2880,
  faceHeight: 3840,
  cabinetWidth: 960,
  cabinetHeight: 960,
  columns: 3,
  rows: 4,
  rearOpening: 2000,
  freeHeight: 2500,
  postDiameter: 150,
  baseDiameter: 600,
  baseThickness: 25,
};
```

Utilize uma escala consistente para converter milímetros para unidades do Three.js.

Exemplo aceitável:

```text
1000 mm = 1 unidade Three.js
```

A geometria inteira deve derivar desses parâmetros.

Não espalhe números mágicos pelo código.

## NETLIFY

O projeto precisa ficar pronto para eu simplesmente:

1. enviar para GitHub;
2. conectar o repositório no Netlify;
3. usar:

```text
Build command: npm run build
Publish directory: dist
```

Crie `netlify.toml` configurado corretamente.

## QUALIDADE

Quero que você trate isso como uma aplicação demonstrativa real.

Não entregue somente código parcialmente funcional.

Faça o seguinte ciclo:

1. analise o PDF e os requisitos;
2. defina a geometria;
3. implemente;
4. rode `npm install`;
5. rode o projeto;
6. corrija erros;
7. rode `npm run build`;
8. corrija qualquer problema de build;
9. revise responsividade;
10. revise câmera;
11. revise geometria;
12. entregue o projeto funcionando.

## NÃO FAÇA

- não crie backend;
- não crie login;
- não crie banco;
- não use React apenas por hábito;
- não transforme em sistema multi-página;
- não use imagens renderizadas no lugar do 3D real;
- não invente cálculo estrutural;
- não declare que a estrutura é estruturalmente dimensionada;
- não substitua as medidas fornecidas por aproximações arbitrárias.

## RESULTADO ESPERADO

Ao abrir a URL publicada no Netlify, o cliente deve imediatamente ver uma apresentação elegante do:

**ESBOÇO LED 3X4M — PAINEL EM V**

e conseguir usar o mouse ou o dedo para girar o painel e compreender espacialmente o projeto.

A prioridade é:

1. geometria correta;
2. interação 3D;
3. apresentação profissional;
4. responsividade;
5. deploy simples no Netlify.

Comece agora implementando diretamente no workspace.

Não fique apenas explicando o que pretende fazer.

Crie os arquivos, execute o projeto, teste e corrija até a build estar funcionando.
