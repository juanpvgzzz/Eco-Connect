// Aritmética de semanas con fechas civiles «AAAA-MM-DD» (sin horas ni zona):
// así un cambio de mes o de año no depende de la hora local del dispositivo.
import { bogotaDayKey } from "../../utils/dateTime.js";

const toUtc = (key) => {
  const [y, m, d] = key.split("-").map(Number);
  return Date.UTC(y, m - 1, d);
};
const fromUtc = (ms) => new Date(ms).toISOString().slice(0, 10);

export const addDays = (key, n) => fromUtc(toUtc(key) + n * 864e5);
// Lunes de la semana del día dado (lunes = 0 … domingo = 6).
export const mondayOf = (key) => addDays(key, -((new Date(toUtc(key)).getUTCDay() + 6) % 7));
export const todayKey = () => bogotaDayKey(Date.now());
export const weekDays = (monday) => Array.from({ length: 7 }, (_, i) => addDays(monday, i));

const label = (key, options) =>
  new Intl.DateTimeFormat("es-CO", { timeZone: "UTC", ...options }).format(new Date(toUtc(key)));
export const dayName = (key) => {
  const text = label(key, { weekday: "long" });
  return text.charAt(0).toUpperCase() + text.slice(1);
};
export const dayShort = (key) => label(key, { day: "numeric", month: "short" });
export const rangeLabel = (monday) => {
  const sunday = addDays(monday, 6);
  const sameYear = monday.slice(0, 4) === sunday.slice(0, 4);
  const start = label(monday, sameYear ? { day: "numeric", month: "long" } : { day: "numeric", month: "long", year: "numeric" });
  return `${start} – ${label(sunday, { day: "numeric", month: "long", year: "numeric" })}`;
};

// Hora entera en Bogotá (0–23) de una cita.
export const bogotaHour = (value) =>
  Number(new Intl.DateTimeFormat("en-GB", { timeZone: "America/Bogota", hour: "2-digit", hourCycle: "h23" }).format(new Date(value)));
