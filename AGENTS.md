# AGENTS.md — política do repositório

## Regra permanente: Git sempre atualizado (commit + push)

Toda sessão de trabalho neste projeto (humana ou de IA) DEVE terminar com o
estado local publicado no GitHub:

1. `git add` das mudanças da tarefa (código, documentação e dados de
   aplicação em `mini-services/led-cad/data`).
2. Commit com mensagem descritiva do que foi feito.
3. `git push` para `origin/main`.
4. Confirmar com `git status -sb` que não há nada pendente
   (sem "ahead"/"behind" e sem arquivos relevantes não rastreados).

Motivo: o GitHub é a fonte de comparação com revisores externos (ex.: GPT).
Nenhum trabalho deve ficar apenas local.

Artefatos locais (logs, `*.pid`, `.tmp.*`, `tool-results/`) ficam cobertos
pelo `.gitignore` e não sobem.

## Contexto rápido do projeto

- LED Structure CAD: protótipo local em Python/FastAPI para esboços de
  estruturas para painéis de LED. Documentação canônica em
  [mini-services/led-cad/CANONICAL_PROJECT_CONTEXT.md](mini-services/led-cad/CANONICAL_PROJECT_CONTEXT.md).
- Execução (processo único): `cd mini-services/led-cad && py main.py`
  → aplicativo em http://localhost:3000 (frontend + API no mesmo processo).
- O shell Next.js da raiz é proxy legado, FORA do fluxo obrigatório.
