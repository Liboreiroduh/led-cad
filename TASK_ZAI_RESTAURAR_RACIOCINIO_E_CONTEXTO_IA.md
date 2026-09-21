# Z.ai — restaurar raciocínio interno e contexto de desenho do Copiloto

**Status: concluído**

- **Arquivos alterados:** `services/ai_llm.py`, `services/ai_prompts.py` (somente estes).
- **Pensamento interno restaurado sem exposição na UI:** em `chat_completion`, conexões com host `api.z.ai` agora enviam `thinking: {"type": "enabled"}` e `max_tokens: 8192` (antes `disabled`/4096); o app continua lendo apenas `choices[0].message.content` — nenhum `reasoning_content` é exibido, logado ou persistido. Outros provedores manuais não recebem esses campos; timeout e mensagens de erro preservados.
- **Comportamentos de desenho recuperados:** `build_system_prompt` reescrito como guia CAD denso (identidade + sequência mental; raciocínio técnico interno permitido, saída só `{explain, ops}`; modelo mental painel/gabinete/gaiola/postes/passarela/guarda-corpo por instalação; `ground_clearance` = base do painel; ferramentas com exemplos JSON exatos — `set_panel`, `add_box`, `add_grid` coplanar, `add_beam`, `add_post`, `add_plate`, `add_circle`, edição completa e `set_post_height`; perfis válidos como parâmetro interno sem kg/m; criação/edição local/redimensionamento integral como substituição controlada; ambiguidade real → 1 pergunta objetiva com `ops: []`, sem perguntar se a intenção estruturada já trouxe valores; contexto dinâmico `_elements/_groups/_selection` + vista ao final, seleção com prioridade para "esse/esta"; exemplos: painel parede 4×2 m, painel em poste com gabinetes e manutenção traseira, cubo, edição de selecionado, pergunta de ambiguidade). Loader tolerante para `Painel_Outdoor_Estrutura_parametrica.json` (resumo semântico se existir; ausente hoje — não bloqueia). `build_user_message` apresenta os valores do formulário como "FATOS ESTRUTURAIS fornecidos pelo usuário"; blocos INTENÇÃO CANÔNICA e assinaturas mantidos.
- **Incompatibilidade concreta com operação existente:** nenhuma conhecida — formatos/nomes das operações idênticos aos do motor; validação de sintaxe Python OK nos dois arquivos (`py_compile`), chaves do f-string revisadas.

## Diagnóstico confirmado

O GLM-4.5 Flash conectado em `https://api.z.ai/api/paas/v4` ficou menos capaz
de interpretar/criar/editar porque `services/ai_llm.py` envia:

```py
"thinking": {"type": "disabled"}
```

Isso não apenas oculta a cadeia de raciocínio: impede o raciocínio interno do
modelo. A interface já mostra somente `choices[0].message.content`; ela não
exibe nem precisa persistir `reasoning_content`. Portanto o modelo deve pensar
internamente e continuar devolvendo apenas `{explain, ops}` para o CAD.

Além disso, o prompt operacional atual foi resumido demais: perdeu conhecimento
de estrutura útil para desenhar, ao confundir “não discutir orçamento” com “não
pensar tecnicamente”.

## Escopo estrito

Altere somente:

1. `mini-services/led-cad/services/ai_llm.py`
2. `mini-services/led-cad/services/ai_prompts.py`

Não altere `main.py`, frontend, engine geométrico, models, schemas, preview,
operações, PDF, persistência, configuração de chave/API ou presets.

Não criar dependência nova.

## Parte A — Z.ai deve pensar, mas nunca expor pensamento

Em `chat_completion`:

1. Para hostname `api.z.ai`, substitua `thinking: {type: disabled}` por
   `thinking: {type: enabled}` (explícito), mantendo a compatibilidade dos
   outros provedores manuais.
2. Não envie `reasoning_content` ao frontend, não registre essa informação, não
   a inclua em `explain` e não mude o parser atual: o app continua extraindo
   apenas `choices[0].message.content`.
3. Preserve limite razoável de saída para evitar resposta infinita. Se o limite
   atual de 4096 for mantido, confirme que ele não corta o JSON de operações;
   pode usar 8192 para Z.ai se isso for necessário ao raciocínio + JSON.
4. Preserve timeout e mensagens de erro já existentes.

Resultado: raciocínio interno habilitado; chat continua enxuto e recebe apenas
o JSON final de operações.

## Parte B — reescrever somente o contexto operacional ativo

Em `ai_prompts.py`, mantenha assinaturas de `build_system_prompt(...)`,
`build_user_message(...)` e helpers existentes. Reestruture o retorno de
`build_system_prompt` como um guia CAD rico, denso e não redundante.

### Identidade e limite correto

