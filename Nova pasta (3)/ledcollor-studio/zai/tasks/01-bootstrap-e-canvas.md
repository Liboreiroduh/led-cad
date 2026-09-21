# Task 01 — Bootstrap e canvas do editor

**Status:** concluída  
**Fase:** 1 — MVP local  
**Responsável:** agente de implementação do Z.AI  
**Modelo:** GPT-5.3 Fast

## Resultado esperado

Uma aplicação Vite abre localmente com o shell responsivo do LedCollor Studio: barra superior, barra de ferramentas, viewport principal com grade de trabalho, painel de propriedades e painel inferior de estado. Ainda não é necessário desenhar o painel LED real.

## Implementar

- Criar `frontend/` como aplicação Vite JavaScript ou TypeScript.
- Criar layout de página única com identidade técnica limpa.
- Criar viewport com canvas, grade visual em milímetros e indicador de origem `(0, 0)`.
- Criar alternância visual entre as abas: Frontal, Lateral, Superior e 3D.
- Criar painel lateral de propriedades inicialmente em estado vazio: “Selecione um objeto”.
- Criar barra de ferramentas visual: selecionar, pan, cota e grade.
- Garantir que a interface se reorganize no celular sem overflow horizontal.
- Incluir o aviso técnico obrigatório na tela.
- Criar `README.md` com `npm install`, `npm run dev` e `npm run build`.

## Não implementar nesta task

- Backend, FastAPI, SQLite, autenticação ou VPS.
- IA, interpretação de texto, geração de PDF ou exportações.
- Geometria real do painel LED.
- Editor CAD avançado ou testes extensos.

## Validação mínima

- `npm install` funciona dentro de `frontend/`.
- `npm run dev` abre a aplicação.
- `npm run build` conclui.
- Revisar no navegador em uma largura desktop e em 390 px.
- Não pode haver erro crítico no console nem overflow horizontal.

## Critério de conclusão

O usuário consegue abrir uma interface de editor clara, trocar entre as quatro abas de visualização e entender onde o desenho e as propriedades aparecerão nas próximas tasks.

## Registro de conclusão

- **Status:** concluída
- **URL validada:** http://localhost:5173/ (Vite dev server; build de produção em `frontend/dist/` via `npm run build`, concluída sem erros)
- **Arquivos alterados:**
  - `frontend/package.json` (criado — Vite 6 + TypeScript)
  - `frontend/tsconfig.json` (criado)
  - `frontend/index.html` (criado — shell: barra superior, abas Frontal/Lateral/Superior/3D, viewport, toolbar, painel de propriedades, painel de estado, aviso técnico)
  - `frontend/src/main.ts` (criado — grade adaptativa em mm, origem (0,0), pan/zoom, ferramentas, troca de abas)
  - `frontend/src/style.css` (criado — identidade técnica limpa e layout responsivo)
  - `frontend/README.md` (criado — `npm install`, `npm run dev`, `npm run build`)
  - `frontend/.gitignore` (criado)
- **Limitações para revisão:**
  - A aba 3D exibe apenas um placeholder informativo ("Visualizador 3D — será implementado com Three.js na Task 04"); não há geometria nem órbita ainda.
  - Ferramentas Selecionar e Cota são visuais (sem comportamento de desenho); Pan e Grade (toggle) funcionam, com zoom pela roda do mouse e pan pelo botão do meio ou ferramenta Pan.
  - Botões Novo/Salvar/Exportar desabilitados (persistência chega na Task 06); no mobile eles ficam ocultos para a barra superior caber em 390 px.
  - Validação automatizada com Playwright em 1440×900 e 390×844: 44 checks (elementos visíveis, troca de abas, toggle de grade, coordenadas em mm, sem overflow horizontal, console sem erros críticos) — todos passaram; capturas em `validation-desktop.png` e `validation-mobile-390.png` (pasta raiz do repositório) e script em `validate-task01.mjs`.
- **Próxima task recomendada:** Task 02 — Schema e projeto exemplo (JSON versionado do painel em V carregando no painel de propriedades).

