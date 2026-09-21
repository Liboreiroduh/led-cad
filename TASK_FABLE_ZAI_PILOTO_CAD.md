# TASK FABLE — Z.ai GLM-4.5 como piloto CAD

## Missão

Transformar a conexão Z.ai configurada pelo usuário para **GLM-4.5** no piloto principal do LED Structure CAD. “Treinar” aqui significa especializar o comportamento do copiloto dentro do aplicativo: contexto do projeto, instruções, exemplos, seleção, receitas, contrato de saída, memória de conversa e revisão geométrica. Não prometer fine-tuning do modelo-base nem criar uma falsa API de treinamento.

O piloto deve conversar em português natural, entender pedido de desenho, reconhecer o estado atual, propor a estrutura completa quando o pedido for global e fazer alteração pontual quando houver seleção. Ele pensa internamente e devolve apenas uma proposta curta, verificável e aplicável pelo motor.

## Escopo e arquivos

Trabalhar em `mini-services/led-cad` e priorizar:

- `services/ai_llm.py`
- `services/ai_prompts.py`
- `services/ai_intent.py`
- `services/parametric.py`
- `main.py` nos endpoints do copiloto
- `static/index.html` somente para a experiência do piloto

Não mexer no editor manual, apresentação do cliente, PDF/DXF, tema visual ou cálculos legados. Não ler/imprimir `.env` ou `data/ai_config.json`; use somente sua interface pública e dados sintéticos.

## O que construir

### 0. Pronto para chave: configuração Z.ai sem trabalho manual

Entregar uma experiência em que o usuário só precisa **colar a própria API key** para ativar o Piloto CAD:

- adicionar um preset/draft local **Z.ai · GLM-4.5 · Piloto CAD** no conector;
- preencher automaticamente endpoint oficial atual, modelo GLM-4.5 correto e capabilities do perfil; confirmar o identificador do modelo na documentação oficial antes de fixá-lo;
- a UI deve mostrar um único campo obrigatório: `API key Z.ai`, com botão `Ativar Piloto CAD`;
- não gravar chave no frontend, não exibir chave depois de salvar e não fazer chamada real sem chave;
- não substituir, apagar ou ativar automaticamente as conexões já existentes do usuário; o preset só vira ativo após ele colar a chave e confirmar;
- se a Z.ai devolver limitação de cota/plano, mostrar a mensagem do provedor de forma curta. Não chamar um modelo de “gratuito garantido”: disponibilidade depende da cota da conta do usuário.

O usuário não deve precisar digitar URL, nome técnico de modelo, JSON, capability ou parâmetro de thinking.

### 1. Perfil Z.ai/GLM-4.5 explícito

Criar uma capability/profile específico e detectável para conexões Z.ai com GLM-4.5. Ele deve:

- usar o formato de payload oficialmente compatível com o endpoint já configurado;
- habilitar raciocínio interno somente quando a capability suportar isso;
- nunca retornar, salvar, logar ou mostrar reasoning/thinking ao usuário;
- usar saída estruturada quando suportada; quando não suportada, exigir o mesmo JSON e validar estritamente na borda;
- informar na UI qual conexão/modelo está no modo **Piloto CAD**, sem expor chave;
- preservar OpenAI-compatible e demais conexões existentes.

Não alterar o modelo ativo por nome fixo nem gravar configuração privada. A escolha continua pertencendo à conexão ativa do usuário.

### 2. Pacote de conhecimento do piloto

Criar um único módulo local e compacto para o conhecimento operacional do piloto, por exemplo `services/zai_cad_pilot.py`. Ele deve gerar um contexto por pedido, em vez de manter um prompt gigante solto.

O pacote contém:

- glossário português de painel LED: face, gabinete, modulação, gaiola, quadro, travessa, diagonal, poste, base, parede, suspensão, passarela, guarda-corpo e cota ao solo;
- regra de unidades: `mm`, `cm`, `m`, vírgula decimal, e diferença entre `4×2 m` e `4×2 gabinetes`;
- regra de produto: gabinete **960 mm permanece autoridade** quando a receita/contexto indicar 960; não trocar dimensão por suposição;
- coordenadas do CAD: X largura, Y profundidade, Z altura, solo Z=0;
- receitas determinísticas para parede, um/dois postes, suspenso, rental/totem; dupla face/circular devem declarar pendência se a receita ainda não existir;
- semântica de pedido completo versus edição local;
- exemplos curtos e reais de entrada em português e spec/ops válidas, sem dezenas de exemplos redundantes;
- limite claro: é esboço geométrico, não aprovação estrutural, cálculo, preço ou lista de corte.

O conhecimento deve ser versionado e poder ser exibido como resumo na resposta de diagnóstico, sem conter chaves ou raciocínio interno.

### 3. Roteador de piloto

Antes de chamar o LLM, classificar cada mensagem em uma das rotas:

1. `new_project` ou `global_resize`: intenção tipada → spec → compilador paramétrico Python → preview.
2. `local_edit`: seleção/contexto → plano de operações tipadas → preview.
3. `question`: resposta explicativa curta, sem operações.
4. `ambiguous`: uma pergunta objetiva, sem criar geometria.
5. `review`: conferência determinística do solicitado × presente × pendente.

O GLM-4.5 decide intenção e parâmetros quando texto é livre; Python continua calculando coordenadas, expandindo receitas, validando e aplicando. Nunca deixar o piloto contornar `preview → aplicar → undo`.

Pedidos completos como “painel 4×2 de gabinetes 960, dois postes, gaiola e passarela” não podem terminar em uma barra isolada. A resposta inclui componentes solicitados, presentes, pendentes e premissas, sem cadeia de pensamento.

### 4. Memória útil por projeto

Implementar memória leve por projeto/revisão, sem banco novo:

- último pedido entendido, spec/plan pendente, seleção, revisão-base e premissas;
- uma resposta curta do usuário deve completar a pergunta anterior;
- trocar de projeto ou mudar revisão invalida plano e contexto incompatível;
- mensagens antigas não podem aplicar plano novo nem resposta tardia sobre revisão diferente.

Persistir apenas o necessário e seguro para o projeto local. Nunca persistir chave, reasoning ou conteúdo privado desnecessário.

### 5. Experiência de piloto no frontend

No dock atual, acrescentar sem redesenhar o front:

- identificação do Piloto CAD ativo e do modelo;
- resumo estruturado antes de Aplicar: pedido entendido, dimensões, componentes, pendências e premissas;
- estado explícito: entendendo, planejando, validando, pronto, ambíguo, falhou, cancelado;
- ação Cancelar e descarte de resposta tardia;
- histórico mínimo da conversa daquele projeto, com cada proposta ligada ao próprio plano.

Não mostrar pensamento interno, JSON bruto por padrão ou termos de implementação ao usuário final.

## Casos que precisam funcionar no protótipo

Implementar os caminhos sem criar suite extensa:

1. “Crie painel 4 por 2 gabinetes de 960 mm, dois postes, gaiola e passarela com guarda-corpo.” → preview de conjunto completo.
2. “Painel de 4 por 2 metros na parede, sem gaiola.” → pergunta/receita correta, sem confundir metros com gabinetes.
3. Selecionar um poste e pedir “suba esse poste 500 mm” → edição local, preserva conjunto não citado.
4. “Troque 2×1 por 4×2, preserve dois postes e a passarela.” → substituição controlada, sem sobrepor gaiolas.
5. “Sem passarela e sem guarda-corpo.” → ambos ausentes.
6. Pergunta “qual a largura do painel?” → resposta, sem preview nem mutação.

## Forma de trabalho