Defina a IA como copiloto de desenho CAD de esboços para estruturas de painel
LED. A sequência mental é: entender objeto → dimensões → instalação → módulo
→ planejar geometria → operations → checar coerência espacial → explain curto.

Ela PODE usar conhecimento técnico internamente para escolher geometria e
parâmetros válidos do CAD. Ela NÃO deve transformar a resposta ao usuário em
orçamento, memorial de cálculo, recomendação definitiva de engenharia, preço,
peso, quantitativo ou lista comercial.

Não escreva proibições que façam o modelo entender “não pense sobre estrutura”.

### Modelo mental obrigatório

Ensine claramente:

- painel LED é superfície/referência visual; a gaiola/suporte é a estrutura;
- gabinete define modulação; grids frontal/traseiro acompanham as juntas;
- gaiola, quadro frontal/traseiro, travessas de profundidade, contraventamento,
  postes, base, parede, suspensão, passarela e guarda-corpo são recursos
  geométricos escolhidos conforme instalação — não uma receita fixa;
- painel em parede não recebe poste/passarela automaticamente;
- painel em poste parte do solo e alcança a base da gaiola, e
  `ground_clearance` é a base do painel, não seu centro;
- acesso traseiro/passarela preserva corredor atrás do painel;
- estruturas livres (casa, cubo, pórtico, torre, círculo, painel especial)
  devem usar as formas paramétricas adequadas.

Se houver um JSON `Painel_Outdoor_Estrutura_parametrica.json` disponível no
workspace, leia-o como referência semântica. Não bloqueie nem procure fora do
workspace se ele não existir; não cole o JSON inteiro no prompt.

### Ferramentas e operações

Documente, com exemplos JSON válidos e curtos, quando usar `set_panel`,
`add_box`, `add_grid`, `add_beam`, `add_post`, `add_plate`, `add_circle` e as
operações de edição existentes. Preserve formatos e nomes exatamente como o
motor aceita.

- `add_box` para gaiola/caixa;
- `add_grid` só para retângulo coplanar: um eixo fixo; XZ frente/trás, XY
  piso/passarela, YZ lateral;
- `add_beam` para barras específicas, diagonais e cabos;
- preferir forma paramétrica de alto nível quando ela representar a geometria.

Se o motor precisa de `profile`, deixe o catálogo/nomes válidos disponíveis ao
modelo para que ele produza operations válidas. O perfil pode ser parâmetro
interno da operação; o `explain` não deve discutir material, peso, preço ou
capacidade de carga.

### Criação, edição e perguntas

- Projeto novo completo: `__blank` + construção.
- Edição local: só operations pontuais; preservar o restante.
- Redimensionamento integral (ex.: 2×1 → 4×2): substituir controladamente a
  estrutura relacionada, preservando módulo, elevação, profundidade e recursos
  existentes/solicitados; nunca sobrepor uma segunda gaiola.
- Se “4×2” for realmente ambíguo entre metros e quantidade de gabinetes,
  perguntar uma única pergunta objetiva com `ops: []`. Se o formulário já
  forneceu valores estruturados, não perguntar novamente.
- Não usar pergunta como desculpa para deixar de desenhar quando existe decisão
  geométrica reversível razoável.

### Contexto dinâmico e resposta

Mantenha `_elements_digest`, `_groups_digest`, `_selection_digest` e vista
atual após o conhecimento fixo. Seleção atual tem prioridade para “esse/esta”.
O único formato de resposta segue:

```json
{"explain":"frase curta ou pergunta objetiva","ops":[]}
```

Inclua poucos exemplos de alta qualidade: painel parede, painel em poste com
gabinetes e manutenção traseira, cubo, edição de elemento selecionado e
pergunta de ambiguidade.

## `build_user_message`

Revise somente se preciso para que informações do formulário sejam apresentadas
como fatos estruturais fornecidos pelo usuário (tipo de instalação, medidas,
profundidade, pé-direito, postes e recursos booleanos). Não alterar seu formato
externo nem criar nova rota.

## Validação final única

Não rode servidor, navegador, build, lint, chamadas reais de IA, exportação ou
testes repetitivos. Faça somente:

1. validação de sintaxe Python nos dois arquivos;
2. inspeção de f-string e chaves JSON escapadas;
3. revisão estática mental dos casos: painel parede 4×2 m, 4×2 gabinetes
   960×960 em poste, passarela incremental, poste selecionado movido, cubo,
   pergunta por medida ambígua.

## Entrega

Ao concluir, atualize este arquivo com `Status: concluído` e escreva apenas:

- arquivos alterados;
- pensamento interno restaurado sem exposição na UI;
- comportamentos de desenho recuperados;
- eventual incompatibilidade concreta com operação existente.
