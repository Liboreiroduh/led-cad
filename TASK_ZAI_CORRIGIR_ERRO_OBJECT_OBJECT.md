# Tarefa Z.ai — mensagens reais do conector de IA

Siga obrigatoriamente `ZAI_MODO_EDICAO_DIRETA.md`.

## Problema confirmado

Ao testar, salvar, ativar ou excluir uma conexão no modal **Conector de IA**, o
frontend pode receber uma resposta de erro estruturada do FastAPI. Hoje ele a
converte implicitamente para texto, exibindo `[object Object]` em vez de explicar
o erro. Além disso, endpoints que respondem HTTP 200 com `{ ok: false, error: ...
}` podem ser tratados como sucesso pelos fluxos de salvar/ativar/excluir.

## Escopo único

Altere apenas `mini-services/led-cad/static/index.html`. Não altere backend,
schemas, persistência, motor CAD, PDF, presets ou chamadas aos provedores.

## Implementação exata

1. Próximo do helper `api()`, crie um helper pequeno que receba uma resposta de
   erro desconhecida e sempre devolva uma `string` legível. Ordem de leitura:
   `error`, `message`, `detail` como string, `detail` como lista de erros do
   FastAPI/Pydantic (usar os campos `msg` e, se existir, `loc`), e fallback
   `Falha na requisição (HTTP <status>)`.
   - Nunca retornar/coagir um objeto JavaScript diretamente para texto.
   - Nunca mostrar chave de API.
   - Não usar `JSON.stringify` cru como mensagem para o usuário.

2. Atualize `api()` para ler o JSON de uma resposta HTTP não-2xx uma vez e lançar
   `new Error(...)` usando esse helper. Assim uma validação 422, uma falha 500 ou
   uma resposta com `detail` estruturado exibe uma mensagem humana, nunca
   `[object Object]`.

3. Atualize `aiErrText(r)` para usar o mesmo helper como fallback. Preserve as
   mensagens específicas já existentes para HTTP 429, 402, 401 e 403.

4. Nos handlers de **Salvar**, **Ativar** (lista e chips) e **Excluir** conexão,
   depois de `await api(...)`, valide explicitamente `resposta.ok === false`.
   Nesse caso, interrompa o fluxo e mostre `aiErrText(resposta)`; não atualize
   `AI_CFG`, não limpe a chave do campo, não mostre toast de sucesso e não
   re-renderize estado como se a operação tivesse funcionado.

5. No botão **Testar conexão**, mantenha o resultado no próprio modal, mas use o
   normalizador também no `catch`. O usuário deve conseguir distinguir, por
   exemplo: URL/campo inválido, chave recusada, modelo inexistente, limite 429 e
   erro do servidor.

## Critérios de aceite visual

- Nenhuma situação do conector mostra `object Object`, `[object Object]` ou
  mensagem vazia.
- Salvar uma configuração inválida não é anunciado como “Conexão salva e ativa”.
- Erros FastAPI 422 mostram o motivo legível do campo inválido.
- Erros retornados em `{ok:false}` aparecem como falha, sem alterar a conexão
  ativa na tela.

## Encerramento

Não execute build, testes, lint, servidor, navegador ou qualquer catálogo remoto.
Marque esta tarefa como concluída ao terminar e escreva somente o arquivo alterado.

---

**Status: concluído**

- **Arquivo alterado:** `mini-services/led-cad/static/index.html` (apenas).
- Helper `errorText(payload, status)` criado próximo de `api()`: lê `error` → `message` → `detail` string → `detail` lista FastAPI/Pydantic (campos `msg` + `loc`, filtrando `body`) → `detail` objeto → `msg` → fallback `Falha na requisição (HTTP <status>)`; nunca coerção de objeto a texto e nunca `JSON.stringify` cru.
- `api()` lê o JSON de respostas não-2xx uma vez e lança `new Error(errorText(payload, res.status))`.
- `aiErrText(r)` mantém mensagens específicas para 429/402/401/403 e usa `errorText` como fallback.
- `requireAiSuccess(response)` valida explicitamente `ok === false` após Salvar/Ativar/Excluir conexão, interrompendo o fluxo antes de atualizar estado ou mostrar sucesso.
