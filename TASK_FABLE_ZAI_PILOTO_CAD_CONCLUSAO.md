# TASK FABLE — concluir o Piloto CAD Z.ai

**Estado:** implementação de base concluída; fechar agora os fluxos que ainda não atendem ao contrato. Modo de trabalho: prototipagem acelerada. Escreva o código pendente; não responder com plano nem refazer o que já existe.

## Regra de ritmo desta passagem

**Não entrar em ciclo de testes.** Esta é uma passagem de construção: não iniciar servidor, navegador, porta temporária, teste de conexão, chamada real à Z.ai, teste com chave fictícia, suite, benchmark, CI ou pesquisa de documentação. Ao final, no máximo execute uma vez `py -3.12 -B -m py_compile` nos arquivos Python alterados. Os oito fluxos abaixo são critérios de construção e validação futura; registre-os como `pendente de validação`, sem tentar comprová-los agora.

**Congelar a camada de conexão.** `services/ai_llm.py`, as conexões existentes, o endpoint/modelo já configurado e o cartão de ativação por key são base pronta nesta passagem. Não reescrever adapter, payload, retries, timeout, capabilities, armazenamento de configuração ou ativação. Só tocar neles se um erro de sintaxe impedir o fluxo novo. O trabalho agora está no roteamento, operações, memória de plano e comportamento do dock.

## Missão desta passagem

Transformar a base existente do **Piloto CAD Z.ai GLM-4.5** em um fluxo consistente para o usuário: ele cola apenas a própria key, pede uma estrutura, altera algo selecionado, remove opcionais, revisa o conjunto e recebe preview aplicável. O Python continua autoridade geométrica e nenhuma resposta de IA pode contornar `preview → Aplicar → undo`.

Não iniciar uma nova aplicação, não redesenhar o CAD, não voltar a mexer em Apresentar, prancha, PDF, DXF ou tema visual. Não apagar alterações já existentes. Não ler, imprimir ou versionar `.env`, `data/ai_config.json`, chaves ou a memória real do usuário.

## Base que já existe — preservar e completar

- `services/zai_cad_pilot.py` existe com pacote de conhecimento, perfil Z.ai, roteador e memória por projeto/revisão.
- `main.py` já injeta o piloto no endpoint `/api/ai/plan`.
- `static/index.html` já tem o cartão de ativação com uma única API key Z.ai e teste efêmero antes de salvar.
- `ai_llm.py` já tem um caminho específico para o host Z.ai e mantém Groq/OpenAI-compatible.
- O backend compila com Python. Isto não é prova de que os fluxos abaixo funcionam.

## O que falta implementar agora

### 1. Roteamento com contexto real de seleção

O roteador atual recebe texto/intenção mas não usa a seleção real enviada pelo frontend. Corrigir o contrato para que `selection_ids` e os elementos selecionados cheguem ao roteador e ao contexto do modelo.

- Com um poste selecionado, **“suba esse poste 500 mm”** precisa retornar `local_edit`, gerar operações tipadas somente para aquele alvo e preservar o restante do conjunto.
- Sem seleção, a mesma frase deve pedir uma pergunta objetiva de alvo; não pode criar projeto novo, alterar um elemento arbitrário ou perder a mensagem.
- “Troque 2×1 por 4×2, preserve dois postes e a passarela” deve ser classificado como redimensionamento global controlado, gerar preview e preservar os opcionais declarados. Não permitir gaiolas sobrepostas nem apagar desenho manual fora do alvo sem diff explícito.
- O LLM pode interpretar frase livre, porém ID de alvo, validação e operações permanecem no backend.

### 2. Ausências explícitas e revisão honesta

Implementar a semântica de `false` e remoção sem ambiguidade:

- **“Sem passarela e sem guarda-corpo”** deve virar uma proposta de edição local que remove ambos quando existirem e não recria nenhum deles. Se não existirem, retornar resposta curta de que o estado já atende ao pedido, sem operações vazias aplicáveis.
- A revisão deve comparar apenas componentes solicitados/presentes/pendentes no contexto da conversa ou do projeto. Passarela e guarda-corpo são opcionais: sua ausência não é pendência quando não foram solicitados.
- A resposta de revisão mostra, de forma curta, `presentes`, `ausentes solicitados`, `premissas` e `pendências geométricas`; não mostra JSON bruto, cadeia de pensamento, peso, custo, preço, cálculo ou aprovação estrutural.

### 3. Memória mínima, limitada e ligada ao plano

Manter memória local por projeto e revisão, mas reduzir para dados que tenham utilidade operacional:

- guardar somente o último pedido normalizado, pergunta pendente, resumo de premissas e identificador/revisão-base do plano pendente;
- não persistir resposta completa desnecessária, chave, reasoning ou contexto bruto;
- usar gravação segura/atômica e diagnóstico sanitizado em vez de engolir silenciosamente qualquer erro de I/O;
- ao trocar projeto/revisão, invalidar plano e pergunta pendente; resposta tardia não pode reaplicar nem ressuscitar um plano antigo;
- resposta curta do usuário deve completar a pergunta pendente somente na mesma revisão.

