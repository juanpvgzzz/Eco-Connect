# Acuerdos de desarrollo e integración

## API y estructura

Si el equipo aún no ha elegido framework, el acuerdo inicial es FastAPI. La composición de la API vive en `backend/app/`; cada área implementa su lógica en su propio paquete. `frontend/` queda reservado. Esta base no define endpoints de producto ni dependencias adicionales.

## Datos y migraciones

Usa PostgreSQL para el desarrollo integrado. Las pruebas que escriben datos deben apuntar a una base de prueba aislada mediante `TEST_DATABASE_URL`; no reutilices datos de desarrollo. Las ramas funcionales mantienen sus migraciones y coordinan el orden antes de integrar el MVP.

## Dueños de carpetas

- Codex 1: composición, configuración, sesiones, Docker base, `accounts/` y `content/`.
- Codex 2: `collections/` y su interfaz de cierre.
- Codex 3: `points/` y su función de acreditación.

Cada responsable actualiza sus pruebas. Las ramas de trabajo deben partir del mismo commit base y mantenerse independientes hasta la integración acordada.
