# EcoConecta

Backend compartido de EcoConecta para cuentas, guía ambiental y flujos HTTP de la comunidad. La persistencia PostgreSQL se integra mediante los contratos de `docs/contratos-modulos.md`.

## Mapa del repositorio

- `frontend/`: espacio reservado para el equipo de frontend.
- `backend/app/main.py`: composición de la API FastAPI.
- `backend/app/accounts/`: registro, PIN, sesiones e identidad para módulos consumidores.
- `backend/app/content/`: guía ambiental con borradores y publicaciones.
- `backend/app/community/`: HTTP autenticado para solicitudes, citas, avisos, puntos y canjes.
- `backend/tests/`: pruebas por área con almacenes y gateways falsos.
- `db/migrations/`: historial SQL coordinado por funcionalidad si se mantiene esta estrategia.
- `docs/`: acuerdos de desarrollo e integración.

## Responsabilidades

- **Codex 1:** composición, configuración, sesiones, Docker base, cuentas, piloto y contenidos (`accounts/`, `content/`).
- **Codex 2:** solicitudes, agenda y cierre de recolecciones (`collections/`) y su interfaz de cierre.
- **Codex 3:** puntos, premios y canjes (`points/`) y la función de acreditación.

Cada responsable mantiene las pruebas y migraciones de su área y coordina el orden de integración.

## Preparar y ejecutar

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/uvicorn backend.app.main:app --reload
```

La documentación interactiva aparece en `/docs`. Las rutas que dependen de PostgreSQL o de Codex 2/3 devuelven `503` hasta que se inyecten sus adaptadores; el contrato está en `docs/contratos-modulos.md`.

## Desarrollo y pruebas

Ejecuta `.venv/bin/pytest`. Las pruebas actuales usan almacenes falsos y no escriben en una base real. Las pruebas integradas que escriban datos deben usar una base PostgreSQL aislada indicada por `TEST_DATABASE_URL`. Cada rama puede probarse con dependencias simuladas; el MVP conjunto se valida al integrar las ramas. Copia `.env.example` a `.env` y completa los valores localmente; nunca compartas secretos.
