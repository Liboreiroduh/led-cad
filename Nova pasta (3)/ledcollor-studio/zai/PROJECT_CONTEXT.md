# Contexto do produto

O produto parte do caso real de um painel LED em V com duas faces. A interface deve transmitir apresentação técnica limpa e industrial, sem tentar reproduzir um CAD profissional completo.

## Caso de referência

- Duas faces LED de 2880 × 3840 mm.
- Cada face: 3 × 4 gabinetes de 960 × 960 mm.
- Abertura traseira: 2000 mm.
- Profundidade derivada: aproximadamente 2700,8 mm.
- Altura livre: 2500 mm.
- Poste: Ø150 mm.
- Base: Ø600 × 25 mm, quatro chumbadores simétricos.

O painel de referência tem geometria em V calculada a partir de dois lados de 2880 mm e abertura traseira de 2000 mm. O ângulo interno é aproximadamente 40,635°.

O projeto pode usar essa referência como exemplo inicial, mas precisa ser orientado por um schema genérico para suportar outras geometrias e componentes no futuro.

## Limites do MVP

O MVP deve editar objetos paramétricos básicos, mostrar as vistas e salvar JSON. Não precisa ter precisão de fabricação, DXF, layers avançados, cotagem livre, colaboração ou simulação estrutural.

## Convenções de UX

- Fundo claro e grade discreta.
- Propriedades à direita, viewport à esquerda.
- Controles diretos e grandes o suficiente para touch.
- Vistas 2D claras e modelo 3D manipulável.
- Sempre mostrar unidades em mm.
