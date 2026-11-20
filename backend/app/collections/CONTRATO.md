# Integración de recolecciones

## API común y comunidad (Codex 1)

Montar `router(Collections(transaction), authenticated_actor)` en la aplicación FastAPI común. El módulo utiliza Pydantic 2. La dependencia de sesión traduce la identidad verificada a `Actor(id, rol, flujo)`. El cliente usa el rol `cliente` y la coordinadora usa `lider` con flujo `huerta` o `reciclaje`. El equipo de campo se identifica mediante su UUID de turno. Los cuerpos de las solicitudes no eligen el actor.

La API de comunidad puede llamar directamente a `Collections.create(actor, key, request)` o utilizar `POST /recolecciones` con la cabecera `Idempotency-Key`. El formulario conserva una clave por envío lógico hasta obtener la respuesta. El tipo de residuo elegido determina el flujo. El servicio devuelve el registro con su UUID estable. En la bandeja, el parámetro `estado` admite `recibida` para pendientes, `programada`, `recolectada` para atendidas y `cancelada`. Las citas sin desplazamiento se interpretan en hora de Barranquilla.

Los errores funcionales usan `Problem` y las rutas los traducen a `{"detail": "..."}`. Códigos propuestos para integración: 403 para rol o piloto, 404 para solicitud inexistente en el colectivo, 409 para conflicto de estado, turno o clave y 422 para datos inválidos. La autenticación y su respuesta 401 pertenecen a la aplicación común.

## Persistencia y puntos (Codex 3)

`service.Transaction` define el puerto que debe implementar el adaptador de PostgreSQL. El contexto confirma al salir con éxito y revierte ante cualquier excepción. Cada llamada usa una única transacción y conexión, incluida la acreditación. El adaptador debe devolver registros materializados.

- `reserve` necesita unicidad por operación, propietario y clave. Dos inserciones concurrentes deben converger en una fila. `locked` filtra por colectivo y bloquea la fila hasta finalizar la transacción.
- `on_duty` consulta el turno vigente para el colectivo y el instante solicitado. Devuelve el UUID de la persona asignada o ausencia de turno.
- `event` guarda hora del evento, instantánea, autora y motivo. Registra también el aviso en las bandejas correspondientes. Para una cita incluye día, hora y responsable. Una visita fallida conserva el turno anterior como evidencia y el aviso indica que se requiere nueva cita. Los avisos se consultan dentro de EcoConecta mediante `GET /recolecciones/avisos`. El adaptador devuelve los avisos del cliente por su UUID autenticado o los del colectivo de la líder. El celular en `contacto` se conserva como dato de la solicitud.
- `credit` recibe el UUID estable de la recolección o entrega directa, UUID del cliente, material y kilos decimales. PostgreSQL debe garantizar un solo movimiento por entrega. Los valores de puntos se resuelven en el módulo de puntos.
- `summary` filtra por colectivo y fecha de alta en el intervalo desde inclusivo y hasta exclusivo. Devuelve flujo, periodo y conteos por estado vigente. Las consultas de avisos e historial deben conservar el filtro de colectivo.
- `set_stock` registra la cantidad absoluta y autora, serializando cambios de existencias con canjes. `redeem` comprueba código, saldo y disponibilidad en PostgreSQL y devuelve un comprobante. Un reintento confirmado devuelve el mismo comprobante. Un rechazo de negocio revierte la transacción completa.

## Verificación

### Contratos publicados el 20 de noviembre

Para montar las rutas operativas en la app de Codex 01 (`d251a68`):

```python
from backend.app.accounts.dependencies import get_current_identity
from backend.app.collections.api import account_actor, router
from backend.app.collections.service import Collections

app.include_router(router(Collections(transaction), account_actor(get_current_identity, collectives)))
```

`collectives` relaciona identificadores del catálogo con `huerta` o `reciclaje`. La dependencia traduce roles `resident` y `business` a cliente y exige colectivo conocido para `leader`. La app publicada tiene un bloqueo de importación en Python 3.11: la anotación de `CommunityService.list_appointments` referencia `AppointmentView` antes de su definición.

El gateway de las rutas `/community` es una integración adicional. Debe traducir `organic → organico → huerta`, `recyclable → reciclable → reciclaje` y los estados `recibida/revision/programada/recolectada/cancelada` a `received/under_review/scheduled/collected/cancelled`. Debe proyectar lecturas por dueño, fecha de creación y nombre del responsable. Codex 01 debe transportar la clave de reintento del envío hasta `create_for_user`; la firma publicada solo recibe identidad y comando. Dos entregas intencionales pueden tener idéntico contenido.

En Codex 03 (`2df1b7f`), el esquema necesita representar colectivo, flujo, clave de alta y responsable de turno para materializar las consultas y restricciones del puerto. El adaptador debe resolver el material al UUID de catálogo, preservar el resultado parcial y diferenciar el UUID de solicitud del de entrega. La entrega directa también requiere resolver un responsable de campo. Las funciones publicadas de cierre y entrega directa abren su propia conexión y acreditan puntos. Invocarlas desde `Transaction.credit` abriría una transacción independiente. La integración debe compartir conexión y transacción para cierre, historial, aviso y abono, con un único escritor de cada movimiento.

Desde la raíz, con FastAPI, Pydantic 2 y httpx instalados, ejecutar `python -m unittest discover -s backend/tests/collections -v`. Las pruebas HTTP usan identidades ficticias y un doble con reversión. La concurrencia entre conexiones, los turnos reales, la persistencia de los avisos internos y los movimientos de saldo y stock se verifican después con el adaptador compartido y una base PostgreSQL aislada.
