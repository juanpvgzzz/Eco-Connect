# EcoConecta

Base compartida para el backend de EcoConecta y el futuro frontend. El repositorio aún no incluye funcionalidades de producto.

## Mapa del repositorio

- `frontend/`: espacio reservado para el equipo de frontend.
- `backend/app/`: composición y configuración común de la API en Python; los módulos se separan por responsabilidad.
- `backend/tests/`: pruebas de cada área, junto a sus responsabilidades.
- `db/migrations/`: historial SQL coordinado por funcionalidad si se mantiene esta estrategia.
- `docs/`: acuerdos de desarrollo e integración.

## Responsabilidades

- **Codex 1:** composición, configuración, sesiones, Docker base, cuentas, piloto y contenidos (`accounts/`, `content/`).
- **Codex 2:** solicitudes, agenda y cierre de recolecciones (`collections/`) y su interfaz de cierre.
- **Codex 3:** puntos, premios y canjes (`points/`) y la función de acreditación.

Cada responsable mantiene las pruebas y migraciones de su área y coordina el orden de integración. No se han agregado endpoints ni dependencias de producto.

## Desarrollo y pruebas

FastAPI es el acuerdo inicial si se incorpora el framework; esta base solo reserva la estructura. Las pruebas que escriben datos deben usar una base PostgreSQL aislada. Cada rama puede probarse con sus dependencias simuladas. El MVP conjunto se valida al integrar las ramas. Copia `.env.example` a `.env` y completa los valores localmente; nunca compartas secretos.
