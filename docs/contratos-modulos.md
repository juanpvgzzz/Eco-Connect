# Contratos de integración

Este documento fija las interfaces que consume HTTP. Los adaptadores PostgreSQL implementan las firmas de `backend/app/**/ports.py`. Las pruebas unitarias usan dobles explícitos y las pruebas de integración usan PostgreSQL 16.

## Cuentas y sesiones — persistencia compartida (Codex 3)

`AccountStore` debe implementar `find_by_national_id`, `find_by_id`, `create_account`, `set_authorization`, `is_login_locked`, `record_login_failure`, `clear_login_failures`, `save_session`, `find_session` y `revoke_session`.

- `national_id` se recibe normalizado a solo dígitos y requiere una restricción única en PostgreSQL. `create_account` traduce colisión a `DuplicateNationalId` ante registros concurrentes.
- `is_login_locked`, `record_login_failure` y `clear_login_failures` usan la clave SHA-256 `attempt_key` entregada por la aplicación. Actualizan el contador de forma atómica con el umbral y ventana recibidos e incluyen identificadores existentes y desconocidos para conservar respuestas uniformes. El adaptador debe podar filas vencidas para limitar crecimiento. Nunca almacena PIN en claro.
- Persistir el digest SHA-256 del token y `expires_at`/`revoked_at`; no persistir el token sin transformar. `find_session` solo devuelve sesiones existentes.
- `set_authorization` cambia rol, piloto y `collective_id` en la cuenta ya existente. El rol líder requiere un colectivo válido. El adaptador crea la cuenta administrativa inicial mediante un proceso operativo confiable, nunca desde registro público.

## Contenidos — persistencia compartida (Codex 3)

`ContentStore` ofrece lectura filtrada a publicados para `list_published`, lectura por id para `find_content`, lectura administrativa `list_all` y escritura `save_content`. La aplicación verifica rol admin; el adaptador conserva autor, estado y fechas.

## Recolecciones, citas y avisos — Codex 2

`CommunityCollectionsGateway.create_for_user(actor, request, idempotency_key)` recibe la identidad autenticada, el comando validado y la cabecera `Idempotency-Key` obligatoria. Debe conservar la clave hasta `Collections.create(actor, key, request)` de Codex 2; el cliente reutiliza la misma clave en reintentos del mismo envío y crea una nueva para otro envío. La clave se recorta y limita a 128 caracteres en la capa HTTP. El módulo Codex 2 reserva por propietario y clave y devuelve el mismo registro si la solicitud coincide; reutilizarla con otros datos produce conflicto.

### Traducción entre Cuentas y Codex 02

La ruta de cuentas expone `POST /community/collections` con `flow`, `description`, `contact`, `address` y una ventana `preferred_from`/`preferred_until`. Codex 02 expone `POST /recolecciones` con `residuo`, `material`, `contacto`, `direccion`, `generador`, `disponibilidad` y `observaciones`. El adaptador debe traducir explícitamente:

| Cuentas / comunidad | Codex 02 | Regla |
| --- | --- | --- |
| `organic` | `organico` | flujo orgánico |
| `recyclable` | `reciclable` | flujo reciclable |
| `actor.id` | `Actor.id` UUID | usar el ID autenticado; el cuerpo no elige propietario |
| `household` / `business` | `hogar` / `unidad_productiva` | `generador`; pilotaje empresarial sigue siendo autorización del adaptador |
| `Idempotency-Key` | argumento `key` de `Collections.create` | conservar la misma clave del envío lógico |

La descripción se conserva completa en `observaciones`. La ventana se representa como dos instantes ISO 8601 en UTC separados por `/` en `disponibilidad`. El formulario comunitario indica el flujo, por lo que el adaptador usa `Orgánico` o `Reciclable` en el campo descriptivo `material`; el catálogo determina el material y la tarifa al cerrar la entrega. La clave y el propietario delimitan el reintento.

`ECO_PILOT_ID` identifica el piloto de la instancia. La cuenta de cada líder referencia un colectivo de ese piloto. El catálogo asigna un colectivo por flujo y piloto. El adaptador controla el acceso de las unidades productivas con `pilot_enabled`. En solicitudes antiguas, asigna el flujo después de revisar los datos operativos para habilitar la bandeja de la líder.

Para lectura, `list_for_user(owner_id)`, `get_for_user(owner_id, request_id)`, `list_notifications_for_user(owner_id)` y `list_appointments_for_user(owner_id)` deben filtrar en origen por el propietario solicitado. Una empresa no habilitada lanza `BusinessNotEnabled` y HTTP responde 403. Estados consumidos: `received`, `under_review`, `scheduled`, `collected`, `cancelled`. Las citas deben incluir fecha con zona horaria y responsable; solo entonces el estado puede ser `scheduled`. HTTP las convierte a `America/Bogota`.

La solicitud HTTP contiene flujo (`organic` o `recyclable`), descripción, contacto, dirección y ventana de disponibilidad futura con zona explícita. La identidad autenticada determina al usuario y aporta el tipo de generador; se ignora cualquier `owner_id` enviado por el cliente. El adaptador enruta orgánicos a huerteros y reciclables a recicladores, sujeto al puente de piloto/colectivo pendiente arriba.

Un registro con estado `scheduled` requiere fecha/hora con zona y persona encargada. La cita se presenta al usuario en `America/Bogota`; respuestas de otros estados no cuentan como cita programada.

## Puntos y canjes — Codex 3 y Codex 2

`CommunityPointsGateway` ofrece `get_points_for_user(owner_id)`, `list_movements_for_user(owner_id)`, `list_rewards()` y `request_code_for_user(owner_id, reward_id)`. Las lecturas privadas filtran por dueño. La solicitud devuelve un código sin debitar puntos; la confirmación del canje sigue en la API de Codex 2. Saldo insuficiente se traduce a `InsufficientPoints`.

El código dura 24 horas. La confirmación revalida el saldo y las existencias, y aplica el débito y la reducción de stock en una transacción. La repetición de un código confirmado devuelve el mismo comprobante.

## Composición

`backend.app.main:app` carga los adaptadores PostgreSQL y las rutas de `/recolecciones` cuando se configuran `DATABASE_URL` y `ECO_PILOT_ID`. Para pruebas unitarias, `create_app` acepta los adaptadores por parámetro. Sin adaptador para una ruta de cuentas, contenidos o comunidad, esa ruta responde `503`.

Las transiciones de recolección, los avisos, el cierre y el abono usan una sola transacción. La migración `002_api_integration.sql` conserva el historial de la migración inicial y agrega los catálogos y columnas de integración.