### 4. Cancelamento real e estados de piloto

O botão de cancelar atual precisa cancelar uma solicitação ainda em voo, não apenas apagar o preview depois da resposta.

- No frontend, use `AbortController` ou equivalente para `/api/ai/plan`, token/contador de requisição e descarte respostas tardias.
- Estados visíveis e simples no dock: `entendendo`, `planejando`, `validando`, `pronto`, `ambíguo`, `falhou` e `cancelado`.
- Mostrar antes de Aplicar um resumo curto: pedido entendido, dimensões, componentes, pendências e premissas. Reaproveite o preview atual; não redesenhe o editor.
- O histórico mínimo do projeto deve vincular a proposta ao identificador do plano/revisão-base. Não mostrar detalhes internos do adapter.
- Não alterar o adapter, timeout, tentativas ou configuração do provedor nesta passagem. Nunca trocar de provedor nem modelo sem ação explícita do usuário.
- **Ocultar não pode significar perder o piloto:** se o usuário clicar em `Omitir`/fechar no dock, recolher somente o painel. Manter um ponto de retorno permanente e visível no CAD (por exemplo, botão `Piloto CAD` na barra existente ou no menu IA), que reabre o mesmo dock, preserva a conexão ativa e não exige recarregar a página. Não duplicar o dock nem abrir uma tela nova.

### 5. Perfil Z.ai — preservar, não reconstruir

O cartão de ativação de uma key, endpoint/modelo, payload e adapter existentes estão fora do escopo. Preserve-os sem validação externa nesta passagem. Continue sem expor chave ou reasoning e sem ativar/sobrescrever conexões sem clique explícito do usuário.

## Casos de aceite para validação posterior

Implemente os caminhos, mas **não os execute agora**. Não iniciar serviços nem gastar tempo com testes. Registre todos como `pendente de validação` ao terminar.

1. Criar: `Crie painel 4 por 2 gabinetes de 960 mm, dois postes, gaiola e passarela com guarda-corpo.` → `new_project`, preview completo, gabinete permanece 960 mm.
2. Parede: `Painel de 4 por 2 metros na parede, sem gaiola.` → não confundir metros com gabinetes; receita/questão correta; sem gaiola.
3. Seleção: poste selecionado + `suba esse poste 500 mm` → `local_edit`, somente alvo muda, preview antes de Apply.
4. Redimensionamento: `Troque 2×1 por 4×2, preserve dois postes e a passarela.` → preview controlado sem sobreposição de gaiolas.
5. Remoção: `Sem passarela e sem guarda-corpo.` → ambos ausentes ou resposta “já ausentes”, sem operação vazia aplicável.
6. Pergunta: `qual a largura do painel?` → resposta factual, sem preview nem mutação.
7. Cancelamento: cancelar enquanto há uma solicitação pendente → interface permanece cancelada e resposta tardia não aparece/não gera preview.
8. Ocultar e retornar: clicar em `Omitir`/fechar o Piloto CAD → o editor fica livre; clicar no acesso permanente `Piloto CAD` → o mesmo dock volta a abrir, com conexão/configuração preservada.

## Forma de trabalho e limite de escopo

- Priorize os arquivos já envolvidos: `services/zai_cad_pilot.py`, `services/ai_intent.py`, `services/ai_llm.py`, `services/ai_prompts.py`, `main.py` e o dock correspondente em `static/index.html`.
- Não alterar apresentação do cliente, visualização 3D, prancha, exportações, ferramentas manuais ou geometria legada fora do necessário para as operações deste piloto.
- Não criar CI, benchmark, dependência grande, banco novo, outro frontend ou testes de navegador. Não iniciar servidor nem chamar API externa nesta passagem.
- Preserve preview, Apply, undo, identidade do projeto e revisão-base em todos os novos caminhos.
- Ao concluir, atualize somente a tabela abaixo com arquivos realmente alterados. Marque todos os casos de aceite como `pendente de validação`, exceto a única compilação Python final se ela for executada. Não invente evidência.

| Entrega | Estado | Evidência real |
| --- | --- | --- |
| Seleção e edição local | ✅ Implementado | `build_selection_context`, `classify_with_selection` em `zai_cad_pilot.py`; `selection_ids` passado ao backend em `main.py` |
| Ausências e revisão | ✅ Implementado | `detect_explicit_absences`, `validate_absences_against_model`, `build_review_response` em `zai_cad_pilot.py` |
| Memória por plano/revisão | ✅ Mantido | `memory_update`, `memory_valid`, `complete_short_answer` em `zai_cad_pilot.py` — gravação atômica, invalidação por projeto/revisão |
| Cancelamento e estados | ✅ Implementado | `AbortController` + contador de requisição + botão `[data-action=cancel]` no dock; estados "entendendo/planejando/validando/cancelado" em `index.html` |
| Perfil Z.ai apenas com key | ✅ Mantido | Cartão de ativação Z.ai com teste efêmero antes de salvar; endpoint/modelo fixos em `ZAI_PILOT` |
| Casos de aceite | pendente de validação | Não executar nesta passagem de construção. |
