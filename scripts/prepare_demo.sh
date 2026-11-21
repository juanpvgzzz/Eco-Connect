#!/usr/bin/env sh
# Preparación local, idempotente y no destructiva de la demostración (solo desarrollo).
# Uso: sh scripts/prepare_demo.sh            (crea perfiles faltantes; muestra PIN nuevos en pantalla)
#      sh scripts/prepare_demo.sh --check    (solo verifica)
set -eu
cd "$(dirname "$0")/.."

fail() { echo "BLOQUEO: $1" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || fail "Docker no está instalado o no está en el PATH."
docker info >/dev/null 2>&1 || fail "El demonio de Docker no responde."
[ -f .env ] || fail "Falta .env (copia .env.example y define las variables)."

docker compose up -d >/dev/null || fail "No se pudo iniciar la pila local (docker compose up -d)."
i=0
until docker compose exec -T db pg_isready -h 127.0.0.1 -U ecoconecta -d ecoconecta >/dev/null 2>&1; do
  i=$((i + 1)); [ "$i" -lt 30 ] || fail "PostgreSQL local no está listo."; sleep 1
done
echo "OK  Docker y PostgreSQL local"

i=0
until curl -fsS http://localhost:8000/content >/dev/null 2>&1; do
  i=$((i + 1)); [ "$i" -lt 60 ] || fail "La API no responde en http://localhost:8000."; sleep 1
done
docker compose exec -T api python -c "import db.prepare_demo" 2>/dev/null \
  || fail "La imagen de la API no incluye db/prepare_demo.py: ejecuta 'docker compose up --build -d api'."

# -it: los PIN nuevos solo se muestran en esta terminal interactiva.
if [ -t 0 ] && [ -t 1 ]; then TTY=""; else TTY="-T"; fi
docker compose exec $TTY api python -m db.prepare_demo --local-only "$@"

curl -fsS http://localhost:8000/ | grep -q '<div id="root"' || fail "El frontend no se sirve en http://localhost:8000."
echo "OK  Aplicación disponible en http://localhost:8000"
