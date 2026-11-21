// Renderizado de cada pantalla con datos con la forma real de la API.
// Detecta referencias indefinidas o props nulas antes de llegar al navegador.
import { test, before, after, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createElement as h } from "react";
import { renderToString } from "react-dom/server";
import { close, load, memoryStorage } from "./helpers.js";

const user = { id: "u1", collective_id: null, profile: { full_name: "Ana María Pérez", national_id: "123", phone: "3001234567", address: "Manzana 12, Casa 8, Villas de San Pablo, Barranquilla", kind: "household", role: "resident", pilot_enabled: true } };
const seen = { isNew: () => false, setSeenAt() {}, markSeen: () => 0 };
const residentData = {
  rows: [
    { id: "r1", status: "received", description: "Llamar antes", address: "Manzana 12, Casa 8, Villas de San Pablo", created_at: "2026-11-20T10:00:00Z", flow: "recyclable", material: "Cartón, Botellas plásticas", availability: "Lunes · Mañana", notes: "Llamar antes" },
    { id: "r2", status: "scheduled", description: "Orgánico", address: "Calle 1", created_at: "2026-11-19T10:00:00Z", flow: "organic", material: "Cáscaras", availability: null, notes: null },
    { id: "r3", status: "collected", description: "Solicitud antigua", address: "Calle 2", created_at: "2026-11-01T10:00:00Z" },
  ],
  notices: [{ id: "n1", title: "Recolección programada", message: "Recolección programada. 21/11/2026 09:00. Luis", created_at: "2026-11-20T11:00:00Z" }],
  appointments: [{ collection_id: "r2", status: "scheduled", scheduled_at: "2026-11-22T14:00:00Z", responsible_name: "Luis Gómez" }],
  points: { balance: 40 },
  movements: [{ id: "m1", points: 40, reason: "Entrega", created_at: "2026-11-02T10:00:00Z" }],
};
const leaderRows = [
  { id: "a", cliente: "c", flujo: "huerta", estado: "recibida", solicitud: { residuo: "organico", material: "Cáscaras", contacto: "3001234567", direccion: "Manzana 1, Casa 2", generador: "hogar", disponibilidad: "Lunes · Mañana", observaciones: "" }, cita: null, responsable: null, nombre_responsable: null, entrega: null },
  { id: "b", cliente: "c", flujo: "huerta", estado: "programada", solicitud: { residuo: "organico", material: "Poda", contacto: "3001234567", direccion: "Calle 3", generador: "unidad_productiva", disponibilidad: "Martes", observaciones: "Perro bravo" }, cita: "2026-11-22T14:00:00Z", responsable: "x", nombre_responsable: "Luis Gómez", entrega: null },
  { id: "c", cliente: "c", flujo: "huerta", estado: "recolectada", solicitud: null, entrega: { material: "Compost", kilos: "2.500", resultado: "total" } },
];

let m;
before(async () => {
  m = {
    ...(await load("/src/app/App.jsx")),
    ...(await load("/src/features/auth/Login.jsx")),
    ...(await load("/src/features/auth/Registration.jsx")),
    ...(await load("/src/features/resident/ResidentHome.jsx")),
    ...(await load("/src/features/resident/RequestCard.jsx")),
    ...(await load("/src/features/leader/LeaderBoard.jsx")),
    ...(await load("/src/features/notices/NoticeList.jsx")),
    ...(await load("/src/features/notices/model.js")),
    ...(await load("/src/components/ErrorBoundary.jsx")),
    ...(await load("/src/features/operations/AppHeader.jsx")),
    ...(await load("/src/features/admin/AdminDashboard.jsx")),
    ...(await load("/src/features/leader/LeaderCard.jsx")),
    ...(await load("/src/features/resident/HistoryView.jsx")),
    ...(await load("/src/features/resident/NextPickup.jsx")),
    ...(await load("/src/features/resident/CalendarView.jsx")),
    ...(await load("/src/features/resident/PointsView.jsx")),
    ...(await load("/src/features/resident/RequestTimeline.jsx")),
    ...(await load("/src/features/worker/WorkerHome.jsx")),
    ...(await load("/src/features/resident/EducationLibrary.jsx")),
  };
});
after(close);
beforeEach(() => {
  globalThis.sessionStorage = memoryStorage();
});

