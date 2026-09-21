# LedCollor Studio — Frontend

Protótipo de editor CAD simplificado para painéis LED. Shell responsivo do editor com viewport, grade em milímetros e abas de vista (Frontal, Lateral, Superior e 3D).

## Requisitos

- Node.js 18+ (testado com Node 22)

## Como rodar

```bash
npm install
npm run dev
```

Abra a URL exibida no terminal (por padrão `http://localhost:5173`).

## Build de produção

```bash
npm run build
npm run preview
```

## Stack

- [Vite](https://vitejs.dev/) + TypeScript (vanilla, sem framework)
- Canvas 2D para as vistas 2D com grade adaptativa em mm
- Three.js/OrbitControls previsto para o visualizador 3D (Task 04)

## Estrutura

```
frontend/
├── index.html        # Shell do editor (barra superior, abas, viewport, painéis)
├── src/
│   ├── main.ts       # Grade em mm, pan/zoom, ferramentas e abas
│   └── style.css     # Identidade visual e layout responsivo
└── package.json
```

> **Aviso técnico:** essa é apenas uma referência técnica para montagem, não serve como desenho estrutural final.
