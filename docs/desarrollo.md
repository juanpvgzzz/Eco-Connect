# Acuerdos de desarrollo e integración

## API y estructura

FastAPI es el framework inicial. La composición vive en `backend/app/main.py`; `accounts/` expone `get_current_identity`, `content/` sirve la guía y `community/` contiene rutas HTTP de usuario. `frontend/` queda reservado.

## Datos y migraciones

Usa PostgreSQL para el desarrollo integrado. Las pruebas que escriben datos deben apuntar a una base de prueba aislada mediante `TEST_DATABASE_URL`; no reutilices datos de desarrollo. Codex 3 mantiene conexión, modelos compartidos e historial de migraciones. Las otras áreas coordinan con Codex 3 los cambios de persistencia. Los adaptadores reales se implementan contra `contratos-modulos.md`.

## Dueños de carpetas

- Codex 1: composición, configuración, sesiones, Docker base, `accounts/` y `content/`.
- Codex 2: `collections/` y su interfaz de cierre.
- Codex 3: `points/` y su función de acreditación.

Cada responsable actualiza sus pruebas. Las ramas de trabajo deben partir del mismo commit base y mantenerse independientes hasta la integración acordada.

## Autenticación

El registro acepta hogares y comercios y asigna únicamente `resident` o `business`. El PIN se almacena con Argon2; los tokens de sesión son opacos, se persisten como SHA-256 y caducan a las 12 horas. Cinco intentos fallidos en 15 minutos bloquean nuevos intentos por 15 minutos; el contador se comparte entre cédulas existentes e inexistentes y el adaptador debe podar registros vencidos. La administración inicial debe provisionarse por un mecanismo confiable del adaptador; no hay alta pública de administradores o líderes. Los perfiles líder requieren `collective_id`.

## Estado de integración

Los tests disponibles usan dobles en memoria. La app exportada no sirve rutas que necesitan persistencia hasta recibir `account_store`, `content_store`, `collections_gateway` y `points_gateway` en `create_app`.
