// Disponibilidad del vecino → texto para el campo `disponibilidad` de la API.
// No es una cita: la recogida solo queda programada cuando el colectivo la confirma.

export const DAYS = [
  { id: "lun", label: "Lunes", short: "Lun" },
  { id: "mar", label: "Martes", short: "Mar" },
  { id: "mie", label: "Miércoles", short: "Mié" },
  { id: "jue", label: "Jueves", short: "Jue" },
  { id: "vie", label: "Viernes", short: "Vie" },
  { id: "sab", label: "Sábado", short: "Sáb" },
  { id: "dom", label: "Domingo", short: "Dom" },
];
export const SLOTS = [
  { id: "manana", label: "Mañana", range: "7:00 a. m. a 12:00 m." },
  { id: "tarde", label: "Tarde", range: "12:00 m. a 5:00 p. m." },
];

const listJoin = (items) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} y ${items.at(-1)}`);

export function describeAvailability({ days = [], slots = [], note = "" }) {
  const dayLabels = DAYS.filter((d) => days.includes(d.id)).map((d) => d.label);
  const slotLabels = SLOTS.filter((s) => slots.includes(s.id)).map((s) => `${s.label} (${s.range})`);
  const parts = [];
  if (dayLabels.length) parts.push(dayLabels.length === DAYS.length ? "Todos los días" : listJoin(dayLabels));
  if (slotLabels.length) parts.push(listJoin(slotLabels));
  const extra = note.replace(/\s+/g, " ").trim();
  if (extra) parts.push(`Nota: ${extra}`);
  return parts.join(" · ");
}

export function validateAvailability({ days = [], slots = [], note = "" }) {
  const errors = {};
  if (!days.length) errors.days = "Elige al menos un día.";
  if (!slots.length) errors.slots = "Elige al menos una franja horaria.";
  if (describeAvailability({ days, slots, note }).length > 500) errors.note = "La nota es demasiado larga.";
  return errors;
}
