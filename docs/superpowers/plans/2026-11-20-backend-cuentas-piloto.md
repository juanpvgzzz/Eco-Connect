# Backend de cuentas y contenidos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar la API HTTP del usuario para cuentas, guía, recolecciones, citas, notificaciones, puntos y solicitud de códigos de canje.

**Architecture:** Routers FastAPI delegan en servicios de dominio. Persistencia se expresa como protocolos consumibles por el adaptador de Codex 3; esta rama no crea tablas ni conexión paralela. Las sesiones son tokens opacos persistidos por el puerto y revocables al cerrar sesión.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, pwdlib con Argon2, pytest, HTTPX.

**Spec:** `../01_Codex_Backend_Usuario.md` proporcionado fuera del repositorio; alcance y límites también en `docs/desarrollo.md`.

## Global Constraints

- Solo la administración crea perfiles de administrador o líder y habilita comercios piloto.
- No duplicar modelos, conexión ni migraciones que pertenecen a Codex 3.
- Las operaciones de datos propios filtran por el id autenticado.
- Cada solicitud incluye flujo orgánico o reciclable y se entrega al coordinador correspondiente.
- Una cita no está programada sin fecha, hora y persona encargada.
- Pruebas con datos ficticios y almacenes aislados.
- Las funcionalidades de recolecciones y puntos esperan los contratos reales de Codex 2 y Codex 3.

## Review Focus

- Dos registros simultáneos con la misma cédula: solo uno debe persistir por la restricción única del almacén.
- Cédula inexistente y PIN incorrecto: respuesta de autenticación indistinguible y contador aplicado.
- Token vencido, revocado o alterado: no autentica.
- Atributos de rol enviados en el registro: rechazo y sin privilegios.
- Contenido en borrador: nunca aparece en consulta pública.

---

### Task 1: Cuentas, identidad y sesiones

**Files:** `backend/app/accounts/{models,ports,service,schemas,router,dependencies}.py`; `backend/app/main.py`; `backend/tests/accounts/test_service.py`; `backend/tests/accounts/test_api.py`.

**Interfaces:** Expone `get_current_identity` para módulos consumidores. El puerto de persistencia incluye cuentas, contador de intentos y sesiones; Codex 3 implementa su adaptador.

- [x] Probar registro, hashing Argon2, rol público limitado, bloqueo tras cinco fallos, sesión y revocación.
- [x] Probar rutas HTTP de registro, login, perfil propio y logout con un almacén falso.
- [x] Implementar lo mínimo para pasar las pruebas y documentar contrato del puerto.

### Task 2: Guía ambiental y administración

**Files:** `backend/app/content/{models,ports,service,schemas,router}.py`; `backend/tests/accounts/test_content.py`.

**Interfaces:** Contenido clasificado en materiales, separación, huerta, rutas y horarios; lectura pública solo publicada y cambios reservados a admin.

- [x] Probar visibilidad de borradores, permisos y publicación.
- [x] Implementar servicio y rutas con almacén falso.

### Task 3: HTTP de comunidad, composición y contratos

**Files:** `backend/app/community/`; `backend/app/main.py`; `backend/tests/accounts/test_community_api.py`; `docs/contratos-modulos.md`; `docs/desarrollo.md`; `README.md`.

- [x] Probar ownership, ambos flujos, citas completas, validación de disponibilidad, hora local y canje sin débito.
- [x] Implementar gateways explícitos para Codex 2/3; no duplicar sus reglas ni persistencia.
- [x] Incluir routers, composición, contratos y comandos de instalación, prueba y arranque.
- [x] Verificar pruebas, importación de OpenAPI y `git diff --check`.

### Explicitly deferred

La app no trae aún adaptadores PostgreSQL ni implementaciones de Codex 2/3; las rutas de esas áreas están listas para gateways definidos en `docs/contratos-modulos.md` y devuelven `503` si no se inyectan. Confirmar y ajustar firmas al recibir los contratos reales antes de integrar ramas.
