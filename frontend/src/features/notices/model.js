// Normaliza los avisos reales de la API en una forma común para la interfaz.
// No se crean avisos: solo se transforman los que FastAPI registra.
import { flowName } from "../../utils/format.js";
import { timestampMillis, toBogotaTimestamp } from "../../utils/dateTime.js";

// Títulos que produce FastAPI (collections/postgres.py EVENT_TITLES) → tipo de aviso.
const BY_TITLE = [
  ["Solicitud recibida", "received"],
  ["Solicitud en revisión", "reviewed"],
  ["Solicitud revisada", "reviewed"],
  ["Recolección reprogramada", "rescheduled"],
  ["Recolección programada", "scheduled"],
  ["Visita fallida", "failed"],
  ["Recolección cancelada", "cancelled"],
  ["Recolección completada", "collected"],
  ["Entrega directa registrada", "direct"],
];
const BY_EVENT = {
  recibida: "received", revision: "reviewed", programada: "scheduled", reprogramada: "rescheduled",
  visita_fallida: "failed", cancelada: "cancelled", recolectada: "collected", entrega_directa: "direct",
  aviso_recolector: "workerNotice",
};
export const NOTICE_TITLES = {
  received: "Solicitud recibida",
  reviewed: "Solicitud revisada",
  scheduled: "Recogida programada",
  rescheduled: "Cambio de horario",
  failed: "Visita fallida",
  cancelled: "Recogida cancelada",
  collected: "Recogida completada",
  direct: "Entrega directa registrada",
  workerNotice: "Aviso al recolector registrado",
  points: "Puntos acreditados",
  redeemed: "Canje de puntos",
  other: "Aviso",
};

const kindFromTitle = (title = "") => BY_TITLE.find(([t]) => title.startsWith(t))?.[1] || "other";

// GET /community/notifications → { id, title, message, created_at }
// El mensaje repite el título al inicio; se quita para no duplicarlo.
export function residentNotice(n) {
  const kind = kindFromTitle(n.title);
  let text = n.message || "";
  if (text.startsWith(n.title)) text = text.slice(n.title.length).replace(/^\.\s*/, "");
  let cita = n.scheduled_at;
  // Compatibilidad con avisos anteriores que traían la cita al inicio del texto.
  const legacy = ["scheduled", "rescheduled", "failed"].includes(kind)
    && /^(\d{2})\/(\d{2})\/(\d{4})[ ,]+(\d{2}:\d{2})(?:\.\s*|$)/.exec(text);
  if (legacy) {
    const [, day, month, year, time] = legacy;
    cita ||= toBogotaTimestamp(`${year}-${month}-${day}T${time}`);
    text = text.slice(legacy[0].length);
  }
  return {
    id: "n-" + n.id, kind, title: NOTICE_TITLES[kind] === "Aviso" ? n.title : NOTICE_TITLES[kind],
    text, date: n.created_at, cita,
  };
}

// GET /community/points/movements → { id, points, reason, created_at }
export function pointsNotice(m) {
  const credited = m.points > 0;
  return {
    id: "p-" + m.id,
    kind: credited ? "points" : "redeemed",
    title: NOTICE_TITLES[credited ? "points" : "redeemed"],
    text: credited ? `Recibiste ${m.points} puntos por tu entrega.` : `Usaste ${Math.abs(m.points)} puntos en un canje.`,
    points: m.points,
    date: m.created_at,
  };
}

// GET /recolecciones/avisos → { solicitud_id, evento, cita, motivo } (sin fecha propia)
export function leaderNotice(n, index, rows) {
  const kind = BY_EVENT[n.evento] || "other";
  const row = rows.find((r) => r.id === n.solicitud_id);
  const material = row?.solicitud?.material || row?.entrega?.material;
  return {
    id: `l-${index}-${n.solicitud_id}-${n.evento}`,
    kind,
    title: NOTICE_TITLES[kind] === "Aviso" ? n.evento : NOTICE_TITLES[kind],
    text: [material, row?.flujo && flowName[row.flujo === "huerta" ? "organic" : "recyclable"]].filter(Boolean).join(" · "),
    cita: n.cita,
    reason: n.motivo,
    requestId: n.solicitud_id,
  };
}

export const byDateDesc = (a, b) => (timestampMillis(b.date) || 0) - (timestampMillis(a.date) || 0);
