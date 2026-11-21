# EcoConecta

API FastAPI para cuentas, guía ambiental, recolecciones, agenda, avisos, puntos y canjes. Las operaciones comparten PostgreSQL y se sirven desde el mismo proceso.

## Ejecutar con Docker

1. Copia `.env.example` a `.env`. Define `POSTGRES_PASSWORD` para desarrollo local, `DATABASE_URL` con el host `db` y las credenciales del servicio, y `ECO_PILOT_ID` con el UUID del piloto. Para cargar la demo usa `10000000-0000-4000-8000-000000000001` como ID del piloto.
2. Ejecuta `docker compose up --build -d`. La API aplica las migraciones al arrancar.
3. Prepara el piloto local con `docker compose exec api python -m db.initialize_collectives --local-only --create-pilot`. Esto agrega el piloto y los colectivos que falten. La carga de `db/demo.sql` es una alternativa para una base de pruebas vacía.
4. Crea el primer administrador con `docker compose exec api python -m db.provision_admin --local-only DOCUMENTO "Nombre"`. El comando solicita el PIN de forma interactiva. Si su cuenta ya existe, usa `docker compose exec -e ECO_ALLOW_ADMIN_BOOTSTRAP=true api python -m db.promote_admin --local-only --national-id DOCUMENTO`.
5. Abre la [documentación OpenAPI local](http://localhost:8000/docs).

Para habilitar una coordinadora, regístrala desde la página local. Entra como administrador, búscala en **Usuarios y roles**, elige **Coordinación** y su colectivo, y guarda. Al iniciar sesión verá la bandeja de huerta o reciclaje. Los recolectores se mantienen como integrantes operativos registrados en PostgreSQL.

Para conectar el frontend, la especificación está en `/openapi.json`. Las rutas privadas usan `Authorization: Bearer <token>`. Los formularios de alta de recolección reutilizan la misma cabecera `Idempotency-Key` al reintentar un envío. Consulta [los contratos de integración](docs/contratos-modulos.md) para los campos y traducciones.

## Preparar la demostración local (solo desarrollo)

`sh scripts/prepare_demo.sh` verifica Docker, PostgreSQL, la API y los siete perfiles del piloto local. Crea solo los que faltan, sin duplicar ni borrar datos. Se niega a ejecutarse contra bases que no sean locales. Usa `--check` para verificar sin crear.

Las cuentas 10001 (vecino), 20001 (coordinación de huerteros) y 30001 (coordinación de recicladores) usan el PIN documentado `1234`. Los PIN que se generen para las demás cuentas se muestran una sola vez en la terminal interactiva y no se guardan.

Para asignar un PIN temporal a otra cuenta de demostración, ejecuta `docker compose exec api python -m db.prepare_demo --local-only --set-pin CEDULA`.

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
