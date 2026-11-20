# Contratos de integración

Este documento fija las interfaces que consume HTTP. Los adaptadores PostgreSQL y los módulos dueños deben implementar las firmas de `backend/app/**/ports.py`; las pruebas actuales usan dobles explícitos. Confirmar estos contratos al integrar las ramas de Codex 2 y Codex 3.

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

### Traducción pendiente entre Cuentas y Codex 02

La ruta de cuentas expone `POST /community/collections` con `flow`, `description`, `contact`, `address` y una ventana `preferred_from`/`preferred_until`. Codex 02 expone `POST /recolecciones` con `residuo`, `material`, `contacto`, `direccion`, `generador`, `disponibilidad` y `observaciones`. El adaptador debe traducir explícitamente:

| Cuentas / comunidad | Codex 02 | Regla |
| --- | --- | --- |
| `organic` | `organico` | flujo orgánico |
| `recyclable` | `reciclable` | flujo reciclable |
| `actor.id` | `Actor.id` UUID | usar el ID autenticado; el cuerpo no elige propietario |
| `household` / `business` | `hogar` / `unidad_productiva` | `generador`; pilotaje empresarial sigue siendo autorización del adaptador |
| `Idempotency-Key` | argumento `key` de `Collections.create` | conservar la misma clave del envío lógico |

`description` no equivale necesariamente a `material` más `observaciones`, y la ventana con dos fechas no cabe sin pérdida en el texto `disponibilidad`; el adaptador debe acordar esos dos mapeos antes de conectarse. Codex 02 espera roles `cliente`/`lider` y UUIDs, mientras Cuentas usa roles `resident`/`business`/`leader` y guarda IDs como texto; el adaptador valida y convierte esas identidades. `AccountIdentity.collective_id` no tiene campo equivalente en `Actor`: Codex 02 usa `Actor.flujo` (`huerta`/`reciclaje`) como ámbito de liderazgo, no como ID de colectivo. Además, su `Transaction.pilot(client)` no recibe el `pilot_id` de Cuentas. No inferir colectivo ni piloto desde el flujo o `pilot_enabled`; falta definir el puente de IDs y alcance en el adaptador real.

Para lectura, `list_for_user(owner_id)`, `get_for_user(owner_id, request_id)`, `list_notifications_for_user(owner_id)` y `list_appointments_for_user(owner_id)` deben filtrar en origen por el propietario solicitado. Una empresa no habilitada lanza `BusinessNotEnabled` y HTTP responde 403. Estados consumidos: `received`, `under_review`, `scheduled`, `collected`, `cancelled`. Las citas deben incluir fecha con zona horaria y responsable; solo entonces el estado puede ser `scheduled`. HTTP las convierte a `America/Bogota`.

La solicitud HTTP contiene flujo (`organic` o `recyclable`), descripción, contacto, dirección y ventana de disponibilidad futura con zona explícita. La identidad autenticada determina al usuario y aporta el tipo de generador; se ignora cualquier `owner_id` enviado por el cliente. El adaptador enruta orgánicos a huerteros y reciclables a recicladores, sujeto al puente de piloto/colectivo pendiente arriba.

Un registro con estado `scheduled` requiere fecha/hora con zona y persona encargada. La cita se presenta al usuario en `America/Bogota`; respuestas de otros estados no cuentan como cita programada.

## Puntos y canjes — Codex 3 y Codex 2

`CommunityPointsGateway` ofrece `get_points_for_user(owner_id)`, `list_movements_for_user(owner_id)`, `list_rewards()` y `request_code_for_user(owner_id, reward_id)`. Las lecturas privadas filtran por dueño. La solicitud devuelve un código sin debitar puntos; la confirmación del canje sigue en la API de Codex 2. Saldo insuficiente se traduce a `InsufficientPoints`.

Los adaptadores reales de Codex 02 y Codex 03 aún no están montados en esta rama. Si falta el gateway necesario, las rutas responden 503; mientras tanto, las pruebas usan dobles explícitos. La integración sigue pendiente de la traducción de solicitud/identidad anterior, del puente piloto-colectivo y de conectar consultas de citas/avisos y puntos al almacenamiento compartido.

## Inyección en la app

El adaptador compartido crea la app con `create_app(account_store=..., content_store=..., collections_gateway=..., points_gateway=...)`. Las rutas de recolección requieren solo `collections_gateway`; las rutas de puntos solo `points_gateway`. Si falta el adaptador requerido por una ruta, esta responde `503`; no se usa persistencia en memoria en producción.