- Implementar agora; não responder com plano.
- Use fontes oficiais da Z.ai somente se precisar confirmar payload/capability atual do GLM-4.5. Não enviar arquivos, projetos ou credenciais do usuário a serviço externo.
- Não criar teste extenso, CI, benchmark ou nova aplicação. Faça smoke checks locais nos endpoints alterados e um fluxo representativo pelo front se disponível.
- Não chamar integração real caso a conexão do usuário não esteja explicitamente pronta; deixe o adapter pronto e informe a limitação sem bloquear o piloto local.
- Ao terminar, atualizar somente este quadro com evidência real.

| Entrega | Estado | Evidência |
| --- | --- | --- |
| Profile Z.ai GLM-4.5-Flash | implementado, validação profunda pendente | `services/zai_cad_pilot.py` (novo): `ZAI_BASE_URL="https://api.z.ai/api/paas/v4"`, `ZAI_PILOT_MODEL="glm-4.5-flash"` (corrigido a pedido do usuário — o 4.5 puro havia sido configurado primeiro), `is_zai_pilot()` detecta o perfil; `services/ai_llm.py` já tinha o host `api.z.ai` com thinking enabled + max_tokens 8192 e sem JSON Schema Groq (payload oficial compatível, sem expor reasoning). Preservadas todas as conexões existentes. |
| Pronto para chave (seção 0) | implementado, validação profunda pendente | `static/index.html`: painel "Piloto CAD — Z.ai GLM-4.5" no modal ⚙ com ÚNICO campo API key + botão `Ativar Piloto CAD`; JS faz teste efêmero (`/api/ai/test-dry`) com endpoint/modelo fixos antes de salvar, reusa a conexão Piloto existente sem tocar nas demais, chave nunca fica no front (limpa após salvar; backend já só devolve `has_key`+máscara); erros 429/402 exibidos curtos. Smoke test em porta 3110: conexão criada/ativada com dados sintéticos, `question` ("qual a largura?") respondida pelo roteador sem LLM, `review` determinístico com pendências, pedidos de criação seguiram ao LLM (401 com chave fictícia, mensagem do provedor exibida). Conexão de teste excluída e servidor temporário encerrado. Reexecução com GLM-4.5-Flash: servidor temporário 3110 refeito; roteador (question/review/ambiguous) validado; fluxo de criação REAL validado — "crie painel 2 por 1 gabinete de 960 na parede" (após correção do regex `_CAB` em `services/ai_intent.py` p/ aceitar "N por M gabinete de 960") devolveu `mode:plan, engine:llm, ok:True` com 23 alterações de preview via Piloto CAD ativo com chave real do usuário. |
| Conhecimento e roteador do piloto | implementado, validação profunda pendente | `services/zai_cad_pilot.py`: `knowledge_package()` versionado (glossário PT, unidades mm/cm/m e 4×2 m vs 4×2 gabinetes, gabinete 960 como autoridade, coordenadas X/Y/Z, receitas, pendências dupla-face/circular, limite de esboço), `knowledge_block()` injetado no prompt quando o piloto está ativo; `classify()` decide new_project/local_edit/question/ambiguous/review em Python antes do LLM; `answer_factual()` responde perguntas de medidas sem LLM. Integrado em `/api/ai/plan` (main.py) — nenhuma rota contorna preview → aplicar → undo. |
| Memória segura por projeto/revisão | implementado, validação profunda pendente | `services/zai_cad_pilot.py`: `data/pilot_memory.json` com last_text/route/answer/pending_question por project_id; `memory_valid()` invalida em troca de projeto/revisão; `complete_short_answer()` completa pergunta pendente com resposta curta; `pending_question` gravada na rota ambiguous para o próximo turno. Nunca persiste chave ou reasoning. |
| UX Piloto CAD | implementado, validação profunda pendente | `static/index.html`: painel de ativação com estado/erro (`zaiPilotOut`), respostas `engine:"pilot"` aparecem como mensagens do copiloto (resumo antes de Aplicar já existia via renderPlanPreview; estados entendendo/validando via waitTimer existentes). Sem JSON bruto, sem pensamento interno, sem termos técnicos ao usuário. |