test("inicio de sesión: título, campos, mostrar PIN y crear cuenta", () => {
  const html = renderToString(h(m.Login, { onLogin() {} }));
  for (const text of ["Iniciar sesión", "Cédula", "PIN", "Mostrar PIN", "Entrar", "Crear cuenta"]) assert.ok(html.includes(text), text);
  assert.match(html, /autoComplete="current-password"|autocomplete="current-password"/i);
});

test("registro: primer paso con nombre, cédula y celular colombiano", () => {
  const html = renderToString(h(m.Registration, { onBack() {}, onCreated() {} })).replaceAll("<!-- -->", "");
  for (const text of ["Crear cuenta", "Datos y contacto", "Datos personales", "Contacto", "Nombre completo", "Cédula", "Celular", "+57", "Paso 1 de 3"]) assert.ok(html.includes(text), text);
});

test("inicio del vecino: acción principal, cuatro accesos, cita y hasta tres solicitudes", (context) => {
  context.mock.method(Date, "now", () => Date.parse("2026-11-20T12:00:00Z"));
  const notices = [...residentData.notices.map(m.residentNotice), ...residentData.movements.map(m.pointsNotice)];
  const older = { ...residentData.rows[2], id: "r4", description: "Solicitud anterior al listado reciente" };
  const data = { ...residentData, rows: [...residentData.rows, older] };
  const html = renderToString(h(m.ResidentHome, { user, data, notices, view: "inicio", setView() {}, seen, onCreate() {}, created: null, clearCreated() {}, logout() {} })).replaceAll("<!-- -->", "");
  const shortcuts = /<nav class="resident-shortcuts"[^>]*>(.*?)<\/nav>/s.exec(html)?.[1] || "";
  const titles = [...shortcuts.matchAll(/class="resident-shortcut-title">([^<]+)/g)].map((match) => match[1]);
  assert.deepEqual(titles, ["Mis solicitudes", "Mis citas", "Mis puntos", "Guía ambiental"]);
  assert.equal((shortcuts.match(/class="resident-shortcut-description"/g) || []).length, 4);
  assert.doesNotMatch(shortcuts, /disabled=""|<time|Luis Gómez/);
  assert.match(html, /¡Hola, <span class="home-hero-name">Ana<\/span>!.*home-cta.*Próxima recogida.*Accesos rápidos.*Solicitudes recientes/s);
  assert.match(html, /class="home-cta" data-primary="true"[^>]*>.*?<span>Solicitar recogida<\/span>/s);
  assert.match(html, /class="home-points-chip".*?<span>40 puntos<\/span>/s);
  assert.equal((html.match(/class="request-card"/g) || []).length, 3);
  assert.match(html, /Ver todas/);
  assert.doesNotMatch(html, /Solicitud anterior al listado reciente|class="request-appointment"/);
  // La próxima recogida sale de /community/appointments (responsable real).
  assert.match(html, /22\/11\/2026, 9:00 a\. m\./);
  assert.match(html, /Responsable: Luis Gómez/);
  assert.match(html, /<dt>Visita<\/dt>/);
  assert.match(html, /class="home-request-status" data-tone="scheduled"/);
  assert.match(html, /<span title="r1">#r1<\/span>/);
  // Material real en la tarjeta, no las observaciones.
  assert.match(html, /<h3 class="request-title">Cartón, Botellas plásticas<\/h3>/);
  assert.doesNotMatch(html, /<h3 class="request-title">Llamar antes<\/h3>/);
});

test("historial: todas las solicitudes; las antiguas sin material muestran su descripción", () => {
  const html = renderToString(h(m.HistoryView, { rows: residentData.rows, appointments: residentData.appointments, onNew() {}, onBack() {} })).replaceAll("<!-- -->", "");
  assert.match(html, /3 solicitudes/);
  assert.match(html, /<h3 class="request-title">Solicitud antigua<\/h3>/);
  assert.match(html, /class="request-appointment"/);
});

test("próxima recogida: sin cita confirmada no inventa fecha", () => {
  const html = renderToString(h(m.NextPickup, { appointments: [], pending: 2 })).replaceAll("<!-- -->", "");
  assert.match(html, /Tienes 2 solicitudes esperando/);
  assert.match(html, /class="next-pickup-pending"/);
  assert.doesNotMatch(html, /Mañana|Hoy/);
  assert.match(renderToString(h(m.NextPickup, { appointments: [], pending: 0 })), /Todavía no tienes recogidas programadas/);
});

test("calendario: marca solo días con citas confirmadas y lista las próximas", (context) => {
  context.mock.method(Date, "now", () => Date.parse("2026-11-20T12:00:00Z"));
  const html = renderToString(h(m.CalendarView, { appointments: residentData.appointments, rows: residentData.rows, onBack() {} })).replaceAll("<!-- -->", "");
  assert.match(html, /Mis recogidas programadas/);
  assert.match(html, /Noviembre de 2026/i);
  assert.equal((html.match(/data-has="true"/g) || []).length, 1);
  assert.match(html, /1 recogida programada/);
  assert.match(html, /Luis Gómez/);
  assert.match(html, /22\/11\/2026, 9:00 a\. m\./);
  assert.match(renderToString(h(m.CalendarView, { appointments: [], rows: [], onBack() {} })), /Sin recogidas programadas/);
});

test("calendario: ubica citas en la semana y el mes de Colombia", (context) => {
  context.mock.method(Date, "now", () => Date.parse("2026-11-21T12:00:00Z"));
  const appointments = [
    { ...residentData.appointments[0], scheduled_at: "2026-11-23T04:30:00Z" },
    { ...residentData.appointments[0], collection_id: "r3", scheduled_at: "2026-11-23T05:30:00Z" },
    { ...residentData.appointments[0], collection_id: "r4", scheduled_at: "2026-12-01T03:30:00Z" },
    { ...residentData.appointments[0], collection_id: "r5", scheduled_at: "sin fecha" },
  ];
  const html = renderToString(h(m.CalendarView, { appointments, rows: residentData.rows, onBack() {} }));
  for (const date of ["2026-11-22", "2026-11-23", "2026-11-30"]) {
    assert.match(html, new RegExp(`data-has="true"><time dateTime="${date}"`));
  }
  assert.match(html, /30\/11\/2026, 10:30 p\. m\./);
  assert.doesNotMatch(html, /Invalid Date|sin fecha/);
});

test("puntos: saldo y movimientos reales", () => {
  const html = renderToString(h(m.PointsView, { points: { balance: 40 }, movements: residentData.movements, onBack() {} })).replaceAll("<!-- -->", "");
  assert.match(html, /40/);
  assert.match(html, /recogidas realizadas/);
  assert.match(html, /sujetas a validación de la Fundación Santo Domingo/);
  assert.match(html, /Historial de puntos/);
  assert.match(html, /Puntos por entrega/);
  assert.match(html, /\+40/);
});

test("piloto: una unidad productiva pendiente consulta su historial sin abrir el formulario", () => {
  const business = { ...user, profile: { ...user.profile, kind: "business", role: "business", pilot_enabled: false } };
  const props = { user: business, data: { rows: [] }, view: "historial", setView() {} };
  const blocked = renderToString(h(m.ResidentHome, props));
  assert.match(blocked, /Mis solicitudes/);
  assert.doesNotMatch(blocked, /Solicitar mi primera recogida/);
  const direct = renderToString(h(m.ResidentHome, { ...props, view: "nueva" }));
  assert.match(direct, /Unidad productiva pendiente de habilitación/);
  const allowed = { ...business, profile: { ...business.profile, pilot_enabled: true } };
  assert.match(renderToString(h(m.ResidentHome, { ...props, user: allowed })), /Solicitar mi primera recogida/);
  const pendingHome = renderToString(h(m.ResidentHome, { ...props, view: "inicio" }));
  assert.match(pendingHome, /class="home-cta" data-primary="true" disabled=""/);
  assert.doesNotMatch(pendingHome, /Crear solicitud/);
  assert.equal((pendingHome.match(/disabled=""/g) || []).length, 1);
  const allowedHome = renderToString(h(m.ResidentHome, { ...props, user: allowed, view: "inicio" }));
  assert.doesNotMatch(allowedHome, /disabled=""/);
  assert.match(allowedHome, /Aún no tienes solicitudes.*Crear solicitud/s);
});

test("residentes: los accesos aparecen durante la carga y se puede volver al inicio", () => {
  const props = { user, data: null, setView() {} };
  const home = renderToString(h(m.ResidentHome, { ...props, view: "inicio" }));
  assert.match(home, /Guía ambiental/);
  assert.match(home, /Cargando tus recogidas/);
  assert.match(home, /animate-pulse/);
  assert.doesNotMatch(home, /class="home-points-chip"/);
  assert.doesNotMatch(home, /Todavía no tienes recogidas/);
  const appointments = renderToString(h(m.ResidentHome, { ...props, view: "citas" }));
  assert.match(appointments, /Inicio<\/button>/);
});

test("inicio: el saldo cero es real y los estados desconocidos conservan su texto", () => {
  const row = { ...residentData.rows[0], status: "visit_failed" };
  const html = renderToString(h(m.ResidentHome, {
    user, data: { rows: [row], points: { balance: 0 } }, view: "inicio", setView() {},
  })).replaceAll("<!-- -->", "");
  assert.match(html, /class="home-points-chip".*?<span>0 puntos<\/span>/s);
  assert.match(html, /class="home-request-status" data-tone="unknown".*?visit_failed/s);
});

test("inicio: botones y enlaces visuales reutilizan los destinos existentes", (context) => {
  const destinations = [];
  const previousFrame = globalThis.requestAnimationFrame;
  globalThis.requestAnimationFrame = () => 0;
  context.after(() => {
    if (previousFrame === undefined) delete globalThis.requestAnimationFrame;
    else globalThis.requestAnimationFrame = previousFrame;
  });

  const props = { user, data: residentData, view: "inicio", setView: (id) => destinations.push(id) };
  function* elements(node) {
    if (Array.isArray(node)) {
      for (const child of node) yield* elements(child);
    } else if (node?.props) {
      yield node;
      yield* elements(node.props.children);
    }
  }

  const nodes = [...elements(m.ResidentHome(props))];
  const welcome = nodes.find((node) => node.props.onRequest);
  welcome.props.onRequest();
  welcome.props.onPoints();
  nodes.find((node) => node.type === m.NextPickup).props.onDetails();
  for (const node of nodes.filter((node) => node.props["data-shortcut"])) node.props.onClick();
  nodes.find((node) => node.props.children === "Ver todas").props.onClick();
  const empty = [...elements(m.ResidentHome({ ...props, data: { rows: [] } }))];
  empty.find((node) => node.props.action?.props.children === "Crear solicitud").props.action.props.onClick();
  assert.deepEqual(destinations, ["nueva", "puntos", "historial", "historial", "citas", "puntos", "educacion", "historial", "nueva"]);
});

test("panel del vecino: confirmación real tras crear una solicitud", () => {
  const html = renderToString(h(m.ResidentHome, { user, data: residentData, notices: [], view: "inicio", setView() {}, seen, onCreate() {}, created: "r1", clearCreated() {}, logout() {} }));
  assert.match(html, /¡Solicitud recibida correctamente!/);
  assert.match(html, /data-new="true"/);
});

test("tarjeta: el detalle incluye disponibilidad y observaciones reales", () => {
  const html = renderToString(h(m.RequestCard, { row: residentData.rows[0] }));
  assert.match(html, /Lunes · Mañana/);
  assert.match(html, /Llamar antes/);
  assert.match(html, /aria-expanded="false"/);
});

test("avisos: solo transforma eventos reales y quita el título repetido", () => {
  const n = m.residentNotice(residentData.notices[0]);
  assert.equal(n.kind, "scheduled");
  assert.equal(n.title, "Recogida programada");
  assert.equal(n.text, "Luis");
  assert.equal(n.cita, "2026-11-21T09:00:00-05:00");
  assert.match(renderToString(h(m.NoticeList, { notices: [n] })), /21\/11\/2026, 9:00 a\. m\./);
  const current = m.residentNotice({
    ...residentData.notices[0], message: "Recolección programada. Luis",
    scheduled_at: "2026-11-22T01:30:00Z",
  });
  assert.match(renderToString(h(m.NoticeList, { notices: [current] })), /21\/11\/2026, 8:30 p\. m\./);
  const p = m.pointsNotice(residentData.movements[0]);
  assert.equal(p.kind, "points");
  assert.match(renderToString(h(m.NoticeList, { notices: [n, p] })), /Puntos acreditados/);
  assert.match(renderToString(h(m.NoticeList, { notices: [] })), /Sin avisos por ahora/);
});

test("panel de coordinadora: filtros con conteos y bandeja legible", () => {
  const html = renderToString(h(m.LeaderBoard, { flow: "huerta", data: { rows: leaderRows, notices: [{ solicitud_id: "a", evento: "recibida" }], workers: [{ id: "w", full_name: "Luis Gómez" }], materials: [] }, view: "inicio", setView() {}, perform() {} }));
  for (const text of ["Huerta comunitaria", "Solicitudes de orgánicos", "Pendientes", "Revisadas", "Programadas", "Completadas", "Canceladas", "Cáscaras", "Ver solicitud"]) assert.ok(html.includes(text), text);
  assert.match(html, /aria-selected="true"[^>]*>.*Pendientes/s);
  assert.match(html, /class="ops-item"[^>]*aria-expanded="false"/);
});

test("coordinación de reciclaje: identifica el colectivo aun con la bandeja vacía", () => {
  const html = renderToString(h(m.LeaderBoard, { flow: "reciclaje", data: { rows: [] }, view: "inicio" }));
  assert.match(html, /Colectivo de reciclaje/);
  assert.match(html, /Solicitudes de reciclables/);
  assert.doesNotMatch(html, /Huerta comunitaria/);
});

test("coordinación: el calendario, el directorio de integrantes y los avisos conservan su vista", () => {
  const props = { flow: "huerta", data: { rows: [], notices: [] }, token: "t", setView() {} };
  const rendered = (view) => renderToString(h(m.LeaderBoard, { ...props, view }));
  assert.match(rendered("calendario"), /Calendario de recolecciones/);
  assert.match(rendered("integrantes"), /Integrantes/);
  assert.match(rendered("avisos"), /Sin avisos por ahora/);
  assert.doesNotMatch(rendered("avisos"), /Estados de las solicitudes/);
});

test("coordinación: el resumen permite consultar fechas sin esperar a la bandeja", () => {
  const html = renderToString(h(m.LeaderBoard, { flow: "huerta", data: null, view: "reportes", token: "t" }));
  assert.match(html, /Resumen por período/);
  assert.match(html, /Fecha inicial.*Fecha final.*Consultar resumen.*Consultando solicitudes/s);
  assert.equal((html.match(/type="date"/g) || []).length, 2);
  assert.doesNotMatch(html, /Cargando la bandeja/);
});

test("administración: el directorio abre con búsqueda y el menú permanece cerrado", () => {
  const admin = { ...user, profile: { ...user.profile, role: "admin" } };
  const html = renderToString(h(m.AdminDashboard, { user: admin, token: "t", end() {} }));
  assert.match(html, /Administración/);
  assert.match(html, /Buscar por nombre o cédula/);
  assert.match(html, /Cargando usuarios/);
  assert.match(html, /aria-label="Abrir menú"/);
  assert.doesNotMatch(html, /id="menu-lateral"|admin-sidebar/);
});

test("restauración de sesión: el colectivo y el rol se leen desde /accounts/me", async (context) => {
  const fetch = context.mock.method(globalThis, "fetch");
  let identity = user;
  fetch.mock.mockImplementation(async (url, options) => {
    assert.match(url, /\/accounts\/me$/);
    assert.equal(options.headers.Authorization, "Bearer session-token");
    return { ok: true, json: async () => identity };
  });

  for (const flow of ["huerta", "reciclaje"]) {
    identity = { ...user, collective_id: "collective", collective_flow: flow, profile: { ...user.profile, role: "leader" } };
    const restored = await m.restoreSession("session-token");
    assert.equal(restored.user.collective_flow, flow);
    assert.equal(sessionStorage.getItem("eco.api.session"), "session-token");
  }
  identity = { ...identity, collective_id: null };
  await assert.rejects(m.restoreSession("session-token"), /colectivo autorizado/);
  identity = { ...identity, profile: { ...user.profile, role: "field_worker" } };
  await assert.rejects(m.restoreSession("session-token"), /vinculada a un integrante/);
  identity = { ...identity, worker_id: "w1", collective_id: "c", collective_flow: "reciclaje" };
  assert.equal((await m.restoreSession("session-token")).user.worker_id, "w1");
});

test("detalle de coordinadora: datos, acciones e historial", () => {
  const html = renderToString(h(m.LeaderCard, { row: leaderRows[1], perform() {}, token: "t", workers: [{ id: "w", full_name: "Luis Gómez" }], materials: [{ code: "poda", name: "Poda" }] })).replaceAll("<!-- -->", "");
  for (const text of ["Poda", "Perro bravo", "Luis Gómez", "Reprogramar visita", "Registrar recogida", "Consultar historial", "Registrar aviso a Luis Gómez"]) assert.ok(html.includes(text), text);
});

test("encabezado: avisos y menú lateral cerrado por defecto", () => {
  const html = renderToString(h(m.AppHeader, { user, unread: 2, onNotices() {}, onLogout() {}, menu: [{ id: "inicio", label: "Inicio", onClick() {} }] }));
  assert.match(html, /aria-label="Avisos, 2 nuevos"/);
  assert.match(html, /aria-label="Abrir menú"/);
  assert.match(html, /aria-expanded="false"/);
  assert.doesNotMatch(html, /id="menu-lateral"/);
  assert.match(html, /src="\/marca\/ecoconecta.png"/);
});

test("encabezado del inicio: mantiene el salto y el menú, y anuncia notificaciones", () => {
  const props = { user, residentHome: true, unread: 2, onNotices() {} };
  const html = renderToString(h(m.AppHeader, props));
  assert.match(html, /href="#contenido"/);
  assert.match(html, /aria-label="Notificaciones" aria-description="2 nuevas"/);
  assert.match(html, /class="home-notice-dot" aria-hidden="true"/);
  assert.match(html, /aria-expanded="false" aria-label="Abrir menú"/);
  assert.match(html, /src="\/marca\/ecoconecta.png" alt="[^"]+" width="2172" height="724"/);
  assert.doesNotMatch(renderToString(h(m.AppHeader, { ...props, unread: 0 })), /home-notice-dot/);
});

test("protección de errores: un fallo de render muestra un mensaje, no una pantalla en blanco", () => {
  const boundary = new m.ErrorBoundary({});
  boundary.state = m.ErrorBoundary.getDerivedStateFromError(new Error("boom"));
  const html = renderToString(boundary.render());
  assert.match(html, /Algo no salió como esperábamos/);
  assert.match(html, /Reintentar/);
});

test("recogida completada: resultado trazado a la coordinadora y al recolector", () => {
  const row = { ...leaderRows[1], estado: "recolectada", entrega: { material: "poda", kilos: "2.500", resultado: "total",
    recogida_en: "2026-11-20T15:00:00-05:00", recolector: "w", constancia: "Llamada: 3 bolsas", observaciones: "Material limpio" } };
  const html = renderToString(h(m.LeaderCard, { row, perform() {}, token: "t", workers: [{ id: "w", full_name: "Luis Gómez" }], materials: [{ code: "poda", name: "Poda" }] })).replaceAll("<!-- -->", "");
  for (const text of ["Recogida real", "La realizó", "Luis Gómez", "Constancia (registrada por la coordinadora)", "Llamada: 3 bolsas", "Material limpio", "Poda · 2,5 kg · Total"]) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /Registrar recogida/);
});

