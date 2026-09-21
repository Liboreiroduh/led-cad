# Z.ai — auditoria e unificação da interação de IA

**Status: concluído**

**Arquivos alterados:**
- `services/ai_intent.py` (NOVO) — intenção canônica única (`new`/`local_edit`/`global_resize`), contexto estrutural do modelo (painel, módulo de gabinete deduzido das grades, gaiola, postes, passarela, guarda-corpo), booleanos mandatórios `cage/walkway/guardrail` (guarda-corpo exige passarela), bloco de contratos para o prompt e JSON da intenção. Ponto único `build_intent(text, model, form)` usado por Formulário e Copiloto.
- `services/ai_prompts.py` — `build_system_prompt(..., intent=)` injeta o bloco `INTENÇÃO CANÔNICA` (contexto atual + alvo + contratos: features `false` obrigatórios, mesma cota painel/postes/gaiola, local_edit preserva, global_resize substitui UMA estrutura via `__blank`, `add_grid` e receitas); `build_user_message(..., intent=)` embute o JSON da intenção. Prompt ativo sem instrução de perfil/metalon/material/peso/preço/quantitativo (legado mantido apenas como referência).
- `main.py` — `/api/ai/command` e `/api/ai/plan` usam a MESMA preparação (`build_intent` → `build_system_prompt(intent=…)` → `build_user_message(intent=…)`); pedidos `new`/`global_resize` nunca caem no parser rápido (o fallback offline não desenha estruturas — sem geometria divergente); erros concretos preservam o projeto.
- `static/index.html` — Formulário rápido envia intenção estruturada (`form: {cols, rows, gw, gh, gd, pd, posts, cage_d, cage, walk, rail}`) com os três booleanos SEMPRE explícitos (inclusive falsos) e o texto passando a afirmar "SEM gaiola/SEM passarela/SEM guarda-corpo" quando desmarcados.

## Objetivo

Reconstruir a coerência entre **Formulário rápido**, **Copiloto IA**, prompts,
operações CAD, preview e aplicação. A IA deve voltar a raciocinar como
projetista de esboço geométrico, com contexto rico da ferramenta, mas sem
material, preço, peso, quantitativo ou orçamento.

O problema atual não é um pedido isolado: as rotas evoluíram separadamente e
produzem comportamentos incompatíveis. Exemplo observado: pedir painel 4×2 a
partir de 2×1 pode duplicar a estrutura; formulário com gaiola/passarela/
guarda-corpo desmarcados pode resultar em estrutura que os contém.

## Escopo canônico

Trabalhe somente em `mini-services/led-cad`.

Leia antes de editar, nesta ordem:

1. `main.py` — `/api/ai/command`, `/api/ai/plan`, preview e aplicação.
2. `services/ai_prompts.py` — `build_system_prompt`, `build_user_message` e
   o prompt legado, somente como fonte de conhecimento perdido.
3. `services/ai_llm.py` — contrato do provedor; não altere conexão/chave.
4. `core/ai_ops.py` e `core/operations.py` — operações aceitas e suas regras.
5. `static/index.html` — modal Novo/Formulário rápido e Copiloto.

Não mapear o resto do repositório nem tocar em PDF, desenho técnico, presets,
persistência de chaves, catálogo de provedores ou frontend fora dessas áreas.

## Resultado de arquitetura obrigatório

### 1. Uma intenção canônica antes da IA

Crie uma única representação interna (função/helper simples, sem banco e sem
nova dependência) para pedido de criação/edição, utilizada tanto pelo
Formulário rápido quanto pelo Copiloto. Ela deve conter, quando aplicável:

- intenção: `new`, `local_edit` ou `global_resize`;
- painel: largura, altura, profundidade, módulo de gabinete, colunas/linhas;
- instalação: altura da base/pé-direito, postes e posição conhecida;
- recursos booleanos explícitos: `cage`, `walkway`, `guardrail`;
- contexto do modelo atual: painel visual, gaiola, grades de gabinetes,
  postes, passarela e guarda-corpo existentes.

