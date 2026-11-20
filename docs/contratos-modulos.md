# Contratos de integración

Este documento fija las interfaces que consume HTTP. Los adaptadores PostgreSQL y los módulos dueños deben implementar las firmas de `backend/app/**/ports.py`; las pruebas actuales usan dobles explícitos. Confirmar estos contratos al integrar las ramas de Codex 2 y Codex 3.

## Cuentas y sesiones — persistencia compartida (Codex 3)

`AccountStore` debe implementar `find_by_national_id`, `find_by_id`, `create_account`, `set_authorization`, `is_login_locked`, `record_login_failure`, `clear_login_failures`, `save_session`, `find_session` y `revoke_session`.

- `national_id` se recibe normalizado a solo dígitos y requiere una restricción única en PostgreSQL. `create_account` traduce colisión a `DuplicateNationalId` ante registros concurrentes.
- `record_login_failure` actualiza contadores y bloqueo de forma atómica por cédula, usando el umbral y ventana recibidos. Nunca almacena PIN en claro.
- Persistir el digest SHA-256 del token y `expires_at`/`revoked_at`; no persistir el token sin transformar. `find_session` solo devuelve sesiones existentes.
- `set_authorization` cambia rol y piloto en la cuenta ya existente. El adaptador crea la cuenta administrativa inicial mediante un proceso operativo confiable, nunca desde registro público.

## Contenidos — persistencia compartida (Codex 3)

`ContentStore` ofrece lectura filtrada a publicados para `list_published`, lectura por id para `find_content`, lectura administrativa `list_all` y escritura `save_content`. La aplicación verifica rol admin; el adaptador conserva autor, estado y fechas.

## Recolecciones, citas y avisos — Codex 2

`CommunityCollectionsGateway` recibe `AccountIdentity` en `create_for_user(actor, request)` para que Codex 2 aplique elegibilidad del comercio piloto y guarde/avise mediante su operación de alta. Para lectura, `list_for_user(owner_id)`, `get_for_user(owner_id, request_id)`, `list_notifications_for_user(owner_id)` y `list_appointments_for_user(owner_id)` deben filtrar en origen por el propietario solicitado. Una empresa no habilitada lanza `BusinessNotEnabled`. Estados consumidos: `received`, `scheduled`, `collected`, `cancelled`. Las citas deben incluir fecha con zona horaria y responsable; HTTP las convierte a `America/Bogota`.

La solicitud HTTP contiene descripción, contacto, dirección y ventana de disponibilidad futura con zona explícita. La identidad autenticada determina al usuario; se ignora cualquier `owner_id` enviado por el cliente.

## Puntos y canjes — Codex 3 y Codex 2

`CommunityPointsGateway` ofrece `get_points_for_user(owner_id)`, `list_movements_for_user(owner_id)`, `list_rewards()` y `request_code_for_user(owner_id, reward_id)`. Las lecturas privadas filtran por dueño. La solicitud devuelve un código sin debitar puntos; la confirmación del canje sigue en la API de Codex 2. Saldo insuficiente se traduce a `InsufficientPoints`.

## Inyección en la app

El adaptador compartido crea la app con `create_app(account_store=..., content_store=..., collections_gateway=..., points_gateway=...)`. Hasta entonces, las rutas dependientes responden `503`; no se usa persistencia en memoria en producción.
