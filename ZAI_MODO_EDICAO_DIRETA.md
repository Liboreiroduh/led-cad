# Z.ai — modo de edição direta

Regra operacional para todas as próximas tarefas neste protótipo.

1. Ler somente o arquivo-alvo e, se indispensável, as poucas linhas que chamam a função a alterar.
2. Aplicar a mudança pedida diretamente na versão canônica `mini-services/led-cad`.
3. Não mapear arquitetura, não reavaliar requisitos antigos, não procurar melhorias adjacentes, não criar alternativas e não refatorar fora do alvo.
4. Não rodar testes, build, lint, servidor, navegador, exportação, screenshot ou validação automática, salvo se a tarefa pedir explicitamente.
5. Não fazer perguntas quando a tarefa já determina o resultado. Escolher a alteração mínima e seguir.
6. Não criar relatório paralelo. No máximo, ao terminar, marcar a tarefa como concluída e listar em uma linha o arquivo alterado.
7. Se a alteração for inviável sem uma decisão nova do usuário, parar e escrever somente o bloqueio concreto.

O objetivo é editar rápido e entregar a mudança. A conferência visual/funcional será feita pelo usuário depois, e correções posteriores serão tarefas pequenas separadas.
