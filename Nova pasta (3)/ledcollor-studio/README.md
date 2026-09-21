# LedCollor Studio — Protótipo CAD

Base de trabalho para o Z.AI desenvolver um CAD simplificado para painéis LED.

## Iniciar no Z.AI

1. Abra a pasta `ledcollor-studio/` como projeto no Z.AI.
2. Selecione o modelo **GPT-5.3 Fast**.
3. Cole o conteúdo de [`zai/ORCHESTRATOR_PROMPT.md`](zai/ORCHESTRATOR_PROMPT.md) na primeira mensagem.
4. Peça: **“Inicie a Task 01.”**

O Z.AI deve executar somente a task ativa em [`zai/tasks/`](zai/tasks/), validar visualmente e atualizar o status antes de seguir.

## Regra do protótipo

Construir → abrir no navegador → publicar → receber feedback → ajustar.

Evite cobertura extensa de testes, mocks e refatorações antecipadas. Use verificações curtas: aplicação inicia, console sem erros críticos, fluxo principal no desktop e no celular, build concluída e link público quando a publicação estiver na fase ativa.

## Estado inicial

- Fase atual: **Fase 1 — editor local**
- Task ativa: [`01-bootstrap-e-canvas.md`](zai/tasks/01-bootstrap-e-canvas.md)
- Projeto de referência: [`examples/painel-led-v.json`](examples/painel-led-v.json)
- Referência visual: o visualizador 3D do painel LED em V já existente na pasta-pai deste workspace.

## Estrutura esperada após a Fase 1

```text
frontend/       Aplicação Vite e editor visual
backend/        Reservado para a Fase 2 (FastAPI)
shared/         Schema JSON e regras de geometria
zai/            Roadmap, contexto e tasks do orquestrador
examples/       Projetos paramétricos iniciais
```
