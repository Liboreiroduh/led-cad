#!/bin/bash
cd /home/z/my-project/mini-services/ai-gateway
exec /usr/local/bin/bun run dev >> server.log 2>&1
