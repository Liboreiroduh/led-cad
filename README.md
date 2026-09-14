# LED Structure CAD

Protótipo local em Python/FastAPI para criar e editar esboços geométricos de estruturas para painéis LED.

O aplicativo usa coordenadas em milímetros, canvas 3D editável, presets, exportação técnica e um Copiloto de IA que devolve operações geométricas para o motor CAD.

Leia [CANONICAL_PROJECT_CONTEXT.md](CANONICAL_PROJECT_CONTEXT.md) antes de trabalhar com uma IA externa neste repositório.

## Executar localmente

```powershell
cd mini-services/led-cad
python -m uvicorn main:app --host 127.0.0.1 --port 3000
```

Abra `http://localhost:3000`.

## Segurança

As chaves de IA são configuração local e ficam em `data/ai_config.json`, que não é versionado. Cadastre-as pelo Conector de IA na aplicação; nunca publique esse arquivo.
