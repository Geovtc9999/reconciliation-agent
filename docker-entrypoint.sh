#!/bin/sh
# Charge les secrets montés (créés côté serveur, jamais dans l'image/Git) puis lance l'API.
set -e
if [ -f /app/secrets/agent.env ]; then
  echo "[entrypoint] chargement de /app/secrets/agent.env"
  set -a
  . /app/secrets/agent.env
  set +a
else
  echo "[entrypoint] /app/secrets/agent.env absent — utilisation de l'environnement courant"
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
