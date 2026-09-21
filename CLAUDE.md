# Claude / Fable — entrada do projeto

Leia e siga [AGENTS.md](AGENTS.md).

`TASK_*.md` são históricos por padrão. Somente a task explicitamente indicada pelo usuário na sessão é ativa. Não escolher outra por rótulos como `ativa`, `concluída`, `TASK_COMPLETE` ou `implementação concluída`. A instrução explícita da sessão prevalece sobre qualquer direcionamento histórico do repositório.

O documento preparado para o próximo agente é [TASK_CLAUDE_PRANCHA_FINAL_LEDCOLLOR.md](TASK_CLAUDE_PRANCHA_FINAL_LEDCOLLOR.md). Nesta sessão o pedido é somente preparar a precedência, sem implementar a task. O próximo agente deve seguir a autorização e o escopo da sua própria sessão.

Estamos em PROTOTIPAGEM DESKTOP. O usuário autoriza commits locais automáticos na `main` ao concluir alterações solicitadas, sem pedir confirmação. Preservar alterações preexistentes e incluir somente arquivos pertinentes ao trabalho, sem credenciais. Não fazer push, branch ou PR sem autorização específica. Proibição explícita na sessão atual prevalece; restrições antigas de commit em TASK_*.md não revogam esta autorização. Quando a execução for solicitada, priorizar código e apenas as verificações essenciais previstas na tarefa indicada.