O formulário deve enviar esses valores estruturados; não depender somente de
uma frase montada para a IA interpretar. O Copiloto continua aceitando texto
livre, mas deve derivar a mesma intenção/contexto antes de montar o prompt.

### 2. Contratos sem ambiguidade

Os booleanos do formulário são mandatórios:

- `cage:false` → não criar gaiola nem grades de gabinetes;
- `walkway:false` → não criar passarela;
- `guardrail:false` → não criar guarda-corpo;
- guarda-corpo nunca existe sem passarela.

Para painel elevado, `set_panel.ground_clearance`, topo dos postes e base da
gaiola devem representar a mesma cota. O painel é somente referência visual;
não é uma barra nem substitui a gaiola.

Para alteração local, preservar elementos não citados. Para redimensionamento
integral de painel/gaiola (2×1 → 4×2), gerar uma substituição controlada de
uma única estrutura: inferir módulo atual, preservar elevação/profundidade e
recursos existentes/explicitamente solicitados, remover o conjunto antigo e
criar somente o novo — nunca sobrepor duas gaiolas.

### 3. Prompt rico, focado em desenho

Recomponha `build_system_prompt` usando o conhecimento útil do prompt legado:

- sistema de coordenadas;
- semântica de painel, gaiola, grades, poste, passarela e guarda-corpo;
- operações disponíveis e formatos exatos;
- planos válidos de `add_grid` e quando usar `add_beam`;
- leitura de grupos e elementos existentes;
- receitas para painel LED, gaiola, estrutura em poste, passarela, casa,
  caixa/cubo, círculo, torre e pórtico;
- diferença entre criação, edição local e redimensionamento global;
- exemplos JSON curtos e válidos.

Remova do conteúdo enviado à IA qualquer instrução de escolher metalon/perfil,
bitola, material, peso, preço, orçamento, lista de materiais ou plano de
corte. Perfis internos podem continuar como detalhe técnico do motor, mas não
são responsabilidade da IA nem aparecem na linguagem do usuário.

Não coloque um romance no prompt: use uma seção de regras e receitas compacta,
mas suficientemente explícita para a IA operar a ferramenta sem adivinhar.

### 4. Uma única pipeline para formulário e Copiloto

Elimine divergência entre `/api/ai/command` e `/api/ai/plan` no que diz
respeito a construção de contexto, normalização, coerência geométrica e
validação. Pode haver diferença de UX:

- Formulário cria/aplica diretamente após gerar uma proposta válida.
- Copiloto sempre devolve preview e aguarda Aplicar.

Mas os dois devem usar a mesma intenção, contexto, regras de coerência e
prompt. Não deixar fallback silencioso produzir geometria diferente.

### 5. Erros e resposta ao usuário

Se a IA gerar operação inválida, mostrar o motivo concreto e preservar o
projeto. Não ocultar erro atrás de “sem alterações”. Se uma proposta for
aplicada, não emitir erro falso posterior. Não altere a camada de conexão de
IA já funcional.

## Critérios de aceite estáticos

- O texto/objeto gerado pelo Formulário contém explicitamente os três
  booleanos, inclusive quando falsos.
- Formulário e Copiloto chamam a mesma preparação de intenção/contexto.
- Não há no prompt ativo instrução sobre material, preço, peso ou quantitativo.
- O prompt ativo contém contratos claros para painel/gaiola/poste/passarela,
  `add_grid`, criação, edição local e redimensionamento global.
- Uma solicitação global 2×1 → 4×2 é encaminhada como substituição de uma
  estrutura, não como adição paralela.
- Uma solicitação local continua sem reconstruir o projeto inteiro.

## Limites de execução

- Não rode testes, build, lint, navegador, servidor, exportação, screenshots
  ou chamadas reais de IA durante a tarefa.
- Não faça revisões repetitivas nem reabra arquitetura fora do escopo.
- Edite de uma vez os arquivos necessários após a leitura indicada.
- Ao terminar, atualize este arquivo com `Status: concluído` e uma lista curta
  de arquivos alterados; não escreva relatório paralelo.
