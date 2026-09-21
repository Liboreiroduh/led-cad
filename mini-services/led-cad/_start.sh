#!/bin/bash
# LED STRUCTURE CAD — inicializador canônico (usar via start-stop-daemon).
# Bind 0.0.0.0 (IPv4): a borda do sandbox diala diretamente e o gateway :81
# faz fallback para 127.0.0.1 (localhost resolve ::1 primeiro aqui).
# Sem --reload: o StatReload crasha no sandbox (OSError /proc/*/net) —
# após editar .py, reinicie com:
#   kill $(cat ledcad.pid) 2>/dev/null; sleep 2
#   start-stop-daemon -d "$(dirname "$0")" --start --background \
#     --make-pidfile --pidfile "$(dirname "$0")/ledcad.pid" \
#     --startas /bin/bash -- -c 'exec /home/z/my-project/mini-services/led-cad/_start.sh'
cd "$(dirname "$0")"
exec /home/z/.venv/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 3100 >> server.log 2>&1
