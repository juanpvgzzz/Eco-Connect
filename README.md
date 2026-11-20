# EcoConecta

API FastAPI para cuentas, guía ambiental, recolecciones, agenda, avisos, puntos y canjes. Las operaciones comparten PostgreSQL y se sirven desde el mismo proceso.

## Ejecutar con Docker

1. Copia `.env.example` a `.env`. Define `POSTGRES_PASSWORD` para desarrollo local, `DATABASE_URL` con el host `db` y las credenciales del servicio, y `ECO_PILOT_ID` con el UUID del piloto. Para cargar la demo usa `10000000-0000-4000-8000-000000000001` como ID del piloto.
2. Ejecuta `docker compose up --build -d`. La API aplica las migraciones al arrancar.
3. En una base nueva de desarrollo, carga los datos ficticios con `docker compose exec -T db psql -v ON_ERROR_STOP=1 -U ecoconecta -d ecoconecta < db/demo.sql`.
4. Crea el administrador con `docker compose exec api python -m db.provision_admin DOCUMENTO "Nombre"`. El comando solicita el PIN de forma interactiva.
5. Abre la [documentación OpenAPI local](http://localhost:8000/docs).

Para probar el flujo de liderazgo, registra una cuenta desde la API y usa el administrador para asignarle el rol `leader` y el ID de su colectivo. Consulta los IDs con `docker compose exec db psql -U ecoconecta -d ecoconecta -c 'select id, flow from collectives'`. Los turnos ficticios de la demo se crean al cargarla y cubren la fecha actual y los 30 días siguientes. Organiza los turnos reales en `collection_shifts` y registra los materiales y reglas de puntos antes de cerrar entregas.

Para conectar el frontend, la especificación está en `/openapi.json`. Las rutas privadas usan `Authorization: Bearer <token>`. Los formularios de alta de recolección reutilizan la misma cabecera `Idempotency-Key` al reintentar un envío. Consulta [los contratos de integración](docs/contratos-modulos.md) para los campos y traducciones.

## Ejecutar con PostgreSQL local

Con PostgreSQL 16 disponible, exporta `DATABASE_URL` apuntando a esa base y `ECO_PILOT_ID` con el UUID de su piloto. Las migraciones crean la estructura. Carga el catálogo del piloto en PostgreSQL o usa `db/demo.sql` en una base local de desarrollo.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m db.migrate
.venv/bin/uvicorn backend.app.main:app --reload
```

## Ejecutar las pruebas

```bash
.venv/bin/pytest -q
TEST_DATABASE_URL="$URL_BASE_DE_PRUEBAS" .venv/bin/pytest -q backend/tests db/tests
```

`TEST_DATABASE_URL` debe apuntar a una base desechable que permita crear y eliminar esquemas. Las pruebas de integración verifican registro y sesiones, citas, avisos, cierre, puntos, stock, canjes y reversión ante fallos.
