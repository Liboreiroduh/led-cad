# TASK — Saída final de prancha LED Collor baseada no documento de referência

## MODO DE TRABALHO

Estamos em **PROTOTIPAGEM DESKTOP**.

- Prioridade: CODAR e fazer funcionar ponta a ponta.
- Não criar branch, PR ou commit.
- Não gastar tempo com cobertura perfeita, refatoração ampla ou bateria extensa de testes.
- Faça apenas smoke tests essenciais.
- Bugs não bloqueadores podem ser registrados para depois.
- Use agentes em paralelo quando houver partes independentes.
- Só pare por bloqueio técnico real.

---

# CORREÇÃO DE DIREÇÃO

O PDF de referência **NÃO define um tipo de estrutura em V**.

Ele deve ser usado como **PADRÃO DE SAÍDA FINAL DA PRANCHA**.

Não ensine a IA que o projeto padrão é:
- duas faces;
- painel em V;
- poste central;
- 2880 × 3840;
- base Ø600;
- abertura traseira de 2000 mm.

Esses valores pertencem apenas ao exemplo visual fornecido.

O sistema deve continuar capaz de criar livremente:
- uma face;
- duas ou mais faces;
- faces paralelas;
- faces em ângulo;
- painéis em V;
- painéis curvos;
- painéis circulares;
- estruturas em poste;
- parede;
- suspensão;
- rental;
- cubos;
- formatos especiais;
- estruturas combinadas.

O **desenho muda**.

A **linguagem visual da prancha final permanece LED Collor**.

---

# OBJETIVO

Transformar a exportação final do LED CAD em uma prancha profissional no padrão visual do documento de referência enviado pelo usuário.

Fluxo:

```text
pedido do usuário
    ↓
IA entende e constrói a geometria
    ↓
ProjectModel / geometria real
    ↓
projeções + cotas
    ↓
PLANEJADOR DE FOLHAS
    ↓
template visual LED Collor
    ↓
PDF final
```

A prancha nunca deve dirigir a geometria.

A geometria dirige a prancha.

---

# 1. O QUE EXTRAIR DO PDF DE REFERÊNCIA

Usar o PDF fornecido pelo usuário como referência visual e editorial.

Ele demonstra:

## Identidade visual

- folha branca;
- moldura técnica fina;
- título grande no topo;
- subtítulo da vista;
- desenho técnico central;
- cotas bem destacadas;
- logo LED Collor;
- `ledcollor.com.br`;
- Instagram `ledcollor`;
- unidades em `mm`;
- número da folha;
- aviso técnico em vermelho no rodapé;
- visual limpo de apresentação.

Não copiar a geometria específica do painel em V para outros projetos.

---

# 2. LAYOUT VISUAL

Criar um novo perfil de exportação, por exemplo:

```text
ledcollor_presentation
```

Não quebrar o PDF técnico atual.

Arquitetura:

```text
ProjectModel
   │
   ├── export técnico atual
   │
   └── export apresentação LED Collor
```

O perfil LED Collor deve ter:

```text
┌──────────────────────────────────────────────┬─────────────┐
│                                              │             │
│  TÍTULO DA VISTA                            │  LOGO       │
│  subtítulo                                  │  LED COLLOR │
│                                              │             │
│                                              │  site       │
│              DESENHO                        │  instagram  │
│                                              │             │
│              + COTAS                        │             │
│                                              │             │
│                                              ├─────────────┤
│                                              │ UNIDADES    │
│                                              │ mm          │
│                                              ├─────────────┤
│                                              │ FOLHA       │
│                                              │ 01/XX       │
├──────────────────────────────────────────────┴─────────────┤
│ AVISO TÉCNICO EM VERMELHO                                  │
│ texto secundário                                           │
└────────────────────────────────────────────────────────────┘
```

A proporção e composição devem seguir visualmente o documento de referência, mas serem implementadas de forma paramétrica.

---

# 3. NÃO FIXAR 7 PÁGINAS

O documento fornecido possui 7 páginas porque aquela estrutura específica precisava daquelas 7 vistas/detalhes.

O sistema final precisa ter **quantidade dinâmica de folhas**.

Exemplo:

```text
estrutura simples em parede
→ frontal
→ lateral
→ superior
→ isométrica
= talvez 4 folhas
```

```text
estrutura de 2 faces
→ face A
→ face B
→ traseira quando aplicável
→ lateral
→ planta
→ detalhe de base
→ isométrica
= número apropriado
```

```text
estrutura curva
→ elevação
→ planta mostrando o raio/curvatura
→ lateral quando útil
→ detalhes de suporte
→ isométrica
```

