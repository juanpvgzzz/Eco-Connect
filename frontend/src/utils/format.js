// Estados de la API pública (/community) y de la operación (/recolecciones).
export const nameOf = {
  received: "Recibida", under_review: "En revisión", scheduled: "Programada", collected: "Completada", cancelled: "Cancelada",
  recibida: "Recibida", revision: "En revisión", programada: "Programada", recolectada: "Completada",
  reprogramada: "Reprogramada", cancelada: "Cancelada", visita_fallida: "Visita fallida",
  aviso_recolector: "Aviso al recolector", entrega_directa: "Entrega directa",
  puntos_acreditados: "Puntos acreditados",
};
// Estado normalizado para agrupar y elegir tono e icono.
export const stageOf = {
  received: "pending", recibida: "pending", under_review: "review", revision: "review",
  scheduled: "scheduled", programada: "scheduled", reprogramada: "scheduled",
  collected: "done", recolectada: "done", cancelled: "cancelled", cancelada: "cancelled",
};
export {
  formatAvailability,
  formatDateTime as formatDate,
  formatDateTime as formatWhen,
  formatShortDate as formatDay,
} from "./dateTime.js";
export const formValues = (event) => Object.fromEntries(new FormData(event.currentTarget));
export const sessionKey = import.meta.env.VITE_DEMO_MODE === "true" ? "eco.demo.session" : "eco.api.session";
export const flowOf = (value) => (["organic", "organico", "huerta"].includes(value) ? "organic" : ["recyclable", "reciclable", "reciclaje"].includes(value) ? "recyclable" : null);
export const flowName = { organic: "Orgánico", recyclable: "Reciclable" };
