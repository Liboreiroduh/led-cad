# Estado para revisão do GPT

## Achados por leitura do código

O catálogo `mini-services/led-cad/presets/referencias/catalogo.json` contém cartões compactos com tamanho e template. Não contém a descrição completa da montagem de cada desenho original.

Em `services/preset_service.py`, `_resolved_preset()` expande esses cartões usando seis templates genéricos. Profundidade, altura ao solo, perfis, travessas e contraventamentos vêm de defaults comuns. `_build_panel()` cria uma superfície única; `_vertical_xs()` distribui vãos uniformes pelo espaçamento máximo. Isso não comprova correspondência com gabinetes nem com a disposição de barras da referência.

Consequência: escolher um cartão com nome de referência não garante obter a geometria daquela referência. Ensinar apenas os nomes desses cartões à IA não corrige a perda de informação no catálogo/gerador.

Não foi feita comparação visual individual dos presets com cada PDF. Os achados são de código; diferenças por referência precisam ser levantadas sem inventar medidas.

## Trabalho solicitado ao executor

Execute a correção em modo de prototipagem. Mapeie cada preset a sua referência local e registre medidas e componentes realmente disponíveis, distinguindo dimensão nominal, face LED e gabinete. Preserve medidas existentes até haver evidência para alterá-las. Complete os dados necessários para reproduzir cada montagem, reutilizando o motor atual. Identifique claramente presets genéricos e dados ainda desconhecidos.

Integre esse conhecimento ao piloto para que ele use a mesma receita do botão Novo, adapte parâmetros explícitos e gere preview pelo backend. Não reconstruir conexões de IA. Não substituir todos os desenhos por um único template. Não criar outro editor. Priorizar implementação; validação visual conjunta com o usuário fica para depois.

## Cópia para análise

A versão canônica para análise e desenvolvimento é `main`. Inclui código, banco SQLite, projetos, presets e referências locais elegíveis. Credenciais, configuração privada de IA, memória de conversa, logs, caches e dependências instaladas são excluídos da cópia publicada. Configure sua própria key localmente. O banco Prisma do shell Next não substitui os projetos JSON do backend CAD. Trabalhar diretamente na versão canônica, sem novas branches ou PRs nesta prototipagem.