A numeração deve ser automática:

```text
01/05
02/05
...
05/05
```

Nunca `01/07` hardcoded.

---

# 4. PLANEJADOR DE FOLHAS

Criar uma camada responsável por analisar a geometria e montar o documento.

Algo conceitualmente como:

```python
plan_document(model) -> [
    SheetSpec(...),
    SheetSpec(...),
]
```

Exemplo conceitual:

```json
{
  "title": "ELEVAÇÃO FACE LED",
  "subtitle": "VISTA FRONTAL",
  "view": "FRONTAL",
  "subject": "FACE-A",
  "dimensions": "auto"
}
```

Outro:

```json
{
  "title": "VISTA SUPERIOR / PLANTA",
  "subtitle": "GEOMETRIA DA ESTRUTURA",
  "view": "SUPERIOR",
  "dimensions": "auto"
}
```

O planejador deve decidir folhas a partir do projeto real.

Não pedir ao LLM para desenhar as páginas.

Python determina as vistas.

---

# 5. REGRAS DE ESCOLHA DAS VISTAS

Não hardcodar apenas o projeto da referência.

Usar a geometria do `ProjectModel`, grupos, faces, suportes e envelope estrutural.

Regras iniciais suficientes para protótipo:

## Sempre que fizer sentido

- elevação/frontal;
- lateral;
- superior/planta;
- perspectiva isométrica.

## Quando existir

- traseira;
- segunda face;
- faces adicionais;
- base;
- poste;
- suporte;
- passarela;
- fechamento/lona;
- detalhe específico relevante.

## Painéis curvos

A planta superior precisa representar claramente:

- arco;
- raio quando conhecido;
- largura/profundidade do envelope;
- relação dos suportes.

A prancha não deve converter um painel curvo para retângulo somente para exportar.

## Duas faces / múltiplas faces

Cada face relevante deve poder receber uma elevação própria.

Exemplo:

```text
ELEVAÇÃO FACE A
ELEVAÇÃO FACE B
```

Não assumir V.

---

# 6. TÍTULOS DINÂMICOS

Seguir o estilo do PDF de referência:

```text
ELEVAÇÃO FACE LED
(VISTA FRONTAL DE UMA FACE)

ELEVAÇÃO TRASEIRA
(VISTA DA LONA)

ELEVAÇÃO LATERAL
VISTA LATERAL

VISTA SUPERIOR / PLANTA
(GEOMETRIA DA ESTRUTURA)

DETALHE DA BASE
VISTA FRONTAL

DETALHE DA BASE
VISTA SUPERIOR

PERSPECTIVA ISOMÉTRICA
VISTA EM PERSPECTIVA
```

Esses são exemplos editoriais.

O sistema pode adaptar:

```text
ELEVAÇÃO FACE A
ELEVAÇÃO FACE B
VISTA SUPERIOR / PLANTA
DETALHE DO POSTE
DETALHE DA BASE
PERSPECTIVA ISOMÉTRICA
```

Título deve descrever a geometria real.

---

# 7. LOGO LED COLLOR

Procurar primeiro nos assets existentes do projeto pela logo oficial da LED Collor.

Se houver PNG/SVG/logo utilizável:
- usar o asset real;
- não reconstruir logo por texto.

Se não houver:
- deixar a integração preparada;
- usar placeholder temporário claramente identificável;
- não bloquear o protótipo.

A área lateral também deve conter, quando configurado:

```text
ledcollor.com.br
@ledcollor
```

Centralizar isso em configuração/metadata do documento, não repetir hardcoded em cada página.

---

# 8. AVISO DO RODAPÉ

Usar o padrão editorial mostrado no documento de referência.

Separar:

```text
warning_primary
warning_secondary
```

Exemplo de configuração:

```text
ESBOÇO DE REFERÊNCIA GEOMÉTRICO — SOMENTE PARA A EMPRESA RESPONSÁVEL PELA CRIAÇÃO

Este é apenas um esboço de referência geométrico.
```

O primeiro texto deve aparecer destacado em vermelho.

Manter configurável.

---

# 9. COTAS

Preservar e reutilizar a política existente de:

```text
drawing/dimensions.py
drawing/projections.py
```

Todas as medidas devem vir da geometria real.

Nunca fazer:

```python
draw_text("2880")
draw_text("3840")
draw_text("2500")
```

porque essas medidas pertencem somente ao exemplo.

Fazer:

```text
geometria
→ dimensão calculada
→ cota
→ renderer
```

Uma alteração feita pela IA precisa aparecer automaticamente no PDF.

---

# 10. PAINEL / ESTRUTURA COMO FONTES DE VERDADE

