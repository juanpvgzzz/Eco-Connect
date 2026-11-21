export const BOGOTA_ZONE = "America/Bogota";

const formatter = (options) => new Intl.DateTimeFormat("es-CO", { timeZone: BOGOTA_ZONE, ...options });
const shortDate = formatter({ year: "numeric", month: "2-digit", day: "2-digit" });
const fullDate = formatter({ dateStyle: "full" });
const month = formatter({ month: "long", year: "numeric" });
const clock = formatter({ hour: "numeric", minute: "2-digit", hourCycle: "h12" });
const inputClock = formatter({ hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const offset = formatter({ timeZoneName: "longOffset" });
const datePattern = /^\d{4}-\d{2}-\d{2}$/;
const localPattern = /^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d{1,3})?)?$/;
const timestampPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/i;

const parts = (format, date) => Object.fromEntries(format.formatToParts(date).map(({ type, value }) => [type, value]));
const plain = (text) => text.replace(/[\u00a0\u202f]/g, " ");

function civilDate(value) {
  // Una fecha de calendario no es medianoche UTC. Usar mediodía solo como
  // soporte para Intl conserva el día civil en Colombia.
  const date = new Date(`${value}T12:00:00Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value ? date : null;
}

function parse(value) {
  if (typeof value === "string") {
    if (datePattern.test(value)) return civilDate(value);
    if (localPattern.test(value)) {
      const timestamp = toBogotaTimestamp(value);
      return timestamp ? new Date(timestamp) : null;
    }
    if (!timestampPattern.test(value) || !civilDate(value.slice(0, 10))) return null;
  } else if (!(value instanceof Date) && typeof value !== "number") return null;
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date : null;
}

const isDateOnly = (value) => typeof value === "string" && datePattern.test(value);

function dateKey(date) {
  const { year, month, day } = parts(shortDate, date);
  return `${year.padStart(4, "0")}-${month}-${day}`;
}

export function bogotaDayKey(value) {
  const date = parse(value);
  return date ? dateKey(date) : "";
}

function inputValue(date) {
  const { hour, minute } = parts(inputClock, date);
  return `${dateKey(date)}T${hour}:${minute}`;
}

export function toBogotaInput(value) {
  const date = parse(value);
  return date && !isDateOnly(value) ? inputValue(date) : "";
}

export function toBogotaTimestamp(value) {
  if (typeof value !== "string" || !localPattern.test(value) || !civilDate(value.slice(0, 10))) return "";
  const local = value.length === 16 ? `${value}:00` : value;
  const approximate = new Date(`${local}Z`);
  const zoneOffset = parts(offset, approximate).timeZoneName.replace(/^GMT/, "");
  const timestamp = `${local}${zoneOffset}`;
  const instant = new Date(timestamp);
  return Number.isFinite(instant.getTime()) && inputValue(instant) === value.slice(0, 16) ? timestamp : "";
}

export function timestampMillis(value) {
  return isDateOnly(value) ? NaN : (parse(value)?.getTime() ?? NaN);
}

export function formatShortDate(value) {
  const date = parse(value);
  return date ? shortDate.format(date) : "";
}

export function formatFullDate(value) {
  const date = parse(value);
  return date ? fullDate.format(date) : "";
}

export function formatMonth(value) {
  const date = parse(value);
  return date ? month.format(date) : "";
}

export function formatTime(value) {
  const date = parse(value);
  return date && !isDateOnly(value) ? plain(clock.format(date)) : "";
}

export function formatDateTime(value) {
  const date = parse(value);
  if (!date) return "";
  const day = shortDate.format(date);
  return isDateOnly(value) ? day : `${day}, ${plain(clock.format(date))}`;
}

export function formatAvailability(value) {
  if (typeof value !== "string") return "";
  const [start, end, ...rest] = value.split("/");
  if (!rest.length && isDateOnly(start) && isDateOnly(end)) {
    const from = formatShortDate(start);
    const until = formatShortDate(end);
    return from && until ? `${from} – ${until}` : "";
  }
  if (!rest.length && Number.isFinite(timestampMillis(start)) && Number.isFinite(timestampMillis(end))) {
    if (bogotaDayKey(start) === bogotaDayKey(end)) {
      return `${formatFullDate(start)}, de ${formatTime(start)} a ${formatTime(end)}`;
    }
    return `${formatDateTime(start)} – ${formatDateTime(end)}`;
  }
  // Los formularios también guardan disponibilidades como texto libre.
  return /^\d{4}-\d{2}-\d{2}(?:T|\/|$)/.test(value) ? formatDateTime(value) : value;
}
