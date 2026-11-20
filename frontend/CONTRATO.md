# Frontend de EcoConecta

Desde este directorio, con Node 22 y npm, ejecutar `npm ci` y `npm run dev`. `npm run build` genera la distribución. El modo demo usa tres cuentas ficticias seleccionables en el inicio de sesión. El PIN es 1234. Las operaciones se comparten entre esos perfiles en el almacenamiento local del mismo origen y navegador. La sesión y el borrador pertenecen a la pestaña. Usar únicamente información ficticia en la demo.

## Acceso a datos

`src/data.js` intercambia el adaptador local por HTTP si se define `VITE_API_URL` en `.env.local` antes de iniciar o compilar. La URL puede ser un origen o un prefijo como `/api`. El modo HTTP usa sesión Bearer y propaga los errores. Consultas basadas en cuentas `63743b6`, recolecciones `4312edc` y PostgreSQL `2df1b7f`.

| Pantalla | Operación HTTP |
| --- | --- |
| Acceso | POST /accounts/login con national_id y pin; GET /accounts/me; POST /accounts/logout |
| Alta | POST /recolecciones con Idempotency-Key, residuo, material, contacto, direccion, generador, disponibilidad y observaciones |
| Panel del cliente | GET /community/collections, /community/appointments, /community/points y /community/notifications |
| Panel de líderes | GET /recolecciones y /recolecciones/avisos; la identidad de la sesión determina el colectivo |
| Agenda | POST /recolecciones/{id}/programar con cita y motivo para una reprogramación |
| Cierre | POST /recolecciones/{id}/cerrar con material, kilos y resultado total o parcial |

Un borrador tiene una clave por usuario y contenido. El mismo envío conserva su clave después de un error o de recargar la pestaña. Editar el contenido crea otra clave. El borrador se descarta cuando el servidor confirma el alta. Las citas se envían con desplazamiento de Barranquilla y se presentan en America/Bogota.

## Pendientes para Codex 03

- Confirmar SHA integrado, URL, perfiles de prueba, turnos y acceso desde el origen del frontend (CORS o proxy). Verificar que una creación en /recolecciones se pueda leer desde /community/collections bajo la misma identidad y que el aviso se proyecte a /community/notifications.
- El estado operativo usa recibida, revision, programada, recolectada o cancelada. Comunidad expone received, under_review, scheduled, collected o cancelled. La API de comunidad tiene además un alta con flow, description, contact, address y ventana horaria. La demo utiliza el alta de recolecciones por su contrato explícito de idempotencia.
- El panel de cliente recibe responsible_name; el de líderes solo recibe el UUID responsable. Confirmar si se publicará su nombre en la bandeja de líderes. El catálogo de identificadores de colectivos también requiere una etiqueta legible para mostrar en el panel.
- La demo asigna un responsable ficticio por turno y diez puntos por kilo con redondeo hacia abajo. En modo HTTP el servidor asigna el turno y devuelve el saldo y las citas. Confirmar las reglas de puntos y la respuesta ante un turno no disponible en el despliegue integrado.
- Prueba de aceptación integrada: crear solicitud como cliente, confirmar su aislamiento entre colectivos, agendar como líder, consultar la cita y el responsable como cliente, cerrar como líder y verificar estado, puntos y avisos internos como cliente.