A IA continua responsável por interpretar e construir o objeto solicitado.

Exemplo:

```text
"painel curvo 5 × 2 com raio de 4 m em dois postes"
```

A IA/motor cria a geometria.

Depois:

```text
document planner
```

analisa aquela geometria e gera as folhas corretas no padrão LED Collor.

A IA **não deve ser treinada para transformar tudo em V**.

---

# 11. SEPARAÇÃO CORRETA

```text
IA / CAD
"o que eu vou construir?"

EXPORTADOR
"como vou apresentar aquilo?"
```

Não misturar os dois problemas.

A referência enviada pelo usuário responde principalmente à segunda pergunta.

---

# 12. AJUSTAR O PROMPT DA IA APENAS ONDE NECESSÁRIO

Não inserir no prompt operacional:

```text
painel padrão = duas faces em V
```

Remover qualquer instrução introduzida pela task anterior que faça isso.

O prompt pode conhecer apenas que:

```text
o projeto final será documentado automaticamente pelo sistema;
a IA deve fornecer geometria semanticamente organizada;
use grupos/IDs claros para faces, bases, postes e componentes;
isso permite ao exportador identificar vistas e detalhes.
```

Exemplo de grupos úteis:

```text
FACE-A
FACE-B
FACE-C
ESTRUTURA-FACE-A
POSTES
BASES
PASSARELA
GUARDA-CORPO
FECHAMENTO
```

Sem obrigar que existam todos.

---

# 13. PREPARAR GEOMETRIA PARA DOCUMENTAÇÃO

Revisar se o modelo atual possui semântica suficiente para o exportador saber:

- quantas faces existem;
- quais elementos pertencem a uma face;
- quais são postes;
- quais são bases;
- qual é o fechamento;
- quais partes são detalhes relevantes.

Não criar arquitetura gigante nesta fase.

Use grupos/metadata existentes sempre que possível.

Se precisar de pequena extensão no modelo, faça a mínima.

---

# 14. EXPORTAÇÃO

Criar endpoint/opção separada, por exemplo:

```text
/api/export/pdf/presentation
```

ou equivalente coerente com a aplicação.

Preservar:

```text
/api/export/pdf
```

atual.

O objetivo é podermos comparar os dois durante a prototipagem.

---

# 15. FIDELIDADE VISUAL

O PDF de apresentação deve parecer uma prancha da LED Collor, e não um relatório genérico do ReportLab.

Prioridades visuais:

1. composição da página;
2. logo/identidade;
3. títulos;
4. desenho grande;
5. cotas legíveis;
6. coluna lateral;
7. folha/unidade;
8. aviso inferior.

Não gastar esta task tentando atingir perfeição tipográfica milimétrica.

Primeiro deixe a estrutura visual claramente reconhecível como o modelo fornecido.

---

# 16. CASOS PARA TESTE DE PROTÓTIPO

Usar poucos testes reais.

## Caso 1 — estrutura retangular atual

Gerar PDF LED Collor.

Validar:
- layout;
- vistas;
- cotas;
- logo;
- folha dinâmica.

## Caso 2 — estrutura com duas faces

Não importa se paralelas ou anguladas.

Validar:
- o sistema reconhece mais de uma face;
- consegue criar folhas apropriadas;
- não assume automaticamente V.

## Caso 3 — geometria especial/curva disponível no motor

Validar:
- planta representa a geometria real;
- PDF não achata o projeto para retângulo.

Não bloquear a task por casos que o motor CAD ainda não consegue construir.

---

# 17. NÃO FAZER AGORA

Não:

- redesenhar o sistema inteiro;
- criar novo CAD;
- criar banco vetorial;
- treinar modelo;
- criar motor estrutural;
- fazer cálculo de engenharia;
- criar BOM;
- criar orçamento;
- criar lista de corte;
- ficar escrevendo dezenas de testes;
- ficar refinando PDF indefinidamente;
- fazer commit/PR.

---

# 18. VALIDAÇÃO FINAL MÍNIMA

Ao terminar:

1. `py_compile` dos Python alterados;
2. subir o app local;
3. gerar um projeto existente;
4. exportar o novo PDF de apresentação;
5. conferir rapidamente todas as páginas;
6. corrigir apenas erro bloqueador/visual grave;
7. parar.

---

# ENTREGA

Ao terminar, informe apenas:

- arquivos alterados;
- onde ficou o planejador de folhas;
- onde ficou o template LED Collor;
- novo endpoint/botão de exportação;
- como número/tipo de páginas são decididos;
- como múltiplas faces e geometria especial são tratadas;
- limitações atuais observadas no protótipo.