test("historial del vecino: se carga bajo demanda desde su propia solicitud", () => {
  const html = renderToString(h(m.RequestTimeline, { id: "r1", token: "t" }));
  assert.match(html, /Ver historial/);
});

test("recolector: solo sus asignaciones, registro y cierre de sesión visible", () => {
  const worker = { id: "w", profile: { full_name: "Hugo Huertero", role: "field_worker" }, collective_flow: "huerta" };
  const rows = [
    { ...leaderRows[1], estado: "programada" },
    { ...leaderRows[2], id: "z", estado: "recolectada", solicitud: { ...leaderRows[0].solicitud, material: "Hojas" }, entrega: { material: "ORG", kilos: "2.5", unidad: "kg", resultado: "total" } },
  ];
  const html = renderToString(h(m.WorkerHome, { user: worker, data: { rows, materials: [{ code: "ORG", name: "Orgánico" }] }, perform() {}, token: "t", logout() {} })).replaceAll("<!-- -->", "");
  for (const text of ["Mis recogidas", "Orgánicos", "Por realizar", "Realizadas", "Cerrar sesión", "Ver recogida", "Registrar recolección", "Calle 3", "300 123 4567"]) assert.ok(html.includes(text), text);
  assert.match(html, /<details class="worker-detail">/);
});

test("guía ambiental pública: orientación de flujo sin inventar rutas ni horarios", () => {
  const html = renderToString(h(m.EducationLibrary, { onBack() {}, backLabel: "Volver a iniciar sesión" }));
  for (const text of ["¿Orgánico o reciclable?", "Residuos orgánicos", "Residuos reciclables", "Volver a iniciar sesión", "Acerca de EcoConecta"]) assert.ok(html.includes(text), text);
});

test("RN-08: un hogar no habilitado para el piloto no abre el formulario", () => {
  const pending = { ...user, profile: { ...user.profile, pilot_enabled: false } };
  const props = { user: pending, data: { rows: [] }, setView() {} };
  const direct = renderToString(h(m.ResidentHome, { ...props, view: "nueva" }));
  assert.match(direct, /Hogar pendiente de habilitación/);
  assert.doesNotMatch(direct, /Solicitar recogida<\/h1>/);
  const home = renderToString(h(m.ResidentHome, { ...props, view: "inicio" }));
  assert.match(home, /class="home-cta" data-primary="true" disabled=""/);
  assert.match(renderToString(h(m.ResidentHome, { ...props, user, view: "nueva" })), /Solicitar recogida/);
});
