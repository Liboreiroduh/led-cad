# Provedores gratuitos decididos — LED CAD

Esta é uma decisão de arquitetura baseada em documentação oficial, em 14/09/2026. Não contém chaves e não deve ser tratada como lista de modelos permanente.

## Objetivo

O copiloto precisa devolver texto/JSON para operar o CAD. Priorizamos APIs que exigem apenas criar conta e chave, funcionam via HTTP compatível com OpenAI ou já têm adaptador simples, e possuem camada gratuita/quota gratuita útil para testes.

## Provedores aprovados para o front

| Prioridade | Provedor | Configuração decidida | Regra de uso |
|---|---|---|---|
| 1 | Google Gemini | `gemini-2.5-flash` como padrão; `gemini-2.5-flash-lite` como econômico; `gemini-2.5-pro` opcional | A API Gemini tem camada gratuita com limites. É a opção padrão para o CAD por capacidade de raciocínio e JSON. |
| 2 | OpenRouter | Base fixa `https://openrouter.ai/api/v1`; lista buscada dinamicamente; aceitar só modelos com preços zero | A pessoa cria uma chave OpenRouter. Sem créditos, a documentação informa limite de 50 pedidos gratuitos/dia; modelos podem mudar. Exibir também `openrouter/free` como roteador automático opcional. |
| 3 | Groq | Base fixa `https://api.groq.com/openai/v1`; modelo inicial `qwen/qwen3.8-27b`; catálogo consultado dinamicamente no endpoint oficial de modelos | Conta/chave Groq oferece camada gratuita com limites de taxa. Não chamar de ilimitado ou prometer preço zero para todos os modelos; a UI deve identificar como “quota gratuita sujeita a limites”. |

## Não incluir agora

- OpenAI: é provedor pago e já existe separado.
- `compat`: continua como rota manual para quem já possui provedor/chave, mas não é catálogo de gratuitos.
- z.ai: manter o conector já instalado/configurado pelo usuário; plano de coding/web não deve ser apresentado como garantia de API pública gratuita.
- Provedores com créditos promocionais, trial incerto, infraestrutura própria, conta cloud complexa ou documentação de gratuidade não confirmada não entram neste MVP.

## Regras de segurança e UX

1. Chaves ficam no servidor local e a API pública devolve só estado e máscara.
2. Testar configuração digitada antes de salvar. O teste é efêmero.
3. Catálogos são buscados pelo backend com a chave salva/digitada; navegador nunca chama fornecedor diretamente.
4. Falta de quota/limite deve exibir a resposta real do provedor e preservar a configuração anterior.
5. Não alternar automaticamente de provedor quando houver erro ou limite.

## Fontes oficiais

- Google: modelos e preços da Gemini API.
- OpenRouter: API de modelos, variante `:free` e FAQ de limites dos modelos gratuitos.
- Groq: compatibilidade OpenAI, catálogo `GET /openai/v1/models` e documentação de rate limits.
